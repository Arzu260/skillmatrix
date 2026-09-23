# Guía de despliegue

Esta guía explica cómo poner SkillMatrix en marcha en cualquier entorno: un portátil para probarla,
un servidor Windows o Linux, Docker o Kubernetes. Los ejemplos de configuración están en la carpeta
[`deploy/`](../deploy).

**Índice**

1. [Cómo está compuesta](#1-cómo-está-compuesta)
2. [Requisitos](#2-requisitos)
3. [Preparar PostgreSQL](#3-preparar-postgresql)
4. [Configuración](#4-configuración)
5. [Opciones de despliegue](#5-opciones-de-despliegue)
6. [HTTPS y proxy inverso](#6-https-y-proxy-inverso)
7. [Primer arranque](#7-primer-arranque)
8. [Actualizar a una nueva versión](#8-actualizar-a-una-nueva-versión)
9. [Copias de seguridad](#9-copias-de-seguridad)
10. [Monitorización y registros](#10-monitorización-y-registros)
11. [Escalado](#11-escalado)
12. [Lista de comprobación para producción](#12-lista-de-comprobación-para-producción)
13. [Solución de problemas](#13-solución-de-problemas)

---

## 1. Cómo está compuesta

```mermaid
flowchart LR
    U[Navegador] -->|HTTPS| P[Proxy inverso<br/>nginx · IIS · Ingress]
    A[Otras aplicaciones] -->|HTTPS + token| P
    P -->|HTTP| S[SkillMatrix<br/>Python · Waitress<br/>puerto 5000]
    S -->|TCP 5432| D[(PostgreSQL)]
```

- **Un único proceso Python** sirve la interfaz web, la API y la documentación de la API. No hace falta
  Node.js, ni un servidor web aparte, ni ningún paso de compilación.
- **PostgreSQL** guarda todos los datos. La aplicación no escribe nada en disco, así que se puede
  reemplazar o multiplicar sin perder información.
- El **proxy inverso** es opcional, pero se recomienda en producción para servir HTTPS.

## 2. Requisitos

| Componente | Versión | Notas |
|---|---|---|
| Python | 3.10 o superior | Solo si no usáis Docker. |
| PostgreSQL | 13 o superior | Probado con la 16. Vale uno existente o uno gestionado (Azure Database, Amazon RDS, Cloud SQL…). |
| Sistema operativo | Windows Server 2016+, cualquier Linux actual o contenedores | |
| Recursos | 1 vCPU y 512 MB de RAM por instancia | Suficiente para cientos de empleados. |
| Red | Puerto de la aplicación (5000 por defecto) y salida al 5432 de PostgreSQL | La aplicación no necesita acceso a internet. |

## 3. Preparar PostgreSQL

Crea un usuario y una base de datos dedicados (en `psql`, pgAdmin o la consola de vuestro proveedor):

```sql
CREATE USER skillmatrix WITH PASSWORD 'una-clave-larga-y-segura';
CREATE DATABASE skillmatrix OWNER skillmatrix;
```

No hace falta crear tablas: la aplicación las crea al arrancar y aplica las migraciones pendientes
en cada nueva versión.

- El usuario necesita ser **propietario de la base de datos** (o tener permiso para crear tablas en el esquema `public`).
- Con un PostgreSQL gestionado o remoto, activa el cifrado añadiendo `?sslmode=require` al final de `DATABASE_URL`.
- Si el servidor restringe conexiones por IP (`pg_hba.conf` o reglas del proveedor), permite la del servidor de la aplicación.

## 4. Configuración

Toda la configuración se hace con **variables de entorno**. Para instalaciones sin Docker, se pueden poner
en un archivo `.env` junto a `app.py` (plantilla: [`.env.example`](../.env.example)).
El `.env` no se sube al repositorio.

| Variable | Obligatoria | Valor por defecto | Descripción |
|---|:-:|---|---|
| `DATABASE_URL` | Sí | — | `postgresql://usuario:clave@servidor:5432/basedatos` |
| `ADMIN_PASSWORD` | | `admin` | Contraseña del usuario `admin` que se crea la primera vez. Después ya no se usa. |
| `SKILLMATRIX_DEMO` | | `1` | `1` carga datos de ejemplo si la base de datos está vacía. **En producción, `0`.** |
| `HOST` | | `0.0.0.0` | Interfaz de escucha. Detrás de un proxy en la misma máquina, `127.0.0.1`. |
| `PORT` | | `5000` | Puerto de escucha. |
| `THREADS` | | `8` | Peticiones simultáneas por instancia. |
| `DB_POOL_SIZE` | | `10` | Conexiones máximas a PostgreSQL por instancia (≥ `THREADS`). |
| `DB_CONNECT_TIMEOUT` | | `15` | Segundos que espera a PostgreSQL al arrancar antes de dar error. |
| `COOKIE_SECURE` | | `0` | `1` cuando se sirve por HTTPS: la cookie de sesión solo viaja cifrada. |
| `CORS_ORIGINS` | | vacío | Solo si otra web llama a la API desde el navegador: dominios permitidos, separados por comas. |
| `SECRET_KEY` | | generada | Clave para firmar las sesiones. Si no se indica, se genera una y se guarda en la base de datos, compartida por todas las instancias. |

> **Secretos**: `DATABASE_URL` y `ADMIN_PASSWORD` contienen contraseñas. Guárdalas en el gestor de secretos
> de vuestro entorno (Secret de Kubernetes, variables protegidas del servicio, Vault…) o, con `.env`,
> limita los permisos de lectura del archivo al usuario que ejecuta el servicio.

## 5. Opciones de despliegue

Elige la que encaje con vuestra infraestructura:

| Opción | Cuándo usarla |
|---|---|
| [A. Docker Compose](#a-docker-compose) | Probar la aplicación, o un único servidor con Docker. |
| [B. Servidor Linux con systemd](#b-servidor-linux-con-systemd) | Máquina virtual Linux sin contenedores. |
| [C. Servidor Windows como servicio](#c-servidor-windows-como-servicio) | Infraestructura Windows. |
| [D. Kubernetes](#d-kubernetes) | Ya tenéis un clúster. |
| [E. Plataformas gestionadas](#e-plataformas-gestionadas-paas) | Azure App Service, AWS App Runner, Cloud Run, etc. |

### A. Docker Compose

[`docker-compose.yml`](../docker-compose.yml) levanta PostgreSQL y la aplicación juntos.

```bash
git clone https://github.com/Arzu260/skillmatrix.git skillmatrix && cd skillmatrix
cat > .env <<'EOF'
POSTGRES_PASSWORD=una-clave-larga-y-segura
ADMIN_PASSWORD=otra-clave-segura
SKILLMATRIX_DEMO=0
EOF
docker compose up -d --build
docker compose logs -f app
```

Si ya tenéis un PostgreSQL, construid solo la imagen de la aplicación y pasadle la conexión:

```bash
docker build -t skillmatrix:2.0.0 .
docker run -d --name skillmatrix --restart unless-stopped -p 5000:5000 \
  -e DATABASE_URL="postgresql://skillmatrix:CLAVE@servidor-bd:5432/skillmatrix" \
  -e SKILLMATRIX_DEMO=0 skillmatrix:2.0.0
```

La imagen se ejecuta sin permisos de root e incluye una comprobación de salud (`HEALTHCHECK`).

### B. Servidor Linux con systemd

```bash
sudo useradd --system --create-home --home-dir /opt/skillmatrix skillmatrix
sudo -u skillmatrix git clone https://github.com/Arzu260/skillmatrix.git /opt/skillmatrix/app-tmp
sudo -u skillmatrix bash -c 'shopt -s dotglob && mv /opt/skillmatrix/app-tmp/* /opt/skillmatrix/ && rmdir /opt/skillmatrix/app-tmp'
cd /opt/skillmatrix
sudo -u skillmatrix python3 -m venv .venv
sudo -u skillmatrix .venv/bin/pip install -r requirements.txt
sudo -u skillmatrix cp .env.example .env && sudo chmod 600 .env
sudo -u skillmatrix nano .env                       # DATABASE_URL, SKILLMATRIX_DEMO=0, HOST=127.0.0.1…
sudo cp deploy/systemd/skillmatrix.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now skillmatrix
curl http://127.0.0.1:5000/api/health               # {"status":"ok"}
```

Después, configura el proxy inverso ([sección 6](#6-https-y-proxy-inverso)).

### C. Servidor Windows como servicio

1. Instala [Python 3.10+](https://www.python.org/downloads/) marcando *Add Python to PATH*.
2. Clona o copia el proyecto, por ejemplo en `D:\Apps\skillmatrix`.
3. Ejecuta `iniciar.bat` una vez: crea `.env` (edítalo), el entorno `.venv` e instala las dependencias.
   Comprueba que la aplicación arranca y ciérrala.
4. Para que arranque con el servidor, regístrala como servicio. Python no lo permite directamente, así que
   se usa un envoltorio como [NSSM](https://nssm.cc) o [WinSW](https://github.com/winsw/winsw).
   Con NSSM hay un script preparado (PowerShell como administrador):

   ```powershell
   cd D:\Apps\skillmatrix
   .\deploy\windows\instalar-servicio.ps1 -Nssm "C:\Herramientas\nssm.exe"
   ```

   El script registra el servicio con arranque automático, guarda el registro en `logs\` con rotación y
   abre el puerto en el firewall de Windows.

Para publicarlo con HTTPS en IIS, usa *Application Request Routing* + *URL Rewrite* como proxy inverso
hacia `http://localhost:5000` (misma idea que el ejemplo de nginx).

### D. Kubernetes

1. Construye la imagen y publícala en vuestro registro:
   ```bash
   docker build -t REGISTRO/skillmatrix:2.0.0 .
   docker push REGISTRO/skillmatrix:2.0.0
   ```
2. Edita [`deploy/kubernetes/skillmatrix.yaml`](../deploy/kubernetes/skillmatrix.yaml): imagen, `DATABASE_URL`,
   contraseña inicial, dominio y clase del Ingress.
3. Aplícalo:
   ```bash
   kubectl create namespace skillmatrix
   kubectl apply -n skillmatrix -f deploy/kubernetes/skillmatrix.yaml
   kubectl -n skillmatrix rollout status deploy/skillmatrix
   ```

El ejemplo incluye 2 réplicas, *readiness probe* sobre `/api/health` (que comprueba la base de datos),
*liveness probe* solo de TCP (para que una caída de la base de datos no provoque reinicios en cadena),
límites de recursos, ejecución sin root e Ingress con TLS. Con un gestor de secretos externo
(External Secrets, Sealed Secrets, Vault), sustituye el `Secret` en claro del ejemplo.

### E. Plataformas gestionadas (PaaS)

Cualquier plataforma que ejecute contenedores sirve: Azure App Service for Containers, Azure Container Apps,
AWS App Runner/ECS, Google Cloud Run, OpenShift…

- Usa la imagen del `Dockerfile`.
- Define las variables de entorno de la [sección 4](#4-configuración), con `DATABASE_URL` como secreto.
- Configura el puerto 5000 (o cambia `PORT` al que exija la plataforma).
- Usa `/api/health` como comprobación de salud.
- Pon `COOKIE_SECURE=1`: estas plataformas sirven HTTPS por defecto.

## 6. HTTPS y proxy inverso

En producción, sirve la aplicación por **HTTPS**: el login y los tokens de la API viajan en cada petición.

1. Haz que la aplicación escuche solo en local: `HOST=127.0.0.1`.
2. Pon delante un proxy con el certificado de la empresa. Ejemplo de nginx en
   [`deploy/nginx/skillmatrix.conf`](../deploy/nginx/skillmatrix.conf).
3. Activa `COOKIE_SECURE=1`.
4. Permite subidas de hasta 20 MB (importación de Excel): `client_max_body_size 20m` en nginx,
   `maxAllowedContentLength` en IIS.

## 7. Primer arranque

1. Arranca con `SKILLMATRIX_DEMO=0` si no queréis datos de ejemplo.
2. Entra con `admin` y la contraseña de `ADMIN_PASSWORD` y **cámbiala** (barra lateral → *Cambiar contraseña*).
3. En *Administración → Usuarios*, crea los usuarios de RRHH (rol administrador), managers y lectores.
4. Carga los datos: altas manuales, importación de Excel (*Importar / exportar*) o la API.
5. Si otras aplicaciones van a integrarse, crea un token para cada una en *Administración → Aplicaciones*.
6. Ajusta el plazo de caducidad de las evaluaciones en *Administración → Ajustes* (12 meses por defecto).

**Venís de la versión 1 (SQLite):** con la base de datos PostgreSQL vacía, ejecuta
`python migrar_desde_sqlite.py ruta\a\skillmatrix.db`. Se conservan los usuarios y sus contraseñas.

## 8. Actualizar a una nueva versión

1. Haz una copia de seguridad ([sección 9](#9-copias-de-seguridad)).
2. Actualiza el código y las dependencias, y reinicia:

| Entorno | Comandos |
|---|---|
| Linux/Windows sin Docker | `git pull` · `.venv/bin/pip install -r requirements.txt` · reiniciar el servicio |
| Docker Compose | `git pull` · `docker compose up -d --build` |
| Kubernetes | publicar la nueva imagen · `kubectl -n skillmatrix set image deploy/skillmatrix skillmatrix=REGISTRO/skillmatrix:X.Y.Z` |

Los cambios de esquema se aplican solos al arrancar. Cada versión del esquema se registra en la tabla
`schema_version`, y un bloqueo en PostgreSQL impide que dos instancias migren a la vez.
Revisa el [CHANGELOG](../CHANGELOG.md) antes de actualizar.

## 9. Copias de seguridad

Todo el estado está en PostgreSQL, así que basta con copiar la base de datos:

```bash
# Copia (formato comprimido)
pg_dump -Fc -h SERVIDOR -U skillmatrix skillmatrix > skillmatrix_$(date +%F).dump

# Restauración en una base de datos vacía
pg_restore -h SERVIDOR -U skillmatrix -d skillmatrix --no-owner skillmatrix_2026-09-23.dump
```

Programa la copia (cron, Programador de tareas de Windows, CronJob de Kubernetes o la copia automática de
vuestro PostgreSQL gestionado) y **prueba a restaurarla** de vez en cuando.

## 10. Monitorización y registros

- **Salud**: `GET /api/health` devuelve `200 {"status":"ok"}` si la aplicación responde y la base de datos
  está accesible. Úsalo en el balanceador, en las sondas de Kubernetes o en vuestra herramienta de monitorización.
- **Registros**: la aplicación escribe en la salida estándar y de error.
  - systemd: `journalctl -u skillmatrix`
  - Docker: `docker compose logs app`
  - NSSM: `logs\skillmatrix.log`
  - Kubernetes: `kubectl logs`
- **Tareas de administración desde consola**: `python gestion.py --help` (cambiar contraseñas, crear
  usuarios, revocar todos los tokens de API ante un incidente).
- **Auditoría funcional**: cada cambio de nivel queda en la tabla `assessment_history`, con autor y origen
  (`web`, `api`, `import`). El último uso de cada token de API se ve en *Administración → Aplicaciones*.

## 11. Escalado

La aplicación puede ejecutarse en **varias instancias a la vez** detrás de un balanceador, sin afinidad de sesión:

- Las sesiones van en cookies firmadas con una clave común guardada en la base de datos (o en `SECRET_KEY`).
- Las migraciones usan un bloqueo en PostgreSQL, así que las instancias pueden arrancar a la vez.
- Ninguna instancia guarda estado en disco.

Cada instancia abre como máximo `DB_POOL_SIZE` conexiones: comprueba que `instancias × DB_POOL_SIZE`
no supera el `max_connections` de PostgreSQL.

## 12. Lista de comprobación para producción

- [ ] `SKILLMATRIX_DEMO=0`.
- [ ] Contraseña de `admin` cambiada tras el primer acceso.
- [ ] Contraseña de la base de datos larga y guardada como secreto; `.env` con permisos restringidos.
- [ ] Servida por HTTPS, con `COOKIE_SECURE=1`, y la aplicación sin exponerse directamente (`HOST=127.0.0.1` o red interna).
- [ ] Copia de seguridad diaria programada y restauración probada.
- [ ] Monitorización de `/api/health`.
- [ ] Un token de API por aplicación integrada, con el permiso mínimo necesario (lectura si no necesita escribir).
- [ ] Usuarios personales para cada persona de RRHH o manager, sin cuentas compartidas.

## 13. Solución de problemas

| Síntoma | Causa probable y solución |
|---|---|
| Al arrancar: *No se puede conectar a PostgreSQL* | PostgreSQL parado, `DATABASE_URL` incorrecta o conexión bloqueada por firewall o `pg_hba.conf`. Prueba con `psql "<DATABASE_URL>"` desde el mismo servidor. |
| *Falta la variable DATABASE_URL* | No existe `.env` o no está junto a `app.py`, o la variable no llega al contenedor o servicio. |
| `permission denied for schema public` | El usuario no es propietario de la base de datos: `ALTER DATABASE skillmatrix OWNER TO skillmatrix;` |
| El login funciona pero la sesión se pierde en cada petición | `COOKIE_SECURE=1` sin HTTPS. Desactívalo o sirve por HTTPS. |
| La importación de Excel falla con archivos grandes | Límite de tamaño del proxy (`client_max_body_size` / `maxAllowedContentLength`). |
| Otra web recibe errores CORS al llamar a la API | Añade su dominio a `CORS_ORIGINS`. Las llamadas entre servidores no necesitan CORS. |
| `too many connections` en PostgreSQL | Reduce `DB_POOL_SIZE` o el número de instancias, o aumenta `max_connections`. |
| Se ha perdido la contraseña de un administrador | Desde el servidor, con acceso al `.env`: `python gestion.py cambiar-clave admin`. Ejecuta `python gestion.py --help` para ver otras tareas: crear usuarios, listarlos o revocar todos los tokens. |
