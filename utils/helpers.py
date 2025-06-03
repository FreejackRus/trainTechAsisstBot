import os
from bs4 import BeautifulSoup
import pandas as pd

def load_train_list():
    train_list_path = os.path.join(os.path.dirname(__file__), '../files', 'Test-tavria-poezda (1).txt')
    trains = []
    try:
        with open(train_list_path, 'r', encoding='utf-8-sig') as f:  # <-- здесь изменение
            for line in f:
                trains.append(line.strip())
    except FileNotFoundError:
        print(f"Error: Train list file not found at {train_list_path}")
    return trains


def clean_html(text):
    if not isinstance(text, str):
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator="\n").strip()



import logging
import pandas as pd

# Настройка логирования
logging.basicConfig(
    filename="wagon_checks.log",  # Файл, куда будут писаться логи
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

async def is_wagon_sn_valid(wagon_sn: str) -> bool:
    """
    Проверяет, существует ли указанный серийный номер вагона в файле wagons.xlsx.
    Использует правильный относительно текущего файла путь к Excel-файлу.
    """
    try:
        # Получаем абсолютный путь к текущему файлу helpers.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Строим путь к файлу wagons.xlsx
        file_path = os.path.join(current_dir, "..", "files", "wagons.xlsx")

        # Проверяем существование файла
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл {file_path} не найден.")

        # Загружаем данные
        df = pd.read_excel(file_path)

        # Проверяем наличие нужной колонки
        if "Номер вагона" in df.columns:
            wagon_numbers = df["Номер вагона"].astype(str).str.strip().unique()
            exists = wagon_sn.strip() in wagon_numbers

            # Логируем результат
            if exists:
                logging.info(f"Номер вагона {wagon_sn} найден в базе.")
            else:
                logging.warning(f"Номер вагона {wagon_sn} НЕ НАЙДЕН в базе.")

            return exists
        else:
            error_msg = "В файле отсутствует колонка 'Номер вагона'"
            logging.error(error_msg)
            raise ValueError(error_msg)

    except Exception as e:
        logging.error(f"Ошибка при проверке серийного номера вагона {wagon_sn}: {e}")
        return False