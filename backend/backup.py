"""Creates a consistent point-in-time copy of the live database via SQLite's
VACUUM INTO - atomic and safe to run against a live connection, unlike
copying the raw db file directly, which can pull a torn/inconsistent read if
a write lands mid-copy.

Meant to be invoked over SSH by the scheduled off-platform backup workflow
(.github/workflows/db-backup.yml), which downloads the resulting file via
sftp and deletes it from the volume afterwards - also prunes anything left
over from a previous run that never got cleaned up (e.g. a failed download),
so a string of failures can't slowly fill the volume.

Run as: python -m backend.backup
Prints the absolute path of the new backup file to stdout, nothing else.
"""

import sqlite3
from datetime import datetime, timezone

from .db import DB_PATH

BACKUP_DIR = DB_PATH.parent / "backups"
MAX_AGE_HOURS = 24  # generous vs. the daily schedule, in case a run is late


def _prune_old_backups() -> None:
    if not BACKUP_DIR.exists():
        return
    cutoff = datetime.now(timezone.utc).timestamp() - MAX_AGE_HOURS * 3600
    for f in BACKUP_DIR.glob("data-*.db"):
        if f.stat().st_mtime < cutoff:
            f.unlink()


def create_backup() -> str:
    BACKUP_DIR.mkdir(exist_ok=True)
    _prune_old_backups()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = BACKUP_DIR / f"data-{stamp}.db"
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(f"VACUUM INTO '{dest}'")
    finally:
        conn.close()
    return str(dest)


if __name__ == "__main__":
    print(create_backup())
