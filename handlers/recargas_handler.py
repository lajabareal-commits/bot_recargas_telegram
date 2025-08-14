# handlers/recargas_handler.py

from services.database import get_db
from handlers.lineas_handler import cargar_lineas  # Reutilizamos
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

# --- Funciones de acceso a datos (PostgreSQL) ---

def cargar_recargas():
    """Obtiene todas las recargas de la base de datos."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT numero, fecha FROM recargas ORDER BY fecha DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def ultima_recarga(numero: str) -> str | None:
    """Devuelve la fecha de la última recarga de una línea."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT fecha FROM recargas WHERE numero = %s ORDER BY fecha DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row['fecha'].isoformat() if row else None
    except Exception as e:
        print(f"❌ Error al obtener última recarga para {numero}: {e}")
        return None

def dias_para_recargar(numero: str) -> int:
    """Devuelve cuántos días faltan para poder recargar (0 si ya puede)."""
    fecha_ult = ultima_recarga(numero)
    if not fecha_ult:
        return 0
    dt_ult = datetime.fromisoformat(fecha_ult).date()
    dias_transcurridos = (datetime.now().date() - dt_ult).days
    return max(0, 30 - dias_transcurridos)

def puede_recargar(numero: str) -> bool:
    """Verifica si puede recargarse (30 días desde la última)."""
    return dias_para_recargar(numero) == 0

def registrar_recarga_hoy(numero: str):
    """Registra una recarga con la fecha de hoy."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        hoy = datetime.now().date()
        cursor.execute("INSERT INTO recargas (numero, fecha) VALUES (%s, %s)", (numero, hoy))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Error al registrar recarga para {numero}: {e}")
        raise

# --- Handlers ---

# Menú principal de recargas
async def gestionar_recargas(update, context):
    query = update.callback_query
    await query.answer()

    lineas = cargar_lineas()
    if not lineas:
        await query.edit_message_text(
            text="❌ No hay líneas registradas.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]])
        )
        return

    keyboard = [
        [InlineKeyboardButton(f"📱 {l['nombre']} ({l['numero']})", callback_data=f"recarga_{l['numero']}")]
        for l in lineas
    ]
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="atras")])

    await query.edit_message_text(
        text="💳 **Gestión de Recargas**\n\nSelecciona una línea:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# Mostrar estado de recarga y opciones
async def mostrar_recarga(update, context):
    query = update.callback_query
    await query.answer()
    numero = query.data.replace("recarga_", "")

    lineas = cargar_lineas()
    linea = next((l for l in lineas if l["numero"] == numero), None)
    if not linea:
        await query.edit_message_text(
            text="❌ Línea no encontrada.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]])
        )
        return

    fecha_ult = ultima_recarga(numero)
    texto = f"📱 **{linea['nombre']}**\n`{numero}`\n\n"
    if fecha_ult:
        texto += f"📅 Última recarga: `{fecha_ult}`\n\n"
    else:
        texto += "🆕 Nunca se ha recargado.\n\n"

    dias_faltan = dias_para_recargar(numero)
    if dias_faltan == 0:
        keyboard = [
            [InlineKeyboardButton("✅ Recargar hoy", callback_data=f"rec_hoy_{numero}")],
            [InlineKeyboardButton("🔙 Volver", callback_data="atras")]
        ]
        texto += "🟢 Puedes recargar ahora."
    else:
        keyboard = [
            [InlineKeyboardButton("🔙 Volver", callback_data="atras")]
        ]
        texto += f"🔴 No puedes recargar aún.\n⏳ Faltan {dias_faltan} días para poder recargar."

    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# Guardar recarga con fecha de hoy
async def usar_hoy(update, context):
    query = update.callback_query
    await query.answer()
    numero = query.data.replace("rec_hoy_", "")

    try:
        registrar_recarga_hoy(numero)
        await query.edit_message_text(
            text=f"✅ Línea `{numero}` recargada con fecha de hoy.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]]),
            parse_mode="Markdown"
        )
    except Exception:
        await query.edit_message_text(
            text="❌ Error al registrar la recarga. Intenta de nuevo.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="atras")]])
        )

# --- Exportar handlers ---
recargas_handlers = [
    CallbackQueryHandler(gestionar_recargas, pattern="^gestionar_recargas$"),
    CallbackQueryHandler(mostrar_recarga, pattern="^recarga_\\d+$"),
    CallbackQueryHandler(usar_hoy, pattern="^rec_hoy_\\d+$"),
]