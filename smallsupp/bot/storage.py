import sqlite3
from contextlib import closing
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "requests.db"


def init_db() -> None:
    with closing(sqlite3.connect(DB_PATH, timeout=10)) as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_at TEXT NOT NULL,
                    chat_id INTEGER NOT NULL,
                    telegram_message_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    message_text TEXT NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'pending',
                    UNIQUE(chat_id, telegram_message_id)
                )
            """)


def save_request(
    *,
    received_at: str,
    chat_id: int,
    telegram_message_id: int,
    user_id: int,
    username: str | None,
    message_text: str,
    branch=user_branch
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
                    message_text
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, telegram_message_id) DO NOTHING
                """,
                (
                    received_at,
                    chat_id,
                    telegram_message_id,
                    user_id,
                    username,
                    message_text,
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
                raise RuntimeError("Не удалось получить ID сохранённого обращения.")

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
                message_text
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