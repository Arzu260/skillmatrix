"""Copia los datos de SkillMatrix v1 (SQLite) a la base de datos PostgreSQL de la v2.

Uso:   python migrar_desde_sqlite.py  D:\\Proyectos\\skillmatrix-v1\\data\\skillmatrix.db

La base de datos PostgreSQL de destino (DATABASE_URL del .env) debe estar vacía.
Se conservan usuarios y contraseñas, empleados, habilidades, puestos, niveles e historial.
La fecha de la última evaluación será la de la última modificación de cada nivel en la v1.
"""
import os
import sqlite3
import sys

os.environ["SKILLMATRIX_DEMO"] = "0"
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

import db  # noqa: E402

TABLES = [  # (tabla v1, tabla v2, columnas v1 -> v2)
    ("users", "users", {"id": "id", "username": "username", "password_hash": "password_hash",
                        "full_name": "full_name", "role": "role"}),
    ("job_roles", "job_roles", {"id": "id", "name": "name"}),
    ("employees", "employees", {"id": "id", "name": "name", "email": "email", "department": "department",
                                "job_role_id": "job_role_id"}),
    ("skills", "skills", {"id": "id", "name": "name", "category": "category", "description": "description"}),
    ("employee_skills", "assessments", {"employee_id": "employee_id", "skill_id": "skill_id", "level": "level",
                                        "updated_by": "evaluated_by", "updated_at": "evaluated_at"}),
    ("role_requirements", "role_requirements", {"job_role_id": "job_role_id", "skill_id": "skill_id",
                                                "required_level": "required_level"}),
    ("history", "assessment_history", {"employee_id": "employee_id", "skill_id": "skill_id", "old_level": "old_level",
                                       "new_level": "new_level", "changed_by": "changed_by", "changed_at": "changed_at"}),
]


def main(path):
    if not os.path.exists(path):
        sys.exit(f"No existe el archivo {path}")
    src = sqlite3.connect(path)
    src.row_factory = sqlite3.Row
    db.init_db(seed_demo=False)
    with db.pool().connection() as c:
        if c.execute("SELECT count(*) AS n FROM employees").fetchone()["n"]:
            sys.exit("La base de datos de destino ya tiene empleados. Usa una base de datos vacía.")
        with c.transaction():
            c.execute("DELETE FROM users")          # el admin inicial se sustituye por los usuarios de la v1
            for old, new, cols in TABLES:
                rows = src.execute(f"SELECT {', '.join(cols)} FROM {old}").fetchall()
                marks = ["%s"] * len(cols)
                if new == "assessments":            # sin fecha en la v1 -> ahora
                    marks[-1] = "COALESCE(%s::timestamptz, now())"
                sql = f"INSERT INTO {new} ({', '.join(cols.values())}) VALUES ({', '.join(marks)})"
                for r in rows:
                    vals = [r[k] for k in cols]
                    if new == "assessments":
                        vals[3] = vals[3] or "migración"
                        vals[4] = vals[4] or None
                    c.execute(sql, vals)
                print(f"  {new:20s} {len(rows):6d} filas")
            c.execute("UPDATE assessments SET source='migración'")
            c.execute("UPDATE assessment_history SET source='migración'")
            for t in ("users", "job_roles", "employees", "skills"):
                c.execute(f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), COALESCE((SELECT max(id) FROM {t}), 1))")
    print("\nMigración completada. Los usuarios conservan sus contraseñas.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
