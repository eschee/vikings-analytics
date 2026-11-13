-- Store both arms of each impact, not just the gap between them.
--
-- game_impacts recorded impact_pts, the SIZE of the swing, which is all the
-- ranking needs. The website also shows the two sides of it -- "if they win
-- 84%, if they lose 60%" -- and those cannot be recovered from the swing
-- alone. They could be reconstructed from the unconditional odds and the win
-- probability via the law of total probability, but only approximately: the
-- stored win probability is the MODEL's, while the split actually used the
-- simulated frequency, and the two differ by Monte Carlo noise. Storing the
-- real numbers is simpler and exact.
--
-- ADD COLUMN IF NOT EXISTS is idempotent, which matters because apply_schema()
-- runs every migration on every load.
--
-- Runs saved before this migration keep NULL here; the website should treat a
-- NULL as "not available for this run" rather than as a zero.

ALTER TABLE game_impacts
    ADD COLUMN IF NOT EXISTS value_if_root_for_wins NUMERIC(8,3);

ALTER TABLE game_impacts
    ADD COLUMN IF NOT EXISTS value_if_root_for_loses NUMERIC(8,3);
