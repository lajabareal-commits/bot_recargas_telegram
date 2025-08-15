# handlers/recargas_handler.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from datetime import datetime, timedelta
import logging
from services.database import get_db

logger = logging.getLogger(__name__)

# -------------------------------
# Funciones de acceso a datos
# -------------------------------

def cargar_recargas():
    """Carga todas las recargas desde la base de datos."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, numero, fecha::text FROM recargas ORDER BY fecha DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"❌ Error cargando recargas: {e}", exc_info=True)
        return []

def ultima_recarga(numero):
    """Devuelve la última fecha de recarga de un número, como string ISO, o None."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT fecha::text FROM recargas WHERE numero = %s ORDER BY fecha DESC LIMIT 1",
            (numero,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row and 'fecha' in row:
            return row['fecha']
        return None
    except Exception as e:
        logger.error(f"❌ Error al obtener última recarga para {numero}: {e}", exc_info=True)
        return None

def puede_recargar(numero):
    """Devuelve True si han pasado 30 días o más desde la última recarga."""
    fecha_str = ultima_recarga(numero)
    if not fecha_str:
        return True
    try:
        dt_ult = datetime.fromisoformat(fecha_str)
        return (datetime.now() - dt_ult).days >= 30
    except Exception as e:
        logger.error(f"❌ Error parseando fecha de última recarga para {numero}: {e}", exc_info=True)
        return True

def registrar_recarga(numero, fecha=None):
    """Registra una nueva recarga en la base de datos."""
    if fecha is None:
        fecha = datetime.now().date()
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO recargas (numero, fecha) VALUES (%s, %s)",
            (numero, fecha)
        )
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"✅ Recarga registrada para {numero} en {fecha}")
    except Exception as e:
        logger.error(f"❌ Error registrando recarga para {numero}: {e}", exc_info=True)

# -------------------------------
# Handlers de Telegram
# -------------------------------

async def gestionar_recargas(update, context):
    """Muestra resumen de recargas de la línea principal."""
    query = update.callback_query
    await query.answer()

    from handlers.lineas_handler import obtener_principal
    principal = obtener_principal()

    if not principal:
        texto = "⚠️ No hay una línea principal definida.\n"
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="atras")]]
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    texto = f"💳 **Gestión de Recargas**\n\n"
    texto += f"📱 Línea principal: *{principal['nombre']}* (`{principal['numero']}`)\n\n"

    recargas = cargar_recargas()
    recargas_linea = [r for r in recargas if r["numero"] == principal["numero"]]

    if recargas_linea:
        ultima = recargas_linea[0]["fecha"]
        texto += f"📅 Última recarga: `{ultima}`\n"
        permitido = puede_recargar(principal["numero"])
        estado = "✅ Puede recargar" if permitido else "⏳ Aún no puede recargar"
        texto += f"Estado: {estado}\n"
    else:
        texto += "❌ No hay recargas registradas.\n"

    keyboard = [
        [InlineKeyboardButton("➕ Registrar nueva recarga", callback_data="registrar_recarga")],
        [InlineKeyboardButton("🔙 Volver al inicio", callback_data="atras")]
    ]

    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def registrar_recarga_handler(update, context):
    """Registra una recarga para la línea principal."""
    query = update.callback_query
    await query.answer()

    from handlers.lineas_handler import obtener_principal
    principal = obtener_principal()
    if not principal:
        await query.edit_message_text(
            text="❌ No hay una línea principal definida.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]])
        )
        return

    if not puede_recargar(principal["numero"]):
        await query.edit_message_text(
            text="⏳ Aún no han pasado 30 días desde la última recarga.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]])
        )
        return

    registrar_recarga(principal["numero"])

    await query.edit_message_text(
        text=f"✅ Recarga registrada para *{principal['nombre']}* (`{principal['numero']}`).",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]]),
        parse_mode="Markdown"
    )

# -------------------------------
# Exportar handlers
# -------------------------------

recargas_handlers = [
    CallbackQueryHandler(gestionar_recargas, pattern="^gestionar_recargas$"),
    CallbackQueryHandler(registrar_recarga_handler, pattern="^registrar_recarga$"),
]

