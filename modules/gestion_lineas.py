# modules/gestionar_lineas.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters
from database.connection import get_db_connection
from utils.auth import is_user_authorized
from datetime import date, timedelta

# Estados para el flujo de agregar línea
ESTADO_AGREGAR_NUMERO = "agregar_numero"
ESTADO_AGREGAR_ALIAS = "agregar_alias"

async def limpiar_lineas_antiguas():
    """Elimina permanentemente líneas inactivas con más de 7 días de inactividad + sus recursos."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()

        # Obtener líneas inactivas con más de 7 días
        cur.execute("""
            SELECT id
            FROM lineas
            WHERE activa = FALSE AND fecha_registro <= %s
        """, (date.today() - timedelta(days=7),))
        lineas_a_borrar = cur.fetchall()

        for (linea_id,) in lineas_a_borrar:
            # Primero borrar recursos asociados
            cur.execute("DELETE FROM recursos_linea WHERE linea_id = %s", (linea_id,))
            # Luego borrar la línea
            cur.execute("DELETE FROM lineas WHERE id = %s", (linea_id,))
            print(f"🧹 Línea {linea_id} y sus recursos eliminados permanentemente por antigüedad.")

        conn.commit()
        if lineas_a_borrar:
            print(f"✅ Limpieza automática completada: {len(lineas_a_borrar)} líneas eliminadas.")
    except Exception as e:
        print(f"❌ Error en limpieza automática: {e}")
    finally:
        cur.close()
        conn.close()

async def mostrar_gestion_lineas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra directamente las líneas registradas + botones de acción."""
    query = update.callback_query
    if query:
        await query.answer()

    # Ejecutar limpieza automática al cargar el módulo
    await limpiar_lineas_antiguas()

    user_id = update.effective_user.id

    # Obtener todas las líneas activas del usuario
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, numero_linea, nombre_alias FROM lineas WHERE propietario_id = %s AND activa = TRUE", (user_id,))
    lineas = cur.fetchall()
    cur.close()
    conn.close()

    # Construir mensaje con la lista de líneas
    if not lineas:
        texto = "📭 *No tienes líneas registradas aún.*"
    else:
        texto = "📱 *Tus Líneas Registradas:*\n\n"
        for linea_id, numero, alias in lineas:
            texto += f"▫️ *{alias or 'Sin alias'}* (`{numero}`) — ID: `{linea_id}`\n"

    # Crear botones: Agregar y Eliminar en una fila, Volver en otra
    keyboard = [
        [
            InlineKeyboardButton("➕ Agregar Línea", callback_data='iniciar_agregar_linea'),
            InlineKeyboardButton("➖ Eliminar Línea", callback_data='eliminar_linea')
        ],
        [
            InlineKeyboardButton("⬅️ Volver al inicio", callback_data='volver_start')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")

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

        # Guardar en la base de datos
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
                0.00,
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
        keyboard = [[InlineKeyboardButton("⬅️ Volver al menú de líneas", callback_data='gestionar_lineas')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(mensaje, reply_markup=reply_markup)

async def eliminar_linea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra las líneas para que el usuario elija cuál eliminar (lógicamente o permanentemente)."""
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
        keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_lineas')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=texto, reply_markup=reply_markup)
        return

    texto = "🗑️ *Elige la línea que deseas eliminar:*\n"
    keyboard = []
    for linea in lineas:
        linea_id, numero, alias = linea
        nombre_mostrar = f"{alias or 'Sin alias'} ({numero})"
        keyboard.append([InlineKeyboardButton(nombre_mostrar, callback_data=f'confirmar_eliminar_{linea_id}')])

    keyboard.append([InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_lineas')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=texto, reply_markup=reply_markup, parse_mode="Markdown")

async def confirmar_eliminar_linea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra opciones: eliminar lógicamente o permanentemente."""
    query = update.callback_query
    await query.answer()

    linea_id = int(query.data.split('_')[-1])
    context.user_data['linea_id_a_eliminar'] = linea_id

    keyboard = [
        [InlineKeyboardButton("🗑️ Eliminar Lógicamente", callback_data='eliminar_logico')],
        [InlineKeyboardButton("💀 Eliminar Permanentemente", callback_data='eliminar_permanente')],
        [InlineKeyboardButton("⬅️ Cancelar", callback_data='gestionar_lineas')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="⚠️ *Elige tipo de eliminación:*\n- *Lógicamente:* se oculta, se borra en 7 días.\n- *Permanentemente:* se borra ahora, con todos sus recursos.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def eliminar_logico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Marca la línea como inactiva (borrado lógico)."""
    query = update.callback_query
    await query.answer()

    linea_id = context.user_data.get('linea_id_a_eliminar')
    if not linea_id:
        await query.edit_message_text("❌ Error: no se seleccionó una línea.")
        return

    user_id = update.effective_user.id

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE lineas SET activa = FALSE WHERE id = %s AND propietario_id = %s", (linea_id, user_id))
        conn.commit()
        if cur.rowcount == 0:
            mensaje = "❌ No se pudo eliminar la línea (no existe o no te pertenece)."
        else:
            mensaje = "✅ Línea marcada como inactiva. Se eliminará permanentemente en 7 días."
    except Exception as e:
        print(f"Error al eliminar lógicamente: {e}")
        mensaje = "❌ Hubo un error al eliminar la línea."
    finally:
        cur.close()
        conn.close()

    keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_lineas')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=mensaje, reply_markup=reply_markup)

async def eliminar_permanente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Borra la línea y todos sus recursos permanentemente."""
    query = update.callback_query
    await query.answer()

    linea_id = context.user_data.get('linea_id_a_eliminar')
    if not linea_id:
        await query.edit_message_text("❌ Error: no se seleccionó una línea.")
        return

    user_id = update.effective_user.id

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Primero borrar recursos asociados
        cur.execute("DELETE FROM recursos_linea WHERE linea_id = %s", (linea_id,))
        # Luego borrar la línea
        cur.execute("DELETE FROM lineas WHERE id = %s AND propietario_id = %s", (linea_id, user_id))
        conn.commit()
        if cur.rowcount == 0:
            mensaje = "❌ No se pudo eliminar la línea (no existe o no te pertenece)."
        else:
            mensaje = "💀✅ ¡Línea y todos sus recursos BORRADOS permanentemente!"
    except Exception as e:
        print(f"Error al eliminar permanentemente: {e}")
        mensaje = "❌ Hubo un error al eliminar la línea."
    finally:
        cur.close()
        conn.close()

    keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data='gestionar_lineas')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=mensaje, reply_markup=reply_markup)

async def volver_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vuelve al menú principal (/start)."""
    from modules.start import mostrar_menu_inicio
    await mostrar_menu_inicio(update, context)

def register_handlers(application):
    # Handler principal
    application.add_handler(CallbackQueryHandler(mostrar_gestion_lineas, pattern='^gestionar_lineas$'))

    # Handlers para agregar línea
    application.add_handler(CallbackQueryHandler(iniciar_agregar_linea, pattern='^iniciar_agregar_linea$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_respuesta_agregar))

    # Handlers para eliminar línea
    application.add_handler(CallbackQueryHandler(eliminar_linea, pattern='^eliminar_linea$'))
    application.add_handler(CallbackQueryHandler(confirmar_eliminar_linea, pattern='^confirmar_eliminar_\\d+$'))
    application.add_handler(CallbackQueryHandler(eliminar_logico, pattern='^eliminar_logico$'))
    application.add_handler(CallbackQueryHandler(eliminar_permanente, pattern='^eliminar_permanente$'))

    # Handler para volver
    application.add_handler(CallbackQueryHandler(volver_start, pattern='^volver_start$'))