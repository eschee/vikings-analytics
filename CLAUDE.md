# Vikings Analytics — Project Rules

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

## Git workflow (you handle git)
- Never work directly on `main`. Create a branch per feature: `feature/<short-name>`.
- Make small commits with clear messages as you complete each piece.
- Push the branch and open a pull request with `gh pr create` when a feature works.
- Ask me before merging a PR into main.
- Never force-push or rewrite history.
- Briefly explain each git command you run and why, since I'm learning git.

## Working style
- Explain what code does as you write it; I want to understand it.
- Check real function and column names in libraries before using them.
