# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado [SemVer](https://semver.org/lang/es/).

## [Sin publicar]

### Cambiado
- CI: `actions/checkout` y `actions/setup-python` actualizadas a v7 (Node.js 24) y ejecución fijada en Ubuntu 24.04.

### Añadido
- Dependabot: propone cada semana las actualizaciones de las acciones de GitHub y de las dependencias de Python.

### Corregido
- Las pruebas no se ejecutaban con `pytest` a secas (faltaba `pytest.ini`).

## [2.0.0] - 2026-09-23

### Añadido
- Base de datos PostgreSQL con migraciones automáticas y versionadas.
- API REST `/api/v1` con tokens por aplicación (lectura o lectura y escritura), documentación OpenAPI/Swagger
  en `/api/docs` y carga masiva de evaluaciones (todo o nada).
- Fecha de la última evaluación en cada nivel, con plazo de caducidad configurable (12 meses por defecto) y
  marcas de «desactualizado» en la matriz, la ficha, el resumen y la API.
- Distinción entre «sin evaluar» y «0 = no lo conoce».
- Código de empleado (`external_id`) para enlazar con sistemas de RRHH.
- Confirmación de niveles vigentes, por celda o para todo un empleado.
- Exportación e importación en formato «evaluaciones» (una fila por evaluación, con fecha).
- Sección de Administración: usuarios, aplicaciones (tokens) y ajustes.
- `gestion.py` para tareas de administración desde la consola.
- Dockerfile, docker-compose y ejemplos de despliegue para systemd, nginx, Kubernetes y servicio de Windows.
- Pruebas automáticas e integración continua con GitHub Actions.
- Script `migrar_desde_sqlite.py` para traer los datos de la versión 1.

### Cambiado
- La interfaz web usa la misma API que las integraciones.
- Contraseñas de al menos 8 caracteres.
- Reimportar un Excel sin cambios ya no altera las fechas de evaluación.

## [1.0.0] - 2026-09-23

### Añadido
- Primera versión: matriz de habilidades editable (escala 0-5), puestos y brechas, resumen con gráficos,
  importación y exportación Excel/CSV, usuarios con roles. Flask + SQLite.
