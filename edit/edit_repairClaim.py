import re
from datetime import datetime as dt_datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from handlers.repair_handler import show_repair_summary, PROBLEMS_REPAIR
from keyboards.inline_kb import get_checkbox_kb_with_other, get_cancel_kb
from states.repair_states import ClaimRepair

router = Router()

# Индекс пункта "Другое" в списке PROBLEMS_REPAIR
OTHER_OPTION_INDEX = len(PROBLEMS_REPAIR) - 1 if PROBLEMS_REPAIR else -1


@router.callback_query(F.data == "edit_start")
async def edit_choice_menu(callback: CallbackQuery, state: FSMContext):
    edit_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Номер поезда", callback_data="edit_train_number")],
        [InlineKeyboardButton(text="Номер вагона", callback_data="edit_wagon_number")],
        [InlineKeyboardButton(text="Серийный номер вагона", callback_data="edit_wagon_sn")],
        [InlineKeyboardButton(text="Проблемы", callback_data="edit_problem")],
        [InlineKeyboardButton(text="ФИО заявителья", callback_data="edit_executor")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_summary")]
    ])
    await callback.message.edit_text("🔧 Выберите поле для редактирования:", reply_markup=edit_kb)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_"))
async def start_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data
    await state.update_data(editing=True)

    if field == "edit_location":
        location_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Москва", callback_data="location_moscow")],
            [InlineKeyboardButton(text="Санкт-Петербург", callback_data="location_spb")],
            [InlineKeyboardButton(text="Симферополь", callback_data="location_simferopol")]
        ])
        await callback.message.edit_text("Выберите новое место проведения работ:")
        await callback.message.edit_reply_markup(reply_markup=location_kb)
        return

    if field == "edit_problem":
        data = await state.get_data()
        selected = data.get("selected_problems", [])
        await callback.message.edit_text("Выберите новые проблемы:")
        await callback.message.edit_reply_markup(
            reply_markup=get_checkbox_kb_with_other(PROBLEMS_REPAIR, selected, prefix="repair")
        )
        return

    if field == "edit_date":
        await state.set_state(ClaimRepair.date)
        await callback.message.edit_text("📅 Введите новую дату в формате дд.мм.гггг:")
        await callback.answer()
        return

    state_mapping = {
        "edit_train_number": ClaimRepair.train_number,
        "edit_wagon_number": ClaimRepair.wagon_number,
        "edit_wagon_sn": ClaimRepair.wagon_sn,
        "edit_executor": ClaimRepair.executor_name
    }

    prompts = {
        "edit_train_number": "Введите новый номер поезда:",
        "edit_wagon_number": "Введите новый номер вагона:",
        "edit_wagon_sn": "Введите новый серийный номер вагона:",
        "edit_executor": "Введите новое ФИО заявителя:"
    }

    if field in state_mapping:
        await state.set_state(state_mapping[field])
        prompt = prompts.get(field, "Введите новое значение:")
        await callback.message.answer(prompt, reply_markup=get_cancel_kb())

    await callback.answer()


@router.callback_query(F.data == "back_to_summary")
async def back_to_summary(callback: CallbackQuery, state: FSMContext):
    await show_repair_summary(callback.message, state)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^repair_check_\d+$"))
async def handle_edit_repair_check(callback: CallbackQuery, state: FSMContext):
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
async def finish_edit_problems(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    manual_problem = data.get("manual_problem")

    if manual_problem:
        # Если есть ручной ввод — сохраняем только его
        await state.update_data(selected_problems=[manual_problem])
    else:
        selected_indices = data.get("selected_problems", [])
        problem_texts = [PROBLEMS_REPAIR[i] for i in selected_indices if i < len(PROBLEMS_REPAIR)]
        await state.update_data(selected_problems=problem_texts)

    await show_repair_summary(callback.message, state)


@router.callback_query(F.data == "repair_other_manual")
async def handle_edit_repair_other_manual(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите описание проблемы вручную:")
    await state.set_state(ClaimRepair.problem_other)
    await callback.answer()


@router.message(ClaimRepair.problem_other)
async def repair_edit_manual_problem(message: Message, state: FSMContext):
    manual_problem = message.text.strip()

    # Сохраняем как отдельное поле
    await state.update_data(manual_problem=manual_problem)

    # Получаем текущие выбранные индексы проблем
    data = await state.get_data()
    selected = data.get("selected_problems", [])

    # Добавляем индекс "Другое", если его нет
    if OTHER_OPTION_INDEX not in selected and OTHER_OPTION_INDEX != -1:
        selected.append(OTHER_OPTION_INDEX)

    # Обновляем список индексов (не саму строку!)
    await state.update_data(selected_problems=selected)

    await show_repair_summary(message, state)


@router.callback_query(F.data.startswith("train_"))
async def select_train_for_edit(callback: CallbackQuery, state: FSMContext):
    train_number = callback.data.split("_", 1)[1]
    await state.update_data(train_number=train_number)
    await show_repair_summary(callback.message, state)
    await callback.answer()


@router.message(
    F.text,
    lambda m, s: s.get_state() in [
        ClaimRepair.train_number.state,
        ClaimRepair.wagon_number.state,
        ClaimRepair.wagon_sn.state,
        ClaimRepair.executor_name.state,
    ]
)
async def save_edited_text_field(message: Message, state: FSMContext):
    current_state = await state.get_state()

    field_map = {
        ClaimRepair.train_number.state: "train_number",
        ClaimRepair.wagon_number.state: "wagon_number",
        ClaimRepair.wagon_sn.state: "wagon_sn",
        ClaimRepair.executor_name.state: "executor_name",
    }

    field_key = field_map.get(current_state)
    if field_key:
        await state.update_data(**{field_key: message.text.strip()})
    await state.set_state(ClaimRepair.confirmation)
    await show_repair_summary(message, state)