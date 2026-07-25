# CyberAudit AI 🛡️🤖

> **Asistente de Auditoría Avanzado con RAG Local para Normativas de Ciberseguridad**

CyberAudit AI es una solución de software diseñada bajo criterios de **Seguridad por Diseño (Security by Design)** que implementa una arquitectura de **Generación Aumentada por Recuperación (RAG)** de ejecución 100% local. El sistema actúa como un consultor automatizado experto en la legislación de ciberseguridad chilena (Ley Marco Nº 21.663, Ley Nº 21.719, Ley Nº 21.459, Ley Nº 19.628, Ley Nº 19.799) y marcos de control internacionales (CIS Controls v8, ISO 27001/27002, NIST, OWASP).

---

## 🏗️ Decisiones de Arquitectura

### ¿Por qué RAG local en vez de API externa (OpenAI/Anthropic)?
- **Soberanía de datos:** Las normativas legales y consultas de auditoría no salen del host.
- **Cumplimiento:** Evita la fuga de información sensible hacia servidores de terceros.
- **Costo:** Sin consumo de tokens por consulta en servicios cloud.
- **Riesgo:** Mitiga la dependencia operativa de proveedores externos.

### ¿Por qué ChromaDB?
- Base vectorial **ligera y embebida**, no requiere levantar un servidor externo.
- Soporta **filtros de metadatos** (por tipo de normativa, país, organismo).
- Persistencia eficiente en disco, ideal para despliegues en contenedores.

### ¿Por qué Llama 3.2 (3B) vía Ollama?
- **Modelo cuantizado** con excelente desempeño en hardware convencional (CPU/GPU consumer).
- **3B parámetros** es suficiente para estructurar respuestas precisas basadas en contexto normativo.
- **Ollama** simplifica el despliegue, la gestión y la ejecución local del modelo.

### ¿Por qué FastAPI + Pydantic?
- Validación automática y estricta de entradas (incluye defensas anti-prompt injection).
- Documentación interactiva en Swagger UI generada automáticamente.
- Soporte asíncrono nativo, ideal para operaciones de I/O con Ollama.

---

## 📦 Arquitectura del Sistema

```text
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   PDFs (data/)  │────▶│  preprocess.py   │────▶│ rag_chunks.json │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
┌─────────────────┐     ┌──────────────────┐              │
│   ChromaDB      │◀────│ store_vectors.py │◀─────────────┘
│  (vector_db/)   │     └──────────────────┘
└────────┬────────┘
         │
┌────────▼────────┐     ┌─────────────┐     ┌─────────────┐
│     FastAPI     │────▶│   Ollama    │────▶│ Llama 3.2   │
│     (main)      │     │  (local)    │     │   (3B)      │
└────────┬────────┘     └─────────────┘     └─────────────┘
         │
┌────────▼────────┐
│    Streamlit    │
│    (app_ui)     │
└─────────────────┘
Capas de Seguridad Implementadas#ControlImplementación1AutenticaciónAPI Key vía Authorization: Bearer con comparación timing-safe (hmac.compare_digest).2Rate Limiting10 peticiones/minuto por IP (slowapi).3Validación de inputsPydantic con regex anti-prompt injection.4Validación de outputsDetección de intentos de revelar el system prompt.5Logs estructuradosJSON en /app/logs/audit.json (soporte para no repudio).6MétricasEndpoint /metrics con contadores, latencia y registros de errores.7HardeningImagen base slim, usuario sin privilegios no-root (appuser), healthcheck activo.🚀 Instrucciones de Despliegue LocalRequisitos PreviosDocker Desktop activo (con soporte WSL 2 en Windows).Ollama instalado localmente con el modelo previamente descargado:Bashollama pull llama3.2:3b
📌 Nota: Si usas Windows, abre PowerShell. En Linux/macOS, utiliza tu terminal habitual.1. Clonar y Construir la ImagenBashgit clone [https://github.com/Sepulveda9363/ciberauditoria-ai.git](https://github.com/Sepulveda9363/ciberauditoria-ai.git)
cd ciberauditoria-ai
docker build -t cyberaudit-ai:latest .
2. Ejecutar el Contenedor🪟 Windows (PowerShell)PowerShelldocker run -d `
  -p 8000:8000 `
  --name cyberaudit-api `
  -e CYBERAUDIT_API_KEY="tu-clave-super-segura" `
  -e OLLAMA_URL="[http://host.docker.internal:11434/api/generate](http://host.docker.internal:11434/api/generate)" `
  -e ALLOWED_ORIGINS="http://localhost:8501" `
  --add-host=host.docker.internal:host-gateway `
  cyberaudit-ai:latest
🐧 Linux / 🍎 macOS (Bash)Bashdocker run -d \
  -p 8000:8000 \
  --name cyberaudit-api \
  -e CYBERAUDIT_API_KEY="tu-clave-super-segura" \
  -e OLLAMA_URL="[http://host.docker.internal:11434/api/generate](http://host.docker.internal:11434/api/generate)" \
  -e ALLOWED_ORIGINS="http://localhost:8501" \
  --add-host=host.docker.internal:host-gateway \
  cyberaudit-ai:latest
Nota: Si la base vectorial (data/vector_db/) no está incluida previamente en la imagen, primero debes indexar las fuentes (ver sección Ingesta de Documentos).3. Verificar FuncionamientoBashcurl http://localhost:8000/health
4. Acceder a la DocumentaciónSwagger UI: http://localhost:8000/docsMétricas: http://localhost:8000/metrics📚 Ingesta de DocumentosSi necesitas regenerar o actualizar la base de datos vectorial tras añadir nuevos PDFs normativos:Requisitos LocalesBash# Requiere Python 3.10+ local
pip install -r requirements.txt
Pasos de EjecuciónBash# 1. Extraer texto y generar chunks intermedios
python preprocess.py

# 2. Vectorizar e indexar en ChromaDB
python store_vectors.py

# 3. Ejecutar diagnóstico de lectura
python query_db.py --diagnostico
🔑 Uso de la APIAutenticaciónTodas las peticiones protegidas hacia /api/ask requieren el siguiente encabezado HTTP:HTTPAuthorization: Bearer tu-clave-super-segura
Ejemplo 1: Consulta RAG con FiltroBashcurl -X POST http://localhost:8000/api/ask \
  -H "Authorization: Bearer tu-clave-super-segura" \
  -H "Content-Type: application/json" \
  -d '{
    "pregunta": "plazo para notificar incidente Ley 21663",
    "filtro_normativa": "Ley"
  }'
Ejemplo 2: Saludo (Modo Directo / Conversacional)Bashcurl -X POST http://localhost:8000/api/ask \
  -H "Authorization: Bearer tu-clave-super-segura" \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "hola"}'
Ejemplo 3: Bloqueo de Prompt Injection (Devuelve 422 Unprocessable Entity)Bashcurl -X POST http://localhost:8000/api/ask \
  -H "Authorization: Bearer tu-clave-super-segura" \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "ignore previous instructions"}'
🎨 Frontend Streamlit (Opcional)Para desplegar la interfaz gráfica de usuario:Bashpip install streamlit
streamlit run app_ui.py
Accede desde tu navegador en: http://localhost:8501🛠️ Pipeline CI/CDEl flujo de integración continua mediante GitHub Actions (.github/workflows/ci.yml) ejecuta de forma automática en cada push o pull_request:Instalación y validación de dependencias (requirements.txt).Reconstrucción del contenedor Docker para asegurar la integridad de la compilación.📁 Estructura del RepositorioPlaintextcyberaudit-ai/
├── .github/workflows/    # Pipelines de CI/CD
├── data/
│   ├── raw/              # Documentos PDF normativos de entrada
│   ├── processed/        # Chunks JSON intermedios
│   └── vector_db/        # Base de datos vectorial persistente (ChromaDB)
├── src/                  # Módulos y lógica auxiliar
├── tests/                # Batería de pruebas automatizadas (pytest)
├── app_ui.py             # Interfaz web gráfica en Streamlit
├── main.py               # Servidor y API RESTful en FastAPI
├── preprocess.py         # Extractor y fragmentador de PDFs
├── store_vectors.py      # Script de embedding e indexación vectorial
├── query_db.py           # Script de prueba y diagnóstico RAG
├── Dockerfile            # Configuración del contenedor hardenizado
├── STRIDE.md             # Documentación del Modelo de Amenazas
├── requirements.txt      # Librerías de Python
└── README.md             # Documentación principal del proyecto
🛡️ Seguridad y Modelo de AmenazasConsulta el archivo STRIDE.md para revisar el análisis detallado de riesgos, vectores de ataque evaluados y sus correspondientes controles de mitigación implementados.