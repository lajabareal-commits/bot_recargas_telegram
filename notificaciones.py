# notificaciones.py
import logging
from telegram import Bot
from database.connection import get_db_connection
from datetime import date

from utils.limpieza_db import limpiar_recursos_viejos

logger = logging.getLogger(__name__)

async def enviar_mensaje(bot, chat_id, texto):
    """Envía un mensaje a un usuario de Telegram."""
    try:
        await bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
        logger.info(f"✅ Mensaje enviado a {chat_id}")
    except Exception as e:
        logger.error(f"❌ Error al enviar mensaje a {chat_id}: {e}")

async def obtener_recursos_por_vencer_o_vencidos(user_id, hoy):
    """Obtiene recursos (datos, minutos, SMS) por vencer o ya vencidos para un usuario."""
    conn = get_db_connection()
    cur = conn.cursor()

    recursos = {
        "por_vencer": {"datos": [], "minutos": [], "sms": []},
        "vencidos": {"datos": [], "minutos": [], "sms": []}
    }

    cur.execute("""
        SELECT rl.tipo_recurso, rl.cantidad, rl.fecha_vencimiento, l.numero_linea, l.nombre_alias
        FROM recursos_linea rl
        JOIN lineas l ON rl.linea_id = l.id
        WHERE l.propietario_id = %s AND rl.activo = TRUE
        ORDER BY rl.fecha_vencimiento ASC
    """, (user_id,))

    for tipo, cantidad, vence, numero, alias in cur.fetchall():
        dias_restantes = (vence - hoy).days
        nombre_linea = f"{alias or 'Sin alias'} ({numero})"

        logger.info(f"🔍 Recurso {tipo} en {nombre_linea}: vence={vence}, dias_restantes={dias_restantes}")

        if dias_restantes > 0 and dias_restantes <= 3:
            recursos["por_vencer"][tipo].append((cantidad, vence, dias_restantes, nombre_linea))
        elif dias_restantes <= 0:
            dias_vencido = abs(dias_restantes)
            recursos["vencidos"][tipo].append((cantidad, vence, dias_vencido, nombre_linea))

    cur.close()
    conn.close()
    return recursos

async def obtener_recargas_por_vencer_o_vencidas(user_id, hoy):
    """Obtiene recargas por vencer o ya vencidas para un usuario."""
    conn = get_db_connection()
    cur = conn.cursor()

    recargas = {"por_vencer": [], "vencidas": []}

    cur.execute("""
        SELECT numero_linea, nombre_alias, fecha_ultima_recarga
        FROM lineas
        WHERE propietario_id = %s AND activa = TRUE AND fecha_ultima_recarga IS NOT NULL
    """, (user_id,))

    for numero, alias, fecha_ultima in cur.fetchall():
        dias_pasados = (hoy - fecha_ultima).days
        dias_restantes = 30 - dias_pasados
        nombre_linea = f"{alias or 'Sin alias'} ({numero})"

        logger.info(f"🔍 Recarga en {nombre_linea}: fecha_ultima={fecha_ultima}, dias_pasados={dias_pasados}, dias_restantes={dias_restantes}")

        if dias_restantes > 0 and dias_restantes <= 3:
            recargas["por_vencer"].append((nombre_linea, dias_restantes))
        elif dias_restantes <= 0:
            dias_vencida = abs(dias_restantes)
            recargas["vencidas"].append((nombre_linea, dias_vencida))

    cur.close()
    conn.close()
    return recargas

async def enviar_notificaciones_programadas(bot):
    """Función principal: revisa fechas, limpia DB y envía notificaciones."""
    
    # 🧹 PASO 1: Limpiar recursos viejos (¡Nuevo!)
    await limpiar_recursos_viejos()

    # 📅 PASO 2: Revisar y enviar notificaciones (existente)
    hoy = date.today()

    # Obtener todos los usuarios con líneas activas
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT propietario_id FROM lineas WHERE activa = TRUE")
    usuarios = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()

    for user_id in usuarios:
        # Revisar recargas
        recargas = await obtener_recargas_por_vencer_o_vencidas(user_id, hoy)
        # Revisar recursos
        recursos = await obtener_recursos_por_vencer_o_vencidos(user_id, hoy)

        # Construir mensaje
        partes_mensaje = ["🔔 *NOTIFICACIÓN AUTOMÁTICA*\n"]

        # Recargas por vencer
        if recargas["por_vencer"]:
            partes_mensaje.append("⚠️ *Recargas Próximas a Vencer (30 días):*")
            for nombre_linea, dias in recargas["por_vencer"]:
                partes_mensaje.append(f"▫️ {nombre_linea} → {dias} días restantes")

        # Recargas vencidas
        if recargas["vencidas"]:
            partes_mensaje.append("\n❌ *Recargas Vencidas:*")
            for nombre_linea, dias in recargas["vencidas"]:
                partes_mensaje.append(f"▫️ {nombre_linea} → vencida hace {dias} días")

        # Recursos por vencer
        tipos = [("datos", "📊 *Datos (GB) Próximos a Vencer:*"), 
                 ("minutos", "⏱️ *Minutos Próximos a Vencer:*"), 
                 ("sms", "✉️ *SMS Próximos a Vencer:*")]

        for tipo, titulo in tipos:
            if recursos["por_vencer"][tipo]:
                partes_mensaje.append(f"\n{titulo}")
                for cantidad, vence, dias, nombre_linea in recursos["por_vencer"][tipo]:
                    partes_mensaje.append(f"▫️ {cantidad} {tipo} en {nombre_linea} → {dias} días (vence {vence.strftime('%d/%m')})")

        # Recursos vencidos
        tipos_vencidos = [("datos", "📉 *Datos (GB) Vencidos:*"), 
                          ("minutos", "📉 *Minutos Vencidos:*"), 
                          ("sms", "📉 *SMS Vencidos:*")]

        for tipo, titulo in tipos_vencidos:
            if recursos["vencidos"][tipo]:
                partes_mensaje.append(f"\n{titulo}")
                for cantidad, vence, dias, nombre_linea in recursos["vencidos"][tipo]:
                    partes_mensaje.append(f"▫️ {cantidad} {tipo} en {nombre_linea} → vencido hace {dias} días (venció {vence.strftime('%d/%m')})")

        # Enviar mensaje si hay algo que notificar
        if len(partes_mensaje) > 1:  # Más que solo el título
            partes_mensaje.append("\nRevisa todos los detalles con /start.")
            mensaje = "\n".join(partes_mensaje)
            await enviar_mensaje(bot, user_id, mensaje)
            logger.info(f"📩 Notificación enviada a usuario {user_id}")
        else:
            logger.info(f"📭 Usuario {user_id} no tiene recargas ni recursos por vencer o vencidos.")

    logger.info("✅ Revisión de notificaciones completada para todos los usuarios.")