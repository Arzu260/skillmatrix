## Qué cambia y por qué

<!-- Describe el cambio y el motivo. Enlaza el issue si existe: "Cierra #12". -->

## Cómo probarlo

<!-- Pasos para que quien revisa lo compruebe. -->

## Comprobaciones

- [ ] Las pruebas pasan (`pytest -q`) y he añadido pruebas para lo nuevo.
- [ ] Si cambia la API: es compatible con v1 y está documentada en `openapi.py` y `docs/API.md`.
- [ ] Si cambia la base de datos: nueva migración al final de `MIGRATIONS` (sin tocar las existentes).
- [ ] Documentación y `CHANGELOG.md` actualizados si afecta a usuarios o integradores.
