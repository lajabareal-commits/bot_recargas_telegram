# services/database.py

import psycopg2
from psycopg2.extras import RealDictCursor
import config

def get_db():
    return psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASS,
        cursor_factory=RealDictCursor  # Para devolver resultados como diccionarios
    )

def init_db():
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