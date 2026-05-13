# Coderhouse · Postulaciones de profesores

Sitio estático que publica las **comisiones sin profesor asignado** del backoffice de Coderhouse para que potenciales profesores se postulen.

```
GitHub Actions (cron diario)
  ↓ build_cohorts.py llama a la M2M API
  ↓ commitea cohorts.json al repo
GitHub Pages sirve index.html
  ↓ fetch('cohorts.json')
  ↓ form submit → Google Apps Script → Google Sheets
```

## Estructura

| Archivo | Propósito |
|---|---|
| `index.html` | Página pública. Lee `cohorts.json` al cargar. |
| `cohorts.json` | Generado por la cron. Lista de comisiones sin profesor. |
| `scripts/build_cohorts.py` | Llama M2M API y genera `cohorts.json`. |
| `.github/workflows/update-cohorts.yml` | Cron diaria 09:00 ART (12:00 UTC). |
| `apps_script.gs` | Webhook para recibir postulaciones en Google Sheets. |

## Setup (una sola vez)

### 1) Google Sheet + Apps Script

1. Crear un Google Sheet llamado `Postulaciones Profesores`.
2. **Extensions → Apps Script**, pegar el contenido de [`apps_script.gs`](apps_script.gs).
3. **Deploy → New deployment**:
   - Type: **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone**
4. Copiar la URL del Web App (queda como `https://script.google.com/macros/s/.../exec`).
5. En [`index.html`](index.html), reemplazar `APPS_SCRIPT_URL` con esa URL.

### 2) Repo en GitHub

1. Crear un repo nuevo (ej. `coderhouse-postulaciones`).
2. Subir todo el contenido de esta carpeta.
3. **Settings → Secrets and variables → Actions → New repository secret**, agregar:
   - `BACKOFFICE_API_URL` — la URL base del backoffice (igual a la del `.env` local).
   - `CLAUDE_STUDENT_API_KEY` — la key `claude-student`.
   - `CLAUDE_FINANCE_API_KEY` — la key `claude-finance`.

### 3) GitHub Pages

1. **Settings → Pages → Source: Deploy from a branch**.
2. Branch: `main`, folder: `/ (root)`.
3. En unos minutos queda publicado en `https://<usuario>.github.io/<repo>/`.

### 4) Ejecutar la cron por primera vez

- **Actions → Update cohorts.json → Run workflow** (manual).
- A partir de ahí corre sola todos los días a las **09:00 ART**.

## ¿Qué hace `build_cohorts.py`?

1. Lista todas las cohortes con `status=NOT_STARTED` (`/student/enrollment/m2m/admin/cohorts`).
2. Lista todas las asignaciones activas (`/platform/staff/m2m/admin/assignments?status=ACTIVE`).
3. Filtra cohortes que **no** tienen rol `PROFESOR` ni `INSTRUCTOR` asignado.
4. Filtra por ventana temporal (default: próximos **60 días** vía `DAYS_AHEAD`).
5. Resuelve el título de cada producto en paralelo.
6. Escribe `cohorts.json` con shape:

```json
{
  "generated_at": "2026-05-13T20:30:00+00:00",
  "total": 108,
  "cohorts": [
    {
      "id": "uuid",
      "title": "AI Automation",
      "schedule": "Lun y Mié — 20:30 ART",
      "start": "27/05/2026",
      "end": "15/07/2026",
      "cid": "103055",
      "modality": "ONLINE",
      "country": "AR",
      "active": true
    }
  ]
}
```

## Ajustes comunes

| Querés cambiar… | Dónde tocar |
|---|---|
| Cantidad de días hacia adelante | `DAYS_AHEAD` en el workflow (`60` → otro número) |
| Frecuencia de la cron | `cron:` en `update-cohorts.yml` (formato cron UTC) |
| Campos del formulario | `index.html` (sección `form-view`) + `apps_script.gs` (`HEADERS` y `appendRow`) |
| Roles que cuentan como "profesor asignado" | `TEACHER_ROLES` en `build_cohorts.py` |

## Probar local

```bash
export BACKOFFICE_API_URL="https://..."
export CLAUDE_STUDENT_API_KEY="..."
export CLAUDE_FINANCE_API_KEY="..."
python3 scripts/build_cohorts.py
python3 -m http.server 8000  # abrir http://localhost:8000
```
