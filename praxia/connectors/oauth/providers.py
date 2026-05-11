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

# --- Notion -------------------------------------------------------------

NOTION_OAUTH = OAuthProviderConfig(
    name="notion",
    authorize_url="https://api.notion.com/v1/oauth/authorize",
    token_url="https://api.notion.com/v1/oauth/token",
    default_scopes=[],   # Notion uses workspace-level grants, not scopes
    extra_authorize_params={"owner": "user"},
    pkce=False,           # Notion does not support PKCE; uses HTTP Basic auth at token endpoint
)

# --- Atlassian (Confluence + Jira share OAuth) -------------------------

ATLASSIAN_OAUTH = OAuthProviderConfig(
    name="atlassian",
    authorize_url="https://auth.atlassian.com/authorize",
    token_url="https://auth.atlassian.com/oauth/token",
    default_scopes=[
        "read:confluence-content.summary",
        "read:confluence-content.all",
        "write:confluence-content",
        "read:jira-work",
        "write:jira-work",
        "offline_access",
    ],
    extra_authorize_params={"audience": "api.atlassian.com", "prompt": "consent"},
    pkce=True,
)

# --- Slack -------------------------------------------------------------

SLACK_OAUTH = OAuthProviderConfig(
    name="slack",
    authorize_url="https://slack.com/oauth/v2/authorize",
    token_url="https://slack.com/api/oauth.v2.access",
    revoke_url="https://slack.com/api/auth.revoke",
    default_scopes=[
        "channels:history",
        "channels:read",
        "groups:history",
        "groups:read",
        "im:history",
        "files:read",
        "files:write",
        "chat:write",
        "users:read",
        "search:read",
    ],
    pkce=False,           # Slack v2 OAuth uses confidential client flow
)

# --- GitHub ------------------------------------------------------------

GITHUB_OAUTH = OAuthProviderConfig(
    name="github",
    authorize_url="https://github.com/login/oauth/authorize",
    token_url="https://github.com/login/oauth/access_token",
    default_scopes=["repo", "read:org", "read:user"],
    pkce=False,
)

# --- HubSpot -----------------------------------------------------------

HUBSPOT_OAUTH = OAuthProviderConfig(
    name="hubspot",
    authorize_url="https://app.hubspot.com/oauth/authorize",
    token_url="https://api.hubapi.com/oauth/v1/token",
    default_scopes=[
        "crm.objects.contacts.read",
        "crm.objects.contacts.write",
        "crm.objects.companies.read",
        "crm.objects.deals.read",
        "crm.objects.deals.write",
    ],
    pkce=False,
)

# --- Zendesk -----------------------------------------------------------

ZENDESK_OAUTH = OAuthProviderConfig(
    name="zendesk",
    # Subdomain-specific. Operators must template the URL with their tenant
    # subdomain at runtime (or set PRAXIA_ZENDESK_SUBDOMAIN env var).
    authorize_url="https://{subdomain}.zendesk.com/oauth/authorizations/new",
    token_url="https://{subdomain}.zendesk.com/oauth/tokens",
    default_scopes=["read", "write"],
    pkce=True,
)

# --- Linear -----------------------------------------------------------

LINEAR_OAUTH = OAuthProviderConfig(
    name="linear",
    authorize_url="https://linear.app/oauth/authorize",
    token_url="https://api.linear.app/oauth/token",
    default_scopes=["read", "write"],
    pkce=False,
)

# --- Cybozu kintone ---------------------------------------------------
# kintone OAuth 2.0 (Authorization Code). Like Zendesk, the endpoints
# embed the tenant subdomain ({subdomain}.cybozu.com), so callers must
# pass `url_params={"subdomain": "<tenant>"}` when building the flow.

KINTONE_OAUTH = OAuthProviderConfig(
    name="kintone",
    authorize_url="https://{subdomain}.cybozu.com/oauth2/authorization",
    token_url="https://{subdomain}.cybozu.com/oauth2/token",
    default_scopes=[
        "k:app_record:read",
        "k:app_record:write",
        "k:app_settings:read",
        "k:file:read",
        "k:file:write",
    ],
    pkce=False,  # Cybozu uses HTTP Basic auth at the token endpoint
)


PROVIDERS_BY_NAME: dict[str, OAuthProviderConfig] = {
    p.name: p for p in (
        BOX_OAUTH, MICROSOFT_OAUTH, DROPBOX_OAUTH, GOOGLE_OAUTH, SALESFORCE_OAUTH,
        NOTION_OAUTH, ATLASSIAN_OAUTH, SLACK_OAUTH, GITHUB_OAUTH, HUBSPOT_OAUTH,
        ZENDESK_OAUTH, LINEAR_OAUTH, KINTONE_OAUTH,
    )
}
