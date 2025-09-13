# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Lista de IDs de usuarios autorizados (puedes poner varios)
AUTHORIZED_USERS = list(map(int, os.getenv("ADMIN_ID", "").split(","))) if os.getenv("ADMIN_ID") else []

# Base de datos
DATABASE_URL = os.getenv("DATABASE_URL")

# Para Render (FastAPI)
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render lo inyecta automáticamente
