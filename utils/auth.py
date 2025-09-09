# utils/auth.py
from config import AUTHORIZED_USERS

def is_user_authorized(user_id: int) -> bool:
    """Verifica si el usuario está autorizado para usar el bot."""
    return user_id in AUTHORIZED_USERS