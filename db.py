"""Acceso a PostgreSQL: pool de conexiones, migraciones de esquema y datos de ejemplo."""
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import g
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout
from werkzeug.security import generate_password_hash

_pool = None

# Cada migración se aplica una sola vez, en orden. Para cambiar el esquema en el futuro,
# añade una tupla (versión, sql) al final; nunca modifiques una ya publicada.
MIGRATIONS = [
    (1, """
    CREATE TABLE users (
        id            serial PRIMARY KEY,
        username      text NOT NULL UNIQUE,
        password_hash text NOT NULL,
        full_name     text NOT NULL DEFAULT '',
        role          text NOT NULL CHECK (role IN ('admin', 'manager', 'lector')),
        created_at    timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE api_tokens (
        id           serial PRIMARY KEY,
        name         text NOT NULL,
        token_prefix text NOT NULL,
        token_hash   text NOT NULL UNIQUE,
        scope        text NOT NULL CHECK (scope IN ('read', 'write')),
        created_by   text NOT NULL DEFAULT '',
        created_at   timestamptz NOT NULL DEFAULT now(),
        last_used_at timestamptz,
        revoked_at   timestamptz
    );

    CREATE TABLE job_roles (
        id   serial PRIMARY KEY,
        name text NOT NULL
    );
    CREATE UNIQUE INDEX job_roles_name_uq ON job_roles (lower(name));

    CREATE TABLE employees (
        id          serial PRIMARY KEY,
        external_id text UNIQUE,
        name        text NOT NULL,
        email       text,
        department  text NOT NULL DEFAULT '',
        job_role_id int REFERENCES job_roles(id) ON DELETE SET NULL,
        created_at  timestamptz NOT NULL DEFAULT now(),
        updated_at  timestamptz NOT NULL DEFAULT now()
    );
    CREATE UNIQUE INDEX employees_email_uq ON employees (lower(email));

    CREATE TABLE skills (
        id          serial PRIMARY KEY,
        name        text NOT NULL,
        category    text NOT NULL DEFAULT 'Sin categoría',
        description text NOT NULL DEFAULT ''
    );
    CREATE UNIQUE INDEX skills_name_uq ON skills (lower(name));

    -- Nivel actual de cada empleado en cada habilidad y cuándo se evaluó por última vez.
    -- Sin fila = "sin evaluar". level 0 = "no lo conoce" (evaluado).
    CREATE TABLE assessments (
        employee_id  int NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
        skill_id     int NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
        level        smallint NOT NULL CHECK (level BETWEEN 0 AND 5),
        evaluated_at timestamptz NOT NULL DEFAULT now(),
        evaluated_by text NOT NULL DEFAULT '',
        source       text NOT NULL DEFAULT 'web',
        PRIMARY KEY (employee_id, skill_id)
    );
    CREATE INDEX assessments_skill_idx ON assessments (skill_id);
    CREATE INDEX assessments_evaluated_idx ON assessments (evaluated_at);

    CREATE TABLE role_requirements (
        job_role_id    int NOT NULL REFERENCES job_roles(id) ON DELETE CASCADE,
        skill_id       int NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
        required_level smallint NOT NULL CHECK (required_level BETWEEN 1 AND 5),
        PRIMARY KEY (job_role_id, skill_id)
    );

    -- Histórico de cambios de nivel (new_level NULL = evaluación eliminada).
    CREATE TABLE assessment_history (
        id          bigserial PRIMARY KEY,
        employee_id int NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
        skill_id    int NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
        old_level   smallint,
        new_level   smallint,
        changed_by  text NOT NULL DEFAULT '',
        source      text NOT NULL DEFAULT 'web',
        changed_at  timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX assessment_history_emp_idx ON assessment_history (employee_id, changed_at DESC);
    CREATE INDEX assessment_history_time_idx ON assessment_history (changed_at DESC);

    CREATE TABLE settings (
        key   text PRIMARY KEY,
        value text NOT NULL
    );
    INSERT INTO settings (key, value) VALUES ('stale_months', '12');
    """),
]


def database_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta la variable DATABASE_URL (p. ej. postgresql://usuario:clave@localhost:5432/skillmatrix). "
                           "Revisa el archivo .env.")
    return url


def pool():
    global _pool
    if _pool is None:
        _pool = ConnectionPool(database_url(), min_size=1, max_size=int(os.environ.get("DB_POOL_SIZE", "10")),
                               kwargs={"row_factory": dict_row}, open=True)
    return _pool


def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


# ---------------------------------------------------------------- por petición
def conn():
    """Conexión de la petición en curso. Los handlers hacen commit explícito."""
    if "conn" not in g:
        g.conn = pool().getconn()
    return g.conn


def release(_exc=None):
    c = g.pop("conn", None)
    if c is not None:
        c.rollback()          # descarta cualquier cambio sin commit
        pool().putconn(c)


def q(sql, params=None):
    with conn().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []


def q1(sql, params=None):
    rows = q(sql, params)
    return rows[0] if rows else None


def commit():
    conn().commit()


# --------------------------------------------------------------- inicialización
def _safe_url():
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", database_url())


def init_db(seed_demo=True):
    """Aplica las migraciones pendientes y crea el administrador inicial."""
    try:
        pool().wait(timeout=float(os.environ.get("DB_CONNECT_TIMEOUT", "15")))
    except PoolTimeout:
        close_pool()
        raise SystemExit(f"\n  No se puede conectar a PostgreSQL ({_safe_url()}).\n"
                         "  Comprueba que el servidor está arrancado y que usuario, contraseña y base de datos "
                         "de DATABASE_URL (archivo .env) son correctos.\n")
    with pool().connection() as c:
        with c.transaction():
            c.execute("SELECT pg_advisory_xact_lock(724351)")   # evita carreras con varios procesos
            c.execute("CREATE TABLE IF NOT EXISTS schema_version (version int PRIMARY KEY, "
                      "applied_at timestamptz NOT NULL DEFAULT now())")
            current = c.execute("SELECT COALESCE(max(version), 0) AS v FROM schema_version").fetchone()["v"]
            for version, sql in MIGRATIONS:
                if version > current:
                    c.execute(sql)
                    c.execute("INSERT INTO schema_version (version) VALUES (%s)", (version,))
            if c.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0:
                c.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES (%s,%s,%s,'admin')",
                          ("admin", generate_password_hash(os.environ.get("ADMIN_PASSWORD", "admin")),
                           "Administrador RRHH"))
                if seed_demo and c.execute("SELECT count(*) AS n FROM employees").fetchone()["n"] == 0:
                    _seed(c)
            c.execute("INSERT INTO settings (key, value) VALUES ('secret_key', %s) ON CONFLICT (key) DO NOTHING",
                      (secrets.token_hex(32),))


def secret_key():
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    with pool().connection() as c:
        return c.execute("SELECT value FROM settings WHERE key='secret_key'").fetchone()["value"]


def _seed(c):
    skills = [("Oracle", "Bases de datos"), ("PostgreSQL", "Bases de datos"),
              ("Java", "Lenguajes"), ("Python", "Lenguajes"), ("JavaScript", "Lenguajes"),
              ("Spring Boot", "Frameworks"), ("React", "Frameworks"),
              ("Kubernetes", "Infraestructura"), ("Docker", "Infraestructura"),
              ("Linux", "Infraestructura"), ("AWS", "Cloud"), ("Git", "Herramientas")]
    sid = {n: c.execute("INSERT INTO skills (name, category) VALUES (%s,%s) RETURNING id", (n, cat)).fetchone()["id"]
           for n, cat in skills}
    rid = {n: c.execute("INSERT INTO job_roles (name) VALUES (%s) RETURNING id", (n,)).fetchone()["id"]
           for n in ("Desarrollador backend", "Ingeniero DevOps", "Desarrollador frontend")}
    reqs = {
        "Desarrollador backend": {"Java": 4, "Spring Boot": 4, "Oracle": 3, "Git": 3, "Docker": 2},
        "Ingeniero DevOps": {"Kubernetes": 4, "Docker": 4, "Linux": 4, "AWS": 3, "Git": 3, "Python": 2},
        "Desarrollador frontend": {"JavaScript": 4, "React": 4, "Git": 3},
    }
    for role, req in reqs.items():
        for s, lvl in req.items():
            c.execute("INSERT INTO role_requirements VALUES (%s,%s,%s)", (rid[role], sid[s], lvl))
    # (nombre, email, código, departamento, puesto, meses desde la última evaluación, niveles)
    people = [
        ("Lucía Martín", "lucia.martin@empresa.com", "E001", "Desarrollo", "Desarrollador backend", 2,
         {"Java": 5, "Spring Boot": 4, "Oracle": 3, "Git": 4, "Docker": 2, "PostgreSQL": 3}),
        ("Carlos Gómez", "carlos.gomez@empresa.com", "E002", "Desarrollo", "Desarrollador backend", 15,
         {"Java": 3, "Spring Boot": 2, "Oracle": 4, "Git": 3, "PostgreSQL": 2, "Python": 1}),
        ("Marta Ruiz", "marta.ruiz@empresa.com", "E003", "Sistemas", "Ingeniero DevOps", 1,
         {"Kubernetes": 5, "Docker": 5, "Linux": 4, "AWS": 3, "Git": 3, "Python": 3}),
        ("Javier Sanz", "javier.sanz@empresa.com", "E004", "Sistemas", "Ingeniero DevOps", 20,
         {"Kubernetes": 2, "Docker": 3, "Linux": 5, "AWS": 1, "Git": 2, "Oracle": 2}),
        ("Elena Torres", "elena.torres@empresa.com", "E005", "Desarrollo", "Desarrollador frontend", 4,
         {"JavaScript": 5, "React": 4, "Git": 4, "Python": 0}),
        ("Pablo Herrero", "pablo.herrero@empresa.com", "E006", "Desarrollo", "Desarrollador frontend", 13,
         {"JavaScript": 3, "React": 2, "Git": 2, "Java": 1}),
        ("Ana Pérez", "ana.perez@empresa.com", "E007", "Datos", None, 6,
         {"Python": 5, "PostgreSQL": 4, "Oracle": 3, "AWS": 2, "Git": 3}),
        ("Diego Álvarez", "diego.alvarez@empresa.com", "E008", "Sistemas", "Ingeniero DevOps", 8,
         {"Kubernetes": 3, "Docker": 4, "Linux": 3, "AWS": 4, "Git": 4}),
    ]
    now = datetime.now(timezone.utc)
    for name, email, code, dept, role, months, lv in people:
        eid = c.execute("INSERT INTO employees (external_id, name, email, department, job_role_id) "
                        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                        (code, name, email, dept, rid.get(role))).fetchone()["id"]
        for i, (s, l) in enumerate(lv.items()):
            when = now - timedelta(days=months * 30 + i * 3)
            c.execute("INSERT INTO assessments (employee_id, skill_id, level, evaluated_at, evaluated_by, source) "
                      "VALUES (%s,%s,%s,%s,'demo','demo')", (eid, sid[s], l, when))
