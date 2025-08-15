# bot_app.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import Application
import config
import logging
import sys

# Configurar logging para ver todo en los logs de Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Enviar logs a la consola (y a Render)
    ]
)

logger = logging.getLogger(__name__)

# Importar handlers
try:
    from handlers.lineas_handler import lineas_handlers
    from handlers.recargas_handler import recargas_handlers
    from handlers.paquetes_handler import paquetes_handler
    logger.info("✅ Handlers importados correctamente")
except Exception as e:
    logger.error(f"❌ Error al importar handlers: {e}")
    raise

# Inicializar FastAPI
app = FastAPI()

# Crear la aplicación del bot
try:
    bot_app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).updater(None).build()
    logger.info("✅ Aplicación del bot creada")
except Exception as e:
    logger.error(f"❌ Error al crear la aplicación del bot: {e}")
    raise

# Registrar handlers
try:
    for handler in lineas_handlers:
        bot_app.add_handler(handler)
    for handler in recargas_handlers:
        bot_app.add_handler(handler)
    for handler in paquetes_handlers:
    bot_app.add_handler(handler)
logger.info("✅ Todos los handlers registrados")
except Exception as e:
    logger.error(f"❌ Error al registrar handlers: {e}")
    raise

# Webhook: Telegram envía actualizaciones aquí
@app.post(f"/webhook/{config.TELEGRAM_BOT_TOKEN}")
async def webhook(update: dict):
    logger.info("📩 Webhook: Solicitud recibida")
    logger.debug(f"📥 Datos recibidos: {update}")

    try:
        await bot_app.initialize()
        logger.info("🔄 Bot inicializado")

        # Convertir el diccionario a objeto Update
        update_obj = Update.de_json(update, bot_app.bot)
        logger.info(f"📩 Procesando update ID: {update_obj.update_id}")

        # Procesar la actualización
        await bot_app.process_update(update_obj)
        logger.info("✅ Update procesado correctamente")

        return JSONResponse(content={"status": "ok"})

    except Exception as e:
        logger.error(f"❌ Error procesando el update: {e}", exc_info=True)
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

# Ruta de salud
@app.get("/")
def health():
    logger.info("🟢 Health check: OK")
    return {"status": "Bot activo", "timestamp": str(__import__('datetime').datetime.now())}
