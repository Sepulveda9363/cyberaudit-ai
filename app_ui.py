"""
CyberAudit AI — Frontend Streamlit
Interfaz de chat para consultar la API RAG segura.
"""

import os
import requests
import streamlit as st

# ───────────────────────────────────────────────
# CONFIGURACIÓN
# ───────────────────────────────────────────────

st.set_page_config(
    page_title="CyberAudit AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# URL de la API (desde variable de entorno o default)
API_URL = os.getenv("CYBERAUDIT_API_URL", "http://localhost:8000/api/ask")
API_KEY = os.getenv("CYBERAUDIT_API_KEY", "tu-clave-segura-123")

# Headers de autenticación
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# ───────────────────────────────────────────────
# ESTILOS CSS PERSONALIZADOS
# ───────────────────────────────────────────────

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
    }
    .confidence-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 1rem;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .confidence-high { background-color: #d4edda; color: #155724; }
    .confidence-medium { background-color: #fff3cd; color: #856404; }
    .confidence-low { background-color: #f8d7da; color: #721c24; }
    .source-box {
        background-color: #f8f9fa;
        border-left: 3px solid #1f77b4;
        padding: 0.5rem;
        margin: 0.3rem 0;
        border-radius: 0 0.3rem 0.3rem 0;
    }
    .mode-rag { color: #28a745; font-weight: 600; }
    .mode-direct { color: #6c757d; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────────
# SIDEBAR
# ───────────────────────────────────────────────

with st.sidebar:
    st.markdown('<p class="main-header">🛡️ CyberAudit AI</p>', unsafe_allow_html=True)
    st.caption("Asistente RAG seguro para normativas de ciberseguridad")
    
    st.divider()
    
    st.header("⚙️ Configuración")
    
    # Selector de filtro de normativa
    filtro_normativa = st.selectbox(
        "Filtrar por normativa:",
        options=["Todas", "Ley", "ISO", "Framework", "Guía", "Política"],
        index=0,
        help="Limita la búsqueda a un tipo específico de documento"
    )
    
    # Convertir "Todas" a None
    filtro_api = None if filtro_normativa == "Todas" else filtro_normativa
    
    st.divider()
    
    st.header("📋 Información del Sistema")
    st.markdown("""
    **Modelo:** Llama 3.2 (3B) vía Ollama  
    **Embeddings:** all-MiniLM-L6-v2  
    **Vector DB:** ChromaDB (local)  
    **Auth:** API Key + Rate Limiting  
    """)
    
    st.divider()
    
    st.header("📚 Normativas Indexadas")
    st.markdown("""
    - 🇨🇱 **Ley N° 21.663** (Marco de Ciberseguridad)
    - 🇨🇱 **Ley N° 21.719**
    - 🛡️ **CIS Controls v8**
    - 📋 **ISO 27001 / 27002 / 31000**
    - 🔍 **OWASP Top 10**
    - 🏛️ **NIST CSF**
    """)
    
    st.info("🔒 Datos 100% locales. Sin envío a APIs de terceros.")
    
    # Health check visual
    try:
        health = requests.get(API_URL.replace("/api/ask", "/health"), timeout=5)
        if health.status_code == 200:
            st.success("🟢 API Online")
        else:
            st.warning("🟡 API responde con error")
    except:
        st.error("🔴 API Offline")

# ───────────────────────────────────────────────
# HEADER PRINCIPAL
# ───────────────────────────────────────────────

st.markdown('<p class="main-header">🛡️ CyberAudit AI</p>', unsafe_allow_html=True)
st.caption("Consultor experto en normativas de ciberseguridad chilenas e internacionales")

# ───────────────────────────────────────────────
# ESTADO DE SESIÓN
# ───────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())[:8]

# ───────────────────────────────────────────────
# MOSTRAR HISTORIAL
# ───────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        if msg["role"] == "assistant" and msg.get("meta"):
            meta = msg["meta"]
            
            # Badge de confianza
            conf = meta.get("confianza", 0)
            if conf >= 0.7:
                badge_class = "confidence-high"
                badge_text = "Alta confianza"
            elif conf >= 0.4:
                badge_class = "confidence-medium"
                badge_text = "Confianza media"
            else:
                badge_class = "confidence-low"
                badge_text = "Baja confianza"
            
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                st.markdown(f'<span class="confidence-badge {badge_class}">{badge_text} ({conf:.0%})</span>', unsafe_allow_html=True)
            with col2:
                modo = meta.get("modo", "desconocido")
                modo_class = "mode-rag" if "rag" in modo else "mode-direct"
                st.markdown(f'<span class="{modo_class}">🔄 Modo: {modo}</span>', unsafe_allow_html=True)
            with col3:
                st.caption(f"⏱️ {meta.get('tiempo_ms', 0):.0f} ms")
            
            # Fuentes
            if meta.get("fuentes"):
                with st.expander("📚 Fuentes consultadas"):
                    for f in meta["fuentes"]:
                        relevancia = f.get("relevancia", 0)
                        paginas = f.get("paginas", [])
                        pag_str = ", ".join(str(p) for p in paginas) if paginas else "N/A"
                        
                        st.markdown(f"""
                        <div class="source-box">
                            <strong>{f.get('fuente', 'Desconocida')}</strong> 
                            <span style="color:#666">| {f.get('tipo', 'Doc')} | Pág. {pag_str}</span><br>
                            <small>Relevancia: {relevancia:.1%}</small><br>
                            <em>{f.get('fragmento', '')[:200]}...</em>
                        </div>
                        """, unsafe_allow_html=True)

# ───────────────────────────────────────────────
# INPUT DE USUARIO
# ───────────────────────────────────────────────

if prompt := st.chat_input("Escribe tu consulta sobre ciberseguridad o normativas..."):

    # Guardar pregunta
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Procesar respuesta
    with st.chat_message("assistant"):
        with st.status("🔍 Analizando consulta...", expanded=True) as status:
            
            # Paso 1: Validar
            status.write("📝 Validando entrada...")
            if len(prompt) < 3:
                st.error("La pregunta es demasiado corta.")
                st.stop()
            
            # Paso 2: Enviar a API
            status.write("🧠 Consultando base de conocimientos...")
            
            payload = {
                "pregunta": prompt,
                "session_id": st.session_state.session_id
            }
            if filtro_api:
                payload["filtro_normativa"] = filtro_api
            
            try:
                response = requests.post(
                    API_URL,
                    headers=HEADERS,
                    json=payload,
                    timeout=120
                )
                
                # Paso 3: Procesar respuesta
                status.write("📊 Procesando resultados...")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    respuesta = data.get("respuesta", "Sin respuesta.")
                    modo = data.get("modo", "desconocido")
                    confianza = data.get("confianza", 0.0)
                    tiempo_ms = data.get("tiempo_ms", 0)
                    fuentes = data.get("fuentes", [])
                    
                    status.update(label="✅ Respuesta generada", state="complete")
                    
                    # Mostrar respuesta
                    st.markdown(respuesta)
                    
                    # Guardar en historial con metadatos
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": respuesta,
                        "meta": {
                            "modo": modo,
                            "confianza": confianza,
                            "tiempo_ms": tiempo_ms,
                            "fuentes": fuentes
                        }
                    })
                    
                    # Forzar rerun para mostrar metadatos formateados
                    st.rerun()
                
                elif response.status_code == 401:
                    status.update(label="❌ Error de autenticación", state="error")
                    st.error("🔑 API Key inválida. Verificá la configuración.")
                
                elif response.status_code == 422:
                    status.update(label="❌ Entrada no válida", state="error")
                    error_detail = response.json().get("detail", [{}])[0].get("msg", "Entrada inválida")
                    st.error(f"🛡️ {error_detail}")
                
                elif response.status_code == 429:
                    status.update(label="⏳ Rate limit", state="error")
                    st.error("⚠️ Demasiadas consultas. Esperá un minuto antes de intentar de nuevo.")
                
                elif response.status_code == 500:
                    status.update(label="❌ Error interno", state="error")
                    st.error("🔧 Error interno del servidor. Contacte al administrador.")
                
                else:
                    status.update(label=f"❌ Error {response.status_code}", state="error")
                    st.error(f"Error inesperado: {response.status_code}")
            
            except requests.Timeout:
                status.update(label="⏱️ Timeout", state="error")
                st.error("⏱️ El modelo tardó demasiado en responder. Intentá con una pregunta más corta.")
            
            except requests.ConnectionError:
                status.update(label="🔌 Sin conexión", state="error")
                st.error(f"🔌 No se pudo conectar con la API en `{API_URL}`. ¿Está corriendo el contenedor?")
            
            except Exception as e:
                status.update(label="❌ Error", state="error")
                st.error(f"Error: {str(e)}")

# ───────────────────────────────────────────────
# FOOTER
# ───────────────────────────────────────────────

st.divider()
st.caption("🔒 CyberAudit AI v3.0 | Diplomatura en Seguridad en Desarrollo e IA | Todos los datos se procesan localmente")