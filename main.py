# main.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from services.database import init_db
import config

# Handlers modularizados
from handlers.lineas_handler import lineas_handlers, cargar_lineas
from handlers.paquetes_handler import paquetes_handlers, paquete_activo, calcular_expiracion, cargar_paquetes
from handlers.recargas_handler import recargas_handlers, ultima_recarga, puede_recargar, cargar_recargas
from services.utils import obtener_principal


# ----------------------------------------
# Inicialización de la base de datos
# ----------------------------------------
def setup():
    """Crea las tablas si no existen."""
    init_db()


# ----------------------------------------
# Verificación de admin
# ----------------------------------------
async def es_admin(update: Update):
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID:
        await update.message.reply_text("❌ No tienes permiso para usar este bot.")
        return False
    return True


# ----------------------------------------
# Comando /start
# ----------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler del comando /start"""
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


# ----------------------------------------
# Handler de botones generales
# ----------------------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "atras":
       # Volver al menú principal
       keyboard = [
           [InlineKeyboardButton("🔍 Consultar líneas", callback_data="consultar_lineas")],
           [InlineKeyboardButton("💳 Gestionar recargas", callback_data="gestionar_recargas")],
           [InlineKeyboardButton("📦 Gestionar paquetes", callback_data="gestionar_paquetes")],
           [InlineKeyboardButton("⚙️ Gestionar líneas", callback_data="gestionar_lineas")]
       ]
       reply_markup = InlineKeyboardMarkup(keyboard)
       await query.edit_message_text(
           text="👋 Hola, soy tu bot personal de gestión de líneas móviles.\nSelecciona una opción:",
           reply_markup=reply_markup
       )

# ----------------------------------------
# Exportar handlers modulares
# ----------------------------------------
__all__ = [
    "setup",
    "start",
    "button_handler",
    "lineas_handlers",
    "recargas_handlers",
    "paquetes_handlers",
]

