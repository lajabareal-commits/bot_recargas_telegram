# notificaciones.py
import logging
from telegram import Bot
from database.connection import get_db_connection
from datetime import date, timedelta

logger = logging.getLogger(__name__)

async def enviar_mensaje(bot, chat_id, texto):
    """Envía un mensaje a un usuario de Telegram."""
    try:
        await bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
        logger.info(f"✅ Mensaje enviado a {chat_id}")
    except Exception as e:
        logger.error(f"❌ Error al enviar mensaje a {chat_id}: {e}")

async def obtener_recursos_por_vencer(user_id, hoy, umbral_dias=3):
    """Obtiene recursos (datos, minutos, SMS) por vencer para un usuario."""
    conn = get_db_connection()
    cur = conn.cursor()

    recursos_por_tipo = {"datos": [], "minutos": [], "sms": []}

    cur.execute("""
        SELECT rl.tipo_recurso, rl.cantidad, rl.fecha_vencimiento
        FROM recursos_linea rl
        JOIN lineas l ON rl.linea_id = l.id
        WHERE l.propietario_id = %s AND rl.activo = TRUE
          AND rl.fecha_vencimiento >= %s
          AND rl.fecha_vencimiento <= %s
        ORDER BY rl.fecha_vencimiento ASC
    """, (user_id, hoy, hoy + timedelta(days=umbral_dias)))

    for tipo, cantidad, vence in cur.fetchall():
        dias_restantes = (vence - hoy).days
        logger.info(f"🔍 Recurso {tipo}: cantidad={cantidad}, vence={vence}, dias_restantes={dias_restantes}")
        if 0 <= dias_restantes <= umbral_dias:
            recursos_por_tipo[tipo].append((cantidad, vence, dias_restantes))

    cur.close()
    conn.close()
    return recursos_por_tipo

async def obtener_recargas_por_vencer(user_id, hoy, umbral_dias=3):
    """Obtiene líneas con recargas por vencer o vencidas HOY para un usuario."""
    conn = get_db_connection()
    cur = conn.cursor()

    recargas = []
    cur.execute("""
        SELECT numero_linea, nombre_alias, fecha_ultima_recarga
        FROM lineas
        WHERE propietario_id = %s AND activa = TRUE AND fecha_ultima_recarga IS NOT NULL
    """, (user_id,))

    for numero, alias, fecha_ultima in cur.fetchall():
        dias_pasados = (hoy - fecha_ultima).days
        dias_restantes = 30 - dias_pasados
        logger.info(f"🔍 Línea {numero} ({alias}): fecha_ultima={fecha_ultima}, dias_pasados={dias_pasados}, dias_restantes={dias_restantes}")

        # Notificar si está por vencer (>=0) o venció hoy o ayer (>= -1)
        if dias_restantes <= umbral_dias and dias_restantes >= -1:
            recargas.append((alias or 'Sin alias', numero, dias_restantes))

    cur.close()
    conn.close()
    return recargas

async def enviar_notificaciones_programadas(bot):
    """Función principal: revisa fechas y envía notificaciones precisas."""
    hoy = date.today()
    umbral_dias = 3

    # Obtener todos los usuarios con líneas activas
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT propietario_id FROM lineas WHERE activa = TRUE")
    usuarios = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()

    for user_id in usuarios:
        # Revisar recargas
        recargas = await obtener_recargas_por_vencer(user_id, hoy, umbral_dias)
        # Revisar recursos
        recursos = await obtener_recursos_por_vencer(user_id, hoy, umbral_dias)

        # Construir mensaje solo si hay algo por vencer
        partes_mensaje = []

        if recargas:
            partes_mensaje.append("⚠️ *Recargas Próximas a Vencer:*")
            for alias, numero, dias in recargas:
                estado = "✅ Activo" if dias > 0 else "❌ Vencido hoy" if dias == 0 else "‼️ Vencido ayer"
                partes_mensaje.append(f"▫️ `{numero}` ({alias}) → {abs(dias)} días ({estado})")

        if recursos["datos"]:
            partes_mensaje.append("\n📊 *Datos (GB) Próximos a Vencer:*")
            for cantidad, vence, dias in recursos["datos"]:
                partes_mensaje.append(f"▫️ {cantidad} GB → {dias} días (vence {vence.strftime('%d/%m')})")

        if recursos["minutos"]:
            partes_mensaje.append("\n⏱️ *Minutos Próximos a Vencer:*")
            for cantidad, vence, dias in recursos["minutos"]:
                partes_mensaje.append(f"▫️ {cantidad} min → {dias} días (vence {vence.strftime('%d/%m')})")

        if recursos["sms"]:
            partes_mensaje.append("\n✉️ *SMS Próximos a Vencer:*")
            for cantidad, vence, dias in recursos["sms"]:
                partes_mensaje.append(f"▫️ {cantidad} SMS → {dias} días (vence {vence.strftime('%d/%m')})")

        if partes_mensaje:
            mensaje = (
                "🔔 *NOTIFICACIÓN AUTOMÁTICA*\n"
                "Estos son tus servicios próximos a vencer:\n\n"
                + "\n".join(partes_mensaje) +
                "\n\nRevisa detalles con /start."
            )
            await enviar_mensaje(bot, user_id, mensaje)
            logger.info(f"📩 Notificación enviada a usuario {user_id}")
        else:
            logger.info(f"📭 Usuario {user_id} no tiene nada por vencer.")

    logger.info("✅ Revisión de notificaciones completada para todos los usuarios.")