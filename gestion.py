"""Tareas de administración desde la consola.

  python gestion.py cambiar-clave USUARIO           Cambia la contraseña (la pide por teclado).
  python gestion.py crear-usuario USUARIO [--rol admin|manager|lector] [--nombre "Nombre"]
  python gestion.py listar-usuarios
  python gestion.py revocar-tokens                  Revoca todos los tokens de API activos.
"""
import argparse
import getpass
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

from werkzeug.security import generate_password_hash  # noqa: E402

import db  # noqa: E402


def ask_password():
    p1 = getpass.getpass("Nueva contraseña (mínimo 8 caracteres): ")
    if len(p1) < 8:
        sys.exit("La contraseña debe tener al menos 8 caracteres.")
    if getpass.getpass("Repítela: ") != p1:
        sys.exit("Las contraseñas no coinciden.")
    return generate_password_hash(p1)


def main():
    ap = argparse.ArgumentParser(description="Administración de SkillMatrix", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("cambiar-clave", help="Cambiar la contraseña de un usuario")
    s.add_argument("usuario")
    s = sub.add_parser("crear-usuario", help="Crear un usuario")
    s.add_argument("usuario")
    s.add_argument("--rol", default="admin", choices=["admin", "manager", "lector"])
    s.add_argument("--nombre", default="")
    sub.add_parser("listar-usuarios", help="Listar usuarios")
    sub.add_parser("revocar-tokens", help="Revocar todos los tokens de API")
    a = ap.parse_args()

    os.environ.setdefault("SKILLMATRIX_DEMO", "0")
    db.init_db(seed_demo=False)
    with db.pool().connection() as c:
        if a.cmd == "cambiar-clave":
            if not c.execute("SELECT 1 FROM users WHERE username=%s", (a.usuario,)).fetchone():
                sys.exit(f"No existe el usuario «{a.usuario}».")
            c.execute("UPDATE users SET password_hash=%s WHERE username=%s", (ask_password(), a.usuario))
            print(f"Contraseña de «{a.usuario}» cambiada.")
        elif a.cmd == "crear-usuario":
            if c.execute("SELECT 1 FROM users WHERE username=%s", (a.usuario,)).fetchone():
                sys.exit(f"Ya existe el usuario «{a.usuario}».")
            c.execute("INSERT INTO users (username, password_hash, full_name, role) VALUES (%s,%s,%s,%s)",
                      (a.usuario, ask_password(), a.nombre, a.rol))
            print(f"Usuario «{a.usuario}» creado con rol {a.rol}.")
        elif a.cmd == "listar-usuarios":
            for u in c.execute("SELECT username, role, full_name FROM users ORDER BY username"):
                print(f"  {u['username']:20s} {u['role']:8s} {u['full_name']}")
        elif a.cmd == "revocar-tokens":
            n = c.execute("UPDATE api_tokens SET revoked_at=now() WHERE revoked_at IS NULL").rowcount
            print(f"{n} token(s) revocado(s).")
    db.close_pool()


if __name__ == "__main__":
    main()
