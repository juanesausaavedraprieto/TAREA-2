import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from dotenv import load_dotenv
import unicodedata

load_dotenv()

CSV_PATH = "data/convocatorias_estatales.csv"

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "contrataciones_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "")
    )

def init_db():
    """Crea las tablas necesarias en PostgreSQL si no existen."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ofertas_registradas (
            id_oferta VARCHAR(50) PRIMARY KEY,
            titulo VARCHAR(255),
            entidad VARCHAR(255),
            descripcion TEXT,
            requisitos TEXT,
            area_profesional VARCHAR(100),
            ubicacion VARCHAR(100),
            modalidad VARCHAR(50),
            tipo_contrato VARCHAR(50),
            salario VARCHAR(50),
            fecha_publicacion VARCHAR(100),
            fecha_cierre VARCHAR(100),
            url TEXT,
            fuente VARCHAR(100),
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            estado VARCHAR(50),
            nivel_compatibilidad VARCHAR(50)
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cronograma_eventos (
            id SERIAL PRIMARY KEY,
            id_oferta VARCHAR(50) REFERENCES ofertas_registradas (id_oferta) ON DELETE CASCADE,
            evento VARCHAR(100),
            fecha VARCHAR(100)
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alertas_suscritas (
            id SERIAL PRIMARY KEY,
            email_usuario VARCHAR(150),
            area_profesional VARCHAR(100),
            ubicacion VARCHAR(100),
            modalidad VARCHAR(50),
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            estado VARCHAR(50) DEFAULT 'Activa'
        );
    """)
    conn.commit()
    cursor.close()
    conn.close()

# ----------------------------------------------------
# Esquemas JSON Schema para OpenAI Assistants API
# ----------------------------------------------------
tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "filtrar_ofertas_laborales",
            "description": "Filtra el dataset oficial de convocatorias laborales estatales por área profesional, ubicación y modalidad mediante código interno.",
            "parameters": {
                "type": "object",
                "properties": {
                    "area_profesional": {
                        "type": "string",
                        "description": "Área o carrera del postulante (ej. 'Sistemas', 'Administración')."
                    },
                    "ubicacion": {
                        "type": "string",
                        "description": "Departamento o ciudad de la vacante (ej. 'Piura', 'Lima')."
                    },
                    "modalidad": {
                        "type": "string",
                        "enum": ["Presencial", "Híbrida", "Remota", "No especificado"],
                        "description": "Modalidad de trabajo deseada."
                    }
                },
                "required": ["area_profesional"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verificar_duplicado",
            "description": "Comprueba si una oferta laboral ya se encuentra persistida en la base de datos PostgreSQL local mediante su ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id_oferta": {
                        "type": "string",
                        "description": "Identificador único de la convocatoria (ej. 'CAS-2026-001')."
                    }
                },
                "required": ["id_oferta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_oferta_idonea",
            "description": "Guarda la oferta seleccionada y su cronograma de eventos en PostgreSQL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id_oferta": {"type": "string"},
                    "titulo": {"type": "string"},
                    "entidad": {"type": "string"},
                    "descripcion": {"type": "string"},
                    "requisitos": {"type": "string"},
                    "area_profesional": {"type": "string"},
                    "ubicacion": {"type": "string"},
                    "modalidad": {"type": "string"},
                    "tipo_contrato": {"type": "string"},
                    "salario": {"type": "string"},
                    "fecha_publicacion": {"type": "string"},
                    "fecha_cierre": {"type": "string"},
                    "url": {"type": "string"},
                    "fuente": {"type": "string"},
                    "nivel_compatibilidad": {"type": "string"},
                    "cierre_convocatoria": {"type": "string"},
                    "evaluacion_curricular": {"type": "string"},
                    "evaluacion_tecnica": {"type": "string"},
                    "entrevista": {"type": "string"},
                    "publicacion_resultados": {"type": "string"}
                },
                "required": [
                    "id_oferta", "titulo", "entidad", "ubicacion", "modalidad",
                    "fecha_cierre", "url", "fuente", "nivel_compatibilidad", "cierre_convocatoria"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "crear_alerta_postulante",
            "description": "Registra una alerta automatizada para monitorear vacantes futuras de un perfil laboral.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_usuario": {"type": "string", "description": "Correo del postulante."},
                    "area_profesional": {"type": "string", "description": "Área profesional de interés."},
                    "ubicacion": {"type": "string", "description": "Departamento o ciudad de preferencia."},
                    "modalidad": {"type": "string", "description": "Modalidad de trabajo deseada."}
                },
                "required": ["email_usuario", "area_profesional"]
            }
        }
    }
]

# ----------------------------------------------------
# Implementación de las funciones de backend
# ----------------------------------------------------
def normalizar_texto(texto):
    if not isinstance(texto, str):
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()

def execute_filtrar_ofertas(area_profesional: str, ubicacion: str = "", modalidad: str = "") -> str:
    """Filtra el dataset de convocatorias estatales por área profesional, ubicación y modalidad."""
    try:
        if not os.path.exists(CSV_PATH):
            return json.dumps({"error": f"No se encontró el archivo de datos en {CSV_PATH}"})

        df = pd.read_csv(CSV_PATH)
        area_norm = df['area_profesional'].astype(str).apply(normalizar_texto)
        ubic_norm = df['ubicacion'].astype(str).apply(normalizar_texto)
        mod_norm = df['modalidad'].astype(str).apply(normalizar_texto)
        
        filtro_area_str = normalizar_texto(area_profesional)
        palabras_clave = [p for p in filtro_area_str.split() if len(p) > 3]
        if not palabras_clave:
            palabras_clave = [filtro_area_str]

        condicion = False
        for p in palabras_clave:
            condicion = condicion | area_norm.str.contains(p, na=False)

        if ubicacion and normalizar_texto(ubicacion) not in ["", "no especificado"]:
            condicion = condicion & ubic_norm.str.contains(normalizar_texto(ubicacion), na=False)

        if modalidad and normalizar_texto(modalidad) not in ["", "no especificado"]:
            condicion = condicion & mod_norm.str.contains(normalizar_texto(modalidad), na=False)

        resultados_df = df[condicion]
        
        if resultados_df.empty:
            condicion_amplia = False
            for p in palabras_clave:
                condicion_amplia = condicion_amplia | area_norm.str.contains(p, na=False)
            if ubicacion and normalizar_texto(ubicacion) not in ["", "no especificado"]:
                condicion_amplia = condicion_amplia & ubic_norm.str.contains(normalizar_texto(ubicacion), na=False)
            resultados_df = df[condicion_amplia]

        resultados = resultados_df.head(5).to_dict(orient="records")
        return json.dumps(resultados, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error al filtrar datos: {str(e)}"})

def execute_verificar_duplicado(id_oferta: str) -> str:
    """Verifica si el id_oferta ya existe en la base de datos PostgreSQL."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id_oferta FROM ofertas_registradas WHERE id_oferta = %s;", (id_oferta,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return json.dumps({"existe": row is not None})
    except Exception as e:
        return json.dumps({"error": str(e)})

def execute_registrar_oferta(
    id_oferta: str,
    titulo: str,
    entidad: str,
    ubicacion: str,
    modalidad: str,
    fecha_cierre: str,
    url: str,
    fuente: str,
    nivel_compatibilidad: str,
    cierre_convocatoria: str = "Fecha no especificada en la convocatoria.",
    evaluacion_curricular: str = "Fecha no especificada en la convocatoria.",
    evaluacion_tecnica: str = "Fecha no especificada en la convocatoria.",
    entrevista: str = "Fecha no especificada en la convocatoria.",
    publicacion_resultados: str = "Fecha no especificada en la convocatoria.",
    area_profesional: str = "No especificado",
    descripcion: str = "No especificado",
    requisitos: str = "No especificado",
    tipo_contrato: str = "CAS",
    salario: str = "No especificado",
    fecha_publicacion: str = "Fecha no especificada en la convocatoria."
) -> str:
    """Registra la oferta seleccionada y su cronograma en PostgreSQL."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ofertas_registradas (
                id_oferta, titulo, entidad, descripcion, requisitos, area_profesional,
                ubicacion, modalidad, tipo_contrato, salario, fecha_publicacion,
                fecha_cierre, url, fuente, estado, nivel_compatibilidad
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_oferta) DO NOTHING;
        """, (
            id_oferta, titulo, entidad, descripcion, requisitos, area_profesional,
            ubicacion, modalidad, tipo_contrato, salario, fecha_publicacion,
            fecha_cierre, url, fuente, "Registrada", nivel_compatibilidad
        ))
        
        cronograma = {
            "Cierre de convocatoria": cierre_convocatoria,
            "Evaluación curricular": evaluacion_curricular,
            "Evaluación técnica": evaluacion_tecnica,
            "Entrevista": entrevista,
            "Publicación de resultados": publicacion_resultados
        }
        
        for evento, fecha in cronograma.items():
            cursor.execute("""
                INSERT INTO cronograma_eventos (id_oferta, evento, fecha)
                VALUES (%s, %s, %s);
            """, (id_oferta, evento, fecha))
            
        conn.commit()
        cursor.close()
        conn.close()
        return json.dumps({"status": "success", "mensaje": f"Oferta {id_oferta} registrada exitosamente en PostgreSQL."})
    except Exception as e:
        return json.dumps({"status": "error", "mensaje": str(e)})

def execute_crear_alerta(email_usuario: str, area_profesional: str, ubicacion: str = "Piura", modalidad: str = "No especificado") -> str:
    """Registra una suscripción de alerta en PostgreSQL para monitoreo futuro."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alertas_suscritas (email_usuario, area_profesional, ubicacion, modalidad)
            VALUES (%s, %s, %s, %s);
        """, (email_usuario, area_profesional, ubicacion, modalidad))
        conn.commit()
        cursor.close()
        conn.close()
        return json.dumps({
            "status": "success",
            "mensaje": f"Alerta automatizada activada exitosamente para {email_usuario}. Se monitoreará la bolsa estatal de forma continua."
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

def obtener_ofertas_db():
    """Consulta todas las ofertas persistidas para la visualización en Streamlit."""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id_oferta, titulo, entidad, modalidad, estado, nivel_compatibilidad FROM ofertas_registradas ORDER BY fecha_registro DESC;")
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return filas
    except Exception:
        return []

def obtener_alertas_db():
    """Consulta las alertas programadas activas para la barra lateral."""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT email_usuario, area_profesional, ubicacion, estado FROM alertas_suscritas ORDER BY fecha_registro DESC;")
        filas = cursor.fetchall()
        cursor.close()
        conn.close()
        return filas
    except Exception:
        return []