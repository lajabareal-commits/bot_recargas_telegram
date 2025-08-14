# bot_app.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import Application
import config
from handlers.lineas_handler import lineas_handlers
from handlers.recargas_handler import recargas_handlers
from handlers.paquetes_handler import paquetes_handlers

# Inicializar la app FastAPI
app = FastAPI()

# Inicializar el bot
bot_app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

# Registrar handlers
for handler in lineas_handlers:
    bot_app.add_handler(handler)
bot_app.add_handler(paquetes_handler)
for handler in recargas_handlers:
    bot_app.add_handler(handler)

# Ruta del webhook
@app.post(f"/webhook/{config.TELEGRAM_BOT_TOKEN}")
async def webhook(update: dict):
    try:
        await bot_app.initialize()
        await bot_app.process_update(Update.de_json(update, bot_app.bot))
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        print(f"Error procesando update: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

# Salud (opcional)
@app.get("/")
def health():
    return {"status": "Bot corriendo"}
