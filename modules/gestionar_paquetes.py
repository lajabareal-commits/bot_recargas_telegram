# modules/gestionar_paquetes.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes
from database.connection import get_db_connection
from datetime import date

# Definición de paquetes (ID, Descripción, Precio)
PAQUETES = [
    (1, "2GB + 15min + 20 SMS", 120.0),
    (2, "4GB + 35min + 40 SMS", 240.0),
    (3, "6GB + 60min + 70 SMS", 360.0),
    (4, "4.5GB", 240.0),
    (5, "5min", 37.5),
    (6, "20 SMS", 15.0),
]

DIAS_VIGENCIA = 35

# Estados para selección de fecha
ESTADO_ELEGIR_AÑO_PAQUETE = "elegir_año_paquete"
ESTADO_ELEGIR_MES_PAQUETE = "elegir_mes_paquete"
ESTADO_ELEGIR_DIA_PAQUETE = "elegir_dia_paquete"

async def mostrar_gestion_paquetes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra directamente los recursos de la línea principal + botones de acción."""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id

    # Obtener línea principal
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, numero_linea, nombre_alias
        FROM lineas
        WHERE propietario_id = %s AND es_principal = TRUE AND activa = TRUE
    """, (user_id,))
    linea_principal = cur.fetchone()

    if not linea_principal:
        # Si no hay línea principal, mostrar mensaje y botón para seleccionar una
        texto = "⚠️ *No tienes una línea principal seleccionada.*\nPor favor, elige una línea para gestionar paquetes."
        keyboard = [
            [InlineKeyboardButton("📲 Seleccionar Línea Principal", callback_data='seleccionar_linea_principal')],
            [InlineKeyboardButton("⬅️ Volver al inicio", callback_data='volver_start_paquetes')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if query:
            await query.edit_message_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")
        cur.close()
        conn.close()
        return

    linea_id, numero, alias = linea_principal
    nombre_linea = f"{alias or 'Sin alias'} ({numero})"

    # Obtener recursos activos de la línea principal
    cur.execute("""
        SELECT tipo_recurso, cantidad, fecha_activacion, fecha_vencimiento, origen_paquete
        FROM recursos_linea
        WHERE linea_id = %s AND activo = TRUE
        ORDER BY tipo_recurso, fecha_vencimiento DESC
    """, (linea_id,))
    recursos = cur.fetchall()
    cur.close()
    conn.close()

    hoy = date.today()

    # Construir mensaje
    texto = f"📦 *Gestión de Paquetes*\n*Línea Principal:* {nombre_linea}\n\n"

    if not recursos:
        texto += "📭 *No tienes recursos activos en esta línea.*\n"
    else:
        texto += "📱 *Tus Recursos Activos:*\n\n"
        recursos_agrupados = {}

        for tipo, cantidad, activacion, vence, origen in recursos:
            if tipo not in recursos_agrupados:
                recursos_agrupados[tipo] = []
            recursos_agrupados[tipo].append((cantidad, activacion, vence, origen))

        for tipo, lista in recursos_agrupados.items():
            texto += f"*{tipo.upper()}*\n"
            for cantidad, activacion, vence, origen in lista:
                dias_restantes = (vence - hoy).days
                if dias_restantes < 0:
                    estado = f"❌ Vencido (hace {abs(dias_restantes)} días)"
                elif dias_restantes <= 3:
                    estado = f"⚠️ Pronto ({dias_restantes} días)"
                else:
                    estado = f"✅ Activo ({dias_restantes} días)"
                texto += (
                    f"▫️ {cantidad} {tipo} → {estado}\n"
                    f"   📅 Desde: {activacion.strftime('%d/%m/%Y')}\n"
                    f"   📆 Vence: {vence.strftime('%d/%m/%Y')}\n"
                    f"   ℹ️ Origen: {origen}\n\n"
                )

    # Botones: Comprar y Cambiar Línea en una fila, Volver en otra
    keyboard = [
        [
            InlineKeyboardButton("➕ Comprar Nuevo Paquete", callback_data='comprar_paquete'),
            InlineKeyboardButton("📲 Cambiar Línea Principal", callback_data='seleccionar_linea_principal')
        ],
        [
            InlineKeyboardButton("⬅️ Volver al inicio", callback_data='volver_start_paquetes')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")

# ▼▼▼ SELECCIÓN DE LÍNEA PRINCIPAL ▼▼▼

async def seleccionar_linea_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permite al usuario seleccionar una línea como principal."""
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
        keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_paquetes')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=texto, reply_markup=reply_markup)
        return

    texto = "📲 *Elige la línea que deseas marcar como PRINCIPAL:*"
    keyboard = []
    for linea in lineas:
        linea_id, numero, alias = linea
        nombre_mostrar = f"{alias or 'Sin alias'} ({numero})"
        keyboard.append([InlineKeyboardButton(nombre_mostrar, callback_data=f'set_principal_{linea_id}')])

    keyboard.append([InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_paquetes')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")

async def set_linea_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Marca una línea como principal (y desmarca otras)."""
    query = update.callback_query
    await query.answer()

    linea_id = int(query.data.split('_')[-1])
    user_id = update.effective_user.id

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE lineas SET es_principal = FALSE WHERE propietario_id = %s", (user_id,))
        cur.execute("UPDATE lineas SET es_principal = TRUE WHERE id = %s", (linea_id,))
        conn.commit()
        mensaje = "✅ ¡Línea marcada como principal!"
    except Exception as e:
        print(f"Error al marcar línea principal: {e}")
        mensaje = "❌ Error al establecer línea principal."
    finally:
        cur.close()
        conn.close()

    keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_paquetes')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=mensaje, reply_markup=reply_markup)

# ▲▲▲ FIN SELECCIÓN LÍNEA PRINCIPAL ▲▲▲

# ▼▼▼ COMPRA DE PAQUETE ▼▼▼

async def comprar_paquete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la lista de paquetes disponibles para comprar."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, numero_linea, nombre_alias FROM lineas WHERE propietario_id = %s AND es_principal = TRUE AND activa = TRUE", (user_id,))
    linea_principal = cur.fetchone()
    cur.close()
    conn.close()

    if not linea_principal:
        await query.edit_message_text(
            text="❌ No tienes una línea principal seleccionada. Elige una primero.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📲 Seleccionar Línea Principal", callback_data='seleccionar_linea_principal')
            ]])
        )
        return

    linea_id, numero, alias = linea_principal
    context.user_data['linea_id_paquete'] = linea_id

    texto = f"📦 *Línea Principal: {alias or 'Sin alias'} ({numero})*\n\n*Elige un paquete para comprar:*"
    keyboard = []
    for pid, desc, precio in PAQUETES:
        keyboard.append([InlineKeyboardButton(f"{desc} - ${precio}", callback_data=f'paquete_{pid}')])

    keyboard.append([InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_paquetes')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")

async def elegir_paquete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guarda el paquete elegido y muestra opciones de fecha."""
    query = update.callback_query
    await query.answer()

    paquete_id = int(query.data.split('_')[-1])
    paquete = next((p for p in PAQUETES if p[0] == paquete_id), None)

    if not paquete:
        await query.edit_message_text("❌ Paquete no encontrado.")
        return

    context.user_data['paquete_seleccionado'] = paquete  # (id, desc, precio)

    keyboard = [
        [InlineKeyboardButton("✅ Usar fecha actual (hoy)", callback_data='fecha_actual_paquete')],
        [InlineKeyboardButton("📅 Seleccionar fecha con botones", callback_data='fecha_botones_paquete')],
        [InlineKeyboardButton("⬅️ Volver", callback_data='comprar_paquete')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"📆 *Has elegido: {paquete[1]} - ${paquete[2]}*\n\n*¿Qué fecha de compra deseas registrar?*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ▼▼▼ REUTILIZAMOS LÓGICA DE FECHAS (con prefijos para paquetes) ▼▼▼

async def extraer_recursos_de_paquete(tipo_paquete: str) -> list:
    """Extrae recursos individuales (GB, min, SMS) de un paquete."""
    recursos = []
    tipo_lower = tipo_paquete.lower()

    if "gb" in tipo_lower:
        import re
        match_gb = re.search(r'(\d+\.?\d*)\s*gb', tipo_lower)
        if match_gb:
            recursos.append(('datos', float(match_gb.group(1))))

    if "min" in tipo_lower:
        match_min = re.search(r'(\d+\.?\d*)\s*min', tipo_lower)
        if match_min:
            recursos.append(('minutos', float(match_min.group(1))))

    if "sms" in tipo_lower:
        match_sms = re.search(r'(\d+\.?\d*)\s*sms', tipo_lower)
        if match_sms:
            recursos.append(('sms', float(match_sms.group(1))))

    return recursos

async def registrar_recursos(linea_id: int, recursos: list, fecha_compra: date, conn, tipo_paquete: str):
    """Registra o actualiza recursos individuales para una línea."""
    vencimiento = fecha_compra + timedelta(days=DIAS_VIGENCIA)
    cur = conn.cursor()

    try:
        for tipo, cantidad in recursos:
            cur.execute("""
                UPDATE recursos_linea
                SET activo = FALSE
                WHERE linea_id = %s AND tipo_recurso = %s AND activo = TRUE
            """, (linea_id, tipo))

            cur.execute("""
                INSERT INTO recursos_linea (linea_id, tipo_recurso, cantidad, fecha_activacion, fecha_vencimiento, origen_paquete)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (linea_id, tipo, cantidad, fecha_compra, vencimiento, tipo_paquete))

        conn.commit()
    except Exception as e:
        print(f"Error al registrar recursos: {e}")
        conn.rollback()
        raise e
    finally:
        cur.close()

async def usar_fecha_actual_paquete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Registra los recursos del paquete con fecha de hoy."""
    query = update.callback_query
    await query.answer()

    paquete = context.user_data.get('paquete_seleccionado')
    linea_id = context.user_data.get('linea_id_paquete')

    if not paquete or not linea_id:
        await query.edit_message_text("❌ Error: datos incompletos.")
        return

    hoy = date.today()
    recursos = await extraer_recursos_de_paquete(paquete[1])

    conn = get_db_connection()
    try:
        await registrar_recursos(linea_id, recursos, hoy, conn, paquete[1])
        mensaje = f"✅ ¡Recursos registrados!\nActivados desde: {hoy.strftime('%d/%m/%Y')}\nVigencia: 35 días."
    except Exception as e:
        print(f"Error al registrar recursos: {e}")
        mensaje = "❌ Error al registrar recursos."
    finally:
        conn.close()

    context.user_data.pop('paquete_seleccionado', None)
    context.user_data.pop('linea_id_paquete', None)

    keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_paquetes')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=mensaje, reply_markup=reply_markup)

async def iniciar_seleccion_fecha_botones_paquete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 1: Elegir año (para paquete)."""
    query = update.callback_query
    await query.answer()

    año_actual = date.today().year
    años = [año_actual - 2, año_actual - 1, año_actual, año_actual + 1, año_actual + 2]

    keyboard = []
    for año in años:
        keyboard.append([InlineKeyboardButton(str(año), callback_data=f'sel_año_paq_{año}')])

    keyboard.append([InlineKeyboardButton("⬅️ Cancelar", callback_data='cancelar_fecha_paquete')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="🗓️ *Paso 1 de 3: Elige el AÑO (para fecha de compra):*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def seleccionar_año_paquete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 2: Guarda el año y muestra los meses (para paquete)."""
    query = update.callback_query
    await query.answer()

    año = int(query.data.split('_')[-1])
    context.user_data['año_seleccionado_paq'] = año

    meses = [
        ("Enero", 1), ("Febrero", 2), ("Marzo", 3), ("Abril", 4),
        ("Mayo", 5), ("Junio", 6), ("Julio", 7), ("Agosto", 8),
        ("Septiembre", 9), ("Octubre", 10), ("Noviembre", 11), ("Diciembre", 12)
    ]

    keyboard = []
    for nombre, num in meses:
        keyboard.append([InlineKeyboardButton(nombre, callback_data=f'sel_mes_paq_{num}')])

    keyboard.append([InlineKeyboardButton("⬅️ Cambiar año", callback_data='fecha_botones_paquete')])
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data='cancelar_fecha_paquete')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=f"🗓️ *Paso 2 de 3: Elige el MES (Año: {año}):*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def seleccionar_mes_paquete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paso 3: Guarda el mes y muestra los días válidos (para paquete)."""
    query = update.callback_query
    await query.answer()

    mes = int(query.data.split('_')[-1])
    año = context.user_data['año_seleccionado_paq']
    context.user_data['mes_seleccionado_paq'] = mes

    import calendar
    num_dias = calendar.monthrange(año, mes)[1]
    dias = list(range(1, num_dias + 1))

    keyboard = []
    fila = []
    for dia in dias:
        fila.append(InlineKeyboardButton(str(dia), callback_data=f'sel_dia_paq_{dia}'))
        if len(fila) == 5:
            keyboard.append(fila)
            fila = []
    if fila:
        keyboard.append(fila)

    keyboard.append([InlineKeyboardButton("⬅️ Cambiar mes", callback_data=f'sel_año_paq_{año}')])
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data='cancelar_fecha_paquete')])

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

async def seleccionar_dia_paquete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Registra los recursos del paquete con fecha manual."""
    query = update.callback_query
    await query.answer()

    dia = int(query.data.split('_')[-1])
    mes = context.user_data['mes_seleccionado_paq']
    año = context.user_data['año_seleccionado_paq']
    paquete = context.user_data['paquete_seleccionado']
    linea_id = context.user_data['linea_id_paquete']

    try:
        fecha_compra = date(año, mes, dia)
    except ValueError:
        await query.edit_message_text("❌ Fecha inválida.")
        return

    recursos = await extraer_recursos_de_paquete(paquete[1])

    conn = get_db_connection()
    try:
        await registrar_recursos(linea_id, recursos, fecha_compra, conn, paquete[1])
        mensaje = f"✅ ¡Recursos registrados!\nActivados desde: {fecha_compra.strftime('%d/%m/%Y')}\nVigencia: 35 días."
    except Exception as e:
        print(f"Error al registrar recursos: {e}")
        mensaje = "❌ Error al registrar recursos."
    finally:
        conn.close()

    for key in ['año_seleccionado_paq', 'mes_seleccionado_paq', 'paquete_seleccionado', 'linea_id_paquete']:
        context.user_data.pop(key, None)

    keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_paquetes')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=mensaje, reply_markup=reply_markup)

async def cancelar_seleccion_fecha_paquete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la selección de fecha para paquete."""
    query = update.callback_query
    await query.answer()

    for key in ['año_seleccionado_paq', 'mes_seleccionado_paq', 'paquete_seleccionado', 'linea_id_paquete']:
        context.user_data.pop(key, None)

    await query.edit_message_text(
        text="❌ Selección cancelada.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Volver", callback_data='comprar_paquete')
        ]])
    )

# ▲▲▲ FIN LÓGICA DE FECHAS PARA PAQUETES ▲▲▲

# ▼▼▼ NAVEGACIÓN ▼▼▼

async def volver_start_paquetes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vuelve al menú principal (/start) con resumen actualizado."""
    from modules.start import mostrar_menu_inicio
    await mostrar_menu_inicio(update, context)

# ▲▲▲ FIN NAVEGACIÓN ▲▲▲

def register_handlers(application):
    # Handler principal
    application.add_handler(CallbackQueryHandler(mostrar_gestion_paquetes, pattern='^gestionar_paquetes$'))

    # Selección de línea principal
    application.add_handler(CallbackQueryHandler(seleccionar_linea_principal, pattern='^seleccionar_linea_principal$'))
    application.add_handler(CallbackQueryHandler(set_linea_principal, pattern='^set_principal_\\d+$'))

    # Comprar paquete
    application.add_handler(CallbackQueryHandler(comprar_paquete, pattern='^comprar_paquete$'))
    application.add_handler(CallbackQueryHandler(elegir_paquete, pattern='^paquete_\\d+$'))

    # Fechas
    application.add_handler(CallbackQueryHandler(usar_fecha_actual_paquete, pattern='^fecha_actual_paquete$'))
    application.add_handler(CallbackQueryHandler(iniciar_seleccion_fecha_botones_paquete, pattern='^fecha_botones_paquete$'))
    application.add_handler(CallbackQueryHandler(seleccionar_año_paquete, pattern='^sel_año_paq_\\d+$'))
    application.add_handler(CallbackQueryHandler(seleccionar_mes_paquete, pattern='^sel_mes_paq_\\d+$'))
    application.add_handler(CallbackQueryHandler(seleccionar_dia_paquete, pattern='^sel_dia_paq_\\d+$'))
    application.add_handler(CallbackQueryHandler(cancelar_seleccion_fecha_paquete, pattern='^cancelar_fecha_paquete$'))

    # Volver
    application.add_handler(CallbackQueryHandler(volver_start_paquetes, pattern='^volver_start_paquetes$'))