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