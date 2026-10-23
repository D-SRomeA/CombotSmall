import asyncio
import json
import logging
from urllib.request import Request, urlopen

from bot.storage import get_pending_requests, mark_request_synced


logger = logging.getLogger(__name__)


def send_request(
    url: str,
    secret: str,
    request_data: dict,
) -> None:
    request_key = (
        f"{request_data['chat_id']}:"
        f"{request_data['telegram_message_id']}"
    )

    payload = {
        "secret": secret,
        "received_at": request_data["received_at"],
        "chat_id": str(request_data["chat_id"]),
        "telegram_message_id": str(request_data["telegram_message_id"]),
        "user_id": str(request_data["user_id"]),
        "username": request_data["username"],
        "message_text": request_data["message_text"],
        "branch": request_data["branch"]
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with urlopen(request, timeout=45) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not isinstance(result, dict):
        raise RuntimeError(
            f"Apps Script вернул неожиданный формат ответа: {type(result).name}"
        )

    if result.get("ok") is not True or result.get("request_key") != request_key:
        raise RuntimeError(
            "Apps Script не подтвердил сохранение: "
            f"ok={result.get('ok')!r}, "
            f"request_key={result.get('request_key')!r}, "
            f"ожидаемый ключ={request_key!r}, "
            f"ошибка={result.get('error')!r}"
        )


async def sync_loop(url: str, secret: str) -> None:
    while True:
        try:
            pending = await asyncio.to_thread(get_pending_requests)

            for request_data in pending:
                try:
                    await asyncio.to_thread(
                        send_request,
                        url,
                        secret,
                        request_data,
                    )

                    await asyncio.to_thread(
                        mark_request_synced,
                        request_data["id"],
                    )

                    logger.info(
                        "Обращение №%s передано в таблицу",
                        request_data["id"],
                    )

                except Exception as error:
                    # Не выводим URL, секрет и содержимое обращения.
                    logger.exception(
                        "Обращение №%s осталось в очереди.",
                        request_data["id"],
                    )

        except Exception as error:
            logger.error(
                "Ошибка чтения очереди. Тип ошибки: %s",
                type(error).__name__,
            )

        await asyncio.sleep(60)