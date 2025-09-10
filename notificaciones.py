# notificaciones.py
import asyncio
import logging
import time
from telegram import Bot
from database.connection import get_db_connection
from datetime import date, timedelta
import os
from config import TELEGRAM_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def enviar_mensaje(bot, chat_id, texto):
    try:
        await bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
        logger.info(f"✅ Mensaje enviado a {chat_id}")
    except Exception as e:
        logger.error(f"❌ Error al enviar mensaje a {chat_id}: {e}")

async def verificar_y_notificar(bot):
    bot = Bot(token=TELEGRAM_TOKEN)
    hoy = date.today()
    umbral_dias = 3

    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Notificar por recargas próximas a vencer
    cur.execute("""
        SELECT DISTINCT l.propietario_id
        FROM lineas l
        WHERE l.activa = TRUE
          AND l.fecha_ultima_recarga IS NOT NULL
          AND (CURRENT_DATE - l.fecha_ultima_recarga) >= (30 - %s)
          AND (CURRENT_DATE - l.fecha_ultima_recarga) < 30
    """, (umbral_dias,))
    usuarios_recarga = cur.fetchall()

    for (user_id,) in usuarios_recarga:
        mensaje = (
            "⚠️ *Recordatorio de Recarga*\n"
            f"Tienes líneas próximas a vencer en los próximos {umbral_dias} días.\n"
            "Revisa tu panel con /start."
        )
        await enviar_mensaje(bot, user_id, mensaje)

    # 2. Notificar por recursos próximos a vencer
    cur.execute("""
        SELECT DISTINCT l.propietario_id
        FROM recursos_linea rl
        JOIN lineas l ON rl.linea_id = l.id
        WHERE rl.activo = TRUE
          AND rl.fecha_vencimiento >= CURRENT_DATE
          AND rl.fecha_vencimiento <= CURRENT_DATE + INTERVAL '%s days'
    """, (umbral_dias,))
    usuarios_recursos = cur.fetchall()

    for (user_id,) in usuarios_recursos:
        mensaje = (
            "📦 *Recordatorio de Recursos*\n"
            f"Tienes minutos, SMS o datos próximos a vencer en los próximos {umbral_dias} días.\n"
            "Revisa tu panel con /start."
        )
        await enviar_mensaje(bot, user_id, mensaje)

    cur.close()
    conn.close()
    logger.info("🔔 Verificación de notificaciones completada.")

async def main():
    while True:
        logger.info("⏰ Ejecutando ciclo de notificaciones...")
        await verificar_y_notificar()
        # Dormir 24 horas (86400 segundos)
        logger.info("😴 Durmiendo 24 horas hasta la próxima verificación...")
        time.sleep(86400)  # 24 * 60 * 60

if __name__ == "__main__":
    asyncio.run(main())
