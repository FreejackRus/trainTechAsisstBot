from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# === Главное меню — только кнопка "Начать" ===
def get_main_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Начать", callback_data="main_menu_start")
    )
    return builder.as_markup()

def get_return_main_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Вернуться в начало", callback_data="main_menu_start")
    )
    return builder.as_markup()

# === Типы заявок — теперь здесь наши новые кнопки ===
def get_claim_type_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Переоснащение", callback_data="main_menu_renewal")
    )
    builder.row(
        InlineKeyboardButton(text="Восстановление работы", callback_data="claim_type_restoration")
    )
    builder.row(
        InlineKeyboardButton(text="Проверить статус заявки", callback_data="main_menu_check_status")
    )
    return builder.as_markup()

# === Новая клавиатура для переоснащения ===
def get_renewal_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Переоснащение вагона", callback_data="claim_type_equipment_v1"),
        InlineKeyboardButton(text="Переоснащение нескольких вагонов", callback_data="claim_type_equipment_v2")
    )
    builder.row(
        InlineKeyboardButton(text="Вернуться в главное меню", callback_data="main_menu_start")
    )
    return builder.as_markup()

# === Клавиатура с чекбоксами (остаётся без изменений) ===
def get_checkbox_kb_with_other(options: list, selected: list = None, prefix="default"):
    if selected is None:
        selected = []
    builder = InlineKeyboardBuilder()
    for idx, option in enumerate(options):
        emoji = "✅" if idx in selected else "⬜"
        builder.add(InlineKeyboardButton(
            text=f"{emoji} {option}",
            callback_data=f"{prefix}_check_{idx}"
        ))
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="Готово", callback_data=f"{prefix}_done"),
        InlineKeyboardButton(text="Иное (прописать)", callback_data=f"{prefix}_other_manual")
    )
    return builder.as_markup()

# === Кнопка отмены ===
def get_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отменить", callback_data="cancel_anywhere")]
    ])

def get_retry_or_main_menu_kb():
            buttons = [
                [InlineKeyboardButton(text="🔄 Ввести другой ID", callback_data="retry_ticket_id")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu_start")]
            ]
            return InlineKeyboardMarkup(inline_keyboard=buttons)