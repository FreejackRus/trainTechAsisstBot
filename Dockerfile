# Базовый образ
FROM python:3.12-slim

# Рабочая директория
WORKDIR /app



# Копируем все файлы проекта
COPY . .

# Запуск бота
CMD ["python", "main.py"]