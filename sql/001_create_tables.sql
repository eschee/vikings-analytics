-- Vikings Analytics — core schema
-- Run with: psql "$DATABASE_URL" -f sql/001_create_tables.sql
--
-- Source: nflverse via nflreadpy 0.1.5
--   games     <- load_schedules(seasons=...)   season-scoped
--   plays     <- load_pbp(seasons=...)         season-scoped
--   players   <- load_players()                full-league snapshot, no season arg
--   contracts <- load_contracts()              full-league snapshot, no season arg
--
-- Re-runnability: games/plays are reloaded one season at a time (DELETE by
-- season, then INSERT). players/contracts have no season column upstream, so
-- they are fully replaced on each load. See etl/load_data.py.

-- ---------------------------------------------------------------------------
-- games: one row per game, including the betting lines
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS games (
    game_id         TEXT PRIMARY KEY,
    season          SMALLINT    NOT NULL,
    game_type       TEXT,                 -- REG / WC / DIV / CON / SB
    week            SMALLINT,
    gameday         DATE,
    weekday         TEXT,
    gametime        TEXT,                 -- kickoff "HH:MM" in ET, not a timestamp
    away_team       TEXT,
    home_team       TEXT,
    away_score      SMALLINT,
    home_score      SMALLINT,
    result          SMALLINT,             -- home_score - away_score
    total           SMALLINT,             -- combined points actually scored
    overtime        BOOLEAN,
    location        TEXT,
    div_game        BOOLEAN,

    -- betting market
    spread_line     NUMERIC(5,1),         -- home team spread, e.g. -3.5
    total_line      NUMERIC(5,1),         -- over/under
    away_moneyline  INTEGER,
    home_moneyline  INTEGER,
    away_spread_odds INTEGER,
    home_spread_odds INTEGER,
    under_odds      INTEGER,
    over_odds       INTEGER,

    -- conditions
    roof            TEXT,
    surface         TEXT,
    temp            SMALLINT,
    wind            SMALLINT,
    stadium         TEXT,
    stadium_id      TEXT,

    -- people
    away_qb_id      TEXT,
    home_qb_id      TEXT,
    away_qb_name    TEXT,
    home_qb_name    TEXT,
    away_coach      TEXT,
    home_coach      TEXT,
    referee         TEXT,

    away_rest       SMALLINT,
    home_rest       SMALLINT,
    old_game_id     TEXT
);

CREATE INDEX IF NOT EXISTS idx_games_season      ON games (season);
CREATE INDEX IF NOT EXISTS idx_games_home_team   ON games (home_team);
CREATE INDEX IF NOT EXISTS idx_games_away_team   ON games (away_team);
CREATE INDEX IF NOT EXISTS idx_games_season_week ON games (season, week);

-- ---------------------------------------------------------------------------
-- plays: trimmed play-by-play (46 of the 372 upstream columns)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plays (
    game_id         TEXT     NOT NULL,
    play_id         INTEGER  NOT NULL,
    season          SMALLINT NOT NULL,
    week            SMALLINT,
    season_type     TEXT,
    game_date       DATE,

    -- teams
    home_team       TEXT,
    away_team       TEXT,
    posteam         TEXT,                 -- team with the ball (NULL on timeouts etc.)
    defteam         TEXT,

    -- situation
    qtr             SMALLINT,
    down            SMALLINT,             -- NULL on kickoffs, PATs, timeouts
    ydstogo         SMALLINT,
    yardline_100    SMALLINT,             -- yards from opponent's goal line
    goal_to_go      BOOLEAN,
    drive           SMALLINT,
    game_seconds_remaining  INTEGER,

    -- what happened
    play_type       TEXT,                 -- pass / run / punt / field_goal / ...
    play_desc       TEXT,                 -- upstream "desc" (reserved word in SQL)
    yards_gained    SMALLINT,
    shotgun         BOOLEAN,
    no_huddle       BOOLEAN,
    pass_play       BOOLEAN,              -- upstream "pass"
    rush_play       BOOLEAN,              -- upstream "rush"
    air_yards       SMALLINT,
    yards_after_catch SMALLINT,
    pass_length     TEXT,                 -- short / deep
    pass_location   TEXT,                 -- left / middle / right
    run_location    TEXT,
    run_gap         TEXT,                 -- end / tackle / guard

    -- efficiency metrics
    epa             NUMERIC(10,6),
    qb_epa          NUMERIC(10,6),
    cpoe            NUMERIC(10,6),
    success         BOOLEAN,
    wp              NUMERIC(10,6),        -- win probability before the play
    wpa             NUMERIC(10,6),

    -- score state
    posteam_score       SMALLINT,
    defteam_score       SMALLINT,
    score_differential  SMALLINT,

    -- outcomes
    first_down      BOOLEAN,
    touchdown       BOOLEAN,
    interception    BOOLEAN,
    fumble_lost     BOOLEAN,
    penalty         BOOLEAN,

    -- players involved
    passer_player_id    TEXT,
    passer_player_name  TEXT,
    rusher_player_id    TEXT,
    rusher_player_name  TEXT,
    receiver_player_id  TEXT,
    receiver_player_name TEXT,

    PRIMARY KEY (game_id, play_id)
);

CREATE INDEX IF NOT EXISTS idx_plays_game_id   ON plays (game_id);
CREATE INDEX IF NOT EXISTS idx_plays_season    ON plays (season);
CREATE INDEX IF NOT EXISTS idx_plays_posteam   ON plays (posteam);
-- the query shape this project will run constantly: one team, one season
CREATE INDEX IF NOT EXISTS idx_plays_posteam_season ON plays (posteam, season);
CREATE INDEX IF NOT EXISTS idx_plays_play_type ON plays (play_type);

-- ---------------------------------------------------------------------------
-- players: full-league snapshot keyed by gsis_id (verified unique, no nulls)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS players (
    gsis_id             TEXT PRIMARY KEY,
    display_name        TEXT,
    first_name          TEXT,
    last_name           TEXT,
    football_name       TEXT,
    birth_date          DATE,
    position            TEXT,
    position_group      TEXT,
    height              SMALLINT,         -- inches
    weight              SMALLINT,         -- pounds
    jersey_number       TEXT,             -- upstream is a string
    college_name        TEXT,
    college_conference  TEXT,
    rookie_season       SMALLINT,
    last_season         SMALLINT,
    years_of_experience SMALLINT,
    latest_team         TEXT,
    status              TEXT,
    draft_year          SMALLINT,
    draft_round         SMALLINT,
    draft_pick          SMALLINT,
    draft_team          TEXT,
    headshot            TEXT,
    -- cross-source id map, handy for joining to contracts/PFR/ESPN data
    esb_id              TEXT,
    pfr_id              TEXT,
    pff_id              TEXT,
    otc_id              TEXT,
    espn_id             TEXT,
    smart_id            TEXT
);

CREATE INDEX IF NOT EXISTS idx_players_latest_team ON players (latest_team);
CREATE INDEX IF NOT EXISTS idx_players_position    ON players (position);
CREATE INDEX IF NOT EXISTS idx_players_name        ON players (display_name);

-- ---------------------------------------------------------------------------
-- contracts: OverTheCap data. No natural key upstream — (player, year_signed)
-- is NOT unique (31,874 distinct pairs across 53,739 rows), so we use a
-- surrogate key. The nested season_history / contract_history columns are
-- List(Struct) upstream and are not loaded here.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contracts (
    contract_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player          TEXT,
    gsis_id         TEXT,                 -- nullable upstream (3,566 missing)
    otc_id          INTEGER,
    position        TEXT,
    team            TEXT,
    is_active       BOOLEAN,
    year_signed     SMALLINT,
    years           SMALLINT,
    value           NUMERIC(14,4),        -- total value, $M
    apy             NUMERIC(14,4),        -- average per year, $M
    guaranteed      NUMERIC(14,4),
    apy_cap_pct     NUMERIC(10,6),        -- APY as share of the cap
    inflated_value       NUMERIC(14,4),
    inflated_apy         NUMERIC(14,4),
    inflated_guaranteed  NUMERIC(14,4),
    draft_year      SMALLINT,
    draft_round     SMALLINT,
    draft_overall   SMALLINT,
    draft_team      TEXT,
    college         TEXT,
    date_of_birth   DATE,
    player_page     TEXT
);

CREATE INDEX IF NOT EXISTS idx_contracts_gsis_id ON contracts (gsis_id);
CREATE INDEX IF NOT EXISTS idx_contracts_team    ON contracts (team);
CREATE INDEX IF NOT EXISTS idx_contracts_player  ON contracts (player);
