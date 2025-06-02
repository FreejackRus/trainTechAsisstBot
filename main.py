import asyncio
from aiogram import Bot, Dispatcher
from handlers.general_handlers import router as general_router
from handlers.repair_handler import router as repair_router
from handlers.renewalV1_handler import router as renewal_router
from handlers.renewalV2_handler import router as renewalV2_router
import config
import logging
import sys

from handlers.status_handler import router as status_router
from edit.edit_repairClaim import router as edit_router
from edit.edit_renewalV1Claim import router as renewal_edit_router
from edit.edit_renewalV2Claim import router as renewalV2_edit_router




# === Логирование ===
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# === Бот и диспетчер ===
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Подключаем роутеры
dp.include_router(general_router)
dp.include_router(repair_router)
dp.include_router(status_router)
dp.include_router(renewal_router)
dp.include_router(renewalV2_router)
dp.include_router(renewal_edit_router)
dp.include_router(renewalV2_edit_router)
dp.include_router(edit_router)



# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())