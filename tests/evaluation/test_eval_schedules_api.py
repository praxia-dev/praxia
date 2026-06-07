"""Tests for /api/v1/schedules + the cron parser.

We don't wait for the background ticker (60s) to fire here — that would
make the suite painfully slow. Instead we test:

1. **CRUD** — create, list, update (toggle enabled), delete.
2. **Cron parsing** — accepted/rejected expressions surface as 200/400.
3. **next_run_at** — populated on create + advanced on update.
4. **Isolation** — Alice can't see Bob's schedules.

The ticker itself is covered by direct unit tests on `next_run` and
`_tick_once` rather than via the API surface.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from praxia.auth.manager import AuthManager  # noqa: E402
from praxia.server.app import create_app  # noqa: E402
from praxia.server.routers.schedules import next_run, parse_cron  # noqa: E402


@pytest.fixture
def server(tmp_path: Path):
    storage = tmp_path / "praxia"
    auth = AuthManager(storage_dir=storage / "auth")
    user, api_key = auth.users.create(username="alice", role="member", password=None)
    app = create_app(storage_dir=storage)
    client = TestClient(app)
    return client, {"X-API-Key": api_key}, user, storage


class TestCronParser:
    def test_wildcard(self):
        m, h, dom, mo, dow = parse_cron("* * * * *")
        assert m == set(range(60))
        assert h == set(range(24))
        assert dom == set(range(1, 32))
        assert mo == set(range(1, 13))
        assert dow == set(range(7))

    def test_step(self):
        m, *_ = parse_cron("*/15 * * * *")
        assert m == {0, 15, 30, 45}

    def test_range_and_list(self):
        _, h, *_ = parse_cron("0 9-12,17 * * *")
        assert h == {9, 10, 11, 12, 17}

    def test_dow_7_normalises_to_0(self):
        *_, dow = parse_cron("0 0 * * 7")
        assert dow == {0}

    @pytest.mark.parametrize("expr", [
        "",                    # empty
        "0",                   # too few fields
        "0 0 0 0 0",           # dom=0 out of range
        "60 0 0 0 0",          # minute=60
        "0 0 32 1 0",          # dom=32
        "0 0 1 1 abc",         # non-numeric
        "0 0 1 1 1/0",         # step=0
    ])
    def test_rejects_malformed(self, expr):
        with pytest.raises(ValueError):
            parse_cron(expr)


class TestNextRun:
    def test_top_of_next_hour(self):
        # Every hour at minute 0.
        from_t = datetime(2026, 6, 7, 9, 30, 0)
        n = next_run("0 * * * *", from_t)
        assert n == datetime(2026, 6, 7, 10, 0, 0)

    def test_skips_to_next_matching_day(self):
        # 9:00 Mon-Fri only — Sat → Mon.
        sat = datetime(2026, 6, 6, 9, 30, 0)  # 2026-06-06 is a Saturday
        n = next_run("0 9 * * 1-5", sat)
        assert n is not None
        assert n.weekday() == 0  # Monday


class TestCRUD:
    def test_create_validates_cron(self, server):
        client, hdr, _, _ = server
        r = client.post("/api/v1/schedules", json={"cron": "bogus", "prompt": "hi"}, headers=hdr)
        assert r.status_code == 400

    def test_create_validates_prompt(self, server):
        client, hdr, _, _ = server
        r = client.post("/api/v1/schedules", json={"cron": "0 9 * * *", "prompt": "   "}, headers=hdr)
        assert r.status_code == 400

    def test_create_list_update_delete(self, server):
        client, hdr, _, _ = server
        r = client.post(
            "/api/v1/schedules",
            json={"cron": "0 9 * * *", "prompt": "morning brief"},
            headers=hdr,
        )
        assert r.status_code == 200
        rec = r.json()
        assert rec["next_run_at"] is not None
        assert rec["enabled"] is True

        listing = client.get("/api/v1/schedules", headers=hdr).json()
        assert any(s["id"] == rec["id"] for s in listing["schedules"])

        sid = rec["id"]
        prev_next = rec["next_run_at"]
        # Change cron; next_run_at should be recomputed (different cron).
        r = client.patch(
            f"/api/v1/schedules/{sid}",
            json={"cron": "0 0 * * *"},  # midnight, not 9am
            headers=hdr,
        )
        assert r.status_code == 200
        new_rec = r.json()
        assert new_rec["cron"] == "0 0 * * *"
        assert new_rec["next_run_at"] is not None
        assert new_rec["next_run_at"] != prev_next

        # Toggle disabled.
        r = client.patch(f"/api/v1/schedules/{sid}", json={"enabled": False}, headers=hdr)
        assert r.json()["enabled"] is False

        # Delete.
        r = client.delete(f"/api/v1/schedules/{sid}", headers=hdr)
        assert r.status_code == 200 and r.json()["deleted"] is True
        assert client.get("/api/v1/schedules", headers=hdr).json()["schedules"] == []

    def test_isolated_by_user(self, server):
        client, hdr_a, _, storage = server
        auth = AuthManager(storage_dir=storage / "auth")
        _bob, bob_key = auth.users.create(username="bob", role="member", password=None)
        hdr_b = {"X-API-Key": bob_key}

        client.post("/api/v1/schedules", json={"cron": "0 * * * *", "prompt": "a"}, headers=hdr_a)
        client.post("/api/v1/schedules", json={"cron": "0 * * * *", "prompt": "b"}, headers=hdr_b)

        listing_a = client.get("/api/v1/schedules", headers=hdr_a).json()["schedules"]
        listing_b = client.get("/api/v1/schedules", headers=hdr_b).json()["schedules"]
        assert len(listing_a) == 1 and listing_a[0]["prompt"] == "a"
        assert len(listing_b) == 1 and listing_b[0]["prompt"] == "b"

    def test_404_on_unknown_schedule(self, server):
        client, hdr, _, _ = server
        assert client.patch("/api/v1/schedules/nope", json={"enabled": False}, headers=hdr).status_code == 404
        assert client.delete("/api/v1/schedules/nope", headers=hdr).status_code == 404
