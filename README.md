# AI Task Manager API

API REST para administrar tareas, construida como un MVP simple, predecible y fácil de probar.
No requiere autenticación ni multiusuario y expone operaciones CRUD sobre una única entidad
`Task` persistida en SQLite.

> Estado del proyecto: Etapas 1 a 5 implementadas (fundaciones, configuración, persistencia,
> servicios y capa HTTP). Ver [Estado actual y funcionalidades pendientes](#15-estado-actual-y-funcionalidades-pendientes).

---

## 1. Descripción general

El proyecto expone cuatro operaciones sobre tareas (crear, listar, obtener/actualizar/eliminar
por identificador) más un healthcheck. El contrato HTTP se genera automáticamente con FastAPI
y se versiona en [`docs/openapi.json`](docs/openapi.json).

Decisiones del MVP, según `AGENTS.md`:

- Sin autenticación ni multiusuario.
- Identificadores `Integer` autoincrementales.
- Estados: `pending`, `in_progress`, `completed`.
- Prioridades: `low`, `medium`, `high`; valor por defecto `medium`.
- Fechas almacenadas y expuestas en UTC (ISO-8601 con sufijo `Z`).
- Paginación y filtros incluidos desde el primer endpoint de listado.
- SQLite + SQLAlchemy síncrono.
- Actualizaciones parciales mediante `PATCH`.
- Sin Alembic: la creación de tablas se controla por configuración solo en desarrollo.

**Fuera del MVP:** autenticación, roles, proyectos, notas, webhooks, migraciones automáticas,
concurrencia distribuida y despliegue.

---

## 2. Objetivos y funcionalidades principales

- Ofrecer una API REST JSON con un contrato estable y documentado.
- Mantener reglas de negocio separadas de HTTP y de SQL.
- Permitir listar tareas con filtros, orden determinista y paginación.
- Garantizar un formato de error único en toda la API.
- Cubrir el comportamiento con tests unitarios, de integración y de API.

Funcionalidades implementadas:

| Funcionalidad | Descripción |
|---|---|
| CRUD de tareas | `POST`, `GET` (lista e item), `PATCH` y `DELETE`. |
| Filtros de listado | `status`, `priority`, `limit`, `offset` y `sort`. |
| Orden determinista | `created_at` con desempate por `id` descendente. |
| Reglas de negocio | Normalización de `title`, defaults y gestión de `completed_at`. |
| Healthcheck | `GET /health` consulta la base de datos real. |
| Contrato | Swagger UI, ReDoc, `/openapi.json` y `docs/openapi.json`. |
| Errores | Envelope común `{detail, code, fields}`. |

---

## 3. Tecnologías utilizadas

Versiones resueltas en `uv.lock`:

| Uso | Tecnología | Versión |
|---|---|---|
| Lenguaje | Python | 3.14 (fijado en `.python-version`; `requires-python >=3.14`) |
| Framework HTTP | FastAPI | 0.165.0 |
| ORM | SQLAlchemy (modo síncrono 2.x) | 2.1.9 |
| Base de datos | SQLite (driver `sqlite3` del stdlib) | — |
| Validación / DTOs | Pydantic v2 | 2.14.4 |
| Servidor ASGI | uvicorn | 0.54.0 |
| Pruebas | pytest | 9.2.0 |
| Cliente HTTP de tests | httpx | 0.28.1 |
| Lint | Ruff | 0.17.6 |
| Gestor de entorno y dependencias | uv | `uv.lock` |

Pydantic llega como dependencia transitiva de FastAPI; no está declarado directamente en
`pyproject.toml`. El proyecto usa `TestClient` de FastAPI (basado en httpx) para los tests de API.

---

## 4. Arquitectura y estructura del proyecto

Flujo de dependencias:

```text
HTTP → api → services → repositories → models → db → SQLite
              │             │
              └──── schemas ────┘   (contrato transversal)

exceptions.py: errores de dominio + handlers HTTP globales
```

`schemas` es transversal: ninguna capa inferior importa a una superior. Los endpoints son
delgados, el repositorio es el único que construye consultas y el modelo ORM solo representa
la tabla.

Estructura real del repositorio:

```text
.
├── AGENTS.md                       # reglas de trabajo y decisiones aprobadas
├── pyproject.toml                  # metadatos, dependencias y config de pytest
├── uv.lock                         # lockfile de uv
├── .python-version                 # 3.14
├── docs/
│   └── openapi.json                # contrato versionado generado desde FastAPI
├── src/
│   └── ai_task_manager/
│       ├── __init__.py             # versión y helper utc_now()
│       ├── main.py                 # create_app(), lifespan, /health
│       ├── config.py               # configuración desde variables de entorno
│       ├── exceptions.py           # errores de dominio y handlers globales
│       ├── db/
│       │   ├── __init__.py
│       │   ├── base.py             # Base, convenciones y columnas de auditoría
│       │   └── session.py          # engine, SessionLocal y get_session
│       ├── models/
│       │   ├── __init__.py
│       │   └── task.py             # entidad Task, enums, constraints e índices
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── common.py           # ErrorResponse y Page[T]
│       │   └── task.py             # TaskCreate, TaskUpdate, TaskRead, TaskPage
│       ├── repositories/
│       │   ├── __init__.py
│       │   └── task_repository.py  # CRUD, filtros, orden y paginación
│       ├── services/
│       │   ├── __init__.py
│       │   └── task_service.py     # reglas de negocio y excepciones de dominio
│       └── api/
│           ├── __init__.py
│           ├── deps.py             # composición session → repository → service
│           └── v1/
│               ├── __init__.py
│               ├── router.py       # agregador de rutas v1
│               └── tasks.py        # endpoints de tareas
└── tests/
    ├── conftest.py                 # sesión SQLite en memoria y repositorio de prueba
    ├── api/
    │   ├── conftest.py             # app de prueba con dependency_overrides
    │   ├── test_health.py
    │   └── test_tasks.py
    ├── integration/
    │   └── test_task_repository.py
    └── unit/
        ├── test_config.py
        ├── test_exceptions.py
        ├── test_session.py
        ├── test_task_service.py
        └── test_time.py
```

---

## 5. Responsabilidad de cada capa

| Capa / módulo | Responsabilidad |
|---|---|
| **API** (`api/`, `main.py`) | Validar request/response, delegar al servicio, serializar DTOs, códigos HTTP, `Location`, healthcheck y documentación. No accede a `Session` directamente. |
| **Services** (`services/task_service.py`) | Normalizar `title`, validar enums, aplicar defaults, gestionar `completed_at` y lanzar excepciones de dominio. No conoce HTTP ni SQL. |
| **Repositories** (`repositories/task_repository.py`) | Único módulo que construye consultas: CRUD, filtros, orden, paginación, `flush` y validación de campos actualizables. |
| **Models** (`models/task.py`) | Mapear la tabla `tasks` con SQLAlchemy 2.x declarativo. No valida payloads de API. |
| **Schemas** (`schemas/`) | Contrato transversal: DTOs de entrada/salida, enums, envelope de paginación y de error. |
| **DB** (`db/`) | `Base`, convención de constraints, timestamps, engine, sesiones y `get_session` con commit/rollback/close. |
| **Config** (`config.py`) | Leer y validar variables de entorno; `get_settings()` está cacheado por proceso. |
| **Exceptions** (`exceptions.py`) | Errores tipados de dominio y handlers que producen siempre el mismo JSON de error. |

---

## 6. Requisitos previos

- Python 3.14 (ver `.python-version`; `pyproject.toml` exige `>=3.14`).
- [`uv`](https://docs.astral.sh/uv/) instalado y disponible en el `PATH`.
- No se necesita instalar ni configurar SQLite por separado: se usa el módulo `sqlite3`
  de la biblioteca estándar.

Podés comprobar el entorno con:

```bash
uv --version
```

---

## 7. Instalación y configuración del entorno con uv

Desde la raíz del repositorio:

```bash
uv sync
```

`uv sync` crea/actualiza `.venv` usando las versiones fijadas en `uv.lock` e instala también
el grupo de dependencias de desarrollo (`pytest`, `httpx` y `ruff`) por defecto. Si querés
omitirlo:

```bash
uv sync --no-dev
```

Todos los comandos de este README se ejecutan con `uv run`, que usa el entorno del proyecto
sin necesidad de activar manualmente `.venv`.

---

## 8. Instalación de dependencias

No hay comandos adicionales: `uv sync` instala todo lo declarado en `pyproject.toml` y
`uv.lock`. No se agregaron dependencias fuera de las declaradas originalmente.

---

## 9. Variables de entorno

La configuración se lee desde el entorno del proceso en `config.py`. El proyecto **no carga
archivos `.env` automáticamente**: exportá las variables en tu shell o en la configuración de
tu entorno.

| Variable | Valor por defecto | Regla |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./ai_task_manager.db` | Debe comenzar con `sqlite://`. Para una BD en memoria: `sqlite:///:memory:`. |
| `ENV` | `development` | Debe ser `development`, `testing` o `production` (se normaliza a minúsculas y se recorta). |
| `API_PREFIX` | `/api/v1` | Debe comenzar con `/`; se eliminan las barras finales. |
| `CREATE_TABLES_ON_STARTUP` | `true` si `ENV=development`; si no, `false` | Acepta `1/true/yes/on` y `0/false/no/off` (o vacío). Si se define explícitamente, prevalece sobre `ENV`. |

Ejemplo para trabajar sin crear archivos en disco:

```bash
export DATABASE_URL=sqlite:///:memory:
export ENV=development
```

`get_settings()` usa `lru_cache(maxsize=1)`: los cambios de entorno requieren reiniciar la
aplicación para tomar efecto.

---

## 10. Cómo ejecutar la aplicación

El paquete vive bajo `src/`, por eso uvicorn necesita `--app-dir src`:

```bash
uv run uvicorn --app-dir src ai_task_manager.main:app --reload
```

La aplicación queda en `http://127.0.0.1:8000`.

Con `ENV=development` y la `DATABASE_URL` por defecto, el lifespan crea las tablas al
arrancar y se genera `ai_task_manager.db` en la raíz (ignorado por `.gitignore`). Para usar
solo memoria:

```bash
DATABASE_URL=sqlite:///:memory: uv run uvicorn --app-dir src ai_task_manager.main:app --reload
```

Si el puerto 8000 está ocupado, agregá `--port 8001`.

---

## 11. Acceso a Swagger UI y OpenAPI

Con la aplicación en marcha:

| Recurso | URL |
|---|---|
| Swagger UI | `http://127.0.0.1:8000/docs` |
| ReDoc | `http://127.0.0.1:8000/redoc` |
| OpenAPI generado | `http://127.0.0.1:8000/openapi.json` |
| Contrato versionado | [`docs/openapi.json`](docs/openapi.json) |

Un test comprueba que el archivo versionado coincide con el contrato generado por la app.

---

## 12. Cómo ejecutar los tests con Pytest

```bash
uv run pytest
```

Para ver el detalle de cada caso:

```bash
uv run pytest -v
```

`pyproject.toml` configura `pythonpath = ["src"]` y `testpaths = ["tests"]`, por lo que los
comandos funcionan desde la raíz sin variables adicionales.

Suite actual: **112 tests en verde** (22 de API, 29 de integración y 61 unitarios). Las pruebas
usan SQLite en memoria con `StaticPool` y `dependency_overrides`, sin tocar la base de datos real.

---

## 13. Cómo ejecutar Ruff

```bash
uv run ruff check .
```

Resultado actual: `All checks passed!`.

---

## 14. Endpoints disponibles

Prefijo de la API: `/api/v1` (el healthcheck está en la raíz). Contenido: `application/json`.

| Método | Ruta | Éxito | Errores |
|---|---|---|---|
| `GET` | `/health` | `200` → `{"status": "ok"}` | `503` si la BD no responde |
| `POST` | `/api/v1/tasks` | `201` + cabecera `Location` | `400` (*), `422` |
| `GET` | `/api/v1/tasks` | `200` → `TaskPage` | `422` |
| `GET` | `/api/v1/tasks/{task_id}` | `200` → `TaskRead` | `404`, `422` |
| `PATCH` | `/api/v1/tasks/{task_id}` | `200` → `TaskRead` | `404`, `422` |
| `DELETE` | `/api/v1/tasks/{task_id}` | `204` sin cuerpo | `404`, `422` |

(*) El contrato documenta `400` para errores genéricos de dominio; las reglas implementadas
hoy producen `422` (validación) y `404` (no encontrado).

### Parámetros de `GET /api/v1/tasks`

| Parámetro | Tipo | Default | Detalle |
|---|---|---|---|
| `status` | `pending`, `in_progress`, `completed` | — | Filtro opcional. |
| `priority` | `low`, `medium`, `high` | — | Filtro opcional. |
| `limit` | entero `1..100` | `20` | Tamaño de página. |
| `offset` | entero `>= 0` | `0` | Desplazamiento. |
| `sort` | `created_at:asc`, `created_at:desc` | `created_at:desc` | Orden principal; desempate por `id` descendente. |

Respuesta de paginación:

```json
{"items": [], "total": 0, "limit": 20, "offset": 0}
```

### Cuerpos de request

`POST /api/v1/tasks` (`TaskCreate`):

| Campo | Tipo | Requerido | Detalle |
|---|---|---|---|
| `title` | string `1..200` | sí | Se normaliza con `strip()` en el servicio. |
| `description` | string o `null` | no | Opcional. |
| `status` | enum | no | Default `pending`. |
| `priority` | enum | no | Default `medium`. |
| `due_at` | datetime ISO o `null` | no | Se almacena en UTC naive. |

`PATCH /api/v1/tasks/{task_id}` (`TaskUpdate`): los mismos campos son opcionales. Solo se
aplican los campos efectivamente enviados (`exclude_unset=True`). `completed_at` no se puede
fijar directamente: se gestiona automáticamente al completar o revertir una tarea.

Ejemplo:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title": "Comprar leche", "priority": "high"}'
```

```bash
curl 'http://127.0.0.1:8000/api/v1/tasks?status=pending&limit=20&offset=0'
```

### Formato de error

Todas las respuestas de error usan el mismo envelope:

```json
{
  "detail": "title must not be empty",
  "code": "validation_error",
  "fields": {"title": "must not be empty"}
}
```

`fields` es opcional. Los errores de validación de FastAPI/Pydantic también se convierten a
este formato y devuelven juntos todos los campos inválidos.

---

## 15. Estado actual y funcionalidades pendientes

Implementado y verificado:

- Etapas 1-4: configuración, base de datos, modelo, repositorio, servicio y tests.
- Etapa 5: schemas, capa API, `main.py`, healthcheck, tests HTTP y contrato OpenAPI versionado.
- `uv run ruff check .` y `uv run pytest -v` en verde.

Pendiente:

- Crear una colección **nueva** de Postman bajo `postman/` con environment local
  (`baseUrl=http://127.0.0.1:8000`), derivada de `docs/openapi.json`. Requiere solicitud
  explícita; no se reutiliza la colección “Task Manager” existente.
- No hay mocks, monitores ni documentación publicada.
- Mejoras menores relevadas en auditorías y pendientes de aprobación: configuración explícita
  de Ruff en `pyproject.toml`, declaración directa de Pydantic y ajustes de acoplamiento/engine.

Según `AGENTS.md`, antes de proponer un commit deben estar en verde `uv run ruff check .` y
`uv run pytest`. No se realizan commits ni pushes sin autorización explícita.
