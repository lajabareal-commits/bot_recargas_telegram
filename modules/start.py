# modules/start.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes
from utils.auth import is_user_authorized
from utils.recargas import calcular_estado_recarga
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

    # 📊 Generar y mostrar el menú de inicio con resumen detallado
    await mostrar_menu_inicio(update, context)

async def mostrar_menu_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera y muestra el menú principal con panel de resumen detallado."""
    user = update.effective_user

    # 📊 Obtener datos para el panel de resumen
    resumen = await generar_panel_resumen_detallado(user.id)

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

    if update.message:  # Si viene de /start
        await update.message.reply_text(mensaje, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:  # Si viene de un botón "Volver"
        query = update.callback_query
        await query.answer()
        # Añadimos \u200b para evitar "Message is not modified"
        await query.edit_message_text(text=mensaje + "\u200b", reply_markup=reply_markup, parse_mode="Markdown")

async def generar_panel_resumen_detallado(user_id):
    """Genera un string con el panel de resumen detallado para el usuario."""
    conn = get_db_connection()
    cur = conn.cursor()
    hoy = date.today()

    # Obtener todas las líneas activas, poniendo la principal primero
    cur.execute("""
        SELECT id, numero_linea, nombre_alias, fecha_ultima_recarga, es_principal
        FROM lineas
        WHERE propietario_id = %s AND activa = TRUE
        ORDER BY es_principal DESC, id ASC
    """, (user_id,))
    lineas = cur.fetchall()

    if not lineas:
        cur.close()
        conn.close()
        return "📭 *No tienes líneas registradas aún.*"

    partes_resumen = []

    for linea_id, numero, alias, fecha_ultima_recarga, es_principal in lineas:
        nombre_linea = f"{alias or 'Sin alias'} ({numero})"
        if es_principal:
            nombre_linea += " ⭐"

        partes_resumen.append(f"\n📱 *{nombre_linea}*")

        # Estado de recarga
        if fecha_ultima_recarga:
            estado_info = calcular_estado_recarga(fecha_ultima_recarga, hoy)
            estado_recarga = estado_info["estado"]
            partes_resumen.append(f"   🔋 Recarga: {estado_recarga} (última: {fecha_ultima_recarga.strftime('%d/%m')})")
        else:
            partes_resumen.append("   ❓ Sin recarga registrada")

        # Recursos activos
        cur.execute("""
            SELECT tipo_recurso, cantidad, fecha_vencimiento, origen_paquete
            FROM recursos_linea
            WHERE linea_id = %s AND activo = TRUE
            ORDER BY tipo_recurso, fecha_vencimiento ASC
        """, (linea_id,))
        recursos = cur.fetchall()

        if recursos:
            for tipo, cantidad, vence, origen in recursos:
                dias_restantes = (vence - hoy).days
                if dias_restantes < 0:
                    estado = f"❌ Vencido (hace {abs(dias_restantes)} días)"
                elif dias_restantes <= 3:
                    estado = f"⚠️ Pronto ({dias_restantes} días)"
                else:
                    estado = f"✅ Activo ({dias_restantes} días)"
                partes_resumen.append(f"   📦 {cantidad} {tipo} → {estado} (vence {vence.strftime('%d/%m')})")
        else:
            partes_resumen.append("   📭 Sin recursos activos")

    cur.close()
    conn.close()

    return "\n".join(partes_resumen)

def register_handlers(application):
    application.add_handler(CommandHandler("start", start))