# services/database.py

import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Obtener la URL de la base de datos de Railway
DATABASE_URL = os.getenv("DATABASE_URL")  # Se define automáticamente en Railway

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

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
