FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir aiogram flask

CMD ["python", "bot.py"]