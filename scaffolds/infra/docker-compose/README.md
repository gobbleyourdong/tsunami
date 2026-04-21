# infra/docker-compose

**Pitch:** multi-service stack — web + db + cache + reverse-proxy. All
services wired with healthchecks + `depends_on: { condition: service_healthy }`
so `docker compose up` waits for Postgres before the web service boots.
env-file pattern for secrets, named volumes for persistence, Caddy in
front so you get HTTPS with a one-line swap.

## Quick start

```bash
cp .env.example .env
# edit .env — at minimum set POSTGRES_PASSWORD

docker compose up --build
# web:  http://localhost
# health: http://localhost/health
```

## Services

| Service | Image                 | Purpose                              | Healthcheck            |
|---------|-----------------------|--------------------------------------|------------------------|
| `web`   | built from `web/`     | app server (swap `server.js` for yours) | GET :3000/health      |
| `db`    | `postgres:16-alpine`  | primary database                      | `pg_isready`           |
| `cache` | `redis:7-alpine`      | cache / queue backend                 | `redis-cli ping`       |
| `proxy` | `caddy:2-alpine`      | reverse proxy / TLS termination       | n/a (stateless)        |

## Customize

- **Swap in your own app** → replace `web/server.js` + `web/package.json`
  (or point the Dockerfile at a different language/framework). The
  healthcheck endpoint is `GET /health` — keep it, or update the
  healthcheck block in `docker-compose.yml`.
- **Add services** → append to `services:` with `depends_on:` if needed.
  For anything stateful, add a named volume at the bottom.
- **TLS** → change `:80` in `proxy/Caddyfile` to your domain
  (`app.example.com { reverse_proxy web:3000 }`) and Caddy auto-provisions
  Let's Encrypt certs at first request.
- **Staging vs prod** → split env files (`.env.staging`, `.env.production`)
  and point `docker compose --env-file` at the target.
- **Migrations** → don't put them in `db/init.sql` (that runs once, on
  empty volume). Wire a real migration tool into your web service
  startup, or add a one-shot `migrate` service.

## Don't

- Commit `.env` — it's in `.gitignore` for a reason
- Expose database ports to the host unless you're local-testing
- Use `latest` image tags in production (pin versions)

## Anchors

`docker-compose`, `compose.yml`, `Caddy`, `Traefik`, `nginx`, `supabase-compose`.
