"""Especificación OpenAPI 3.0 de la API pública (se sirve en /api/v1/openapi.json y /api/docs)."""


def _ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def _q(name, desc, typ="string", **kw):
    return {"name": name, "in": "query", "required": False, "description": desc, "schema": {"type": typ, **kw}}


def _p(name, desc="Identificador"):
    return {"name": name, "in": "path", "required": True, "description": desc, "schema": {"type": "integer"}}


def _json(schema, example=None):
    c = {"schema": schema}
    if example is not None:
        c["example"] = example
    return {"content": {"application/json": c}}


def _ok(desc, schema=None, code="200"):
    return {code: {"description": desc, **(_json(schema) if schema else {})}}


ERR = {"401": {"$ref": "#/components/responses/Unauthorized"},
       "403": {"$ref": "#/components/responses/Forbidden"},
       "422": {"$ref": "#/components/responses/Invalid"}}
NF = {"404": {"$ref": "#/components/responses/NotFound"}}
PAGING = [_q("limit", "Máximo de elementos (1-1000).", "integer", default=100),
          _q("offset", "Elementos a saltar.", "integer", default=0)]


def _page(item):
    return {"type": "object", "properties": {"items": {"type": "array", "items": item},
                                             "total": {"type": "integer"}, "limit": {"type": "integer"},
                                             "offset": {"type": "integer"}}}


def _list(item):
    return {"type": "object", "properties": {"items": {"type": "array", "items": item}, "total": {"type": "integer"}}}


def spec():
    ts = {"type": "string", "format": "date-time"}
    schemas = {
        "Error": {"type": "object", "properties": {"error": {"type": "string"},
                                                   "errors": {"type": "array", "items": {"type": "object"}}}},
        "Employee": {"type": "object", "properties": {
            "id": {"type": "integer"}, "external_id": {"type": "string", "nullable": True,
                                                       "description": "Código de empleado en el sistema de RRHH."},
            "name": {"type": "string"}, "email": {"type": "string", "nullable": True},
            "department": {"type": "string"}, "job_role_id": {"type": "integer", "nullable": True},
            "job_role": {"type": "string", "nullable": True},
            "assessed": {"type": "integer", "description": "Habilidades evaluadas."},
            "known": {"type": "integer", "description": "Habilidades con nivel ≥ 1."},
            "experts": {"type": "integer", "description": "Habilidades con nivel ≥ 4."},
            "stale": {"type": "integer", "description": "Evaluaciones desactualizadas."},
            "last_evaluated_at": {**ts, "nullable": True}, "oldest_evaluated_at": {**ts, "nullable": True},
            "created_at": ts, "updated_at": ts}},
        "EmployeeInput": {"type": "object", "required": ["name"], "properties": {
            "name": {"type": "string"}, "email": {"type": "string"}, "external_id": {"type": "string"},
            "department": {"type": "string"}, "job_role_id": {"type": "integer", "nullable": True},
            "job_role": {"type": "string", "description": "Alternativa a job_role_id: nombre del puesto (se crea si no existe)."}}},
        "EmployeeDetail": {"allOf": [_ref("Employee"), {"type": "object", "properties": {
            "assessments": {"type": "array", "items": {"type": "object", "properties": {
                "skill_id": {"type": "integer"}, "skill": {"type": "string"}, "category": {"type": "string"},
                "level": {"type": "integer"}, "evaluated_at": ts, "evaluated_by": {"type": "string"},
                "source": {"type": "string"}, "stale": {"type": "boolean"},
                "required_level": {"type": "integer", "nullable": True}}}},
            "requirements": {"type": "array", "items": _ref("Requirement")},
            "coverage": {"type": "integer", "nullable": True, "description": "% de cumplimiento del puesto."},
            "gap_points": {"type": "integer"}, "below": {"type": "integer"}}}]},
        "Skill": {"type": "object", "properties": {
            "id": {"type": "integer"}, "name": {"type": "string"}, "category": {"type": "string"},
            "description": {"type": "string"}, "people": {"type": "integer"}, "experts": {"type": "integer"},
            "stale": {"type": "integer"}}},
        "SkillInput": {"type": "object", "required": ["name"], "properties": {
            "name": {"type": "string"}, "category": {"type": "string"}, "description": {"type": "string"}}},
        "Requirement": {"type": "object", "properties": {
            "skill_id": {"type": "integer"}, "skill": {"type": "string"}, "required_level": {"type": "integer", "minimum": 1, "maximum": 5}}},
        "JobRole": {"type": "object", "properties": {
            "id": {"type": "integer"}, "name": {"type": "string"}, "employees": {"type": "integer"},
            "requirements": {"type": "array", "items": _ref("Requirement")}}},
        "JobRoleInput": {"type": "object", "properties": {
            "name": {"type": "string"},
            "requirements": {"type": "array", "description": "Sustituye todos los requisitos. Usa skill_id o skill (nombre).",
                             "items": {"type": "object", "properties": {
                                 "skill_id": {"type": "integer"}, "skill": {"type": "string"},
                                 "required_level": {"type": "integer", "minimum": 0, "maximum": 5}}}}}},
        "Assessment": {"type": "object", "properties": {
            "employee_id": {"type": "integer"}, "employee": {"type": "string"}, "employee_email": {"type": "string"},
            "employee_external_id": {"type": "string"}, "skill_id": {"type": "integer"}, "skill": {"type": "string"},
            "category": {"type": "string"}, "level": {"type": "integer", "minimum": 0, "maximum": 5},
            "evaluated_at": ts, "evaluated_by": {"type": "string"},
            "source": {"type": "string", "enum": ["web", "api", "import", "demo"]}, "stale": {"type": "boolean"}}},
        "AssessmentInput": {"type": "object", "required": ["level"], "description":
            "Identifica al empleado con employee_id, employee_external_id o employee_email, "
            "y la habilidad con skill_id o skill (nombre).", "properties": {
                "employee_id": {"type": "integer"}, "employee_external_id": {"type": "string"},
                "employee_email": {"type": "string"}, "skill_id": {"type": "integer"}, "skill": {"type": "string"},
                "category": {"type": "string", "description": "Solo si se crea la habilidad."},
                "level": {"type": "integer", "minimum": 0, "maximum": 5},
                "evaluated_at": {**ts, "description": "Fecha de la evaluación. Por defecto, ahora. Si es anterior a la "
                                                      "ya registrada, la fila se ignora (skipped)."}}},
        "UpsertResult": {"type": "object", "properties": {k: {"type": "integer"} for k in
                                                          ("processed", "created", "changed", "reviewed", "skipped", "unchanged")}},
    }
    tags = [{"name": n, "description": d} for n, d in (
        ("Empleados", "Personas de la plantilla."), ("Habilidades", "Catálogo de tecnologías y conocimientos."),
        ("Evaluaciones", "Nivel (0-5) de cada empleado en cada habilidad, con su fecha de evaluación."),
        ("Puestos", "Puestos de trabajo, nivel requerido y análisis de brechas."),
        ("Informes", "Matriz completa, resumen y exportación."))]
    paths = {
        "/employees": {
            "get": {"tags": ["Empleados"], "summary": "Listar empleados", "parameters": [
                _q("q", "Búsqueda en nombre, email, departamento o código."), _q("department", "Departamento exacto."),
                _q("job_role_id", "Puesto.", "integer"), _q("email", "Email exacto."), _q("external_id", "Código exacto."),
                _q("updated_since", "Modificados desde esta fecha.", format="date-time"),
                _q("has_stale", "true = solo con evaluaciones desactualizadas.", "boolean"), *PAGING],
                "responses": {**_ok("Lista paginada", _page(_ref("Employee"))), **ERR}},
            "post": {"tags": ["Empleados"], "summary": "Crear empleado", "requestBody": _json(_ref("EmployeeInput"),
                     {"name": "Laura Vidal", "email": "laura.vidal@empresa.com", "external_id": "E101",
                      "department": "Desarrollo", "job_role": "Desarrollador backend"}),
                     "responses": {**_ok("Creado", _ref("Employee"), "201"), **ERR,
                                   "409": {"description": "Email o código duplicado"}}}},
        "/employees/{id}": {
            "parameters": [_p("id")],
            "get": {"tags": ["Empleados"], "summary": "Ficha con evaluaciones y cumplimiento del puesto",
                    "responses": {**_ok("Empleado", _ref("EmployeeDetail")), **ERR, **NF}},
            "patch": {"tags": ["Empleados"], "summary": "Modificar (solo los campos enviados)",
                      "requestBody": _json(_ref("EmployeeInput")), "responses": {**_ok("Actualizado", _ref("Employee")), **ERR, **NF}},
            "put": {"tags": ["Empleados"], "summary": "Modificar (igual que PATCH)",
                    "requestBody": _json(_ref("EmployeeInput")), "responses": {**_ok("Actualizado", _ref("Employee")), **ERR, **NF}},
            "delete": {"tags": ["Empleados"], "summary": "Eliminar empleado y sus evaluaciones",
                       "responses": {"204": {"description": "Eliminado"}, **ERR, **NF}}},
        "/employees/{id}/history": {"parameters": [_p("id")], "get": {
            "tags": ["Empleados"], "summary": "Histórico de cambios de nivel (últimos 200)",
            "responses": {**_ok("Histórico", {"type": "object"}), **ERR}}},
        "/employees/{id}/review": {"parameters": [_p("id")], "post": {
            "tags": ["Evaluaciones"], "summary": "Confirmar niveles vigentes (renueva la fecha sin cambiar el nivel)",
            "requestBody": {"required": False, **_json({"type": "object", "properties": {
                "skill_ids": {"type": "array", "items": {"type": "integer"}, "description": "Vacío = todas."}}})},
            "responses": {**_ok("Revisadas", {"type": "object", "properties": {"reviewed": {"type": "integer"}}}), **ERR}}},
        "/skills": {
            "get": {"tags": ["Habilidades"], "summary": "Listar habilidades",
                    "responses": {**_ok("Lista", _list(_ref("Skill"))), **ERR}},
            "post": {"tags": ["Habilidades"], "summary": "Crear habilidad",
                     "requestBody": _json(_ref("SkillInput"), {"name": "Terraform", "category": "Infraestructura"}),
                     "responses": {**_ok("Creada", _ref("Skill"), "201"), **ERR}}},
        "/skills/{id}": {"parameters": [_p("id")],
                         "patch": {"tags": ["Habilidades"], "summary": "Modificar habilidad",
                                   "requestBody": _json(_ref("SkillInput")), "responses": {**_ok("Actualizada", _ref("Skill")), **ERR, **NF}},
                         "delete": {"tags": ["Habilidades"], "summary": "Eliminar habilidad y sus evaluaciones",
                                    "responses": {"204": {"description": "Eliminada"}, **ERR, **NF}}},
        "/assessments": {
            "get": {"tags": ["Evaluaciones"], "summary": "Listar evaluaciones", "parameters": [
                _q("employee_id", "", "integer"), _q("employee_email", ""), _q("employee_external_id", ""),
                _q("skill_id", "", "integer"), _q("skill", "Nombre de la habilidad."), _q("category", ""),
                _q("min_level", "", "integer"), _q("max_level", "", "integer"),
                _q("stale", "true = solo desactualizadas; false = solo vigentes.", "boolean"),
                _q("evaluated_since", "", format="date-time"), _q("evaluated_before", "", format="date-time"), *PAGING],
                "responses": {**_ok("Lista paginada", _page(_ref("Assessment"))), **ERR}},
            "post": {"tags": ["Evaluaciones"], "summary": "Registrar evaluaciones (una o muchas)",
                     "description": "Acepta un objeto, una lista o {\"items\": [...]} (máx. 5000). **Todo o nada**: si alguna "
                                    "fila es incorrecta devuelve 422 con la lista de errores y no guarda nada. "
                                    "Enviar el mismo nivel renueva la fecha de evaluación (reviewed).",
                     "parameters": [_q("create_missing_skills", "Crear las habilidades que no existan.", "boolean", default=False)],
                     "requestBody": _json({"oneOf": [_ref("AssessmentInput"), {"type": "array", "items": _ref("AssessmentInput")},
                                                     {"type": "object", "properties": {"items": {"type": "array", "items": _ref("AssessmentInput")}}}]},
                                          {"items": [{"employee_email": "lucia.martin@empresa.com", "skill": "Kubernetes", "level": 3},
                                                     {"employee_external_id": "E002", "skill_id": 1, "level": 4,
                                                      "evaluated_at": "2026-09-01T09:00:00Z"}]}),
                     "responses": {**_ok("Resultado", _ref("UpsertResult")), **ERR}}},
        "/assessments/{employee_id}/{skill_id}": {
            "parameters": [_p("employee_id", "Empleado"), _p("skill_id", "Habilidad")],
            "put": {"tags": ["Evaluaciones"], "summary": "Fijar el nivel de un empleado en una habilidad",
                    "requestBody": _json({"type": "object", "required": ["level"], "properties": {
                        "level": {"type": "integer", "minimum": 0, "maximum": 5}, "evaluated_at": ts}}, {"level": 4}),
                    "responses": {**_ok("Evaluación guardada", {"type": "object"}), **ERR, **NF}},
            "delete": {"tags": ["Evaluaciones"], "summary": "Eliminar la evaluación (pasa a «sin evaluar»)",
                       "responses": {"204": {"description": "Eliminada"}, **ERR, **NF}}},
        "/job-roles": {
            "get": {"tags": ["Puestos"], "summary": "Listar puestos con sus requisitos",
                    "responses": {**_ok("Lista", _list(_ref("JobRole"))), **ERR}},
            "post": {"tags": ["Puestos"], "summary": "Crear puesto", "requestBody": _json(_ref("JobRoleInput"),
                     {"name": "Arquitecto cloud", "requirements": [{"skill": "AWS", "required_level": 4},
                                                                    {"skill": "Kubernetes", "required_level": 3}]}),
                     "responses": {**_ok("Creado", _ref("JobRole"), "201"), **ERR}}},
        "/job-roles/{id}": {"parameters": [_p("id")],
                            "get": {"tags": ["Puestos"], "summary": "Ver puesto", "responses": {**_ok("Puesto", _ref("JobRole")), **ERR, **NF}},
                            "patch": {"tags": ["Puestos"], "summary": "Modificar nombre y/o requisitos",
                                      "requestBody": _json(_ref("JobRoleInput")), "responses": {**_ok("Actualizado", _ref("JobRole")), **ERR, **NF}},
                            "delete": {"tags": ["Puestos"], "summary": "Eliminar puesto",
                                       "responses": {"204": {"description": "Eliminado"}, **ERR, **NF}}},
        "/job-roles/{id}/gaps": {"parameters": [_p("id")], "get": {
            "tags": ["Puestos"], "summary": "Análisis de brechas frente al puesto",
            "parameters": [_q("scope", "role = empleados del puesto; all = toda la plantilla.", enum=["role", "all"], default="role")],
            "responses": {**_ok("Brechas", {"type": "object"}), **ERR, **NF}}},
        "/matrix": {"get": {"tags": ["Informes"], "summary": "Matriz completa empleados × habilidades",
                            "description": "assessments está indexado por \"<employee_id>-<skill_id>\".",
                            "responses": {**_ok("Matriz", {"type": "object"}), **ERR}}},
        "/dashboard": {"get": {"tags": ["Informes"], "summary": "Indicadores del resumen",
                               "responses": {**_ok("Resumen", {"type": "object"}), **ERR}}},
        "/export": {"get": {"tags": ["Informes"], "summary": "Descargar Excel o CSV", "parameters": [
            _q("format", "", enum=["xlsx", "csv"], default="xlsx"),
            _q("layout", "Solo CSV: matrix (una columna por habilidad) o long (una fila por evaluación, con fecha).",
               enum=["matrix", "long"], default="matrix")],
            "responses": {"200": {"description": "Archivo"}, **ERR}}},
        "/settings": {"get": {"tags": ["Informes"], "summary": "Meses tras los que una evaluación se considera desactualizada",
                              "responses": {**_ok("Ajustes", {"type": "object", "properties": {"stale_months": {"type": "integer"}}}), **ERR}}},
    }
    return {
        "openapi": "3.0.3",
        "info": {"title": "SkillMatrix API", "version": "1.0",
                 "description": "API para consultar y registrar las habilidades de los empleados (escala 0-5).\n\n"
                                "**Autenticación**: cabecera `Authorization: Bearer <token>`. Los tokens los crea un "
                                "administrador en *Administración → Aplicaciones*. Un token `read` solo consulta; "
                                "`write` también modifica.\n\n"
                                "**Fechas**: ISO 8601. Una evaluación está *desactualizada* (`stale`) si su "
                                "`evaluated_at` es anterior al umbral configurado (12 meses por defecto).\n\n"
                                "**Niveles**: 0 No lo conoce · 1 Nociones básicas · 2 Principiante · 3 Intermedio · "
                                "4 Avanzado · 5 Experto. Sin evaluación = sin evaluar."},
        "servers": [{"url": "/api/v1"}],
        "security": [{"bearerAuth": []}],
        "tags": tags,
        "paths": paths,
        "components": {
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "smx_…"}},
            "schemas": schemas,
            "responses": {
                "Unauthorized": {"description": "Falta el token o no es válido", **_json(_ref("Error"))},
                "Forbidden": {"description": "El token no tiene permiso", **_json(_ref("Error"))},
                "NotFound": {"description": "No encontrado", **_json(_ref("Error"))},
                "Invalid": {"description": "Datos no válidos", **_json(_ref("Error"))}}},
    }
