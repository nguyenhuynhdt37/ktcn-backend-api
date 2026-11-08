# KTCT branch deployments

| Branch | Automatic target | Website | API and storage |
|---|---|---|---|
| `dev` | Test | `test-ktcn.itup.io.vn/vi`, `test-admin-ktcn.itup.io.vn` | `test-api-ktcn.itup.io.vn`, `test-media-ktcn.itup.io.vn` |
| `main` | Production | `ktcn.itup.io.vn/vi`, `admin-ktcn.itup.io.vn` | `api-ktcn.itup.io.vn`, existing production MinIO |

All three repositories have `dev` and `main`:
`ktcn-backend-api`, `ktcn-admin-portal`, and `ktcn-client-frontend` under
`nguyenhuynhdt37`. Develop and review on dev, then merge dev into main when ready
for production. Pushing either branch builds and deploys that component only.
There is no separate deployment approval step on main. Pull requests build on
GitHub-hosted Linux AMD64 runners and never deploy.

Merging branches transfers code only. Test PostgreSQL (`university_cms_test`),
Redis, MinIO, backend and their volumes are separate from production
(`university_cms`). Data/uploads are not copied during deployment or merge. Both
environments share the physical server; they are not separate VMs. Test services
retain their data between code deployments.

## Build and deployment

GitHub builds one image configured for the target branch, publishes it to GHCR,
and sends its immutable digest to the server. Test and production public API/site
URLs are set at build time. Builds are canceled when superseded on the same
branch. The host verifies the commit is still the branch head before deploying.

Only deploy jobs run on dedicated native server runners, with labels
`[self-hosted, linux, x64, ktcn-deploy, ktcn-<component>]`. Root-owned pre-job hooks
accept the exact repo/workflow and only `dev:deploy-test` or
`main:deploy-production`. PR events, other branches and legacy promotion jobs are
rejected before their steps execute. Runner accounts have no Docker membership
and cannot read production `.env` files. They call the host deploy script through
SSH loopback (`127.0.0.1`) with a key restricted to one component and branch. No
Tailscale/VPN credentials or public SSH endpoint is required by Actions.

The host serializes deployments using a file lock. Dev updates the test Compose
service. Main updates that component in its existing production Compose project,
preserving existing ports, environment files, volumes and other components.
Backend deployments run Alembic migrations against the selected environment.
Production backend deployments create a PostgreSQL custom-format backup before
migration. Health checks include DB/Redis for backend, `/vi` for website, and `/`
for admin. On failure, the previous application image is restored where available.
Database schema is never automatically downgraded or restored; keep migrations
backward compatible, or explicitly restore a backup during maintenance.

## Server files

Root: `/home/admin/KTCT/deploy` (outside source checkouts).

- `bin/deploy.py`: installed branch-bound deploy tool.
- `staging/compose.yml`, `backend.env`, `db.env`, `minio.env`: separate test stack.
- `staging/admin-login.json`: generated test superadmin credentials (0600).
- `staging-state.json`: last successful test image/commit per component.
- `production-state.json`: last successful production image/commit per component.
- `production/*-before.json`: prior image tags for component rollback.
- `deployments/{staging,production}-<component>.json`: deployment history.
- `backups/main-backend-*.dump`: production backups before backend migrations.

Test bootstrapping copies DDL and Alembic version metadata only. Production users,
content and credentials are not copied. Test has a separate superadmin, vi/en
languages and header/footer navigation. AI credentials and push keys are not
copied to test. `bootstrap.py` is for first-time initialization; do not run it on a
live stack to reset data. Backup/image retention is initially manual.

## Routing

Existing Traefik gateway: `admin@10.10.10.99`.
Dynamic config: `/opt/traefik/config/dynamic.yml`.
Follow the existing router/service layout used by `/usr/local/bin/deploy`, routing
HTTPS to `10.10.10.100`:

| Hostname | Host port |
|---|---:|
| `test-ktcn.itup.io.vn` | 13002 |
| `test-admin-ktcn.itup.io.vn` | 15177 |
| `test-api-ktcn.itup.io.vn` | 18000 |
| `test-media-ktcn.itup.io.vn` | 19000 |
| `ktcn.itup.io.vn` | 3002 |
| `admin-ktcn.itup.io.vn` | 5177 |
| `api-ktcn.itup.io.vn` | 8000 |

Test PostgreSQL and Redis do not publish host ports. Production PostgreSQL's host
port remains 5433. Routing is configured once; code deployments keep these ports.

## Setup and maintenance

The installed native runner services are `ktcn-runner-backend`,
`ktcn-runner-frontend`, and `ktcn-runner-admin`. Inspect with `systemctl status`
and `journalctl -u`. `install-runners.py`, run with sudo, verifies the official
Linux AMD64 runner archive's SHA256 digest before installation. It prepares
unprivileged system users, protected service units and root-owned job guards.
Native runners update themselves. Guard/tool updates require host administration.

Local private keys stay in `~/.config/ktcn-deploy`, outside all repositories:

| Key file | SSH forced-command mode |
|---|---|
| `backend`, `frontend`, `admin` | `stage-backend`, `stage-frontend`, `stage-admin` |
| `prod-backend`, `prod-frontend`, `prod-admin` | `prod-backend`, `prod-frontend`, `prod-admin` |

Public keys in admin's authorized_keys use:
`restrict,command="/usr/bin/python3 /home/admin/KTCT/deploy/bin/deploy.py <mode>"`.
The old shared `production` key/mode and manual promote workflow are retired.
The known server ED25519 fingerprint is
`SHA256:h3zMtXFTMp2DVn3V2CTI9d2wUlw4a9TzyCpTXgeuB6c`.

After `gh auth login` as the repo owner, run `configure-github.py` locally to set
staging branch policy to dev, production policy to main, remove deployment
reviewer/wait gates, install each environment's component-bound SSH key and
register/start runners. The separate `runner-register` key invokes the root-owned
`/opt/ktcn-runner-tools/register-runner.py` only. Registration sends a short-lived
GitHub runner token through the existing administration SSH connection; no
personal GitHub token is stored on the server. Runtime registry tokens are kept
only in a temporary Docker config for the duration of each deployment.

Validate deployment and runner guards:

```sh
python3 -m unittest discover -s deploy -p 'test_*.py' -v
```

Validate workflows with actionlint and `.github/actionlint.yaml`. After a change,
verify the target public URL and API health; for media changes verify test
upload/download. Reverting source changes on main triggers another production
deployment, but migrations and data recovery still require appropriate handling.
