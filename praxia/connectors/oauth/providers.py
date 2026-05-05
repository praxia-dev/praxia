"""OAuth provider configurations — endpoints, scopes, peculiarities."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OAuthProviderConfig:
    """Per-provider OAuth 2.0 configuration."""

    name: str
    authorize_url: str
    token_url: str
    revoke_url: str | None = None
    default_scopes: list[str] = field(default_factory=list)
    # Some providers (Salesforce instance URLs, Box JWT, etc.) need extras
    # passed at the authorization step or returned in the token response.
    extra_authorize_params: dict[str, str] = field(default_factory=dict)
    # PKCE recommended for public clients; required by some providers
    pkce: bool = True
    # Some providers return token expiry in ID-token form vs. expires_in
    expires_in_field: str = "expires_in"


# --- Box ----------------------------------------------------------------

BOX_OAUTH = OAuthProviderConfig(
    name="box",
    authorize_url="https://account.box.com/api/oauth2/authorize",
    token_url="https://api.box.com/oauth2/token",
    revoke_url="https://api.box.com/oauth2/revoke",
    default_scopes=["root_readwrite"],
    pkce=False,  # Box does not require PKCE for confidential clients
)

# --- Microsoft (Entra ID for SharePoint / OneDrive) ---------------------

MICROSOFT_OAUTH = OAuthProviderConfig(
    name="microsoft",
    authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
    default_scopes=[
        "offline_access",
        "User.Read",
        "Files.ReadWrite.All",
        "Sites.ReadWrite.All",
    ],
    pkce=True,
)

# --- Dropbox ------------------------------------------------------------

DROPBOX_OAUTH = OAuthProviderConfig(
    name="dropbox",
    authorize_url="https://www.dropbox.com/oauth2/authorize",
    token_url="https://api.dropboxapi.com/oauth2/token",
    revoke_url="https://api.dropboxapi.com/2/auth/token/revoke",
    default_scopes=[
        "files.metadata.read",
        "files.content.read",
        "files.content.write",
    ],
    extra_authorize_params={"token_access_type": "offline"},
    pkce=True,
)

# --- Google (Drive) -----------------------------------------------------

GOOGLE_OAUTH = OAuthProviderConfig(
    name="google",
    authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
    token_url="https://oauth2.googleapis.com/token",
    revoke_url="https://oauth2.googleapis.com/revoke",
    default_scopes=[
        "https://www.googleapis.com/auth/drive",
    ],
    extra_authorize_params={"access_type": "offline", "prompt": "consent"},
    pkce=True,
)

# --- Salesforce ---------------------------------------------------------

SALESFORCE_OAUTH = OAuthProviderConfig(
    name="salesforce",
    authorize_url="https://login.salesforce.com/services/oauth2/authorize",
    token_url="https://login.salesforce.com/services/oauth2/token",
    revoke_url="https://login.salesforce.com/services/oauth2/revoke",
    default_scopes=["api", "refresh_token", "offline_access"],
    pkce=True,
)


PROVIDERS_BY_NAME: dict[str, OAuthProviderConfig] = {
    p.name: p for p in (BOX_OAUTH, MICROSOFT_OAUTH, DROPBOX_OAUTH, GOOGLE_OAUTH, SALESFORCE_OAUTH)
}
