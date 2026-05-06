"""Webhook subscription registry + dispatch + HMAC signing."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib import error, request

_log = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Praxia-Webhook/1.0",
}


@dataclass
class Subscription:
    id: str
    url: str
    event: str = "*"
    active: bool = True
    secret: str = ""        # if set, every delivery includes X-Praxia-Signature
    labels: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class WebhookDelivery:
    id: str
    subscription_id: str
    event: str
    status_code: int | None
    success: bool
    error: str = ""
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


def sign_payload(payload: bytes, secret: str) -> str:
    """HMAC-SHA256 of the body. Receiver verifies via header."""
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_payload(payload: bytes, secret: str, signature: str) -> bool:
    """Constant-time verify. Header value is the X-Praxia-Signature contents."""
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature)


class WebhookManager:
    """Persistent subscriptions + dispatch."""

    def __init__(
        self,
        storage_dir: Path | str = ".praxia/webhooks",
        *,
        max_workers: int = 8,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.dir = Path(storage_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.subs_path = self.dir / "subscriptions.json"
        self.log_path = self.dir / "deliveries.jsonl"
        self.timeout = timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()

    # --- CRUD --------------------------------------------------------------

    def add(
        self, *, url: str, event: str = "*", secret: str = "",
        labels: dict[str, str] | None = None,
    ) -> Subscription:
        sub = Subscription(
            id=str(uuid.uuid4()), url=url, event=event,
            secret=secret or "", labels=labels or {},
        )
        with self._lock:
            subs = self._read_subs()
            subs.append(sub)
            self._write_subs(subs)
        return sub

    def remove(self, sub_id: str) -> bool:
        with self._lock:
            subs = self._read_subs()
            new = [s for s in subs if s.id != sub_id]
            if len(new) == len(subs):
                return False
            self._write_subs(new)
            return True

    def list(self) -> list[Subscription]:
        return self._read_subs()

    def set_active(self, sub_id: str, active: bool) -> Subscription | None:
        with self._lock:
            subs = self._read_subs()
            for s in subs:
                if s.id == sub_id:
                    s.active = active
                    self._write_subs(subs)
                    return s
        return None

    # --- Dispatch ----------------------------------------------------------

    def dispatch(
        self, event: str, payload: dict[str, Any], *, sync: bool = False
    ) -> list[WebhookDelivery]:
        """Send to all active subscriptions matching `event`.

        sync=False (default) → fire and return immediately; deliveries log
        async. sync=True → wait for each delivery (useful in tests + critical
        events).
        """
        subs = [
            s for s in self.list()
            if s.active and (s.event == "*" or s.event == event)
        ]
        if not subs:
            return []

        body = json.dumps({
            "event": event,
            "payload": payload,
            "timestamp": time.time(),
        }, ensure_ascii=False).encode("utf-8")

        deliveries: list[WebhookDelivery] = []
        if sync:
            for s in subs:
                deliveries.append(self._deliver(s, event, body))
        else:
            for s in subs:
                self._executor.submit(self._deliver, s, event, body)
        return deliveries

    def _deliver(self, sub: Subscription, event: str, body: bytes) -> WebhookDelivery:
        start = time.time()
        headers = dict(DEFAULT_HEADERS)
        headers["X-Praxia-Event"] = event
        headers["X-Praxia-Delivery"] = str(uuid.uuid4())
        if sub.secret:
            headers["X-Praxia-Signature"] = sign_payload(body, sub.secret)

        req = request.Request(sub.url, data=body, headers=headers, method="POST")
        result = WebhookDelivery(
            id=headers["X-Praxia-Delivery"],
            subscription_id=sub.id,
            event=event,
            status_code=None,
            success=False,
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                result.status_code = resp.status
                result.success = 200 <= resp.status < 300
        except error.HTTPError as e:
            result.status_code = e.code
            result.error = f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
        result.duration_ms = (time.time() - start) * 1000
        self._log_delivery(result)
        return result

    def deliveries(self, *, limit: int = 100) -> list[WebhookDelivery]:
        if not self.log_path.exists():
            return []
        out: list[WebhookDelivery] = []
        with self.log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(WebhookDelivery(**json.loads(line)))
                except Exception:
                    continue
        return out[-limit:]

    # --- Storage helpers --------------------------------------------------

    def _read_subs(self) -> list[Subscription]:
        if not self.subs_path.exists():
            return []
        try:
            data = json.loads(self.subs_path.read_text(encoding="utf-8"))
            return [Subscription(**d) for d in data]
        except Exception:
            return []

    def _write_subs(self, subs: list[Subscription]) -> None:
        data = [asdict(s) for s in subs]
        tmp = self.subs_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.subs_path)

    def _log_delivery(self, d: WebhookDelivery) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(d), ensure_ascii=False) + "\n")
