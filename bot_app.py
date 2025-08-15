from contextlib import asynccontextmanager
import os
import sys
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

import config

# Logging a consola (Render capta stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Función temporal para validar admin (puedes reemplazarla con tu lógica real)
async def es_admin(update: Update) -> bool:
    # Ejemplo: solo el usuario con ID igual a config.ADMIN_ID puede usar /start
    if update.effective_user and update.effective_user.id == config.ADMIN_ID:
        return True
    else:
        logger.warning(f"Usuario {update.effective_user.id} no autorizado para usar /start")
        return False

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update):
        return

    keyboard = [
        [InlineKeyboardButton("🔍 Consultar líneas", callback_data="consultar_lineas")],
        [InlineKeyboardButton("💳 Gestionar recargas", callback_data="gestionar_recargas")],
        [InlineKeyboardButton("📦 Gestionar paquetes", callback_data="gestionar_paquetes")],
        [InlineKeyboardButton("⚙️ Gestionar líneas", callback_data="gestionar_lineas")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 Hola, soy tu bot personal de gestión de líneas móviles.\n"
        "Selecciona una opción:",
        reply_markup=reply_markup
    )

# Importar handlers
try:
    from handlers.lineas_handler import lineas_handlers
    from handlers.recargas_handler import recargas_handlers
    from handlers.paquetes_handler import paquetes_handlers
    logger.info("✅ Handlers importados correctamente")
except Exception as e:
    logger.error(f"❌ Error al importar handlers: {e}")
    raise

# Crear la aplicación del bot (modo webhook => updater(None))
try:
    bot_app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .updater(None)
        .build()
    )
    logger.info("✅ Aplicación del bot creada")
except Exception as e:
    logger.error(f"❌ Error al crear la aplicación del bot: {e}")
    raise

# Registrar el comando /start
bot_app.add_handler(CommandHandler("start", start))

# Registrar handlers adicionales
try:
    for handler in (*lineas_handlers, *recargas_handlers, *paquetes_handlers):
        bot_app.add_handler(handler)
    logger.info("✅ Todos los handlers registrados")
except Exception as e:
    logger.error(f"❌ Error al registrar handlers: {e}")
    raise

# Constantes de webhook
WEBHOOK_PATH = f"/webhook/{config.TELEGRAM_BOT_TOKEN}"
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL", getattr(config, "PUBLIC_URL", None))
WEBHOOK_URL = f"{PUBLIC_URL}{WEBHOOK_PATH}" if PUBLIC_URL else None

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Arranca/parada de PTB y (si se puede) fija el webhook al iniciar."""
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

# Inicializar FastAPI con ciclo de vida
app = FastAPI(lifespan=lifespan)

# Endpoint del webhook (Telegram POSTea aquí)
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    logger.info("📩 Webhook: solicitud recibida")
    try:
        payload = await request.json()
        update_obj = Update.de_json(payload, bot_app.bot)
        logger.info(f"🔎 Procesando update ID: {update_obj.update_id}")
        await bot_app.process_update(update_obj)
        logger.info("✅ Update procesado")
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"❌ Error procesando el update: {e}", exc_info=True)
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

# Health check
@app.get("/")
def health():
    logger.info("🟢 Health check: OK")
    from datetime import datetime
    return {"status": "Bot activo", "timestamp": str(datetime.now())}

