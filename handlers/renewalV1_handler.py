import logging
import re
from datetime import datetime as dt_datetime, timedelta

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from glpi_api import connect
from keyboards.inline_kb import get_cancel_kb, get_return_main_menu_kb
from states.renewal_states import ClaimRenewal
from utils.helpers import load_train_list, is_wagon_sn_valid
from utils.renewal_utils import show_renewal_summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = Router()

# === Константы ===
LOCATIONS = {
    "renewalV1_loc_moscow": "Москва",
    "renewalV1_loc_spb": "Санкт-Петербург",
    "renewalV1_loc_simferopol": "Симферополь"
}

# === Константы ===
ITEMS_PER_PAGE = 5
CALLBACK_RENEWAL_TRAIN_SELECT = "renewal_train_"
CALLBACK_RENEWAL_PAGE_PREV = "renewal_page_prev"
CALLBACK_RENEWAL_PAGE_NEXT = "renewal_page_next"
CALLBACK_RENEWAL_SEARCH = "renewal_search_train"


# === Отображение страницы со списком поездов ===
async def show_renewal_train_page(message: Message, state: FSMContext, page: int):
    data = await state.get_data()
    trains = data.get("trains", [])
    if not trains:
        await message.answer("❌ Список поездов пуст.")
        return

    # Пагинация
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_trains = trains[start_idx:end_idx]

    keyboard = InlineKeyboardBuilder()

    # Кнопки для поездов — каждая на новой строке
    for train_id in page_trains:
        train_text = f"🚆 Поезд №{train_id}"
        keyboard.button(
            text=train_text,
            callback_data=f"{CALLBACK_RENEWAL_TRAIN_SELECT}{train_id}"
        )

    # Навигационные кнопки
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=CALLBACK_RENEWAL_PAGE_PREV))
    if end_idx < len(trains):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=CALLBACK_RENEWAL_PAGE_NEXT))

    if nav_buttons:
        keyboard.row(*nav_buttons)

    # Поиск
    keyboard.row(InlineKeyboardButton(text="🔍 Поиск поезда", callback_data=CALLBACK_RENEWAL_SEARCH))

    # Устанавливаем одну кнопку в строку
    keyboard.adjust(1)  # Это гарантирует, что каждая кнопка будет на своей строке

    # Отправляем или редактируем сообщение
    try:
        await message.edit_text("Выберите поезд:", reply_markup=keyboard.as_markup())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        elif "message can't be edited" in str(e):
            await message.answer("Выберите поезд:", reply_markup=keyboard.as_markup())
        else:
            raise
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        await message.answer("Выберите поезд:", reply_markup=keyboard.as_markup())

    await state.update_data(page=page)


@router.callback_query(F.data == "claim_type_equipment_v1")
async def handle_equipment(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v1] Получен callback: claim_type_equipment_v1 | Текущее состояние: {await state.get_state()}")
    current_state = await state.get_state()
    if current_state != ClaimRenewal.none:
        await state.clear()
    await callback.message.answer("Вы выбрали 'Переоснащение v1'.")
    await state.set_state(ClaimRenewal.executor_name)
    await callback.message.answer("Введите ФИО ответственного сотрудника:", reply_markup=get_cancel_kb())
    await callback.answer()


@router.message(ClaimRenewal.executor_name)
async def renewal_executor_name(message: Message, state: FSMContext):
    logger.info(f"[v1] Введите ФИО ответственного сотрудника | Текущее состояние: {await state.get_state()}")
    if len(message.text.strip()) < 2:
        await message.answer("❌ ФИО должно содержать минимум 2 символа.")
        return
    await state.update_data(executor_name=message.text)
    await message.answer(f"✅ ФИО ответственного сотрудника: {message.text}") # Added line
    data = await state.get_data()
    trains = data.get("trains", [])
    if not trains:
        trains = load_train_list()
        if not trains:
            await message.answer("❌ Список поездов пуст или не найден.")
            return
    await state.update_data(trains=trains, page=0)
    await show_renewal_train_page(message, state, 0)


@router.callback_query(F.data == CALLBACK_RENEWAL_PAGE_PREV)
async def navigate_renewal_pages_prev(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v1] Навигация назад | Callback: {callback.data} | Состояние: {await state.get_state()}")
    data = await state.get_data()
    page = data.get("page", 0) - 1
    await state.update_data(page=page)
    await show_renewal_train_page(callback.message, state, page)


@router.callback_query(F.data == CALLBACK_RENEWAL_PAGE_NEXT)
async def navigate_renewal_pages_next(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v1] Навигация вперёд | Callback: {callback.data} | Состояние: {await state.get_state()}")
    data = await state.get_data()
    page = data.get("page", 0) + 1
    await state.update_data(page=page)
    await show_renewal_train_page(callback.message, state, page)


@router.callback_query(F.data.startswith(CALLBACK_RENEWAL_TRAIN_SELECT))
async def select_renewal_train(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v1] Выбор поезда | Callback: {callback.data} | Состояние: {await state.get_state()}")
    renewal_train_number = callback.data.replace(CALLBACK_RENEWAL_TRAIN_SELECT, "", 1)
    await callback.message.answer(f"✅ Номер поезда: {renewal_train_number}") # Added line
    await state.update_data(train_number=renewal_train_number)
    await state.set_state(ClaimRenewal.wagon_sn)
    await callback.message.answer("Введите серийный номер вагона:", reply_markup=get_cancel_kb())
    await callback.answer()


@router.callback_query(F.data == CALLBACK_RENEWAL_SEARCH)
async def open_renewal_search_train(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v1] Поиск поезда | Callback: {callback.data} | Состояние: {await state.get_state()}")
    await callback.message.answer("Введите часть номера поезда для поиска:")
    await state.set_state(ClaimRenewal.train_search)
    await callback.answer()


@router.message(ClaimRenewal.train_search)
async def search_renewal_train(message: Message, state: FSMContext):
    logger.info(f"[v1] Поиск поезда по тексту | Состояние: {await state.get_state()}")
    query = message.text.strip().upper()
    data = await state.get_data()
    all_trains = data.get("trains", []) or load_train_list()
    results = [t for t in all_trains if t.upper().startswith(query)]
    if not results:
        await message.answer("❌ По вашему запросу поездов не найдено.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=train, callback_data=f"{CALLBACK_RENEWAL_TRAIN_SELECT}{train}")]
        for train in results[:10]
    ])
    await message.answer("Выберите поезд из результатов поиска:", reply_markup=kb)




@router.message(ClaimRenewal.wagon_sn)
async def renewal_wagon_sn(message: Message, state: FSMContext):
    logger.info(f"[v1] Ввод серийного номера вагона | Состояние: {await state.get_state()}")
    sn = message.text.strip()
    if len(sn) < 6:
        await message.answer("❌ Серийный номер должен содержать минимум 6 символов.")
        return
    # Проверка наличия в базе (в файле)
    if not await is_wagon_sn_valid(sn):
        await message.answer("❌ Вагон с таким серийным номером не найден в базе.")
        return
    await state.update_data(wagon_sn=sn)
    await message.answer(f"✅ Серийный номер вагона: {sn}") # Added line
    await state.set_state(ClaimRenewal.location)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=loc, callback_data=key)] for key, loc in LOCATIONS.items()
    ])
    await message.answer("Выберите место проведения работ:", reply_markup=kb)


@router.callback_query(F.data.startswith("renewalV1_loc_"), ClaimRenewal.location)
async def renewal_location(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v1] Выбор места | Callback: {callback.data} | Состояние: {await state.get_state()}")
    location = LOCATIONS.get(callback.data, "Неизвестное место")
    await state.update_data(location=location)
    await callback.message.answer(f"✅ Место проведения работ: {location}")

    # Переход к вводу даты
    await state.set_state(ClaimRenewal.date)
    await callback.message.answer("📅 Введите дату нахождения состава в депо в формате дд.мм.гггг:")
    await callback.answer()


@router.message(ClaimRenewal.date)
async def process_date_input(message: Message, state: FSMContext):
    date_str = message.text.strip()
    try:
        # Парсим дату
        date_obj = dt_datetime.strptime(date_str, "%d.%m.%Y").date()
        formatted_date = date_obj.strftime("%d.%m.%Y")
        
        today = dt_datetime.now().date()
        tomorrow = today + timedelta(days=1)

        if date_obj < tomorrow:
            await message.answer("❌ Допускается ввод только завтрашней или будующей даты. Введите дату в формате дд.мм.гггг:")
            return ValueError

        await state.update_data(date=formatted_date)
        await message.answer(f"✅ Дата: {formatted_date}") # Added line

        # Запрашиваем ручной ввод времени
        await message.answer(f"📅 Дата выбрана: {formatted_date}\n⏰ Введите время в формате чч:мм (например, 08:30):")
        await state.set_state(ClaimRenewal.time)

    except ValueError:
        await message.answer("❌ Неверный формат даты. Введите дату в формате дд.мм.гггг:")


@router.message(ClaimRenewal.time)
async def renewal_custom_time(message: Message, state: FSMContext):
    logger.info(f"[v1] Ввод времени вручную | Состояние: {await state.get_state()}")
    time = message.text.strip()

    # Проверяем формат времени (чч:мм, часы 00-23, минуты 00-59)
    if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", time):
        await message.answer(
            "❌ Неверный формат времени. Используйте чч:мм (например, 08:30 или 14:45)."
        )
        return

    data = await state.get_data()
    full_datetime = f"{data['date']} {time}"
    await state.update_data(datetime=full_datetime)
    await message.answer(f"✅ Время: {time}") # Added line
    await state.set_state(ClaimRenewal.comment)

    await message.answer(
        "💬 Введите дополнительную информацию или нажмите Пропустить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="skip_comment")]
        ])
    )


@router.callback_query(F.data == "skip_comment", ClaimRenewal.comment)
async def skip_comment(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v1] Пропуск комментария | Callback: {callback.data} | Состояние: {await state.get_state()}")
    await state.update_data(comment="-")
    await show_renewal_summary(callback.message, state)
    await callback.answer()


@router.message(ClaimRenewal.comment)
async def renewal_comment(message: Message, state: FSMContext):
    logger.info(f"[v1] Ввод комментария | Состояние: {await state.get_state()}")
    await state.update_data(comment=message.text)
    await message.answer(f"✅ Комментарий: {message.text}") # Added line
    await show_renewal_summary(message, state)


@router.callback_query(F.data == "create_renewal_claim", ClaimRenewal.confirmation)
async def create_renewal_claim(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v1] Создание заявки | Callback: {callback.data} | Состояние: {await state.get_state()}")
    data = await state.get_data()
    data.setdefault('comment', '')
    try:
        with connect(config.GLPI_URL, config.GLPI_APP_TOKEN, config.GLPI_USER_TOKEN, False) as glpi:
            content = (
                f"Заявка создана через Telegram\n#телеграм\n"
                f"ФИО исполнителя: {data['executor_name']}\n"
                f"Поезд: {data['train_number']}\n"
                f"Количество вагонов: 1\n"
                f"Серийный номер вагона: {data['wagon_sn']}\n"
                f"Место: {data['location']}\n"
                f"Дата и время: {data['datetime']}\n"
                f"Комментарий: {data['comment']}"
            )
            ticket_result = glpi.add("Ticket", {
                "name": "API GLPI - Переоснащение",
                "content": content,
                "urgency": 4,
                "impact": 4,
                "priority": 4,
                "type": 1,
                "requesttypes_id": 1,
                "itilcategories_id": 38,
                "entities_id": 16,
                "_users_id_observer": [22]
            })
            ticket_id = ticket_result[0]["id"]
            claim_info = (
                "✅ Заявка успешно создана в системе GLPI!\n"
                f"🔢 Номер заявки: {ticket_id}\n"
                f"📍 Поезд: {data['train_number']}, "
                f"📍 Вагон: {data['wagon_sn']}"
            )
            await callback.message.answer(claim_info, reply_markup=get_return_main_menu_kb())
            await state.clear()
    except Exception as e:
        logger.error(f"[GLPI Error] {e}")
        await callback.message.answer(
            "❌ Не удалось создать заявку в GLPI.\nПопробуйте позже.",
            reply_markup=get_return_main_menu_kb()
        )
        await state.clear()
