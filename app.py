"""
SkillMatrix - Matriz de habilidades de empleados (Flask + PostgreSQL)
Arranque:  python app.py      (configuración en el archivo .env)
"""
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Flask, jsonify, request, send_from_directory
from flask.json.provider import DefaultJSONProvider

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

import db  # noqa: E402  (después de cargar .env)
from api import bp  # noqa: E402
from openapi import spec  # noqa: E402


class JSONProvider(DefaultJSONProvider):
    ensure_ascii = False
    sort_keys = False

    @staticmethod
    def default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, date):
            return o.isoformat()
        if isinstance(o, Decimal):
            return float(o)
        return DefaultJSONProvider.default(o)


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.json = JSONProvider(app)
    db.init_db(seed_demo=os.environ.get("SKILLMATRIX_DEMO", "1") == "1")
    app.secret_key = db.secret_key()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=10),
                      MAX_CONTENT_LENGTH=20 * 1024 * 1024)
    app.teardown_appcontext(db.release)
    app.register_blueprint(bp)

    cors = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]

    @app.after_request
    def _cors(resp):
        origin = request.headers.get("Origin")
        if cors and request.path.startswith("/api/v1") and (origin in cors or "*" in cors):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            resp.headers["Vary"] = "Origin"
        return resp

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/v1/openapi.json")
    def openapi_json():
        return jsonify(spec())

    @app.get("/api/docs")
    def docs():
        return send_from_directory(app.static_folder, "docs.html")

    @app.get("/api/health")
    def health():
        db.q1("SELECT 1")
        return jsonify(status="ok")

    @app.errorhandler(404)
    def _404(e):
        if request.path.startswith("/api/"):
            return jsonify(error="Ruta no encontrada. Consulta /api/docs."), 404
        return e

    @app.errorhandler(405)
    def _405(e):
        return jsonify(error="Método no permitido en esta ruta."), 405

    @app.errorhandler(500)
    def _500(e):
        return jsonify(error="Error interno del servidor. Revisa el registro de la aplicación."), 500

    return app


app = create_app()

if __name__ == "__main__":
    host, port = os.environ.get("HOST", "0.0.0.0"), int(os.environ.get("PORT", "5000"))
    print(f"\n  SkillMatrix en http://localhost:{port}   ·   API: http://localhost:{port}/api/docs\n")
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=int(os.environ.get("THREADS", "8")))
    except ImportError:
        app.run(host=host, port=port)
