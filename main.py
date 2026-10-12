import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo
from aiohttp import web

from app import api, config, db, handlers, notify

log = logging.getLogger("bigbro")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN .env faylida ko'rsatilmagan")

    db.init()
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    me = await bot.get_me()

    dp = Dispatcher()
    dp.include_router(handlers.router)

    runner = web.AppRunner(api.create_app(bot, me.username))
    await runner.setup()
    await web.TCPSite(runner, config.HOST, config.PORT).start()
    log.info("Mini app server: http://%s:%s", config.HOST, config.PORT)

    await bot.set_my_commands([
        BotCommand(command="start", description="Navbat olish"),
        BotCommand(command="navbatlar", description="Navbatlar ro'yxati (xodimlar uchun)"),
    ])
    if config.WEBAPP_URL.startswith("https://"):
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Navbat olish", web_app=WebAppInfo(url=config.WEBAPP_URL))
        )
        log.info("Mini app URL: %s", config.WEBAPP_URL)
    else:
        log.warning("WEBAPP_URL https:// bilan boshlanmaydi — Telegram mini appni ocholmaydi")

    reminders = asyncio.create_task(notify.reminder_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        reminders.cancel()
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
