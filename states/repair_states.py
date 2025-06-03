from aiogram.fsm.state import State, StatesGroup


class ClaimRepair(StatesGroup):
    train_number = State()
    wagon_number = State()
    wagon_sn = State()
    problem_types = State()  # Теперь список
    problem_other = State()  # Для ручного ввода
    executor_name = State()
    executor_position = State()
    confirmation = State()

