"""GitHub connector — pull issues / PRs / files, push issues / comments.

Path semantics:
    pull:  "owner/repo"                — recent issues
           "owner/repo/issues:open"    — filtered issues
           "owner/repo/code:<query>"   — code search
           "owner/repo/path/to/file"   — single file content
    push:  "owner/repo"                — creates a new issue
           "owner/repo#<num>"          — adds a comment to an existing issue
"""
from __future__ import annotations

from typing import Any

from praxia.connectors._helpers import resolve_oauth_token
from praxia.connectors.base import Connector, ConnectorItem, _require


class GitHubConnector:
    name = "github"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        user_id: str | None = None,
    ) -> None:
        gh = _require("github", "pip install PyGithub")
        access_token = resolve_oauth_token(access_token, user_id, "github")
        self._gh = gh.Github(access_token)

    def pull(self, path: str, *, limit: int = 30) -> list[ConnectorItem]:
        # owner/repo[/...]
        parts = path.split("/", 2)
        if len(parts) < 2:
            raise ValueError(f"Path must be 'owner/repo[...]' — got {path!r}")
        owner, repo = parts[0], parts[1]
        sub = parts[2] if len(parts) == 3 else ""
        repo_obj = self._gh.get_repo(f"{owner}/{repo}")

        if sub.startswith("code:"):
            return self._search_code(repo_obj, sub[len("code:"):], limit=limit)
        if sub.startswith("issues:"):
            state = sub[len("issues:"):]
            return self._issues(repo_obj, state=state, limit=limit)
        if sub:
            return self._file(repo_obj, sub)
        return self._issues(repo_obj, state="all", limit=limit)

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        body = data.content if isinstance(data.content, str) else str(data.content)
        # owner/repo or owner/repo#NUM
        if "#" in path:
            repo_path, issue_num = path.rsplit("#", 1)
            repo = self._gh.get_repo(repo_path)
            issue = repo.get_issue(int(issue_num))
            comment = issue.create_comment(body)
            return {"id": comment.id, "url": comment.html_url}
        repo = self._gh.get_repo(path)
        issue = repo.create_issue(
            title=(data.name or "(no title)")[:256],
            body=body,
            labels=list((data.metadata or {}).get("labels", [])),
        )
        return {"number": issue.number, "url": issue.html_url}

    # --- helpers ---------------------------------------------------------

    def _issues(self, repo, *, state: str, limit: int) -> list[ConnectorItem]:
        out = []
        for i, issue in enumerate(repo.get_issues(state=state)):
            if i >= limit:
                break
            out.append(ConnectorItem(
                id=str(issue.number),
                name=issue.title,
                content=issue.body or "",
                mime_type="text/markdown",
                metadata={
                    "state": issue.state,
                    "labels": [lbl.name for lbl in issue.labels],
                    "assignee": issue.assignee.login if issue.assignee else None,
                    "url": issue.html_url,
                    "is_pull_request": issue.pull_request is not None,
                },
            ))
        return out

    def _search_code(self, repo, query: str, *, limit: int) -> list[ConnectorItem]:
        # PyGithub: search across all GH; restrict to repo
        full_query = f"{query} repo:{repo.full_name}"
        out = []
        for i, hit in enumerate(self._gh.search_code(full_query)):
            if i >= limit:
                break
            try:
                content = hit.decoded_content.decode("utf-8", errors="replace")
            except Exception:
                content = ""
            out.append(ConnectorItem(
                id=hit.path,
                name=hit.path,
                content=content,
                mime_type="text/plain",
                metadata={"url": hit.html_url, "sha": hit.sha},
            ))
        return out

    def _file(self, repo, path: str) -> list[ConnectorItem]:
        f = repo.get_contents(path)
        if isinstance(f, list):  # directory
            return [
                ConnectorItem(
                    id=item.path,
                    name=item.name,
                    content="",
                    mime_type="application/octet-stream",
                    metadata={"type": item.type, "size": item.size},
                )
                for item in f
            ]
        content = ""
        try:
            content = f.decoded_content.decode("utf-8", errors="replace")
        except Exception:
            pass
        return [ConnectorItem(
            id=f.path,
            name=f.name,
            content=content,
            mime_type="text/plain",
            metadata={"sha": f.sha, "size": f.size, "url": f.html_url},
        )]
