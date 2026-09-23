# Guía de la API

SkillMatrix expone una API REST en `/api/v1`. La interfaz web usa esta misma API, así que todo lo que se
puede hacer desde la web se puede hacer también desde otra aplicación.

- **Referencia completa e interactiva** (Swagger UI): `https://<servidor>/api/docs`
- **Especificación OpenAPI 3** (para Postman, Insomnia o generadores de clientes): `https://<servidor>/api/v1/openapi.json`

![Documentación interactiva](img/api-docs.png)

## Autenticación

Cada aplicación usa **su propio token**, que crea un administrador en *Administración → Aplicaciones*:

![Gestión de tokens](img/tokens.png)

| Permiso | Puede |
|---|---|
| Solo lectura (`read`) | Consultar empleados, habilidades, evaluaciones, puestos e informes. |
| Lectura y escritura (`write`) | Además, crear, modificar y borrar esos datos. |

Ningún token permite administrar usuarios, tokens ni ajustes. El token se envía en cada petición:

```
Authorization: Bearer smx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- El token completo **solo se muestra al crearlo**. SkillMatrix guarda únicamente su huella (SHA-256).
- Guardadlo como secreto en la aplicación que lo use; no lo pongáis en el código ni en repositorios.
- Si se filtra, revocadlo en *Administración → Aplicaciones* y cread otro. Para revocarlos todos a la vez:
  `python gestion.py revocar-tokens`.
- Los cambios que hace una aplicación quedan registrados como `api:<nombre del token>`.

## Convenciones

| Aspecto | Regla |
|---|---|
| Formato | JSON en UTF-8. Las peticiones con cuerpo llevan `Content-Type: application/json`. |
| Fechas | ISO 8601 (`2026-09-01`, `2026-09-01T10:00:00Z`, `2026-09-01T12:00:00+02:00`). Sin zona horaria se interpretan como UTC. Las respuestas incluyen zona horaria. |
| Paginación | Los listados grandes aceptan `limit` (1-1000, por defecto 100) y `offset`, y devuelven `{"items": [...], "total": N, "limit": …, "offset": …}`. |
| Modificaciones | `PATCH` (o `PUT`) cambia solo los campos enviados. |
| Errores | `{"error": "mensaje"}`. En cargas masivas, además `errors: [{"index": 3, "error": "…"}]`. |
| Códigos HTTP | `200` correcto · `201` creado · `204` borrado · `401` falta el token o no es válido · `403` sin permiso · `404` no existe · `409` duplicado · `422` datos no válidos. |

### Identificar empleados y habilidades

Para no obligar a guardar los identificadores internos de SkillMatrix, las evaluaciones admiten varias formas de identificación:

| Entidad | Opciones (se usa la primera que venga) |
|---|---|
| Empleado | `employee_id` (interno) · `employee_external_id` (código de vuestro sistema de RRHH) · `employee_email` |
| Habilidad | `skill_id` (interno) · `skill` (nombre, sin distinguir mayúsculas) |

Se recomienda rellenar el **código de empleado** (`external_id`) de todos los empleados, porque no cambia
cuando cambia el email.

## Recursos

| Método y ruta | Descripción |
|---|---|
| `GET /employees` | Listado. Filtros: `q` (texto), `department`, `job_role_id`, `email`, `external_id`, `updated_since`, `has_stale=true`. |
| `GET /employees/{id}` | Ficha: evaluaciones con fecha, requisitos del puesto, % de cumplimiento (`coverage`) y habilidades por debajo (`below`). |
| `POST /employees` | Alta. Campos: `name` (obligatorio), `email`, `external_id`, `department`, `job_role_id` o `job_role` (nombre; se crea si no existe). |
| `PATCH /employees/{id}` | Modificación parcial. |
| `DELETE /employees/{id}` | Baja, con sus evaluaciones. |
| `GET /employees/{id}/history` | Histórico de cambios de nivel. |
| `POST /employees/{id}/review` | Confirma los niveles actuales con fecha de hoy (opcional: `{"skill_ids": [..]}`). |
| `GET /assessments` | Evaluaciones. Filtros: `employee_id`, `employee_email`, `employee_external_id`, `skill_id`, `skill`, `category`, `min_level`, `max_level`, `stale`, `evaluated_since`, `evaluated_before`. |
| `POST /assessments` | Alta o actualización de una o muchas evaluaciones (ver abajo). |
| `PUT /assessments/{employee_id}/{skill_id}` | Fija un nivel: `{"level": 4}` (opcional `evaluated_at`). |
| `DELETE /assessments/{employee_id}/{skill_id}` | Quita la evaluación (pasa a «sin evaluar»). |
| `GET /skills` · `POST /skills` · `PATCH /skills/{id}` · `DELETE /skills/{id}` | Catálogo de habilidades (`name`, `category`, `description`). |
| `GET /job-roles` · `GET /job-roles/{id}` | Puestos con sus requisitos. |
| `POST /job-roles` · `PATCH /job-roles/{id}` · `DELETE /job-roles/{id}` | Gestión de puestos. `requirements` sustituye la lista completa de requisitos. |
| `GET /job-roles/{id}/gaps?scope=role\|all` | Brechas de los empleados del puesto, o de toda la plantilla como candidatos. |
| `GET /matrix` | Matriz completa (empleados, habilidades y evaluaciones indexadas por `"<empleado>-<habilidad>"`). |
| `GET /dashboard` | Indicadores del resumen. |
| `GET /export?format=xlsx\|csv&layout=matrix\|long` | Descarga de la matriz o de las evaluaciones con fecha. |
| `GET /settings` | Plazo (en meses) a partir del cual una evaluación está desactualizada. |

## Registrar evaluaciones: `POST /assessments`

Acepta un objeto, una lista o `{"items": [...]}`, con un máximo de 5000 elementos por petición.

```json
[
  {"employee_email": "ana.perez@empresa.com", "skill": "Kubernetes", "level": 3},
  {"employee_external_id": "E002", "skill_id": 7, "level": 4, "evaluated_at": "2026-09-01T09:00:00Z"}
]
```

Respuesta:

```json
{"processed": 2, "created": 1, "changed": 1, "reviewed": 0, "skipped": 0, "unchanged": 0}
```

| Resultado | Significado |
|---|---|
| `created` | No tenía evaluación en esa habilidad. |
| `changed` | Ha cambiado el nivel. Queda en el histórico. |
| `reviewed` | Mismo nivel: solo se renueva la fecha de evaluación. |
| `skipped` | Se ha ignorado porque su `evaluated_at` es anterior a la evaluación ya registrada. Así, reenviar datos antiguos no borra una evaluación más reciente. |

Reglas:

- **Todo o nada.** Si alguna fila es incorrecta (empleado inexistente, nivel fuera de 0-5, fecha futura…),
  la respuesta es `422` con la lista de errores y no se guarda ninguna fila.
- Si una habilidad no existe, es un error, salvo que se añada `?create_missing_skills=true`. En ese caso
  se crea, con la categoría del campo `category` si se envía.
- Sin `evaluated_at`, la fecha de evaluación es la del momento de la petición.

## Evaluaciones desactualizadas

Cada evaluación tiene `evaluated_at` y un indicador `stale`, que vale `true` cuando es anterior al plazo
configurado (12 meses por defecto; consúltalo en `GET /settings`).

```bash
# Personas con alguna evaluación desactualizada
GET /employees?has_stale=true

# Evaluaciones desactualizadas de una habilidad
GET /assessments?skill=Oracle&stale=true

# Evaluado en el último trimestre
GET /assessments?evaluated_since=2026-07-01
```

## Ejemplos

### curl

```bash
TOKEN="smx_..."
BASE="https://skillmatrix.empresa.local/api/v1"

# Expertos (nivel ≥ 4) en Kubernetes
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/assessments?skill=Kubernetes&min_level=4"

# Alta de un empleado
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Laura Vidal","email":"laura.vidal@empresa.com","external_id":"E101","department":"QA","job_role":"Tester"}' \
  "$BASE/employees"
```

### Python

```python
import requests

s = requests.Session()
s.headers["Authorization"] = "Bearer smx_..."
BASE = "https://skillmatrix.empresa.local/api/v1"

# Recorrer todas las evaluaciones con paginación
offset, todas = 0, []
while True:
    r = s.get(f"{BASE}/assessments", params={"limit": 500, "offset": offset})
    r.raise_for_status()
    page = r.json()
    todas += page["items"]
    offset += page["limit"]
    if offset >= page["total"]:
        break

# Registrar evaluaciones de un curso terminado
r = s.post(f"{BASE}/assessments", json=[
    {"employee_external_id": "E004", "skill": "Kubernetes", "level": 3, "evaluated_at": "2026-09-20"},
])
if r.status_code == 422:
    print(r.json()["errors"])
r.raise_for_status()
```

### PowerShell

```powershell
$headers = @{ Authorization = "Bearer smx_..." }
$base = "https://skillmatrix.empresa.local/api/v1"

$pendientes = Invoke-RestMethod -Headers $headers -Uri "$base/employees?has_stale=true"
$pendientes.items | Select-Object name, job_role, stale, last_evaluated_at

$body = ConvertTo-Json -InputObject @(@{ employee_email = "ana.perez@empresa.com"; skill = "Oracle"; level = 4 })   # válido en PowerShell 5.1 y 7
Invoke-RestMethod -Method Post -Headers $headers -ContentType "application/json" -Uri "$base/assessments" -Body $body
```

## Escenarios de integración habituales

| Escenario | Cómo hacerlo |
|---|---|
| **Sincronizar la plantilla desde el sistema de RRHH** | Para cada persona, `GET /employees?external_id=…`. Si no existe, `POST /employees`; si existe, `PATCH /employees/{id}` con los cambios. Las bajas, con `DELETE`. Token `write`. |
| **Plataforma de formación que actualiza niveles al aprobar un curso** | `POST /assessments` con `employee_email` o `employee_external_id`, `skill`, `level` y la fecha del examen en `evaluated_at`. Token `write`. |
| **Buscar personas para un proyecto** | `GET /assessments?skill=Oracle&min_level=4&stale=false`. Token `read`. |
| **Cuadro de mando corporativo (Power BI, Grafana…)** | `GET /assessments` paginado o `GET /export?format=csv&layout=long`. Token `read`. |
| **Recordatorios de revisión a managers** | `GET /employees?has_stale=true` periódicamente y enviar el aviso con vuestra herramienta de correo o chat. Token `read`. |

## Llamadas desde el navegador (CORS)

Las integraciones entre servidores no necesitan configuración adicional. Si una aplicación web llama a la API
**desde el navegador** en otro dominio, añade su origen a `CORS_ORIGINS` (ver
[Guía de despliegue](DESPLIEGUE.md#4-configuración)). Ten en cuenta que en ese caso el token queda expuesto
en el navegador: usa un token de solo lectura o, mejor, pasa las llamadas por el servidor de esa aplicación.
