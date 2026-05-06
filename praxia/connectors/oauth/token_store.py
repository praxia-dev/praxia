"""Per-user OAuth token storage with automatic refresh.

Stores `OAuthToken` records keyed by `(user_id, provider)`. Tokens are
encrypted at rest with envelope encryption: a fresh 256-bit data key
per write, AES-GCM payload encryption, and the data key wrapped by a
configurable `KmsAdapter` (local / AWS KMS / Azure Key Vault / GCP KMS
/ HashiCorp Vault).

On read, expired tokens are refreshed transparently if a refresh_token
is present.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from praxia.connectors.oauth.kms import (
    KmsAdapter,
    build_adapter,
    envelope_decrypt,
    envelope_encrypt,
)
from praxia.connectors.oauth.providers import PROVIDERS_BY_NAME


@dataclass
class OAuthToken:
    """A user's live OAuth credentials for one provider."""

    user_id: str
    provider: str
    access_token: str
    token_type: str = "Bearer"
    refresh_token: str | None = None
    expires_at: float = 0.0  # epoch seconds; 0 = unknown / never expires
    scope: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, *, leeway_seconds: int = 60) -> bool:
        if not self.expires_at:
            return False
        return time.time() + leeway_seconds >= self.expires_at


class OAuthTokenStore:
    """Encrypted on-disk per-user token catalog.

    Storage layout:
        <storage_dir>/oauth_tokens.jsonl
        Each line is one envelope-encrypted token blob (JSON).

    Encryption: AES-GCM with a fresh 256-bit data key per write. The data
    key is wrapped by the configured `KmsAdapter` — `local` (default,
    HKDF from a secret), `aws` (KMS), `azure` (Key Vault), `gcp` (Cloud
    KMS), or `vault` (HashiCorp Vault Transit).

    Args:
        storage_dir: where the encrypted JSONL lives.
        encryption_secret: legacy — only used by the local adapter.
        kms: an explicit `KmsAdapter` instance (production path). If
             None, builds one from `PRAXIA_KMS_ADAPTER` (default
             "local").
    """

    def __init__(
        self,
        storage_dir: Path | str = ".praxia/auth",
        *,
        encryption_secret: str | None = None,
        kms: KmsAdapter | None = None,
    ) -> None:
        self.dir = Path(storage_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "oauth_tokens.jsonl"
        self._secret = (
            encryption_secret
            or os.getenv("PRAXIA_TOKEN_ENC_KEY")
            or os.getenv("PRAXIA_JWT_SECRET", "praxia-dev-only")
        ).encode()
        # KMS adapter for envelope encryption. For local adapter, pass the
        # secret through; other adapters take their own kwargs (see kms.py).
        if kms is None:
            adapter_name = os.getenv("PRAXIA_KMS_ADAPTER", "local").lower()
            if adapter_name == "local":
                kms = build_adapter("local", secret=self._secret.decode())
            else:
                kms = build_adapter(adapter_name)
        self._kms = kms

    # --- CRUD --------------------------------------------------------------

    def save(self, token: OAuthToken) -> None:
        existing = [t for t in self.list_all() if not (t.user_id == token.user_id and t.provider == token.provider)]
        existing.append(token)
        with self.path.open("w", encoding="utf-8") as f:
            for t in existing:
                f.write(self._encrypt_line(t) + "\n")

    def get(self, user_id: str, provider: str) -> OAuthToken | None:
        for t in self.list_all():
            if t.user_id == user_id and t.provider == provider:
                return t
        return None

    def delete(self, user_id: str, provider: str) -> bool:
        existing = self.list_all()
        filtered = [t for t in existing if not (t.user_id == user_id and t.provider == provider)]
        if len(filtered) == len(existing):
            return False
        with self.path.open("w", encoding="utf-8") as f:
            for t in filtered:
                f.write(self._encrypt_line(t) + "\n")
        return True

    def list_all(self) -> list[OAuthToken]:
        if not self.path.exists():
            return []
        out: list[OAuthToken] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                token = self._decrypt_line(line)
                if token:
                    out.append(token)
        return out

    def list_for_user(self, user_id: str) -> list[OAuthToken]:
        return [t for t in self.list_all() if t.user_id == user_id]

    # --- Refresh -----------------------------------------------------------

    def refresh(self, token: OAuthToken, *, client_id: str, client_secret: str) -> OAuthToken:
        """Exchange refresh_token for a new access_token. Saves on success."""
        if not token.refresh_token:
            raise RuntimeError(
                f"No refresh_token for user={token.user_id} provider={token.provider}; "
                f"user must re-authorize"
            )
        provider = PROVIDERS_BY_NAME.get(token.provider)
        if not provider:
            raise ValueError(f"Unknown provider: {token.provider}")

        body = urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            }
        ).encode()
        req = urllib.request.Request(
            provider.token_url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        token.access_token = data["access_token"]
        if "refresh_token" in data:  # rotated refresh token (e.g., Salesforce)
            token.refresh_token = data["refresh_token"]
        if provider.expires_in_field in data:
            token.expires_at = time.time() + int(data[provider.expires_in_field])
        token.extra.update({k: v for k, v in data.items() if k not in ("access_token", "refresh_token", "expires_in")})

        self.save(token)
        return token

    # --- Encryption (envelope; data key wrapped by KMS adapter) -----------

    def _encrypt_line(self, token: OAuthToken) -> str:
        plain = json.dumps(asdict(token), ensure_ascii=False).encode()
        envelope = envelope_encrypt(self._kms, plain)
        return json.dumps(envelope, separators=(",", ":"))

    def _decrypt_line(self, line: str) -> OAuthToken | None:
        line = line.strip()
        if not line:
            return None
        try:
            # New format: JSON envelope
            if line.startswith("{"):
                envelope = json.loads(line)
                plain = envelope_decrypt(self._kms, envelope)
                return OAuthToken(**json.loads(plain.decode()))
            # Legacy format: bare base64 from v0.1 — try the legacy decoder
            return self._decrypt_legacy(line)
        except Exception:
            return None

    def _decrypt_legacy(self, line: str) -> OAuthToken | None:
        """Decode tokens written by the v0.1 (HMAC keystream) format.

        Kept for backward compat so users upgrading don't have to
        re-authorize. Re-saving any token rewrites it in the new envelope
        format.
        """
        try:
            ciphertext = base64.b64decode(line)
            keystream = self._legacy_keystream(len(ciphertext))
            plain = bytes(c ^ k for c, k in zip(ciphertext, keystream))
            return OAuthToken(**json.loads(plain.decode()))
        except Exception:
            return None

    def _legacy_keystream(self, length: int) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < length:
            block = hmac.new(
                self._secret, f"|{counter}".encode(), hashlib.sha256
            ).digest()
            out.extend(block)
            counter += 1
        return bytes(out[:length])


# --- Convenience helper -----------------------------------------------------

def oauth_token_for(
    user_id: str,
    provider: str,
    *,
    store: OAuthTokenStore | None = None,
    auto_refresh: bool = True,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> OAuthToken:
    """Return a live access token for `user_id` on `provider`.

    Auto-refreshes if expired. Raises if the user has never authorized
    this provider.

    Args:
        client_id / client_secret: required only when auto_refresh and the
                                    token is actually expired. Read from
                                    env (PRAXIA_OAUTH_<PROVIDER>_CLIENT_ID/
                                    SECRET) by default.
    """
    store = store or OAuthTokenStore()
    token = store.get(user_id, provider)
    if not token:
        raise PermissionError(
            f"User {user_id} has not authorized {provider}. "
            f"Run: praxia oauth start {provider} --user-id {user_id}"
        )
    if token.is_expired() and auto_refresh:
        cid = client_id or os.getenv(f"PRAXIA_OAUTH_{provider.upper()}_CLIENT_ID")
        csec = client_secret or os.getenv(f"PRAXIA_OAUTH_{provider.upper()}_CLIENT_SECRET")
        if not (cid and csec):
            raise RuntimeError(
                f"Token for {user_id}/{provider} expired but no client credentials available. "
                f"Set PRAXIA_OAUTH_{provider.upper()}_CLIENT_ID and _CLIENT_SECRET."
            )
        token = store.refresh(token, client_id=cid, client_secret=csec)
    return token
