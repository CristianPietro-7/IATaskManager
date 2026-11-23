# AGENTS.md — AI Task Manager API

Documento de contexto y reglas de trabajo para agentes que participen en este repositorio.
Toda decisión aquí refleja la arquitectura aprobada. Cualquier cambio de fondo debe
proponerse y aprobarse antes de implementarse.

---

## 1. Objetivo del proyecto

Construir una API REST para administrar tareas, con un MVP simple, predecible y
fácil de probar.

**Decisiones aprobadas para el MVP:**

- Sin autenticación ni multiusuario.
- Identificadores `Integer` autoincrementales.
- Estados: `pending`, `in_progress`, `completed`.
- Prioridades: `low`, `medium`, `high`; valor por defecto `medium`.
- Fechas almacenadas y expuestas en UTC.
- Paginación y filtros incluidos desde el primer endpoint de listado.
- SQLite + SQLAlchemy síncrono.
- Actualizaciones parciales mediante `PATCH`.
- Sin Alembic: creación de tablas controlada por configuración solo en desarrollo.
- Colección Postman nueva; no se reutiliza la colección “Task Manager” existente.

**Estado actual del repositorio:** solo existen `pyproject.toml`, `uv.lock`,
`.python-version` y este archivo. Los directorios `src/`, `tests/` y `docs/`
están vacíos y la rama `master` aún no tiene commits.

**No objetivos del MVP:** autenticación, roles, proyectos, notas, webhooks,
migraciones automáticas, concurrencia distribuida ni despliegue.

---

## 2. Tecnologías

| Uso | Tecnología | Referencia instalada |
|---|---|---|
| Lenguaje | Python | 3.14 (`.python-version`) |
| Framework HTTP | FastAPI | 0.165.0 |
| ORM | SQLAlchemy (modo síncrono, 2.x) | 2.1.9 |
| Base de datos | SQLite (driver `sqlite3` del stdlib) | — |
| Validación / DTOs | Pydantic v2 | 2.14.4 |
| Servidor ASGI | uvicorn | 0.54.0 |
| Pruebas | pytest + `TestClient` de FastAPI (httpx) | pytest 9.2.0 / httpx 0.28.1 |
| Lint / formato | Ruff | 0.17.6 |
| Gestor de entorno | uv | `uv.lock` |
| Contrato y pruebas HTTP | OpenAPI + Postman/Newman | planificado, no instalado aún |

**No se añaden dependencias sin aprobación explícita.** En particular: sin
Alembic, sin `pydantic-settings`, sin `pytest-asyncio`, sin `pytest-cov` y sin
librerías de autenticación mientras no se soliciten.

---

## 3. Arquitectura

### 3.1 Principios

- Arquitectura por capas: `api → services → repositories → models`.
- `schemas` es un contrato transversal; ninguna capa inferior importa a una superior.
- Los endpoints son delgados: validan, delegan y serializan.
- Los servicios contienen las reglas de negocio y no conocen HTTP ni SQL.
- El repositorio es el único que construye consultas.
- El modelo ORM solo representa la tabla; no valida payloads de API.

### 3.2 Estructura

```
src/ai_task_manager/
├── main.py                 # fábrica de la app, lifespan, routers, /health
├── config.py               # configuración desde variables de entorno
├── exceptions.py           # errores de dominio y handlers globales
├── db/
│   ├── base.py             # DeclarativeBase, convenciones, mixin de timestamps
│   └── session.py          # engine, SessionLocal, dependencia get_session
├── models/
│   └── task.py             # modelo ORM de tasks
├── schemas/
│   ├── common.py           # ErrorResponse, envelope de paginación
│   └── task.py             # TaskCreate, TaskUpdate, TaskRead, TaskPage, enums
├── repositories/
│   └── task_repository.py  # CRUD, filtros, orden y paginación
├── services/
│   └── task_service.py     # reglas de negocio y coordinación
├── api/
│   ├── deps.py             # composición session → repository → service
│   └── v1/
│       ├── router.py       # agregador de rutas v1
│       └── tasks.py        # endpoints de tareas
tests/
├── conftest.py
├── unit/
├── integration/
└── api/
docs/                       # openapi.json versionado
postman/                    # colección y environments versionados
```

### 3.3 Responsabilidades

| Módulo | Responsabilidad |
|---|---|
| `config.py` | Leer y validar entorno (`DATABASE_URL`, `ENV`, prefijo API, flag de desarrollo). |
| `db/base.py` | Declarar `Base`, convención de constraints y columnas de auditoría. |
| `db/session.py` | Crear engine/sesiones; exponer `get_session` con commit, rollback y cierre. |
| `models/task.py` | Mapear la tabla `tasks`, tipos, índices e integridad. |
| `schemas/task.py` | Definir DTOs de entrada/salida, enums y conversión desde ORM. |
| `schemas/common.py` | Formato de error y envelope de paginación consistentes. |
| `repositories/task_repository.py` | Consultas y persistencia; devolver entidades o `None`. |
| `services/task_service.py` | Normalización, reglas de estado, `completed_at` y excepciones de dominio. |
| `api/deps.py` | Inyectar repositorio y servicio mediante `Depends`. |
| `api/v1/tasks.py` | Manejar request/response, códigos HTTP y errores mapeados. |
| `exceptions.py` | Excepciones tipadas y handlers que producen siempre el mismo JSON de error. |
| `main.py` | `create_app()`, lifespan, inclusión de routers, documentación y healthcheck. |

### 3.4 Modelo de datos

Tabla `tasks`:

| Campo | Tipo | Regla |
|---|---|---|
| `id` | Integer PK autoincrement | Identificador expuesto. |
| `title` | String(200) | Obligatorio; no vacío tras `strip()`. |
| `description` | Text | Opcional. |
| `status` | String(20) | `pending` / `in_progress` / `completed`; default `pending`. |
| `priority` | String(10) | `low` / `medium` / `high`; default `medium`. |
| `due_at` | DateTime | Opcional, UTC. |
| `created_at` | DateTime | UTC, asignado al insertar. |
| `updated_at` | DateTime | UTC, actualizado en cada cambio. |
| `completed_at` | DateTime | Opcional; se fija al completar y se limpia al revertir. |

Índices: `status` y `created_at DESC`. Sin `UNIQUE` sobre `title`.

DTOs: `TaskCreate`, `TaskUpdate` (todo opcional, `exclude_unset=True` en
`PATCH`), `TaskRead`, `TaskPage` (`items`, `total`, `limit`, `offset`) y
`ErrorResponse` (`detail`, `code` opcional, `fields` opcional).

### 3.5 Endpoints

Prefijo `/api/v1`, contenido `application/json`.

| Método | Ruta | Éxito | Errores |
|---|---|---|---|
| `GET` | `/health` | `200` | `503` si la BD no responde |
| `POST` | `/tasks` | `201` + `Location` | `400`, `422` |
| `GET` | `/tasks` | `200` (`TaskPage`) | `422` |
| `GET` | `/tasks/{task_id}` | `200` | `404`, `422` |
| `PATCH` | `/tasks/{task_id}` | `200` | `404`, `422` |
| `DELETE` | `/tasks/{task_id}` | `204` sin cuerpo | `404`, `422` |

Filtros de listado: `status`, `priority`, `limit` (default 20, máx. 100),
`offset` y `sort=created_at:desc`. Documentación automática en `/docs`,
`/redoc` y `/openapi.json`.

---

## 4. Convenciones de código

- Seguir PEP 8 y Ruff; máximo 100 caracteres por línea hasta configurar Ruff.
- `snake_case` para módulos, funciones y variables; `PascalCase` para clases;
  `UPPER_CASE` para constantes.
- Type hints en funciones y métodos públicos. Evitar `Any` salvo justificación.
- SQLAlchemy 2.x declarativo con `Mapped[...]` y `mapped_column(...)`.
- Pydantic v2 con `ConfigDict(from_attributes=True, extra="forbid")` en DTOs de
  entrada; validadores con `field_validator` / `model_validator`.
- Fechas: helper único `utc_now()`; almacenar UTC naive en SQLite y serializar
  en ISO con sufijo `Z`. Nunca mezclar naive y aware.
- Los errores de negocio se lanzan como excepciones tipadas desde el servicio y
  se traducen a HTTP en la capa `api`. Nunca `raise HTTPException` en servicios.
- Sin SQL crudo fuera del repositorio. Sin acceso a `Session` en endpoints.
- Sin `print()`: usar `logging` cuando sea necesario.
- Nombres de pruebas descriptivos: `test_<comportamiento>_<condicion>`.
- No copiar patrones de la colección Postman antigua ni de otros proyectos.

---

## 5. Reglas de Git

- Estado inicial: rama `master` sin commits. El primer commit debe registrar la
  base del proyecto de forma limpia.
- Trabajar en ramas cortas: `feature/<alcance>`, `fix/<alcance>`,
  `test/<alcance>`, `docs/<alcance>`.
- Mensajes en formato *Conventional Commits*: `feat:`, `fix:`, `test:`, `docs:`,
  `refactor:`, `chore:`.
- Commits atómicos: un propósito por commit. No mezclar código, pruebas y
  documentación si pueden separarse.
- Antes de proponer un commit: `ruff check .` y `.venv/bin/pytest` en verde.
- No hacer commit ni push sin que el usuario lo solicite explícitamente.
- Prohibido: `git push --force`, `git reset --hard`, reescribir historial
  compartido y `--no-verify`.
- Nunca versionar `.venv/`, `__pycache__/`, `.pytest_cache/`, `.env`,
  `*.db`, `*.sqlite3` ni secretos.
- No modificar `pyproject.toml` ni `uv.lock` sin aprobación de nuevas
  dependencias.

---

## 6. Estrategia de testing

1. **Unitarias (`tests/unit`):** servicios con repositorio falso en memoria.
   Cubren normalización de `title`, defaults, transiciones de estado y
   `completed_at`. Sin BD ni HTTP.
2. **Integración (`tests/integration`):** repositorio contra SQLite en memoria
   (`StaticPool`), con `create_all`/`drop_all` o rollback por prueba. Cubren
   filtros, orden, paginación y constraints.
3. **API (`tests/api`):** `TestClient` con `dependency_overrides` para inyectar
   la sesión de prueba. Cubren `200/201/204/404/422`, `Location`, envelope de
   paginación y formato de errores.

Reglas:

- Toda regla de negocio nueva o bug corregido debe tener una prueba asociada.
- Ninguna prueba depende de la base de datos real ni del orden de ejecución.
- Patrón AAA (arrange, act, assert); sin `sleep()` ni esperas arbitrarias.
- Para fechas, inyectar un reloj o comparar rangos: no depender de `now()` exacto.
- Comandos de referencia: `.venv/bin/ruff check .` y `.venv/bin/pytest`.
- Objetivo de cobertura: ≥85% en `services` y `repositories`; 100% de las rutas
  principales.

---

## 7. Reglas de uso de Postman

- Crear una colección **nueva** en `postman/`. **No reutilizar, modificar ni
  publicar** la colección existente “Task Manager” ni su workspace.
- El contrato fuente es `docs/openapi.json`, generado desde FastAPI. La
  colección se deriva de él; si cambia el contrato, se actualiza primero el
  OpenAPI y luego la colección.
- Versionar en Git: colección v2.1 y environment local con
  `baseUrl=http://127.0.0.1:8000`. Sin credenciales ni secretos en archivos.
- Organizar la colección en carpetas `Health` y `Tasks` (create, list, get,
  update, delete). Cada request lleva asserts de código de estado y de campos
  obligatorios; el ID creado se guarda en una variable para encadenar requests.
- La colección se ejecuta contra la app local levantada con uvicorn, **después**
  de que Pytest esté en verde.
- Reportar el resultado de los assertions, no solo que el run terminó. Un run
  completado con asserts fallidos es un fallo.
- No crear mocks, monitores ni documentación publicada salvo petición explícita.
- Publicar o sincronizar cambios hacia un workspace compartido requiere
  consentimiento explícito del usuario en el momento de la acción.

---

## 8. Restricciones para los agentes

- No implementar la API ni crear módulos de `src/` hasta recibir una tarea
  concreta que lo pida.
- No crear archivos distintos a los solicitados; no borrar ni sobrescribir
  trabajo existente sin revisarlo antes.
- No modificar recursos de Postman ni el workspace; solo archivos locales bajo
  `postman/` cuando se soliciten.
- No instalar dependencias ni cambiar `pyproject.toml` o `uv.lock` sin
  aprobación.
- No ejecutar operaciones destructivas: borrados recursivos, `git reset --hard`,
  force push, drops de BD ni sobreescritura de ramas.
- No exponer secretos ni guardar credenciales en variables, archivos o logs.
- No hacer commit ni push sin autorización explícita.
- Respetar la dirección de dependencias y las decisiones aprobadas; cualquier
  desviación se presenta como propuesta y espera aprobación.
- Si una herramienta no está disponible o una acción no puede verificarse,
  reportarlo con claridad; no inventar resultados.
- Al finalizar cada tarea, indicar qué archivos se cambiaron, qué
  verificaciones se ejecutaron y qué queda pendiente.
