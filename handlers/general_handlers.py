from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from keyboards.inline_kb import get_main_menu_kb, get_claim_type_kb, get_cancel_kb

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()


# === /start ===
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    logger.info("Команда /start получена")
    await message.answer("🤖 Добро пожаловать в бот технической поддержки Peremena!\n\n", reply_markup=get_main_menu_kb())


# === Создать заявку ===
@router.callback_query(F.data == "main_menu_start")
async def create_claim(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await callback.answer("Сначала завершите или отмените текущую заявку.", show_alert=True)
        return

    try:
        await callback.message.edit_text("Выберите тип заявки:", reply_markup=get_claim_type_kb())
        await callback.answer()
    except Exception as e:
        logger.error(f"[create_claim] Ошибка при изменении сообщения: {e}")
        await callback.answer("Ошибка. Попробуйте позже.", show_alert=True)


# === Отменить (claim_type_cancel) ===
@router.callback_query(F.data == "claim_type_cancel")
async def handle_claim_type_cancel(callback: CallbackQuery):
    try:
        await callback.message.edit_text("Вы отменили создание заявки.", reply_markup=get_main_menu_kb())
        await callback.answer()
    except Exception as e:
        logger.error(f"[handle_claim_type_cancel] Ошибка: {e}")


# === Отменить (cancel_anywhere) ===
@router.callback_query(F.data == "cancel_anywhere")
async def cancel_anywhere(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    logger.info(f"[cancel_anywhere] Текущее состояние: {current_state}")

    if current_state:
        await state.clear()
        await callback.message.edit_text("Вы вышли из создания заявки.", reply_markup=get_main_menu_kb())
    else:
        await callback.message.edit_text("Вы уже в главном меню.", reply_markup=get_main_menu_kb())
    await callback.answer()


# === Помощь ===
@router.callback_query(F.data == "main_menu_help")
async def cmd_help(callback: CallbackQuery):
    help_text = (
        "📌 *Как работает этот бот?*\n\n"
        "1. /start — начать работу с ботом\n"
        "2. Выберите 'Создать заявку' → тип заявки → заполните форму\n"
        "3. Используйте 'Прочее (вручную)', если нужен свой вариант проблемы/работы\n"
        "4. После создания заявки она отправляется в GLPI\n"
        "5. С помощью 'Проверить статус заявок' вы можете посмотреть свои обращения\n"
        "Если у вас возникли вопросы — обратитесь к поддержке."
    )
    try:
        await callback.message.edit_text(help_text, parse_mode="Markdown", reply_markup=get_main_menu_kb())
        await callback.answer()
    except Exception as e:
        logger.error(f"[cmd_help] Ошибка: {e}")

# Импортируем функцию из status_handler
from handlers.status_handler import request_ticket_id


@router.callback_query(F.data == "main_menu_check_status")
async def check_status(callback: CallbackQuery, state: FSMContext):
    await request_ticket_id(callback.message, state)