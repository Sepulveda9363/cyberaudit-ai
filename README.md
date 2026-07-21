# CyberAudit AI 🛡️🤖
> **Asistente de Auditoría Avanzado con RAG Local para Normativas de Ciberseguridad y Controles CIS**

CyberAudit AI es una solución de software diseñada bajo criterios de **Seguridad por Diseño (Security by Design)** que implementa una arquitectura de **Generación Aumentada por Recuperación (RAG)** de ejecución 100% local. El sistema actúa como un consultor automatizado experto en la legislación de ciberseguridad chilena e infraestructura crítica (Ley Marco Nº 21.663) y marcos de control internacionales como CIS Controls v8.

---

## 🏗️ Arquitectura del Sistema (RAG Local Segura)

Para garantizar la confidencialidad, soberanía de datos y evitar riesgos de fuga de información hacia APIs de terceros (como OpenAI o Anthropic), todo el procesamiento se ejecuta en el host local:

1. **Capa de Ingesta (Retrieval):** Los cuerpos legales (PDF) son segmentados y vectorizados mediante el modelo embebido multilingüe `all-MiniLM-L6-v2`.
2. **Base de Datos Vectorial:** Los vectores y sus metadatos se indexan de manera persistente en una instancia local de **ChromaDB**.
3. **Filtro Avanzado e Inyección de Contexto:** Una capa intermedia en FastAPI intercepta las consultas analíticas críticas (ej. plazos legales de reporte) aplicando filtros de metadatos algorítmicos para forzar la recuperación exacta de los artículos correspondientes.
4. **Capa de Generación (LLM Local):** Orquestado a través de **Ollama**, el modelo cuántico **Llama 3.2 (3B)** procesa el prompt del sistema blindado para generar respuestas estructuradas en formato JSON técnico con citas explícitas de fuentes y páginas.

---

## 📦 Docker & Hardening (Hito 2)

El servicio ha sido completamente contenedorizado siguiendo directrices de robustecimiento (*hardening*) para despliegues seguros en entornos institucionales:

* **Minimización de Superficie de Ataque:** Uso de una imagen base optimizada `python:3.10-slim`.
* **Principio de Menor Privilegio (Non-Root):** El contenedor no se ejecuta como `root`. Se crea un usuario de sistema dedicado (`appuser`) con permisos restringidos sobre el directorio `/app`.
* **Aislamiento de Red:** Mapeo controlado del puerto de servicio (`8000:8000`) utilizando un puente de red dinámico (`host.docker.internal`) para comunicarse de forma segura con el backend de Ollama en el host.

---

## 🚀 Instrucciones de Despliegue Local

### Requisitos Previos
* **Docker Desktop** activo (con soporte WSL 2 configurado).
* **Ollama** instalado en el host con el modelo descargado: `ollama run llama3.2:3b`.

### 1. Construcción de la Imagen
Desde la raíz del repositorio, ejecuta el proceso de build de Docker:
```bash
docker build -t cyberaudit-ai:latest .
2. Ejecución del Contenedor Seguro
Levanta la API en segundo plano inyectando el hostname dinámico para la conexión con la IA:

Bash
docker run -d \
  -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  --name cyberaudit-api-container \
  cyberaudit-ai:latest
3. Verificación del Servicio
Accede a la documentación interactiva e interfaz de pruebas en tu navegador:

Swagger UI: http://localhost:8000/docs

🛠️ Pipeline de Integración Continua (CI/CD)
El proyecto cuenta con un flujo automatizado implementado en GitHub Actions (.github/workflows/ci.yml) que ejecuta dos etapas de control en cada cambio del código base:

Instalación de Dependencias: Validación estática del archivo estructurado requirements.txt.

Validación del Contenedor (Docker Build Test): Compilación limpia automatizada del entorno para verificar la integridad del empaquetado antes de cualquier despliegue operativo.


---

## 🎯 Introducción al Hito 3: Modelo de Amenazas (STRIDE)

Con el `README.md` listo y la API corriendo feliz dentro de Docker, podemos dar el salto hacia el **Hito 3**. Este hito se enfoca en la seguridad profunda del software y nos exige diseñar un **Modelo de Amenazas** utilizando la metodología **STRIDE** (desarrollada por Microsoft).

STRIDE nos obliga a ponernos el sombrero de *hacker* ético y analizar los riesgos del sistema dividiéndolos en 6 categorías:
1. **S**poofing (Suplantación de identidad).
2. **T**ampering (Alteración de datos/código).
3. **R**epudiation (Repudio de acciones).
4. **I**nformation Disclosure (Fuga de información).
5. **D**enial of Service (Denegación de servicio).
6. **E**levation of Privilege (Elevación de privilegios).

Para empezar a mapear los vectores de ataque reales del proyecto: ¿Qué te preocupa más a nivel de seg