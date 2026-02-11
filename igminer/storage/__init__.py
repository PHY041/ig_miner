"""Storage backends for igminer."""

from .base import StorageBackend
from .sqlite_store import SQLiteStorage
from .json_store import JSONStorage

__all__ = ["StorageBackend", "SQLiteStorage", "JSONStorage"]


def get_storage(backend: str = "sqlite", **kwargs) -> StorageBackend:
    """Factory to get the right storage backend.

    Args:
        backend: One of 'sqlite', 'json', 'supabase'.
        **kwargs: Backend-specific config.

    Returns:
        StorageBackend instance.
    """
    if backend == "sqlite":
        return SQLiteStorage(kwargs.get("db_path", "igminer.db"))
    elif backend == "json":
        return JSONStorage(kwargs.get("output_dir", "output"))
    elif backend == "supabase":
        from .supabase_store import SupabaseStorage
        return SupabaseStorage(
            url=kwargs["supabase_url"],
            key=kwargs["supabase_key"],
            schema=kwargs.get("schema", "public"),
            bucket=kwargs.get("bucket"),
        )
    else:
        raise ValueError(f"Unknown storage backend: {backend}")
