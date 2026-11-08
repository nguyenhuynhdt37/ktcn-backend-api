# KTCT deployment

Three repositories publish Docker images on pushes to `main`:

- `nguyenhuynhdt37/ktcn-backend-api`
- `nguyenhuynhdt37/ktcn-client-frontend`
- `nguyenhuynhdt37/ktcn-admin-portal`

Pull requests build images without publishing or deploying. Each main-branch run
builds test and production variants from one commit, then deploys its component to
test. Frontend public URLs are baked into each variant. Backend variants may share
the same digest. Every deployment uses the immutable image digest, never `latest`. Superseded builds
are canceled; the host also checks the current main commit before deploying, so
a slow older build cannot replace a newer test candidate. Pending production
approval does not block further test builds.

When all three test components pass HTTP checks (including DB/Redis health), the
server writes a full release manifest. The workflow that completes that candidate
opens a **production approval** job. Review the test website and admin, then choose
**Review deployments → Approve and deploy**. A preflight rejects production if its
GitHub environment has no required reviewer. If a newer test deployment occurs
while approval is pending, the old release cannot be promoted: review the newest
release instead. Deploy jobs run on dedicated self-hosted runners on webdeploy, then connect to
127.0.0.1 through SSH. SSH keys are restricted to their component or production
command; test keys cannot deploy production. No VPN, external SSH route, or
Tailscale credentials are required by GitHub Actions.

## Server layout

Configuration and state live at `/home/admin/KTCT/deploy`, outside source checkouts:

- `bin/`: installed deployment scripts (update manually after review).
- `staging/`: Compose, protected environment files, schema initialization marker.
- `staging-state.json`: successful test image/commit for each component.
- `releases/`: immutable manifests identified by `YYYYmmddHHMMSS-<12 hex chars>`.
- `candidate.json`: currently reviewable test release.
- `production-before.json`: application images captured before the latest attempt.
- `production-current.json`, `production-history.json`: successful releases.
- `backups/`: PostgreSQL custom-format backups created before production changes.

Test PostgreSQL, Redis and MinIO use separate volumes. Bootstrap copies production
DDL and Alembic version metadata only, with no production application rows/users.
Test credentials are generated on the host. AI credentials and push notification
keys are not copied to test. Test containers have memory limits.

## Domain routing

Configure these HTTPS routes on the existing proxy/tunnel. The upstream host is
`100.122.190.92` from an existing management network, or `10.10.10.100` from the host LAN:

| Hostname | Upstream port |
|---|---:|
| `test-ktcn.itup.io.vn` | 13002 |
| `test-admin-ktcn.itup.io.vn` | 15177 |
| `test-api-ktcn.itup.io.vn` | 18000 |
| `test-media-ktcn.itup.io.vn` | 19000 |

The fourth route is for test object storage; test API uses its public HTTPS name
because the application's current MinIO client shares one HTTPS setting between
public and internal endpoints. PostgreSQL and Redis test ports are not published.
Protect test hosts with proxy access controls where available, and exclude them
from search indexing. Production routes remain on ports 3002 / 5177 / 8000.

## One-time setup

1. Install this directory's scripts into `/home/admin/KTCT/deploy/bin` and run
   `python3 /home/admin/KTCT/deploy/bin/bootstrap.py` as admin. Re-running preserves
   existing credentials and does not reinitialize an already initialized test DB.
2. Generate four dedicated Ed25519 key pairs (backend/frontend/admin/production)
   locally in `~/.config/ktcn-deploy`. Keep private keys outside all repositories.
3. Add public keys to the host's `~/.ssh/authorized_keys` using forced commands:
   `restrict,command="/usr/bin/python3 /home/admin/KTCT/deploy/bin/deploy.py stage-backend"`
   for the backend test key; similarly `stage-frontend`, `stage-admin`, and
   `production` for the other keys. Preserve existing authorized keys.
4. Pin the verified host key in `~/.config/ktcn-deploy/known_hosts`.
   Verified ED25519 fingerprint at setup:
   `SHA256:h3zMtXFTMp2DVn3V2CTI9d2wUlw4a9TzyCpTXgeuB6c`.
5. Install the three runner accounts and systemd units on the host:
   `sudo python3 /home/admin/KTCT/deploy/bin/install-runners.py`.
   The official Linux AMD64 release archive is verified against its SHA256 digest
   from the GitHub release API before extraction. Runners use distinct system users
   under `/var/lib/ktcn-runners`, without Docker/admin membership. Services restrict
   filesystem writes to their own directories and hide `/home`.
6. Generate a separate local key pair `~/.config/ktcn-deploy/runner-register`.
   Add its public key to admin's authorized_keys with:
   `restrict,command="sudo -n /usr/bin/python3 /opt/ktcn-runner-tools/register-runner.py"`.
   The root-owned registration tool only accepts one of the three known components
   and a short-lived GitHub registration token; it cannot execute arbitrary commands.
7. Run `gh auth login` as the repository owner, then
   `python3 deploy/configure-github.py` locally. This creates staging/production
   environments and main-only branch policies, installs the existing SSH secrets,
   requires owner approval for production, disables admin bypass, and registers
   each repo runner using a one-hour registration token sent over the existing
   management connection. No long-lived personal GitHub token is stored on the
   server. Owner self-review is allowed.
8. Configure the four test DNS/proxy routes above. Merge the workflow changes into
   main. After the three first builds complete, their deployment jobs populate
   test. An initial backend container from the running host image, if present,
   is only a bootstrap diagnostic and cannot form an approved release manifest.

## Runner execution policy

Builds, pull requests, and the reviewer-policy check run on GitHub-hosted machines.
Only deployment jobs use `[self-hosted, linux, x64, ktcn-deploy, ktcn-<component>]`.
Each native runner has a root-owned pre-job hook outside its writable application
folder. The hook accepts only its exact repository, main ref, push/manual-dispatch
origin, expected workflow path, and deploy job IDs. It rejects PR and
pull_request_target events, other branches, arbitrary workflows, and build jobs
before their steps execute. This supplements the main-only environments and
production approval. Services use separate unprivileged users, filesystem
restrictions, memory/CPU limits and no Docker socket access. Maintain trust in
main-branch workflow changes and repository administrators.

Runner services are `ktcn-runner-backend`, `ktcn-runner-frontend`, and
`ktcn-runner-admin`. Inspect with `systemctl status <name>` or
`journalctl -u <name>`. They remain inactive until registered. The native runner
application updates itself through GitHub; deployments still run preinstalled
host scripts, rather than checking out and executing application source on the
runner. Root-owned guard/service changes require explicit host administration.

GHCR credentials from each repository's `GITHUB_TOKEN` are used transiently on the
server to cache both variants. Production normally uses these cached digests.
If an image was pruned, `GHCR_READ_TOKEN` (read:packages across the three packages)
can be configured in the production environment to pull private packages. Token
values exist only in a temporary Docker config, removed when the command exits.

## Promote and roll back

For an automatic candidate, approve the production job in the workflow that
reports `RELEASE_ID=...`. For explicit operations, open **ktcn-backend-api →
Actions → Promote production → Run workflow**, choose `promote` or `rollback`,
and enter the exact release ID. Both operations require production approval.
Only the current tested candidate can be promoted. Rollback accepts only a release
that has previously succeeded in production.

Production keeps the existing Compose project/container names, `.env` files,
volumes, host ports and other services. The deployed application image is supplied
through a separate Compose override. The server pulls/cache-checks all images,
snapshots the current image IDs, creates a DB backup, runs backend migrations,
then replaces and checks backend, frontend, and admin in that order. Deployments
are serialized across all repos with a host-side file lock.

On failure the script attempts to restore previous application images. Database
schema is never automatically downgraded or data automatically restored. A schema
change that is incompatible with the prior image may require a maintenance window
and explicit restore from the saved `.dump`. Keep migrations backward compatible.
A container replacement can cause a short interruption; this is not a zero-downtime
blue/green deployment. Backup, release and image retention are manual initially.

## Validation

Run deployment guard tests:

```sh
python3 -m unittest discover -s deploy -p 'test_*.py' -v
```

Validate workflows with actionlint. Builds run in GitHub-hosted Linux AMD64
runners; the deployment host only pulls and runs the resulting images. After
initial deployment, verify test login, API calls and media uploads through the
public HTTPS domains before approving the first production release. A separate test superadmin and vi/en languages have been provisioned on this
host; login details are stored at `staging/admin-login.json` with mode 0600.
Production users are not copied during bootstrap.

References: [GitHub environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments),
[Self-hosted runner communication](https://docs.github.com/en/actions/reference/runners/self-hosted-runners#communication),
[Pre-job hooks](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/run-scripts).
