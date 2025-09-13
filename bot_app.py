# bot_app.py
import os
import sys
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from telegram import Update
from telegram.ext import Application

import config
from bot.core import TelegramBot
from notificaciones import enviar_notificaciones_programadas

# -----------------------
# Configurar logging
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# -----------------------
# Crear aplicación del bot
# -----------------------
bot_app = Application.builder().token(config.TELEGRAM_TOKEN).updater(None).build()

telegram_bot = TelegramBot()
bot_app = telegram_bot.application

# -----------------------
# Configurar webhook
# -----------------------
WEBHOOK_PATH = f"/webhook/{config.TELEGRAM_TOKEN}"
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL", getattr(config, "PUBLIC_URL", None))
WEBHOOK_URL = f"{PUBLIC_URL}{WEBHOOK_PATH}" if PUBLIC_URL else None

# -----------------------
# Lifespan de FastAPI
# -----------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Startup FastAPI: inicializando PTB…")
    await bot_app.initialize()
    await bot_app.start()
    logger.info("✅ PTB iniciado")
    logger.info("✅ Base de datos ya inicializada por TelegramBot")

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

# -----------------------
# Crear instancia FastAPI
# -----------------------
app = FastAPI(lifespan=lifespan)

# -----------------------
# Endpoint webhook
# -----------------------
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

# ------------------------
# Endpoint cron-job para notificaciones
# ------------------------
@app.get("/check-notifications")
@app.post("/check-notifications")
async def check_notifications_endpoint(request: Request):
    logger.info("🔔 [NOTIFICACIONES] Iniciando revisión programada de fechas...")
    try:
        await enviar_notificaciones_programadas(bot_app.bot)
        logger.info("✅ [NOTIFICACIONES] Revisión completada. Notificaciones enviadas si correspondía.")
        return JSONResponse(content={"status": "ok", "message": "Revisión de notificaciones completada"})
    except Exception as e:
        logger.error(f"❌ [NOTIFICACIONES] Error al enviar notificaciones: {str(e)}", exc_info=True)
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

# -----------------------
# Ruta de salud
# -----------------------
@app.get("/")
def health():
    from datetime import datetime
    logger.info("🟢 Health check: OK")
    return {"status": "Bot activo", "timestamp": str(datetime.now())}

# -----------------------
# Endpoint para UptimeRobot (evitar cold start)
# -----------------------
@app.get("/ping")
def ping():
    """Endpoint simple para UptimeRobot. Responde 'pong'."""
    logger.info("🏓 Ping recibido (UptimeRobot)")
    return {"status": "pong"}