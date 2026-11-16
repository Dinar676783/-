import asyncio
import json
import os
import shutil
import random
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ---------- ТОКЕН (один бот) ----------
bot = Bot(token="8914648437:AAE7qfTXQY1VF_wUx-X-sRvqnzGYk3PtwmY")
dp = Dispatcher()

# ---------- ФАЙЛЫ ----------
COUNTER_FILE = "msg_counter.txt"
WINNERS_FILE = "winners.json"
BACKUP_FILE = "winners_backup.json"
TARGET_FILE = "target_pos.txt"
BEAR_IMAGE = "bear.png"

NFT_WINNERS_FILE = "nft_winners.json"
NFT_BACKUP_FILE = "nft_winners_backup.json"
NFT_IMAGE = "nft.png"
CHATS_FILE = "known_chats.json"

# ---------- Админы ----------
ADMIN_IDS = {6305430094, 6699838073}

# chat_id -> данные ивента
active_giveaways = {}

# user_id -> данные ожидания ввода (chat_id, step)
waiting_for_nft_input = {}

# ============================================================
#                     ОБЩИЕ ХЕЛПЕРЫ
# ============================================================

def _load_json_list(paths):
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, OSError):
                continue
    return []

def _save_json_list(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def remember_chat(chat_id, title):
    chats = _load_json_list([CHATS_FILE])
    for c in chats:
        if c["chat_id"] == chat_id:
            c["title"] = title
            _save_json_list(CHATS_FILE, chats)
            return
    chats.append({"chat_id": chat_id, "title": title})
    _save_json_list(CHATS_FILE, chats)

# ============================================================
#                        МИШКИ
# ============================================================

def get_count():
    try:
        with open(COUNTER_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0

def save_count(c):
    with open(COUNTER_FILE, "w") as f:
        f.write(str(c))

def get_target_pos():
    try:
        with open(TARGET_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None

def save_target_pos(pos):
    with open(TARGET_FILE, "w") as f:
        f.write(str(pos))

def load_winners():
    return _load_json_list([WINNERS_FILE, BACKUP_FILE])

def save_winners(winners):
    _save_json_list(WINNERS_FILE, winners)

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
        "gift": "Мишка",
        "status": "Ожидает выдачи",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_winners(winners)

# ============================================================
#                        NFT
# ============================================================

def nft_load_winners():
    return _load_json_list([NFT_WINNERS_FILE, NFT_BACKUP_FILE])

def nft_save_winners(winners):
    _save_json_list(NFT_WINNERS_FILE, winners)

def nft_save_new_winner(user_id, username, full_name, chat_id, chat_title, prize):
    winners = nft_load_winners()
    if os.path.exists(NFT_WINNERS_FILE):
        try:
            shutil.copy(NFT_WINNERS_FILE, NFT_BACKUP_FILE)
        except OSError:
            pass

    winners.append({
        "user_id": user_id,
        "username": username or "",
        "full_name": full_name,
        "chat_id": chat_id,
        "chat_title": chat_title or "",
        "gift": prize,
        "status": "Ожидает выдачи",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    nft_save_winners(winners)

# ============================================================
#                   СБРОС ЗАВИСШИХ ИВЕНТОВ
# ============================================================

@dp.message(Command("reset"), F.chat.type == "private")
async def cmd_reset(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    count = len(active_giveaways)
    for chat_id, data in active_giveaways.items():
        if data.get("timer_task"):
            data["timer_task"].cancel()
            
    active_giveaways.clear()
    await message.answer(f"🧹 Очищено зависших ивентов: {count}")

# ============================================================
#                   АДМИН-ПАНЕЛЬ (ЛИЧКА)
# ============================================================

@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Запустить NFT", callback_data="start_launch_nft")],
            [InlineKeyboardButton(text="🧸 Мишки (статистика)", callback_data="bear_panel")],
            [InlineKeyboardButton(text="🎨 NFT (статистика)", callback_data="nft_admin_panel")],
        ])
        await message.answer(
            "👋 Привет, Админ!\n\n"
            "Нажми «🚀 Запустить NFT», чтобы выбрать чат и начать ивент.\n"
            "Или посмотри статистику победителей.\n\n"
            "💡 Если бот пишет, что ивент уже идет, отправь /reset",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await message.answer("👋 Привет! Я бот для розыгрышей. Добавь меня в свой чат, чтобы участвовать в ивентах!")

@dp.message(Command("launch"), F.chat.type == "private")
async def cmd_launch_nft(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    chats = _load_json_list([CHATS_FILE])
    if not chats:
        await message.answer("❌ Бот пока не знает ни одного чата.\nЗайди в нужный чат и напиши там /start или любое сообщение, чтобы я его запомнил.")
        return

    kb = InlineKeyboardBuilder()
    for c in chats:
        kb.button(text=f"💬 {c['title']}", callback_data=f"select_chat_{c['chat_id']}")
    kb.adjust(1)

    await message.answer(
        "👇 Выбери чат, где будем разыгрывать NFT:",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(F.data.startswith("select_chat_"))
async def cb_select_chat(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    chat_id = int(call.data.split("_")[2])
    chat_title = next((c["title"] for c in _load_json_list([CHATS_FILE]) if c["chat_id"] == chat_id), "Неизвестный чат")

    # Принудительно чистим старый ивент, если он там завис
    if chat_id in active_giveaways:
        old_data = active_giveaways.pop(chat_id)
        if old_data.get("timer_task"):
            old_data["timer_task"].cancel()

    waiting_for_nft_input[call.from_user.id] = {"chat_id": chat_id, "title": chat_title}

    await call.message.edit_text(
        f"✅ Выбран чат: <b>{chat_title}</b>\n\n"
        f"📝 Теперь напиши параметры в ответном сообщении:\n"
        f"<code>[минуты] [название приза]</code>\n\n"
        f"Пример: <code>1 HappyBrownie-83197</code>",
        parse_mode="HTML"
    )
    await call.answer()

# ============================================================
#                ВВОД ДАННЫХ ДЛЯ NFT (В ЛИЧКЕ)
# ============================================================

@dp.message(F.chat.type == "private", F.text)
async def handle_nft_input(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return

    if user_id in waiting_for_nft_input:
        data = waiting_for_nft_input.pop(user_id)
        chat_id = data["chat_id"]
        chat_title = data["title"]
        
        args = message.text.split(maxsplit=1)
        try:
            minutes = int(args[0])
            if minutes < 1 or minutes > 60:
                raise ValueError
            prize = args[1] if len(args) > 1 else "NFT Подарок"
        except (ValueError, IndexError):
            await message.answer(
                "⚠️ <b>Неверный формат!</b>\n"
                "Напиши: <code>[минуты] [название приза]</code>\n"
                "Пример: <code>1 HappyBrownie-83197</code>",
                parse_mode="HTML"
            )
            return

        active_giveaways[chat_id] = {
            "hold_time": minutes * 60,
            "prize": prize,
            "chat_title": chat_title,
            "leader_id": None,
            "leader_name": "",
            "leader_username": "",
            "timer_task": None,
            "leader_message_id": None
        }

        start_text = (
            f"👋 <b>Ивент начался!</b>\n\n"
            f"1 сообщение = 1 очко.\n"
            f"🎯 Цель: продержаться {minutes} мин без перебива.\n\n"
            f"🏅 <b>Приз:</b>\n"
            f"{prize}\n\n"
            f"👉 <i>Напишите сообщение, чтобы стать лидером!</i>"
        )
        
        try:
            await bot.send_message(chat_id, start_text, parse_mode="HTML")
            await message.answer(f"✅ Ивент успешно запущен в чате <b>{chat_title}</b>!\nПриз: {prize}", parse_mode="HTML")
        except Exception as e:
            await message.answer(f"❌ Ошибка запуска в чате: {e}\nВозможно, бот не админ или был удален.")

# ============================================================
#                    СООБЩЕНИЯ В ЧАТЕ
# ============================================================

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(message: types.Message):
    remember_chat(message.chat.id, message.chat.title)

    if message.text and message.text.startswith("/"):
        return
    if message.from_user.is_bot:
        return

    chat_id = message.chat.id

    if chat_id in active_giveaways:
        giveaway = active_giveaways[chat_id]
        
        # Если пишет тот же лидер - игнорируем
        if giveaway["leader_id"] == message.from_user.id:
            return
            
        new_leader = message.from_user
        giveaway["leader_id"] = new_leader.id
        giveaway["leader_name"] = new_leader.full_name
        giveaway["leader_username"] = new_leader.username or ""

        # Отменяем старый таймер, если он был
        if giveaway.get("timer_task"):
            giveaway["timer_task"].cancel()

        # Удаляем старое сообщение бота с лидером
        if giveaway.get("leader_message_id"):
            try:
                await bot.delete_message(chat_id, giveaway["leader_message_id"])
            except Exception:
                pass

        mention = f"@{new_leader.username}" if new_leader.username else new_leader.full_name
        hold_min = giveaway["hold_time"] // 60

        msg = await message.reply(
            f"🔄 <b>Перебито!</b>\n\n"
            f"👑 Новый лидер: {mention}\n"
            f"⏳ До конца: {hold_min} мин",
            parse_mode="HTML"
        )
        giveaway["leader_message_id"] = msg.message_id

        task = asyncio.create_task(nft_hold_timer(chat_id, giveaway["hold_time"]))
        giveaway["timer_task"] = task
        return

    count = get_count() + 1
    save_count(count)

    pos = ((count - 1) % 1500) + 1

    if pos == 1:
        new_target = random.randint(1300, 1500)
        save_target_pos(new_target)

    target_pos = get_target_pos()

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

        if os.path.exists(BEAR_IMAGE):
            await message.reply_photo(photo=FSInputFile(BEAR_IMAGE), caption=caption, parse_mode="HTML")
        else:
            await message.reply(caption, parse_mode="HTML")

# ============================================================
#                NFT: ТАЙМЕР УДЕРЖАНИЯ
# ============================================================

async def nft_hold_timer(chat_id: int, hold_time: int):
    try:
        # Ждем нужное время
        await asyncio.sleep(hold_time)
        
        # Проверяем, существует ли еще ивент
        giveaway = active_giveaways.get(chat_id)
        if not giveaway:
            return

        winner_id = giveaway["leader_id"]
        winner_username = giveaway["leader_username"]
        winner_name = giveaway["leader_name"]
        prize = giveaway["prize"]
        chat_title = giveaway.get("chat_title", "")

        # Удаляем последнее сообщение лидера перед финалом
        if giveaway.get("leader_message_id"):
            try:
                await bot.delete_message(chat_id, giveaway["leader_message_id"])
            except Exception:
                pass

        # Очищаем ивент из памяти
        active_giveaways.pop(chat_id, None)

        # Сохраняем в файл
        nft_save_new_winner(
            user_id=winner_id,
            username=winner_username,
            full_name=winner_name,
            chat_id=chat_id,
            chat_title=chat_title,
            prize=prize
        )

        mention = f"@{winner_username}" if winner_username else winner_name
        text = (
            f"🏆 <b>Ивент завершен!</b>\n\n"
            f"🎉 Победитель: {mention}\n"
            f"🎁 Приз: <b>{prize}</b>\n\n"
            f"✅ Подарок будет выдан администратором."
        )

        if os.path.exists(NFT_IMAGE):
            await bot.send_photo(chat_id, photo=FSInputFile(NFT_IMAGE), caption=text, parse_mode="HTML")
        else:
            await bot.send_message(chat_id, text, parse_mode="HTML")

    except asyncio.CancelledError:
        pass

# ============================================================
#                   КНОПКИ И СТАТИСТИКА
# ============================================================

@dp.callback_query(F.data == "start_launch_nft")
async def cb_start_launch_nft(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    chats = _load_json_list([CHATS_FILE])
    if not chats:
        await call.message.edit_text("❌ Бот пока не знает ни одного чата.\nЗайди в нужный чат и напиши там любое сообщение, чтобы я его запомнил.")
        return

    kb = InlineKeyboardBuilder()
    for c in chats:
        kb.button(text=f"💬 {c['title']}", callback_data=f"select_chat_{c['chat_id']}")
    kb.button(text="⬅️ Назад", callback_data="back_to_menu")
    kb.adjust(1)

    await call.message.edit_text("👇 Выбери чат, где будем разыгрывать NFT:", reply_markup=kb.as_markup())
    await call.answer()

def nft_admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Экспорт в CSV", callback_data="nft_export_csv")
    kb.button(text="🔄 Обновить список", callback_data="nft_refresh")
    kb.button(text="✅ Выдать всем", callback_data="nft_give_all")
    kb.button(text="⬅️ Назад", callback_data="back_to_menu")
    return kb.as_markup()

def nft_winners_text():
    winners = nft_load_winners()
    if not winners:
        return "Пока никто не выигрывал NFT."
    lines = [f"<b>Всего победителей NFT:</b> {len(winners)}\n"]
    for i, w in enumerate(winners[-30:], 1):
        mention = f"@{w['username']}" if w.get("username") else w.get("full_name", "—")
        status = w.get("status", "Ожидает выдачи")
        status_emoji = "⏳" if status == "Ожидает выдачи" else "✅"
        gift = w.get("gift", "NFT")
        chat = w.get("chat_title", "—")
        lines.append(f"{i}. {mention} — <b>{gift}</b> ({chat}) {status_emoji} {status}")
    if len(winners) > 30:
        lines.append(f"\n… и ещё {len(winners) - 30}. Полный список — в экспорте.")
    return "\n".join(lines)

@dp.callback_query(F.data == "nft_admin_panel")
async def cb_nft_panel(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    await call.message.edit_text(nft_winners_text(), parse_mode="HTML", reply_markup=nft_admin_kb())
    await call.answer()

@dp.callback_query(F.data == "nft_refresh")
async def cb_nft_refresh(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    await call.message.edit_text(nft_winners_text(), parse_mode="HTML", reply_markup=nft_admin_kb())
    await call.answer("Обновлено")

@dp.callback_query(F.data == "nft_give_all")
async def cb_nft_give_all(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    winners = nft_load_winners()
    count = 0
    for w in winners:
        if w.get("status") == "Ожидает выдачи":
            w["status"] = "Выдан вручную"
            count += 1
    nft_save_winners(winners)
    await call.answer(f"Отмечено как выданные: {count} чел.", show_alert=True)
    await call.message.edit_text(nft_winners_text(), parse_mode="HTML", reply_markup=nft_admin_kb())

@dp.callback_query(F.data == "nft_export_csv")
async def cb_nft_export(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    winners = nft_load_winners()
    if not winners:
        await call.answer("Список пуст", show_alert=True)
        return
    csv_path = "nft_winners_export.csv"
    with open(csv_path, "w", encoding="utf-8-sig") as f:
        f.write("№;user_id;username;full_name;gift;chat_title;status;date\n")
        for i, w in enumerate(winners, 1):
            f.write(
                f"{i};{w['user_id']};{w.get('username', '')};{w.get('full_name', '')};"
                f"{w.get('gift', 'NFT')};{w.get('chat_title', '')};"
                f"{w.get('status', 'Ожидает выдачи')};{w.get('date', '')}\n"
            )
    await call.message.answer_document(FSInputFile(csv_path), caption=f"📤 Экспорт NFT ({len(winners)} чел.)")
    await call.answer("Готово")

def bear_admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Экспорт в CSV", callback_data="bear_export_csv")
    kb.button(text="🔄 Обновить список", callback_data="bear_refresh")
    kb.button(text="✅ Выдать всем", callback_data="bear_give_all")
    kb.button(text="⬅️ Назад", callback_data="back_to_menu")
    return kb.as_markup()

def bear_winners_text():
    winners = load_winners()
    if not winners:
        return "Пока никто не выигрывал мишек."
    lines = [f"<b>Всего победителей (мишки):</b> {len(winners)}\n"]
    for i, w in enumerate(winners[-30:], 1):
        mention = f"@{w['username']}" if w.get("username") else w.get("full_name", "—")
        status = w.get("status", "Ожидает выдачи")
        status_emoji = "⏳" if status == "Ожидает выдачи" else "✅"
        lines.append(f"{i}. {mention} — сообщение #{w.get('message_number', '?')}, {status_emoji} {status}")
    return "\n".join(lines)

@dp.callback_query(F.data == "bear_panel")
async def cb_bear_panel(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    await call.message.edit_text(bear_winners_text(), parse_mode="HTML", reply_markup=bear_admin_kb())
    await call.answer()

@dp.callback_query(F.data == "bear_refresh")
async def cb_bear_refresh(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    await call.message.edit_text(bear_winners_text(), parse_mode="HTML", reply_markup=bear_admin_kb())
    await call.answer("Обновлено")

@dp.callback_query(F.data == "bear_give_all")
async def cb_bear_give_all(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    winners = load_winners()
    count = 0
    for w in winners:
        if w.get("status") == "Ожидает выдачи":
            w["status"] = "Выдан вручную"
            count += 1
    save_winners(winners)
    await call.answer(f"Отмечено как выданные: {count} чел.", show_alert=True)
    await call.message.edit_text(bear_winners_text(), parse_mode="HTML", reply_markup=bear_admin_kb())

@dp.callback_query(F.data == "bear_export_csv")
async def cb_bear_export(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    winners = load_winners()
    if not winners:
        await call.answer("Список пуст", show_alert=True)
        return
    csv_path = "winners_export.csv"
    with open(csv_path, "w", encoding="utf-8-sig") as f:
        f.write("№;user_id;username;full_name;gift;message_number;status;date\n")
        for i, w in enumerate(winners, 1):
            f.write(f"{i};{w['user_id']};{w.get('username', '')};{w.get('full_name', '')};Мишка;{w.get('status')};{w.get('date')}\n")
    await call.message.answer_document(FSInputFile(csv_path), caption="📤 Экспорт мишек")
    await call.answer("Готово")

@dp.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Запустить NFT", callback_data="start_launch_nft")],
        [InlineKeyboardButton(text="🧸 Мишки (статистика)", callback_data="bear_panel")],
        [InlineKeyboardButton(text="🎨 NFT (статистика)", callback_data="nft_admin_panel")],
    ])
    await call.message.edit_text("Главное меню:", reply_markup=kb)
    await call.answer()

# ============================================================
#                        ЗАПУСК
# ============================================================

async def main():
    print("Бот запущен...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
