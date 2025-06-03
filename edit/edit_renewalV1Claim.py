import logging
import re
from datetime import datetime as dt_datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from handlers.renewalV1_handler import show_renewal_train_page
from states.renewal_states import ClaimRenewal
from utils.helpers import load_train_list, is_wagon_sn_valid
from utils.renewal_utils import show_renewal_summary

logger = logging.getLogger(__name__)
router = Router()

# === Константы ===
LOCATIONS = {
    "renewalV1_loc_moscow": "Москва",
    "renewalV1_loc_spb": "Санкт-Петербург",
    "renewalV1_loc_simferopol": "Симферополь"
}
# constants.py
CALLBACK_RENEWAL_TRAIN_SELECT = "renewalV1_train_"
CALLBACK_RENEWAL_PAGE_PREV = "renewalV1_page_prev"
CALLBACK_RENEWAL_PAGE_NEXT = "renewalV1_page_next"
CALLBACK_RENEWAL_SEARCH = "renewalV1_search"
DEFAULT_TIMES = ["09:00", "10:00", "11:00", "12:00"]

ITEMS_PER_PAGE = 5

# === Клавиатура редактирования ===
def get_edit_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить ФИО", callback_data="edit_renewalV1_executor_name")],
        [InlineKeyboardButton(text="Изменить номер поезда", callback_data="edit_renewalV1_train_number")],
        [InlineKeyboardButton(text="Изменить серийный номер вагона", callback_data="edit_renewalV1_wagon_sn")],
        [InlineKeyboardButton(text="Изменить место", callback_data="edit_renewalV1_location")],
        [InlineKeyboardButton(text="Изменить дату", callback_data="edit_renewalV1_date")],
        [InlineKeyboardButton(text="Изменить время", callback_data="edit_renewalV1_time")],
        [InlineKeyboardButton(text="Изменить дополнительную информацию", callback_data="edit_renewalV1_comment")],
        [InlineKeyboardButton(text="Назад к заявке", callback_data="renewalV1_back_to_summary")]
    ])


# === Начало режима редактирования ===
@router.callback_query(F.data == "renewalV1_edit_start")
async def edit_renewal_start(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v1] Редактирование началось. Переход в режим editing.")
    await state.set_state(ClaimRenewal.editing)
    await callback.message.edit_text("Выберите поле для редактирования:", reply_markup=get_edit_kb())
    await callback.answer()


# === Обработчики выбора полей для редактирования ===
@router.callback_query(
    F.data.in_([
        "edit_renewalV1_executor_name",
        "edit_renewalV1_train_number",
        "edit_renewalV1_wagon_sn",
        "edit_renewalV1_location",
        "edit_renewalV1_date",
        "edit_renewalV1_time",
        "edit_renewalV1_comment"
    ]),
    ClaimRenewal.editing
)
async def start_editing_field(callback: CallbackQuery, state: FSMContext):
    field_map = {
        "edit_renewalV1_executor_name": ("executor_name", "Введите новое ФИО исполнителя:"),
        "edit_renewalV1_train_number": ("train_number", "Выберите новый номер поезда:"),
        "edit_renewalV1_wagon_sn": ("wagon_sn", "Введите новый серийный номер вагона:"),
        "edit_renewalV1_location": ("location", "Выберите новое место проведения работ:"),
        "edit_renewalV1_date": ("date", "📅 Выберите новую дату нахождения состава в депо:"),
        "edit_renewalV1_time": ("time", "⏰ Выберите новое время:"),
        "edit_renewalV1_comment": ("comment", "💬 Введите новую доп. информацию:")
    }

    field_key = callback.data
    field_info = field_map.get(field_key)

    if not field_info:
        await callback.message.answer("❌ Неизвестное поле редактирования.")
        return

    field_name, prompt = field_info
    await state.update_data(editing_field=field_name)

    # === Для каждого поля — свой переход ===
    data = await state.get_data()
    if field_name == "train_number":
        trains = data.get("trains", []) or load_train_list()
        page = data.get("page", 0)
        await state.update_data(trains=trains, page=page)
        await show_renewal_train_page(callback.message, state, page=page)
    elif field_name == "location":
        locations_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=loc, callback_data=key)] for key, loc in LOCATIONS.items()
        ])
        await callback.message.answer(prompt, reply_markup=locations_kb)
    elif field_name == "date":
        await callback.message.answer("📅 Введите новую дату в формате дд.мм.гггг:")
        await state.set_state(ClaimRenewal.date)
        await state.update_data(editing_field="date")  # Сохраняем, что сейчас редактируем дату
        await callback.answer()
    elif field_name == "time":
        time_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=time, callback_data=f"renewalV1_time_{time}")]
            for time in DEFAULT_TIMES
        ] + [[InlineKeyboardButton(text="Другое время", callback_data="renewalV1_time_custom")]])
        await callback.message.answer(prompt, reply_markup=time_kb)
    elif field_name == "comment":
        com_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="skip_comment")]
        ])
        await state.set_state(ClaimRenewal.comment)
        await callback.message.answer(prompt, reply_markup=com_kb)
    else:
        await callback.message.answer(prompt)

    await callback.answer()


# === Обработчик текстовых изменений полей ===
@router.message(ClaimRenewal.editing)
async def handle_edited_field(message: Message, state: FSMContext):
    logger.info(f"[1] Получено значение для редактирования: {message.text}")
    data = await state.get_data()
    field_to_edit = data.get("editing_field")

    if not field_to_edit:
        await message.answer("❌ Не указано, какое поле редактировать.")
        return

    value = message.text.strip()

    # Проверки
    if field_to_edit == "wagon_sn" and len(value) < 6 or not is_wagon_sn_valid(value):
        await message.answer("❌ Вагон с таким серийным номером не найден в базе.")
        return
    elif field_to_edit == "time" and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", value):
        await message.answer("❌ Неверный формат времени. Используйте чч:мм")
        return
    elif field_to_edit == "date" and not re.match(r"\d{2}\.\d{2}\.\d{4}", value):
        await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
        return

    # Сохранение данных
    update_dict = {field_to_edit: value}
    await state.update_data(update_dict)
    await message.answer(f"✅ Поле '{field_to_edit}' обновлено.")

    # Очистка флага и показ сводки
    await state.update_data(editing_field=None)
    await show_renewal_summary(message, state)


# === Обработчики поезда при редактировании ===
@router.callback_query(F.data == "edit_renewalV1_train_number", ClaimRenewal.editing)
async def edit_train_number(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Редактирование номера поезда | Состояние: {await state.get_state()}")
    data = await state.get_data()
    page = data.get("page", 0)
    await state.update_data(editing_field="train_number")
    await show_renewal_train_page(callback.message, state, page=page)
    await callback.answer()


@router.callback_query(F.data.startswith(CALLBACK_RENEWAL_TRAIN_SELECT), ClaimRenewal.editing)
async def select_edited_train(callback: CallbackQuery, state: FSMContext):
    train_id = callback.data.replace(CALLBACK_RENEWAL_TRAIN_SELECT, "", 1)
    await state.update_data(train_number=train_id)
    await callback.message.answer(f"✅ Поезд изменён на: {train_id}")
    await show_renewal_summary(callback.message, state)
    await state.update_data(editing_field=None)
    await callback.answer()


@router.callback_query(F.data == CALLBACK_RENEWAL_PAGE_PREV, ClaimRenewal.editing)
async def navigate_renewal_pages_prev(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = max(data.get("page", 0) - 1, 0)
    await state.update_data(page=page)
    await show_renewal_train_page(callback.message, state, page=page)
    await callback.answer()


@router.callback_query(F.data == CALLBACK_RENEWAL_PAGE_NEXT, ClaimRenewal.editing)
async def navigate_renewal_pages_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get("page", 0) + 1
    await state.update_data(page=page)
    await show_renewal_train_page(callback.message, state, page=page)
    await callback.answer()


@router.callback_query(F.data == CALLBACK_RENEWAL_SEARCH, ClaimRenewal.editing)
async def open_renewal_search_train(callback: CallbackQuery, state: FSMContext):
    logger.info("[v2] Поиск поезда при редактировании")
    await state.set_state(ClaimRenewal.train_search)
    await callback.message.answer("Введите часть номера поезда для поиска:")
    await callback.answer()


@router.message(ClaimRenewal.train_search, ClaimRenewal.editing)
async def search_edited_train(message: Message, state: FSMContext):
    query = message.text.strip().upper()
    data = await state.get_data()
    all_trains = data.get("trains", []) or load_train_list()
    results = [t for t in all_trains if t.upper().startswith(query)]

    if not results:
        await message.answer("❌ По вашему запросу поездов не найдено.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚆 Поезд №{train}", callback_data=f"{CALLBACK_RENEWAL_TRAIN_SELECT}{train}")]
        for train in results[:10]
    ])

    await message.answer("Выберите поезд из результатов поиска:", reply_markup=kb)


# === Обработчики мест ===
@router.callback_query(F.data.startswith("renewalV1_loc_"), ClaimRenewal.editing)
async def handle_location_change(callback: CallbackQuery, state: FSMContext):
    location = LOCATIONS.get(callback.data, "Неизвестное место")
    await state.update_data(location=location)
    await callback.message.answer(f"✅ Место изменено на: {location}")
    await show_renewal_summary(callback.message, state)
    await callback.answer()


# === Обработчики времени ===
@router.callback_query(F.data.startswith("renewalV1_time_"), ClaimRenewal.editing)
async def handle_time_change(callback: CallbackQuery, state: FSMContext):
    time = callback.data.replace("renewalV1_time_", "", 1)
    data = await state.get_data()
    new_datetime = f"{data['date']} {time}"
    await state.update_data(datetime=new_datetime, time=time)
    await callback.message.answer(f"✅ Время изменено на: {time}")
    await show_renewal_summary(callback.message, state)
    await callback.answer()


@router.message(ClaimRenewal.time, ClaimRenewal.editing)
async def save_custom_time(message: Message, state: FSMContext):
    time = message.text.strip()
    if not re.match(r"^(?:[01]\d|2[0-3]):(?:[0-5]\d)$", time):
        await message.answer("❌ Неверный формат времени. Используйте чч:мм (например, 08:30 или 14:45).")
        return

    data = await state.get_data()
    new_datetime = f"{data['date']} {time}"
    await state.update_data(datetime=new_datetime, time=time)
    await message.answer(f"✅ Время изменено на: {time}")
    await show_renewal_summary(message, state)


@router.message(ClaimRenewal.date)
async def process_edit_date_input(message: Message, state: FSMContext):
    date_str = message.text.strip()

    try:
        # Парсим дату
        date_obj = dt_datetime.strptime(date_str, "%d.%m.%Y").date()

        # today = dt_datetime.now().date()
        # yesterday = today - timedelta(days=1)
        #
        # if date_obj not in [today, yesterday]:
        #     await message.answer("❌ Допускается ввод только сегодняшней или вчерашней даты. Введите дату в формате дд.мм.гггг:")
        #     return

        formatted_date = date_obj.strftime("%d.%m.%Y")

        data = await state.get_data()
        new_datetime = f"{formatted_date} {data.get('time', '09:00')}"

        await state.update_data(date=formatted_date, datetime=new_datetime)
        await message.answer(f"✅ Дата изменена на: {formatted_date}")
        await show_renewal_summary(message, state)
        await state.update_data(editing_field=None)  # Сбрасываем флаг редактирования

    except ValueError:
        await message.answer("❌ Неверный формат даты. Введите дату в формате дд.мм.гггг:")


# === Обработчики документа ===
@router.message(F.data.startswith("renewalV1_comment_"), ClaimRenewal.editing)
async def renewal_get_new_comment(message: Message, state: FSMContext):
    comment = message.text.strip()

    data = await state.get_data()
    new_comment = f"{data['comment']} {comment}"
    await state.update_data( comment=new_comment)
    await message.answer(f"✅ Комментарий изменен  на: {comment}")
    await show_renewal_summary(message, state)


@router.callback_query(F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v1] Удаление комментария | Состояние: {await state.get_state()}")
    await state.update_data(comment=None)
    await callback.message.answer("✅ Комментарий пропущен.")
    await show_renewal_summary(callback.message, state)
    await callback.answer()


# === Возврат к сводке ===
@router.callback_query(F.data == "renewalV1_back_to_summary", ClaimRenewal.editing)
async def back_to_summary(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v1] Возврат к сводке через кнопку")
    await show_renewal_summary(callback.message, state)
    await callback.answer()