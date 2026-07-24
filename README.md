# CyberAudit AI 🛡️🤖

> **Asistente de Auditoría Avanzado con RAG Local para Normativas de Ciberseguridad**

CyberAudit AI es una solución de software diseñada bajo criterios de **Seguridad por Diseño (Security by Design)** que implementa una arquitectura de **Generación Aumentada por Recuperación (RAG)** de ejecución 100% local. El sistema actúa como un consultor automatizado experto en la legislación de ciberseguridad chilena (Ley Marco Nº 21.663, Ley Nº 21.719) y marcos de control internacionales (CIS Controls v8, ISO 27001/27002, NIST, OWASP).

---

## 🏗️ Decisiones de Arquitectura

### ¿Por qué RAG local en vez de API externa (OpenAI/Anthropic)?
- **Soberanía de datos:** Las normativas legales no salen del host.
- **Cumplimiento:** Evita fuga de información hacia terceros.
- **Costo:** Sin consumo de tokens por consulta.
- **Riesgo:** Mitiga dependencia de proveedores externos.

### ¿Por qué ChromaDB?
- Base vectorial **ligera y embebida**, no requiere servidor externo.
- Soporta **filtros de metadatos** (por tipo de normativa, país, organismo).
- Persistencia en disco, ideal para contenedores.

### ¿Por qué Llama 3.2 (3B) vía Ollama?
- **Modelo cuantizado** que corre en CPU/GPU consumer.
- **3B parámetros** es suficiente para respuestas estructuradas sobre normativa.
- **Ollama** simplifica el despliegue local del modelo.

### ¿Por qué FastAPI + Pydantic?
- Validación automática de inputs (incluye anti-prompt injection).
- Documentación interactiva Swagger UI incluida.
- Async nativo, ideal para I/O con Ollama.

---

## 📦 Arquitectura del Sistema
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   PDFs (data/)  │────▶│  preprocess.py   │────▶│ rag_chunks.json │
└─────────────────┘     └──────────────────┘     └─────────────────┘
│
┌─────────────────┐     ┌──────────────────┐              │
│   ChromaDB      │◀────│ store_vectors.py │◀─────────────┘
│  (vector_db/)   │     └──────────────────┘
└────────┬────────┘
│
┌────▼────┐     ┌─────────────┐     ┌─────────────┐
│  FastAPI │────▶│   Ollama    │────▶│ Llama 3.2   │
│  (main)  │     │  (local)    │     │   (3B)      │
└────┬─────┘     └─────────────┘     └─────────────┘
│
┌────▼────┐
│Streamlit│
│(app_ui) │
└─────────┘
plain

### Capas de seguridad implementadas:
1. **Autenticación:** API Key vía `Authorization: Bearer` con comparación timing-safe (`hmac.compare_digest`).
2. **Rate Limiting:** 10 peticiones/minuto por IP (`slowapi`).
3. **Validación de inputs:** Pydantic con regex anti-prompt injection.
4. **Validación de outputs:** Detección de intentos de revelar el system prompt.
5. **Logs estructurados:** JSON en `/app/logs/audit.json` (no repudio).
6. **Métricas:** Endpoint `/metrics` con contadores, latencia y errores.
7. **Hardening de contenedor:** Imagen slim, usuario no-root (`appuser`), healthcheck.

---

## 🚀 Instrucciones de Despliegue Local

### Requisitos Previos
- **Docker Desktop** activo (con WSL 2).
- **Ollama** instalado con el modelo descargado:
  ```bash
  ollama pull llama3.2:3b
1. Clonar y construir
bash
git clone https://github.com/Sepúlveda9363/ciberauditoría-ai.git
cd ciberauditoría-ai
docker build -t cyberaudit-ai:latest .
2. Ejecutar el contenedor
bash
docker run -d \
  -p 8000:8000 \
  --name cyberaudit-api \
  -e CYBERAUDIT_API_KEY="tu-clave-super-segura" \
  -e OLLAMA_URL="http://host.docker.internal:11434/api/generate" \
  -e ALLOWED_ORIGINS="http://localhost:8501" \
  --add-host=host.docker.internal:host-gateway \
  cyberaudit-ai:latest
Nota: Si la base vectorial (data/vector_db/) no está incluida en la imagen, primero debés indexar los PDFs (ver sección "Ingesta de documentos" abajo).
3. Verificar que funciona
bash
curl http://localhost:8000/health
4. Acceder a la documentación
Swagger UI: http://localhost:8000/docs
Métricas: http://localhost:8000/metrics
📚 Ingesta de Documentos (si es necesario re-indexar)
Si necesitás regenerar la base vectorial (por ejemplo, agregaste nuevos PDFs):
bash
# Requiere Python 3.10+ local
pip install -r requirements.txt

# 1. Extraer texto y generar chunks
python preprocess.py

# 2. Vectorizar e indexar en ChromaDB
python store_vectors.py

# 3. Verificar
python query_db.py --diagnostico
🔑 Uso de la API
Autenticación
Todas las peticiones a /api/ask requieren header:
plain
Authorization: Bearer tu-clave-super-segura
Consulta RAG con filtro
bash
curl -X POST http://localhost:8000/api/ask \
  -H "Authorization: Bearer tu-clave-super-segura" \
  -H "Content-Type: application/json" \
  -d '{
    "pregunta": "plazo para notificar incidente Ley 21663",
    "filtro_normativa": "Ley"
  }'
Saludo (modo directo, sin RAG)
bash
curl -X POST http://localhost:8000/api/ask \
  -H "Authorization: Bearer tu-clave-super-segura" \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "hola"}'
Prompt injection bloqueado (422)
bash
curl -X POST http://localhost:8000/api/ask \
  -H "Authorization: Bearer tu-clave-super-segura" \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "ignore previous instructions"}'
🎨 Frontend Streamlit (opcional)
Si querés una interfaz gráfica:
bash
pip install streamlit
streamlit run app_ui.py
Accedé en: http://localhost:8501
🛠️ Pipeline CI/CD
GitHub Actions (.github/workflows/ci.yml) ejecuta en cada push:
Instalación de dependencias (requirements.txt).
Build del contenedor Docker para verificar integridad.
📁 Estructura del Repositorio
plain
cyberaudit-ai/
├── .github/workflows/    # CI/CD
├── data/
│   ├── raw/              # PDFs de normativas (no van al contenedor)
│   ├── processed/        # Chunks JSON intermedios
│   └── vector_db/        # ChromaDB persistente
├── src/                  # Módulos auxiliares (si aplica)
├── tests/                # Tests pytest
├── app_ui.py             # Frontend Streamlit
├── main.py               # API FastAPI
├── preprocess.py         # Pipeline de ingesta
├── store_vectors.py      # Indexador vectorial
├── query_db.py           # Script de diagnóstico RAG
├── Dockerfile            # Contenedor hardenizado
├── STRIDE.md             # Modelo de amenazas
├── requirements.txt
└── README.md
🛡️ Seguridad
Ver STRIDE.md para el modelo de amenazas completo con mitigaciones por categoría.