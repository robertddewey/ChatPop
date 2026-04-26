# GitHub Actions workflows

Workflows are committed with a `.disabled` suffix so they don't run yet.
GitHub Actions only treats `.yml` and `.yaml` files in this directory as
active workflows. Rename to enable.

## Workflows

| File | Trigger | What it does | Prerequisites |
|---|---|---|---|
| `refresh-dev-seed.yml.disabled` | Push to `main` | Drops + recreates `dev_seed` on RDS, applies migrations and fixtures from current `main`. Keeps the canonical clone source aligned with `main`. | AWS OIDC role + Tailscale OAuth + GitHub repo secrets. See header of the workflow file. |
| `test.yml.disabled` | PR + push to `main` | Spins up ephemeral Postgres (with pgvector) + Redis as service containers, runs `manage.py migrate` + the test suite. Catches schema and code regressions before merge. | None — uses repo's `requirements.txt` directly. |

## Local equivalents

Until these run automatically, the same actions are available manually:

```bash
./bin/chatpop seed refresh     # Refresh dev_seed (manual equivalent of refresh-dev-seed.yml)
cd backend && ./venv/bin/python manage.py test    # Run tests locally
```

## Enabling order

When the team grows past 1-2 developers:

1. Enable `test.yml` first — easy, no AWS setup needed, immediately useful.
2. Set up AWS OIDC + Tailscale OAuth (one-time, ~30 min).
3. Enable `refresh-dev-seed.yml`.
