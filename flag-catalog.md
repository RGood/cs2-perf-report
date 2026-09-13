# Flag catalog: impact flags and how to detect them with demoparser2

Sign: + positive impact, − negative. ✓ = already implemented in the report. Detection uses demoparser2 events
(`player_death`, `player_hurt`, `weapon_fire`, `player_blind`, grenade detonations, bomb events, `weapon_reload`,
`player_footstep`) and tick props (`X/Y/Z`, `yaw/pitch`, `velocity`, `is_walking`, `ducking`, `is_scoped`, `spotted`,
`approximate_spotted_by`, `flash_duration`, `inventory`, `clip`, `balance`, `cash_spent_this_round`, `current_equip_value`,
`has_defuser`, `has_helmet`, `is_defusing`, `in_bomb_zone`, `is_bomb_planted`, `bomb_planted_site`, `last_place_name`).
"Engagement" = the 4 s before a death. "Contact" = first enemy within 25 m. "Visible" = server `spotted` flag.

## 1. Openings and duels

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Opening kill ✓ | + | First `player_death` of the round, attacker = me | |
| Lost CT opener ✓ / Lost T opener | − | First death of the round, victim = me, by side | |
| Opening death traded | + | First death = me; a teammate kills my killer within 5 s | Death still cost, but spacing was right |
| Untradeable opener | − | First death = me, nearest teammate > 15 m, not traded within 5 s | |
| Pre-aimed | + | At the tick an enemy first becomes visible within 35 m, my crosshair is within 5° of them | Angle from `yaw/pitch` vs bearing; ignore enemies behind me (> 60° off) |
| Crosshair off at first sight | − | Same transition, offset > 15° | |
| Pre-fired the angle | + | My first `weapon_fire` on a victim comes before or within 0.3 s of them becoming visible, and I hit them | |
| First bullet hit | + | In an engagement, my first `weapon_fire` tick has a matching `player_hurt` on an enemy | Per Leetify first-bullet accuracy |
| First bullet missed | − | Engagement's first shot has no hurt event, and I lost the duel | |
| Slow to damage | − | Time from enemy first visible to my first `player_hurt` on them > 700 ms, and I lost | Leetify "time to damage" |
| Won after being hit first | + | Victim's `player_hurt` on me precedes my first hurt on them, and I get the kill | |
| Died without firing ✓ | − | 0 shots in the engagement | |
| Long-distance spray missed ✓ | − | Continuous run ≥ 7 shots at cycle rate, ≥ 20 m, ≤ 20 dmg to killer | |
| Bursts missed at range ✓ | − | ≥ 6 shots as bursts/taps, ≥ 20 m, ≤ 20 dmg | |
| Shot while moving | − | `weapon_fire` ticks where `velocity` magnitude > ~35 u/s for rifles (> ~60 for SMGs), share of engagement shots | Counter-strafing; thresholds per weapon class |
| Counter-strafed engagement | + | ≥ 85% of engagement shots fired with velocity under the threshold | |
| Moving scoped shot | − | `weapon_fire` with `is_scoped` and velocity > 30 u/s on awp/ssg08 | |
| Wallbang kill | + | `player_death.penetrated > 0`, attacker = me | |
| Kill through smoke | + | `player_death.thrusmoke` true, attacker = me | |
| Died through smoke | − | Same flag, victim = me, killer not visible | Walked in front of a smoke you had not cleared |
| Kill off your own flash ✓ | + | Victim `flash_duration > 0`, my `player_blind` on them within 4 s | |
| Died flashed ✓ | − | My `flash_duration > 0` at death; attribute to teammate or enemy from `player_blind.attacker` | |
| Noscope kill | + | `player_death.noscope`, attacker = me | Minor |
| Headshot kill | + | `player_death.headshot`, attacker = me | Already a modifier |
| Died to a jumping player | − | `attackerinair` on my death, close range | Minor; a lost close fight |

## 2. Peeking and positioning

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Isolated before dying ✓ | − | Untraded, nearest teammate > 15 m, and I or they moved apart in the last 10 s | |
| Died anchoring ✓ | − | Untraded, alone, held position ≥ 10 s | |
| Anchor held with value ✓ | + | Anchor death with ≥ 8 s delay and damage ≥ 50 or a grenade after contact | |
| Re-peeked the same angle | − | I fire or take damage at position P, leave (> 3 m, unspotted), return within 8 s to within 2 m of P, and die | The classic overpeek |
| Wide swing alone | − | At death my velocity > 200 u/s, I was closing on the killer over the last 1 s, no teammate within 15 m | |
| Died in a crossfire | − | `approximate_spotted_by` shows ≥ 2 enemies seeing me at death from bearings > 45° apart | Multi-angle exposure |
| Shot in the back | − | Angle between my `yaw` and the bearing to my killer > 100° at death | Flank not covered or no rotation check |
| Unseen kill | + | At my kill, victim's `yaw` vs bearing to me > 90°, and I had no `player_footstep` in the prior 5 s | Silent approach paid off |
| Kill with cover | + | My kill while a teammate within 20 m also has the victim visible | Crossfire actually set |
| Info peek survived | + | I become visible near an enemy ≤ 30 m for < 0.5 s, they fire, I take no damage and retreat > 3 m | Approximate |
| Chased and died | − | After a kill I advance > 15 m toward remaining enemies within 5 s and die | |
| Traded by enemy ✓ | − | Died within 5 s of my kill, within 8 m of where I got it | |
| Repositioned after a kill ✓ | + | Second kill ≥ 8 m from the first in the same round | |
| Ran into contact | − | ≥ 3 `player_footstep` events by me while not visible with an unspotted enemy ≤ 20 m, then I lose the fight | Running gave the position away |
| Walked into an AWP line | − | Died to awp/ssg08 at ≥ 30 m within 2 s of first becoming visible to the killer | |
| Instant death | − | Died before 10 s of round time | |
| Early solo T contact ✓ | − | T death < 20 s, nearest teammate > 10 m, 0 damage | |
| Rotated off site early | − | CT: I move > 30 m from my starting area before any enemy is within 40 m of it; that site is then hit within 15 s | Panic rotate |
| Frozen on site | − | CT: bomb planted or ≥ 2 enemies on the other site; I stay > 40 m away for > 15 s while alive; round lost | Rotated too late |
| Solo rotation into a lost site | − | CT: ≥ 2 teammates already dead at site X; I enter X alone (nearest mate > 20 m) and die | |
| Caught the rotation | + | T lurk kill: > 30 s, nearest teammate > 40 m, victim moved > 20 m in the last 10 s | |
| Post-plant hold | + | T: after plant I survive ≥ 20 s and get a kill, or the bomb explodes | |

## 3. Trading and teamplay

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Trade kill ✓ | + | Killed the enemy who killed a teammate within 5 s | |
| Death traded ✓ | + | A teammate killed my killer within 5 s | |
| Missed trade | − | Teammate died within 15 m of me; their killer was visible ≥ 1.5 s afterwards; I fired nothing and did no damage | |
| Baited a teammate | − | Teammate dies within 10 m of me, I was unspotted, did not fire within 3 s, and moved away | Distinguish from Missed trade by the retreat |
| Kill while down a man | + | My kill when my team has fewer alive than theirs; it evens or flips the count | HLTV round-swing proxy |
| Flash assist ✓ | + | My `player_blind` on an enemy a teammate then kills within 4 s | |
| Flashed a teammate | − | `player_blind` attacker = me, victim = teammate, duration > 1 s | |
| Flashed myself | − | `player_blind` attacker = me, victim = me, duration > 0.5 s | |
| Team damage | − | `player_hurt` attacker = me, victim = teammate, any weapon | Grenade team damage the usual case |
| Weapon drop | + | In freeze time my `inventory` loses a rifle and a teammate's gains the same within 3 s | |
| Stopped the defuse | + | My kill on an enemy with `is_defusing` true | |
| Killed the planter | + | My kill on an enemy between `bomb_beginplant` and `bomb_planted` | |

## 4. Utility

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Died with usable utility ✓ | − | Held grenade with time, a target, and a safe throw window ≥ 1.5 s after contact | |
| Utility thrown too early ✓ | − | Smoke/molotov thrown with no enemy within 30 m and none visible, then missing during ≥ 4 s of contact | |
| Utility on a timer ✓ | − | Same grenade, same place, same second in ≥ 4 rounds | |
| Utility on a signal ✓ | + | Smoke/molotov with ≥ 2 enemies within 30 m, round won | |
| Utility damage ✓ | + | HE/molotov damage ≥ 30 in a round | |
| Flash blinded nobody | − | `flashbang_detonate` by me with no enemy `player_blind` | |
| Flash without a swing | − | My flash blinds an enemy but no teammate or I peek (become visible to them) within 3 s | Boosteria "unsupported flash" |
| Molotov forced a retreat | + | `inferno_startburn` by me with an enemy within 8 m of it; they move away > 5 m or take damage within 3 s | |
| Molotov on nothing | − | My molotov burn with no enemy within 12 m for its whole duration, thrown after contact | Distinct from early throw |
| Plant smoke | + | My smoke detonates within 10 m of the plant spot in the 10 s before `bomb_planted` | |
| Smoke for the retake | + | CT post-plant: my smoke within 12 m of the bomb, then a teammate or I enter the site within 8 s | |
| HE on a stack | + | My HE damages ≥ 2 enemies | |
| Wasted HE | − | My HE with 0 enemy damage, thrown after contact | |
| Full buy, zero impact ✓ | − | Full buy, 0 damage, no grenade thrown, died | |

## 5. Economy

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| SMG on a full-buy round | − | CT/T equip ≥ 3000 with MP9/MP7/MAC-10 as primary while team average ≥ 4000 | Currently a review-only stat; not in the report yet |
| Bought against a team save | − | `cash_spent_this_round` ≥ 3500 while team average equip < 2000 | |
| Saved with money | − | `balance` ≥ 4750 but equip < 3000 on a round the team full-bought | |
| No defuse kit | − | CT full buy (equip ≥ 3700) with `has_defuser` false at freeze end | Cheap fix |
| No helmet on rifle | − | Rifle in inventory, `has_helmet` false, opponents on rifles | |
| Killed a full buy on eco | + | Victim `current_equip_value` ≥ 3700 while mine < 1500 | HLTV 3.0 economy-adjusted kill |
| Lost a full buy to a pistol | − | My death: killer equip < 1500, mine ≥ 3700 | |
| Saved the rifle ✓ | + | Survived a lost round with equip ≥ 3000 | |
| Exit frag | + | Kill on a lost round after ≤ 1 teammate remains, that denies the enemy a saved weapon or wins money | Economy value, not round value |
| Picked up a rifle on eco | + | `item_pickup` of a rifle when my freeze-time equip < 1500 | |
| Alone on eco ✓ | − | Eco round, nearest teammate > 25 m at death | |

## 6. Bomb and objective

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Bomb died with me | − | `inventory` has C4 at death, before 30 s, > 30 m from either site, plant not started | |
| Bomb abandoned | − | `bomb_dropped` by me; no `bomb_pickup` within 15 s while I am alive and > 10 m away | |
| Plant under pressure | + | `bomb_planted` by me with an enemy alive within 25 m | |
| Planted without cover | − | `bomb_beginplant` by me with a visible enemy within 25 m, no teammate within 15 m, and I die during the plant | |
| Fast plant | + | `bomb_planted` before 35 s of round time | |
| Defused under fire | + | `bomb_defused` by me with ≥ 1 enemy alive | |
| Sneaky defuse | + | `bomb_defused` by me while an enemy alive within 25 m never had me visible during the defuse | Ninja defuse |
| Defuse fake worked | + | `bomb_begindefuse` then `is_defusing` drops without `bomb_defused`; an enemy dies to my team within 3 s | |
| Defuse started too late | − | `bomb_begindefuse` with bomb time remaining < defuse length (10 s, 5 with kit) | Uses `bomb_time`, `has_defuser` |
| Retake kill ✓ | + | CT kill after plant, round won | |
| Solo retake | − | CT post-plant: I enter within 20 m of the bomb with no teammate within 15 m and die | |
| Died while planting | − | My death between my `bomb_beginplant` and `bomb_planted` | |
| Clutch won ✓ | + | Last alive, round won | |
| Clutch lost without damage | − | Last alive, round lost, 0 damage after the last teammate died | |

## 7. Reloads, weapons, sound

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Died reloading | − | `weapon_reload` by me within 2.5 s before death with no `weapon_fire` after it | |
| Reloaded in the open | − | `weapon_reload` while visible with an enemy alive within 25 m, then died within 3 s | |
| Reloaded with a near-full clip in contact | − | `weapon_reload` with `clip` ≥ 80% of max while an enemy is within 25 m | Habit reload |
| Died with an empty clip | − | `clip == 0` at death and a `weapon_fire` in the last 2 s | Sprayed dry |
| Switched to pistol and won | + | Kill with a pistol within 3 s of my primary's clip hitting 0 | |
| Crouch-peeked into a rifle | − | `ducking` true at death, killer ≥ 15 m, I was visible ≥ 1 s | Crouching in the open |
| Jumped into a fight | − | `is_airborne` at death or at my last shots, killer within 15 m | |

## Source basis

Leetify's glossary defines KAST, opening duels, trades, time to damage, utility damage and utility score, clutch and
multi-kill volatility. HLTV Rating 3.0 adds economy-adjusted kills, survival in difficult situations, multi-kill
weighting and round swing (how much a kill moved the win probability given alive counts, bomb and economy). The
coaching lists contribute re-peeking, multi-angle exposure, wide swings without support, chasing, isolated peeks,
panic and frozen rotations, unsupported flashes, mistimed molotovs, early utility spending, reload timing, and giving
away position by sound.
