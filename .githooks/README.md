# Git hooks

These hooks automate the per-branch DB / S3 workflow for cloud development.

## What's here

| Hook | Trigger | What it does |
|---|---|---|
| `post-checkout` | After `git checkout` / `git switch` | Switches `backend/.env` to point at the branch's DB and S3 prefix. Creates them on RDS / S3 if this is the first checkout of the branch. Kills any running Daphne so the next request reads new env. |
| `post-merge` | After `git pull` / `git merge` | If the merge included new migration files, auto-runs `python manage.py migrate` against the current branch's DB. |

## Activation

Hooks are not active by default after `git clone`. Run once per machine:

```bash
./bin/chatpop setup
```

That points `core.hooksPath` at this directory and verifies prerequisites.

## When hooks skip silently

- Repo not configured for cloud mode (no `AWS_PROFILE=chatpop` in `backend/.env`)
- File-level checkouts (`git checkout -- somefile`)
- Detached HEAD checkouts (`git checkout <sha>`)
- No `.dev-identity` file present

## Disabling temporarily

If you need to bypass a hook for one command:

```bash
git -c core.hooksPath=/dev/null checkout <branch>
```

To disable permanently for this clone:

```bash
git config --unset core.hooksPath
```

## Troubleshooting

If a hook fails mid-run (e.g., AWS credentials expired), it will exit
non-zero but the git command itself still succeeds — git considers
post-* hooks advisory. Re-run `./infra/configure-env.sh` manually after
fixing the underlying issue.
