# modules/gestionar_recargas.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters
from database.connection import get_db_connection
from datetime import date
import calendar

# Estados para el flujo de recarga
ESTADO_ELEGIR_LINEA = "elegir_linea_recarga"
ESTADO_ELEGIR_FECHA = "elegir_fecha_recarga"
ESTADO_INGRESAR_FECHA_MANUAL = "ingresar_fecha_manual"

async def mostrar_gestion_recargas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra directamente las próximas recargas + botones de acción."""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id

    # Obtener todas las líneas con recarga registrada
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT numero_linea, nombre_alias, fecha_ultima_recarga
        FROM lineas
        WHERE propietario_id = %s AND activa = TRUE AND fecha_ultima_recarga IS NOT NULL
        ORDER BY fecha_ultima_recarga ASC
    """, (user_id,))
    lineas_con_recarga = cur.fetchall()

    hoy = date.today()

    # Construir mensaje
    texto = "💳 *Gestión de Recargas*\n\n"

    if not lineas_con_recarga:
        texto += "📭 *No tienes líneas con recargas registradas.*\n"
    else:
        texto += "📅 *Próximas Recargas (cada 30 días):*\n\n"
        for numero, alias, fecha_ultima in lineas_con_recarga:
            dias_pasados = (hoy - fecha_ultima).days
            dias_restantes = 30 - dias_pasados
            nombre_linea = f"{alias or 'Sin alias'} ({numero})"

            if dias_restantes < 0:
                estado = f"❌ Vencida (hace {abs(dias_restantes)} días)"
            elif dias_restantes <= 3:
                estado = f"⚠️ Pronto ({dias_restantes} días)"
            else:
                estado = f"✅ Activa ({dias_restantes} días)"

            texto += (
                f"▫️ *{nombre_linea}*\n"
                f"   📅 Última: {fecha_ultima.strftime('%d/%m/%Y')}\n"
                f"   ⏳ Estado: {estado}\n\n"
            )

    # Botones: Registrar Recarga y Volver
    keyboard = [
        [InlineKeyboardButton("➕ Registrar Recarga", callback_data='registrar_recarga')],
        [InlineKeyboardButton("⬅️ Volver al inicio", callback_data='volver_start_recargas')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")

    cur.close()
    conn.close()

# ▼▼▼ REGISTRAR RECARGA ▼▼▼

async def registrar_recarga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el flujo para registrar una recarga: primero elige la línea."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, numero_linea, nombre_alias FROM lineas WHERE propietario_id = %s AND activa = TRUE", (user_id,))
    lineas = cur.fetchall()
    cur.close()
    conn.close()

    if not lineas:
        texto = "📭 No tienes líneas registradas. Registra una primero en 'Gestionar Líneas'."
        keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_recargas')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=texto, reply_markup=reply_markup)
        return

    texto = "📲 *Elige la línea a la que deseas registrar una recarga:*"
    keyboard = []
    for linea in lineas:
        linea_id, numero, alias = linea
        nombre_mostrar = f"{alias or 'Sin alias'} ({numero})"
        keyboard.append([InlineKeyboardButton(nombre_mostrar, callback_data=f'elegir_linea_{linea_id}')])

    keyboard.append([InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_recargas')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")

async def elegir_linea_para_recarga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guarda la línea elegida y muestra opciones de fecha."""
    query = update.callback_query
    await query.answer()

    linea_id = int(query.data.split('_')[-1])
    context.user_data['linea_id_recarga'] = linea_id

    keyboard = [
        [InlineKeyboardButton("✅ Usar fecha actual (hoy)", callback_data='fecha_actual')],
        [InlineKeyboardButton("📅 Seleccionar fecha con botones", callback_data='fecha_botones')],
        [InlineKeyboardButton("⬅️ Volver", callback_data='registrar_recarga')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="📆 *¿Qué fecha quieres registrar para la recarga?*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def usar_fecha_actual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Registra la recarga con la fecha de hoy."""
    query = update.callback_query
    await query.answer()

    linea_id = context.user_data.get('linea_id_recarga')
    if not linea_id:
        await query.edit_message_text("❌ Error: no se seleccionó una línea.")
        return

    hoy = date.today()

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE lineas SET fecha_ultima_recarga = %s WHERE id = %s", (hoy, linea_id))
        conn.commit()
        mensaje = f"✅ ¡Recarga registrada con fecha de hoy ({hoy.strftime('%d/%m/%Y')})!"
    except Exception as e:
        print(f"Error al registrar recarga: {e}")
        mensaje = "❌ Hubo un error al registrar la recarga."
    finally:
        cur.close()
        conn.close()

    keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_recargas')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=mensaje, reply_markup=reply_markup)

# ▼▼▼ SELECCIÓN DE FECHA CON BOTONES ▼▼▼

async def iniciar_seleccion_fecha_botones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 1: Elegir año."""
    query = update.callback_query
    await query.answer()

    año_actual = date.today().year
    años = [año_actual - 2, año_actual - 1, año_actual, año_actual + 1, año_actual + 2]

    keyboard = []
    for año in años:
        keyboard.append([InlineKeyboardButton(str(año), callback_data=f'sel_año_{año}')])

    keyboard.append([InlineKeyboardButton("⬅️ Cancelar", callback_data='cancelar_fecha')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="🗓️ *Paso 1 de 3: Elige el AÑO:*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def seleccionar_año(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 2: Guarda el año y muestra los meses."""
    query = update.callback_query
    await query.answer()

    año = int(query.data.split('_')[-1])
    context.user_data['año_seleccionado'] = año

    meses = [
        ("Enero", 1), ("Febrero", 2), ("Marzo", 3), ("Abril", 4),
        ("Mayo", 5), ("Junio", 6), ("Julio", 7), ("Agosto", 8),
        ("Septiembre", 9), ("Octubre", 10), ("Noviembre", 11), ("Diciembre", 12)
    ]

    keyboard = []
    for nombre, num in meses:
        keyboard.append([InlineKeyboardButton(nombre, callback_data=f'sel_mes_{num}')])

    keyboard.append([InlineKeyboardButton("⬅️ Cambiar año", callback_data='fecha_botones')])
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data='cancelar_fecha')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=f"🗓️ *Paso 2 de 3: Elige el MES (Año: {año}):*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def seleccionar_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 3: Guarda el mes y muestra los días válidos."""
    query = update.callback_query
    await query.answer()

    mes = int(query.data.split('_')[-1])
    año = context.user_data['año_seleccionado']
    context.user_data['mes_seleccionado'] = mes

    num_dias = calendar.monthrange(año, mes)[1]
    dias = list(range(1, num_dias + 1))

    keyboard = []
    fila = []
    for dia in dias:
        fila.append(InlineKeyboardButton(str(dia), callback_data=f'sel_dia_{dia}'))
        if len(fila) == 5:
            keyboard.append(fila)
            fila = []
    if fila:
        keyboard.append(fila)

    keyboard.append([InlineKeyboardButton("⬅️ Cambiar mes", callback_data=f'sel_año_{año}')])
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data='cancelar_fecha')])

    nombre_mes = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ][mes - 1]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=f"🗓️ *Paso 3 de 3: Elige el DÍA (Mes: {nombre_mes}, Año: {año}):*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def seleccionar_dia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 4: Guarda el día, forma la fecha y actualiza la DB."""
    query = update.callback_query
    await query.answer()

    dia = int(query.data.split('_')[-1])
    mes = context.user_data['mes_seleccionado']
    año = context.user_data['año_seleccionado']
    linea_id = context.user_data['linea_id_recarga']

    try:
        fecha_recarga = date(año, mes, dia)
    except ValueError:
        await query.edit_message_text("❌ Fecha inválida.")
        return

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE lineas SET fecha_ultima_recarga = %s WHERE id = %s", (fecha_recarga, linea_id))
        conn.commit()
        mensaje = f"✅ ¡Recarga registrada con fecha {fecha_recarga.strftime('%d/%m/%Y')}!"
    except Exception as e:
        print(f"Error al registrar recarga manual: {e}")
        mensaje = "❌ Hubo un error al registrar la recarga."
    finally:
        cur.close()
        conn.close()

    for key in ['año_seleccionado', 'mes_seleccionado', 'linea_id_recarga']:
        context.user_data.pop(key, None)

    keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_recargas')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=mensaje, reply_markup=reply_markup)

async def cancelar_seleccion_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la selección de fecha."""
    query = update.callback_query
    await query.answer()

    for key in ['año_seleccionado', 'mes_seleccionado', 'linea_id_recarga']:
        context.user_data.pop(key, None)

    await query.edit_message_text(
        text="❌ Selección cancelada.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Volver", callback_data='registrar_recarga')
        ]])
    )

# ▲▲▲ FIN SELECCIÓN DE FECHA ▲▲▲

# ▼▼▼ NAVEGACIÓN ▼▼▼

async def volver_start_recargas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vuelve al menú principal (/start)."""
    from modules.start import mostrar_menu_inicio
    await mostrar_menu_inicio(update, context)

# ▲▲▲ FIN NAVEGACIÓN ▲▲▲

def register_handlers(application):
    # Handler principal
    application.add_handler(CallbackQueryHandler(mostrar_gestion_recargas, pattern='^gestionar_recargas$'))

    # Registrar recarga
    application.add_handler(CallbackQueryHandler(registrar_recarga, pattern='^registrar_recarga$'))
    application.add_handler(CallbackQueryHandler(elegir_linea_para_recarga, pattern='^elegir_linea_\\d+$'))

    # Fechas
    application.add_handler(CallbackQueryHandler(usar_fecha_actual, pattern='^fecha_actual$'))
    application.add_handler(CallbackQueryHandler(iniciar_seleccion_fecha_botones, pattern='^fecha_botones$'))
    application.add_handler(CallbackQueryHandler(seleccionar_año, pattern='^sel_año_\\d+$'))
    application.add_handler(CallbackQueryHandler(seleccionar_mes, pattern='^sel_mes_\\d+$'))
    application.add_handler(CallbackQueryHandler(seleccionar_dia, pattern='^sel_dia_\\d+$'))
    application.add_handler(CallbackQueryHandler(cancelar_seleccion_fecha, pattern='^cancelar_fecha$'))

    # Volver
    application.add_handler(CallbackQueryHandler(volver_start_recargas, pattern='^volver_start_recargas$'))