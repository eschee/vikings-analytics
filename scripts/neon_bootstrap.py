"""Set up the Neon database: migrations, two roles, seed data.

Run once, as the Neon owner:

    python scripts/neon_bootstrap.py            # do it
    python scripts/neon_bootstrap.py --dry-run  # print the SQL, no passwords

Reads NEON_ADMIN_URL from .env. Writes the two derived connection strings back
into .env and prints NOTHING that could reconstruct them -- only masked
confirmations. Copy the values out of .env yourself when pasting into Vercel
and GitHub; they never pass through a terminal or a chat log.

THE TWO ROLES

web_reader      SELECT on the five tables the site reads, and nothing else.
                It cannot write, and it cannot see plays/players/contracts,
                which are not uploaded at all.

refresh_writer  Exactly the verbs the refresh job issues, and no DDL. It can
                replace the season's games and append a run; it cannot create
                or alter a table, which is why `hatewatch.run --skip-schema`
                exists. Migrations are applied here, by the owner, instead.

Both get SELECT on every table they read -- for refresh_writer that includes
sim_runs (INSERT ... RETURNING run_id needs SELECT on the returned column) and
game_impacts (the summary queries and the retention DELETE both read it).
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from urllib.parse import urlsplit, urlunsplit, quote

import psycopg
from dotenv import load_dotenv
from psycopg import sql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "etl"))

ENV_PATH = os.path.join(ROOT, ".env")
SQL_DIR = os.path.join(ROOT, "sql")

WEB_READER = "web_reader"
REFRESH_WRITER = "refresh_writer"

# The only tables that go to Neon. plays, players and contracts stay local:
# 163 MB of analysis data that neither the site nor the refresh job reads.
SITE_TABLES = ["games", "teams", "sim_runs", "team_odds", "game_impacts"]

PASSWORD_BYTES = 32  # ~43 chars of URL-safe base64


def mask(url: str) -> str:
    """A form of the URL safe to print: no password, truncated host."""
    parts = urlsplit(url)
    host = parts.hostname or "?"
    tail = host[-24:] if len(host) > 24 else host
    return f"{parts.scheme}://{parts.username}:****@...{tail}{parts.path}"


def derive_url(admin_url: str, user: str, password: str) -> str:
    """Same host and database as the admin URL, different credentials."""
    parts = urlsplit(admin_url)
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def write_env(updates: dict[str, str]) -> None:
    """Replace or append keys in .env, leaving every other line untouched."""
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as fh:
            lines = fh.read().splitlines()

    remaining = dict(updates)
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else None
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    for key, value in remaining.items():
        out.append(f"{key}={value}")

    # 0600: the file holds live credentials.
    fd = os.open(ENV_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join(out).rstrip("\n") + "\n")


def apply_migrations(conn: psycopg.Connection) -> list[str]:
    names = sorted(f for f in os.listdir(SQL_DIR) if f.endswith(".sql"))
    for name in names:
        with open(os.path.join(SQL_DIR, name)) as fh:
            conn.execute(fh.read())
    conn.commit()
    return names


def grant_statements(maintain: bool) -> list[sql.Composed]:
    """Every grant, built with identifiers rather than string formatting."""
    tables = [sql.Identifier(t) for t in SITE_TABLES]
    both = [sql.Identifier(WEB_READER), sql.Identifier(REFRESH_WRITER)]
    reader = sql.Identifier(WEB_READER)
    writer = sql.Identifier(REFRESH_WRITER)

    stmts = [
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.SQL(", ").join(both)),
        # web_reader: read the five tables, nothing more.
        sql.SQL("GRANT SELECT ON {} TO {}").format(sql.SQL(", ").join(tables), reader),
        # refresh_writer: SELECT on everything it reads...
        sql.SQL("GRANT SELECT ON {} TO {}").format(sql.SQL(", ").join(tables), writer),
        # ...replace the season's games...
        sql.SQL("GRANT INSERT, DELETE ON {} TO {}").format(sql.Identifier("games"), writer),
        # ...append a run...
        sql.SQL("GRANT INSERT ON {}, {}, {} TO {}").format(
            sql.Identifier("sim_runs"), sql.Identifier("team_odds"),
            sql.Identifier("game_impacts"), writer),
        # ...and prune old impact grids. No DELETE on sim_runs: removing a run
        # would cascade and take its team_odds with it, and those are kept.
        sql.SQL("GRANT DELETE ON {} TO {}").format(sql.Identifier("game_impacts"), writer),
    ]
    if maintain:
        # PG16+. Lets the job ANALYZE after COPY without owning the tables.
        stmts.append(
            sql.SQL("GRANT MAINTAIN ON {} TO {}").format(sql.SQL(", ").join(tables), writer)
        )
    # Nothing new is readable by accident later.
    stmts.append(
        sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "REVOKE ALL ON TABLES FROM PUBLIC")
    )
    return stmts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the SQL that would run; generate no passwords")
    ap.add_argument("--skip-migrations", action="store_true")
    ap.add_argument("--skip-seed", action="store_true",
                    help="do not upload teams and the 2026 games")
    args = ap.parse_args()

    load_dotenv(ENV_PATH)

    # The dry run deliberately needs no credentials: it is for reading the
    # plan before anything is created.
    if args.dry_run:
        print("Would run, in order:\n")
        print("  1. every migration in sql/")
        print(f"  2. CREATE ROLE {WEB_READER} LOGIN PASSWORD '<generated>'")
        print(f"     CREATE ROLE {REFRESH_WRITER} LOGIN PASSWORD '<generated>'")
        print("  3. these grants:")
        for stmt in grant_statements(maintain=True):
            print("       " + stmt.as_string(None) + ";")
        print("  4. upload teams and the 2026 games")
        print("  5. write NEON_WEB_READER_URL and NEON_REFRESH_URL into .env")
        return 0

    admin = os.environ.get("NEON_ADMIN_URL")
    if not admin:
        raise SystemExit(
            "NEON_ADMIN_URL is not in .env. Add the Neon owner connection "
            "string there (edit the file directly; do not paste it into a "
            "shell command, where it would land in your history)."
        )

    try:
        conn = psycopg.connect(admin)
    except psycopg.Error:
        raise SystemExit(
            "could not connect with NEON_ADMIN_URL (driver message withheld: "
            "it contains the host and user). Check the value in .env."
        )

    with conn:
        version_num = int(conn.execute("show server_version_num").fetchone()[0])
        version = conn.execute("select version()").fetchone()[0].split(" on ")[0]
        owner = conn.execute("select current_user").fetchone()[0]
        db = conn.execute("select current_database()").fetchone()[0]
        maintain = version_num >= 160000

        print(f"  server         : {version}")
        print(f"  database       : {db}")
        print(f"  connected as   : {owner}")
        print(f"  GRANT MAINTAIN : {'supported' if maintain else 'not available (PG<16)'}")
        if not maintain:
            print("                   ANALYZE will warn and continue; harmless.")

        if not args.skip_migrations:
            names = apply_migrations(conn)
            print(f"\n  migrations applied: {', '.join(names)}")

        # --- roles ----------------------------------------------------------
        print("\n  creating roles...")
        created = {}
        for role in (WEB_READER, REFRESH_WRITER):
            password = secrets.token_urlsafe(PASSWORD_BYTES)
            created[role] = password
            exists = conn.execute(
                "select 1 from pg_roles where rolname = %s", (role,)
            ).fetchone()
            if exists:
                conn.execute(
                    sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(password))
                )
                print(f"    {role}: existed, password rotated")
            else:
                conn.execute(
                    sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(password))
                )
                print(f"    {role}: created")

        for stmt in grant_statements(maintain):
            conn.execute(stmt)
        conn.commit()
        print(f"    grants applied on: {', '.join(SITE_TABLES)}")

        # --- seed -------------------------------------------------------------
        if not args.skip_seed:
            import load_data

            print("\n  uploading teams and the 2026 season...")
            load_data.load_snapshot_table(conn, load_data.TEAMS)
            load_data.load_season_table(conn, load_data.GAMES, [2026])
            conn.commit()

        # --- credentials ------------------------------------------------------
        reader_url = derive_url(admin, WEB_READER, created[WEB_READER])
        writer_url = derive_url(admin, REFRESH_WRITER, created[REFRESH_WRITER])
        write_env({
            "NEON_WEB_READER_URL": reader_url,
            "NEON_REFRESH_URL": writer_url,
        })

    print("\n  written to .env (values not shown):")
    print(f"    NEON_WEB_READER_URL = {mask(reader_url)}")
    print(f"    NEON_REFRESH_URL    = {mask(writer_url)}")
    print("\n  Copy them out of .env yourself:")
    print("    NEON_WEB_READER_URL -> Vercel env var DATABASE_URL")
    print("    NEON_REFRESH_URL    -> GitHub secret NEON_REFRESH_URL")
    print("    NEON_ADMIN_URL      -> stays local. Never Vercel, never GitHub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
