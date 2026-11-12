-- Teams lookup: conference and division for each franchise.
-- Source: nflreadpy.load_teams()
--
-- Upstream ships 36 rows, not 32: LAR, OAK, SD and STL are legacy rows for
-- relocated franchises. Schedules from 2022 on use LA (not LAR) for the Rams,
-- LV for the Raiders and LAC for the Chargers. Keeping the legacy rows means
-- older seasons can still join, but anything that needs "the current NFL"
-- (standings, playoff seeding) must filter on is_current -- otherwise NFC West
-- has six teams and division seeding breaks.

CREATE TABLE IF NOT EXISTS teams (
    team_abbr       TEXT PRIMARY KEY,
    team_name       TEXT,
    team_nick       TEXT,
    team_conf       TEXT,                 -- AFC / NFC
    team_division   TEXT,                 -- e.g. "NFC North"
    is_current      BOOLEAN NOT NULL,     -- false for LAR/OAK/SD/STL
    team_color      TEXT,                 -- for the site's team styling later
    team_color2     TEXT,
    team_logo_espn  TEXT
);

CREATE INDEX IF NOT EXISTS idx_teams_conf     ON teams (team_conf);
CREATE INDEX IF NOT EXISTS idx_teams_division ON teams (team_division);
CREATE INDEX IF NOT EXISTS idx_teams_current  ON teams (is_current);
