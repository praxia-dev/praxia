"""Email connector — IMAP read + SMTP send (generic) + Gmail / Microsoft Graph variants.

Three backends in one connector:

    backend="imap"     → standard IMAP4 over SSL + SMTP for sending
    backend="gmail"    → Gmail API (uses Google OAuth token)
    backend="outlook"  → Microsoft Graph mail (uses Microsoft OAuth token)

Path semantics:
    pull:  "<folder>:<query>"  — e.g. "INBOX:from:bob@example.com"
           "<folder>"           — recent messages in folder
    push:  "<to_email>"         — sends a new message; subject from
                                  ConnectorItem.name, body from .content

Env fallback for IMAP/SMTP (when not using OAuth):
    PRAXIA_CONN_EMAIL_IMAP_HOST / PORT
    PRAXIA_CONN_EMAIL_SMTP_HOST / PORT
    PRAXIA_CONN_EMAIL_USERNAME
    PRAXIA_CONN_EMAIL_PASSWORD
"""
from __future__ import annotations

import email
import email.message
import imaplib
import os
import smtplib
import ssl
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any

from praxia.connectors.base import Connector, ConnectorItem


class EmailConnector:
    name = "email"

    def __init__(
        self,
        *,
        backend: str = "imap",
        # IMAP / SMTP
        imap_host: str | None = None,
        imap_port: int = 993,
        smtp_host: str | None = None,
        smtp_port: int = 587,
        username: str | None = None,
        password: str | None = None,
        # OAuth backends
        access_token: str | None = None,
        user_id: str | None = None,
        from_address: str | None = None,
    ) -> None:
        self.backend = backend
        self._from = from_address or username

        if backend == "imap":
            self._init_imap(imap_host, imap_port, smtp_host, smtp_port, username, password)
        elif backend == "gmail":
            self._init_gmail(access_token, user_id)
        elif backend == "outlook":
            self._init_outlook(access_token, user_id)
        else:
            raise ValueError(
                f"Unknown email backend: {backend!r}. Use imap / gmail / outlook."
            )

    # --- Init paths -------------------------------------------------------

    def _init_imap(self, imap_host, imap_port, smtp_host, smtp_port, username, password):
        self._imap_host = imap_host or os.getenv("PRAXIA_CONN_EMAIL_IMAP_HOST")
        self._imap_port = int(imap_port)
        self._smtp_host = smtp_host or os.getenv("PRAXIA_CONN_EMAIL_SMTP_HOST")
        self._smtp_port = int(smtp_port)
        self._username = username or os.getenv("PRAXIA_CONN_EMAIL_USERNAME")
        self._password = password or os.getenv("PRAXIA_CONN_EMAIL_PASSWORD")
        if not (self._imap_host and self._username and self._password):
            raise ValueError(
                "Provide imap_host + username + password (or PRAXIA_CONN_EMAIL_* env)."
            )

    def _init_gmail(self, access_token, user_id):
        if user_id and not access_token:
            from praxia.connectors.oauth import oauth_token_for
            access_token = oauth_token_for(user_id, "google").access_token
        if not access_token:
            raise ValueError("Provide access_token or user_id (with Google OAuth token).")
        # Lazy import to keep optional
        try:
            from googleapiclient.discovery import build  # type: ignore
            from google.oauth2.credentials import Credentials  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Gmail backend requires google-api-python-client + google-auth. "
                "Install with: pip install google-api-python-client google-auth"
            ) from e
        creds = Credentials(token=access_token)
        self._gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)

    def _init_outlook(self, access_token, user_id):
        if user_id and not access_token:
            from praxia.connectors.oauth import oauth_token_for
            access_token = oauth_token_for(user_id, "microsoft").access_token
        if not access_token:
            raise ValueError("Provide access_token or user_id (with Microsoft OAuth token).")
        self._outlook_token = access_token

    # --- Pull / Push ------------------------------------------------------

    def pull(self, path: str, *, limit: int = 25) -> list[ConnectorItem]:
        if self.backend == "imap":
            return self._imap_pull(path, limit=limit)
        if self.backend == "gmail":
            return self._gmail_pull(path, limit=limit)
        return self._outlook_pull(path, limit=limit)

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        if self.backend == "imap":
            return self._imap_push(path, data)
        if self.backend == "gmail":
            return self._gmail_push(path, data)
        return self._outlook_push(path, data)

    # --- IMAP / SMTP -----------------------------------------------------

    def _imap_pull(self, path: str, *, limit: int) -> list[ConnectorItem]:
        folder, _, query = path.partition(":")
        folder = folder or "INBOX"
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(self._imap_host, self._imap_port, ssl_context=ctx) as M:
            M.login(self._username, self._password)
            M.select(folder, readonly=True)
            search_str = "(" + query + ")" if query else "ALL"
            _typ, ids = M.search(None, search_str)
            id_list = ids[0].split()[-limit:][::-1]  # latest N
            out: list[ConnectorItem] = []
            for mid in id_list:
                _typ, data = M.fetch(mid, "(RFC822)")
                if not data or not data[0]:
                    continue
                raw = data[0][1] if isinstance(data[0], tuple) else data[0]
                msg = email.message_from_bytes(raw)
                out.append(self._email_to_item(msg, str(mid.decode())))
            return out

    def _imap_push(self, to: str, data: ConnectorItem) -> dict[str, Any]:
        msg = email.message.EmailMessage()
        msg["From"] = self._from
        msg["To"] = to
        msg["Subject"] = (data.name or "(no subject)")[:200]
        body = data.content if isinstance(data.content, str) else str(data.content)
        msg.set_content(body)
        ctx = ssl.create_default_context()
        with smtplib.SMTP(self._smtp_host, self._smtp_port) as s:
            s.starttls(context=ctx)
            s.login(self._username, self._password)
            s.send_message(msg)
        return {"to": to, "subject": msg["Subject"]}

    # --- Gmail API ------------------------------------------------------

    def _gmail_pull(self, path: str, *, limit: int) -> list[ConnectorItem]:
        # path: "<label>:<query>" or just "<query>" (label assumed INBOX)
        if ":" in path:
            label, _, query = path.partition(":")
        else:
            label, query = "INBOX", path
        q = query or ""
        if label and label != "INBOX":
            q = f"in:{label.lower()} " + q
        result = self._gmail.users().messages().list(
            userId="me", q=q.strip(), maxResults=min(limit, 100)
        ).execute()
        out: list[ConnectorItem] = []
        for m in result.get("messages", []):
            full = self._gmail.users().messages().get(
                userId="me", id=m["id"], format="full"
            ).execute()
            payload = full.get("payload", {})
            headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
            body = self._extract_gmail_body(payload)
            out.append(ConnectorItem(
                id=full["id"],
                name=headers.get("Subject", ""),
                content=body,
                mime_type="text/plain",
                metadata={
                    "from": headers.get("From"),
                    "to": headers.get("To"),
                    "date": headers.get("Date"),
                    "thread_id": full.get("threadId"),
                },
            ))
        return out

    def _gmail_push(self, to: str, data: ConnectorItem) -> dict[str, Any]:
        import base64
        msg = email.message.EmailMessage()
        msg["To"] = to
        msg["Subject"] = (data.name or "(no subject)")[:200]
        body = data.content if isinstance(data.content, str) else str(data.content)
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = self._gmail.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        return {"id": sent.get("id"), "thread_id": sent.get("threadId")}

    @staticmethod
    def _extract_gmail_body(payload: dict) -> str:
        import base64
        if payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "replace")
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "replace")
        # Fallback: HTML
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "replace")
        return ""

    # --- Microsoft Graph mail -------------------------------------------

    def _outlook_pull(self, path: str, *, limit: int) -> list[ConnectorItem]:
        import json
        from urllib import parse, request
        folder, _, query = path.partition(":")
        folder = folder or "inbox"
        url = (
            f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder}/messages"
            f"?$top={min(limit, 100)}"
        )
        if query:
            url += "&$search=" + parse.quote('"' + query + '"')
        req = request.Request(url, headers={
            "Authorization": f"Bearer {self._outlook_token}",
            "Accept": "application/json",
        })
        with request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        out: list[ConnectorItem] = []
        for m in data.get("value", []):
            out.append(ConnectorItem(
                id=m.get("id", ""),
                name=m.get("subject", ""),
                content=(m.get("body") or {}).get("content", ""),
                mime_type=(m.get("body") or {}).get("contentType", "text/html"),
                metadata={
                    "from": ((m.get("from") or {}).get("emailAddress") or {}).get("address"),
                    "received": m.get("receivedDateTime"),
                    "is_read": m.get("isRead"),
                },
            ))
        return out

    def _outlook_push(self, to: str, data: ConnectorItem) -> dict[str, Any]:
        import json
        from urllib import request
        body = data.content if isinstance(data.content, str) else str(data.content)
        url = "https://graph.microsoft.com/v1.0/me/sendMail"
        payload = {
            "message": {
                "subject": (data.name or "(no subject)")[:200],
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
            "saveToSentItems": True,
        }
        req = request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._outlook_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=30) as resp:
            return {"to": to, "status": resp.status}

    # --- Common ---------------------------------------------------------

    @staticmethod
    def _email_to_item(msg: email.message.Message, msg_id: str) -> ConnectorItem:
        from_ = parseaddr(msg.get("From", ""))[1]
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(part.get_content_charset() or "utf-8", "replace")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(msg.get_content_charset() or "utf-8", "replace")
        return ConnectorItem(
            id=msg_id,
            name=msg.get("Subject", ""),
            content=body,
            mime_type="text/plain",
            metadata={
                "from": from_,
                "to": msg.get("To"),
                "date": msg.get("Date"),
            },
        )
