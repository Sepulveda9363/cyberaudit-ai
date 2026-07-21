# 1. Imagen base ligera y segura
FROM python:3.10-slim

# 2. Configurar variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV RUNNING_IN_DOCKER=true

# 3. Establecer el directorio de trabajo
WORKDIR /app

# 4. Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copiar e instalar los requerimientos de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar el código de la aplicación y la base de datos vectorial
COPY ./main.py /app/main.py
COPY ./data /app/data

# 7. HARDENING: Crear usuario sin privilegios y asignar permisos sobre /app
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 8. Exponer el puerto
EXPOSE 8000

# 9. Comando para ejecutar la API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]