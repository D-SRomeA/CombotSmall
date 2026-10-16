import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "requests.db"


def init_db() -> None:
    with closing(sqlite3.connect(DB_PATH, timeout=10)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_at TEXT NOT NULL,
                    chat_id INTEGER NOT NULL,
                    telegram_message_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    message_text TEXT NOT NULL,
                    branch TEXT,
                    sync_status TEXT NOT NULL DEFAULT 'pending',
                    UNIQUE(chat_id, telegram_message_id)
                )
                """
            )

            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(requests)"
                ).fetchall()
            }

            if "branch" not in columns:
                connection.execute(
                    "ALTER TABLE requests ADD COLUMN branch TEXT"
                )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    default_branch TEXT,
                    full_name TEXT,
                    phone TEXT,
                    position TEXT,
                    registered_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )


def save_request(
    *,
    received_at: str,
    chat_id: int,
    telegram_message_id: int,
    user_id: int,
    username: str | None,
    message_text: str,
    branch: str,
) -> int:
    with closing(sqlite3.connect(DB_PATH, timeout=10)) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO requests (
                    received_at,
                    chat_id,
                    telegram_message_id,
                    user_id,
                    username,
                    message_text,
                    branch
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, telegram_message_id) DO NOTHING
                """,
                (
                    received_at,
                    chat_id,
                    telegram_message_id,
                    user_id,
                    username,
                    message_text,
                    branch,
                ),
            )

            row = connection.execute(
                """
                SELECT id
                FROM requests
                WHERE chat_id = ? AND telegram_message_id = ?
                """,
                (chat_id, telegram_message_id),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "Не удалось получить ID сохранённого обращения."
                )

            request_id = int(row[0])

    return request_id


def get_pending_requests(limit: int = 10) -> list[dict]:
    with closing(sqlite3.connect(DB_PATH, timeout=10)) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                id,
                received_at,
                chat_id,
                telegram_message_id,
                user_id,
                username,
                message_text,
                branch
            FROM requests
            WHERE sync_status = 'pending'
            ORDER BY id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [dict(row) for row in rows]


def mark_request_synced(request_id: int) -> None:
    with closing(sqlite3.connect(DB_PATH, timeout=10)) as connection:
        with connection:
            connection.execute(
                """
                UPDATE requests
                SET sync_status = 'synced'
                WHERE id = ?
                """,
                (request_id,),
            )


def get_user_branch(user_id: int) -> str | None:
    with closing(sqlite3.connect(DB_PATH, timeout=10)) as connection:
        row = connection.execute(
            """
            SELECT default_branch
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        return row[0] if row is not None else None


def save_user_branch(
    *,
    user_id: int,
    username: str | None,
    branch: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()

    with closing(sqlite3.connect(DB_PATH, timeout=10)) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO users (
                    user_id,
                    username,
                    default_branch,
                    registered_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    default_branch = excluded.default_branch,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    username,
                    branch,
                    now,
                    now,
                ),
            )