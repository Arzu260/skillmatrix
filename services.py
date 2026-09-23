"""Lógica de negocio compartida por la API y la importación de archivos."""
from datetime import datetime, timedelta, timezone

from db import q, q1

LEVELS = {0: "No lo conoce", 1: "Nociones básicas", 2: "Principiante",
          3: "Intermedio", 4: "Avanzado", 5: "Experto"}


class ValidationError(Exception):
    pass


# ------------------------------------------------------------------ utilidades
def as_int(v, lo=None, hi=None, field="valor"):
    if isinstance(v, bool):
        raise ValidationError(f"«{field}» debe ser un número entero.")
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValidationError(f"«{field}» debe ser un número entero.")
    if f != int(f):
        raise ValidationError(f"«{field}» debe ser un número entero.")
    n = int(f)
    if (lo is not None and n < lo) or (hi is not None and n > hi):
        raise ValidationError(f"«{field}» debe estar entre {lo} y {hi}.")
    return n


def as_datetime(v, field="fecha"):
    """Acepta ISO 8601 ("2026-03-01", "2026-03-01T10:00:00Z", "...+02:00"). Sin zona = UTC."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        dt = v
    else:
        try:
            dt = datetime.fromisoformat(str(v).strip().replace("Z", "+00:00"))
        except ValueError:
            raise ValidationError(f"«{field}» no es una fecha ISO 8601 válida (p. ej. 2026-03-01 o 2026-03-01T10:00:00Z).")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if dt > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValidationError(f"«{field}» no puede ser una fecha futura.")
    return dt


def as_bool(v):
    return str(v).lower() in ("1", "true", "yes", "si", "sí", "on")


def stale_months():
    row = q1("SELECT value FROM settings WHERE key='stale_months'")
    return int(row["value"]) if row else 12


def stale_limit():
    """Las evaluaciones anteriores a esta fecha se consideran desactualizadas."""
    m = stale_months()
    return q1("SELECT now() - make_interval(months => %s) AS d", (m,))["d"]


# ------------------------------------------------------------ resolución de IDs
def resolve_employee(item):
    """Localiza un empleado por employee_id, employee_external_id o employee_email."""
    if item.get("employee_id") not in (None, ""):
        row = q1("SELECT id FROM employees WHERE id=%s", (as_int(item["employee_id"], field="employee_id"),))
        ref = f"id {item['employee_id']}"
    elif item.get("employee_external_id"):
        row = q1("SELECT id FROM employees WHERE external_id=%s", (str(item["employee_external_id"]).strip(),))
        ref = f"código «{item['employee_external_id']}»"
    elif item.get("employee_email"):
        row = q1("SELECT id FROM employees WHERE lower(email)=lower(%s)", (str(item["employee_email"]).strip(),))
        ref = f"email «{item['employee_email']}»"
    else:
        raise ValidationError("Indica employee_id, employee_external_id o employee_email.")
    if not row:
        raise ValidationError(f"No existe ningún empleado con {ref}.")
    return row["id"]


def resolve_skill(item, create=False, category=None):
    """Localiza una habilidad por skill_id o skill (nombre, sin distinguir mayúsculas)."""
    if item.get("skill_id") not in (None, ""):
        row = q1("SELECT id FROM skills WHERE id=%s", (as_int(item["skill_id"], field="skill_id"),))
        if not row:
            raise ValidationError(f"No existe ninguna habilidad con id {item['skill_id']}.")
        return row["id"]
    name = str(item.get("skill") or "").strip()
    if not name:
        raise ValidationError("Indica skill_id o skill (nombre de la habilidad).")
    row = q1("SELECT id FROM skills WHERE lower(name)=lower(%s)", (name,))
    if row:
        return row["id"]
    if not create:
        raise ValidationError(f"No existe la habilidad «{name}». Créala antes o envía create_missing_skills=true.")
    return q1("INSERT INTO skills (name, category) VALUES (%s,%s) RETURNING id",
              (name, category or "Sin categoría"))["id"]


# ------------------------------------------------------------------ evaluaciones
def set_assessment(employee_id, skill_id, level, actor, source, evaluated_at=None, touch_if_same=True):
    """Registra una evaluación.

    Devuelve: "created" | "changed" | "reviewed" (mismo nivel, fecha renovada) |
              "unchanged" (mismo nivel sin renovar) | "skipped" (fecha anterior a la registrada).
    """
    old = q1("SELECT level, evaluated_at FROM assessments WHERE employee_id=%s AND skill_id=%s",
             (employee_id, skill_id))
    if old and evaluated_at and evaluated_at < old["evaluated_at"]:
        return "skipped"            # no machacar una evaluación más reciente con datos antiguos
    if old and old["level"] == level and not touch_if_same:
        return "unchanged"
    q("""INSERT INTO assessments (employee_id, skill_id, level, evaluated_at, evaluated_by, source)
         VALUES (%s, %s, %s, COALESCE(%s, now()), %s, %s)
         ON CONFLICT (employee_id, skill_id) DO UPDATE SET
           level=EXCLUDED.level, evaluated_at=EXCLUDED.evaluated_at,
           evaluated_by=EXCLUDED.evaluated_by, source=EXCLUDED.source""",
      (employee_id, skill_id, level, evaluated_at, actor, source))
    if old and old["level"] == level:
        return "reviewed"
    q("""INSERT INTO assessment_history (employee_id, skill_id, old_level, new_level, changed_by, source, changed_at)
         VALUES (%s,%s,%s,%s,%s,%s, COALESCE(%s, now()))""",
      (employee_id, skill_id, old["level"] if old else None, level, actor, source, evaluated_at))
    return "changed" if old else "created"


def delete_assessment(employee_id, skill_id, actor, source):
    old = q1("DELETE FROM assessments WHERE employee_id=%s AND skill_id=%s RETURNING level", (employee_id, skill_id))
    if old:
        q("INSERT INTO assessment_history (employee_id, skill_id, old_level, new_level, changed_by, source) "
          "VALUES (%s,%s,%s,NULL,%s,%s)", (employee_id, skill_id, old["level"], actor, source))
    return bool(old)


def assessment_dict(r, limit):
    return {"level": r["level"], "evaluated_at": r["evaluated_at"], "evaluated_by": r["evaluated_by"],
            "source": r["source"], "stale": r["evaluated_at"] < limit}


# ----------------------------------------------------------------------- brechas
def requirements():
    req = {}
    for r in q("SELECT job_role_id, skill_id, required_level FROM role_requirements"):
        req.setdefault(r["job_role_id"], {})[r["skill_id"]] = r["required_level"]
    return req


def gap_for(levels, req):
    """levels: {skill_id: nivel}; sin evaluar cuenta como 0. Devuelve (cumplimiento %, puntos de brecha, pendientes)."""
    if not req:
        return None, 0, 0
    total = sum(req.values())
    covered = sum(min(levels.get(s, 0), r) for s, r in req.items())
    below = sum(1 for s, r in req.items() if levels.get(s, 0) < r)
    return round(100 * covered / total), total - covered, below


def employee_levels():
    """{employee_id: {skill_id: (nivel, evaluated_at)}}"""
    out = {}
    for r in q("SELECT employee_id, skill_id, level, evaluated_at FROM assessments"):
        out.setdefault(r["employee_id"], {})[r["skill_id"]] = (r["level"], r["evaluated_at"])
    return out
