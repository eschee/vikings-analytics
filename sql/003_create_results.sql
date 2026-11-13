-- Simulation output tables: what the website reads.
--
-- Three tables. sim_runs is one row per simulation run, team_odds is one row
-- per team per run, and game_impacts is one row per (game, subject team, goal)
-- per run. Old runs are kept so odds can be charted over time, which is why
-- every table is keyed by run_id rather than being overwritten in place.
--
-- NO FOREIGN KEYS TO games OR teams, deliberately. The ETL replaces games one
-- season at a time (DELETE then INSERT) and fully replaces teams (TRUNCATE).
-- A foreign key pointing at either would make the next refresh fail outright,
-- or -- worse, with ON DELETE CASCADE -- silently delete the stored history we
-- are keeping these tables for. The run_id reference is safe because only this
-- code writes sim_runs.
--
-- The website reads these tables through a read-only database user. Writes
-- come only from the refresh job (hatewatch/run.py).

CREATE TABLE IF NOT EXISTS sim_runs (
    run_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    season          SMALLINT    NOT NULL,
    week            SMALLINT    NOT NULL,   -- first unplayed week at run time
    n_sims          INTEGER     NOT NULL,
    data_as_of      TIMESTAMPTZ NOT NULL,   -- when games/lines were refreshed
    model_version   TEXT        NOT NULL,   -- see hatewatch/config.py
    CONSTRAINT sim_runs_n_sims_positive CHECK (n_sims > 0)
);

CREATE INDEX IF NOT EXISTS idx_sim_runs_season_week
    ON sim_runs (season, week, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sim_runs_created
    ON sim_runs (created_at DESC);


-- One row per team per run. Stored for all 32 teams: a single simulation
-- yields every team's numbers, so throwing 31 of them away would be waste.
CREATE TABLE IF NOT EXISTS team_odds (
    run_id          BIGINT      NOT NULL
                    REFERENCES sim_runs (run_id) ON DELETE CASCADE,
    team            TEXT        NOT NULL,
    playoff_pct     NUMERIC(6,3) NOT NULL,
    division_pct    NUMERIC(6,3) NOT NULL,
    top_seed_pct    NUMERIC(6,3) NOT NULL,
    -- Mean playoff seed in the iterations where the team got in. NULL when a
    -- team never made the playoffs in any iteration, because the average of
    -- nothing is not zero -- zero would read as "always the #0 seed".
    avg_seed        NUMERIC(5,3),
    PRIMARY KEY (run_id, team)
);

CREATE INDEX IF NOT EXISTS idx_team_odds_team ON team_odds (team);


-- One row per (game, subject team, goal) per run.
--
-- "team" is the team whose point of view this row takes -- the fan reading the
-- site -- and is usually NOT playing in the game. "root_for" is which side
-- that fan should want to win.
CREATE TABLE IF NOT EXISTS game_impacts (
    run_id            BIGINT      NOT NULL
                      REFERENCES sim_runs (run_id) ON DELETE CASCADE,
    game_id           TEXT        NOT NULL,
    team              TEXT        NOT NULL,   -- subject team (the fan)
    goal              TEXT        NOT NULL,
    root_for          TEXT        NOT NULL,   -- which side to want
    -- Swing in the goal if root_for wins rather than loses. Percentage points
    -- for the probability goals, draft picks for the draft goal.
    impact_pts        NUMERIC(7,3) NOT NULL,
    root_for_win_pct  NUMERIC(6,3) NOT NULL,  -- model's chance root_for wins
    tier              TEXT        NOT NULL,
    reason_code       TEXT        NOT NULL,
    PRIMARY KEY (run_id, game_id, team, goal),

    -- Allowlists rather than free text: the website renders these directly,
    -- so a typo in the writer should fail loudly here instead of reaching a
    -- page as an unknown value.
    CONSTRAINT game_impacts_goal_known CHECK (
        goal IN ('playoffs', 'division', 'top_seed', 'draft')),
    CONSTRAINT game_impacts_tier_known CHECK (
        tier IN ('must_win', 'root_hard', 'a_little', 'doesnt_matter')),
    CONSTRAINT game_impacts_reason_known CHECK (
        reason_code IN ('division_rival', 'wildcard_competitor',
                        'top_seed_race', 'tiebreaker_effect', 'other'))
);

CREATE INDEX IF NOT EXISTS idx_game_impacts_run_team
    ON game_impacts (run_id, team, goal);
CREATE INDEX IF NOT EXISTS idx_game_impacts_game
    ON game_impacts (run_id, game_id);
CREATE INDEX IF NOT EXISTS idx_game_impacts_tier
    ON game_impacts (run_id, team, tier);
