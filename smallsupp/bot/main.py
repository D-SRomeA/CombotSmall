import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("В файле .env не найден BOT_TOKEN")


dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(
        "Привет! Это тестовый бот поддержки.\n"
        "Напишите /help, чтобы увидеть доступные команды."
    )


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n"
        "/start — начать работу\n"
        "/help — показать помощь"
    )


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())