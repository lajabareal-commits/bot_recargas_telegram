# services/utils.py

from services.database import get_db
import logging

# Mueve aquí las funciones que son usadas por múltiples handlers

def obtener_principal():
    """Devuelve la línea principal, o None si no hay."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT numero, nombre FROM lineas WHERE es_principal = TRUE")
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"❌ Error obteniendo línea principal: {e}", exc_info=True)
        return None

logger = logging.getLogger(__name__)
# Puedes agregar más funciones compartidas aquí si es necesario
