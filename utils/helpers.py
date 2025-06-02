import os
from bs4 import BeautifulSoup


def load_train_list():
    train_list_path = os.path.join(os.path.dirname(__file__), '..', 'Test-tavria-poezda (1).txt')
    trains = []
    try:
        with open(train_list_path, 'r', encoding='utf-8') as f:
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