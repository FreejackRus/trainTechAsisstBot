from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards.reply_kb import get_main_menu_kb, get_claim_type_kb

router = Router()

# === /start ===
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer( "🤖 Добро пожаловать в бот технической поддержки Peremena!\n\n"
        "Выберите действие:\n", reply_markup=get_main_menu_kb())

# === /help ===
@router.message(F.text == "Помощь")
async def cmd_help(message: Message):
    help_text = (
        "📌 *Как работает этот бот?*\n\n"
        "1. /start — начать работу с ботом\n"
        "2. Выберите 'Создать заявку' → тип заявки → заполните форму\n"
        "3. Используйте 'Прочее (вручную)', если нужен свой вариант проблемы/работы\n"
        "4. После создания заявки она отправляется в GLPI\n"
        "5. С помощью 'Проверить статус заявок' вы можете посмотреть свои обращения\n"
        "Если у вас возникли вопросы — обратитесь к поддержке."
    )
    await message.answer(help_text, parse_mode="Markdown")
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