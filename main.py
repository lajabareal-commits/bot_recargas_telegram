# main.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from services.database import init_db
import config

# Handlers modularizados
from handlers.lineas_handler import lineas_handlers, obtener_principal, cargar_lineas
from handlers.paquetes_handler import paquetes_handlers, paquete_activo, calcular_expiracion, cargar_paquetes
from handlers.recargas_handler import recargas_handlers, ultima_recarga, puede_recargar, cargar_recargas


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

    if query.data == "consultar_lineas":
        lineas = cargar_lineas()
        principal = obtener_principal()
        recargas = cargar_recargas()
        paquetes = cargar_paquetes()

        if not lineas:
            await query.edit_message_text(
                text="❌ No tienes líneas registradas.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]])
            )
            return

        texto = "📌 **Estado de Líneas**\n\n"

        for linea in lineas:
            nombre = linea['nombre']
            numero = linea['numero']
            es_principal = linea.get("es_principal", False)

            texto += f"📱 *{nombre}* (`{numero}`)"
            if es_principal:
                texto += " ⭐\n"
            else:
                texto += "\n"

            # Recarga
            fecha_ult = ultima_recarga(numero)
            if fecha_ult:
                texto += f"• 💳 Última recarga: `{fecha_ult}`\n"
                if puede_recargar(numero):
                    texto += "• 🟢 Puedes recargar ahora\n"
                else:
                    dt_ult = datetime.fromisoformat(fecha_ult)
                    proxima = dt_ult + timedelta(days=30)
                    dias_faltan = (proxima - datetime.now()).days
                    texto += f"• 🔴 Quedan `{dias_faltan}` días para recargar\n"
            else:
                texto += "• 🆕 Sin recargas registradas\n"

            # Paquetes (solo principal)
            if es_principal:
                texto += "• 📦 Paquetes:\n"
                tiene_alguno = False
                for paquete in reversed(paquetes):
                    if paquete_activo(paquete):
                        exp = calcular_expiracion(paquete["fecha_compra"], paquete["duracion_dias"])
                        dias_restantes = (exp - datetime.now()).days
                        tipo = "4.5GB" if paquete["tipo"] == "datos_4_5gb" else "2GB+SMS"
                        texto += f"  - {tipo}: expira en `{dias_restantes}` días\n"
                        tiene_alguno = True
                if not tiene_alguno:
                    texto += "  - ❌ Sin paquetes activos\n"

            texto += "\n"

        await query.edit_message_text(
            text=texto,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]]),
            parse_mode="Markdown"
        )

    elif query.data == "gestionar_recargas":
        await query.edit_message_text(text="💳 Gestión de recargas (función en desarrollo).")

    elif query.data == "gestionar_paquetes":
        await query.edit_message_text(text="📦 Gestión de paquetes (función en desarrollo).")

    elif query.data == "gestionar_lineas":
        await query.edit_message_text(text="⚙️ Gestión de líneas (función en desarrollo).")


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

