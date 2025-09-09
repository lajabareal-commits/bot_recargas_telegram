# modules/consultar_lineas.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes
from database.connection import get_db_connection
from datetime import date

# Número de líneas por página (para navegación)
LINEAS_POR_PAGINA = 1  # Mostramos 1 línea a la vez para darle espacio y detalle

async def mostrar_consulta_lineas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de consulta de líneas, empezando por la principal."""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id

    # Obtener todas las líneas activas, poniendo la principal primero
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, numero_linea, nombre_alias, fecha_ultima_recarga, es_principal
        FROM lineas
        WHERE propietario_id = %s AND activa = TRUE
        ORDER BY es_principal DESC, id ASC  -- Principal primero, luego el resto
    """, (user_id,))
    lineas = cur.fetchall()
    cur.close()
    conn.close()

    if not lineas:
        texto = "📭 No tienes líneas registradas. Registra una en 'Gestionar Líneas'."
        keyboard = [[InlineKeyboardButton("⬅️ Volver al inicio", callback_data='volver_start_consulta')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            await query.edit_message_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")
        return

    # Guardar en contexto para navegación
    context.user_data['todas_lineas_consulta'] = lineas
    context.user_data['indice_linea_actual'] = 0

    await mostrar_linea_actual(update, context)

async def mostrar_linea_actual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la línea actual según el índice."""
    lineas = context.user_data.get('todas_lineas_consulta', [])
    indice = context.user_data.get('indice_linea_actual', 0)

    if not lineas or indice >= len(lineas):
        return

    linea_id, numero, alias, fecha_ultima_recarga, es_principal = lineas[indice]

    # Construir mensaje bonito
    titulo = f"📱 *{alias or 'Sin alias'}* (`{numero}`)"
    if es_principal:
        titulo += " ⭐"  # Emoji de estrella para línea principal

    # Obtener paquetes activos de esta línea
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT tipo_paquete, precio, fecha_compra, fecha_vencimiento
        FROM paquetes
        WHERE linea_id = %s AND activo = TRUE
        ORDER BY fecha_vencimiento DESC
    """, (linea_id,))
    paquetes = cur.fetchall()
    cur.close()
    conn.close()

    hoy = date.today()

    # Calcular estado de recarga
    estado_recarga = "❓ Sin recarga registrada"
    dias_para_recarga = None
    emoji_recarga = "⚪"

    if fecha_ultima_recarga:
        dias_pasados = (hoy - fecha_ultima_recarga).days
        dias_para_recarga = 30 - dias_pasados
        if dias_para_recarga <= 0:
            estado_recarga = f"❌ Vencida (hace {abs(dias_para_recarga)} días)"
            emoji_recarga = "❌"
        elif dias_para_recarga <= 3:
            estado_recarga = f"⚠️ Pronto ({dias_para_recarga} días)"
            emoji_recarga = "⚠️"
        else:
            estado_recarga = f"✅ Activa ({dias_para_recarga} días restantes)"
            emoji_recarga = "✅"

    # Construir sección de recarga
    recarga_texto = f"{emoji_recarga} *Recarga:* {estado_recarga}"
    if fecha_ultima_recarga:
        recarga_texto += f"\n   📅 Última: {fecha_ultima_recarga.strftime('%d/%m/%Y')}"

    # Construir sección de paquetes
    if paquetes:
        paquetes_texto = "📦 *Paquetes Activos:*\n"
        for tipo, precio, compra, vence in paquetes:
            dias_restantes = (vence - hoy).days
            if dias_restantes < 0:
                estado_paq = f"❌ Vencido (hace {abs(dias_restantes)} días)"
                emoji_paq = "❌"
            elif dias_restantes <= 3:
                estado_paq = f"⚠️ Pronto ({dias_restantes} días)"
                emoji_paq = "⚠️"
            else:
                estado_paq = f"✅ Activo ({dias_restantes} días)"
                emoji_paq = "✅"
            paquetes_texto += (
                f"\n▫️ {emoji_paq} *{tipo}* - ${precio}\n"
                f"   📅 Compra: {compra.strftime('%d/%m/%Y')}\n"
                f"   📆 Vence: {vence.strftime('%d/%m/%Y')} ({estado_paq})\n"
            )
    else:
        paquetes_texto = "📭 *No tiene paquetes activos.*"

    # Construir mensaje completo
    mensaje = (
        f"{titulo}\n"
        f"{'─' * 30}\n"
        f"{recarga_texto}\n"
        f"{'─' * 30}\n"
        f"{paquetes_texto}"
    )

    # Botones de navegación
    total = len(lineas)
    botones = []

    if total > 1:
        botones_fila = []
        if indice > 0:
            botones_fila.append(InlineKeyboardButton("◀️ Anterior", callback_data='linea_anterior'))
        botones_fila.append(InlineKeyboardButton(f"{indice + 1}/{total}", callback_data='nada'))  # Solo informativo
        if indice < total - 1:
            botones_fila.append(InlineKeyboardButton("Siguiente ▶️", callback_data='linea_siguiente'))
        botones.append(botones_fila)

    botones.append([InlineKeyboardButton("⬅️ Volver al inicio", callback_data='volver_start_consulta')])
    reply_markup = InlineKeyboardMarkup(botones)

    # Enviar o editar mensaje
    if update.callback_query:
        await update.callback_query.edit_message_text(text=mensaje, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text=mensaje, reply_markup=reply_markup, parse_mode="Markdown")

async def navegar_linea_anterior(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navega a la línea anterior."""
    query = update.callback_query
    await query.answer()

    indice_actual = context.user_data.get('indice_linea_actual', 0)
    if indice_actual > 0:
        context.user_data['indice_linea_actual'] = indice_actual - 1
        await mostrar_linea_actual(update, context)

async def navegar_linea_siguiente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navega a la línea siguiente."""
    query = update.callback_query
    await query.answer()

    indice_actual = context.user_data.get('indice_linea_actual', 0)
    total_lineas = len(context.user_data.get('todas_lineas_consulta', []))
    if indice_actual < total_lineas - 1:
        context.user_data['indice_linea_actual'] = indice_actual + 1
        await mostrar_linea_actual(update, context)

async def volver_start_consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vuelve al menú principal (/start)."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    mensaje = (
        f"👋 ¡Hola {user.first_name}!\n\n"
        f"🌟 Bienvenido a tu asistente de gestión móvil.\n"
        f"Aquí podrás controlar todo lo relacionado con tus líneas, recargas y paquetes.\n\n"
        f"👇 Elige una opción para comenzar:"
    )

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
    await query.edit_message_text(text=mensaje, reply_markup=reply_markup, parse_mode="Markdown")

def register_handlers(application):
    application.add_handler(CallbackQueryHandler(mostrar_consulta_lineas, pattern='^consultar_lineas$'))
    application.add_handler(CallbackQueryHandler(navegar_linea_anterior, pattern='^linea_anterior$'))
    application.add_handler(CallbackQueryHandler(navegar_linea_siguiente, pattern='^linea_siguiente$'))
    application.add_handler(CallbackQueryHandler(volver_start_consulta, pattern='^volver_start_consulta$'))