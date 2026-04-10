# Usa una imagen oficial de Python
FROM python:3.11-slim

# Evita que Python genere archivos .pyc y que el buffer se llene
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependencias del sistema necesarias para PostgreSQL y compilaciones (gcc, libpq-dev)
RUN apt-get update \
    && apt-get install -y libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Instala dependencias de Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install gunicorn

# Copia el proyecto entero
COPY . /app/

# Recolección de archivos estáticos
RUN SECRET_KEY='dummy-key-for-build' python manage.py collectstatic --noinput

# Asegura que el entrypoint sea ejecutable
RUN chmod +x /app/entrypoint.sh

# Expone el puerto 8000
EXPOSE 8000

# Usa entrypoint.sh que corre: migrate → seed_db → rebuild_assignments → gunicorn
CMD ["/app/entrypoint.sh"]
