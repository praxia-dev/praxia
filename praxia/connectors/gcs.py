"""Google Cloud Storage connector — pull / push objects.

Auth: standard GCP application-default credentials (gcloud auth, workload
identity, service account JSON path). Or pass `credentials_json` directly.

Path semantics:
    pull:  "<bucket>/<prefix>"
    push:  "<bucket>/<key>"
"""
from __future__ import annotations

import json
from typing import Any

from praxia.connectors.base import Connector, ConnectorItem, _require


class GcsConnector:
    name = "gcs"
    MAX_OBJECT_SIZE = 5 * 1024 * 1024

    def __init__(
        self,
        *,
        project: str | None = None,
        credentials_json: str | dict | None = None,
    ) -> None:
        gcs = _require("google.cloud.storage", "pip install google-cloud-storage")
        if credentials_json:
            from google.oauth2 import service_account  # type: ignore
            data = (
                json.loads(credentials_json)
                if isinstance(credentials_json, str)
                else credentials_json
            )
            cred = service_account.Credentials.from_service_account_info(data)
            self._client = gcs.Client(project=project, credentials=cred)
        else:
            # ADC: gcloud auth application-default login / workload identity / GAE
            self._client = gcs.Client(project=project)

    def pull(self, path: str, *, limit: int = 20) -> list[ConnectorItem]:
        bucket_name, prefix = self._split(path)
        bucket = self._client.bucket(bucket_name)
        out: list[ConnectorItem] = []
        for blob in self._client.list_blobs(bucket, prefix=prefix, max_results=limit):
            size = blob.size or 0
            if size > self.MAX_OBJECT_SIZE:
                out.append(ConnectorItem(
                    id=blob.name, name=blob.name, content=b"",
                    mime_type=blob.content_type or "application/octet-stream",
                    metadata={"size": size, "skipped": "too_large"},
                ))
                continue
            data = blob.download_as_bytes()
            out.append(ConnectorItem(
                id=blob.name,
                name=blob.name.rsplit("/", 1)[-1],
                content=data,
                mime_type=blob.content_type or "application/octet-stream",
                metadata={
                    "size": size,
                    "md5": blob.md5_hash,
                    "updated": str(blob.updated) if blob.updated else None,
                    "bucket": bucket_name,
                },
            ))
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        bucket_name, key = self._split(path)
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(key)
        body = data.content if isinstance(data.content, (bytes, bytearray)) else str(data.content).encode()
        blob.upload_from_string(body, content_type=data.mime_type or "application/octet-stream")
        return {"bucket": bucket_name, "key": key, "size": len(body)}

    @staticmethod
    def _split(path: str) -> tuple[str, str]:
        if "/" not in path:
            return path, ""
        bucket, _, rest = path.partition("/")
        return bucket, rest
