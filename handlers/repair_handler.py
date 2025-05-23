import logging
from datetime import date as dt_date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.types import Message, CallbackQuery
from aiogram_calendar import SimpleCalendarCallback

import config
from glpi_api import connect
from keyboards.inline_kb import get_checkbox_kb_with_other
from keyboards.reply_kb import get_cancel_kb, get_main_menu_kb
from states.repair_states import ClaimRepair
from utils.ru_calendar import RuSimpleCalendar

router = Router()

# === Проблемы для восстановления ===
PROBLEMS_REPAIR = [
    "Не работает Медиасервер",
    "Не работает Wi-Fi",
    "Не работает Интернет",
    "Нет индикации на точке доступа",
    "Нет индикации коммутатора"
]

# === Восстановление работоспособности ===
@router.message(F.text == "Восстановление работоспособности")
async def start_repair(message: Message, state: FSMContext):
    await state.set_state(ClaimRepair.train_number)
    await message.answer("Введите номер поезда:", reply_markup=get_cancel_kb())

# === Шаг 1: Номер поезда → Wagon number ===
@router.message(ClaimRepair.train_number)
async def repair_wagon_number(message: Message, state: FSMContext):
    if message.text.strip().isdigit():
        await state.update_data(train_number=message.text)
        await state.set_state(ClaimRepair.wagon_number)
        await message.answer("Введите номер вагона:", reply_markup=get_cancel_kb())
    else:
        await message.answer("Введите корректный номер поезда (число):")

# === Шаг 2: Номер вагона → Wagon SN ===
@router.message(ClaimRepair.wagon_number)
async def repair_wagon_sn(message: Message, state: FSMContext):
    if message.text.strip().isdigit():
        await state.update_data(wagon_number=message.text)
        await state.set_state(ClaimRepair.wagon_sn)
        await message.answer("Введите серийный номер вагона:", reply_markup=get_cancel_kb())
    else:
        await message.answer("Введите корректный номер вагона (число):")

# === Шаг 3: Серийный номер вагона → Equipment IN ===
@router.message(ClaimRepair.wagon_sn)
async def repair_equipment_in(message: Message, state: FSMContext):
    await state.update_data(wagon_sn=message.text)
    await state.set_state(ClaimRepair.equipment_in)
    await message.answer("Введите инвентарный номер оборудования:", reply_markup=get_cancel_kb())

# === Шаг 4: Выбор проблемы ===
# === Выбор проблемы ===
@router.message(ClaimRepair.equipment_in)
async def repair_problem_type(message: Message, state: FSMContext):
    await state.update_data(equipment_in=message.text)
    await state.set_state(ClaimRepair.problem_types)
    data = await state.get_data()
    selected = data.get("selected_problems", [])
    await message.answer("Выберите одну или несколько проблем:",
                         reply_markup=get_checkbox_kb_with_other(PROBLEMS_REPAIR, selected, prefix="repair"))

# === Обработка чекбоксов ===
import re
@router.callback_query(F.data.regexp(r"^repair_check_\d+$"))
async def handle_repair_check(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split("_")[2])  # Теперь безопасно
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

# === Готово → сохраняем выбранные пункты ===
@router.callback_query(F.data == "repair_done")
async def finish_repair_problems(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_indices = data.get("selected_problems", [])
    selected_texts = [PROBLEMS_REPAIR[i] for i in selected_indices]
    if not selected_texts and not data.get("manual_problem"):
        await callback.answer("Выберите хотя бы одну проблему.")
        return
    if data.get("manual_problem"):
        selected_texts.append(data["manual_problem"])
    await state.update_data(problem_types=selected_texts)
    await state.set_state(ClaimRepair.location)
    await callback.message.edit_text("Вы выбрали следующие проблемы:\n" + "\n".join(f"• {p}" for p in selected_texts))
    await callback.message.answer("Укажите место проведения работ:", reply_markup=get_cancel_kb())

# === Прочее (вручную) ===
@router.callback_query(F.data == "repair_other_manual")
async def repair_other_problem(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_indices = data.get("selected_problems", [])
    selected_texts = [PROBLEMS_REPAIR[i] for i in selected_indices]
    await state.set_state(ClaimRepair.problem_other)
    await callback.message.edit_text("Опишите свою проблему:")

# === Ввод пользовательского описания ===
@router.message(ClaimRepair.problem_other)
async def handle_other_problem(message: Message, state: FSMContext):
    user_input = message.text.strip()
    if not user_input:
        await message.answer("Пожалуйста, опишите вашу проблему.")
        return
    data = await state.get_data()
    selected_indices = data.get("selected_problems", [])
    selected_texts = [PROBLEMS_REPAIR[i] for i in selected_indices]
    final_problems = selected_texts + [f"Прочее: {user_input}"]
    await state.update_data(problem_types=final_problems)
    await state.set_state(ClaimRepair.location)
    await message.answer(
        "Вы выбрали следующие проблемы:\n" + "\n".join(f"• {p}" for p in final_problems)
    )
    await message.answer("Теперь укажите место проведения работ:", reply_markup=get_cancel_kb())

# === Шаг 5: Место проведения работ → Date ===
@router.message(ClaimRepair.location)
async def repair_choose_date(message: Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.set_state(ClaimRepair.date)

    today = dt_date.today()
    calendar = RuSimpleCalendar()
    markup = await calendar.start_calendar(today.year, today.month)
    await message.answer("Выберите дату:", reply_markup=markup)


# === Шаг 6: Выбор даты через календарь ===
@router.callback_query(SimpleCalendarCallback.filter(), ClaimRepair.date)
async def process_ru_calendar(
    callback: CallbackQuery,
    callback_data: dict,
    state: FSMContext
):
    calendar = RuSimpleCalendar()
    selected, date = await calendar.process_selection(callback, callback_data)

    if selected:
        # Дата выбрана
        formatted_date = date.strftime("%d.%m.%Y")
        await state.update_data(date=formatted_date)
        await state.set_state(ClaimRepair.time)

        time_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="09:00", callback_data="time_09:00")],
            [InlineKeyboardButton(text="10:00", callback_data="time_10:00")],
            [InlineKeyboardButton(text="11:00", callback_data="time_11:00")],
            [InlineKeyboardButton(text="12:00", callback_data="time_12:00")],
            [InlineKeyboardButton(text="Другое время", callback_data="time_custom")]
        ])

        await callback.message.edit_text(
            f"📅 Дата выбрана: {formatted_date}\n"
            "⏰ Теперь выберите время:"
        )
        await callback.message.edit_reply_markup(reply_markup=time_kb)
    else:
        # Календарь был обновлён (месяц/год), но дата не выбрана
        pass
# === Шаг 7: Выбор времени ===
@router.callback_query(F.data.startswith("time_"), ClaimRepair.time)
async def select_time(callback: CallbackQuery, state: FSMContext):
    time = callback.data.split("_")[1]
    if time == "custom":
        await callback.message.edit_text("⏰ Введите время вручную (например, 10:30):")
    else:
        data = await state.get_data()
        full_datetime = f"{data['date']} {time}"
        await state.update_data(datetime=full_datetime)
        await state.set_state(ClaimRepair.executor_name)
        await callback.message.edit_text(f"📅 Итоговая дата и время: {full_datetime}")
        await callback.message.answer("ФИО исполнителя:")

# === Время вручную ===
@router.message(ClaimRepair.time)
async def enter_custom_time(message: Message, state: FSMContext):
    time = message.text.strip()
    if re.match(r"^([01]\d|2[0-3]):[0-5]\d$", time):
        data = await state.get_data()
        full_datetime = f"{data['date']} {time}"
        await state.update_data(datetime=full_datetime)
        await state.set_state(ClaimRepair.executor_name)
        await message.answer("ФИО исполнителя:")
    else:
        await message.answer("❌ Неверный формат времени. Введите как 10:30")

# === ФИО исполнителя ===
@router.message(ClaimRepair.executor_name)
async def repair_executor_position(message: Message, state: FSMContext):
    await state.update_data(executor_name=message.text)
    await state.set_state(ClaimRepair.executor_position)
    await message.answer("Должность исполнителя:", reply_markup=get_cancel_kb())

# === Должность исполнителя и завершение ===
@router.message(ClaimRepair.executor_position)
async def finish_repair(message: Message, state: FSMContext):
    data = await state.update_data(executor_position=message.text)
    print(data)

    # === Отправляем заявку в GLPI ===
    try:
        with connect(config.GLPI_URL, config.GLPI_APP_TOKEN, config.GLPI_USER_TOKEN) as glpi:
            # Пример формирования содержимого заявки
            content = (
                f"Заявка создана через Telegram\n"
                f"Поезд: {data['train_number']}\n"
                f"Вагон: {data['wagon_number']}\n"
                f"Серийный номер вагона: {data['wagon_sn']}\n"
                f"Инвентарный номер оборудования: {data['equipment_in']}\n"
                f"Проблемы: {', '.join(data['problem_types'])}\n"
                f"Место: {data['location']}\n"
                f"Дата и время: {data['datetime']}\n"
                f"Исполнитель: {data['executor_name']} ({data['executor_position']})"
            )

            # Создаем заявку в GLPI
            ticket_result = glpi.add("Ticket", {
                "name": "API GLPI",
                "content": content,
                "urgency": 3,
                "impact": 3,
                "priority": 3,
                "type": 1,  # Инцидент
                "requesttypes_id": 1,  # Телефон / Telegram
                "itilcategories_id": 1,  # Категория (например, "Техническая проблема")
                "entities_id": 0,  # Организация
            })

            # Получаем ID заявки
            ticket_id = ticket_result[0]['id']

            # Отправляем пользователю информацию о созданной заявке
            claim_info = (
                "✅ Заявка успешно создана в системе GLPI!\n"
                f"🔢 Номер заявки: {ticket_id}\n"
                f"📝 Тема: {data['problem_types'][0]}\n"
                f"📍 Поезд: {data['train_number']}, Вагон: {data['wagon_number']}"
            )
            await message.answer(claim_info, reply_markup=get_main_menu_kb())
            await message.answer("Вы снова в главном меню.")

            # Очищаем состояние
            await state.clear()

    except Exception as e:
        await message.answer("❌ Не удалось создать заявку в GLPI.\nПопробуйте позже.")
        logging.error(f"Ошибка при создании заявки в GLPI: {e}")