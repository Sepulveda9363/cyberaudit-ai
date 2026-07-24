# =============================================================================
# CyberAudit AI — Dockerfile Hardenizado
# Cumple: imagen mínima, sin root, solo artefactos necesarios, healthcheck
# =============================================================================

# 1. Imagen base mínima y segura
FROM python:3.10-slim

# 2. Metadatos de la imagen
LABEL maintainer="CyberAudit AI Team" \
      description="API RAG segura para normativas de ciberseguridad" \
      version="3.0.0"

# 3. Variables de entorno de seguridad
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RUNNING_IN_DOCKER=true \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 4. Directorio de trabajo
WORKDIR /app

# 5. Instalar dependencias del sistema (mínimas) y limpiar
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
    && apt-get autoremove -y

# 6. Crear usuario no-privilegiado ANTES de copiar archivos
# UID 1000 es estándar, pero fijarlo evita conflictos
RUN groupadd -r appgroup -g 1000 && \
    useradd -r -u 1000 -g appgroup -s /sbin/nologin -d /app appuser

# 7. Crear directorios necesarios con permisos correctos
# /app/logs: para logs estructurados (audit.json)
# /app/data/vector_db: para ChromaDB (se monta o copia)
RUN mkdir -p /app/logs /app/data/vector_db && \
    chown -R appuser:appgroup /app

# 8. Copiar e instalar dependencias Python (capa cacheable)
COPY --chown=appuser:appgroup requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 9. Copiar SOLO el código fuente necesario
# NO copiar data/raw/ ni otros archivos pesados/innecesarios
COPY --chown=appuser:appgroup main.py .
COPY --chown=appuser:appgroup app_ui.py .
COPY --chown=appuser:appgroup preprocess.py .
COPY --chown=appuser:appgroup store_vectors.py .
COPY --chown=appuser:appgroup query_db.py .
COPY --chown=appuser:appgroup STRIDE.md .
COPY --chown=appuser:appgroup README.md .


# 10. Copiar SOLO la base vectorial indexada (NO los PDFs raw)
# Asume que data/vector_db/ existe y fue generado por store_vectors.py
COPY --chown=appuser:appgroup data/vector_db /app/data/vector_db

# 11. Asegurar permisos finales (defensa en profundidad)
RUN chmod -R 755 /app && \
    chmod 644 /app/*.py /app/*.md && \
    chmod 755 /app/logs /app/data /app/data/vector_db

# 12. Cambiar a usuario no-root
USER appuser

# 13. Healthcheck: verifica que la API responde
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 14. Exponer puerto
EXPOSE 8000

# 15. Ejecutar API (sin privilegios, sin shell interactivo)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]