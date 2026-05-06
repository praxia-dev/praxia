"""Shared internal helpers for built-in connectors.

These were factored out after observing the same 4-line OAuth-resolution
block and the same bucket/key splitting in many connectors. Extracting
them reduces duplication and makes the connector pattern uniform.

Public API is intentionally minimal — callers are individual connector
modules, not user code.
"""
from __future__ import annotations

from typing import Any


def resolve_oauth_token(
    access_token: str | None,
    user_id: str | None,
    provider: str,
    *,
    error_hint: str | None = None,
) -> str:
    """Resolve a per-user-OAuth access token, with a clear error if missing.

    Replaces the 4-line pattern that was repeated across every OAuth-using
    connector:

        if user_id and not access_token:
            from praxia.connectors.oauth import oauth_token_for
            access_token = oauth_token_for(user_id, provider).access_token
        if not access_token:
            raise ValueError("Provide access_token or user_id (...).")

    Args:
        access_token: explicit token if the caller already has one
        user_id: Praxia user id (looks up the encrypted token store)
        provider: OAuth provider name (must match providers.PROVIDERS_BY_NAME)
        error_hint: optional extra text appended to the error message

    Returns:
        The resolved access token (str).

    Raises:
        ValueError: when neither argument resolves to a token.
        PermissionError: when user_id is given but the user has no token
                         for that provider (delegated from oauth_token_for).
    """
    if user_id and not access_token:
        # Lazy import — avoids a hard dependency cycle when the OAuth
        # subsystem isn't loaded yet.
        from praxia.connectors.oauth import oauth_token_for
        access_token = oauth_token_for(user_id, provider).access_token
    if not access_token:
        msg = f"Provide access_token or user_id (with a stored {provider} OAuth token)."
        if error_hint:
            msg += " " + error_hint
        raise ValueError(msg)
    return access_token


def split_bucket_path(path: str) -> tuple[str, str]:
    """Split "<bucket>/<key>" into a (bucket, key) tuple.

    Used by S3 / Azure Blob / GCS connectors. Empty key for bucket-only
    paths (e.g. "my-bucket" → ("my-bucket", "")) so list operations work.
    """
    if "/" not in path:
        return path, ""
    bucket, _, rest = path.partition("/")
    return bucket, rest


__all__ = ["resolve_oauth_token", "split_bucket_path"]
