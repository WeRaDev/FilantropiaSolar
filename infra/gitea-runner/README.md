# Gitea Actions Runner (containerized)

Containerized `act_runner` for the local `wera-global` Gitea instance. It
replaces the ad-hoc Homebrew/nohup daemon setup so the runner lifecycle is
managed by Docker instead of manual process handling.

## Lifecycle coupling with Gitea

- Gitea itself runs via Homebrew (`brew services start gitea`).
- Docker Desktop starts at login; this service has `restart: unless-stopped`,
  so the runner comes up automatically with Docker Desktop and keeps retrying
  until Gitea is reachable at `http://host.docker.internal:3000`.
- Effect: when Gitea is initialised (brew service start at login), the runner
  is already waiting and connects as soon as Gitea answers.

## Layout

- `docker-compose.yml` — single `runner` service (`gitea/act_runner:0.4.0`).
- `config.yaml` — runner config (labels map to `gitea/runner-images`, which
  provide Node.js + Python 3.12 as required by the CI workflows).
- `env.example` — copy to `.env` and fill in the registration token.
- `runner-data` volume — holds `/data/.runner` (registration) and job workdirs.

## First-time setup

```bash
cp env.example .env
# put a valid registration token into .env (see env.example for the API call)
docker compose up -d
docker compose logs -f runner
```

Verify registration in Gitea:
`http://127.0.0.1:3000/org/wera-global/settings/actions/runners` (or the org
runners API) should list `wera-global-docker-runner` as online.

## Operations

```bash
docker compose up -d        # start (idempotent)
docker compose restart      # pick up config.yaml changes
docker compose down         # stop (registration persists in the volume)
docker compose down -v      # stop AND wipe registration + workdirs
```

Token is only needed at first registration; after that the runner uses
`/data/.runner`. To rotate: put a new token in `.env` and
`docker compose down -v && docker compose up -d`.

## Notes

- Job containers run as siblings on the host Docker daemon (socket mounted at
  `/var/run/docker.sock`); they reach Gitea via `host.docker.internal:3000`,
  matching `github-server-url` and `GITEA_URL` in `.gitea/workflows/`.
- The legacy host daemon (`act_runner daemon` on the Mac, org runner
  `wera-global-local-runner`) is superseded by this stack and should stay
  stopped to avoid two runners racing for the same jobs.
- CI debugging history (image choice, token auth, tkinter, ruff pin) is in the
  PR#3 discussion and `tasks/revisor-quality-debt.md`.
