-- Add 'own_game' to the game_impacts reason allowlist.
--
-- 003 created the CHECK constraint with five codes. CREATE TABLE IF NOT EXISTS
-- will not revise an existing table, so extending the allowlist needs its own
-- migration rather than an edit to 003.
--
-- DROP IF EXISTS followed by ADD is idempotent as a pair, which matters
-- because apply_schema() runs every file on every load. ADD CONSTRAINT alone
-- would fail the second time.
--
-- Widening an allowlist is safe for stored rows: every existing reason_code is
-- still permitted, so nothing already saved can violate the new constraint.

ALTER TABLE game_impacts
    DROP CONSTRAINT IF EXISTS game_impacts_reason_known;

ALTER TABLE game_impacts
    ADD CONSTRAINT game_impacts_reason_known CHECK (
        reason_code IN ('own_game', 'division_rival', 'wildcard_competitor',
                        'top_seed_race', 'tiebreaker_effect', 'other'));
