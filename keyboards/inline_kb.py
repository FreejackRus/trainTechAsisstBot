from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


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
        InlineKeyboardButton(text="Прочее (вручную)", callback_data=f"{prefix}_other_manual")
    )
    return builder.as_markup()