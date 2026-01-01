FROM python:3.11-slim

WORKDIR /app

# Спочатку залежності (для кешу)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Потім код
COPY . .

CMD ["python", "bot.py"]
