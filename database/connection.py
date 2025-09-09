# database/connection.py
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL

def get_db_connection():
    """Devuelve una conexión activa a la base de datos."""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        print(f"❌ Error al conectar a la base de datos: {e}")
        return None

def init_db():
    """Inicializa las tablas básicas si no existen."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()

        # Tabla de usuarios (para guardar quién usa el bot)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                fecha_registro TIMESTAMP DEFAULT NOW(),
                activo BOOLEAN DEFAULT TRUE
            );
        """)

        # Tabla de líneas (ejemplo inicial para tu bot)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lineas (
                id SERIAL PRIMARY KEY,
                numero_linea VARCHAR(20) UNIQUE NOT NULL,
                nombre_alias VARCHAR(100),
                saldo_actual DECIMAL(10,2) DEFAULT 0.00,
                fecha_ultimo_movimiento TIMESTAMP DEFAULT NOW(),
                propietario_id BIGINT REFERENCES usuarios(id),
                activa BOOLEAN DEFAULT TRUE
            );
        """)

        conn.commit()
        print("✅ Base de datos inicializada. Tablas 'usuarios' y 'lineas' listas.")

    except Exception as e:
        print(f"❌ Error al inicializar la base de datos: {e}")
    finally:
        cur.close()
        conn.close()