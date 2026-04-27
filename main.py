import logging
import asyncio
import os
import sys
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

# Настройка подробного логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Импорт ваших модулей
try:
    from config import BOT_TOKEN, PORT
    from db import init_db
    from handlers import (
        start, cancel_test, age_handler, weight_handler, height_handler,
        level_handler, goal_handler, start_training, handle_training_input,
        progress, reset_test, AGE, WEIGHT, HEIGHT, LEVEL, GOAL, TRAINING
    )
except Exception as e:
    logger.exception("Ошибка импорта модулей. Проверьте структуру проекта.")
    sys.exit(1)

def main():
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

    app.add_handler(conv_test)
    app.add_handler(MessageHandler(filters.Regex("^🏋️ Начать тренировку$"), start_training))
    app.add_handler(MessageHandler(filters.Regex("^📊 Мой прогресс$"), progress))
    app.add_handler(MessageHandler(filters.Regex("^🔄 Сбросить тест$"), reset_test))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_training_input))

    return app

async def run():
    # Инициализируем БД
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных готова.")

    # Получаем URL вебхука
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not webhook_url:
        logger.error("Переменная окружения RENDER_EXTERNAL_URL не установлена!")
        # Для отладки можно использовать polling, но в render нужен вебхук
        logger.info("Проверьте, что вы добавили переменную RENDER_EXTERNAL_URL в Environment Variables.")
        sys.exit(1)
    webhook_url += "/webhook"
    logger.info(f"Устанавливаю вебхук: {webhook_url}")

    bot_app = main()
    await bot_app.bot.set_webhook(webhook_url)

    # aiohttp веб-сервер
    async def webhook_handler(request):
        try:
            data = await request.json()
            update = Update.de_json(data, bot_app.bot)
            await bot_app.process_update(update)
            return web.Response()
        except Exception as e:
            logger.exception("Ошибка при обработке вебхука")
            return web.Response(status=500)

    web_app = web.Application()
    web_app.router.add_post("/webhook", webhook_handler)
    web_app.router.add_get("/health", lambda r: web.Response(text="OK"))

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Бот запущен на порту {PORT}, ожидание вебхуков...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as e:
        logger.exception("Критическая ошибка в основном цикле")
        sys.exit(1)