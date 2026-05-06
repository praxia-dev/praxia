"""Azure Blob Storage connector — pull / push blobs in a container.

Auth: standard Azure credential chain (DefaultAzureCredential) — workload
identity, service principal, az CLI login, etc. Or pass a connection
string / SAS URL.

Path semantics:
    pull:  "<container>/<prefix>"
    push:  "<container>/<blob_name>"
"""
from __future__ import annotations

from typing import Any

from praxia.connectors.base import Connector, ConnectorItem, _require


class AzureBlobConnector:
    name = "azure-blob"
    MAX_BLOB_SIZE = 5 * 1024 * 1024

    def __init__(
        self,
        *,
        account_url: str | None = None,
        connection_string: str | None = None,
        sas_url: str | None = None,
    ) -> None:
        blob_mod = _require(
            "azure.storage.blob",
            "pip install azure-storage-blob",
        )
        if connection_string:
            self._client = blob_mod.BlobServiceClient.from_connection_string(connection_string)
        elif sas_url:
            self._client = blob_mod.BlobServiceClient(account_url=sas_url)
        elif account_url:
            try:
                identity = _require("azure.identity", "pip install azure-identity")
                cred = identity.DefaultAzureCredential()
                self._client = blob_mod.BlobServiceClient(account_url=account_url, credential=cred)
            except ImportError:
                raise
        else:
            raise ValueError(
                "Provide one of: account_url (with DefaultAzureCredential), "
                "connection_string, sas_url."
            )

    def pull(self, path: str, *, limit: int = 20) -> list[ConnectorItem]:
        container, prefix = self._split(path)
        cc = self._client.get_container_client(container)
        out: list[ConnectorItem] = []
        for blob in cc.list_blobs(name_starts_with=prefix):
            if len(out) >= limit:
                break
            size = blob.size or 0
            if size > self.MAX_BLOB_SIZE:
                out.append(ConnectorItem(
                    id=blob.name, name=blob.name, content=b"",
                    mime_type="application/octet-stream",
                    metadata={"size": size, "skipped": "too_large"},
                ))
                continue
            data = cc.get_blob_client(blob.name).download_blob().readall()
            out.append(ConnectorItem(
                id=blob.name,
                name=blob.name.rsplit("/", 1)[-1],
                content=data,
                mime_type="application/octet-stream",
                metadata={
                    "size": size,
                    "etag": getattr(blob, "etag", None),
                    "last_modified": str(blob.last_modified) if blob.last_modified else None,
                    "container": container,
                },
            ))
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        container, blob_name = self._split(path)
        cc = self._client.get_container_client(container)
        body = data.content if isinstance(data.content, (bytes, bytearray)) else str(data.content).encode()
        cc.upload_blob(name=blob_name, data=body, overwrite=True)
        return {"container": container, "blob": blob_name, "size": len(body)}

    @staticmethod
    def _split(path: str) -> tuple[str, str]:
        if "/" not in path:
            return path, ""
        container, _, rest = path.partition("/")
        return container, rest
