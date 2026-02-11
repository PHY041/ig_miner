"""JSON file storage backend — simplest possible, good for quick exports."""

import json
import logging
from pathlib import Path

from .base import StorageBackend

log = logging.getLogger(__name__)


class JSONStorage(StorageBackend):
    """Append-only JSON file storage. Each scrape creates a new file."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._posts: list[dict] = []
        self._users: list[dict] = []
        self._comments: list[dict] = []
        self._existing_codes: set[str] = set()
        self._load_existing()
        log.info(f"JSON storage: {self.output_dir}")

    def _load_existing(self):
        """Load existing codes from previous runs."""
        for f in self.output_dir.glob("posts_*.json"):
            try:
                data = json.loads(f.read_text())
                for p in data:
                    code = p.get("code")
                    if code:
                        self._existing_codes.add(code)
            except (json.JSONDecodeError, KeyError):
                pass

    def upsert_post(self, post: dict) -> bool:
        self._posts.append(post)
        self._existing_codes.add(post.get("code", ""))
        if len(self._posts) >= 100:
            self._flush_posts()
        return True

    def upsert_user(self, user: dict) -> bool:
        self._users.append(user)
        if len(self._users) >= 100:
            self._flush_users()
        return True

    def upsert_comment(self, comment: dict) -> bool:
        self._comments.append(comment)
        if len(self._comments) >= 100:
            self._flush_comments()
        return True

    def get_existing_codes(self) -> set[str]:
        return self._existing_codes

    def get_enriched_users(self) -> set[str]:
        return set()

    def get_post_count(self) -> int:
        return len(self._existing_codes) + len(self._posts)

    def get_posts_needing_comments(self, limit: int = 200) -> list[dict]:
        # JSON backend doesn't track this well — return empty
        return []

    def _flush_posts(self):
        if not self._posts:
            return
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"posts_{ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._posts, f, ensure_ascii=False, indent=2)
        log.info(f"Flushed {len(self._posts)} posts to {path.name}")
        self._posts.clear()

    def _flush_users(self):
        if not self._users:
            return
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"users_{ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._users, f, ensure_ascii=False, indent=2)
        self._users.clear()

    def _flush_comments(self):
        if not self._comments:
            return
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"comments_{ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._comments, f, ensure_ascii=False, indent=2)
        self._comments.clear()

    def close(self):
        self._flush_posts()
        self._flush_users()
        self._flush_comments()
