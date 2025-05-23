from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

import config
from glpi_api import connect

router = Router()


# === FSM для проверки статуса заявки ===
class StatusCheck(StatesGroup):
    ticket_id = State()  # Состояние — ожидаем ID заявки


# === Обработчик команды "Проверить статус заявок" ===
@router.message(F.text == "Проверить статус заявок")
async def request_ticket_id(message: Message, state: FSMContext):
    await state.set_state(StatusCheck.ticket_id)
    await message.answer("Введите ID заявки для проверки:")


# === Получение ID и запрос в GLPI ===
@router.message(StatusCheck.ticket_id)
async def get_ticket_status(message: Message, state: FSMContext):
    ticket_id = message.text.strip()

    if not ticket_id.isdigit():
        await message.answer("❌ Неверный формат. Введите число — ID заявки.")
        return

    try:
        with connect(config.GLPI_URL, config.GLPI_APP_TOKEN, config.GLPI_USER_TOKEN) as glpi:
            ticket = glpi.get_item("Ticket", int(ticket_id))

            if ticket is None:
                await message.answer(f"❌ Заявка с ID {ticket_id} не найдена.")
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
                f"📝 Описание: {content[:5000]}..."
            )
            await message.answer(response, parse_mode="HTML")

    except Exception as e:
        await message.answer("❌ Не удалось получить данные из GLPI.")
        print("Ошибка при получении заявки:", e)

    finally:
        await state.clear()