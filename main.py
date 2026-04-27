import asyncio
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters
from config import BOT_TOKEN, PORT
from handlers import (
    start, cancel_test, age_handler, weight_handler, height_handler,
    level_handler, goal_handler, start_training, handle_training_input,
    progress, reset_test, AGE, WEIGHT, HEIGHT, LEVEL, GOAL, TRAINING
)

logging.basicConfig(level=logging.INFO)

# Создаём приложение бота
app = (Application.builder().token(BOT_TOKEN).build())

# ConversationHandler для теста
conv_test = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age_handler)],
        WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, weight_handler)],
        HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, height_handler)],
        LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, level_handler)],
        GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, goal_handler)],
    },
    fallbacks=[MessageHandler(filters.Regex("^Отмена$"), cancel_test)],
)

# Регистрируем обработчики
app.add_handler(conv_test)
app.add_handler(MessageHandler(filters.Regex("^🏋️ Начать тренировку$"), start_training))
app.add_handler(MessageHandler(filters.Regex("^📊 Мой прогресс$"), progress))
app.add_handler(MessageHandler(filters.Regex("^🔄 Сбросить тест$"), reset_test))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_training_input))

async def health(request):
    return web.Response(text="OK")

async def main():
    # Инициализируем БД (один раз при запуске)
    from db import init_db
    await init_db()
    
    # Устанавливаем вебхук
    # Render даёт URL вида https://app-name.onrender.com
    # Получаем его из переменной окружения RENDER_EXTERNAL_URL или хардкодим? Лучше передать.
    # Для простоты предположим, что URL = "https://ваше-имя.onrender.com"
    # В render нужно задать переменную окружения RENDER_EXTERNAL_URL
    import os
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not webhook_url:
        raise ValueError("RENDER_EXTERNAL_URL not set")
    webhook_url += "/webhook"
    await app.bot.set_webhook(webhook_url)
    
    # Создаём aiohttp веб-сервер
    async def webhook_handler(request):
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        return web.Response()
    
    web_app = web.Application()
    web_app.router.add_post("/webhook", webhook_handler)
    web_app.router.add_get("/health", health)
    
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Webhook listening on port {PORT}")
    await asyncio.Event().wait()  # бесконечно слушаем

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())