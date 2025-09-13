# bot/core.py
from telegram.ext import Application
from config import TELEGRAM_TOKEN
import importlib
import os

class TelegramBot:
    def __init__(self):
        # Crear la aplicación de Telegram
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        # Cargar todos los módulos
        self.load_modules()

    def load_modules(self):
        """Carga todos los módulos de la carpeta 'modules' que tengan la función 'register_handlers'."""
        modules_dir = os.path.join(os.path.dirname(__file__), '..', 'modules')
        for filename in os.listdir(modules_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_name = filename[:-3]  # Quita '.py'
                try:
                    module = importlib.import_module(f'modules.{module_name}')
                    if hasattr(module, 'register_handlers'):
                        module.register_handlers(self.application)
                        print(f"✅ Módulo cargado: {module_name}")
                except Exception as e:
                    print(f"❌ Error al cargar módulo {module_name}: {e}")

    def run(self):
        print("🚀 Bot iniciado y esperando actualizaciones...")
        # No ejecutamos run_polling() aquí — lo manejaremos desde Flask/FastAPI
        pass
