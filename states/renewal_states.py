from aiogram.fsm.state import State, StatesGroup


class ClaimRenewal(StatesGroup):
    train_number = State()
    editing = State()
    none = State()
    executor_name = State()       # ФИО ответственного
    renewal_train_number = State()
    train_search = State()
    wagon_count = State()         # Количество вагонов
    wagon_number = State()
    wagon_sn = State()
    equipment_in = State()
    work_types = State()
    work_other = State()
    new_equipment = State()
    quantity = State()
    location = State()            # Место проведения работ
    date = State()                # Дата
    time = State()                # Время
    comment = State()             # Дополнительная информация
    confirmation = State()        # Подтверждение

class ClaimRenewalV2(StatesGroup):
    document = State()
    custom_time = State()
    train_number = State()

    editing = State()
    none = State()
    executor_name = State()       # ФИО ответственного
    renewal_train_number = State()
    train_search = State()
    wagon_count = State()         # Количество вагонов
    wagon_number = State()
    wagon_sn = State()
    equipment_in = State()
    work_types = State()
    work_other = State()
    new_equipment = State()
    quantity = State()
    location = State()            # Место проведения работ
    date = State()                # Дата
    time = State()                # Время
    comment = State()             # Дополнительная информация
    confirmation = State()        # Подтверждение