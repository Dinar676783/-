import asyncio
from aiogram import Bot, Dispatcher, types

# ====== ВАШ ТОКЕН ======
BOT_TOKEN = "8914648437:AAE7qfTXQY1VF_wUx-X-sRvqnzGYk3PtwmY"

# ====== ID МИШКИ ======
BEAR_GIFT_ID = "5170233102089322756"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

COUNTER_FILE = "msg_counter.txt"


def get_count():
    try:
        with open(COUNTER_FILE, "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return 0


def save_count(c):
    with open(COUNTER_FILE, "w") as f:
        f.write(str(c))


@dp.message()
async def handle_message(message: types.Message):
    # Пропускаем команды
    if message.text and message.text.startswith("/"):
        return

    count = get_count() + 1
    save_count(count)

    # Позиция в цикле из 20 сообщений: 1–20
    pos = ((count - 1) % 20) + 1

    # Выдаём мишку с 15-го по 20-е сообщение включительно
    if 15 <= pos <= 20:
        user_id = message.from_user.id

        try:
            await bot.send_gift(
                user_id=user_id,
                gift_id=BEAR_GIFT_ID,
                text=f"🎁 Поздравляем! Вы выиграли мишку (сообщение #{count})"
            )
            await message.reply("🎉 Поздравляем! Вы выиграли мишку!")
        except Exception as e:
            print(f"Ошибка отправки подарка: {e}")
            await message.reply("😢 Не удалось отправить подарок, обратитесь к администратору.")


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())