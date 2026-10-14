import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from bot.storage import init_db, save_request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

load_dotenv()

try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
except KeyError as error:
    raise RuntimeError(
        "Не найден BOT_TOKEN. Создайте .env в корне проекта."
    ) from error


class TicketForm(StatesGroup):
    waiting_for_text = State()


dp = Dispatcher()


def main_keyboard():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🆕 Создать обращение",
        callback_data="ticket:create",
    )
    builder.button(
        text="ℹ️ Помощь",
        callback_data="help:show",
    )

    builder.adjust(1)

    return builder.as_markup()


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(
        "Здравствуйте! Это бот отдела.\n\n"
        "Нажмите «Создать обращение», чтобы отправить сообщение сотрудникам.",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "1. Нажмите «Создать обращение».\n"
        "2. Одним сообщением опишите ваш вопрос.\n"
        "3. Сотрудник подготовит ответ.",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(F.data == "help:show")
async def show_help_handler(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer(
            "Исходное сообщение недоступно.",
            show_alert=True,
        )
        return

    await callback.message.answer(
        "Нажмите «Создать обращение» и отправьте текст одним сообщением."
    )
    await callback.answer()


@dp.callback_query(F.data == "ticket:create")
async def create_ticket_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.message is None:
        await callback.answer(
            "Исходное сообщение недоступно.",
            show_alert=True,
        )
        return

    await state.set_state(TicketForm.waiting_for_text)

    await callback.message.answer(
        "📝 Напишите ваше обращение одним текстовым сообщением.\n\n"
        "Чтобы отменить создание, используйте /cancel."
    )
    await callback.answer()


@dp.message(TicketForm.waiting_for_text, Command("cancel"))
async def cancel_ticket_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "Создание обращения отменено.",
        reply_markup=main_keyboard(),
    )


@dp.message(TicketForm.waiting_for_text, F.text)
async def receive_ticket_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if message.chat.type != "private":
        await message.answer("Обращение нужно отправить в личный чат с ботом.")
        return

    user = message.from_user
    text = message.text

    if user is None or text is None:
        await message.answer("Не удалось обработать сообщение.")
        return

    ticket_text = text.strip()

    if not ticket_text:
        await message.answer("Текст обращения не должен быть пустым.")
        return

    try:
        request_id = await asyncio.to_thread(
            save_request,
            received_at=message.date.isoformat(),
            chat_id=message.chat.id,
            telegram_message_id=message.message_id,
            user_id=user.id,
            username=user.username,
            message_text=ticket_text,
        )
    except Exception:
        logger.exception("Ошибка сохранения обращения")

        await message.answer(
            "Не удалось сохранить обращение.\n"
            "Попробуйте отправить текст ещё раз."
        )
        return

    await state.clear()

    logger.info("Обращение №%s сохранено", request_id)

    await message.answer(
        f"Обращение №{request_id} зарегистрировано.",
        reply_markup=main_keyboard(),
    )

async def main() -> None:
    await asyncio.to_thread(init_db)

    bot = Bot(token=BOT_TOKEN)

    logger.info("База данных готова. Запускаем бота")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())