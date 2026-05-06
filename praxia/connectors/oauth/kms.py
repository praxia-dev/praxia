"""KMS / HSM backed envelope encryption for OAuth tokens.

The default `OAuthTokenStore` uses HMAC-derived symmetric encryption — fine
for development and small self-hosted deployments. Production deployments
should plug in a real KMS so the master key never lives on the application
host.

This module defines a `KmsAdapter` Protocol plus four built-in adapters
discovered through `praxia.extensions.Registry`:

    - "local"  — HKDF / HMAC-derived AES-GCM key (self-contained, default)
    - "aws"    — AWS KMS via boto3 (CMK + GenerateDataKey envelope)
    - "azure"  — Azure Key Vault Keys via azure-identity + azure-keyvault-keys
    - "gcp"    — Google Cloud KMS via google-cloud-kms
    - "vault"  — HashiCorp Vault Transit secrets engine via hvac

Envelope encryption pattern (used by all non-local adapters):

    1. Generate a random 256-bit data key (DEK) per encrypt.
    2. Encrypt the plaintext with the DEK (AES-GCM).
    3. Encrypt the DEK with the KMS key (kms.encrypt).
    4. Store {ciphertext, encrypted_dek, nonce} on disk.
    5. To decrypt: kms.decrypt(encrypted_dek) → DEK → AES-GCM decrypt.

The DEK never lives on disk in plaintext, and the master key never
leaves the KMS / HSM.

Selection:

    # Environment variable
    PRAXIA_KMS_ADAPTER=aws
    PRAXIA_KMS_KEY_ID=arn:aws:kms:us-east-1:...:key/...

    # Or programmatically
    from praxia.connectors.oauth.kms import build_adapter
    adapter = build_adapter("aws", key_id="arn:aws:kms:...")

    store = OAuthTokenStore(storage_dir=..., kms=adapter)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from abc import abstractmethod
from typing import Any, Protocol, runtime_checkable

from praxia.extensions import Registry, lazy

KMS_ADAPTERS: Registry["KmsAdapter"] = Registry(
    name="KMS adapter",
    entry_point_group="praxia.kms_adapters",
)


@runtime_checkable
class KmsAdapter(Protocol):
    """Anything that wraps + unwraps a 256-bit data encryption key.

    Implementations need only two methods. Encryption of the actual
    plaintext happens in the wrapper layer using AES-GCM with the DEK,
    so all adapters share the same on-disk format.
    """

    name: str

    @abstractmethod
    def wrap(self, dek: bytes) -> bytes:
        """Encrypt the data key with the KMS master key."""
        ...

    @abstractmethod
    def unwrap(self, wrapped_dek: bytes) -> bytes:
        """Decrypt a wrapped data key. Returns the raw 32-byte DEK."""
        ...


# --- Adapter: local (HKDF-derived, no external service) ---------------------

class LocalKmsAdapter:
    """Fallback adapter — derives a deterministic key-wrapping key from a
    secret in env. Suitable for dev / single-host deployments. NOT for
    production multi-host or compliance-bound deployments.
    """

    name = "local"

    def __init__(self, *, secret: str | None = None) -> None:
        secret = secret or os.getenv("PRAXIA_TOKEN_ENC_KEY") or os.getenv(
            "PRAXIA_JWT_SECRET", "praxia-dev-only"
        )
        # Derive a stable 256-bit kek from the secret
        self._kek = hashlib.sha256(secret.encode()).digest()

    def wrap(self, dek: bytes) -> bytes:
        # AES-GCM with the kek as the key
        nonce, ct = _aes_gcm_encrypt(self._kek, dek)
        return nonce + ct  # 12-byte nonce + ct+tag

    def unwrap(self, wrapped_dek: bytes) -> bytes:
        if len(wrapped_dek) < 28:  # 12-byte nonce + ≥16-byte ciphertext+tag
            raise ValueError("wrapped DEK too short")
        nonce, ct = wrapped_dek[:12], wrapped_dek[12:]
        return _aes_gcm_decrypt(self._kek, nonce, ct)


# --- Adapter: AWS KMS -------------------------------------------------------

class AwsKmsAdapter:
    """AWS KMS via boto3. Requires `pip install 'praxia[kms-aws]'`.

    Args:
        key_id: ARN, key ID, or alias of the CMK (e.g.,
                "arn:aws:kms:us-east-1:111122223333:key/...",
                "alias/praxia-tokens").
        region: AWS region (else uses AWS_REGION / AWS_DEFAULT_REGION).
    """

    name = "aws"

    def __init__(self, *, key_id: str, region: str | None = None) -> None:
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "boto3 is required for the AWS KMS adapter. "
                "Install with: pip install 'praxia[kms-aws]'"
            ) from e
        self.key_id = key_id
        self._client = boto3.client("kms", region_name=region)

    def wrap(self, dek: bytes) -> bytes:
        resp = self._client.encrypt(KeyId=self.key_id, Plaintext=dek)
        return resp["CiphertextBlob"]

    def unwrap(self, wrapped_dek: bytes) -> bytes:
        resp = self._client.decrypt(CiphertextBlob=wrapped_dek, KeyId=self.key_id)
        return resp["Plaintext"]


# --- Adapter: Azure Key Vault ----------------------------------------------

class AzureKeyVaultAdapter:
    """Azure Key Vault Keys API. Requires `pip install 'praxia[kms-azure]'`.

    Uses RSA-OAEP wrap. The DEK (32 bytes) fits inside an RSA-2048 wrap.
    """

    name = "azure"

    def __init__(self, *, vault_url: str, key_name: str, key_version: str | None = None) -> None:
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore
            from azure.keyvault.keys.crypto import (  # type: ignore
                CryptographyClient, KeyWrapAlgorithm,
            )
        except ImportError as e:
            raise ImportError(
                "azure-keyvault-keys + azure-identity required. "
                "Install with: pip install 'praxia[kms-azure]'"
            ) from e
        self._algo = KeyWrapAlgorithm.rsa_oaep_256
        key_id = f"{vault_url.rstrip('/')}/keys/{key_name}"
        if key_version:
            key_id = f"{key_id}/{key_version}"
        self._client = CryptographyClient(key_id, credential=DefaultAzureCredential())

    def wrap(self, dek: bytes) -> bytes:
        result = self._client.wrap_key(self._algo, dek)
        return result.encrypted_key

    def unwrap(self, wrapped_dek: bytes) -> bytes:
        result = self._client.unwrap_key(self._algo, wrapped_dek)
        return result.key


# --- Adapter: Google Cloud KMS ---------------------------------------------

class GcpKmsAdapter:
    """GCP KMS via google-cloud-kms. Requires `pip install 'praxia[kms-gcp]'`."""

    name = "gcp"

    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        key_ring: str,
        key_name: str,
    ) -> None:
        try:
            from google.cloud import kms  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "google-cloud-kms is required. "
                "Install with: pip install 'praxia[kms-gcp]'"
            ) from e
        self._client = kms.KeyManagementServiceClient()
        self._key_name = self._client.crypto_key_path(
            project_id, location, key_ring, key_name
        )

    def wrap(self, dek: bytes) -> bytes:
        resp = self._client.encrypt(
            request={"name": self._key_name, "plaintext": dek}
        )
        return resp.ciphertext

    def unwrap(self, wrapped_dek: bytes) -> bytes:
        resp = self._client.decrypt(
            request={"name": self._key_name, "ciphertext": wrapped_dek}
        )
        return resp.plaintext


# --- Adapter: HashiCorp Vault Transit --------------------------------------

class VaultTransitAdapter:
    """HashiCorp Vault Transit. Requires `pip install 'praxia[kms-vault]'`.

    Args:
        vault_url: e.g. "https://vault.example.com:8200"
        key_name: transit key name (e.g. "praxia-tokens")
        token: Vault auth token (else from VAULT_TOKEN env)
        mount_point: transit mount point (default "transit")
    """

    name = "vault"

    def __init__(
        self,
        *,
        vault_url: str,
        key_name: str,
        token: str | None = None,
        mount_point: str = "transit",
    ) -> None:
        try:
            import hvac  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "hvac is required for the Vault adapter. "
                "Install with: pip install 'praxia[kms-vault]'"
            ) from e
        self._client = hvac.Client(url=vault_url, token=token or os.getenv("VAULT_TOKEN"))
        self._key_name = key_name
        self._mount = mount_point

    def wrap(self, dek: bytes) -> bytes:
        resp = self._client.secrets.transit.encrypt_data(
            name=self._key_name,
            plaintext=base64.b64encode(dek).decode(),
            mount_point=self._mount,
        )
        # Vault returns "vault:v1:<ciphertext>" — store as bytes
        return resp["data"]["ciphertext"].encode()

    def unwrap(self, wrapped_dek: bytes) -> bytes:
        resp = self._client.secrets.transit.decrypt_data(
            name=self._key_name,
            ciphertext=wrapped_dek.decode(),
            mount_point=self._mount,
        )
        return base64.b64decode(resp["data"]["plaintext"])


# --- AES-GCM helper (standard library only) ---------------------------------

def _aes_gcm_encrypt(key: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    """Returns (nonce, ciphertext+tag)."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(key)
        ct = aesgcm.encrypt(nonce, plaintext, associated_data=None)
        return nonce, ct
    except ImportError:
        # Fallback: pure-Python ChaCha20-Poly1305-equivalent using HMAC
        # NOTE: this is not AES-GCM but provides AEAD-equivalent guarantees
        # for the local adapter only. cryptography is in the base deps so
        # this branch is rarely hit.
        return _hmac_aead_encrypt(key, plaintext)


def _aes_gcm_decrypt(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, associated_data=None)
    except ImportError:
        return _hmac_aead_decrypt(key, nonce, ciphertext)


def _hmac_aead_encrypt(key: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    """Pure-stdlib AEAD using HMAC-SHA256 — last-resort fallback only."""
    nonce = secrets.token_bytes(12)
    keystream = _keystream(key, nonce, len(plaintext))
    ciphertext = bytes(p ^ k for p, k in zip(plaintext, keystream))
    tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()[:16]
    return nonce, ciphertext + tag


def _hmac_aead_decrypt(key: bytes, nonce: bytes, ct_with_tag: bytes) -> bytes:
    if len(ct_with_tag) < 16:
        raise ValueError("ciphertext too short")
    ct, tag = ct_with_tag[:-16], ct_with_tag[-16:]
    expected = hmac.new(key, nonce + ct, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(expected, tag):
        raise ValueError("AEAD tag mismatch")
    keystream = _keystream(key, nonce, len(ct))
    return bytes(c ^ k for c, k in zip(ct, keystream))


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(
            key, nonce + counter.to_bytes(4, "big"), hashlib.sha256
        ).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


# --- Envelope helpers used by OAuthTokenStore ------------------------------

def envelope_encrypt(adapter: KmsAdapter, plaintext: bytes) -> dict[str, str]:
    """Encrypt with a fresh DEK; return JSON-serializable envelope."""
    dek = secrets.token_bytes(32)
    nonce, ct = _aes_gcm_encrypt(dek, plaintext)
    wrapped = adapter.wrap(dek)
    return {
        "v": "1",
        "alg": "aes-gcm",
        "kms": adapter.name,
        "wrapped_dek": base64.b64encode(wrapped).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "ct": base64.b64encode(ct).decode(),
    }


def envelope_decrypt(adapter: KmsAdapter, envelope: dict[str, Any]) -> bytes:
    """Reverse of envelope_encrypt."""
    wrapped = base64.b64decode(envelope["wrapped_dek"])
    nonce = base64.b64decode(envelope["nonce"])
    ct = base64.b64decode(envelope["ct"])
    dek = adapter.unwrap(wrapped)
    return _aes_gcm_decrypt(dek, nonce, ct)


# --- Registry registration --------------------------------------------------

KMS_ADAPTERS.register("local", LocalKmsAdapter)
KMS_ADAPTERS.register("aws", lazy("praxia.connectors.oauth.kms:AwsKmsAdapter"))
KMS_ADAPTERS.register("azure", lazy("praxia.connectors.oauth.kms:AzureKeyVaultAdapter"))
KMS_ADAPTERS.register("gcp", lazy("praxia.connectors.oauth.kms:GcpKmsAdapter"))
KMS_ADAPTERS.register("vault", lazy("praxia.connectors.oauth.kms:VaultTransitAdapter"))


def build_adapter(name: str | None = None, **kwargs: Any) -> KmsAdapter:
    """Factory.

    Resolution order for `name`:
        1. explicit `name=` argument
        2. PRAXIA_KMS_ADAPTER env var
        3. "local"
    """
    name = (name or os.getenv("PRAXIA_KMS_ADAPTER") or "local").lower()
    cls = KMS_ADAPTERS.get(name)
    return cls(**kwargs)


__all__ = [
    "KmsAdapter",
    "KMS_ADAPTERS",
    "LocalKmsAdapter",
    "AwsKmsAdapter",
    "AzureKeyVaultAdapter",
    "GcpKmsAdapter",
    "VaultTransitAdapter",
    "envelope_encrypt",
    "envelope_decrypt",
    "build_adapter",
]
