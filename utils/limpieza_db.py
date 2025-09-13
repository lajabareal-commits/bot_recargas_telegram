# utils/limpieza_db.py
import logging
from database.connection import get_db_connection
from datetime import date, timedelta

logger = logging.getLogger(__name__)

async def limpiar_recursos_viejos():
    """Borra recursos de recursos_linea que vencieron hace más de 4 meses."""
    conn = get_db_connection()
    if not conn:
        logger.error("❌ No se pudo conectar a la base de datos para limpieza.")
        return

    try:
        cur = conn.cursor()

        # Calcular fecha límite: hoy - 4 meses (aproximado como 120 días)
        fecha_limite = date.today() - timedelta(days=120)

        # Contar registros que se van a borrar (para log)
        cur.execute("""
            SELECT COUNT(*) FROM recursos_linea
            WHERE fecha_vencimiento < %s AND activo = FALSE
        """, (fecha_limite,))
        count_before = cur.fetchone()[0]

        # Borrar recursos vencidos hace más de 4 meses
        cur.execute("""
            DELETE FROM recursos_linea
            WHERE fecha_vencimiento < %s AND activo = FALSE
        """, (fecha_limite,))
        conn.commit()

        logger.info(f"🧹 Limpieza de DB completada: {cur.rowcount} recursos eliminados (vencidos antes de {fecha_limite}).")
    except Exception as e:
        logger.error(f"❌ Error durante la limpieza de recursos viejos: {e}", exc_info=True)
        conn.rollback()
    finally:
        cur.close()
        conn.close()