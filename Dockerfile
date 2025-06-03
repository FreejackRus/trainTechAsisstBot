# Базовый образ
FROM python:3.12-slim

# Рабочая директория
WORKDIR /app

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все остальные файлы проекта
COPY . .

# Запуск бота
CMD ["python", "main.py"]