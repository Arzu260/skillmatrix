# Cómo contribuir

## Entorno de desarrollo

Necesitas Python 3.10+ y un PostgreSQL. La forma más rápida es levantar solo la base de datos con Docker:

```bash
docker compose up -d db                      # PostgreSQL en localhost:5432
python -m venv .venv
source .venv/bin/activate                    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                         # Windows: copy .env.example .env
```

En `.env`, con la base de datos de `docker compose`:

```
DATABASE_URL=postgresql://skillmatrix:cambia-esta-clave@localhost:5432/skillmatrix
```

Arranca con `python app.py` y entra en http://localhost:5000 (`admin` / `admin`, con datos de ejemplo).

La interfaz no necesita compilación: los cambios en `static/` se ven al recargar el navegador.
Los cambios en Python requieren reiniciar `app.py`.

## Pruebas

Las pruebas usan una base de datos **aparte y vacía, que se borra en cada ejecución**:

```bash
# una vez:
docker compose exec db createdb -U skillmatrix skillmatrix_test

# cada vez:
export TEST_DATABASE_URL=postgresql://skillmatrix:cambia-esta-clave@localhost:5432/skillmatrix_test
# Windows: set TEST_DATABASE_URL=...
pytest -q
```

GitHub Actions ejecuta las mismas pruebas, más comprobaciones de sintaxis, en cada *push* y
*pull request* ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Un PR con la CI en rojo no se integra.

## Flujo de trabajo

1. Crea una rama desde `main`: `feature/descripcion-corta` o `fix/descripcion-corta`.
2. Haz commits pequeños con mensajes en imperativo que expliquen el porqué: *"Añade filtro por categoría en la API"*.
3. Abre un *pull request* hacia `main` rellenando la plantilla. Hace falta al menos una aprobación.
4. Si el cambio afecta a usuarios o integradores, actualiza el [CHANGELOG](CHANGELOG.md) en la sección *Sin publicar*.

## Convenciones

- **Idioma**: interfaz, mensajes de error y documentación en español; identificadores de código, tablas y
  campos de la API en inglés.
- **Python**: PEP 8, líneas de hasta 120 caracteres. Consultas SQL siempre con parámetros (`%s`), nunca
  interpolando valores. Si se construye SQL dinámico, que sea solo con nombres de columnas de listas fijas.
- **Errores de validación**: lanza `services.ValidationError("mensaje para el usuario")` y la API responde `422`.
- **Transacciones**: el endpoint llama a `commit()` al final, cuando todo es válido. No confirmes a mitad.
- **Frontend**: todo dato que se inserte en el HTML pasa por `esc()`. Sin dependencias nuevas salvo que se
  puedan servir desde `static/vendor/`.

## Cambios en la API

- `/api/v1` es un contrato con otras aplicaciones. Dentro de v1 solo se hacen **cambios compatibles**:
  añadir campos, endpoints o parámetros opcionales. Renombrar o quitar algo requiere `/api/v2`.
- Todo endpoint nuevo o modificado se documenta en `openapi.py` y se cubre con una prueba en `tests/`.
- Si cambia el uso, actualiza también [docs/API.md](docs/API.md).

## Cambios en la base de datos

1. Añade una nueva entrada **al final** de `MIGRATIONS` en `db.py`, con el siguiente número de versión:
   ```python
   (2, """
   ALTER TABLE employees ADD COLUMN manager_email text;
   """),
   ```
2. No modifiques nunca una migración ya integrada en `main`: las instalaciones existentes no la volverían a aplicar.
3. Haz que la migración funcione con datos existentes (valores por defecto, columnas que admitan nulos…).
4. Las pruebas parten de una base de datos vacía, así que aplican todas las migraciones desde cero.
5. Actualiza el diagrama de [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) si cambia el modelo.

## Publicar una versión

1. Mueve lo de *Sin publicar* del CHANGELOG a una nueva sección `## [X.Y.Z] - AAAA-MM-DD`.
2. Crea la etiqueta: `git tag -a vX.Y.Z -m "Versión X.Y.Z"` y `git push --tags`.
3. Si usáis contenedores, publica la imagen con la misma etiqueta.
