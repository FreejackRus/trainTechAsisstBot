import logging
import re
from datetime import datetime as dt_datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from handlers.renewalV2_handler import show_renewal_train_page, CALLBACK_RENEWAL_V2_TRAIN_SELECT
from states.renewal_states import ClaimRenewalV2
from utils.helpers import load_train_list
from utils.renewal_utils import show_renewal_summary_v2

logger = logging.getLogger(__name__)
router = Router()

# === Константы ===
LOCATIONS = {
    "renewalV2_loc_moscow": "Москва",
    "renewalV2_loc_spb": "Санкт-Петербург",
    "renewalV2_loc_simferopol": "Симферополь"
}
DEFAULT_TIMES = ["09:00", "10:00", "11:00", "12:00"]

ITEMS_PER_PAGE = 5
CALLBACK_RENEWAL_V2_PAGE_PREV = "renewalV2_page_prev"
CALLBACK_RENEWAL_V2_PAGE_NEXT = "renewalV2_page_next"
CALLBACK_RENEWAL_V2_SEARCH = "renewalV2_search_train"

# === Клавиатура редактирования ===
def get_edit_kb_v2():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить ФИО", callback_data="edit_renewalV2_executor_name")],
        [InlineKeyboardButton(text="Изменить номер поезда", callback_data="edit_renewalV2_train_number")],
        [InlineKeyboardButton(text="Изменить количество вагонов", callback_data="edit_renewalV2_wagon_count")],
        [InlineKeyboardButton(text="Изменить место", callback_data="edit_renewalV2_location")],
        [InlineKeyboardButton(text="Изменить дату", callback_data="edit_renewalV2_date")],
        [InlineKeyboardButton(text="Изменить время", callback_data="edit_renewalV2_time")],
        [InlineKeyboardButton(text="Изменить документ", callback_data="edit_renewalV2_document")],
        [InlineKeyboardButton(text="Назад к заявке", callback_data="renewalV2_back_to_summary")]
    ])


# === Начало режима редактирования ===
@router.callback_query(F.data == "renewalV2_edit_start")
async def edit_renewal_start(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Редактирование началось. Переход в режим editing.")
    await state.set_state(ClaimRenewalV2.editing)
    await callback.message.edit_text("Выберите поле для редактирования:", reply_markup=get_edit_kb_v2())
    await callback.answer()


# === Обработчики выбора полей для редактирования ===
@router.callback_query(
    F.data.in_([
        "edit_renewalV2_executor_name",
        "edit_renewalV2_train_number",
        "edit_renewalV2_wagon_count",
        "edit_renewalV2_location",
        "edit_renewalV2_date",
        "edit_renewalV2_time",
        "edit_renewalV2_document"
    ]),
    ClaimRenewalV2.editing
)
async def start_editing_field(callback: CallbackQuery, state: FSMContext):
    field_map = {
        "edit_renewalV2_executor_name": ("executor_name", "Введите новое ФИО исполнителя:"),
        "edit_renewalV2_train_number": ("train_number", "Выберите новый номер поезда:"),
        "edit_renewalV2_wagon_count": ("wagon_count", "Введите новое количество вагонов:"),
        "edit_renewalV2_location": ("location", "Выберите новое место проведения работ:"),
        "edit_renewalV2_date": ("date", "📅 Выберите новую дату нахождения состава в депо:"),
        "edit_renewalV2_time": ("time", "⏰ Выберите новое время:"),
        "edit_renewalV2_document": ("document", "📎 Прикрепите новый документ:")
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
        await state.set_state(ClaimRenewalV2.date)
        await state.update_data(editing_field="date")  # Сохраняем, что сейчас редактируем дату
        await callback.answer()
    elif field_name == "time":
        time_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=time, callback_data=f"renewalV2_time_{time}")]
            for time in DEFAULT_TIMES
        ] + [[InlineKeyboardButton(text="Другое время", callback_data="renewalV2_time_custom")]])
        await callback.message.answer(prompt, reply_markup=time_kb)
    elif field_name == "document":
        doc_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="skip_document")]
        ])
        await state.set_state(ClaimRenewalV2.document)
        await callback.message.answer(prompt, reply_markup=doc_kb)
    else:
        await callback.message.answer(prompt)

    await callback.answer()


# === Обработчик текстовых изменений полей ===
@router.message(ClaimRenewalV2.editing)
async def handle_edited_field(message: Message, state: FSMContext):
    logger.info(f"[v2] Получено значение для редактирования: {message.text}")
    data = await state.get_data()
    field_to_edit = data.get("editing_field")

    if not field_to_edit:
        await message.answer("❌ Не указано, какое поле редактировать.")
        return

    value = message.text.strip()

    # Проверки
    if field_to_edit == "wagon_count" and (not value.isdigit() or int(value) <= 0):
        await message.answer("❌ Введите корректное количество вагонов.")
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
    await show_renewal_summary_v2(message, state)


# === Обработчики поезда при редактировании ===
@router.callback_query(F.data == "edit_renewalV2_train_number", ClaimRenewalV2.editing)
async def edit_train_number(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Редактирование номера поезда | Состояние: {await state.get_state()}")
    data = await state.get_data()
    page = data.get("page", 0)
    await state.update_data(editing_field="train_number")
    await show_renewal_train_page(callback.message, state, page=page)
    await callback.answer()


@router.callback_query(F.data.startswith(CALLBACK_RENEWAL_V2_TRAIN_SELECT), ClaimRenewalV2.editing)
async def select_edited_train(callback: CallbackQuery, state: FSMContext):
    train_id = callback.data.replace(CALLBACK_RENEWAL_V2_TRAIN_SELECT, "", 1)
    await state.update_data(train_number=train_id)
    await callback.message.answer(f"✅ Поезд изменён на: {train_id}")
    await show_renewal_summary_v2(callback.message, state)
    await state.update_data(editing_field=None)
    await callback.answer()


@router.callback_query(F.data == CALLBACK_RENEWAL_V2_PAGE_PREV, ClaimRenewalV2.editing)
async def navigate_renewal_pages_prev(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = max(data.get("page", 0) - 1, 0)
    await state.update_data(page=page)
    await show_renewal_train_page(callback.message, state, page=page)
    await callback.answer()


@router.callback_query(F.data == CALLBACK_RENEWAL_V2_PAGE_NEXT, ClaimRenewalV2.editing)
async def navigate_renewal_pages_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get("page", 0) + 1
    await state.update_data(page=page)
    await show_renewal_train_page(callback.message, state, page=page)
    await callback.answer()


@router.callback_query(F.data == CALLBACK_RENEWAL_V2_SEARCH, ClaimRenewalV2.editing)
async def open_renewal_search_train(callback: CallbackQuery, state: FSMContext):
    logger.info("[v2] Поиск поезда при редактировании")
    await state.set_state(ClaimRenewalV2.train_search)
    await callback.message.answer("Введите часть номера поезда для поиска:")
    await callback.answer()


@router.message(ClaimRenewalV2.train_search, ClaimRenewalV2.editing)
async def search_edited_train(message: Message, state: FSMContext):
    query = message.text.strip().upper()
    data = await state.get_data()
    all_trains = data.get("trains", []) or load_train_list()
    results = [t for t in all_trains if t.upper().startswith(query)]

    if not results:
        await message.answer("❌ По вашему запросу поездов не найдено.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚆 Поезд №{train}", callback_data=f"{CALLBACK_RENEWAL_V2_TRAIN_SELECT}{train}")]
        for train in results[:10]
    ])

    await message.answer("Выберите поезд из результатов поиска:", reply_markup=kb)


# === Обработчики мест ===
@router.callback_query(F.data.startswith("renewalV2_loc_"), ClaimRenewalV2.editing)
async def handle_location_change(callback: CallbackQuery, state: FSMContext):
    location = LOCATIONS.get(callback.data, "Неизвестное место")
    await state.update_data(location=location)
    await callback.message.answer(f"✅ Место изменено на: {location}")
    await show_renewal_summary_v2(callback.message, state)
    await callback.answer()


# === Обработчики времени ===
@router.callback_query(F.data.startswith("renewalV2_time_"), ClaimRenewalV2.editing)
async def handle_time_change(callback: CallbackQuery, state: FSMContext):
    time = callback.data.replace("renewalV2_time_", "", 1)
    data = await state.get_data()
    new_datetime = f"{data['date']} {time}"
    await state.update_data(datetime=new_datetime, time=time)
    await callback.message.answer(f"✅ Время изменено на: {time}")
    await show_renewal_summary_v2(callback.message, state)
    await callback.answer()


@router.message(ClaimRenewalV2.custom_time, ClaimRenewalV2.editing)
async def save_custom_time(message: Message, state: FSMContext):
    time = message.text.strip()
    if not re.match(r"^(?:[01]\d|2[0-3]):(?:[0-5]\d)$", time):
        await message.answer("❌ Неверный формат времени. Используйте чч:мм (например, 08:30 или 14:45).")
        return

    data = await state.get_data()
    new_datetime = f"{data['date']} {time}"
    await state.update_data(datetime=new_datetime, time=time)
    await message.answer(f"✅ Время изменено на: {time}")
    await show_renewal_summary_v2(message, state)


@router.message(ClaimRenewalV2.date)
async def process_edit_date_input(message: Message, state: FSMContext):
    date_str = message.text.strip()

    try:
        # Парсим дату
        date_obj = dt_datetime.strptime(date_str, "%d.%m.%Y").date()
        formatted_date = date_obj.strftime("%d.%m.%Y")

        data = await state.get_data()
        new_datetime = f"{formatted_date} {data.get('time', '09:00')}"

        await state.update_data(date=formatted_date, datetime=new_datetime)
        await message.answer(f"✅ Дата изменена на: {formatted_date}")
        await show_renewal_summary_v2(message, state)
        await state.update_data(editing_field=None)  # Сбрасываем флаг редактирования

    except ValueError:
        await message.answer("❌ Неверный формат даты. Введите дату в формате дд.мм.гггг:")


# === Обработчики документа ===
@router.message(ClaimRenewalV2.document, ClaimRenewalV2.editing)
async def renewal_get_new_document(message: Message, state: FSMContext):
    logger.info(f"[v2] Загрузка нового документа | Состояние: {await state.get_state()}")
    if message.photo:
        file_id = message.photo[-1].file_id
        file_name = f"{file_id}.jpg"
    elif message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    else:
        await message.answer("❌ Отправьте фото или файл.")
        return

    await state.update_data(document={"file_id": file_id, "file_name": file_name})
    await message.answer("✅ Документ успешно заменён.")
    await show_renewal_summary_v2(message, state)


@router.callback_query(F.data == "skip_document", ClaimRenewalV2.editing)
async def skip_new_document(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Удаление документа | Состояние: {await state.get_state()}")
    await state.update_data(document=None)
    await callback.message.answer("✅ Документ удалён.")
    await show_renewal_summary_v2(callback.message, state)
    await callback.answer()


# === Возврат к сводке ===
@router.callback_query(F.data == "renewalV2_back_to_summary", ClaimRenewalV2.editing)
async def back_to_summary(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Возврат к сводке через кнопку")
    await show_renewal_summary_v2(callback.message, state)
    await callback.answer()