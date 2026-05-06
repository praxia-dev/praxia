"""User-delegated OAuth 2.0 for connectors.

Each Praxia user authenticates against the external system (Box,
Microsoft 365, Google Drive, Dropbox, Salesforce, etc.) with their
**own credentials**. Their access token is stored per-user, refreshed
automatically, and used when that user invokes the connector.

This means the external system's native ACL is enforced **per Praxia
user** — alice can only see Box folders alice has access to, even if
bob is on the same Praxia install.

Components:

  - `OAuthTokenStore`  — per-user token persistence (encrypted at rest)
  - `OAuthFlow`        — Authorization Code + PKCE handler
  - `OAuthProvider`    — provider-specific config (Box / Microsoft / ...)
  - `oauth_token_for`  — helper resolving user_id → live access token,
                         auto-refreshing if expired
"""
from praxia.connectors.oauth.flow import OAuthFlow, OAuthState
from praxia.connectors.oauth.state_store import PersistentStateStore
from praxia.connectors.oauth.kms import (
    KMS_ADAPTERS,
    KmsAdapter,
    LocalKmsAdapter,
    build_adapter,
    envelope_decrypt,
    envelope_encrypt,
)
from praxia.connectors.oauth.providers import (
    BOX_OAUTH,
    DROPBOX_OAUTH,
    GOOGLE_OAUTH,
    MICROSOFT_OAUTH,
    SALESFORCE_OAUTH,
    OAuthProviderConfig,
)
from praxia.connectors.oauth.token_store import (
    OAuthToken,
    OAuthTokenStore,
    oauth_token_for,
)

__all__ = [
    "OAuthFlow",
    "OAuthState",
    "PersistentStateStore",
    "OAuthProviderConfig",
    "OAuthToken",
    "OAuthTokenStore",
    "oauth_token_for",
    "BOX_OAUTH",
    "MICROSOFT_OAUTH",
    "DROPBOX_OAUTH",
    "GOOGLE_OAUTH",
    "SALESFORCE_OAUTH",
    # KMS
    "KmsAdapter",
    "KMS_ADAPTERS",
    "LocalKmsAdapter",
    "build_adapter",
    "envelope_encrypt",
    "envelope_decrypt",
]
