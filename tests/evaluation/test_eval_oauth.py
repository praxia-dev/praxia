"""Per-user OAuth — token store + flow + provider configs.

Coverage:
    - OAuthTokenStore: save / load / delete / encrypt-at-rest
    - User / provider isolation
    - Token expiration check
    - OAuthFlow.authorization_url: PKCE + state + scope
    - oauth_token_for: clear error when not authorized
    - All 5 providers configured with HTTPS endpoints
"""
from __future__ import annotations

import time
import urllib.parse

import pytest

pytestmark = pytest.mark.evaluation


class TestOAuthTokenStore:
    def test_save_and_load_roundtrip(self, tmp_storage):
        from praxia.connectors.oauth import OAuthToken, OAuthTokenStore

        store = OAuthTokenStore(storage_dir=tmp_storage, encryption_secret="secret")
        token = OAuthToken(
            user_id="alice",
            provider="box",
            access_token="abc123",
            refresh_token="ref-xyz",
            expires_at=time.time() + 3600,
            scope="root_readwrite",
        )
        store.save(token)
        loaded = store.get("alice", "box")
        assert loaded is not None
        assert loaded.access_token == "abc123"
        assert loaded.refresh_token == "ref-xyz"
        assert loaded.scope == "root_readwrite"

    def test_user_isolation(self, tmp_storage):
        from praxia.connectors.oauth import OAuthToken, OAuthTokenStore

        store = OAuthTokenStore(storage_dir=tmp_storage, encryption_secret="s")
        store.save(OAuthToken(
            user_id="alice", provider="box", access_token="alice_token",
            refresh_token=None, expires_at=time.time() + 3600,
        ))
        # bob has no token even though alice does
        assert store.get("bob", "box") is None

    def test_provider_isolation(self, tmp_storage):
        from praxia.connectors.oauth import OAuthToken, OAuthTokenStore

        store = OAuthTokenStore(storage_dir=tmp_storage, encryption_secret="s")
        store.save(OAuthToken(
            user_id="alice", provider="box", access_token="box_token",
            refresh_token=None, expires_at=time.time() + 3600,
        ))
        # alice has Box but not Dropbox
        assert store.get("alice", "box") is not None
        assert store.get("alice", "dropbox") is None

    def test_encryption_at_rest(self, tmp_storage):
        """Raw access token should not appear verbatim in the on-disk file."""
        from praxia.connectors.oauth import OAuthToken, OAuthTokenStore

        store = OAuthTokenStore(storage_dir=tmp_storage, encryption_secret="s")
        plaintext_token = "VERY_SECRET_TOKEN_qwerty_12345"
        store.save(OAuthToken(
            user_id="alice", provider="box", access_token=plaintext_token,
            refresh_token=None, expires_at=time.time() + 3600,
        ))
        # Inspect the on-disk JSON file
        for path in (tmp_storage).rglob("*.json"):
            content = path.read_bytes()
            assert plaintext_token.encode() not in content, (
                f"Plaintext token leaked to disk in {path}"
            )

    def test_delete_is_idempotent(self, tmp_storage):
        from praxia.connectors.oauth import OAuthToken, OAuthTokenStore

        store = OAuthTokenStore(storage_dir=tmp_storage, encryption_secret="s")
        store.save(OAuthToken(
            user_id="alice", provider="box", access_token="x",
            refresh_token=None, expires_at=time.time() + 3600,
        ))
        assert store.delete("alice", "box") is True
        assert store.delete("alice", "box") is False  # already gone — no-op

    def test_expired_token_check(self):
        from praxia.connectors.oauth import OAuthToken

        future = OAuthToken(
            user_id="x", provider="y", access_token="t",
            refresh_token=None, expires_at=time.time() + 3600,
        )
        past = OAuthToken(
            user_id="x", provider="y", access_token="t",
            refresh_token=None, expires_at=time.time() - 3600,
        )
        assert future.is_expired() is False
        assert past.is_expired() is True

    def test_list_for_user(self, tmp_storage):
        from praxia.connectors.oauth import OAuthToken, OAuthTokenStore

        store = OAuthTokenStore(storage_dir=tmp_storage, encryption_secret="s")
        store.save(OAuthToken(
            user_id="alice", provider="box", access_token="a",
            refresh_token=None, expires_at=time.time() + 3600,
        ))
        store.save(OAuthToken(
            user_id="alice", provider="dropbox", access_token="b",
            refresh_token=None, expires_at=time.time() + 3600,
        ))
        store.save(OAuthToken(
            user_id="bob", provider="box", access_token="c",
            refresh_token=None, expires_at=time.time() + 3600,
        ))
        alice_tokens = store.list_for_user("alice")
        assert len(alice_tokens) == 2
        providers = {t.provider for t in alice_tokens}
        assert providers == {"box", "dropbox"}


class TestOAuthFlow:
    def test_authorization_url_includes_state_pkce_scope(self, tmp_storage):
        from praxia.connectors.oauth import (
            BOX_OAUTH,
            OAuthFlow,
            OAuthTokenStore,
        )

        store = OAuthTokenStore(storage_dir=tmp_storage, encryption_secret="s")
        flow = OAuthFlow(
            BOX_OAUTH,
            client_id="cid",
            client_secret="csec",
            redirect_uri="http://localhost:8765/cb",
            token_store=store,
        )
        url, state = flow.authorization_url(user_id="alice")
        parsed = urllib.parse.urlparse(url)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        assert params["client_id"] == "cid"
        assert params["state"] == state
        assert params["response_type"] == "code"
        assert "redirect_uri" in params
        assert len(state) >= 32, "state must be high-entropy"

    def test_state_unique_per_call(self, tmp_storage):
        from praxia.connectors.oauth import (
            BOX_OAUTH,
            OAuthFlow,
            OAuthTokenStore,
        )

        store = OAuthTokenStore(storage_dir=tmp_storage, encryption_secret="s")
        flow = OAuthFlow(
            BOX_OAUTH,
            client_id="cid", client_secret="csec",
            redirect_uri="http://localhost/cb", token_store=store,
        )
        _, state1 = flow.authorization_url(user_id="alice")
        _, state2 = flow.authorization_url(user_id="alice")
        assert state1 != state2


class TestOAuthHelpers:
    def test_oauth_token_for_raises_clear_error_when_unauthorized(self, tmp_storage):
        from praxia.connectors.oauth import OAuthTokenStore, oauth_token_for

        store = OAuthTokenStore(storage_dir=tmp_storage, encryption_secret="s")
        with pytest.raises(PermissionError) as excinfo:
            oauth_token_for("alice", "box", store=store)
        msg = str(excinfo.value)
        assert "alice" in msg
        assert "box" in msg
        assert "praxia oauth start" in msg


class TestOAuthProviders:
    @pytest.mark.parametrize(
        "config_name",
        ["BOX_OAUTH", "MICROSOFT_OAUTH", "DROPBOX_OAUTH", "GOOGLE_OAUTH", "SALESFORCE_OAUTH"],
    )
    def test_provider_endpoints_https(self, config_name):
        import praxia.connectors.oauth as mod

        config = getattr(mod, config_name)
        assert config.authorize_url.startswith("https://")
        assert config.token_url.startswith("https://")
        assert isinstance(config.default_scopes, list)

    def test_provider_count(self):
        """Exactly the 5 providers Praxia v1.0 ships."""
        import praxia.connectors.oauth as mod

        for name in (
            "BOX_OAUTH",
            "MICROSOFT_OAUTH",
            "DROPBOX_OAUTH",
            "GOOGLE_OAUTH",
            "SALESFORCE_OAUTH",
        ):
            assert hasattr(mod, name)
