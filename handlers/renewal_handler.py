import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from glpi_api import connect
from keyboards.inline_kb import get_checkbox_kb_with_other
from keyboards.reply_kb import get_cancel_kb, get_main_menu_kb
from states.renewal_states import ClaimRenewal

router = Router()

# === Типы работ для переоснащения ===
WORK_TYPES_RENEWAL = [
    "Выезд специалиста в депо",
    "Демонтаж",
    "Проверка кабельных трасс",
    "Монтаж",
    "Пуско-наладка системы ИРС",
    "Прочее"
]

# === Начало: Переоснащение ===
@router.message(F.text == "Переоснащение")
async def start_renewal(message: Message, state: FSMContext):
    await state.set_state(ClaimRenewal.train_number)
    await message.answer("Введите номер поезда:", reply_markup=get_cancel_kb())

# === Шаг 1: Номер поезда → Wagon number ===
@router.message(ClaimRenewal.train_number)
async def renewal_wagon_number(message: Message, state: FSMContext):
    if message.text.strip().isdigit():
        await state.update_data(train_number=message.text)
        await state.set_state(ClaimRenewal.wagon_number)
        await message.answer("Введите номер вагона:", reply_markup=get_cancel_kb())
    else:
        await message.answer("Введите корректный номер поезда (число):")

# === Шаг 2: Номер вагона → Wagon SN ===
@router.message(ClaimRenewal.wagon_number)
async def renewal_wagon_sn(message: Message, state: FSMContext):
    if message.text.strip().isdigit():
        await state.update_data(wagon_number=message.text)
        await state.set_state(ClaimRenewal.wagon_sn)
        await message.answer("Введите серийный номер вагона:", reply_markup=get_cancel_kb())
    else:
        await message.answer("Введите корректный номер вагона (число):")

# === Шаг 3: Серийный номер вагона → Equipment IN ===
@router.message(ClaimRenewal.wagon_sn)
async def renewal_equipment_in(message: Message, state: FSMContext):
    await state.update_data(wagon_sn=message.text)
    await state.set_state(ClaimRenewal.equipment_in)
    await message.answer("Введите инвентарный номер оборудования:", reply_markup=get_cancel_kb())

# === Шаг 4: Выбор типа работ ===
@router.message(ClaimRenewal.equipment_in)
async def renewal_work_type(message: Message, state: FSMContext):
    await state.update_data(equipment_in=message.text)
    await state.set_state(ClaimRenewal.work_types)
    await message.answer("Выберите типы работ:",
                         reply_markup=get_checkbox_kb_with_other(WORK_TYPES_RENEWAL, prefix="renewal"))

# === Обработка чекбоксов для работ ===
@router.callback_query(F.data.startswith("renewal_check_"))
async def handle_work_check(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split("_")[2])
    data = await state.get_data()
    selected = data.get("selected_works", [])

    if index in selected:
        selected.remove(index)
    else:
        selected.append(index)

    await state.update_data(selected_works=selected)
    await callback.message.edit_reply_markup(
        reply_markup=get_checkbox_kb_with_other(WORK_TYPES_RENEWAL, selected, prefix="renewal")
    )

# === Готово → сохраняем выбранные работы ===
@router.callback_query(F.data == "renewal_done")
async def finish_selecting_works(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_indices = data.get("selected_works", [])
    selected_texts = [WORK_TYPES_RENEWAL[i] for i in selected_indices]

    if not selected_texts and not data.get("manual_work"):
        await callback.answer("Выберите хотя бы один тип работ.")
        return

    if data.get("manual_work"):
        selected_texts.append(data["manual_work"])

    await state.update_data(work_types=selected_texts)
    await state.set_state(ClaimRenewal.new_equipment)
    await callback.message.edit_text("Вы выбрали следующие типы работ:\n" + "\n".join(f"• {w}" for w in selected_texts))
    await callback.message.answer("Наименование нового оборудования:", reply_markup=get_cancel_kb())

# === Прочее (вручную) для работ ===
@router.callback_query(F.data == "renewal_other_manual")
async def choose_other_work(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_indices = data.get("selected_works", [])
    selected_texts = [WORK_TYPES_RENEWAL[i] for i in selected_indices]
    await state.set_state(ClaimRenewal.work_other)
    await callback.message.edit_text("Опишите прочую работу:")

# === Ввод пользовательской работы ===
@router.message(ClaimRenewal.work_other)
async def handle_other_work(message: Message, state: FSMContext):
    user_input = message.text.strip()
    if not user_input:
        await message.answer("Пожалуйста, опишите прочую работу.")
        return

    data = await state.get_data()
    selected_indices = data.get("selected_works", [])
    selected_texts = [WORK_TYPES_RENEWAL[i] for i in selected_indices]
    final_works = selected_texts + [f"Прочее: {user_input}"]

    await state.update_data(work_types=final_works)
    await state.set_state(ClaimRenewal.new_equipment)
    await message.answer("Теперь укажите новое оборудование:", reply_markup=get_cancel_kb())

# === Шаг 5: Новое оборудование → Quantity ===
@router.message(ClaimRenewal.new_equipment)
async def renewal_quantity(message: Message, state: FSMContext):
    await state.update_data(new_equipment=message.text)
    await state.set_state(ClaimRenewal.quantity)
    await message.answer("Укажите количество:", reply_markup=get_cancel_kb())

# === Шаг 6: Количество и завершение ===
@router.message(ClaimRenewal.quantity)
async def finish_renewal(message: Message, state: FSMContext):
    quantity = message.text.strip()
    if not quantity.isdigit():
        await message.answer("❌ Введите корректное количество (число).")
        return

    data = await state.update_data(quantity=quantity)
    print("Сохранённые данные:", data)

    try:
        with connect(config.GLPI_URL, config.GLPI_APP_TOKEN, config.GLPI_USER_TOKEN) as glpi:
            content = (
                f"Заявка на переоснащение\n"
                f"Поезд: {data['train_number']}\n"
                f"Вагон: {data['wagon_number']}\n"
                f"Серийный номер вагона: {data['wagon_sn']}\n"
                f"Старое оборудование: {data['equipment_in']}\n"
                f"Новое оборудование: {data['new_equipment']}\n"
                f"Количество: {data['quantity']}\n"
                f"Тип работ: {', '.join(data['work_types'])}"
            )

            ticket_result = glpi.add("Ticket", {
                "name": "API GLPI - Переоснащение",
                "content": content,
                "urgency": 3,
                "impact": 3,
                "priority": 3,
                "type": 1,
                "requesttypes_id": 1,
                "itilcategories_id": 3,
                "entities_id": 0
            })

            ticket_id = ticket_result[0]["id"]

            claim_info = (
                "✅ Заявка успешно создана в системе GLPI!\n"
                f"🔢 Номер заявки: {ticket_id}\n"
                f"📝 Тема: {data['work_types'][0]}\n"
                f"📍 Поезд: {data['train_number']}, Вагон: {data['wagon_number']}"
            )
            await message.answer(claim_info, reply_markup=get_main_menu_kb())
            await message.answer("Вы снова в главном меню.")

            await state.clear()

    except Exception as e:
        await state.clear()
        await message.answer(
            "❌ Не удалось создать заявку в GLPI.\nПопробуйте позже.",
            reply_markup=get_main_menu_kb()
        )
        logging.error(f"[GLPI Error] {e}")