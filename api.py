"""API REST v1. La usa la interfaz web (sesión) y otras aplicaciones (token)."""
from flask import Blueprint, g, jsonify, request, session
from psycopg import errors as pgerr
from werkzeug.security import check_password_hash, generate_password_hash

import excel_io
from auth import new_token, require
from db import commit, conn, q, q1
from services import (LEVELS, ValidationError, as_bool, as_datetime, as_int, assessment_dict,
                      delete_assessment, employee_levels, gap_for, requirements, resolve_employee,
                      resolve_skill, set_assessment, stale_limit, stale_months)

bp = Blueprint("api", __name__, url_prefix="/api/v1")
ROLES = ("admin", "manager", "lector")
MAX_BATCH = 5000


def bad(msg, code=400, **extra):
    return jsonify(error=msg, **extra), code


@bp.errorhandler(ValidationError)
def _validation(e):
    return bad(str(e), 422)


@bp.errorhandler(pgerr.UniqueViolation)
def _unique(e):
    conn().rollback()
    detail = str(e.diag.constraint_name or "")
    msg = {"employees_email_uq": "Ya existe un empleado con ese email.",
           "employees_external_id_key": "Ya existe un empleado con ese código.",
           "skills_name_uq": "Ya existe una habilidad con ese nombre.",
           "job_roles_name_uq": "Ya existe un puesto con ese nombre.",
           "users_username_key": "Ya existe un usuario con ese nombre."}.get(detail, "El registro ya existe.")
    return bad(msg, 409)


@bp.errorhandler(pgerr.ForeignKeyViolation)
def _fk(e):
    conn().rollback()
    return bad("Referencia a un registro que no existe.", 422)


def body():
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError("El cuerpo de la petición debe ser JSON (Content-Type: application/json).")
    return data


def paging():
    limit = as_int(request.args.get("limit", 100), 1, 1000, "limit")
    offset = as_int(request.args.get("offset", 0), 0, None, "offset")
    return limit, offset


def page(items, total, limit, offset):
    return jsonify(items=items, total=total, limit=limit, offset=offset)


def text(d, key, default=""):
    v = d.get(key, default)
    return default if v is None else str(v).strip()


# =============================================================== autenticación
@bp.post("/auth/login")
def login():
    d = request.get_json(silent=True) or {}
    u = q1("SELECT * FROM users WHERE username=%s", (text(d, "username"),))
    if not u or not check_password_hash(u["password_hash"], d.get("password") or ""):
        return bad("Usuario o contraseña incorrectos.", 401)
    session.clear()
    session.permanent = True
    session["uid"] = u["id"]
    return jsonify(id=u["id"], username=u["username"], full_name=u["full_name"], role=u["role"])


@bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.get("/auth/me")
@require("read", users_only=True)
def me():
    u = q1("SELECT id, username, full_name, role FROM users WHERE id=%s", (g.principal.id,))
    return jsonify({**u, "levels": LEVELS, "stale_months": stale_months()})


@bp.put("/auth/password")
@require("read", users_only=True)
def change_password():
    d = body()
    u = q1("SELECT password_hash FROM users WHERE id=%s", (g.principal.id,))
    if not check_password_hash(u["password_hash"], d.get("current") or ""):
        return bad("La contraseña actual no es correcta.")
    if len(d.get("new") or "") < 8:
        return bad("La nueva contraseña debe tener al menos 8 caracteres.")
    q("UPDATE users SET password_hash=%s WHERE id=%s", (generate_password_hash(d["new"]), g.principal.id))
    commit()
    return jsonify(ok=True)


# ==================================================================== empleados
EMP_SELECT = """
SELECT e.id, e.external_id, e.name, e.email, e.department, e.job_role_id, r.name AS job_role,
       e.created_at, e.updated_at,
       COALESCE(a.assessed, 0) AS assessed, COALESCE(a.known, 0) AS known, COALESCE(a.experts, 0) AS experts,
       COALESCE(a.stale, 0) AS stale, a.last_evaluated_at, a.oldest_evaluated_at
FROM employees e
LEFT JOIN job_roles r ON r.id = e.job_role_id
LEFT JOIN LATERAL (
    SELECT count(*) AS assessed,
           count(*) FILTER (WHERE level > 0) AS known,
           count(*) FILTER (WHERE level >= 4) AS experts,
           count(*) FILTER (WHERE evaluated_at < %(limit_date)s) AS stale,
           max(evaluated_at) AS last_evaluated_at,
           min(evaluated_at) AS oldest_evaluated_at
    FROM assessments WHERE employee_id = e.id) a ON true
"""


def _emp_filters():
    where, p = [], {"limit_date": stale_limit()}
    a = request.args
    if a.get("q"):
        where.append("(e.name ILIKE %(q)s OR e.email ILIKE %(q)s OR e.department ILIKE %(q)s OR e.external_id ILIKE %(q)s)")
        p["q"] = f"%{a['q']}%"
    if a.get("department"):
        where.append("lower(e.department) = lower(%(department)s)")
        p["department"] = a["department"]
    if a.get("job_role_id"):
        where.append("e.job_role_id = %(job_role_id)s")
        p["job_role_id"] = as_int(a["job_role_id"], field="job_role_id")
    if a.get("email"):
        where.append("lower(e.email) = lower(%(email)s)")
        p["email"] = a["email"]
    if a.get("external_id"):
        where.append("e.external_id = %(external_id)s")
        p["external_id"] = a["external_id"]
    if a.get("updated_since"):
        where.append("e.updated_at >= %(updated_since)s")
        p["updated_since"] = as_datetime(a["updated_since"], "updated_since")
    if as_bool(a.get("has_stale", "")):
        where.append("COALESCE(a.stale, 0) > 0")
    return ("WHERE " + " AND ".join(where)) if where else "", p


@bp.get("/employees")
@require("read")
def list_employees():
    limit, offset = paging()
    where, p = _emp_filters()
    total = q1(f"SELECT count(*) AS n FROM ({EMP_SELECT} {where}) t", p)["n"]
    rows = q(f"{EMP_SELECT} {where} ORDER BY lower(e.name), e.id LIMIT {limit} OFFSET {offset}", p)
    return page(rows, total, limit, offset)


def _employee_values(d, partial):
    out = {}
    if not partial or "name" in d:
        name = text(d, "name")
        if not name:
            raise ValidationError("El nombre es obligatorio.")
        out["name"] = name
    if "email" in d:
        out["email"] = text(d, "email").lower() or None
    if "external_id" in d:
        out["external_id"] = text(d, "external_id") or None
    if "department" in d:
        out["department"] = text(d, "department")
    if "job_role_id" in d:
        rid = d.get("job_role_id")
        out["job_role_id"] = as_int(rid, field="job_role_id") if rid not in (None, "") else None
        if out["job_role_id"] and not q1("SELECT 1 FROM job_roles WHERE id=%s", (out["job_role_id"],)):
            raise ValidationError("El puesto indicado no existe.")
    elif d.get("job_role"):      # por nombre; se crea si no existe
        row = q1("SELECT id FROM job_roles WHERE lower(name)=lower(%s)", (text(d, "job_role"),)) or \
            q1("INSERT INTO job_roles (name) VALUES (%s) RETURNING id", (text(d, "job_role"),))
        out["job_role_id"] = row["id"]
    return out


def _employee_by_id(emp_id):
    return q1(f"{EMP_SELECT} WHERE e.id = %(id)s", {"limit_date": stale_limit(), "id": emp_id})


@bp.post("/employees")
@require("write")
def create_employee():
    v = _employee_values(body(), partial=False)
    cols = ", ".join(v)
    row = q1(f"INSERT INTO employees ({cols}) VALUES ({', '.join(['%s'] * len(v))}) RETURNING id", list(v.values()))
    commit()
    return jsonify(_employee_by_id(row["id"])), 201


@bp.route("/employees/<int:emp_id>", methods=["PUT", "PATCH"])
@require("write")
def update_employee(emp_id):
    if not q1("SELECT 1 FROM employees WHERE id=%s", (emp_id,)):
        return bad("Empleado no encontrado.", 404)
    v = _employee_values(body(), partial=True)
    if v:
        sets = ", ".join(f"{k}=%s" for k in v)
        q(f"UPDATE employees SET {sets}, updated_at=now() WHERE id=%s", [*v.values(), emp_id])
        commit()
    return jsonify(_employee_by_id(emp_id))


@bp.delete("/employees/<int:emp_id>")
@require("write")
def delete_employee(emp_id):
    if not q1("DELETE FROM employees WHERE id=%s RETURNING id", (emp_id,)):
        return bad("Empleado no encontrado.", 404)
    commit()
    return "", 204


@bp.get("/employees/<int:emp_id>")
@require("read")
def get_employee(emp_id):
    e = _employee_by_id(emp_id)
    if not e:
        return bad("Empleado no encontrado.", 404)
    limit = stale_limit()
    rows = q("""SELECT a.*, s.name AS skill, s.category FROM assessments a JOIN skills s ON s.id=a.skill_id
                WHERE a.employee_id=%s ORDER BY lower(s.category), lower(s.name)""", (emp_id,))
    req = requirements().get(e["job_role_id"], {})
    e["assessments"] = [{"skill_id": r["skill_id"], "skill": r["skill"], "category": r["category"],
                         **assessment_dict(r, limit), "required_level": req.get(r["skill_id"])} for r in rows]
    names = {r["id"]: r["name"] for r in q("SELECT id, name FROM skills")}
    e["requirements"] = [{"skill_id": s, "skill": names.get(s), "required_level": l} for s, l in req.items()]
    lv = {r["skill_id"]: r["level"] for r in rows}
    e["coverage"], e["gap_points"], e["below"] = gap_for(lv, req)
    return jsonify(e)


@bp.get("/employees/<int:emp_id>/history")
@require("read")
def employee_history(emp_id):
    rows = q("""SELECT h.*, s.name AS skill FROM assessment_history h JOIN skills s ON s.id=h.skill_id
                WHERE h.employee_id=%s ORDER BY h.changed_at DESC, h.id DESC LIMIT 200""", (emp_id,))
    return jsonify(items=rows)


@bp.post("/employees/<int:emp_id>/review")
@require("write")
def review_employee(emp_id):
    """Confirma como vigentes los niveles actuales (renueva la fecha de evaluación sin cambiarlos)."""
    d = request.get_json(silent=True) or {}
    ids = [as_int(s, field="skill_ids") for s in d.get("skill_ids") or []]
    extra = "AND skill_id = ANY(%s)" if ids else ""
    params = [g.principal.actor, g.principal.source, emp_id] + ([ids] if ids else [])
    rows = q(f"""UPDATE assessments SET evaluated_at=now(), evaluated_by=%s, source=%s
                 WHERE employee_id=%s {extra} RETURNING skill_id""", params)
    commit()
    return jsonify(reviewed=len(rows))


# ================================================================== habilidades
@bp.get("/skills")
@require("read")
def list_skills():
    rows = q("""SELECT s.id, s.name, s.category, s.description,
                       count(a.employee_id) FILTER (WHERE a.level > 0) AS people,
                       count(a.employee_id) FILTER (WHERE a.level >= 4) AS experts,
                       count(a.employee_id) FILTER (WHERE a.evaluated_at < %s) AS stale
                FROM skills s LEFT JOIN assessments a ON a.skill_id = s.id
                GROUP BY s.id ORDER BY lower(s.category), lower(s.name)""", (stale_limit(),))
    return jsonify(items=rows, total=len(rows))


def _skill_values(d, partial):
    out = {}
    if not partial or "name" in d:
        if not text(d, "name"):
            raise ValidationError("El nombre de la habilidad es obligatorio.")
        out["name"] = text(d, "name")
    if not partial or "category" in d:
        out["category"] = text(d, "category") or "Sin categoría"
    if not partial or "description" in d:
        out["description"] = text(d, "description")
    return out


@bp.post("/skills")
@require("write")
def create_skill():
    v = _skill_values(body(), False)
    row = q1("INSERT INTO skills (name, category, description) VALUES (%(name)s, %(category)s, %(description)s) "
             "RETURNING *", v)
    commit()
    return jsonify(row), 201


@bp.route("/skills/<int:skill_id>", methods=["PUT", "PATCH"])
@require("write")
def update_skill(skill_id):
    v = _skill_values(body(), True)
    if v:
        sets = ", ".join(f"{k}=%s" for k in v)
        row = q1(f"UPDATE skills SET {sets} WHERE id=%s RETURNING *", [*v.values(), skill_id])
    else:
        row = q1("SELECT * FROM skills WHERE id=%s", (skill_id,))
    if not row:
        return bad("Habilidad no encontrada.", 404)
    commit()
    return jsonify(row)


@bp.delete("/skills/<int:skill_id>")
@require("write")
def delete_skill(skill_id):
    if not q1("DELETE FROM skills WHERE id=%s RETURNING id", (skill_id,)):
        return bad("Habilidad no encontrada.", 404)
    commit()
    return "", 204


# ======================================================================= puestos
def _roles(role_id=None):
    req = requirements()
    names = {r["id"]: r["name"] for r in q("SELECT id, name FROM skills")}
    counts = {r["job_role_id"]: r["n"] for r in q(
        "SELECT job_role_id, count(*) AS n FROM employees WHERE job_role_id IS NOT NULL GROUP BY job_role_id")}
    rows = q("SELECT id, name FROM job_roles " + ("WHERE id=%s " if role_id else "") + "ORDER BY lower(name)",
             (role_id,) if role_id else None)
    return [{"id": r["id"], "name": r["name"], "employees": counts.get(r["id"], 0),
             "requirements": [{"skill_id": s, "skill": names.get(s), "required_level": l}
                              for s, l in sorted(req.get(r["id"], {}).items(), key=lambda x: names.get(x[0], ""))]}
            for r in rows]


@bp.get("/job-roles")
@require("read")
def list_roles():
    items = _roles()
    return jsonify(items=items, total=len(items))


@bp.get("/job-roles/<int:role_id>")
@require("read")
def get_role(role_id):
    r = _roles(role_id)
    return jsonify(r[0]) if r else bad("Puesto no encontrado.", 404)


def _save_role(role_id, d):
    if role_id is None or "name" in d:
        if not text(d, "name"):
            raise ValidationError("El nombre del puesto es obligatorio.")
        if role_id is None:
            role_id = q1("INSERT INTO job_roles (name) VALUES (%s) RETURNING id", (text(d, "name"),))["id"]
        elif not q1("UPDATE job_roles SET name=%s WHERE id=%s RETURNING id", (text(d, "name"), role_id)):
            return None
    elif not q1("SELECT 1 FROM job_roles WHERE id=%s", (role_id,)):
        return None
    if "requirements" in d:
        reqs = d["requirements"] or []
        if isinstance(reqs, dict):          # admite {"skill_id": nivel}
            reqs = [{"skill_id": k, "required_level": v} for k, v in reqs.items()]
        q("DELETE FROM role_requirements WHERE job_role_id=%s", (role_id,))
        for item in reqs:
            lvl = as_int(item.get("required_level"), 0, 5, "required_level")
            if lvl > 0:
                sid = resolve_skill(item)
                q("INSERT INTO role_requirements VALUES (%s,%s,%s) ON CONFLICT (job_role_id, skill_id) "
                  "DO UPDATE SET required_level=EXCLUDED.required_level", (role_id, sid, lvl))
    commit()
    return role_id


@bp.post("/job-roles")
@require("write")
def create_role():
    rid = _save_role(None, body())
    return jsonify(_roles(rid)[0]), 201


@bp.route("/job-roles/<int:role_id>", methods=["PUT", "PATCH"])
@require("write")
def update_role(role_id):
    if _save_role(role_id, body()) is None:
        return bad("Puesto no encontrado.", 404)
    return jsonify(_roles(role_id)[0])


@bp.delete("/job-roles/<int:role_id>")
@require("write")
def delete_role(role_id):
    if not q1("DELETE FROM job_roles WHERE id=%s RETURNING id", (role_id,)):
        return bad("Puesto no encontrado.", 404)
    commit()
    return "", 204


@bp.get("/job-roles/<int:role_id>/gaps")
@require("read")
def role_gaps(role_id):
    """scope=role: empleados del puesto (por defecto). scope=all: toda la plantilla como candidatos."""
    if not q1("SELECT 1 FROM job_roles WHERE id=%s", (role_id,)):
        return bad("Puesto no encontrado.", 404)
    req = requirements().get(role_id, {})
    levels = employee_levels()
    limit = stale_limit()
    scope = request.args.get("scope", "role")
    emps = q("""SELECT e.id, e.name, e.email, e.external_id, e.department, e.job_role_id, COALESCE(r.name,'') AS job_role
                FROM employees e LEFT JOIN job_roles r ON r.id=e.job_role_id """ +
             ("WHERE e.job_role_id=%s " if scope != "all" else "") + "ORDER BY lower(e.name)",
             (role_id,) if scope != "all" else None)
    rows = []
    for e in emps:
        el = levels.get(e["id"], {})
        lv = {s: v[0] for s, v in el.items()}
        pct, gap, below = gap_for(lv, req)
        rows.append({**e, "coverage": pct, "gap_points": gap, "below": below,
                     "skills": [{"skill_id": s, "required_level": r,
                                 "level": el[s][0] if s in el else None,
                                 "evaluated_at": el[s][1] if s in el else None,
                                 "stale": bool(s in el and el[s][1] < limit)} for s, r in req.items()]})
    rows.sort(key=lambda r: (-(r["coverage"] or 0), r["name"]))
    names = {r["id"]: r["name"] for r in q("SELECT id, name FROM skills")}
    by_skill = [{"skill_id": s, "skill": names.get(s), "required_level": r,
                 "meeting": sum(1 for row in rows if levels.get(row["id"], {}).get(s, (0,))[0] >= r),
                 "total": len(rows)} for s, r in req.items()]
    return jsonify(employees=rows, by_skill=by_skill)


# =================================================================== evaluaciones
@bp.get("/assessments")
@require("read")
def list_assessments():
    limit, offset = paging()
    a = request.args
    lim = stale_limit()
    where, p = [], {"lim": lim}
    for key, col in (("employee_id", "a.employee_id"), ("skill_id", "a.skill_id")):
        if a.get(key):
            where.append(f"{col} = %({key})s")
            p[key] = as_int(a[key], field=key)
    if a.get("employee_email"):
        where.append("lower(e.email) = lower(%(email)s)")
        p["email"] = a["employee_email"]
    if a.get("employee_external_id"):
        where.append("e.external_id = %(ext)s")
        p["ext"] = a["employee_external_id"]
    if a.get("skill"):
        where.append("lower(s.name) = lower(%(skill)s)")
        p["skill"] = a["skill"]
    if a.get("category"):
        where.append("lower(s.category) = lower(%(category)s)")
        p["category"] = a["category"]
    if a.get("min_level"):
        where.append("a.level >= %(min_level)s")
        p["min_level"] = as_int(a["min_level"], 0, 5, "min_level")
    if a.get("max_level"):
        where.append("a.level <= %(max_level)s")
        p["max_level"] = as_int(a["max_level"], 0, 5, "max_level")
    if a.get("stale") not in (None, ""):
        where.append("a.evaluated_at < %(lim)s" if as_bool(a["stale"]) else "a.evaluated_at >= %(lim)s")
    if a.get("evaluated_since"):
        where.append("a.evaluated_at >= %(since)s")
        p["since"] = as_datetime(a["evaluated_since"], "evaluated_since")
    if a.get("evaluated_before"):
        where.append("a.evaluated_at < %(before)s")
        p["before"] = as_datetime(a["evaluated_before"], "evaluated_before")
    w = ("WHERE " + " AND ".join(where)) if where else ""
    base = f"""FROM assessments a JOIN employees e ON e.id=a.employee_id JOIN skills s ON s.id=a.skill_id {w}"""
    total = q1(f"SELECT count(*) AS n {base}", p)["n"]
    rows = q(f"""SELECT a.employee_id, e.name AS employee, e.email AS employee_email, e.external_id AS employee_external_id,
                        a.skill_id, s.name AS skill, s.category, a.level, a.evaluated_at, a.evaluated_by, a.source,
                        (a.evaluated_at < %(lim)s) AS stale
                 {base} ORDER BY lower(e.name), lower(s.name) LIMIT {limit} OFFSET {offset}""", p)
    return page(rows, total, limit, offset)


@bp.post("/assessments")
@require("write")
def upsert_assessments():
    """Alta/actualización masiva. Todo o nada: si una fila falla, no se guarda ninguna."""
    d = body()
    items = d if isinstance(d, list) else d.get("items") if isinstance(d, dict) and "items" in d else [d]
    if not isinstance(items, list) or not items:
        raise ValidationError("Envía un objeto, una lista o {\"items\": [...]}.")
    if len(items) > MAX_BATCH:
        raise ValidationError(f"Máximo {MAX_BATCH} evaluaciones por petición.")
    create = as_bool(request.args.get("create_missing_skills", d.get("create_missing_skills", False)
                                      if isinstance(d, dict) else False))
    errors, parsed = [], []
    for i, it in enumerate(items):
        try:
            if not isinstance(it, dict):
                raise ValidationError("Cada elemento debe ser un objeto.")
            parsed.append((resolve_employee(it), resolve_skill(it, create=create, category=it.get("category")),
                           as_int(it.get("level"), 0, 5, "level"), as_datetime(it.get("evaluated_at"), "evaluated_at")))
        except ValidationError as ex:
            errors.append({"index": i, "error": str(ex)})
    if errors:
        conn().rollback()
        return bad("Ninguna evaluación se ha guardado porque hay errores.", 422, errors=errors[:200])
    stats = {"created": 0, "changed": 0, "reviewed": 0, "skipped": 0, "unchanged": 0}
    p = g.principal
    for emp_id, skill_id, level, when in parsed:
        stats[set_assessment(emp_id, skill_id, level, p.actor, p.source, when)] += 1
    commit()
    return jsonify(processed=len(parsed), **stats)


@bp.put("/assessments/<int:emp_id>/<int:skill_id>")
@require("write")
def put_assessment(emp_id, skill_id):
    d = body()
    level = as_int(d.get("level"), 0, 5, "level")
    if not q1("SELECT 1 FROM employees WHERE id=%s", (emp_id,)) or not q1("SELECT 1 FROM skills WHERE id=%s", (skill_id,)):
        return bad("Empleado o habilidad no encontrados.", 404)
    p = g.principal
    result = set_assessment(emp_id, skill_id, level, p.actor, p.source, as_datetime(d.get("evaluated_at")))
    commit()
    row = q1("SELECT * FROM assessments WHERE employee_id=%s AND skill_id=%s", (emp_id, skill_id))
    return jsonify(result=result, employee_id=emp_id, skill_id=skill_id, **assessment_dict(row, stale_limit()))


@bp.delete("/assessments/<int:emp_id>/<int:skill_id>")
@require("write")
def remove_assessment(emp_id, skill_id):
    if not delete_assessment(emp_id, skill_id, g.principal.actor, g.principal.source):
        return bad("No hay evaluación para ese empleado y habilidad.", 404)
    commit()
    return "", 204


# ======================================================================= matriz
@bp.get("/matrix")
@require("read")
def matrix():
    lim = stale_limit()
    emps = q("""SELECT e.id, e.external_id, e.name, e.email, e.department, e.job_role_id, COALESCE(r.name,'') AS job_role
                FROM employees e LEFT JOIN job_roles r ON r.id=e.job_role_id ORDER BY lower(e.name)""")
    skills = q("SELECT id, name, category, description FROM skills ORDER BY lower(category), lower(name)")
    cells = {f"{r['employee_id']}-{r['skill_id']}": assessment_dict(r, lim)
             for r in q("SELECT * FROM assessments")}
    return jsonify(employees=emps, skills=skills, assessments=cells, job_roles=_roles(),
                   stale_months=stale_months(), stale_before=lim)


# ===================================================================== resumen
@bp.get("/dashboard")
@require("read")
def dashboard():
    lim = stale_limit()
    t = q1("""SELECT (SELECT count(*) FROM employees) AS employees, (SELECT count(*) FROM skills) AS skills,
                     count(*) AS assessments,
                     count(*) FILTER (WHERE evaluated_at < %(lim)s) AS stale,
                     count(*) FILTER (WHERE level >= 4) AS experts,
                     round(avg(level) FILTER (WHERE level > 0), 2) AS avg_known
              FROM assessments""", {"lim": lim})
    t["unassessed"] = t["employees"] * t["skills"] - t["assessments"]
    dist = {i: 0 for i in range(6)}
    for r in q("SELECT level, count(*) AS n FROM assessments GROUP BY level"):
        dist[r["level"]] = r["n"]
    per_skill = q("""SELECT s.id, s.name, s.category,
                            round(COALESCE(sum(a.level), 0)::numeric / GREATEST((SELECT count(*) FROM employees), 1), 2) AS avg,
                            count(a.*) FILTER (WHERE a.level >= 4) AS experts,
                            count(a.*) FILTER (WHERE a.level >= 1) AS known
                     FROM skills s LEFT JOIN assessments a ON a.skill_id=s.id GROUP BY s.id""")
    req, levels = requirements(), employee_levels()
    per_role = []
    for r in q("SELECT id, name FROM job_roles ORDER BY lower(name)"):
        members = [e["id"] for e in q("SELECT id FROM employees WHERE job_role_id=%s", (r["id"],))]
        covs = [gap_for({s: v[0] for s, v in levels.get(m, {}).items()}, req.get(r["id"], {}))[0] for m in members]
        covs = [c for c in covs if c is not None]
        per_role.append({"id": r["id"], "name": r["name"], "employees": len(members),
                         "coverage": round(sum(covs) / len(covs)) if covs else None})
    review = q("""SELECT e.id, e.name, COALESCE(r.name,'') AS job_role, max(a.evaluated_at) AS last_evaluated_at,
                         count(*) FILTER (WHERE a.evaluated_at < %(lim)s) AS stale, count(a.*) AS assessed
                  FROM employees e LEFT JOIN job_roles r ON r.id=e.job_role_id
                  LEFT JOIN assessments a ON a.employee_id=e.id
                  GROUP BY e.id, r.name
                  HAVING count(*) FILTER (WHERE a.evaluated_at < %(lim)s) > 0 OR count(a.*) = 0
                  ORDER BY max(a.evaluated_at) ASC NULLS FIRST LIMIT 8""", {"lim": lim})
    recent = q("""SELECT h.changed_at, h.changed_by, h.source, h.old_level, h.new_level, e.id AS employee_id,
                         e.name AS employee, s.name AS skill
                  FROM assessment_history h JOIN employees e ON e.id=h.employee_id JOIN skills s ON s.id=h.skill_id
                  ORDER BY h.changed_at DESC, h.id DESC LIMIT 8""")
    return jsonify(totals=t, distribution=dist, per_skill=per_skill, per_role=per_role,
                   needs_review=review, recent=recent, stale_months=stale_months())


# ============================================================ importar / exportar
@bp.get("/export")
@require("read")
def export():
    return excel_io.export(request.args.get("format", "xlsx"), request.args.get("layout", "matrix"))


@bp.post("/import")
@require("write")
def import_file():
    f = request.files.get("file")
    if not f:
        raise ValidationError("Adjunta un archivo en el campo «file».")
    stats = excel_io.import_file(f, g.principal, as_bool(request.form.get("review_unchanged", "")))
    commit()
    return jsonify(stats)


# ================================================================ administración
@bp.get("/settings")
@require("read")
def get_settings():
    return jsonify(stale_months=stale_months())


@bp.put("/settings")
@require("admin")
def put_settings():
    m = as_int(body().get("stale_months"), 1, 120, "stale_months")
    q("UPDATE settings SET value=%s WHERE key='stale_months'", (str(m),))
    commit()
    return jsonify(stale_months=m)


@bp.get("/users")
@require("admin")
def list_users():
    return jsonify(items=q("SELECT id, username, full_name, role, created_at FROM users ORDER BY username"))


@bp.post("/users")
@require("admin")
def create_user():
    d = body()
    if not text(d, "username") or len(d.get("password") or "") < 8 or d.get("role") not in ROLES:
        raise ValidationError("Indica usuario, rol y una contraseña de al menos 8 caracteres.")
    row = q1("INSERT INTO users (username, password_hash, full_name, role) VALUES (%s,%s,%s,%s) "
             "RETURNING id, username, full_name, role",
             (text(d, "username"), generate_password_hash(d["password"]), text(d, "full_name"), d["role"]))
    commit()
    return jsonify(row), 201


@bp.put("/users/<int:user_id>")
@require("admin")
def update_user(user_id):
    d = body()
    if d.get("role") not in ROLES:
        raise ValidationError("Rol no válido.")
    if user_id == g.principal.id and d["role"] != "admin":
        raise ValidationError("No puedes quitarte a ti mismo el rol de administrador.")
    if d.get("password") and len(d["password"]) < 8:
        raise ValidationError("La contraseña debe tener al menos 8 caracteres.")
    if not q1("UPDATE users SET full_name=%s, role=%s WHERE id=%s RETURNING id", (text(d, "full_name"), d["role"], user_id)):
        return bad("Usuario no encontrado.", 404)
    if d.get("password"):
        q("UPDATE users SET password_hash=%s WHERE id=%s", (generate_password_hash(d["password"]), user_id))
    commit()
    return jsonify(ok=True)


@bp.delete("/users/<int:user_id>")
@require("admin")
def delete_user(user_id):
    if user_id == g.principal.id:
        raise ValidationError("No puedes eliminar tu propio usuario.")
    q("DELETE FROM users WHERE id=%s", (user_id,))
    commit()
    return "", 204


@bp.get("/tokens")
@require("admin")
def list_tokens():
    return jsonify(items=q("""SELECT id, name, token_prefix, scope, created_by, created_at, last_used_at, revoked_at
                              FROM api_tokens ORDER BY revoked_at IS NOT NULL, created_at DESC"""))


@bp.post("/tokens")
@require("admin")
def create_token():
    d = body()
    if not text(d, "name") or d.get("scope") not in ("read", "write"):
        raise ValidationError("Indica el nombre de la aplicación y el permiso (read o write).")
    token, prefix, digest = new_token()
    row = q1("""INSERT INTO api_tokens (name, token_prefix, token_hash, scope, created_by)
                VALUES (%s,%s,%s,%s,%s) RETURNING id, name, token_prefix, scope, created_at""",
             (text(d, "name"), prefix, digest, d["scope"], g.principal.name))
    commit()
    return jsonify({**row, "token": token}), 201      # el token completo solo se muestra una vez


@bp.delete("/tokens/<int:token_id>")
@require("admin")
def revoke_token(token_id):
    q("UPDATE api_tokens SET revoked_at=now() WHERE id=%s AND revoked_at IS NULL", (token_id,))
    commit()
    return "", 204
