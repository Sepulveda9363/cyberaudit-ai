# Modelo de Amenazas — CyberAudit AI 🛡️

Análisis de seguridad sobre la arquitectura RAG local utilizando la metodología **STRIDE** (Microsoft) y riesgos específicos de sistemas de IA (OWASP Top 10 for LLMs).

---

## 🎯 Alcance del Análisis

**Componentes evaluados:**
- API HTTP (FastAPI) — `main.py`
- Motor RAG (ChromaDB + embeddings) — `store_vectors.py`, `query_db.py`
- LLM local (Ollama + Llama 3.2) — orquestado desde `main.py`
- Pipeline de ingesta — `preprocess.py`
- Contenedor Docker — `Dockerfile`
- Frontend Streamlit — `app_ui.py` (opcional)

**Actores:**
- Usuario legítimo (auditor de ciberseguridad)
- Atacante externo (sin credenciales)
- Atacante interno (con credenciales comprometidas)

---

## 🛡️ Matriz STRIDE

| Categoría | Amenaza Específica | Impacto | Mitigación Implementada | Referencia en Código |
|:---|:---|:---|:---|:---|
| **S**poofing | Suplantación de identidad en la API. Un atacante envía peticiones sin autenticar o con credenciales robadas. | Consumo no autorizado de recursos del LLM; posible exfiltración de datos del RAG. | **Implementada:** Autenticación vía `HTTPBearer` con API Key. Validación timing-safe con `hmac.compare_digest()` para prevenir timing attacks. | `main.py`, función `verify_api_key()` |
| **T**ampering | Alteración de los vectores en `data/vector_db/` o de los PDFs originales. Un malware local modifica los documentos indexados. | El LLM genera respuestas con plazos o normativas falsas (ej. alterar las 3 horas del Art. 9° Ley 21.663), induciendo a fallas legales. | **Implementada:** Hardening del contenedor. La aplicación corre bajo usuario `appuser` (UID 1000, sin shell) sin privilegios de root. Filesystem con permisos restrictivos (`chmod 644/755`). | `Dockerfile`, líneas `USER appuser`, `chmod` |
| **R**epudiation | Un usuario niega haber realizado consultas críticas o maliciosas por falta de trazabilidad. | Imposibilidad de realizar análisis forense posterior a un incidente. | **Implementada:** Logging estructurado en formato JSON con `timestamp`, `session_id`, hash SHA-256 de la pregunta, `modo`, `confianza` y `latencia_ms`. Logs persisten en `/app/logs/audit.json`. | `main.py`, configuración de `logging` + `JSONFormatter` |
| **I**nformation Disclosure | Ataques de **Prompt Injection** para extraer el system prompt o saltarse restricciones del RAG. Exfiltración de datos sensibles mediante el LLM. | Exposición de la propiedad intelectual del backend; posible fuga de datos del contexto RAG hacia el atacante. | **Implementada:** (a) Validación Pydantic con regex que detecta patrones de prompt injection (`ignore previous instructions`, `system prompt`, `jailbreak`, etc.) → rechazo con 422. (b) System prompt blindado que prohíbe revelar instrucciones internas. (c) Validación de salida del LLM: si la respuesta contiene "system prompt" o "instrucciones internas", se reemplaza por mensaje de error de seguridad. | `main.py`, clase `QueryRequest` (validator) + función `llamar_ollama()` |
| **D**enial of Service | Envío masivo de solicitudes POST a `/api/ask` para saturar CPU/VRAM del host (Ollama Llama 3.2 es computacionalmente costoso). | Congelamiento del servidor; negación de servicio a usuarios legítimos. | **Implementada:** Rate limiting con `slowapi`: 10 peticiones/minuto por IP. Exceder el límite devuelve `429 Too Many Requests`. Además, validación Pydantic limita la pregunta a máximo 2000 caracteres, previniendo payloads gigantes. | `main.py`, decorador `@limiter.limit("10/minute")` + `QueryRequest` (`max_length=2000`) |
| **E**levation of Privilege | Exploit en FastAPI (ej. ejecución remota de código) para escalar del contenedor al host. | Compromiso total del host Docker y la red interna. | **Implementada:** (a) Contenedor corre como `appuser` (no root). (b) Imagen base `python:3.10-slim` minimiza superficie de ataque. (c) `HEALTHCHECK` integrado. (d) CORS restringido a orígenes configurados por variable de entorno (`ALLOWED_ORIGINS`). | `Dockerfile`, `USER appuser`, `HEALTHCHECK`, `CORS` en `main.py` |

---

## 🤖 Riesgos Específicos de IA (OWASP Top 10 for LLMs)

| Riesgo | Descripción | Mitigación Implementada | Referencia |
|:---|:---|:---|:---|
| **LLM01 — Prompt Injection** | El atacante manipula el input para alterar el comportamiento del LLM (directo o indirecto). | **Implementada:** (a) Validación de inputs con regex anti-inyección (Pydantic). (b) System prompt blindado que prohíbe ignorar instrucciones. (c) Prompt RAG construido por backend: el usuario NUNCA interactúa directamente con el LLM, solo con la capa FastAPI que inyecta contexto controlado. | `main.py`, `QueryRequest.validator` + `construir_prompt_rag()` |
| **LLM02 — Insecure Output Handling** | El LLM genera outputs maliciosos (código, comandos) que se ejecutan sin validación. | **Implementada:** El output del LLM se devuelve como texto plano al usuario. No se ejecuta ni se interpreta como código. Validación de salida detecta intentos de revelar el system prompt. | `main.py`, `llamar_ollama()` |
| **LLM06 — Sensitive Information Disclosure** | El LLM filtra información sensible del contexto RAG o del system prompt. | **Implementada:** (a) RAG local: los datos nunca salen del host. (b) System prompt prohíbe explícitamente revelar instrucciones internas. (c) Validación de salida intercepta fugas. (d) Logs usan hash SHA-256 de la pregunta, no texto plano, para proteger privacidad. | `main.py`, logging + validación de salida |
| **LLM07 — Insecure Plugin Design** | Plugins o herramientas conectadas al LLM sin validación. | **Mitigado por arquitectura:** No hay plugins ni herramientas externas. El LLM solo recibe contexto RAG controlado por FastAPI. |
| **LLM09 — Overreliance** | El usuario confía ciegamente en respuestas alucinadas del LLM. | **Implementada:** (a) El system prompt obliga al LLM a responder **solo** con el contexto RAG. Si no hay información, debe indicarlo explícitamente. (b) Cada respuesta incluye `confianza` (score de similitud) y `fuentes` con documento y página, permitiendo verificación humana. | `main.py`, `SYSTEM_PROMPT_RAG` + `QueryResponse` |

---

## 📊 Trade-offs de Seguridad

| Decisión | Ventaja | Costo / Riesgo residual |
|:---|:---|:---|
| **RAG local vs. API externa** | Soberanía de datos, sin fuga a terceros. | Requiere hardware local (CPU/GPU). Latencia mayor (~8-10s) que APIs cloud. |
| **Rate limiting 10 req/min** | Protege DoS y costo computacional. | Puede limitar uso legítimo en escenarios de alta demanda. |
| **Validación estricta de inputs** | Bloquea prompt injection efectivamente. | Falsos positivos: preguntas legítimas que contengan palabras clave bloqueadas (ej. "¿Cómo funciona el modo jailbreak de un firewall?"). |
| **Logs con hash anónimo** | Protege privacidad del usuario. | Dificulta el análisis forense detallado (no se puede leer la pregunta exacta, solo el hash). |
| **Imagen slim + no root** | Superficie de ataque mínima. | Dificulta debugging dentro del contenedor (no hay shell interactivo como root). |

---

## 🎯 Conclusión

CyberAudit AI implementa un modelo de amenazas **defensa en profundidad**:
1. **Perímetro:** Auth + Rate Limiting + CORS.
2. **Aplicación:** Validación de inputs/outputs + logging estructurado.
3. **Datos:** RAG 100% local, sin salida de datos sensibles.
4. **Infraestructura:** Contenedor hardenizado (slim, no-root, healthcheck).

Los riesgos residuales más significativos son:
- **Alucinaciones del LLM** (mitigado parcialmente con instrucciones estrictas y citas de fuentes).
- **Compromiso del host** (si el atacante escapa del contenedor, mitigado por no-root y capabilities drop).