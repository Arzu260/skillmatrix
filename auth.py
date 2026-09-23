"""Autenticación y permisos.

Dos formas de identificarse ante la API:
  * Sesión web (cookie), usada por la interfaz. Permisos según el rol del usuario.
  * Token de API (cabecera "Authorization: Bearer smx_..."), usado por otras aplicaciones.
    Alcance "read" (solo lectura) o "write" (lectura y escritura). Nunca da permisos de administración.
"""
import hashlib
import secrets
from dataclasses import dataclass
from functools import wraps

from flask import g, jsonify, request, session

from db import commit, q1

ROLE_PERMS = {"lector": {"read"}, "manager": {"read", "write"}, "admin": {"read", "write", "admin"}}
SCOPE_PERMS = {"read": {"read"}, "write": {"read", "write"}}
TOKEN_PREFIX = "smx_"


@dataclass
class Principal:
    kind: str          # "user" | "token"
    id: int
    name: str          # usuario o nombre de la aplicación
    perms: set
    role: str = ""     # solo usuarios

    @property
    def actor(self):   # lo que queda registrado como "evaluado por"
        return self.name if self.kind == "user" else f"api:{self.name}"

    @property
    def source(self):
        return "web" if self.kind == "user" else "api"


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_token():
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return token, token[:12], hash_token(token)


def _identify():
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
        row = q1("SELECT id, name, scope FROM api_tokens WHERE token_hash=%s AND revoked_at IS NULL",
                 (hash_token(token),))
        if not row:
            return None, "El token de API no es válido o ha sido revocado."
        q1("UPDATE api_tokens SET last_used_at=now() WHERE id=%s "
           "AND (last_used_at IS NULL OR last_used_at < now() - interval '1 minute')", (row["id"],))
        commit()
        return Principal("token", row["id"], row["name"], SCOPE_PERMS[row["scope"]]), None
    uid = session.get("uid")
    if uid:
        u = q1("SELECT id, username, role FROM users WHERE id=%s", (uid,))
        if u:
            return Principal("user", u["id"], u["username"], ROLE_PERMS[u["role"]], u["role"]), None
        session.clear()
    return None, "Autenticación requerida: inicia sesión o envía un token de API en la cabecera Authorization."


def require(perm="read", users_only=False):
    """Decorador: perm en "read" | "write" | "admin"."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            p, err = _identify()
            if not p:
                return jsonify(error=err), 401
            if users_only and p.kind != "user":
                return jsonify(error="Esta operación solo está disponible desde la interfaz web."), 403
            if perm not in p.perms:
                msg = ("El token no tiene permiso de escritura." if p.kind == "token"
                       else "Tu usuario no tiene permiso para esta acción.")
                return jsonify(error=msg), 403
            # Protección CSRF: las peticiones que modifican datos con cookie deben venir de la propia web.
            if p.kind == "user" and request.method not in ("GET", "HEAD", "OPTIONS") \
                    and request.headers.get("X-Requested-With") != "SkillMatrix":
                return jsonify(error="Falta la cabecera X-Requested-With. Usa un token de API para integraciones."), 403
            g.principal = p
            return fn(*a, **kw)
        return wrapper
    return deco
