# utils/recargas.py
from datetime import date

def calcular_estado_recarga(fecha_ultima_recarga, hoy=None):
    """
    Calcula el estado de una recarga según la nueva lógica:
    - Ciclo: 30 días.
    - Solo se puede recargar AL DÍA SIGUIENTE de vencido.
    - Hoy = fecha_ultima_recarga + 31 → es el primer día "por vencer".
    """
    if hoy is None:
        hoy = date.today()

    if not fecha_ultima_recarga:
        return {
            "estado": "❓ Sin recarga registrada",
            "dias_restantes": None,
            "emoji": "⚪"
        }

    dias_pasados = (hoy - fecha_ultima_recarga).days
    dias_restantes = 30 - dias_pasados

    # Nuevo: solo se considera "por vencer" o "vencida" a partir del día 31
    if dias_pasados < 30:
        estado = f"✅ Activa (queda {30 - dias_pasados} días)"
        emoji = "✅"
    elif dias_pasados == 30:
        estado = "⚠️ Vence hoy"
        emoji = "⚠️"
        dias_restantes = 0
    else:  # dias_pasados > 30
        estado = f"❌ Vencida (hace {dias_pasados - 30} días)"
        emoji = "❌"
        dias_restantes = - (dias_pasados - 30)

    return {
        "estado": estado,
        "dias_restantes": dias_restantes,
        "emoji": emoji
    }