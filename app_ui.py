import streamlit as st
import requests

# Configuración de la página
st.set_page_config(
    page_title="CyberAudit AI",
    page_icon="🛡️",
    layout="wide"
)

# Título y encabezado
st.title("🛡️ CyberAudit AI - Consultor de Ciberseguridad")
st.caption("Asistente basado en RAG para normativas chilenas (Ley 21.663) y marcos CIS Controls")

# URL de la API FastAPI (detecta si corre en local o en Docker)
API_URL = "http://localhost:8000/api/ask"

# Sidebar informativa
with st.sidebar:
    st.header("📋 Información del Sistema")
    st.markdown("""
    **CyberAudit AI** utiliza un modelo **Llama 3.2** local y **ChromaDB** para responder consultas sobre ciberseguridad.
    
    ---
    **Normativas indexadas:**
    - Ley N° 21.663 (Marco de Ciberseguridad Chile)
    - Controles de Ciberseguridad CIS
    """)
    st.info("🔒 Sistema aislado sin envío de datos al exterior.")

# Inicializar historial de chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar mensajes previos del historial
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "fuentes" in message and message["fuentes"]:
            with st.expander("📚 Fuentes consultadas"):
                for f in message["fuentes"]:
                    st.write(f"- **{f['source']}** (Pág. {f['pages']})")

# Entrada de usuario (Prompt)
if prompt := st.chat_input("Escribe tu consulta sobre ciberseguridad o normativas..."):
    # Guardar y mostrar pregunta del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Respuesta del asistente
    with st.chat_message("assistant"):
        with st.spinner("Consultando base de conocimientos y generando respuesta..."):
            try:
                response = requests.post(
                    API_URL,
                    json={"pregunta": prompt},
                    timeout=120
                )
                
                if response.status_code == 200:
                    data = response.json()
                    respuesta_texto = data.get("respuesta", "Sin respuesta.")
                    fuentes = data.get("fuentes_consultadas", [])
                    
                    st.markdown(respuesta_texto)
                    
                    if fuentes:
                        with st.expander("📚 Fuentes consultadas"):
                            for f in fuentes:
                                st.write(f"- **{f['source']}** (Pág. {f['pages']})")
                    
                    # Guardar en historial
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": respuesta_texto,
                        "fuentes": fuentes
                    })
                elif response.status_code == 429:
                    st.error("⚠️ Límite de peticiones alcanzado (Rate Limiting). Espera un momento antes de realizar otra consulta.")
                else:
                    st.error(f"Error en la API: {response.status_code}")
            except Exception as e:
                st.error(f"No se pudo conectar con la API en `{API_URL}`. Asegúrate de que el contenedor esté corriendo. Detalle: {str(e)}")