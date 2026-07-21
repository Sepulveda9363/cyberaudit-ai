import os
import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 1. Inicializar FastAPI y configurar el control de Rate Limiting (Mitigación STRIDE DoS)
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="CyberAudit AI API",
    description="API con RAG sobre normativas de ciberseguridad y controles CIS",
    version="0.1.0"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configuración de base de datos vectorial
DB_DIR = "data/vector_db"
client = chromadb.PersistentClient(path=DB_DIR)
emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)
collection = client.get_collection(name="cybersecurity_norms", embedding_function=emb_fn)

# URL por defecto de Ollama corriendo localmente
# Detectar si estamos corriendo dentro de Docker o en local de Windows
if os.environ.get("RUNNING_IN_DOCKER") == "true":
    OLLAMA_URL = "http://host.docker.internal:11434/api/generate"
else:
    OLLAMA_URL = "http://localhost:11434/api/generate"

MODEL_NAME = "llama3.2:3b"

# Definir el modelo de datos de entrada para la API
class QueryRequest(BaseModel):
    pregunta: str

# Endpoint funcional de consulta RAG protegido con Límite de Peticiones
@app.post("/api/ask")
@limiter.limit("5/minute")
def consultar_rag(request: Request, payload: QueryRequest):
    pregunta = payload.pregunta
    pregunta_lower = pregunta.lower()
    
    # 1. Configurar filtro de metadatos inteligente
    filtro_metadata = None
    if "21663" in pregunta_lower or "ciberseguridad" in pregunta_lower or "ley chilena" in pregunta_lower:
        filtro_metadata = {"source": "Ley-21663_08-ABR-2024.pdf"}

    # 2. RETRIEVAL: Buscar fragmentos relevantes en ChromaDB
    try:
        resultados = collection.query(
            query_texts=[pregunta],
            n_results=5,
            where=filtro_metadata
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar la BD vectorial: {str(e)}")
    
    documentos_recuperados = resultados["documents"][0]
    metadatas = resultados["metadatas"][0]
    
    # --- INYECCIÓN DE SEGURIDAD (HARDENING DEL RETRIEVAL) ---
    necesita_plazos = any(x in pregunta_lower for x in ["plazo", "hora", "reportar", "incidente", "artículo 9", "articulo 9"])
    
    if necesita_plazos and filtro_metadata:
        try:
            busqueda_art9 = collection.query(
                query_texts=["Artículo 9 Deber de reportar ciberataques plazo máximo de tres horas alerta temprana"],
                n_results=3,
                where=filtro_metadata
            )
            for doc, meta in zip(busqueda_art9["documents"][0], busqueda_art9["metadatas"][0]):
                if "artículo 9" in doc.lower() and doc not in documentos_recuperados:
                    documentos_recuperados.insert(0, doc)
                    metadatas.insert(0, meta)
                    documentos_recuperados = documentos_recuperados[:5]
                    metadatas = metadatas[:5]
                    break
        except Exception:
            pass

    if not documentos_recuperados:
        raise HTTPException(status_code=404, detail="No se encontró contexto relevante en la base de datos.")

    # Construir el contexto formateado para el LLM
    contexto_str = ""
    fuentes = []
    for doc, meta in zip(documentos_recuperados, metadatas):
        contexto_str += f"- Fuente: {meta['source']} (Págs: {meta['pages']})\nTexto: {doc}\n\n"
        fuentes.append({
            "source": meta["source"],
            "pages": meta["pages"]
        })

    # 3. PROMPT ENGINEERING (Plantilla de sistema altamente clara)
    prompt_sistema = (
        "Eres un auditor y consultor experto en ciberseguridad chilena. "
        "Tu tarea es responder la pregunta del usuario utilizando el contexto provisto abajo.\n\n"
        "REGLA CRÍTICA DE NEGOCIO:\n"
        "Si en el contexto se menciona el 'Artículo 9°' o 'Deber de reportar' de la Ley 21.663, debes detallar explícitamente los plazos:\n"
        "1. Alerta temprana: Máximo 3 horas desde el conocimiento del incidente.\n"
        "2. Actualización: Máximo 72 horas (o 24 horas si es un operador de importancia vital afectado).\n"
        "3. Informe final: Máximo 15 días corridos.\n\n"
        f"--- CONTEXTO ---\n{contexto_str}\n"
        f"--- PREGUNTA ---\n{pregunta}\n\n"
        "Responde de manera profesional, estructurada y basándote en los datos del contexto."
    )

    # 4. GENERACIÓN: Llamar a Ollama localmente
    payload_ollama = {
        "model": MODEL_NAME,
        "prompt": prompt_sistema,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload_ollama, timeout=120)
        response.raise_for_status()
        llm_response = response.json().get("response", "No se recibió respuesta del modelo.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503, 
            detail=f"Error al conectar con Ollama en {OLLAMA_URL}. Detalle: {str(e)}"
        )

    return {
        "pregunta": pregunta,
        "respuesta": llm_response,
        "fuentes_consultadas": fuentes
    }

# Endpoint básico de salud (Hello World)
@app.get("/")
def read_root():
    return {"status": "healthy", "service": "cyberaudit-ai-api"}