# Gateway Service Dockerfile
FROM python:3.12-slim

WORKDIR /gateway

# Instalar curl para healthcheck
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del gateway
COPY main.py .

# Exponer puerto del gateway
EXPOSE 8080

# Variable de entorno para el backend
ENV BACKEND_URL="http://app:8000"
ENV PYTHONUNBUFFERED=1

# Comando para iniciar el gateway
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

