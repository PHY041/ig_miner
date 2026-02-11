"""Supabase storage backend — cloud database with image hosting."""

import logging

import requests as http

from .base import StorageBackend

log = logging.getLogger(__name__)


class SupabaseStorage(StorageBackend):
    """Supabase (PostgREST + Storage) backend.

    Setup: Create tables ig_posts, ig_users, ig_comments in your
    Supabase project. See README for SQL schema.
    """

    def __init__(
        self,
        url: str,
        key: str,
        schema: str = "public",
        bucket: str | None = None,
    ):
        self.url = url.rstrip("/")
        self.key = key
        self.schema = schema
        self.bucket = bucket
        log.info(f"Supabase storage: {self.url} (schema={schema})")

    def _headers(self, write: bool = False) -> dict:
        h = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Accept-Profile": self.schema,
        }
        if write:
            h["Content-Profile"] = self.schema
        return h

    def _upsert(self, table: str, data: dict | list[dict]) -> bool:
        headers = self._headers(write=True)
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        payload = data if isinstance(data, list) else [data]
        resp = http.post(
            f"{self.url}/rest/v1/{table}",
            headers=headers,
            json=payload,
        )
        if resp.status_code not in (200, 201):
            log.warning(f"upsert {table}: {resp.status_code} {resp.text[:200]}")
        return resp.ok

    def upsert_post(self, post: dict) -> bool:
        return self._upsert("ig_posts", {
            "id": post.get("code"),
            "code": post.get("code"),
            "username": post.get("username") or None,
            "caption": post.get("caption", ""),
            "hashtags": post.get("hashtags", []),
            "image_url": post.get("image_url"),
            "storage_url": post.get("storage_url"),
            "media_type": post.get("media_type", 1),
            "likes": post.get("likes", 0),
            "comments_count": post.get("comments_count", 0),
            "views": post.get("views"),
            "location_name": post.get("location_name"),
            "location_lat": post.get("location_lat"),
            "location_lng": post.get("location_lng"),
            "posted_at": post.get("posted_at"),
            "word_count": post.get("word_count", 0),
        })

    def upsert_user(self, user: dict) -> bool:
        return self._upsert("ig_users", user)

    def upsert_comment(self, comment: dict) -> bool:
        # Ensure FK: upsert user first
        if comment.get("username"):
            self.upsert_user({
                "username": comment["username"],
                "full_name": "",
                "is_verified": False,
            })
        return self._upsert("ig_comments", comment)

    def get_existing_codes(self) -> set[str]:
        codes: set[str] = set()
        offset = 0
        while True:
            resp = http.get(
                f"{self.url}/rest/v1/ig_posts?select=code&limit=1000&offset={offset}",
                headers=self._headers(),
            )
            if not resp.ok or not resp.json():
                break
            batch = resp.json()
            codes.update(r["code"] for r in batch if r.get("code"))
            if len(batch) < 1000:
                break
            offset += 1000
        return codes

    def get_enriched_users(self) -> set[str]:
        resp = http.get(
            f"{self.url}/rest/v1/ig_users?select=username&followers=not.is.null",
            headers=self._headers(),
        )
        if resp.ok:
            return {r["username"] for r in resp.json()}
        return set()

    def get_post_count(self) -> int:
        resp = http.get(
            f"{self.url}/rest/v1/ig_posts?select=id&limit=1",
            headers={
                **self._headers(),
                "Range-Unit": "items",
                "Range": "0-0",
                "Prefer": "count=exact",
            },
        )
        for part in resp.headers.get("content-range", "").split("/"):
            if part.isdigit():
                return int(part)
        return 0

    def get_posts_needing_comments(self, limit: int = 200) -> list[dict]:
        resp = http.get(
            f"{self.url}/rest/v1/ig_posts"
            f"?select=code,comments_count"
            f"&comments_count=gt.0"
            f"&order=likes.desc"
            f"&limit={limit}",
            headers=self._headers(),
        )
        if not resp.ok:
            return []

        posts = resp.json()
        # Check which already have comments
        existing_resp = http.get(
            f"{self.url}/rest/v1/ig_comments?select=post_id",
            headers=self._headers(),
        )
        existing_ids = set()
        if existing_resp.ok:
            existing_ids = {
                r["post_id"] for r in existing_resp.json() if r.get("post_id")
            }

        return [p for p in posts if p["code"] not in existing_ids]

    def store_image(self, image_bytes: bytes, filename: str) -> str | None:
        if not self.bucket:
            return None
        resp = http.post(
            f"{self.url}/storage/v1/object/{self.bucket}/{filename}",
            headers={
                "apikey": self.key,
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "image/jpeg",
            },
            data=image_bytes,
        )
        if resp.status_code in (200, 201):
            return f"{self.url}/storage/v1/object/public/{self.bucket}/{filename}"
        if resp.status_code == 400 and "Duplicate" in resp.text:
            return f"{self.url}/storage/v1/object/public/{self.bucket}/{filename}"
        log.warning(f"Upload {filename}: {resp.status_code}")
        return None

    def close(self):
        pass
