# bot_app.py
from contextlib import asynccontextmanager
import os
import sys
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

import config
from main import setup, start, button_handler
from handlers.lineas_handler import lineas_handlers
from handlers.paquetes_handler import paquetes_handlers
from handlers.recargas_handler import recargas_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Inicializar DB
setup()

# Crear aplicación del bot
bot_app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).updater(None).build()

# Registrar handlers
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(button_handler, pattern="^consultar_"))

for handler in (*lineas_handlers, *paquetes_handlers, *recargas_handlers):
    bot_app.add_handler(handler)

# Webhook URL
WEBHOOK_PATH = f"/webhook/{config.TELEGRAM_BOT_TOKEN}"
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL", getattr(config, "PUBLIC_URL", None))
WEBHOOK_URL = f"{PUBLIC_URL}{WEBHOOK_PATH}" if PUBLIC_URL else None

@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("🚀 Startup FastAPI: inicializando PTB…")
    await bot_app.initialize()
    await bot_app.start()
    logger.info("✅ PTB iniciado")

    if WEBHOOK_URL:
        try:
            await bot_app.bot.set_webhook(
                url=WEBHOOK_URL,
                allowed_updates=Update.ALL_TYPES,
            )
            logger.info(f"🌐 Webhook configurado: {WEBHOOK_URL}")
        except Exception as e:
            logger.error(f"⚠️ No se pudo configurar el webhook: {e}", exc_info=True)

    try:
        yield
    finally:
        logger.info("🛑 Shutdown FastAPI: deteniendo PTB…")
        try:
            await bot_app.stop()
            logger.info("✅ PTB detenido")
        except Exception as e:
            logger.error(f"⚠️ Error al detener PTB: {e}", exc_info=True)

app = FastAPI(lifespan=lifespan)

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    logger.info("📩 Webhook: solicitud recibida")
    try:
        payload = await request.json()
        update_obj = Update.de_json(payload, bot_app.bot)
        await bot_app.process_update(update_obj)
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"❌ Error procesando el update: {e}", exc_info=True)
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/")
def health():
    from datetime import datetime
    logger.info("🟢 Health check: OK")
    return {"status": "Bot activo", "timestamp": str(datetime.now())}

