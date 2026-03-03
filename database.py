from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class CompostingBucketDB:
    """数据库封装类（目录化多数据库管理）。"""

    MASTER_DB_NAME = "CompostingBucket.db"

    def __init__(self, db_root_dir: str | Path) -> None:
        self.db_root_dir = Path(db_root_dir)
        self.user_dir = self.db_root_dir / "user"
        self.group_dir = self.db_root_dir / "group"
        self.master_db_path = self.db_root_dir / self.MASTER_DB_NAME

        self._ensure_layout()
        self._init_master_db()
        # 保持向后兼容：主库也可直接用于 records 读写。
        self._init_records_db(self.master_db_path)

    # 确保目录结构存在
    def _ensure_layout(self) -> None:
        self.db_root_dir.mkdir(parents=True, exist_ok=True)
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.group_dir.mkdir(parents=True, exist_ok=True)

    # 将任意字符串转换为安全的文件名片段（仅保留字母数字和部分符号，其他替换为下划线）
    @staticmethod
    def _safe_name(value: str) -> str:
        """Convert arbitrary id into a filesystem-safe file segment."""
        cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", value.strip())
        return cleaned or "unknown"

    # 上下文管理器：自动提交事务并关闭连接
    @contextmanager
    def connect(self, db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
        target_path = Path(db_path) if db_path is not None else self.master_db_path
        conn = sqlite3.connect(target_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # 初始化主数据库，创建 metadata 表
    def _init_master_db(self) -> None:
        """Initialize metadata table in master DB."""
        with self.connect(self.master_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS databases (
                    platforms TEXT NOT NULL,
                    db_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    UNIQUE(platforms, db_name, type)
                )
                """
            )

    def _init_records_db(self, db_path: Path) -> None:
        """Create record storage table/index in target DB."""
        with self.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_records_session_time
                ON records(session_id, created_at)
                """
            )

    def _register_db(self, platform: str, db_name: str, db_type: str) -> None:
        with self.connect(self.master_db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO databases(platforms, db_name, type)
                VALUES (?, ?, ?)
                """,
                (platform, db_name, db_type),
            )

    def _ensure_sub_db(self, platform: str, source_id: str, db_type: str) -> Path:
        folder = self.user_dir if db_type == "user" else self.group_dir
        safe_platform = self._safe_name(platform)
        safe_id = self._safe_name(source_id)
        file_name = f"{safe_platform}_{safe_id}.db"
        db_path = folder / file_name

        if not db_path.exists():
            self._init_records_db(db_path)

        self._register_db(platform=platform, db_name=file_name, db_type=db_type)
        return db_path

    def ensure_user_db(self, platform: str, user_id: str) -> Path:
        """Ensure and return user database path."""
        return self._ensure_sub_db(platform=platform, source_id=user_id, db_type="user")

    def ensure_group_db(self, platform: str, group_id: str) -> Path:
        """Ensure and return group database path."""
        return self._ensure_sub_db(platform=platform, source_id=group_id, db_type="group")

    def init_db(self) -> None:
        """Backward-compatible entrypoint."""
        self._init_master_db()
        self._init_records_db(self.master_db_path)

    def insert_record(
        self,
        session_id: str,
        category: str,
        payload: dict[str, Any] | list[Any] | str,
        db_path: str | Path | None = None,
    ) -> int:
        """Insert one flexible record and return row id."""
        created_at = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload, ensure_ascii=False)

        with self.connect(db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO records(session_id, category, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, category, payload_json, created_at),
            )
            return int(cursor.lastrowid)

    def list_recent(
        self,
        session_id: str,
        limit: int = 20,
        db_path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        """Query recent records and decode JSON payload."""
        with self.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, category, payload_json, created_at
                FROM records
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "category": row["category"],
                    "payload": json.loads(row["payload_json"]),
                    "created_at": row["created_at"],
                }
            )
        return result


if __name__ == "__main__":
    # Example usage: python database.py
    demo_root = Path(__file__).parent / "data"
    demo_db = CompostingBucketDB(demo_root)

    user_db_path = demo_db.ensure_user_db(platform="telegram", user_id="demo-user")

    demo_id = demo_db.insert_record(
        session_id="demo-session",
        category="popped_context",
        payload={
            "reason": "plugin_pop",
            "contexts": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ],
        },
        db_path=user_db_path,
    )

    print(f"inserted id={demo_id}")
    print("recent records:")
    for item in demo_db.list_recent("demo-session", limit=5, db_path=user_db_path):
        print(item)
