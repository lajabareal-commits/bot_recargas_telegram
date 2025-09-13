# bot/core.py
from telegram.ext import Application
from config import TELEGRAM_TOKEN
import importlib
import os
from database.connection import get_db_connection
from datetime import date, timedelta

class TelegramBot:
        def __init__(self):
            self.application = Application.builder().token(TELEGRAM_TOKEN).build()
            try:
                self.limpiar_registros_antiguos()  # <-- Ejecuta limpieza al iniciar
            except Exception as e:
                print(f"❌ Error al ejecutar limpieza automática: {e}")
            self.load_modules()

    def limpiar_registros_antiguos(self):
        """Elimina permanentemente paquetes y recargas con más de 6 meses de antigüedad."""
        conn = get_db_connection()
        if not conn:
            return

        try:
            cur = conn.cursor()
            limite = date.today() - timedelta(days=180)  # 6 meses = 180 días

            # 1. Eliminar recursos_linea con fecha_vencimiento > 6 meses
            cur.execute("""
                DELETE FROM recursos_linea
                WHERE fecha_vencimiento < %s
            """, (limite,))
            recursos_eliminados = cur.rowcount

            # 2. Eliminar recargas (fecha_ultima_recarga) > 6 meses
            # NOTA: Solo eliminamos la fecha, no la línea completa
            cur.execute("""
                UPDATE lineas
                SET fecha_ultima_recarga = NULL
                WHERE fecha_ultima_recarga < %s AND fecha_ultima_recarga IS NOT NULL
            """, (limite,))
            recargas_eliminadas = cur.rowcount

            conn.commit()

            if recursos_eliminados > 0 or recargas_eliminadas > 0:
                print(f"🧹 Limpieza automática completada:")
                print(f"   - {recursos_eliminados} recursos eliminados (más de 6 meses).")
                print(f"   - {recargas_eliminadas} fechas de recarga eliminadas (más de 6 meses).")
            else:
                print("✅ No se encontraron registros antiguos para eliminar.")

        except Exception as e:
            print(f"❌ Error en limpieza automática de registros antiguos: {e}")
        finally:
            cur.close()
            conn.close()

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