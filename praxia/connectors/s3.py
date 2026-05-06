"""AWS S3 connector — pull objects from a bucket prefix, push file uploads.

Auth: standard boto3 chain (env, ~/.aws/credentials, IAM role, etc.).
Per-user OAuth is NOT used — S3 uses IAM credentials, which are operator-managed.

Path semantics:
    pull:  "<bucket>/<prefix>"  — list objects under prefix and return content
                                  for the first `limit` (small objects only)
    push:  "<bucket>/<key>"     — upload data to that key
"""
from __future__ import annotations

from typing import Any

from praxia.connectors.base import Connector, ConnectorItem, _require


class S3Connector:
    name = "s3"
    # 5 MB cap on per-object pull to avoid blowing up LLM context windows
    MAX_OBJECT_SIZE = 5 * 1024 * 1024

    def __init__(
        self,
        *,
        region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        endpoint_url: str | None = None,    # for MinIO etc.
    ) -> None:
        boto3 = _require("boto3", "pip install boto3")
        kwargs: dict[str, Any] = {}
        if region:
            kwargs["region_name"] = region
        if aws_access_key_id:
            kwargs["aws_access_key_id"] = aws_access_key_id
        if aws_secret_access_key:
            kwargs["aws_secret_access_key"] = aws_secret_access_key
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self._s3 = boto3.client("s3", **kwargs)

    def pull(self, path: str, *, limit: int = 20) -> list[ConnectorItem]:
        bucket, prefix = self._split(path)
        resp = self._s3.list_objects_v2(
            Bucket=bucket, Prefix=prefix, MaxKeys=min(limit, 1000)
        )
        out: list[ConnectorItem] = []
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            size = obj.get("Size", 0)
            if size > self.MAX_OBJECT_SIZE:
                # Skip body, return metadata only
                out.append(ConnectorItem(
                    id=key, name=key, content=b"",
                    mime_type="application/octet-stream",
                    metadata={"size": size, "etag": obj.get("ETag"), "skipped": "too_large"},
                ))
                continue
            body = self._s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            out.append(ConnectorItem(
                id=key,
                name=key.rsplit("/", 1)[-1],
                content=body,
                mime_type="application/octet-stream",
                metadata={
                    "size": size,
                    "etag": obj.get("ETag"),
                    "last_modified": str(obj.get("LastModified")),
                    "bucket": bucket,
                    "key": key,
                },
            ))
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        bucket, key = self._split(path)
        body = data.content if isinstance(data.content, (bytes, bytearray)) else str(data.content).encode()
        kwargs: dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "Body": body,
            "ContentType": data.mime_type or "application/octet-stream",
        }
        meta = (data.metadata or {}).get("s3_metadata")
        if meta:
            kwargs["Metadata"] = {str(k): str(v) for k, v in meta.items()}
        self._s3.put_object(**kwargs)
        return {"bucket": bucket, "key": key, "size": len(body)}

    @staticmethod
    def _split(path: str) -> tuple[str, str]:
        if "/" not in path:
            return path, ""
        bucket, _, rest = path.partition("/")
        return bucket, rest
