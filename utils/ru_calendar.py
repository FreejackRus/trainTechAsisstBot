# utils/ru_calendar.py
from aiogram_calendar import SimpleCalendar


class RuSimpleCalendar(SimpleCalendar):
    __lang__ = 'ru'

    def __init__(self):
        super().__init__()
        self._labels.months = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ]
        self._labels.days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        self._labels.today_caption = "Сегодня"
        self._labels.cancel_caption = "Отмена"

    async def start_calendar(self, year: int = None, month: int = None):
        return await super().start_calendar(year, month)