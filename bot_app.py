# bot_app.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram.ext import Application
from telegram import Update
import config

# Importar handlers
from handlers.lineas_handler import lineas_handlers
from handlers.recargas_handler import recargas_handlers
from handlers.paquetes_handler import paquetes_handlers

# Inicializar FastAPI
app = FastAPI()

# ✅ Solución: Desactivar updater porque usamos webhooks
bot_app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).updater(None).build()

# Registrar handlers
for handler in lineas_handlers:
    bot_app.add_handler(handler)
for handler in recargas_handlers:
    bot_app.add_handler(handler)
for handler in paquetes_handlers:
    bot_app.add_handler(handler)  # Asegúrate de que paquetes_handler sea un handler

@app.post(f"/webhook/{config.TELEGRAM_BOT_TOKEN}")
async def webhook(update: dict):
    try:
        await bot_app.initialize()
        await bot_app.process_update(Update.de_json(update, bot_app.bot))
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        print(f"❌ Error: {e}")
        return JSONResponse(content={"status": "error"}, status_code=500)

@app.get("/")
def health():
    return {"status": "Bot activo"}
