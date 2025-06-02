from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import config
from glpi_api import connect
from keyboards.inline_kb import get_main_menu_kb, get_retry_or_main_menu_kb

router = Router()


# === FSM для проверки статуса заявки ===
class StatusCheck(StatesGroup):
    ticket_id = State()  # Состояние — ожидаем ID заявки


@router.message(F.text == "Проверить статус заявки")
async def request_ticket_id(message: Message, state: FSMContext):
    await state.set_state(StatusCheck.ticket_id)
    await message.answer("Введите номер заявки для проверки:")


# === Получение ID и запрос в GLPI ===
@router.message(StatusCheck.ticket_id)
async def get_ticket_status(message: Message, state: FSMContext):
    ticket_id = message.text.strip()

    if not ticket_id.isdigit():
        await message.answer("❌ Неверный формат. Введите число — номер заявки.")
        return

    try:
        with connect(config.GLPI_URL, config.GLPI_APP_TOKEN, config.GLPI_USER_TOKEN) as glpi:
            ticket = glpi.get_item("Ticket", int(ticket_id))

            if ticket is None:
                await message.answer(
                    f"❌ Заявка с номером {ticket_id} не найдена.",
                    reply_markup=get_retry_or_main_menu_kb()
                )
                return

            # Получаем основные поля заявки
            status_id = ticket.get('status', '')
            status_map = {
                '1': 'Новая',
                '2': 'В обработке (назначено)',
                '3': 'В обработке (планируется)',
                '4': 'Ожидание',
                '5': 'Закрыто',
                '6': 'Отменено',
                '7': 'Прочее'
            }
            status_name = status_map.get(str(status_id), 'Неизвестно')

            content = ticket.get('content', 'Нет описания')
            name = ticket.get('name', 'Без названия')
            date_creation = ticket.get('date', 'Не указана')

            # Отправляем информацию пользователю
            response = (
                f"📄 <b>Информация по заявке #{ticket_id}</b>\n\n"
                f"📌 Тема: {name}\n"
                f"📅 Создано: {date_creation}\n"
                f"✅ Статус: {status_name}\n"
                f"📝 Описание: {content}..."
            )
            await message.answer(response, parse_mode="HTML", reply_markup=get_retry_or_main_menu_kb())

    except Exception as e:
        await message.answer(
            "❌ Не удалось получить данные из GLPI.",
            reply_markup=get_retry_or_main_menu_kb()
        )
        print("Ошибка при получении заявки:", e)
        return

    finally:
        await state.clear()


# === Обработка выбора пользователя после ошибки ===
@router.callback_query(F.data == "retry_ticket_id")
async def retry_ticket_input(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(StatusCheck.ticket_id)
    await callback_query.message.edit_text("Введите номер заявки для проверки:")
    await callback_query.answer()

