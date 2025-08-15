# handlers/recargas_handler.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from datetime import datetime, timedelta
import logging
from services.database import get_db

logger = logging.getLogger(__name__)

# -------------------------------
# Funciones de recargas
# -------------------------------

def cargar_recargas():
    """Carga todas las recargas desde la DB."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, numero, fecha FROM recargas ORDER BY fecha DESC")
        recargas = cursor.fetchall()
        cursor.close()
        conn.close()
        return recargas
    except Exception as e:
        logger.error(f"❌ Error cargando recargas: {e}", exc_info=True)
        return []

def ultima_recarga(numero):
    """Devuelve la última fecha de recarga de un número, o None."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT fecha FROM recargas WHERE numero = %s ORDER BY fecha DESC LIMIT 1",
            (numero,)  # ⚠️ Debe ser una tupla
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return row[0].isoformat()  # Devuelve string ISO
        return None
    except Exception as e:
        logger.error(f"❌ Error al obtener última recarga para {numero}: {e}", exc_info=True)
        return None

def puede_recargar(numero):
    """Devuelve True si han pasado más de 30 días desde la última recarga."""
    fecha_ult = ultima_recarga(numero)
    if not fecha_ult:
        return True
    dt_ult = datetime.fromisoformat(fecha_ult)
    return (datetime.now() - dt_ult).days >= 30

def registrar_recarga(numero, fecha=None):
    """Registra una nueva recarga en la DB."""
    if fecha is None:
        fecha = datetime.now().date()
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO recargas (numero, fecha) VALUES (%s, %s)",
            (numero, fecha)
        )
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"✅ Recarga registrada para {numero} en {fecha}")
    except Exception as e:
        logger.error(f"❌ Error registrando recarga para {numero}: {e}", exc_info=True)

# -------------------------------
# Handlers de Telegram
# -------------------------------

# Aquí puedes agregar handlers específicos para comandos o callbacks relacionados con recargas
recargas_handlers = []

