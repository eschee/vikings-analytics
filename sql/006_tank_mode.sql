-- Tank mode: the draft as something to root for.
--
-- 1. team_odds gains three per-team draft numbers: the average projected pick,
--    the chance of the #1 overall pick, and the chance of a top-5 pick. They
--    are NULL for runs saved before this migration -- the website treats a
--    NULL as "not available yet" rather than as zero.
-- 2. game_impacts accepts a fifth goal, 'top_pick' (chance of the #1 pick).
--    'draft' (average pick) was always allowed.
-- 3. game_impacts accepts a new reason, 'draft_rival': a team close to you in
--    the projected draft order. (004 carries the same list; see there.)
--
-- Everything is idempotent, because apply_schema() runs every file on every
-- load: ADD COLUMN IF NOT EXISTS, and DROP CONSTRAINT IF EXISTS before each
-- ADD CONSTRAINT. Both constraint changes only WIDEN an allowlist, so no
-- stored row can violate them.
--
-- No grant changes. web_reader's SELECT and refresh_writer's INSERT are
-- table-level grants, which cover columns added later.

ALTER TABLE team_odds
    ADD COLUMN IF NOT EXISTS avg_draft_pick NUMERIC(5,3);
ALTER TABLE team_odds
    ADD COLUMN IF NOT EXISTS top_pick_pct NUMERIC(6,3);
ALTER TABLE team_odds
    ADD COLUMN IF NOT EXISTS top5_pick_pct NUMERIC(6,3);

ALTER TABLE game_impacts
    DROP CONSTRAINT IF EXISTS game_impacts_goal_known;
ALTER TABLE game_impacts
    ADD CONSTRAINT game_impacts_goal_known CHECK (
        goal IN ('playoffs', 'division', 'top_seed', 'draft', 'top_pick'));

ALTER TABLE game_impacts
    DROP CONSTRAINT IF EXISTS game_impacts_reason_known;
ALTER TABLE game_impacts
    ADD CONSTRAINT game_impacts_reason_known CHECK (
        reason_code IN ('own_game', 'division_rival', 'wildcard_competitor',
                        'top_seed_race', 'tiebreaker_effect', 'other',
                        'draft_rival'));
