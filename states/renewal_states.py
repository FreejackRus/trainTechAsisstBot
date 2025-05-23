from aiogram.fsm.state import State, StatesGroup


class ClaimRenewal(StatesGroup):
    train_number = State()
    wagon_number = State()
    wagon_sn = State()
    equipment_in = State()
    work_types = State()  # Теперь список
    work_other = State()  # Для ручного ввода
    new_equipment = State()
    quantity = State()