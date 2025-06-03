import logging
import os
import re
from datetime import datetime as dt_datetime, timedelta

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import glpi_api
from keyboards.inline_kb import get_cancel_kb, get_return_main_menu_kb
from states.renewal_states import ClaimRenewalV2
from utils.helpers import load_train_list
from utils.renewal_utils import download_file, show_renewal_summary_v2

# === Настройка логирования ===
logging.basicConfig(level=logging.INFO)
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
CALLBACK_RENEWAL_V2_TRAIN_SELECT = "renewalV2_train_"
CALLBACK_RENEWAL_V2_PAGE_PREV = "renewalV2_page_prev"
CALLBACK_RENEWAL_V2_PAGE_NEXT = "renewalV2_page_next"
CALLBACK_RENEWAL_V2_SEARCH = "renewalV2_search_train"


# === Отображение страницы со списком поездов ===
async def show_renewal_train_page(message: Message, state: FSMContext, page: int):
    data = await state.get_data()
    trains = data.get("trains", [])

    if not trains:
        trains = load_train_list()
        if not trains:
            await message.answer("❌ Список поездов пуст или не найден.")
            return

    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_trains = trains[start_idx:end_idx]

    kb = InlineKeyboardBuilder()
    for train_id in page_trains:
        kb.button(text=f"🚆 Поезд №{train_id}", callback_data=f"{CALLBACK_RENEWAL_V2_TRAIN_SELECT}{train_id}")

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=CALLBACK_RENEWAL_V2_PAGE_PREV))
    if end_idx < len(trains):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=CALLBACK_RENEWAL_V2_PAGE_NEXT))

    if nav_buttons:
        kb.row(*nav_buttons)

    kb.row(InlineKeyboardButton(text="🔍 Поиск поезда", callback_data=CALLBACK_RENEWAL_V2_SEARCH))
    kb.adjust(1)  # Каждая кнопка на новой строке

    try:
        await message.edit_text("Выберите поезд:", reply_markup=kb.as_markup())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        elif "message can't be edited" in str(e):
            await message.answer("Выберите поезд:", reply_markup=kb.as_markup())
        else:
            raise
    await state.update_data(page=page)


# === Выбор типа заявки ===
@router.callback_query(F.data == "claim_type_equipment_v2")
async def handle_equipment(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Получен callback: claim_type_equipment_v2 | Состояние: {await state.get_state()}")
    current_state = await state.get_state()
    if current_state != ClaimRenewalV2.none:
        await state.clear()

    await callback.message.answer("Вы выбрали 'Переоснащение v2'.")
    await state.set_state(ClaimRenewalV2.executor_name)
    await callback.message.answer("Введите ФИО исполнителя:", reply_markup=get_cancel_kb())
    await callback.answer()


# === Ввод ФИО исполнителя ===
@router.message(ClaimRenewalV2.executor_name)
async def renewal_executor_name(message: Message, state: FSMContext):
    logger.info(f"[v2] Ввод ФИО исполнителя | Состояние: {await state.get_state()}")
    if len(message.text.strip()) < 2:
        await message.answer("❌ ФИО должно содержать минимум 2 символа.")
        return

    await state.update_data(executor_name=message.text)
    data = await state.get_data()
    trains = data.get("trains", [])
    if not trains:
        trains = load_train_list()
        if not trains:
            await message.answer("❌ Список поездов пуст или не найден.")
            return

    await state.update_data(trains=trains, page=0)
    await show_renewal_train_page(message, state, 0)


# === Навигация по списку поездов ===
@router.callback_query(F.data == CALLBACK_RENEWAL_V2_PAGE_PREV)
async def navigate_renewal_pages_prev(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Навигация назад | Callback: {callback.data} | Состояние: {await state.get_state()}")
    data = await state.get_data()
    page = max(data.get("page", 0) - 1, 0)
    await state.update_data(page=page)
    await show_renewal_train_page(callback.message, state, page)


@router.callback_query(F.data == CALLBACK_RENEWAL_V2_PAGE_NEXT)
async def navigate_renewal_pages_next(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Навигация вперёд | Callback: {callback.data} | Состояние: {await state.get_state()}")
    data = await state.get_data()
    page = data.get("page", 0) + 1
    await state.update_data(page=page)
    await show_renewal_train_page(callback.message, state, page)


# === Выбор поезда из списка ===
@router.callback_query(F.data.startswith(CALLBACK_RENEWAL_V2_TRAIN_SELECT))
async def select_renewal_train(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Выбор поезда | Callback: {callback.data} | Состояние: {await state.get_state()}")
    train_number = callback.data.replace(CALLBACK_RENEWAL_V2_TRAIN_SELECT, "", 1)
    data = await state.get_data()

    # Проверяем режим: создание или редактирование
    if data.get("editing_field") == "train_number":
        await state.update_data(train_number=train_number)
        await callback.message.answer(f"✅ Номер поезда изменён на: {train_number}")
        await show_renewal_summary_v2(callback.message, state)
        await state.update_data(editing_field=None)
    else:
        await state.update_data(train_number=train_number)
        await callback.message.answer(f"✅ Номер поезда: {train_number}")  # Added line
        await state.set_state(ClaimRenewalV2.wagon_count)
        await callback.message.answer("Введите количество вагонов:", reply_markup=get_cancel_kb())

    await callback.answer()


# === Поиск поезда ===
@router.callback_query(F.data == CALLBACK_RENEWAL_V2_SEARCH)
async def open_renewal_search_train(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Поиск поезда | Callback: {callback.data} | Состояние: {await state.get_state()}")
    await callback.message.answer("Введите часть номера поезда для поиска:")
    await state.set_state(ClaimRenewalV2.train_search)
    await callback.answer()


@router.message(ClaimRenewalV2.train_search)
async def search_renewal_train(message: Message, state: FSMContext):
    logger.info(f"[v2] Поиск поезда по тексту | Состояние: {await state.get_state()}")
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


# === Ввод количества вагонов ===
@router.message(ClaimRenewalV2.wagon_count)
async def renewal_wagon_count(message: Message, state: FSMContext):
    logger.info(f"[v2] Ввод количества вагонов | Состояние: {await state.get_state()}")
    count = message.text.strip()
    if not count.isdigit() or int(count) <= 0 or int(count)>26:
        await message.answer("❌ Введите корректное количество вагонов.")
        return

    data = await state.get_data()
    if data.get("editing_field") == "wagon_count":
        await state.update_data(wagon_count=count)
        await message.answer(f"✅ Количество вагонов изменено на: {count}")
        await show_renewal_summary_v2(message, state)
        await state.update_data(editing_field=None)
    else:
        await state.update_data(wagon_count=count)
        await state.set_state(ClaimRenewalV2.location)
        await message.answer(f"✅ Количество вагонов : {count}")
        await message.answer(
            "Выберите место проведения работ:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=loc, callback_data=key)]
                for key, loc in LOCATIONS.items()
            ])
        )




# === Выбор места ===
@router.callback_query(F.data.startswith("renewalV2_loc_"), ClaimRenewalV2.location)
async def renewal_location(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Выбор места | Callback: {callback.data} | Состояние: {await state.get_state()}")
    location = LOCATIONS.get(callback.data, "Неизвестное место")

    data = await state.get_data()
    if data.get("editing_field") == "location":
        await state.update_data(location=location)
        await callback.message.answer(f"✅ Место изменено на: {location}")
        await show_renewal_summary_v2(callback.message, state)
        await state.update_data(editing_field=None)
    else:
        await state.update_data(location=location)
        await callback.message.answer(f"✅ Место проведения работ: {location}")
        await state.set_state(ClaimRenewalV2.date)
        await callback.message.answer("📅 Введите дату нахождения состава в депо в формате дд.мм.гггг:")

    await callback.answer()


@router.message(ClaimRenewalV2.date)
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
        data = await state.get_data()
        new_datetime = f"{formatted_date} {data.get('time', '09:00')}"

        if data.get("editing_field") == "date":
            await state.update_data(date=formatted_date, datetime=new_datetime)
            await message.answer(f"✅ Дата изменена на: {formatted_date}")
            await show_renewal_summary_v2(message, state)
            await state.update_data(editing_field=None)
        else:
            await state.update_data(date=formatted_date, datetime=new_datetime)
            await message.answer("⏰ Введите время в формате чч:мм (например, 09:00):")
            await state.set_state(ClaimRenewalV2.custom_time)

    except ValueError:
        await message.answer("❌ Неверный формат даты. Введите дату в формате дд.мм.гггг:")



@router.message(ClaimRenewalV2.custom_time)
async def renewal_custom_time(message: Message, state: FSMContext):
    logger.info(f"[v2] Ввод времени вручную | Состояние: {await state.get_state()}")
    time = message.text.strip()

    # Проверяем формат времени
    if not re.match(r"^(?:[01]\d|2[0-3]):(?:[0-5]\d)$", time):
        await message.answer(
            "❌ Неверный формат времени. Используйте чч:мм (например, 08:30 или 14:45)."
        )
        return

    # Если время корректно, обновляем данные
    data = await state.get_data()
    full_datetime = f"{data['date']} {time}"
    await state.update_data(datetime=full_datetime, time=time)

    # Если редактируется время
    if data.get("editing_field") == "time":
        await message.answer(f"✅ Время изменено на: {time}")
        await show_renewal_summary_v2(message, state)
        await state.update_data(editing_field=None)
    else:
        # Переход к следующему шагу
        await state.set_state(ClaimRenewalV2.document)
        file_path = "files/Form.doc"
        if os.path.exists(file_path):
            try:
                document = FSInputFile(path=file_path, filename="Форма_заявки.doc")
                await message.answer_document(document=document)
            except Exception as e:
                logger.error(f"[v2] Ошибка при отправке файла: {e}", exc_info=True)
                await message.answer("⚠️ Не удалось отправить форму. Попробуйте позже.")
        else:
            await message.answer(
                "⚠️ Форма для заполнения временно недоступна. Вы можете прикрепить свой документ."
            )

        instruction_message = (
            "📎 Прикрепите документ (фото/файл), если необходимо. "
            "Или нажмите Пропустить:"
        )
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="skip_document")]
        ])
        await message.answer(
            text=instruction_message,
            reply_markup=reply_markup
        )


# === Загрузка документа ===
@router.message(ClaimRenewalV2.document, F.document)
async def renewal_get_document(message: Message, state: FSMContext):
    logger.info(f"[v2] Загрузка документа | Состояние: {await state.get_state()}")

    # Проверяем, что прислан именно документ
    file_id = message.document.file_id
    file_name = message.document.file_name

    # Проверяем расширение файла
    if not file_name.lower().endswith(('.doc')):
        await message.answer("❌ Неверный формат файла. Пожалуйста, загрузите документ в формате .doc или .doc.")
        return

    data = await state.get_data()
    if data.get("editing_field") == "document":
        await state.update_data(document={"file_id": file_id, "file_name": file_name})
        await message.answer("✅ Документ успешно заменён.")
        await show_renewal_summary_v2(message, state)
        await state.update_data(editing_field=None)
    else:
        await state.update_data(document={"file_id": file_id, "file_name": file_name})
        await message.answer("✅ Документ загружен.")
        await show_renewal_summary_v2(message, state)


# === Пропуск документа ===
@router.callback_query(F.data == "skip_document", ClaimRenewalV2.document)
async def skip_document(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Пропуск документа | Callback: {callback.data} | Состояние: {await state.get_state()}")
    data = await state.get_data()
    if data.get("editing_field") == "document":
        await state.update_data(document=None)
        await callback.message.answer("✅ Документ удалён.")
    else:
        await state.update_data(document=None)
        await callback.message.answer("📎 Документ пропущен.")

    await show_renewal_summary_v2(callback.message, state)
    await callback.answer()


# === Создание заявки ===
@router.callback_query(F.data == "create_renewalV2_claim", ClaimRenewalV2.confirmation)
async def create_renewal_claim_v2(callback: CallbackQuery, state: FSMContext):
    logger.info(f"[v2] Создание заявки | Callback: {callback.data} | Состояние: {await state.get_state()}")

    try:
        data = await state.get_data()
        logger.debug("[v2] Полученные данные состояния: %s", data)

        with glpi_api.connect(config.GLPI_URL, config.GLPI_APP_TOKEN, config.GLPI_USER_TOKEN, False) as glpi:
            logger.debug("[v2] Подключение к GLPI установлено")

            content = (
                f"Заявка создана через Telegram\n#телеграм\n"
                f"ФИО исполнителя: {data['executor_name']}\n"
                f"Поезд: {data['train_number']}\n"
                f"Количество вагонов: {data['wagon_count']}\n"
                f"Место: {data['location']}\n"
                f"Дата и время: {data['datetime']}\n"
            )
            logger.debug("[v2] Содержимое заявки:\n%s", content)

            ticket_data = {
                "name": "API GLPI - Переоснащение v2",
                "content": content,
                "urgency": 4,
                "impact": 4,
                "priority": 4,
                "type": 1,
                "requesttypes_id": 1,
                "itilcategories_id": 39,
                "entities_id": 16,
                "_users_id_observer": [22],
            }
            logger.debug("[v2] Данные для создания заявки: %s", ticket_data)

            logger.debug("[v2] Отправка запроса на создание заявки")
            ticket_result = glpi.add("Ticket", ticket_data)
            logger.debug("[v2] Заявка создана: %s", ticket_result)

            ticket_id = ticket_result[0]["id"]
            claim_info = (
                "✅ Заявка успешно создана в системе GLPI!\n"
                f"🔢 Номер заявки: {ticket_id}\n"
                f"📍 Поезд: {data['train_number']},"
                f" Вагонов: {data['wagon_count']}"
            )

            if data.get("document"):
                doc = data["document"]
                file_path = await download_file(callback.bot, doc["file_id"])

                try:
                    upload_result = glpi.upload_document(doc["file_id"], file_path)
                    logger.debug(f"[v2] Файл загружен: {upload_result}")

                    document_id = upload_result['id']

                    glpi.add("Document_Item", {
                        "documents_id": document_id,
                        "items_id": ticket_id,
                        "itemtype": "Ticket"
                    })

                    logger.debug(f"[v2] Документ #{document_id} привязан к заявке #{ticket_id}")
                except Exception as e:
                    logger.error(f"[v2] Ошибка при загрузке или привязке файла: {e}", exc_info=True)
                finally:
                    os.remove(file_path)
            await callback.message.answer(claim_info, reply_markup=get_return_main_menu_kb())
            await state.clear()
            logger.info("[v2] Заявка #%d успешно обработана", ticket_id)

    except Exception as e:
        logger.error(f"[GLPI Error] {e}", exc_info=True)
        await callback.message.answer(
            "❌ Не удалось создать заявку в GLPI.\nПопробуйте позже.",
            reply_markup=get_return_main_menu_kb()
        )
        await state.clear()
