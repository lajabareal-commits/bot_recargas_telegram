# handlers/paquetes_handler.py

from services.database import get_db
from handlers.lineas_handler import obtener_principal  # Reutilizamos la función
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
import logging

logger = logging.getLogger(__name__)

# Tipos de paquetes
PAQUETES = {
    "datos_4_5gb": {"nombre": "4.5 GB de datos", "precio": 240, "duracion": 35, "descripcion": "4.5 GB de datos por $240"},
    "combo_2gb_sms": {"nombre": "2GB + 15 min + 20 SMS", "precio": 120, "duracion": 35, "descripcion": "2GB datos, 15 min y 20 SMS por $120"}
}

# -------------------------------
# Funciones de acceso a datos
# -------------------------------

def cargar_paquetes():
    """Obtiene todos los paquetes de la base de datos."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT tipo, numero, fecha_compra::text FROM paquetes ORDER BY fecha_compra DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"❌ Error cargando paquetes: {e}", exc_info=True)
        return []

def eliminar_paquetes_tipo(numero, tipo):
    """Elimina paquetes anteriores del mismo tipo para esa línea."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM paquetes WHERE numero = %s AND tipo = %s", (numero, tipo))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"❌ Error eliminando paquetes tipo {tipo} para {numero}: {e}", exc_info=True)

def comprar_nuevo_paquete(tipo, numero):
    """Compra un nuevo paquete (elimina el anterior del mismo tipo y agrega uno nuevo)."""
    hoy = datetime.now().date()
    eliminar_paquetes_tipo(numero, tipo)
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO paquetes (tipo, numero, fecha_compra) VALUES (%s, %s, %s)",
            (tipo, numero, hoy)
        )
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"✅ Paquete {tipo} registrado para {numero}")
    except Exception as e:
        logger.error(f"❌ Error comprando paquete {tipo} para {numero}: {e}", exc_info=True)

# Calcular expiración
def calcular_expiracion(fecha_compra_str, duracion_dias):
    fecha_compra = datetime.strptime(fecha_compra_str, "%Y-%m-%d")
    return fecha_compra + timedelta(days=duracion_dias)

# Verificar si el paquete está activo
def paquete_activo(paquete):
    exp = calcular_expiracion(paquete["fecha_compra"], 35)  # Todos duran 35 días
    return datetime.now().date() <= exp.date()

# -------------------------------
# Handlers de Telegram
# -------------------------------

async def gestionar_paquetes(update, context):
    query = update.callback_query
    await query.answer()
    paquetes = cargar_paquetes()
    principal = obtener_principal()

    texto = "📦 **Gestión de Paquetes**\n\n"

    if not principal:
        texto += "⚠️ No hay una línea principal definida.\n"
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="atras")]]
        await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    texto += f"📱 Línea principal: *{principal['nombre']}* (`{principal['numero']}`)\n\n"

    for tipo, info in PAQUETES.items():
        activo = None
        for p in paquetes:
            if p["tipo"] == tipo and paquete_activo(p):
                activo = p
                break
        if activo:
            exp = calcular_expiracion(activo["fecha_compra"], 35)
            dias_restantes = (exp - datetime.now()).days
            texto += f"✅ *{info['nombre']}*\n• Comprado: `{activo['fecha_compra']}`\n• Expira: `{exp.strftime('%Y-%m-%d')}` ({dias_restantes} días)\n\n"
        else:
            texto += f"❌ *{info['nombre']}*: No activo\n"

    keyboard = [
        [InlineKeyboardButton("🛒 Comprar 4.5GB ($240)", callback_data="comprar_datos_4_5gb")],
        [InlineKeyboardButton("🛒 Comprar 2GB+SMS ($120)", callback_data="comprar_combo_2gb_sms")],
        [InlineKeyboardButton("🔙 Volver al inicio", callback_data="atras")]
    ]

    await query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def comprar_paquete(update, context):
    query = update.callback_query
    await query.answer()
    tipo = query.data.replace("comprar_", "")

    if tipo not in PAQUETES:
        await query.edit_message_text(
            text="❌ Tipo de paquete no válido.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]])
        )
        return

    principal = obtener_principal()
    if not principal:
        await query.edit_message_text(
            text="❌ No puedes comprar: no hay una línea principal definida.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]])
        )
        return

    info = PAQUETES[tipo]
    comprar_nuevo_paquete(tipo, principal["numero"])

    await query.edit_message_text(
        text=f"✅ Paquete *{info['nombre']}* comprado para `{principal['nombre']}`.\n📅 Fecha: `{datetime.now().strftime('%Y-%m-%d')}`\n💸 Precio: ${info['precio']}\n⏳ Vigencia: {info['duracion']} días",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]]),
        parse_mode="Markdown"
    )

# Exportar handlers
paquetes_handlers = [
    CallbackQueryHandler(gestionar_paquetes, pattern="^gestionar_paquetes$"),
    CallbackQueryHandler(comprar_paquete, pattern="^comprar_(datos_4_5gb|combo_2gb_sms)$"),
]

