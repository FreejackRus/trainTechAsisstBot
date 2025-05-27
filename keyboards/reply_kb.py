from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_menu_kb():
    kb = [
        [KeyboardButton(text="Создать заявку")],
        [KeyboardButton(text="Проверить статус заявок")],
        [KeyboardButton(text="Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_claim_type_kb():
    kb = [
        [KeyboardButton(text="Восстановление работоспособности")],
        [KeyboardButton(text="Переоснащение")],
        [KeyboardButton(text="Отменить")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отменить")]],
        resize_keyboard=True
    )