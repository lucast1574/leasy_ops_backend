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

# Recolección de archivos estáticos (Útil para entornos en la nube como AWS ECS o AppRunner)
# Pasamos una SECRET_KEY falsa al momento del build para que Django no marque error al hacer collectstatic
RUN SECRET_KEY='dummy-key-for-build' python manage.py collectstatic --noinput

# Expone el puerto 8000
EXPOSE 8000

# Comando para arrancar con Gunicorn (tu carpeta de settings/wsgi se llama 'config')
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
