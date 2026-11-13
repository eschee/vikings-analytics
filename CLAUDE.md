# Vikings Analytics — Project Rules

## Start here
Read `docs/PROJECT.md` at the start of every session. It holds the vision,
the architecture, what is built, the decisions and why, the known limits and
the roadmap. This file is the rules; that one is the context.

## About
Vikings-focused NFL analytics project. Python 3.12 venv in `.venv`, local Postgres 17
(connection string in `.env` as DATABASE_URL). Data comes from nflverse via nflreadpy
(NOT nfl_data_py, which is deprecated). Goal: analysis + prediction models, later a
FastAPI backend, React frontend, and a hosted Postgres (Neon) copy.

## Safety rules
- Only read and edit files inside this project folder.
- Do not use sudo or Homebrew (brew). If something seems to need them, stop and
  tell me what and why instead.
- Only install Python packages into `.venv`, and update requirements.txt when you do.
- Never commit `.env`, data files, or anything in .gitignore.

## Security rules
- Never commit secrets. Secrets live only in `.env`, Vercel env vars, or GitHub
  Actions secrets. Never put a secret in a `NEXT_PUBLIC_` variable — anything with
  that prefix is shipped to the browser.
- Always use parameterized SQL queries. Never build SQL by joining strings.
- The website uses a read-only database user limited to the result tables. Only
  the data refresh job uses the write user.
- Validate all URL parameters and inputs against allowed values; show a 404 for
  anything else.
- No user accounts, logins, or personal data without asking me first.
- Before adding any new package, confirm it is real, widely used, and maintained.
- Before I merge any PR, run a security review of the changes.

## Git workflow (you handle git)
- Never work directly on `main`. Create a branch per feature: `feature/<short-name>`.
- Make small commits with clear messages as you complete each piece.
- Push the branch and open a pull request with `gh pr create` when a feature works.
- Ask me before merging a PR into main.
- Never force-push or rewrite history.
- Stage files by name with `git add <file>`; never use `git add -A` or `git add .`
- Briefly explain each git command you run and why, since I'm learning git.

## Working style
- Explain what code does as you write it; I want to understand it.
- Check real function and column names in libraries before using them.

## Working with me
- I am learning. Explain what you are doing and why, not just what changed.
  When you make a judgement call, say what the alternative was.
- For anything I do myself — dashboards, secrets, pasting values, clicking
  through a UI — give me numbered, step-by-step instructions, naming the exact
  screen and the exact field. Do not assume I know where something lives.
- Before any change to the database, to secrets, or to deployment: show me a
  plan and wait for my OK. That includes schema migrations, roles and grants,
  environment variables, and anything that runs against Neon, Vercel or
  GitHub Actions. Ordinary code changes do not need this.
- Never print a secret value. Not a password, not a connection string, not a
  token — not even partially, and not in a command you ask me to run. Put it
  on the clipboard with `pbcopy`, or write it to a gitignored file, and tell
  me only the variable name and where it goes.
