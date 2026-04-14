"""
Ежедневный бот списка дел для команды в Telegram.

НАСТРОЙКА:
1. Замени BOT_TOKEN на свой токен от @BotFather
2. Замени CHAT_ID на ID своего чата
3. Измени SEND_TIME — время отправки (по UTC, Amsterdam = UTC+2)
4. Отредактируй FIXED_TASKS — ежедневные задачи которые повторяются каждый день

УСТАНОВКА:
    pip install python-telegram-bot apscheduler

ЗАПУСК:
    python team_todo_bot.py
"""

import json
import logging
import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ─── НАСТРОЙКИ ───────────────────────────────────────────────────────────────

BOT_TOKEN = 8061440842:AAGZA0K3p9R3PZ_oYDm4zULFAyYyV8xwY-w   # ← токен от @BotFather
CHAT_ID   = 5123130188             # ← ID твоего чата

SEND_TIME = {"hour": 8, "minute": 0}  # Время отправки (UTC). Amsterdam = UTC+2, значит 8:00 UTC = 10:00 утра

FIXED_TASKS = [
    "Проверить почту и срочные сообщения",
    "Стендап с командой",
    "Обновить статус задач в трекере",
]

TASKS_FILE = "tasks.json"  # Файл для хранения задач команды

# ─── ХРАНИЛИЩЕ ЗАДАЧ ─────────────────────────────────────────────────────────

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

# ─── ФОРМАТИРОВАНИЕ СООБЩЕНИЯ ─────────────────────────────────────────────────

def build_message():
    today = datetime.now().strftime("%d.%m.%Y")
    lines = [f"📋 *Список дел на {today}*\n"]

    lines.append("*🔁 Ежедневные задачи:*")
    for i, task in enumerate(FIXED_TASKS, 1):
        lines.append(f"  ☐ {task}")

    tasks = load_tasks()
    if tasks:
        lines.append("\n*✏️ Задачи команды:*")
        for i, task in enumerate(tasks, 1):
            status = "✅" if task.get("done") else "☐"
            text = task["text"]
            if task.get("assignee"):
                text += f" — @{task['assignee']}"
            if task.get("deadline"):
                text += f" _(до {task['deadline']})_"
            lines.append(f"  {status} {i}. {text}")
    else:
        lines.append("\n_Командных задач пока нет. Добавь через /add_")

    lines.append("\n💡 Команды: /add /done /list /clear")
    return "\n".join(lines)

# ─── ОТПРАВКА ПО РАСПИСАНИЮ ───────────────────────────────────────────────────

async def send_daily(app):
    message = build_message()
    await app.bot.send_message(
        chat_id=CHAT_ID,
        text=message,
        parse_mode="Markdown"
    )
    # Сбрасываем отметки выполнения для нового дня
    tasks = load_tasks()
    for task in tasks:
        task["done"] = False
    save_tasks(tasks)

# ─── КОМАНДЫ БОТА ────────────────────────────────────────────────────────────

async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Добавить задачу.
    Формат: /add Текст задачи @ответственный до ДД.ММ
    Примеры:
      /add Написать отчёт
      /add Позвонить клиенту @Иван до 20.04
    """
    if not context.args:
        await update.message.reply_text(
            "Укажи задачу. Пример:\n/add Написать отчёт @Иван до 20.04"
        )
        return

    text = " ".join(context.args)
    task = {"text": text, "done": False, "assignee": None, "deadline": None}

    # Парсим @упоминание
    words = text.split()
    for word in words:
        if word.startswith("@"):
            task["assignee"] = word[1:]
            task["text"] = task["text"].replace(word, "").strip()

    # Парсим дедлайн "до ДД.ММ" или "до ДД.ММ.ГГГГ"
    if "до " in task["text"]:
        parts = task["text"].split("до ")
        task["text"] = parts[0].strip()
        task["deadline"] = parts[1].strip()

    tasks = load_tasks()
    tasks.append(task)
    save_tasks(tasks)

    await update.message.reply_text(f"✅ Задача добавлена: {task['text']}")


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отметить задачу выполненной. Пример: /done 1"""
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Укажи номер задачи. Пример: /done 1")
        return

    index = int(context.args[0]) - 1
    tasks = load_tasks()

    if 0 <= index < len(tasks):
        tasks[index]["done"] = True
        save_tasks(tasks)
        await update.message.reply_text(f"✅ Задача #{index+1} выполнена!")
    else:
        await update.message.reply_text("❌ Задача с таким номером не найдена.")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущий список дел."""
    message = build_message()
    await update.message.reply_text(message, parse_mode="Markdown")


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить все задачи команды (не трогает фиксированные)."""
    save_tasks([])
    await update.message.reply_text("🗑 Список задач команды очищен.")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для ежедневных задач команды.\n\n"
        "Команды:\n"
        "/add Задача @ответственный до ДД.ММ — добавить задачу\n"
        "/done 1 — отметить задачу #1 выполненной\n"
        "/list — показать список задач\n"
        "/clear — очистить список\n\n"
        f"📬 Каждый день в 10:00 (Amsterdam) я буду отправлять список в чат."
    )

# ─── ЗАПУСК ───────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("add",   cmd_add))
    app.add_handler(CommandHandler("done",  cmd_done))
    app.add_handler(CommandHandler("list",  cmd_list))
    app.add_handler(CommandHandler("clear", cmd_clear))

    # Планировщик ежедневной отправки
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: app.create_task(send_daily(app)),
        trigger="cron",
        hour=SEND_TIME["hour"],
        minute=SEND_TIME["minute"],
    )
    scheduler.start()

    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
