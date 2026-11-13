import asyncio
import json
import os
import shutil
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Токен (ОБЯЗАТЕЛЬНО СГЕНЕРИРУЙТЕ НОВЫЙ В @BotFather и вставьте сюда)
bot = Bot(token="8914648437:AAE7qfTXQY1VF_wUx-X-sRvqnzGYk3PtwmY")
dp = Dispatcher()

BEAR_GIFT_ID = "5170233102089322756"
COUNTER_FILE = "msg_counter.txt"
WINNERS_FILE = "winners.json"
BACKUP_FILE = "winners_backup.json"

# Ваш ID для доступа к админке
ADMIN_ID = 6305430094 

# ---------- Счётчик (не сбрасывается) ----------
def get_count():
    try:
        with open(COUNTER_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0

def save_count(c):
    with open(COUNTER_FILE, "w") as f:
        f.write(str(c))

# ---------- Победители (только добавление, с бэкапом) ----------
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

def save_winner(user_id, username, full_name, message_count, chat_id, chat_title):
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
        "gift": "Мишка",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

    with open(WINNERS_FILE, "w", encoding="utf-8") as f:
        json.dump(winners, f, ensure_ascii=False, indent=2)

# ---------- Команда /start в личке ----------
@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        # Админка для вас
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Админ-панель", callback_data="admin_panel")]
        ])
        await message.answer(
            "👋 Привет, Админ!\n\n"
            "Я бот для выдачи мишек в чатах.\n"
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

    pos = ((count - 1) % 20) + 1

    if 15 <= pos <= 20:
        user = message.from_user
        user_id = user.id

        try:
            await bot.send_gift(
                user_id=user_id,
                gift_id=BEAR_GIFT_ID,
                text=f"🎁 Поздравляем! Вы выиграли мишку (сообщение #{count})"
            )

            save_winner(
                user_id=user_id,
                username=user.username,
                full_name=user.full_name,
                message_count=count,
                chat_id=message.chat.id,
                chat_title=message.chat.title,
            )

            mention = f"@{user.username}" if user.username else user.full_name
            await message.reply(
                f"🎉 <b>Поздравляем!</b>\n"
                f"🎁 <b>{mention}</b> выиграл <b>мишку</b> от @gavendlu\n"
                f"✅ Подарок отправлен.\n\n"
                f"🚨 Пишите сообщения в чате и получайте возможность так же залутать подарки!",
                parse_mode="HTML",
            )

        except Exception as e:
            print(f"Ошибка отправки подарка: {e}")
            await message.reply("😢 Не удалось отправить подарок, обратитесь к администратору.")

# ---------- Админ-панель ----------
def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Экспорт в CSV", callback_data="export_csv")
    kb.button(text="🔄 Обновить список", callback_data="refresh")
    return kb.as_markup()

def winners_text():
    winners = load_winners()
    if not winners:
        return "Пока никто не выигрывал."
    lines = [f"<b>Всего победителей:</b> {len(winners)}\n"]
    for i, w in enumerate(winners[-30:], 1):
        mention = f"@{w['username']}" if w.get("username") else w.get("full_name", "—")
        lines.append(
            f"{i}. {mention} (ID: <code>{w['user_id']}</code>) — "
            f"{w.get('gift', 'Мишка')}, сообщение #{w.get('message_number', '?')}, {w.get('date', '?')}"
        )
    if len(winners) > 30:
        lines.append(f"\n… и ещё {len(winners) - 30}. Полный список — в экспорте.")
    return "\n".join(lines)

@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("У вас нет доступа.", show_alert=True)
        return
    await call.message.edit_text(winners_text(), parse_mode="HTML", reply_markup=admin_kb())
    await call.answer()

@dp.callback_query(F.data == "refresh")
async def cb_refresh(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.edit_text(winners_text(), parse_mode="HTML", reply_markup=admin_kb())
    await call.answer("Обновлено")

@dp.callback_query(F.data == "export_csv")
async def cb_export(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    winners = load_winners()
    if not winners:
        await call.answer("Список пуст", show_alert=True)
        return

    csv_path = "winners_export.csv"
    with open(csv_path, "w", encoding="utf-8-sig") as f:
        f.write("№;user_id;username;full_name;gift;message_number;chat_title;date\n")
        for i, w in enumerate(winners, 1):
            f.write(
                f"{i};{w['user_id']};{w.get('username', '')};{w.get('full_name', '')};"
                f"{w.get('gift', 'Мишка')};{w.get('message_number', '')};"
                f"{w.get('chat_title', '')};{w.get('date', '')}\n"
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
