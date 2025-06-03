# utils/renewal_utils.py
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton
import os
import tempfile
from aiogram import Bot


async def show_renewal_summary(message: CallbackQuery | Message, state: FSMContext):
    if isinstance(message, CallbackQuery):
        message = message.message

    data = await state.get_data()

    # Сбор данных
    executor_name = data.get("executor_name", "-")
    train_number = data.get("train_number", "-")
    wagon_count = data.get("wagon_count", "-")
    wagon_sn = data.get("wagon_sn", "-")
    location = data.get("location", "-")
    datetime = data.get("datetime", "-")
    comment = data.get("comment", "-")

    # Формируем текст сводки
    summary = (
        "📄 *Итоговая информация о заявке*\n\n"
        f"🔹 Тип заявки: Переоснащение v1\n"
        f"👤 Ответственный сотрудник: {executor_name}\n"
        f"🚆 Поезд №: {train_number}\n"
        f"🔢 Количество вагонов: 1"
        f"🔢 Серийный номер вагона: {wagon_sn}\n"
        f"📍 Место проведения работ: {location}\n"
        f"📅 Дата и время нахождения состава в депо: {datetime}\n"
        f"📝 Дополнительная информация: {comment or 'отсутствует'}"
    )

    # Клавиатура подтверждения
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Создать заявку", callback_data="create_renewal_claim")],
        [InlineKeyboardButton(text="🛠 Редактировать", callback_data="renewalV1_edit_start")]
    ])

    current_state = await state.get_state()

    # Если мы были в режиме редактирования — остаёмся в этом состоянии
    if current_state == "ClaimRenewal:editing":
        # Не меняем состояние, просто обновляем сводку
        try:
            await message.edit_text(summary, reply_markup=confirm_kb, parse_mode="Markdown")
        except Exception:
            await message.answer(summary, reply_markup=confirm_kb, parse_mode="Markdown")
    else:
        # Иначе ставим confirmation — для завершения заявки
        from states.renewal_states import ClaimRenewal
        await state.set_state(ClaimRenewal.confirmation)
        await message.answer(summary, reply_markup=confirm_kb, parse_mode="Markdown")



async def download_file(bot: Bot, file_id: str) -> str:
        """
        Скачивает файл из Telegram и возвращает путь к нему.
        """
        try:
            file = await bot.get_file(file_id)
            file_path = os.path.join(tempfile.gettempdir(), file.file_path)

            # Создаём директорию, если её нет
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Скачиваем файл
            await bot.download_file(file.file_path, destination=file_path)
            return file_path
        except Exception as e:
            raise RuntimeError(f"Ошибка при загрузке файла: {e}")

async def show_renewal_summary_v2(message: Message, state: FSMContext):
        """
        Показывает сводку по заявке v2 с возможностью подтверждения или редактирования.
        """
        data = await state.get_data()

        document_info = "отсутствует"
        if data.get("document"):
            doc = data["document"]
            document_info = f"📎 {doc['file_name']} (ID: {doc['file_id']})"

        summary_text = (
            "📄 Подтвердите данные заявки:\n"
            f"👨‍🔧 Исполнитель: {data.get('executor_name', 'не указан')}\n"
            f"🚆 Поезд: {data.get('train_number', 'не указан')}\n"
            f"🔢 Вагонов: {data.get('wagon_count', 'не указано')}\n"
            f"🔢 Серийный номер: {data.get('wagon_sn', 'не указан')}\n"
            f"📍 Место: {data.get('location', 'не указано')}\n"
            f"📅 Дата/время: {data.get('datetime', 'не указано')}\n"
            f"📎 Документ: {document_info}\n\n"
            "Нажмите кнопку ниже для создания заявки:"
        )

        # Клавиатура подтверждения
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Создать заявку", callback_data="create_renewalV2_claim")],
            [InlineKeyboardButton(text="🛠 Редактировать", callback_data="renewalV2_edit_start")]
        ])

        # Устанавливаем состояние подтверждения
        from states.renewal_states import ClaimRenewalV2
        await state.set_state(ClaimRenewalV2.confirmation)

        # Отправляем сводку
        await message.answer(summary_text, reply_markup=confirm_kb, parse_mode="Markdown")