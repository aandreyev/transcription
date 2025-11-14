import os
import time
from typing import Any, Dict, Optional

from src.utils import ConfigManager, log_error
from src.utils.connectivity import (
    check_deepgram_connectivity,
    check_openai_connectivity,
)


def _build_folder_status(cfg: ConfigManager) -> Dict[str, bool]:
    folders = {
        'watch': cfg.get("processing.watch_folder"),
        'processed': cfg.get("processing.processed_folder"),
        'error': cfg.get("processing.error_folder"),
        'output': cfg.get("processing.output_folder"),
    }
    status = {}
    for name, path in folders.items():
        try:
            status[name] = bool(path and os.path.exists(path) and os.access(path, os.W_OK))
        except Exception:
            status[name] = False
    return status


def build_health_snapshot(
    db: Optional[object] = None,
    *,
    include_stats: bool = True,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    """Gather a system health snapshot without triggering heavy processing."""
    cfg = ConfigManager()
    if db is None:
        from src.core.database import Database  # Local import to avoid circular dependency
        db_instance = Database()
    else:
        db_instance = db

    deepgram_ok, _ = check_deepgram_connectivity(timeout=timeout)
    openai_ok, _ = check_openai_connectivity(cfg.get("openai.model", "gpt-4o"), timeout=timeout)

    connections = {
        'deepgram': deepgram_ok,
        'openai': openai_ok,
        'database': True,
    }

    stats = {'total': 0, 'status_counts': {}, 'today': 0, 'success_rate': 0.0}
    if include_stats:
        try:
            stats = db_instance.get_job_stats()
        except Exception as exc:
            connections['database'] = False
            log_error(f"Database stats unavailable: {exc}")

    folder_status = _build_folder_status(cfg)
    healthy = all(connections.values()) and all(folder_status.values())

    return {
        'healthy': healthy,
        'connections': connections,
        'folders': folder_status,
        'stats': stats,
    }

