import streamlit as st
import os
import json
import time
import io
import base64
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai
from gtts import gTTS
import tools

load_dotenv()

# Inicialización de la base de datos PostgreSQL
try:
    tools.init_db()
except Exception as e:
    st.error(f"Error conectando a PostgreSQL: {e}")

st.set_page_config(
    page_title="Asistente de Contrataciones Inclusivas (ODS 8)",
    page_icon="💼",
    layout="wide"
)

st.title("💼 Asistente de Contrataciones Inclusivas (ODS 8)")
st.caption("Plataforma con accesibilidad de audio vinculada a Datos Abiertos del Perú.")

# Función para convertir texto a voz (TTS) con lectura de tildes
def generar_audio_base64(texto):
    try:
        texto_limpio = texto.replace("*", "").replace("#", "").replace("•", "").replace("📌", "").replace("🚀", "")
        tts = gTTS(text=texto_limpio, lang='es', tld='com.mx', slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_b64 = base64.b64encode(fp.read()).decode('utf-8')
        return f'<audio controls autoplay style="width: 100%; height: 38px;"><source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3"></audio>'
    except Exception:
        return None

# Sidebar con estado de PostgreSQL
with st.sidebar:
    st.header("⚙️ Configuración del Motor")
    engine_choice = st.selectbox(
        "Proveedor de IA activo:",
        ["Google Gemini (Fallback)", "OpenAI (Assistants API)"]
    )
    
    activar_voz = st.toggle("🔊 Voz Inclusiva (Lectura con tildes)", value=True)
    
    st.divider()
    st.header("🗄️ Base de Datos Local (PostgreSQL)")
    if st.button("Actualizar registros guardados"):
        st.rerun()
        
    filas = tools.obtener_ofertas_db()
    if filas:
        st.success(f"{len(filas)} oferta(s) registrada(s):")
        st.dataframe(filas, use_container_width=True)
    else:
        st.info("Aún no se han registrado ofertas en PostgreSQL.")
    
    st.divider()
    st.header("🔔 Monitor de Alertas Automáticas")
    alertas = tools.obtener_alertas_db()
    if alertas:
        st.dataframe(alertas, use_container_width=True)
    else:
        st.caption("No hay alertas programadas.")

SYSTEM_PROMPT = """Eres el Asistente de Contrataciones Inclusivas, una solución de IA para automatizar la identificación y gestión de oportunidades laborales formales compatibles con el perfil de un postulante, contribuyendo al acceso a trabajo decente e inclusivo (ODS 8).

OPERAS CON 9 ROLES:
1. Buscador de ofertas: Consulta bolsas de empleo estatales y encuentra ofertas disponibles mediante herramientas.
2. Filtrador: Descarta ofertas que no cumplen los requisitos indicados por el postulante.
3. Analista de perfil: Compara estudios, experiencia, habilidades y otros requisitos con cada oferta.
4. Recomendador: Identifica las ofertas que presentan mayor compatibilidad con el perfil.
5. Registrador: Guarda las ofertas seleccionadas en una base de datos local.
6. Gestor de eventos: Extrae fechas importantes (publicación, inicio, cierre de convocatoria, evaluaciones, entrevista, resultados).
7. Notificador: Envía un mensaje estructurado confirmando que una oferta fue encontrada y registrada.
8. Asistente inclusivo: Prioriza la claridad y accesibilidad de la información y evita criterios discriminatorios.
9. Validador: Comprueba que la información obtenida sea coherente antes de almacenarla.

OBJETIVOS ESPECÍFICOS:
- Buscar ofertas laborales en fuentes estatales disponibles (Plataforma Nacional de Datos Abiertos).
- Identificar ofertas del área profesional del postulante y comparar requisitos con el perfil.
- Filtrar según criterios configurados y descartar las que no cumplen requisitos mínimos obligatorios.
- Registrar ofertas compatibles en PostgreSQL evitando duplicados mediante verificar_duplicado.
- Generar confirmación formal, crear cronograma de eventos, mantener trazabilidad de fuentes y comunicar con claridad.

REGLAS DE BÚSQUEDA Y FILTRADO:
- Solo fuentes autorizadas. Registrar fuente y URL oficial verídica (ej. https://www.datosabiertos.gob.pe).
- No inventar ofertas ni requisitos. No registrar si la información fundamental está incompleta.
- Criterios evaluables: Carrera/especialidad, nivel educativo, experiencia (meses/años), conocimientos técnicos, certificaciones, ubicación, modalidad (presencial, híbrida, remota), contrato, jornada, salario y requisitos obligatorios.
- Distinción crítica:
  * Requisito obligatorio -> si no se cumple, la oferta DEBE descartarse.
  * Requisito deseable -> NO provoca descarte automático; solo ajusta el nivel de compatibilidad.

REGLAS ÉTICAS Y DE INCLUSIÓN:
- Queda PROHIBIDO descartar o favorecer candidatos por: sexo o género, raza o etnia, religión, orientación sexual, embarazo o edad (salvo tope legal explícito en las bases).
- Discapacidad: No descartar, salvo que se trate de una convocatoria específicamente dirigida a dicha población protegida y el postulante corresponda a ella.
- Evaluar únicamente requisitos laborales verificables.
- Si tras consultar las fuentes estatales no se encuentran ofertas vigentes compatibles, informa con tono preventivo y empático al postulante y ofrécele activar una Alerta Laboral Automatizada con execute_crear_alerta (solicitando su correo) para notificarle en cuanto se publique una vacante que calce con sus requisitos.

CONTROL ESTRICTO DE AMBIGÜEDADES:
1. 'Experiencia en programación' -> Pedir o identificar qué lenguajes/tecnologías específicos se consideran.
2. 'Conocimiento de inglés' -> No asumir nivel B2/C1 si la oferta no lo especifica.
3. 'Experiencia requerida' -> Diferenciar taxativamente entre meses/años y entre experiencia laboral general/específica y prácticas.
4. 'Disponibilidad inmediata' -> No asumir que el usuario la tiene.
5. 'Buen manejo de Excel' -> No convertir automáticamente en un nivel avanzado/específico.
6. Salario no indicado -> Mostrar exactamente: 'No especificado'.
7. Ubicación ambigua -> Mostrar exactamente lo indicado por la fuente.
8. Fecha no indicada -> Declarar exactamente: 'Fecha no especificada en la convocatoria'. Jamás inventarla.
9. Requisito deseable -> No tratarlo como obligatorio.
10. Oferta duplicada -> Si ya existe en la base de datos, no crear otro registro e informar con tono preventivo.
11. Oferta vencida -> Marcarla como vencida en lugar de recomendarla como vigente.
12. Fuente caída o contradictoria -> Informar que no pudo verificarse, priorizar bases oficiales y señalar discrepancias.

CALENDARIO DE EVENTOS:
Por cada oferta registrada debes extraer y asignar fechas para: Publicación de convocatoria, Inicio de postulación, Cierre de postulación, Evaluación curricular, Evaluación técnica, Entrevista y Publicación de resultados. Si una fecha no aparece, escribe exactamente: 'Fecha no especificada en la convocatoria.'

MODULACIÓN DE TONO DE VOZ (Cuida ortografía y lectura de tildes):
- Profesional (para mostrar resultados): 'Se encontraron X ofertas que cumplen con los requisitos establecidos en tu perfil.'
- Claro y directo (para filtros y alertas): 'Esta oferta requiere X años de experiencia. Tu perfil registra Y años, por lo que no cumple el requisito obligatorio.'
- Amigable (para notificaciones de éxito): '¡Encontré una oportunidad que podría coincidir con tu perfil! 🚀'
- Inclusivo (respeto y accesibilidad): 'La oferta cumple con los criterios laborales configurados. La decisión de postular corresponde al usuario.'
- Preventivo (ante datos faltantes o duplicados): 'No fue posible determinar el salario porque la convocatoria no proporciona ese dato.'
- Neutral (comparativas): 'La oferta A cumple X de N criterios configurados. La oferta B cumple Y de N.'

ESTRUCTURA OBLIGATORIA DEL MENSAJE DE CONFIRMACIÓN AL REGISTRAR:
📌 **Oferta laboral registrada**
Se encontró una oferta compatible con tu perfil:
- **Cargo:** [Título]
- **Entidad:** [Entidad]
- **Modalidad:** [Modalidad]
- **Ubicación:** [Ubicación]
- **Fecha límite:** [Fecha]
- **Nivel de compatibilidad:** [Porcentaje o ratio]

*La oferta fue registrada correctamente en tu base de datos local.*

**Próximos eventos:**
• Cierre de convocatoria: [Fecha]
• Evaluación curricular: [Fecha]
• Evaluación técnica: [Fecha]
• Entrevista: [Fecha]
• Publicación de resultados: [Fecha]

🔗 **Fuente oficial:** [URL verídica]"""

# Configuración de Clientes
if os.getenv("GEMINI_API_KEY"):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

openai_client = None
if os.getenv("OPENAI_API_KEY"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "audio" in msg and msg["audio"]:
            st.markdown(msg["audio"], unsafe_allow_html=True)

def resolver_nombre_modelo():
    """Detecta una sola vez el modelo exacto disponible en tu cuenta para evitar 404."""
    if "gemini_model_name" not in st.session_state:
        modelo_encontrado = None
        try:
            modelos_disponibles = [
                m.name for m in genai.list_models()
                if "generateContent" in m.supported_generation_methods
            ]
            # Priorizar cualquier variante flash
            for m in modelos_disponibles:
                if "flash" in m.lower():
                    modelo_encontrado = m
                    break
            # Si no hay flash, tomar el primer modelo compatible (ej. gemini-pro)
            if not modelo_encontrado and modelos_disponibles:
                modelo_encontrado = modelos_disponibles[0]
        except Exception:
            modelo_encontrado = "gemini-pro"

        st.session_state.gemini_model_name = modelo_encontrado or "gemini-pro"
        
    return st.session_state.gemini_model_name

def obtener_o_crear_chat():
    """Mantiene la sesión de chat viva para no saturar inicializando conexiones en cada mensaje."""
    if "gemini_chat" not in st.session_state:
        funciones_gemini = [
            tools.execute_filtrar_ofertas,
            tools.execute_verificar_duplicado,
            tools.execute_registrar_oferta,
            tools.execute_crear_alerta
        ]
        
        nombre_modelo = resolver_nombre_modelo()
        
        model = genai.GenerativeModel(
            model_name=nombre_modelo,
            system_instruction=SYSTEM_PROMPT,
            tools=funciones_gemini
        )
        st.session_state.gemini_chat = model.start_chat(enable_automatic_function_calling=True)
    return st.session_state.gemini_chat

def ejecutar_con_gemini(prompt_usuario):
    """Ejecuta la consulta manejando reintentos progresivos si hay saturación rápida."""
    chat = obtener_o_crear_chat()
    
    intentos = 3
    tiempo_espera = 4  # Segundos de enfriamiento
    
    for intento in range(intentos):
        try:
            # Pausa preventiva de 1 segundo para amortiguar ráfagas
            time.sleep(1)
            response = chat.send_message(prompt_usuario)
            return response.text
            
        except Exception as ex:
            error_str = str(ex)
            
            # Control de Rate Limit (429) por preguntas seguidas
            if "429" in error_str or "ResourceExhausted" in error_str:
                if intento < intentos - 1:
                    with st.status(f"⏳ Esperando enfriamiento de cuota ({tiempo_espera}s)...", expanded=False):
                        time.sleep(tiempo_espera)
                    tiempo_espera *= 2
                    continue
                else:
                    return (
                        "⚠️ **Límite de solicitudes por minuto alcanzado.**\n\n"
                        "Por favor, espera unos 15 segundos antes de enviar tu siguiente mensaje para permitir que la cuota gratuita de Google AI Studio se restablezca."
                    )
            
            # Si el historial interno de funciones quedó corrupto o dio 404, reiniciamos el chat
            if "404" in error_str or "function_call" in error_str:
                if "gemini_chat" in st.session_state:
                    del st.session_state["gemini_chat"]
                if "gemini_model_name" in st.session_state:
                    del st.session_state["gemini_model_name"]
                
                # Reintento con modelo reconstruido
                if intento < intentos - 1:
                    chat = obtener_o_crear_chat()
                    continue

            return f"Error durante la ejecución: {error_str}"

user_input = st.chat_input("Escribe tu perfil laboral o consulta convocatorias vigentes...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Procesando con 9 roles y verificando en PostgreSQL..."):
            try:
                if "Gemini" in engine_choice:
                    respuesta = ejecutar_con_gemini(user_input)
                else:
                    st.warning("Assistants API seleccionada: requiere saldo activo en OpenAI Platform.")
                    respuesta = "Por favor, utiliza 'Google Gemini (Fallback)' para ejecutar Function Calling gratuitamente."

                audio_html = generar_audio_base64(respuesta) if activar_voz else None

                st.markdown(respuesta)
                if audio_html:
                    st.markdown(audio_html, unsafe_allow_html=True)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": respuesta,
                    "audio": audio_html
                })
                st.rerun()

            except Exception as e:
                st.error(f"Error de ejecución: {str(e)}")