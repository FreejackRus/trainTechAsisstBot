from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards.reply_kb import get_main_menu_kb, get_claim_type_kb

router = Router()

# === /start ===
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите действие:", reply_markup=get_main_menu_kb())

# === "Создать заявку" ===
@router.message(F.text == "Создать заявку")
async def create_claim_menu(message: Message):
    await message.answer("Выберите тип заявки:", reply_markup=get_claim_type_kb())

# === "Отменить" ===
@router.message(F.text == "Отменить")
async def cancel_anywhere(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("Вы вышли из создания заявки.", reply_markup=get_main_menu_kb())
    else:
        await message.answer("Вы уже в главном меню.", reply_markup=get_main_menu_kb()) 