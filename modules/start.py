# modules/start.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes
from utils.auth import is_user_authorized
from database.connection import get_db_connection
from datetime import date

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # 🔐 Verificar si el usuario está autorizado
    if not is_user_authorized(user.id):
        await update.message.reply_text(
            "🚫 Lo siento, no tienes permiso para usar este bot.\n"
            "Contacta al administrador para obtener acceso."
        )
        return

    # 💾 Guardar o actualizar al usuario en la base de datos
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO usuarios (id, username, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name;
            """, (
                user.id,
                user.username,
                user.first_name,
                user.last_name
            ))
            conn.commit()
            cur.close()
        except Exception as e:
            print(f"❌ Error al guardar usuario: {e}")
        finally:
            conn.close()

    # 📊 Obtener datos para el panel de resumen
    resumen = await generar_panel_resumen(user.id)

    # 🎨 Mensaje de bienvenida + panel de resumen
    mensaje = (
        f"👋 ¡Hola {user.first_name}!\n\n"
        f"🌟 *PANEL DE RESUMEN GENERAL*\n"
        f"{resumen}\n\n"
        f"👇 Elige una opción para gestionar tu cuenta:"
    )

    # 🔘 Creamos los botones en dos filas
    keyboard = [
        [
            InlineKeyboardButton("📱 Consultar Líneas", callback_data='consultar_lineas'),
            InlineKeyboardButton("📋 Gestionar Líneas", callback_data='gestionar_lineas')
        ],
        [
            InlineKeyboardButton("💳 Gestionar Recargas", callback_data='gestionar_recargas'),
            InlineKeyboardButton("📦 Gestionar Paquetes", callback_data='gestionar_paquetes')
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(mensaje, reply_markup=reply_markup, parse_mode="Markdown")

async def generar_panel_resumen(user_id):
    """Genera un string con el panel de resumen para el usuario."""
    conn = get_db_connection()
    cur = conn.cursor()

    hoy = date.today()

    # 1. Obtener línea principal
    cur.execute("""
        SELECT numero_linea, nombre_alias
        FROM lineas
        WHERE propietario_id = %s AND es_principal = TRUE AND activa = TRUE
    """, (user_id,))
    principal = cur.fetchone()

    # 2. Obtener recargas próximas a vencer (<= 3 días)
    cur.execute("""
        SELECT l.numero_linea, l.nombre_alias, l.fecha_ultima_recarga
        FROM lineas l
        WHERE l.propietario_id = %s AND l.activa = TRUE AND l.fecha_ultima_recarga IS NOT NULL
    """, (user_id,))
    lineas_con_recarga = cur.fetchall()
    recargas_peligro = []
    sin_recarga = []

    for linea in lineas_con_recarga:
        numero, alias, fecha_ultima = linea
        dias_pasados = (hoy - fecha_ultima).days
        dias_restantes = 30 - dias_pasados
        if dias_restantes <= 3 and dias_restantes >= 0:
            recargas_peligro.append(f"{alias or 'Sin alias'} ({numero}) → {dias_restantes} días")
        elif dias_restantes < 0:
            recargas_peligro.append(f"{alias or 'Sin alias'} ({numero}) → Vencida ({abs(dias_restantes)} días)")

    # Líneas sin recarga registrada
    cur.execute("""
        SELECT numero_linea, nombre_alias
        FROM lineas
        WHERE propietario_id = %s AND activa = TRUE AND fecha_ultima_recarga IS NULL
    """, (user_id,))
    lineas_sin_recarga = cur.fetchall()
    for linea in lineas_sin_recarga:
        numero, alias = linea
        sin_recarga.append(f"{alias or 'Sin alias'} ({numero})")

    # 3. Obtener paquetes próximos a vencer (<= 3 días)
    cur.execute("""
        SELECT p.tipo_paquete, l.numero_linea, l.nombre_alias, p.fecha_vencimiento
        FROM paquetes p
        JOIN lineas l ON p.linea_id = l.id
        WHERE l.propietario_id = %s AND p.activo = TRUE
        ORDER BY p.fecha_vencimiento ASC
    """, (user_id,))
    paquetes = cur.fetchall()
    paquetes_peligro = []

    for tipo, numero, alias, vence in paquetes:
        dias_restantes = (vence - hoy).days
        if dias_restantes <= 3 and dias_restantes >= 0:
            paquetes_peligro.append(f"{tipo} en {alias or 'Sin alias'} ({numero}) → {dias_restantes} días")
        elif dias_restantes < 0:
            paquetes_peligro.append(f"{tipo} en {alias or 'Sin alias'} ({numero}) → Vencido ({abs(dias_restantes)} días)")

    # 4. Total de líneas activas
    cur.execute("SELECT COUNT(*) FROM lineas WHERE propietario_id = %s AND activa = TRUE", (user_id,))
    total_lineas = cur.fetchone()[0]

    cur.close()
    conn.close()

    # 🧩 Construir el panel de resumen
    lineas_resumen = []

    # Línea principal
    if principal:
        numero, alias = principal
        lineas_resumen.append(f"⭐ *Línea Principal:* {alias or 'Sin alias'} (`{numero}`)")
    else:
        lineas_resumen.append("⚠️ *Línea Principal:* No seleccionada")

    # Recargas en peligro
    if recargas_peligro:
        lineas_resumen.append(f"\n⚠️ *Recargas por vencer:*")
        for item in recargas_peligro:
            lineas_resumen.append(f"   ▫️ {item}")
    else:
        lineas_resumen.append(f"\n✅ *Recargas:* Todas al día")

    # Paquetes en peligro
    if paquetes_peligro:
        lineas_resumen.append(f"\n📦 *Paquetes por vencer:*")
        for item in paquetes_peligro:
            lineas_resumen.append(f"   ▫️ {item}")
    else:
        lineas_resumen.append(f"\n✅ *Paquetes:* Todos activos")

    # Líneas sin recarga
    if sin_recarga:
        lineas_resumen.append(f"\n❓ *Líneas sin recarga:*")
        for item in sin_recarga:
            lineas_resumen.append(f"   ▫️ {item}")

    # Total de líneas
    lineas_resumen.append(f"\n📊 *Total Líneas Activas:* {total_lineas}")

    return "\n".join(lineas_resumen)

def register_handlers(application):
    application.add_handler(CommandHandler("start", start))