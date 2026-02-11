"""Abstract base class for storage backends."""

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Interface that all storage backends must implement."""

    @abstractmethod
    def upsert_post(self, post: dict) -> bool:
        """Store or update a post."""

    @abstractmethod
    def upsert_user(self, user: dict) -> bool:
        """Store or update a user."""

    @abstractmethod
    def upsert_comment(self, comment: dict) -> bool:
        """Store or update a comment."""

    @abstractmethod
    def get_existing_codes(self) -> set[str]:
        """Get all post shortcodes already in storage."""

    @abstractmethod
    def get_enriched_users(self) -> set[str]:
        """Get usernames that already have full profile data."""

    @abstractmethod
    def get_post_count(self) -> int:
        """Get total number of stored posts."""

    @abstractmethod
    def get_posts_needing_comments(self, limit: int = 200) -> list[dict]:
        """Get posts with comments_count > 0 but no stored comments."""

    def store_image(self, image_bytes: bytes, filename: str) -> str | None:
        """Store an image and return its public URL. Optional."""
        return None

    def close(self):
        """Clean up resources."""
