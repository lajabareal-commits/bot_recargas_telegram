# services/database.py

import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Obtener la URL de la base de datos desde la variable de entorno
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL no está definida. Configura la variable de entorno en Render o Railway.")

def get_db():
    """
    Retorna una conexión a la base de datos.
    """
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    """
    Inicializa la base de datos creando las tablas necesarias si no existen.
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Tabla lineas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lineas (
                numero TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                es_principal BOOLEAN DEFAULT FALSE,
                fecha_registro TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Tabla recargas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recargas (
                id SERIAL PRIMARY KEY,
                numero TEXT REFERENCES lineas(numero) ON DELETE CASCADE,
                fecha DATE NOT NULL,
                creado_en TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Tabla paquetes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paquetes (
                id SERIAL PRIMARY KEY,
                numero TEXT REFERENCES lineas(numero) ON DELETE CASCADE,
                tipo TEXT NOT NULL,
                fecha_compra DATE NOT NULL,
                creado_en TIMESTAMP DEFAULT NOW()
            )
        ''')

        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Base de datos inicializada correctamente")

    except Exception as e:
        print(f"❌ Error inicializando la base de datos: {e}")
        raise

