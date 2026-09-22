import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv


load_dotenv()

try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
except KeyError as error:
    raise ValueError("В файле .env отсутствует BOT_TOKEN") from error

OPERATORS_CHAT_ID = os.getenv("OPERATORS_CHAT_ID")


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class TicketForm(StatesGroup):
    waiting_for_text = State()


def main_keyboard():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🆕 Создать обращение",
        callback_data="create_ticket"
    )
    builder.button(
        text="ℹ️ Помощь",
        callback_data="show_help"
    )

    builder.adjust(1)

    return builder.as_markup()


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(
        "Привет! Это бот поддержки.\n"
        "Выберите действие:",
        reply_markup=main_keyboard()
    )


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "Нажмите «Создать обращение», затем опишите проблему одним сообщением.",
        reply_markup=main_keyboard()
    )


@dp.callback_query(F.data == "show_help")
async def show_help_handler(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer(
            "Эта кнопка не поддерживается в таком режиме.",
            show_alert=True
        )
        return

    await callback.message.answer(
        "Нажмите «Создать обращение», затем отправьте описание проблемы."
    )
    await callback.answer()


@dp.callback_query(F.data == "create_ticket")
async def create_ticket_handler(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    if callback.message is None:
        await callback.answer(
            "Эта кнопка не поддерживается в таком режиме.",
            show_alert=True
        )
        return

    await state.set_state(TicketForm.waiting_for_text)

    await callback.message.answer(
        "📝 Напишите проблему одним сообщением.\n\n"
        "Для отмены отправьте /cancel."
    )
    await callback.answer()


@dp.message(TicketForm.waiting_for_text, Command("cancel"))
async def cancel_ticket_handler(
    message: Message,
    state: FSMContext
) -> None:
    await state.clear()

    await message.answer(
        "Создание обращения отменено.",
        reply_markup=main_keyboard()
    )


@dp.message(TicketForm.waiting_for_text, F.text)
async def receive_ticket_text(
    message: Message,
    state: FSMContext
) -> None:
    if message.from_user is None:
        await state.clear()
        await message.answer(
            "Не удалось определить отправителя обращения."
        )
        return

    if message.text is None:
        await message.answer(
            "Пожалуйста, отправьте проблему текстовым сообщением."
        )
        return

    user = message.from_user
    ticket_text = message.text

    if OPERATORS_CHAT_ID:
        await bot.send_message(
            chat_id=int(OPERATORS_CHAT_ID),
            text=(
                "🆕 Новое обращение\n\n"
                f"От: {user.full_name}\n"
                f"Telegram ID: {user.id}\n"
                f"Username: @{user.username or 'нет'}\n\n"
                f"Текст:\n{ticket_text}"
            )
        )

    await state.clear()

    await message.answer(
        "✅ Обращение принято.",
        reply_markup=main_keyboard()
    )

    await state.clear()

    await message.answer(
        "✅ Обращение принято.",
        reply_markup=main_keyboard()
    )


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())