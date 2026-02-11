"""SQLite storage backend — zero config, works out of the box."""

import json
import logging
import sqlite3
from pathlib import Path

from .base import StorageBackend

log = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS posts (
    code TEXT PRIMARY KEY,
    username TEXT,
    caption TEXT,
    hashtags TEXT,
    image_url TEXT,
    local_image_path TEXT,
    media_type INTEGER DEFAULT 1,
    likes INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    views INTEGER,
    location_name TEXT,
    location_lat REAL,
    location_lng REAL,
    posted_at TEXT,
    scraped_at TEXT DEFAULT (datetime('now')),
    word_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    full_name TEXT,
    bio TEXT,
    followers INTEGER,
    following INTEGER,
    post_count INTEGER,
    is_verified BOOLEAN DEFAULT 0,
    is_private BOOLEAN DEFAULT 0,
    profile_pic_url TEXT,
    scraped_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    post_id TEXT REFERENCES posts(code),
    username TEXT,
    text TEXT,
    likes INTEGER DEFAULT 0,
    posted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_posts_username ON posts(username);
CREATE INDEX IF NOT EXISTS idx_posts_likes ON posts(likes DESC);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);
"""


class SQLiteStorage(StorageBackend):
    """SQLite storage — the default. No setup required."""

    def __init__(self, db_path: str = "ig_miner.db"):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()
        log.info(f"SQLite storage: {self.db_path}")

    def upsert_post(self, post: dict) -> bool:
        try:
            self.conn.execute(
                """INSERT INTO posts
                   (code, username, caption, hashtags, image_url,
                    local_image_path, media_type, likes, comments_count,
                    views, location_name, location_lat, location_lng,
                    posted_at, word_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(code) DO UPDATE SET
                    likes=excluded.likes,
                    comments_count=excluded.comments_count,
                    views=excluded.views""",
                (
                    post.get("code"),
                    post.get("username"),
                    post.get("caption", ""),
                    json.dumps(post.get("hashtags", [])),
                    post.get("image_url"),
                    post.get("local_image_path"),
                    post.get("media_type", 1),
                    post.get("likes", 0),
                    post.get("comments_count", 0),
                    post.get("views"),
                    post.get("location_name"),
                    post.get("location_lat"),
                    post.get("location_lng"),
                    post.get("posted_at"),
                    post.get("word_count", 0),
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            log.warning(f"upsert_post {post.get('code')}: {e}")
            return False

    def upsert_user(self, user: dict) -> bool:
        try:
            self.conn.execute(
                """INSERT INTO users
                   (username, full_name, bio, followers, following,
                    post_count, is_verified, is_private, profile_pic_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(username) DO UPDATE SET
                    full_name=COALESCE(excluded.full_name, users.full_name),
                    bio=COALESCE(excluded.bio, users.bio),
                    followers=COALESCE(excluded.followers, users.followers),
                    following=COALESCE(excluded.following, users.following),
                    post_count=COALESCE(excluded.post_count, users.post_count),
                    is_verified=excluded.is_verified,
                    profile_pic_url=COALESCE(excluded.profile_pic_url, users.profile_pic_url)""",
                (
                    user.get("username"),
                    user.get("full_name", ""),
                    user.get("bio"),
                    user.get("followers"),
                    user.get("following"),
                    user.get("post_count"),
                    user.get("is_verified", False),
                    user.get("is_private", False),
                    user.get("profile_pic_url"),
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            log.warning(f"upsert_user {user.get('username')}: {e}")
            return False

    def upsert_comment(self, comment: dict) -> bool:
        try:
            self.conn.execute(
                """INSERT INTO comments (id, post_id, username, text, likes, posted_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                    likes=excluded.likes""",
                (
                    comment.get("id"),
                    comment.get("post_id"),
                    comment.get("username", ""),
                    comment.get("text", ""),
                    comment.get("likes", 0),
                    comment.get("posted_at"),
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            log.warning(f"upsert_comment: {e}")
            return False

    def get_existing_codes(self) -> set[str]:
        rows = self.conn.execute("SELECT code FROM posts").fetchall()
        return {r["code"] for r in rows}

    def get_enriched_users(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT username FROM users WHERE followers IS NOT NULL"
        ).fetchall()
        return {r["username"] for r in rows}

    def get_post_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM posts").fetchone()
        return row["cnt"] if row else 0

    def get_posts_needing_comments(self, limit: int = 200) -> list[dict]:
        rows = self.conn.execute(
            """SELECT p.code, p.comments_count FROM posts p
               WHERE p.comments_count > 0
               AND p.code NOT IN (SELECT DISTINCT post_id FROM comments WHERE post_id IS NOT NULL)
               ORDER BY p.likes DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [{"code": r["code"], "comments_count": r["comments_count"]} for r in rows]

    def store_image(self, image_bytes: bytes, filename: str) -> str | None:
        """Save image to local images/ directory."""
        img_dir = self.db_path.parent / "images"
        img_dir.mkdir(exist_ok=True)
        path = img_dir / filename
        path.write_bytes(image_bytes)
        return str(path)

    def close(self):
        self.conn.close()
