# modules/gestionar_lineas.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters
from database.connection import get_db_connection
from utils.auth import is_user_authorized

# Estados para el flujo de agregar línea (usaremos el contexto del usuario)
ESTADO_AGREGAR_NUMERO = "agregar_numero"
ESTADO_AGREGAR_ALIAS = "agregar_alias"
# Ya no usamos ESTADO_AGREGAR_SALDO

async def mostrar_menu_gestion_lineas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de gestión de líneas."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("👁️ Ver Líneas", callback_data='ver_lineas')],
        [InlineKeyboardButton("➕ Agregar Línea", callback_data='agregar_linea')],
        [InlineKeyboardButton("➖ Eliminar Línea", callback_data='eliminar_linea')],
        [InlineKeyboardButton("⬅️ Volver al inicio", callback_data='volver_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="📋 *Menú de Gestión de Líneas*\nElige una opción:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def ver_lineas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra todas las líneas del usuario."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT numero_linea, nombre_alias FROM lineas WHERE propietario_id = %s AND activa = TRUE", (user_id,))
    lineas = cur.fetchall()
    cur.close()
    conn.close()

    if not lineas:
        texto = "📭 No tienes líneas registradas aún."
    else:
        texto = "📱 *Tus Líneas Registradas:*\n\n"
        for linea in lineas:
            numero, alias = linea
            texto += f"▫️ *{alias or 'Sin alias'}* (`{numero}`)\n"

    keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='menu_gestion_lineas')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")

async def iniciar_agregar_linea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el flujo para agregar una línea."""
    query = update.callback_query
    await query.answer()

    # Guardamos en el contexto que el usuario está en modo "agregar"
    context.user_data['estado'] = ESTADO_AGREGAR_NUMERO

    await query.edit_message_text(
        text="📲 Por favor, envía el *número de la línea* (solo dígitos, sin espacios ni guiones):",
        parse_mode="Markdown"
    )

async def manejar_respuesta_agregar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja las respuestas durante el flujo de agregar línea."""
    user_id = update.effective_user.id
    texto = update.message.text.strip()

    estado = context.user_data.get('estado')

    if estado == ESTADO_AGREGAR_NUMERO:
        # Validar que sea solo dígitos
        if not texto.isdigit():
            await update.message.reply_text("❌ Por favor, envía solo números (sin espacios, guiones ni letras).")
            return

        context.user_data['numero_linea'] = texto
        context.user_data['estado'] = ESTADO_AGREGAR_ALIAS
        await update.message.reply_text(f"✅ Número guardado: {texto}\n\n✏️ Ahora envía un *alias* para esta línea (ej: 'Línea personal', 'Trabajo', etc.):", parse_mode="Markdown")

    elif estado == ESTADO_AGREGAR_ALIAS:
        alias = texto

        # Guardar en la base de datos (saldo por defecto = 0.00)
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO lineas (numero_linea, nombre_alias, saldo_actual, propietario_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (numero_linea) DO UPDATE
                SET nombre_alias = EXCLUDED.nombre_alias,
                    saldo_actual = EXCLUDED.saldo_actual,
                    activa = TRUE;
            """, (
                context.user_data['numero_linea'],
                alias,
                0.00,  # <-- saldo por defecto
                user_id
            ))
            conn.commit()
            mensaje = "✅ ¡Línea agregada correctamente!"
        except Exception as e:
            print(f"Error al guardar línea: {e}")
            mensaje = "❌ Hubo un error al guardar la línea. Inténtalo de nuevo."
        finally:
            cur.close()
            conn.close()

        # Limpiar el estado
        context.user_data.clear()

        # Mostrar mensaje de éxito y botón para volver
        keyboard = [[InlineKeyboardButton("⬅️ Volver al menú de líneas", callback_data='menu_gestion_lineas')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(mensaje, reply_markup=reply_markup)

async def eliminar_linea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra las líneas para que el usuario elija cuál eliminar."""
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
        texto = "📭 No tienes líneas para eliminar."
        keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='menu_gestion_lineas')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=texto, reply_markup=reply_markup)
        return

    texto = "🗑️ *Elige la línea que deseas eliminar:*\n"
    keyboard = []
    for linea in lineas:
        linea_id, numero, alias = linea
        nombre_mostrar = f"{alias or 'Sin alias'} ({numero})"
        keyboard.append([InlineKeyboardButton(nombre_mostrar, callback_data=f'confirmar_eliminar_{linea_id}')])

    keyboard.append([InlineKeyboardButton("⬅️ Volver", callback_data='menu_gestion_lineas')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")

async def confirmar_eliminar_linea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirma y elimina la línea seleccionada."""
    query = update.callback_query
    await query.answer()

    # Extraer el ID de la línea desde el callback_data
    linea_id = int(query.data.split('_')[-1])

    user_id = update.effective_user.id

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # "Eliminar" lógicamente (no borrar, solo marcar como inactiva)
        cur.execute("UPDATE lineas SET activa = FALSE WHERE id = %s AND propietario_id = %s", (linea_id, user_id))
        conn.commit()
        if cur.rowcount == 0:
            mensaje = "❌ No se pudo eliminar la línea (no existe o no te pertenece)."
        else:
            mensaje = "✅ Línea eliminada correctamente."
    except Exception as e:
        print(f"Error al eliminar línea: {e}")
        mensaje = "❌ Hubo un error al eliminar la línea."
    finally:
        cur.close()
        conn.close()

    keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='menu_gestion_lineas')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=mensaje, reply_markup=reply_markup)

async def volver_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vuelve al menú principal (/start)."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    # 🎨 Mensaje de bienvenida
    mensaje = (
        f"👋 ¡Hola {user.first_name}!\n\n"
        f"🌟 Bienvenido a tu asistente de gestión móvil.\n"
        f"Aquí podrás controlar todo lo relacionado con tus líneas, recargas y paquetes.\n\n"
        f"👇 Elige una opción para comenzar:"
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
    await query.edit_message_text(text=mensaje, reply_markup=reply_markup, parse_mode="Markdown")

async def volver_menu_gestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vuelve al menú de gestión de líneas."""
    await mostrar_menu_gestion_lineas(update, context)

def register_handlers(application):
    # Handlers para los callbacks del menú
    application.add_handler(CallbackQueryHandler(mostrar_menu_gestion_lineas, pattern='^gestionar_lineas$'))
    application.add_handler(CallbackQueryHandler(ver_lineas, pattern='^ver_lineas$'))
    application.add_handler(CallbackQueryHandler(iniciar_agregar_linea, pattern='^agregar_linea$'))
    application.add_handler(CallbackQueryHandler(eliminar_linea, pattern='^eliminar_linea$'))
    application.add_handler(CallbackQueryHandler(confirmar_eliminar_linea, pattern='^confirmar_eliminar_'))
    application.add_handler(CallbackQueryHandler(volver_start, pattern='^volver_start$'))
    application.add_handler(CallbackQueryHandler(volver_menu_gestion, pattern='^menu_gestion_lineas$'))

    # Handler para capturar respuestas durante el flujo de agregar línea
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_respuesta_agregar))