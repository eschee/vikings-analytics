"""Why a game matters to a team: rule-based reason codes.

Each row in game_impacts gets one code explaining, in a word, the mechanism by
which this game touches this team's season. The rules are deterministic and
checked in a fixed order -- FIRST MATCH WINS -- so every row gets exactly one
code and the same inputs always produce the same answer.

The subject team is the fan's team. It is usually NOT playing in the game.

PRECEDENCE, and the reasoning behind each rung:

1. own_game
   The subject team is playing. This outranks everything else because it is the
   plainest possible answer to "why does this game matter to me", and because a
   team's own games dominate its list -- all nine of Minnesota's remaining
   games are "must win" for the playoff goal, far above any other game. It is
   checked first and nothing below can override it. The matchup itself still
   shows who the opponent is, so labelling it own_game rather than
   division_rival loses nothing a reader can see; it just stops the page
   saying "Division rival" about a game the team is in.

2. tiebreaker_effect
   Neither team in the game is in the subject's conference. Such a game cannot
   change the subject's record, nor any rival's record inside the conference.
   The only channel left is the NFL tiebreaker ladder: strength of victory and
   strength of schedule add up the records of every opponent a team played, and
   those opponents include the other conference. So an AFC result can nudge an
   NFC tiebreak. This is a real but tiny effect, and such rows almost always
   land in the "doesn't matter" tier -- the code explains the mechanism when
   they do not.

3. division_rival
   At least one team in the game shares the subject's division. Division games
   count twice over: they move a direct rival's record AND they feed the
   head-to-head and division-record rungs of the tiebreaker, which are the
   first two things consulted when the subject and that rival finish level.
   This outranks the codes below because being a division rival is the most
   specific relationship two teams can have.

4. top_seed_race
   Either the goal being measured IS the #1 seed, or both the subject and a
   participant are live contenders for it (each at or above
   TOP_SEED_CONTENDER_PCT). The #1 seed is a separate prize from simply making
   the field -- it is the only first-round bye -- so when that is what is at
   stake it deserves its own label.

5. wildcard_competitor
   A participant is in the subject's conference but a different division, and
   is genuinely in the race: its own playoff odds sit between IN_RACE_MIN_PCT
   and IN_RACE_MAX_PCT. Conference games move the standings the subject is
   measured against, but only matter if the other team is actually contending.
   A locked-in or eliminated team's games change little for anyone.

6. other
   Everything left: a same-conference team whose season is effectively decided,
   or any combination the rules above do not describe.

WHAT CHANGED. Earlier versions had no own_game code and classified a team's own
games by the OPPONENT's relationship, which produced "Must win / Other" for
Minnesota at the Jets -- technically correct under those rules and useless on a
page. own_game replaces that.
"""

from __future__ import annotations

from .config import (
    IN_RACE_MAX_PCT,
    REASON_OWN_GAME,
    IN_RACE_MIN_PCT,
    REASON_DIVISION_RIVAL,
    REASON_OTHER,
    REASON_TIEBREAKER_EFFECT,
    REASON_TOP_SEED_RACE,
    REASON_WILDCARD_COMPETITOR,
    TOP_SEED_CONTENDER_PCT,
)


def reason_code(
    subject: str,
    home: str,
    away: str,
    goal: str,
    conf: dict[str, str],
    division: dict[str, str],
    playoff_pct: dict[str, float],
    top_seed_pct: dict[str, float],
) -> str:
    """Classify why `subject` cares about `away` @ `home`. First match wins."""
    participants = [home, away]
    others = [t for t in participants if t != subject]
    subj_conf = conf[subject]
    subj_div = division[subject]

    # 1. We are playing. Nothing below can outrank that.
    if subject in participants:
        return REASON_OWN_GAME

    # 2. Nothing in this game is in our conference: only tiebreakers connect it.
    if all(conf.get(t) != subj_conf for t in participants):
        return REASON_TIEBREAKER_EFFECT

    # 3. A division rival is involved.
    if any(division.get(t) == subj_div for t in others):
        return REASON_DIVISION_RIVAL

    # 4. The #1 seed is what is being measured, or both sides are contenders.
    if goal == "top_seed":
        return REASON_TOP_SEED_RACE
    if top_seed_pct.get(subject, 0.0) >= TOP_SEED_CONTENDER_PCT and any(
        top_seed_pct.get(t, 0.0) >= TOP_SEED_CONTENDER_PCT
        and conf.get(t) == subj_conf
        for t in others
    ):
        return REASON_TOP_SEED_RACE

    # 5. A conference team that is genuinely still in the race.
    for t in others:
        if conf.get(t) != subj_conf:
            continue
        pct = playoff_pct.get(t)
        if pct is not None and IN_RACE_MIN_PCT <= pct <= IN_RACE_MAX_PCT:
            return REASON_WILDCARD_COMPETITOR

    # 6. Same conference, but the other team's season is effectively settled.
    return REASON_OTHER
