import asyncio
import re
from datetime import datetime
import pytz
KYIV_TZ = pytz.timezone("Europe/Kiev")
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties

TOKEN = "8055579353:AAGA-QOKtGmCk8wEDMJ4UGw1yd6K_b9PIdc"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

tasks = {}  # message_id -> task data

TRIGGERS = [
    "Задача:", "Задача", "задача:", "задача", ":"
]

# ======== ФУНКЦІЇ ========

def parse_task(text: str):
    text = text.strip()
    for t in TRIGGERS:
        if text.startswith(t):
            after_trigger = text[len(t):].strip()
            return after_trigger
    return None

def extract_deadline(task_text: str):
    deadline = None
    display_time = ""
    pattern = re.search(r"(Час:|час:)\s*(\d{1,2}:\d{2})", task_text)
    text_only = task_text
    if pattern:
        time_str = pattern.group(2).strip()
        try:
            h, m = map(int, time_str.split(":"))
            deadline = datetime.now(KYIV_TZ).replace(hour=h, minute=m, second=0, microsecond=0)
            display_time = f"⏰ До {time_str}"
            text_only = task_text[:pattern.start()].strip()
        except:
            text_only = task_text[:pattern.start()].strip()
    else:
        pattern_fail = re.search(r"(Час:|час:).*", task_text)
        if pattern_fail:
            text_only = task_text[:pattern_fail.start()].strip()
    return text_only, deadline, display_time

def build_keyboard(done=False, overdue=False, user=None, executed_date=None):
    if done:
        text = f"✅ {user} {datetime.now(KYIV_TZ).strftime('%H:%M')}"
        if executed_date:
            text += f" ({executed_date})"
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=text, callback_data="done")]]
        )
    if overdue:
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🟥 Виконано", callback_data="done")]]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬜️ Виконано", callback_data="done")]]
    )

# ======== СТВОРЕННЯ ТАСКУ ========

from aiogram.filters import Command

@dp.message(Command(commands=["start"]))
async def ping(message: Message):
    await message.answer("🟢 Бот живий\nНапиши /menu для інструкції")

@dp.message(Command(commands=["menu"]))
async def ping(message: Message):
    await message.answer("<b>1️⃣ Напиши в чат будь-яке із слів-тригерів:</b>\n"
    "Задача:\n"
    "Задача\n"
    "задача:\n"
    "задача\n"
    ":\n"
    "<b>і напиши що потрібно зробити, наприклад:</b>\n"
    "Задача: завезти тару\n"
    "задача завезти тару\n"
    "<b>або просто</b>\n"
    ": завезти тару\n\n"
    "<b>👌 Бот сформує задачу із твого повідомлення ✅</b>\n\n"
    "<b>2️⃣ Якщо напишеш тригер часу:</b>\n"
    "Задача: тара\n"
    "Час: 17:30\n"
    "<b>або просто</b>\n"
    ": тара час: 17:30\n\n"
    "<b>⏰ Бот сформує задачу з таймером (дедлайном), до якого часу її потрібно виконати.</b>\n\n"
    "<b>🟥 Після закінчення вказаного часу, завдання перетвориться на прострочене.</b>\n\n"
    "<b>✅ Виконати прострочене завдання можна. 👍</b>\n\n"
    "<b>🟥 Прострочене завдання перейде до низу чату як термінове до виконання.</b>\n\n"
    "<b>⏰ Всі невиконані завдання за день перемістяться в низ чату після 20:00.</b>")

@dp.message(F.text)
async def create_task(msg: Message):
    after_trigger = parse_task(msg.text)
    if not after_trigger:
        return

    task_text, deadline, display_time = extract_deadline(after_trigger)
    full_text = f"<b>{task_text}</b>"
    if display_time:
        full_text += f"\n{display_time}"

    sent = await msg.answer(full_text, reply_markup=build_keyboard())
    await msg.delete()

    tasks[sent.message_id] = {
        "chat_id": sent.chat.id,
        "text": task_text,
        "deadline": deadline,
        "display_time": display_time,
        "done": False,
        "overdue": False,
        "last_day": None   # ← КРИТИЧНО
    }

# ======== НАТИСКАННЯ КНОПКИ ========

@dp.callback_query(F.data == "done")
async def done_task(call):
    msg = call.message
    task = tasks.get(msg.message_id)
    if not task or task["done"]:
        return

    task["done"] = True
    executed_date = None

    # Перша строка жирна
    first_line = f"<b>{task['text']}</b>"
    second_line = ""
    if task["display_time"]:
        second_line = task["display_time"]
        if task["overdue"]:
            executed_date = datetime.now(KYIV_TZ).strftime("%d.%m")
            second_line = second_line.replace("⏰", "🟥")
            if f"({executed_date})" not in second_line:
                second_line += f" ({executed_date})"

    full_text = first_line
    if second_line:
        full_text += f"\n{second_line}"

    await msg.edit_text(full_text, reply_markup=build_keyboard(
        done=True,
	overdue=task.get("overdue", False),
        user=call.from_user.first_name,
        executed_date=datetime.now(KYIV_TZ).strftime("%d.%m") if task.get("overdue") else None
    ))

    await call.answer("Готово")

# ======== SCHEDULER ========
DAILY_HOUR = 20
DAILY_MINUTE = 5

async def scheduler():
    while True:
        now = datetime.now(KYIV_TZ)

        for mid, task in list(tasks.items()):
            if task["done"]:
                continue

            chat_id = task["chat_id"]

            # 1) Прострочене вперше
            if task["deadline"] and not task["overdue"] and now >= task["deadline"]:
                text = f"<b>{task['text']}</b>\n{task['display_time']}"  # без дати
                sent = await bot.send_message(chat_id, text, reply_markup=build_keyboard(overdue=True))
                await bot.delete_message(chat_id, mid)

                task_copy = task.copy()
                task_copy["overdue"] = True
                task_copy["last_day"] = None  # ← щоб сьогодні ввечері ще раз продублювався
                tasks[sent.message_id] = task_copy
                del tasks[mid]
                continue

            # 2) Щоденне дублювання (для всіх невиконаних)
            # Перевірка: ще не дубльовано сьогодні і настав час
            daily_due = (task["last_day"] is None or task["last_day"] < now.date())
            after_daily_time = now.hour > DAILY_HOUR or (now.hour == DAILY_HOUR and now.minute >= DAILY_MINUTE)

            if daily_due and after_daily_time:
                # Видаляємо старе повідомлення
                await bot.delete_message(chat_id, mid)

                # Формуємо текст
                if task["deadline"] and task["overdue"]:
                    text = f"<b>{task['text']}</b>\n{task['display_time']} ({task['deadline'].strftime('%d.%m')})"
                    keyboard = build_keyboard(overdue=True)
                elif task["deadline"]:
                    text = f"<b>{task['text']}</b>\n{task['display_time']}"
                    keyboard = build_keyboard()
                else:
                    text = f"<b>{task['text']}</b>"
                    keyboard = build_keyboard()

                # Відправляємо дубльоване повідомлення
                sent = await bot.send_message(chat_id, text, reply_markup=keyboard)

                # Оновлюємо last_day, щоб дублювання було лише один раз
                task_copy = task.copy()
                task_copy["last_day"] = now.date()
                tasks[sent.message_id] = task_copy
                del tasks[mid]

        await asyncio.sleep(30)

# ======== ГОЛОВНА ПРОГРАМА ========

async def main():
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
