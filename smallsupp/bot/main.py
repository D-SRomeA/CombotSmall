import asyncio
import logging
import os

from contextlib import suppress

from bot.sheets_sync import sync_loop
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from bot.storage import (
    init_db,
    save_request,
    get_user_branch,
    save_user_branch,
)

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
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL", "").strip()
APPS_SCRIPT_SECRET = os.getenv("APPS_SCRIPT_SECRET", "").strip()

if not APPS_SCRIPT_URL or not APPS_SCRIPT_SECRET:
    raise RuntimeError(
        "В .env необходимо задать APPS_SCRIPT_URL и APPS_SCRIPT_SECRET."
    )

class TicketForm(StatesGroup):
    waiting_for_text = State()
class RegistrationForm(StatesGroup):
    waiting_for_branch = State()

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
async def start_handler(message: Message, state: FSMContext) -> None:
    user = message.from_user

    if user is None:
        return

    user_branch = await asyncio.to_thread(
        get_user_branch,
        user.id,
    )

    if user_branch:
        await message.answer(
            "Здравствуйте! Это бот отдела.\n\n"
            f"Ваш филиал: {user_branch}\n\n"
            "Нажмите «Создать обращение», чтобы отправить сообщение сотрудникам.",
            reply_markup=main_keyboard(),
        )
        return

    await state.set_state(RegistrationForm.waiting_for_branch)

    await message.answer(
        "Здравствуйте! Для работы с ботом укажите название вашего филиала.\n\n"
        "Например: Филиал №127"
    )


@dp.message(RegistrationForm.waiting_for_branch, F.text)
async def receive_branch_handler(
    message: Message,
    state: FSMContext,
) -> None:
    user = message.from_user
    branch = message.text

    if user is None or branch is None:
        return

    branch = branch.strip()

    if not branch:
        await message.answer("Название филиала не должно быть пустым.")
        return

    await asyncio.to_thread(
        save_user_branch,
        user_id=user.id,
        username=user.username,
        branch=branch,
    )

    await state.clear()

    await message.answer(
        f"Филиал сохранён: {branch}\n\n"
        "Теперь вы можете создавать обращения.",
        reply_markup=main_keyboard(),
    )

@dp.message(RegistrationForm.waiting_for_branch, Command("cancel"))
async def cancel_registration_handler(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    await message.answer(
        "Регистрация филиала отменена. Отправьте /start, чтобы начать заново."
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
    if not isinstance(callback.message, Message):
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
    if not isinstance(callback.message, Message):
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

    user_branch = await asyncio.to_thread(
    get_user_branch,
    user.id,
)

    if not user_branch:
        await state.clear()
        await message.answer(
            "Сначала укажите ваш филиал. Для этого отправьте /start."
        )
        return    
    try:
        request_id = await asyncio.to_thread(
            save_request, branch=user_branch,
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

@dp.message(TicketForm.waiting_for_text)
async def unsupported_ticket_message(message: Message) -> None:
    await message.answer(
        "Сейчас принимаются только текстовые обращения.\n"
        "Опишите вопрос текстом или отправьте /cancel."
    )

@dp.message(F.chat.type == "private")
async def message_without_active_form(message: Message) -> None:
    await message.answer(
        "Чтобы зарегистрировать обращение, нажмите "
        "«Создать обращение».\n\n"
        "Если бот был перезапущен, начните создание заново.",
        reply_markup=main_keyboard(),
    )

async def main() -> None:
    await asyncio.to_thread(init_db)

    bot = Bot(token=BOT_TOKEN)

    sync_task = asyncio.create_task(
        sync_loop(APPS_SCRIPT_URL, APPS_SCRIPT_SECRET)
    )

    logger.info("База готова. Бот и синхронизация запущены")

    try:
        await dp.start_polling(bot)

    finally:
        sync_task.cancel()

        with suppress(asyncio.CancelledError):
            await sync_task

        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

