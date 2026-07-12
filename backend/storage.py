"""
storage.py – Backblaze B2 (S3-compatible) object storage client
==================================================================
Local disk storage doesn't survive container redeploys on FastAPI Cloud,
so meal images are stored in a private Backblaze B2 bucket instead.
Since the bucket is private (no credit card needed for B2 this way),
images are served back through our own backend as a proxy — see the
/uploads/meals/{filename} route in main.py.
"""
import os
import boto3
from botocore.exceptions import ClientError

B2_KEY_ID   = os.getenv("B2_KEY_ID")
B2_APP_KEY  = os.getenv("B2_APPLICATION_KEY")
B2_BUCKET   = os.getenv("B2_BUCKET_NAME")
B2_ENDPOINT = os.getenv("B2_ENDPOINT")  # e.g. s3.us-east-005.backblazeb2.com

_client = None


def get_client():
    """Lazily create and cache the boto3 S3-compatible client for B2."""
    global _client
    if _client is None:
        missing = [
            name for name, val in
            [("B2_KEY_ID", B2_KEY_ID), ("B2_APPLICATION_KEY", B2_APP_KEY),
             ("B2_BUCKET_NAME", B2_BUCKET), ("B2_ENDPOINT", B2_ENDPOINT)]
            if not val
        ]
        if missing:
            raise RuntimeError(
                f"B2 storage is not configured — missing env vars: {', '.join(missing)}"
            )
        _client = boto3.client(
            "s3",
            endpoint_url=f"https://{B2_ENDPOINT}",
            aws_access_key_id=B2_KEY_ID,
            aws_secret_access_key=B2_APP_KEY,
        )
    return _client


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream"):
    """Upload raw bytes to the bucket under the given key (e.g. 'meals/xxx.jpg')."""
    client = get_client()
    client.put_object(Bucket=B2_BUCKET, Key=key, Body=data, ContentType=content_type)


def get_object_stream(key: str):
    """Fetch an object from the bucket. Returns the raw boto3 get_object() response."""
    client = get_client()
    return client.get_object(Bucket=B2_BUCKET, Key=key)


def delete_object(key: str):
    """Best-effort delete — never raises, since a missing/already-deleted
    file shouldn't block the caller (e.g. deleting a menu item)."""
    try:
        client = get_client()
        client.delete_object(Bucket=B2_BUCKET, Key=key)
    except ClientError:
        pass