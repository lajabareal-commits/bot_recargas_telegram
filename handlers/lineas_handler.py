# handlers/lineas_handler.py

from services.database import get_db
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from datetime import datetime, timedelta
from handlers.recargas_handler import ultima_recarga, puede_recargar, cargar_recargas
from handlers.paquetes_handler import cargar_paquetes, paquete_activo, calcular_expiracion
import config
import logging

logger = logging.getLogger(__name__)

# -------------------------------
# Funciones de acceso a datos
# -------------------------------

def cargar_lineas():
    """Obtiene todas las líneas de la base de datos."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT numero, nombre, es_principal FROM lineas ORDER BY nombre")
        rows = cursor.fetchall()  # RealDictCursor devuelve diccionarios
        cursor.close()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"❌ Error cargando líneas: {e}", exc_info=True)
        return []

def guardar_linea(numero: str, nombre: str, es_principal: bool = False):
    """Guarda una nueva línea o actualiza si ya existe."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO lineas (numero, nombre, es_principal) VALUES (%s, %s, %s) "
            "ON CONFLICT (numero) DO UPDATE SET nombre = EXCLUDED.nombre",
            (numero, nombre, es_principal)
        )
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"✅ Línea {numero} guardada con nombre {nombre}")
    except Exception as e:
        logger.error(f"❌ Error guardando línea {numero}: {e}", exc_info=True)

def establecer_principal(numero: str):
    """Establece una línea como principal (y desmarca las demás)."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT numero FROM lineas WHERE numero = %s", (numero,))
        if cursor.fetchone() is None:
            cursor.close()
            conn.close()
            return False
        cursor.execute("UPDATE lineas SET es_principal = FALSE")
        cursor.execute("UPDATE lineas SET es_principal = TRUE WHERE numero = %s", (numero,))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"⭐ Línea {numero} establecida como principal")
        return True
    except Exception as e:
        logger.error(f"❌ Error estableciendo principal {numero}: {e}", exc_info=True)
        return False

def eliminar_linea_db(numero: str):
    """Elimina una línea por número."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM lineas WHERE numero = %s", (numero,))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"🗑️ Línea {numero} eliminada")
    except Exception as e:
        logger.error(f"❌ Error eliminando línea {numero}: {e}", exc_info=True)

def obtener_principal():
    """Devuelve la línea principal, o None si no hay."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT numero, nombre FROM lineas WHERE es_principal = TRUE")
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"❌ Error obteniendo línea principal: {e}", exc_info=True)
        return None

# -------------------------------
# Menús
# -------------------------------

def menu_principal_markup():
    keyboard = [
        [InlineKeyboardButton("🔍 Consultar líneas", callback_data="consultar_lineas")],
        [InlineKeyboardButton("💳 Gestionar recargas", callback_data="gestionar_recargas")],
        [InlineKeyboardButton("📦 Gestionar paquetes", callback_data="gestionar_paquetes")],
        [InlineKeyboardButton("⚙️ Gestionar líneas", callback_data="gestionar_lineas")]
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_gestion_markup():
    keyboard = [
        [InlineKeyboardButton("🗑️ Eliminar línea", callback_data="eliminar_linea")],
        [InlineKeyboardButton("➕ Agregar nueva", callback_data="agregar_linea")],
        [InlineKeyboardButton("🔙 Atrás", callback_data="atras")]
    ]
    return InlineKeyboardMarkup(keyboard)

# -------------------------------
# Handlers de Telegram
# -------------------------------

# ----------------------------------------
# Función: Mostrar estado de líneas
# ----------------------------------------
async def mostrar_estado_lineas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado detallado de todas las líneas, con recargas y paquetes."""
    query = update.callback_query

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

async def gestionar_lineas(update, context):
    query = update.callback_query
    await query.answer()

    lineas = cargar_lineas()
    texto = "🔧 **Gestión de Líneas**\n\n"
    if lineas:
        texto += "📱 Líneas registradas:\n"
        for linea in lineas:
            estrella = " ⭐" if linea.get("es_principal", False) else ""
            texto += f"• {linea['nombre']}: `{linea['numero']}`{estrella}\n"
        texto += "\n"
    else:
        texto += "❌ No tienes líneas registradas.\n\n"

    keyboard = []
    if lineas:
        keyboard.append([InlineKeyboardButton("🗑️ Eliminar línea", callback_data="eliminar_linea")])
        keyboard.append([InlineKeyboardButton("⭐ Establecer como principal", callback_data="elegir_principal")])
    keyboard.append([InlineKeyboardButton("➕ Agregar nueva", callback_data="agregar_linea")])
    keyboard.append([InlineKeyboardButton("🔙 Volver al inicio", callback_data="atras")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")

async def solicitar_nueva_linea(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="📞 Escribe el número de la nueva línea (solo dígitos):")
    context.user_data['esperando_linea'] = True
    context.user_data['esperando_nombre'] = False

async def recibir_linea(update, context):
    user_data = context.user_data

    if user_data.get('esperando_linea') and not user_data.get('esperando_nombre'):
        numero = update.message.text.strip()
        if not numero.isdigit():
            await update.message.reply_text("❌ Error: ingresa solo números.")
            return

        lineas = cargar_lineas()
        if numero in [l["numero"] for l in lineas]:
            await update.message.reply_text("⚠️ Esa línea ya está registrada.")
            return

        user_data['nuevo_numero'] = numero
        user_data['esperando_linea'] = False
        user_data['esperando_nombre'] = True

        await update.message.reply_text(
            f"✅ Número `{numero}` válido.\n\n📌 Ahora, escribe un nombre para esta línea:",
            parse_mode="Markdown"
        )
        return

    if user_data.get('esperando_nombre'):
        nombre = update.message.text.strip()
        if not nombre:
            await update.message.reply_text("❌ El nombre no puede estar vacío.")
            return

        numero = user_data['nuevo_numero']
        guardar_linea(numero, nombre)
        await update.message.reply_text(
            f"✅ Línea `{numero}` agregada con nombre *{nombre}*.",
            parse_mode="Markdown"
        )

        user_data.clear()
        await update.message.reply_text("¿Qué deseas hacer ahora?", reply_markup=menu_gestion_markup())
        return

async def eliminar_linea(update, context):
    query = update.callback_query
    await query.answer()

    lineas = cargar_lineas()
    if not lineas:
        await query.edit_message_text(
            text="❌ No hay líneas para eliminar.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Atrás", callback_data="atras")]])
        )
        return

    keyboard = [
        [InlineKeyboardButton(f"🗑️ {l['nombre']} ({l['numero']})", callback_data=f"eliminar_{l['numero']}")]
        for l in lineas
    ]
    keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data="atras")])

    await query.edit_message_text(
        text="❌ Selecciona la línea que deseas eliminar:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirmar_eliminar(update, context):
    query = update.callback_query
    await query.answer()

    numero = query.data.replace("eliminar_", "")
    eliminar_linea_db(numero)

    await query.edit_message_text(
        text=f"✅ Línea `{numero}` eliminada.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]]),
        parse_mode="Markdown"
    )

async def elegir_principal(update, context):
    query = update.callback_query
    await query.answer()

    lineas = cargar_lineas()
    if not lineas:
        await query.edit_message_text(
            text="❌ No hay líneas disponibles.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]])
        )
        return

    keyboard = [
        [InlineKeyboardButton(f"📞 {l['nombre']} ({l['numero']})", callback_data=f"principal_{l['numero']}")]
        for l in lineas
    ]
    keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data="atras")])

    await query.edit_message_text(
        text="⭐ Selecciona la línea que deseas establecer como **principal**:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def confirmar_principal(update, context):
    query = update.callback_query
    await query.answer()

    numero = query.data.replace("principal_", "")
    exito = establecer_principal(numero)

    if not exito:
        await query.edit_message_text(
            text="❌ Línea no encontrada.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]])
        )
        return

    lineas = cargar_lineas()
    nombre = next((l["nombre"] for l in lineas if l["numero"] == numero), numero)

    await query.edit_message_text(
        text=f"✅ Línea `{numero}` (*{nombre}*) ahora es la **principal**. ⭐",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]]),
        parse_mode="Markdown"
    )

async def volver_atras(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="👋 Hola, soy tu bot personal de gestión de líneas móviles.\nSelecciona una opción:",
        reply_markup=menu_principal_markup()
    )

# -------------------------------
# Exportar handlers
# -------------------------------

lineas_handlers = [
    CallbackQueryHandler(gestionar_lineas, pattern="^gestionar_lineas$"),
    CallbackQueryHandler(solicitar_nueva_linea, pattern="^agregar_linea$"),
    CallbackQueryHandler(eliminar_linea, pattern="^eliminar_linea$"),
    CallbackQueryHandler(confirmar_eliminar, pattern="^eliminar_\\d+$"),
    CallbackQueryHandler(elegir_principal, pattern="^elegir_principal$"),
    CallbackQueryHandler(confirmar_principal, pattern="^principal_\\d+$"),
    CallbackQueryHandler(volver_atras, pattern="^atras$"),
    CallbackQueryHandler(mostrar_estado_lineas, pattern="^consultar_lineas$"),
    MessageHandler(filters.TEXT & filters.User(user_id=config.ADMIN_ID), recibir_linea),
]

