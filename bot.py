import asyncio
import json
import os
import shutil
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Токен (ОБЯЗАТЕЛЬНО СГЕНЕРИРУЙТЕ НОВЫЙ В @BotFather)
bot = Bot(token="8914648437:AAE7qfTXQY1VF_wUx-X-sRvqnzGYk3PtwmY")
dp = Dispatcher()

COUNTER_FILE = "msg_counter.txt"
WINNERS_FILE = "winners.json"
BACKUP_FILE = "winners_backup.json"
TARGET_FILE = "target_pos.txt"
BEAR_IMAGE = "bear.png"  # положи картинку мишки рядом со скриптом

# ---------- Админы ----------
ADMIN_IDS = {6305430094, 6699838073}

# ---------- Счётчик ----------
def get_count():
    try:
        with open(COUNTER_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0

def save_count(c):
    with open(COUNTER_FILE, "w") as f:
        f.write(str(c))

# ---------- Выигрышная позиция ----------
def get_target_pos():
    try:
        with open(TARGET_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None

def save_target_pos(pos):
    with open(TARGET_FILE, "w") as f:
        f.write(str(pos))

# ---------- Победители ----------
def load_winners():
    for path in (WINNERS_FILE, BACKUP_FILE):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, OSError):
                continue
    return []

def save_winners(winners):
    with open(WINNERS_FILE, "w", encoding="utf-8") as f:
        json.dump(winners, f, ensure_ascii=False, indent=2)

def save_new_winner(user_id, username, full_name, message_count, chat_id, chat_title):
    winners = load_winners()
    if os.path.exists(WINNERS_FILE):
        try:
            shutil.copy(WINNERS_FILE, BACKUP_FILE)
        except OSError:
            pass

    winners.append({
        "user_id": user_id,
        "username": username or "",
        "full_name": full_name,
        "message_number": message_count,
        "chat_id": chat_id,
        "chat_title": chat_title or "",
        "status": "Ожидает выдачи",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_winners(winners)

# ---------- Команда /start ----------
@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Админ-панель", callback_data="admin_panel")]
        ])
        await message.answer(
            "👋 Привет, Админ!\n\n"
            "Я бот для выдачи подарков в чатах.\n"
            "Нажми на кнопку ниже, чтобы открыть панель управления.",
            reply_markup=kb
        )
    else:
        await message.answer("👋 Привет! Я бот для выдачи подарков в чатах. Добавь меня в свой чат!")

# ---------- Сообщения в чате ----------
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(message: types.Message):
    if message.text and message.text.startswith("/"):
        return

    count = get_count() + 1
    save_count(count)

    # Цикл из 1500 сообщений, выигрышная позиция 1300–1500
    pos = ((count - 1) % 1500) + 1

    # Начинается новый цикл - генерируем позицию
    if pos == 1:
        new_target = random.randint(1300, 1500)
        save_target_pos(new_target)

    target_pos = get_target_pos()

    # Если текущее сообщение попало на выигрышную позицию
    if pos == target_pos:
        user = message.from_user
        user_id = user.id

        save_new_winner(
            user_id=user_id,
            username=user.username,
            full_name=user.full_name,
            message_count=count,
            chat_id=message.chat.id,
            chat_title=message.chat.title,
        )

        mention = f"@{user.username}" if user.username else user.full_name
        caption = (
            f"🥳 <b>Поздравляю!</b>\n"
            f"🎁 <b>{mention}</b> ты выиграл <b>мишку</b> 🧸 от @gavendlu\n"
            f"✅ Подарок отправлен.\n\n"
            f"‼️ Пишите сообщения в чате и получайте возможность так же залутать мишку!"
        )

        # Отправляем с картинкой, если файл есть, иначе просто текст
        if os.path.exists(BEAR_IMAGE):
            await message.reply_photo(
                photo=FSInputFile(BEAR_IMAGE),
                caption=caption,
                parse_mode="HTML"
            )
        else:
            await message.reply(caption, parse_mode="HTML")

# ---------- Админ-панель ----------
def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Экспорт в CSV", callback_data="export_csv")
    kb.button(text="🔄 Обновить список", callback_data="refresh")
    kb.button(text="✅ Выдать всем (ожидает)", callback_data="give_all")
    return kb.as_markup()

def winners_text():
    winners = load_winners()
    if not winners:
        return "Пока никто не выигрывал."
    lines = [f"<b>Всего победителей:</b> {len(winners)}\n"]

    # Показываем последние 30
    for i, w in enumerate(winners[-30:], 1):
        mention = f"@{w['username']}" if w.get("username") else w.get("full_name", "—")
        status = w.get("status", "Ожидает выдачи")
        status_emoji = "⏳" if status == "Ожидает выдачи" else "✅"
        lines.append(
            f"{i}. {mention} (ID: <code>{w['user_id']}</code>) — "
            f"сообщение #{w.get('message_number', '?')}, {status_emoji} {status}"
        )
    if len(winners) > 30:
        lines.append(f"\n… и ещё {len(winners) - 30}. Полный список — в экспорте.")
    return "\n".join(lines)

@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("У вас нет доступа.", show_alert=True)
        return

    await call.message.edit_text(
        winners_text(),
        parse_mode="HTML",
        reply_markup=admin_kb()
    )
    await call.answer()

@dp.callback_query(F.data == "refresh")
async def cb_refresh(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("У вас нет доступа.", show_alert=True)
        return

    await call.message.edit_text(
        winners_text(),
        parse_mode="HTML",
        reply_markup=admin_kb()
    )
    await call.answer("Обновлено")

@dp.callback_query(F.data == "give_all")
async def cb_give_all(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("У вас нет доступа.", show_alert=True)
        return

    winners = load_winners()
    count = 0
    for w in winners:
        if w.get("status") == "Ожидает выдачи":
            w["status"] = "Выдан вручную"
            count += 1

    save_winners(winners)
    await call.answer(f"Отмечено как выданные: {count} чел.", show_alert=True)

    await call.message.edit_text(
        winners_text(),
        parse_mode="HTML",
        reply_markup=admin_kb()
    )

@dp.callback_query(F.data == "export_csv")
async def cb_export(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("У вас нет доступа.", show_alert=True)
        return

    winners = load_winners()
    if not winners:
        await call.answer("Список пуст", show_alert=True)
        return

    csv_path = "winners_export.csv"
    with open(csv_path, "w", encoding="utf-8-sig") as f:
        f.write("№;user_id;username;full_name;gift;message_number;chat_title;status;date\n")
        for i, w in enumerate(winners, 1):
            f.write(
                f"{i};{w['user_id']};{w.get('username', '')};{w.get('full_name', '')};"
                f"Мишка;{w.get('message_number', '')};"
                f"{w.get('chat_title', '')};{w.get('status', 'Ожидает выдачи')};{w.get('date', '')}\n"
            )

    await call.message.answer_document(
        FSInputFile(csv_path),
        caption=f"📤 Экспорт победителей ({len(winners)} чел.)"
    )
    await call.answer("Готово")

# ---------- Запуск ----------
async def main():
    print("Бот запущен... Данные не сбрасываются.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
