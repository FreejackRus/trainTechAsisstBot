import logging
import re
from datetime import datetime as dt_datetime
from typing import Union

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

import config
from glpi_api import connect
from keyboards.inline_kb import get_checkbox_kb_with_other, get_cancel_kb, get_return_main_menu_kb
from states.repair_states import ClaimRepair
from utils.helpers import load_train_list, is_wagon_sn_valid

router = Router()

# Инициализация логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# Константы
ITEMS_PER_PAGE = 5
PROBLEMS_REPAIR = [
    "Недоступен портал",
    "Недоступна wi-fi сеть «Таврия.Медиа»",
]
DEFAULT_TIMES = ["09:00", "10:00", "11:00", "12:00"]


async def show_repair_summary(message: Union[Message, CallbackQuery], state: FSMContext):
    """Показывает сводку заявки с кнопками подтверждения"""
    if isinstance(message, CallbackQuery):
        message = message.message

    data = await state.get_data()
    problem_types = data.get("problem_types", [])

    if not problem_types and "selected_problems" in data:
        problem_types = [PROBLEMS_REPAIR[i] for i in data["selected_problems"] if i < len(PROBLEMS_REPAIR)]

    if data.get("manual_problem"):
        problem_types.append(data["manual_problem"])

    summary = (
        "📄 *Итоговая информация о заявке*\n"
        f"Тип заявки: Восстановление работы\n"
        f"Ответственный сотрудник: {data.get('executor_name', '-')}\n"
        f"Поезд №: {data.get('train_number', '-')}\n"
        f"Номер вагона: {data.get('wagon_number', '-')}\n"
        f"Серийный номер вагона: {data.get('wagon_sn', '-')}\n"
        f"Проблемы: {', '.join(problem_types) if problem_types else '-'}\n"
    )

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать заявку", callback_data="create_repair_claim")],
        [InlineKeyboardButton(text="Редактировать", callback_data="edit_start")]
    ])

    await state.set_state(ClaimRepair.confirmation)
    await message.answer(summary, reply_markup=confirm_kb, parse_mode="Markdown")


async def show_train_page(callback: CallbackQuery, state: FSMContext, page: int):
    """Отображает страницу со списком поездов"""
    data = await state.get_data()
    trains = data.get("trains", [])
    start_index = page * ITEMS_PER_PAGE
    end_index = min(start_index + ITEMS_PER_PAGE, len(trains))
    current_page_trains = trains[start_index:end_index]

    # Создаем кнопки для поездов
    keyboard_buttons = [
        [InlineKeyboardButton(text=f"🚆 Поезд №{train}", callback_data=f"train_{train}")]
        for train in current_page_trains
    ]

    # Добавляем кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page_prev_{page - 1}"))
    if end_index < len(trains):
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"page_next_{page + 1}"))

    keyboard_buttons.append([InlineKeyboardButton(text="🔍 Поиск поезда", callback_data="search_train")])
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)

    # Отправляем новое сообщение вместо редактирования
    await callback.message.edit_reply_markup(
        "Выберите номер поезда:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )


async def process_common_field(message: Message, state: FSMContext,
                               field_name: str, next_state,
                               validation_func=None, error_msg=None):
    """Обрабатывает общие поля формы"""
    value = message.text.strip()

    if validation_func and not validation_func(value):
        await message.answer(error_msg)
        return False

    await state.update_data({field_name: value})
    logger.info(
        f"State data after update for {field_name}: {await state.get_data()}")  # Updated logging to get current data

    # Display the confirmation message for the current field

    if field_name == "wagon_number":
        await message.answer(f"✅ Номер вагона: {value}")
    elif field_name == "wagon_sn":
        await message.answer(f"✅ Серийный номер вагона: {value}")
    elif field_name == "selected_problems":
        await message.answer(f"✅ Выбранные проблемы: {value}")
    elif field_name == "manual_problem":
        await message.answer(f"✅ Проблема (вручную): {value}")


    data = await state.get_data()

    if data.get('editing'):
        await state.update_data(editing=False)
        await show_repair_summary(message, state)
    else:
        await state.set_state(next_state)
        return True

    return False


@router.callback_query(F.data == "claim_type_restoration")
async def handle_restoration(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа заявки 'Восстановление'"""
    # Отправляем сообщение о типе заявки
    await callback.message.answer("🔧 Вы выбрали: Восстановление работоспособности")

    trains = load_train_list()

    if not trains:
        await callback.message.answer("❌ Список поездов пуст или не найден.")
        return

    await state.update_data(trains=trains, page=0)
    # Теперь показываем страницу с поездами в новом сообщении
    await show_train_page(callback, state, 0)

    await callback.answer()


@router.callback_query(F.data.startswith("page_prev_") | F.data.startswith("page_next_"))
async def navigate_pages(callback: CallbackQuery, state: FSMContext):
    """Навигация по страницам списка поездов"""
    data = await state.get_data()
    page = int(callback.data.split("_")[-1])
    total_pages = (len(data.get("trains", [])) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    if 0 <= page < total_pages:
        await state.update_data(page=page)
        await show_train_page(callback, state, page)


@router.callback_query(F.data == "search_train")
async def open_search_train(callback: CallbackQuery, state: FSMContext):
    """Обработка поиска поезда"""
    await callback.message.answer("Введите часть номера поезда для поиска:")
    await state.set_state(ClaimRepair.train_number)
    await callback.answer()


@router.callback_query(F.data.startswith("train_"))
async def select_train(callback: CallbackQuery, state: FSMContext):
    """Выбор поезда из списка"""
    train_number = callback.data.split("_", 1)[1]
    await state.update_data(train_number=train_number)
    await callback.message.answer(f"✅ Номер поезда: {train_number}") # Added line
    data = await state.get_data()

    if data.get('editing'):
        await show_repair_summary(callback, state)
    else:

        await state.set_state(ClaimRepair.wagon_number)
        await callback.message.answer("Введите номер вагона:", reply_markup=get_cancel_kb())

    await callback.answer()


@router.message(ClaimRepair.train_number)
async def search_train(message: Message, state: FSMContext):
    """Поиск поезда по части номера"""
    query = message.text.strip().upper()
    trains = load_train_list()
    results = [t for t in trains if t.upper().startswith(query)]

    if not results:
        await message.answer("❌ По вашему запросу поездов не найдено.")
        return

    await message.answer(
        "Выберите поезд из результатов поиска:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=train, callback_data=f"train_{train}")]
            for train in results[:10]
        ])
    )


@router.message(ClaimRepair.wagon_number)
async def repair_wagon_sn(message: Message, state: FSMContext):
    """Обработка номера вагона"""
    if not await process_common_field(
            message, state,
            "wagon_number", ClaimRepair.wagon_sn,
            lambda x: x.isdigit(), "❌ Номер вагона должен быть числом."
    ):
        return

    await message.answer("Введите серийный номер вагона:", reply_markup=get_cancel_kb())


@router.message(ClaimRepair.wagon_sn)
async def repair_wagon_sn(message: Message, state: FSMContext):
    wagon_sn = message.text.strip()

    """Обработка серийного номера вагона"""
    if not await process_common_field(
            message, state,
            "wagon_sn", ClaimRepair.problem_types, # Изменено на ClaimRepair.problem_types
            lambda x: len(x) >= 6, "❌ Серийный номер должен содержать не менее 6 символов."
    ):
        return
    # Проверка наличия в базе (в файле)
    if not await is_wagon_sn_valid(wagon_sn):
        await message.answer("❌ Вагон с таким серийным номером не найден в базе.")
        return

    # Удален переход на ввод инвентарного номера оборудования
    data = await state.get_data()
    selected = data.get("selected_problems", [])

    await message.answer(
        "Выберите одну или несколько проблем:",
        reply_markup=get_checkbox_kb_with_other(PROBLEMS_REPAIR, selected, prefix="repair")
    )


# Удалена функция @router.message(ClaimRepair.equipment_in) async def repair_problem_type(...)


@router.callback_query(F.data == "repair_other_manual")
async def handle_repair_other_manual(callback: CallbackQuery, state: FSMContext):
    """Обработка ручного ввода проблемы"""
    await callback.message.answer("Введите описание проблемы вручную:")
    await state.set_state(ClaimRepair.problem_other)
    await callback.answer()


@router.message(ClaimRepair.problem_other)
async def repair_manual_problem(message: Message, state: FSMContext):
    """Обработка ручного описания проблемы"""
    if not await process_common_field(
            message, state,
            "manual_problem", None,
            None, None
    ):
        return

    data = await state.get_data()
    selected = data.get("selected_problems", [])
    if len(PROBLEMS_REPAIR) > 0:
        selected.append(len(PROBLEMS_REPAIR) - 1)

    await state.update_data(selected_problems=selected)
    await state.set_state(ClaimRepair.executor_name)


@router.callback_query(F.data.regexp(r"^repair_check_\d+$"))
async def handle_repair_check(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора проблем из списка"""
    index = int(callback.data.split("_")[2])
    data = await state.get_data()
    selected = data.get("selected_problems", [])

    if index in selected:
        selected.remove(index)
    else:
        selected.append(index)


    await state.update_data(selected_problems=selected)
    
    await callback.message.edit_reply_markup(
        reply_markup=get_checkbox_kb_with_other(PROBLEMS_REPAIR, selected, prefix="repair")
    )


@router.callback_query(F.data == "repair_done")
async def finish_repair_problems(callback: CallbackQuery, state: FSMContext):
    """Завершение выбора проблем"""
    data = await state.get_data()
    selected_indices = data.get("selected_problems", [])
    selected_texts = [PROBLEMS_REPAIR[i] for i in selected_indices if i < len(PROBLEMS_REPAIR)]

    if data.get("manual_problem"):
        selected_texts.append(data["manual_problem"])

    await state.update_data(problem_types=selected_texts)

    if data.get('editing'):
        await state.update_data(editing=False)
        await show_repair_summary(callback, state)
    else:
        await callback.message.answer(f"✅ Проблемы: {selected_texts}")
        await state.set_state(ClaimRepair.executor_name)
        await callback.message.answer("ФИО исполнителя:")

    await callback.answer()


@router.message(ClaimRepair.executor_name)
async def repair_executor_position(message: Message, state: FSMContext):
    """Обработка ФИО исполнителя"""
    await state.update_data(executor_name=message.text)
    await show_repair_summary(message, state)


@router.callback_query(F.data == "create_repair_claim", ClaimRepair.confirmation)
async def finish_repair(callback: CallbackQuery, state: FSMContext):
    """Создание заявки в GLPI"""
    data = await state.get_data()
    logger.info("Начинаем создание заявки в GLPI", extra={"data": data})

    try:
        with connect(config.GLPI_URL, config.GLPI_APP_TOKEN, config.GLPI_USER_TOKEN, False) as glpi:
            logger.debug("Успешно подключились к GLPI API")

            content = (
                f"Заявка создана через Telegram\n"
                "#телеграм\n"
                f"Поезд: {data['train_number']}\n"
                f"Вагон: {data['wagon_number']}\n"
                f"Серийный номер вагона: {data['wagon_sn']}\n"
                f"Проблемы: {', '.join(data['problem_types'])}\n"
                f"Ответственный сотрудник: {data['executor_name']}"
            )

            ticket_data = {
                "name": "API GLPI - Восстановление работы",
                "content": content,
                "urgency": 4,
                "impact": 4,
                "priority": 4,
                "type": 1,
                "requesttypes_id": 1,
                "itilcategories_id": 39,
                "entities_id": 16,
                "_users_id_observer": [22]
            }

            logger.debug("Отправляем данные в GLPI", extra={"ticket_data": ticket_data})
            ticket_result = glpi.add("Ticket", ticket_data)

            ticket_id = ticket_result[0]['id']
            logger.info(f"Заявка успешно создана в GLPI", extra={"ticket_id": ticket_id})

            await callback.message.answer(
                f"✅ Заявка №{ticket_id} успешно создана в GLPI!\n\n"
                f"Поезд: {data['train_number']}\n"
                f"Вагон: {data['wagon_number']}\n"
                f"Серийный номер вагона: {data['wagon_sn']}",
                reply_markup=get_return_main_menu_kb()
            )
            await state.clear()

    except Exception as e:
        logger.error("Ошибка при создании заявки в GLPI", exc_info=True)
        await callback.message.answer(f"❌ Произошла ошибка при создании заявки: {e}")
        await state.clear()

    await callback.answer()
