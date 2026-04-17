# Leasy Ops — Backend (Django REST API)

API del sistema operativo interno de Leasy para gestionar tareas de campo
de operarios (verificaciones, recuperos, entregas, conversiones, traslados,
notaría, gestiones).

Sirve a la **app móvil Flutter** (operarios) y al **backoffice Svelte**
(supervisores/admins).

- **Framework:** Django 4.2 + Django REST Framework + SimpleJWT
- **Auth:** Google OAuth (id_token para mobile, auth code para backoffice)
- **DB:** Postgres (RDS en prod vía `DATABASE_URL`) / SQLite (local default)
- **Storage:** S3 con presigned URLs para fotos de tareas
- **Deploy:** AWS ECS (us-east-2) via GitHub Actions + ECR
- **Dominio prod:** `api.opps-app.leasyauto.com`

---

## 🧭 Estructura

```
config/          Django project settings, urls, wsgi/asgi
users/           Usuarios, roles, países, ciudades, distritos, tracking GPS
  views/         Paquete: auth, users, location, tracking, catalogs
tasks/           Tareas, tipos, fotos, resultados, geofences
  views/         Paquete: mobile, backoffice, dashboard, catalogs
  selectors.py   Query helpers compartidos (visibilidad, maps link)
  validators.py  Reglas de geofence + asignación operario ↔ supervisor
  s3.py          Presigned URL helpers
```

---

## 🚀 Correr localmente

### 1. Venv + dependencias

```bash
python -m venv test_venv
test_venv\Scripts\activate      # Windows
# source test_venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. Variables de entorno

Crea un `.env` con lo mínimo:

```env
DEBUG=True
SECRET_KEY=dev-key-cualquier-cosa
ALLOWED_HOSTS=*

# Google OAuth (pide los IDs al admin del proyecto)
GOOGLE_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_WEB_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_WEB_CLIENT_SECRET=...
GOOGLE_ANDROID_CLIENT_ID=...apps.googleusercontent.com

# S3 (si vas a probar subida de fotos)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=...
AWS_S3_REGION_NAME=us-east-2

# Si tienes RDS y quieres usarlo en lugar de SQLite:
# DATABASE_URL=postgres://user:pass@host:5432/dbname
```

### 3. Migraciones + seed

```bash
python manage.py migrate
python manage.py seed_db              # roles, países, ciudades, permisos base
python manage.py seed_geofences       # geofences por ciudad (Lima, Arequipa, CDMX...)
python manage.py seed_districts       # distritos por ciudad
python manage.py rebuild_assignments  # supervisor ↔ operario
```

### 4. Runserver

```bash
python manage.py runserver
# → http://127.0.0.1:8000
```

---

## ✅ Verificar el proyecto

```bash
python manage.py check                 # Django static checks
python manage.py showmigrations        # qué migraciones faltan
python manage.py test                  # tests (actualmente vacíos, WIP)
```

---

## 🌐 Endpoints principales

### Auth
- `POST /api/v1/users/auth/google/` — login (body: `{token}` mobile, `{code}` backoffice)
- `GET  /api/v1/users/check-status/?email=...` — polling post-login

### Mobile (operario)
- `GET  /api/v1/tasks/` — mis tareas
- `POST /api/v1/tasks/<id>/start/`
- `POST /api/v1/tasks/<id>/photos/request-url/` — presigned PUT S3
- `POST /api/v1/tasks/<id>/photos/confirm/`
- `POST /api/v1/tasks/<id>/submit/`
- `POST /api/v1/users/me/location/` — ping GPS

### Backoffice
- `GET  /api/v1/tasks/backoffice/` — lista con filtros
- `POST /api/v1/tasks/backoffice/create/`
- `PATCH /api/v1/tasks/backoffice/<id>/`
- `GET  /api/v1/tasks/dashboard/` — métricas
- `GET  /api/v1/users/tracking/locations/` — live GPS

Ver `users/urls.py` y `tasks/urls.py` para la lista completa.

---

## 🧩 Reglas de negocio clave

- Solo correos `@leasyauto.com` (PE) y `@floty.mx` (MX) pueden loguear.
- Toda tarea debe caer dentro de un **CityGeofence** activo (Haversine).
- Cross-country **nunca**: ni usuarios, ni tareas, ni adopciones.
- Supervisor ve operarios de su ciudad; puede **adoptar** operarios de otras
  ciudades del mismo país (no cross-country).
- Tareas `completed`/`rejected` son terminales — no se reasignan ni borran.

---

## 🚢 Deploy

Push a `main` → GitHub Actions → ECR → ECS `django-cluster/backend-django-service`.

El `Dockerfile` corre `entrypoint.sh`:
```
migrate → seed_db → rebuild_assignments → gunicorn
```

---

## 🗂️ Apps que consumen esta API

- **leasy_ops_backoffice** — Svelte 5 en `opps-app.leasyauto.com`
- **leasy_ops_mobile** — Flutter Android para operarios

Ambas en el repo hermano de este directorio.
