# database/connection.py
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL
import logging

logger = logging.getLogger(__name__)

def get_db_connection():
    """Devuelve una conexión activa a la base de datos."""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        logger.error(f"❌ Error al conectar a la base de datos: {e}")
        return None

def init_db():
    """Inicializa las tablas y columnas básicas si no existen."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()

        # ========================
        # TABLA: usuarios
        # ========================
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

        # ========================
        # TABLA: lineas
        # ========================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lineas (
                id SERIAL PRIMARY KEY,
                numero_linea VARCHAR(20) UNIQUE NOT NULL,
                nombre_alias VARCHAR(100),
                saldo_actual DECIMAL(10,2) DEFAULT 0.00,
                fecha_ultima_recarga DATE,
                fecha_registro TIMESTAMP DEFAULT NOW(),
                propietario_id BIGINT REFERENCES usuarios(id),
                activa BOOLEAN DEFAULT TRUE,
                es_principal BOOLEAN DEFAULT FALSE
            );
        """)

        # ========================
        # TABLA: recursos_linea
        # ========================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recursos_linea (
                id SERIAL PRIMARY KEY,
                linea_id INTEGER REFERENCES lineas(id) ON DELETE CASCADE,
                tipo_recurso VARCHAR(20) NOT NULL,
                cantidad DECIMAL(10,2) NOT NULL,
                fecha_activacion DATE NOT NULL,
                fecha_vencimiento DATE NOT NULL,
                origen_paquete VARCHAR(255),
                activo BOOLEAN DEFAULT TRUE
            );
        """)

        # ========================
        # VERIFICAR Y AGREGAR COLUMNAS FALTANTES (si se añaden en el futuro)
        # ========================
        # Agregar columna 'notas' a 'lineas' solo si no existe
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'lineas' AND column_name = 'notas'
                ) THEN
                    ALTER TABLE lineas ADD COLUMN notas TEXT;
                    RAISE NOTICE '✅ Columna ''notas'' agregada a tabla ''lineas''.';
                END IF;
            END $$;
        """)

        # Agregar columna 'fecha_ultimo_uso' a 'usuarios' solo si no existe
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'usuarios' AND column_name = 'fecha_ultimo_uso'
                ) THEN
                    ALTER TABLE usuarios ADD COLUMN fecha_ultimo_uso TIMESTAMP;
                    RAISE NOTICE '✅ Columna ''fecha_ultimo_uso'' agregada a tabla ''usuarios''.';
                END IF;
            END $$;
        """)

        conn.commit()
        logger.info("✅ Base de datos inicializada. Tablas y columnas verificadas.")

    except Exception as e:
        logger.error(f"❌ Error al inicializar la base de datos: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()