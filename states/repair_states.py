from aiogram.fsm.state import State, StatesGroup


class ClaimRepair(StatesGroup):
    train_number = State()
    wagon_number = State()
    wagon_sn = State()
    equipment_in = State()
    problem_types = State()  # Теперь список
    problem_other = State()  # Для ручного ввода
    location = State()
    date = State()
    time = State()
    datetime = State()
    executor_name = State()
    executor_position = State()