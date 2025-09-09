# bot/core.py
from telegram.ext import Application
from config import TELEGRAM_TOKEN
import importlib
import os
from database.connection import init_db  # <-- NUEVO

class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_TOKEN).updater(None).build()
        init_db()  # <-- NUEVO: Inicializa la DB al arrancar
        self.load_modules()

    def load_modules(self):
        '''Carga todos los modulos de la carpeta modules que tengan registre handler'''
        modules_dir = os.path.join(os.path.dirname(__file__), '..', 'modules')
        for filename in os.listdir(modules_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_name = filename[:-3]
                try:
                    module = importlib.import_module(f'modules.{module_name}')
                    if hasattr(module, 'register_handlers'):
                        module.register_handlers(self.application)
                        print(f"✅ Módulo cargado: {module_name}")
                except Exception as e:
                    print(f"❌ Error al cargar módulo {module_name}: {e}")

    def run(self):
        print("🚀 Bot iniciado y esperando actualizaciones...")
        self.application.run_polling()
