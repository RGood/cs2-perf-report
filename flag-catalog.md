# Flag catalog: impact flags and how to detect them with demoparser2

Sign: + positive impact, − negative. ✓ = implemented in the report (each flag is one file in `flags/`, named after its id). Detection uses demoparser2 events
(`player_death`, `player_hurt`, `weapon_fire`, `player_blind`, grenade detonations, bomb events, `weapon_reload`,
`player_footstep`) and tick props (`X/Y/Z`, `yaw/pitch`, `velocity`, `is_walking`, `ducking`, `is_scoped`, `spotted`,
`approximate_spotted_by`, `flash_duration`, `inventory`, `clip`, `balance`, `cash_spent_this_round`, `current_equip_value`,
`has_defuser`, `has_helmet`, `is_defusing`, `in_bomb_zone`, `is_bomb_planted`, `bomb_planted_site`, `last_place_name`).
"Engagement" = the 4 s before a death. "Contact" = first enemy within 25 m. "Visible" = server `spotted` flag.

## Implemented since this catalog was written

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Late support ✓ | − | Teammate T fought enemy E for ≥ 1.0 s and died; I was alive, not blind, not in my own fight, within 30 m of E; E had me in view ≥ 0.5 s before the death (definite) or I was within 20 m (could have peeked); I did no damage during the fight and engaged E within 4 s after T died | Allows 0.4 s reaction + 0.6 s to swing (`REACTION_S`, `PEEK_S`) |
| Didn't join the fight ✓ | − | A teammate exchanged damage with an enemy for ≥ 1.5 s (≥ 3 s when the only evidence is sound); I was alive, took and dealt no damage, was not flashed, and no other enemy had me in view; I knew where the fight was (I had the enemy in view during or within 10 s before it, the enemy had me in view, the teammate within 12 m had them in view, or shots in that fight were fired within 40 m of me); I never engaged that enemy during the fight or 4 s after and did not close 8 m toward it | Distance alone never triggers it; awareness evidence does. Late support is the stricter case (teammate died, I engaged after) |
| Supported the fight ✓ | + | Same fight window, but I damaged E before T died | Mirror of Late support |
| Died in a crossfire ✓ | − | `approximate_spotted_by` on me lists ≥ 2 enemies in the last 2 s, bearings ≥ 45° apart | |
| Swung into a held angle ✓ | − | At first mutual visibility I was moving (> 120 u/s from positions) and the killer was stationary (< 30) with yaw within 20° of me, ≥ 8 m | Do not use the `velocity` prop: it reports 2000; derive speed from positions |
| Held the angle ✓ | + | The reverse: victim moving, me stationary and aimed, and I got the kill | |
| Seen first, fought anyway ✓ | − | Killer had me in view ≥ 1.5 s before I had them, and I fired | |
| Fought at their range ✓ | − | I moved into view (> 100 u/s) with SMG/pistol vs rifle at ≥ 20 m, or rifle vs AWP at ≥ 35 m, and died | |
| Held an empty site ✓ | − | CT: ≥ 3 enemies spotted by the team ≥ 40 m from me for ≥ 6 s, none within 30 m, I closed < 10 m in 10 s, 0 damage, round lost | Rare by design |
| Rotated on info ✓ | + | CT: ≥ 3 spotted ≥ 40 m away and I closed ≥ 20 m within 8 s | |
| Absent from the hit ✓ | − | T: ≥ 3 teammates within 25 m of each other, two die within 10 s, I am ≥ 40 m away with 0 damage and no kill in the next 15 s | |

Not built, on purpose: any single "low-value position" flag. Position value needs cover and line-of-sight geometry the demo does not carry, and quiet holds are often correct. The measurable pieces above cover the cases that can be backed with data.

## 1. Openings and duels

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Opening kill (retired: an outcome, not a decision) | + | First `player_death` of the round, attacker = me | |
| Lost CT opener / Lost T opener (retired: an outcome, not a decision) | − | First death of the round, victim = me, by side | |
| Opening death traded ✓ | + | First death = me; a teammate kills my killer within 5 s | Death still cost, but spacing was right |
| Untradeable opener ✓ | − | First death = me, nearest teammate > 15 m, not traded within 5 s | |
| Pre-aimed ✓ | + | At the tick an enemy first becomes visible within 35 m, my crosshair is within 5° of them | Angle from `yaw/pitch` vs bearing; ignore enemies behind me (> 60° off) |
| Crosshair off at first sight ✓ | − | Same transition, offset > 15° | |
| Pre-fired the angle ✓ | + | My first `weapon_fire` on a victim comes before or within 0.3 s of them becoming visible, and I hit them | |
| First bullet hit ✓ | + | In an engagement, my first `weapon_fire` tick has a matching `player_hurt` on an enemy | Per Leetify first-bullet accuracy |
| First bullet missed ✓ | − | Engagement's first shot has no hurt event, and I lost the duel | |
| Slow to damage ✓ | − | Time from enemy first visible to my first `player_hurt` on them > 700 ms, and I lost | Leetify "time to damage" |
| Won after being hit first (retired: an outcome, not a decision) | + | Victim's `player_hurt` on me precedes my first hurt on them, and I get the kill | |
| Died without firing | − | 0 shots in the engagement | Not a flag: the engagement text on death cards states the shot count instead |
| Long-distance spray missed ✓ | − | Continuous run ≥ 7 shots at cycle rate, ≥ 20 m, ≤ 20 dmg to killer | |
| Bursts missed at range ✓ | − | ≥ 6 shots as bursts/taps, ≥ 20 m, ≤ 20 dmg | |
| Shot while moving ✓ | − | From the `fire_bullets` event (the game's own `inaccuracy` + `spread` per bullet): a shot counts when I was moving (> 60 u/s from positions), the cone at the aimed enemy's distance was wider than a 0.3 m radius, and it was ≥ 2× that weapon's standing cone at the same point of a spray in this demo; more than half of the engagement shots | Running with a Glock or SMG up close stays tight and is not counted |
| Counter-strafed engagement ✓ | + | ≥ 85% of engagement shots fired with velocity under the threshold | |
| Moving scoped shot ✓ | − | `weapon_fire` with `is_scoped` and velocity > 30 u/s on awp/ssg08 | |
| Wallbang kill (retired: an outcome, not a decision) | + | `player_death.penetrated > 0`, attacker = me | |
| Kill through smoke (retired: an outcome, not a decision) | + | `player_death.thrusmoke` true, attacker = me | |
| Died through smoke ✓ | − | Same flag, victim = me, killer not visible | Walked in front of a smoke you had not cleared |
| Kill off your own flash → Swung your own flash ✓ | + | Victim `flash_duration > 0`, my `player_blind` on them within 4 s | |
| Died flashed ✓ | − | My `flash_duration > 0` at death; attribute to teammate or enemy from `player_blind.attacker` | |
| Noscope kill (retired: an outcome, not a decision) | + | `player_death.noscope`, attacker = me | Minor |
| Headshot kill | + | `player_death.headshot`, attacker = me | Not a flag: a +3 modifier on kill flags |
| Died to a jumping player (retired: an outcome, not a decision) | − | `attackerinair` on my death, close range | Minor; a lost close fight |

## 2. Peeking and positioning

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Isolated before dying ✓ | − | Untraded, nearest teammate > 15 m, and I or they moved apart in the last 10 s | |
| Died anchoring ✓ | − | Untraded, alone, held position ≥ 10 s | |
| Anchor held with value ✓ | + | Anchor death with ≥ 8 s delay and damage ≥ 50 or a grenade after contact | |
| Re-peeked the same angle ✓ | − | I fire or take damage at position P, leave (> 3 m, unspotted), return within 8 s to within 2 m of P, and die | The classic overpeek |
| Wide swing alone ✓ | − | At death my velocity > 200 u/s, I was closing on the killer over the last 1 s, no teammate within 15 m | |
| Died in a crossfire ✓ | − | `approximate_spotted_by` shows ≥ 2 enemies seeing me at death from bearings > 45° apart | Multi-angle exposure |
| Shot in the back ✓ | − | Angle between my `yaw` and the bearing to my killer > 100° at death | Flank not covered or no rotation check |
| Unseen kill → Attacked from off their view ✓ | + | At my kill, victim's `yaw` vs bearing to me > 90°, and I had no `player_footstep` in the prior 5 s | Silent approach paid off |
| Kill with cover → Fought with cover ✓ | + | My kill while a teammate within 20 m also has the victim visible | Crossfire actually set |
| Info peek survived ✓ | + | I become visible near an enemy ≤ 30 m for < 0.5 s, they fire, I take no damage and retreat > 3 m | Approximate |
| Chased and died ✓ | − | After a kill I advance > 15 m toward remaining enemies within 5 s and die | |
| Traded by enemy ✓ | − | Died within 5 s of my kill, within 8 m of where I got it | |
| Repositioned after a kill ✓ | + | Second kill ≥ 8 m from the first in the same round | |
| Ran into contact ✓ | − | Running (> 200 u/s from positions; the demo has no usable footsteps) while unspotted with an unseen enemy ≤ 20 m (no sighting either way in the last 8 s), then I lose the fight. Exempt: a rush (≥ 2 teammates running within 25 m of me at some point in the prior 3 s) or an execute (≥ 2 team grenades within 30 m in the last 6 s) | Running gave the position away |
| Walked into an AWP line ✓ | − | Died to awp/ssg08 at ≥ 30 m within 2 s of first becoming visible to the killer | |
| Instant death (retired: an outcome, not a decision) | − | Died before 10 s of round time | |
| Early solo T contact ✓ | − | T death < 20 s, nearest teammate > 10 m, 0 damage | |
| Rotated off site early ✓ | − | CT: I move > 30 m from my starting area before any enemy is within 40 m of it; that site is then hit within 15 s | Panic rotate |
| Frozen on site ✓ | − | CT: bomb planted or ≥ 2 enemies on the other site; I stay > 40 m away for > 15 s while alive; round lost | Rotated too late |
| Solo rotation into a lost site ✓ | − | CT: ≥ 2 teammates already dead at site X; I enter X alone (nearest mate > 20 m) and die | |
| Caught the rotation (retired: an outcome, not a decision) | + | T lurk kill: > 30 s, nearest teammate > 40 m, victim moved > 20 m in the last 10 s | |
| Post-plant hold ✓ | + | T: after plant I survive ≥ 20 s and get a kill, or the bomb explodes | |

## 3. Trading and teamplay

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Trade kill ✓ | + | Killed the enemy who killed a teammate within 5 s | |
| Death traded ✓ | + | A teammate killed my killer within 5 s | |
| Missed trade ✓ | − | Teammate died within 15 m of me; their killer was visible ≥ 1.5 s afterwards; I fired nothing and did no damage | |
| Baited a teammate ✓ | − | Teammate dies within 10 m of me, I was unspotted, did not fire within 3 s, and moved away | Distinguish from Missed trade by the retreat |
| Kill while down a man (retired: an outcome, not a decision) | + | My kill when my team has fewer alive than theirs; it evens or flips the count | HLTV round-swing proxy |
| Flash assist → Flash blinded an enemy in a fight ✓ | + | My `player_blind` on an enemy a teammate then kills within 4 s | |
| Flashed a teammate ✓ | − | `player_blind` attacker = me, victim = teammate, duration > 1 s | |
| Flashed myself ✓ | − | `player_blind` attacker = me, victim = me, duration > 0.5 s | |
| Team damage ✓ | − | `player_hurt` attacker = me, victim = teammate, any weapon | Bullets: Team damage. Grenades: Utility hurt a teammate |
| Weapon drop ✓ | + | In freeze time my `inventory` loses a rifle and a teammate's gains the same within 3 s | |
| Stopped the defuse → Watched the bomb post-plant ✓ | + | My kill on an enemy with `is_defusing` true | |
| Killed the planter → Held the plant spot ✓ | + | My kill on an enemy between `bomb_beginplant` and `bomb_planted` | |

## 4. Utility

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Died with usable utility ✓ | − | Held grenade with time, a target, and a safe throw window ≥ 1.5 s after contact | |
| Utility thrown too early ✓ | − | Smoke/molotov thrown with no enemy within 30 m and none visible, then missing during ≥ 4 s of contact | |
| Utility on a timer ✓ | − | Same grenade, same place, same second in ≥ 4 rounds | |
| Utility on a signal ✓ | + | Smoke/molotov with ≥ 2 enemies within 30 m, round won | |
| Utility damage (retired: an outcome, not a decision) | + | HE/molotov damage ≥ 30 in a round | |
| Flash blinded nobody ✓ | − | `flashbang_detonate` by me with no enemy `player_blind` | |
| Flash without a swing ✓ | − | My flash blinds an enemy but no teammate or I peek (become visible to them) within 3 s | Boosteria "unsupported flash" |
| Molotov forced a retreat (retired: an outcome, not a decision) | + | `inferno_startburn` by me with an enemy within 8 m of it; they move away > 5 m or take damage within 3 s | |
| Molotov on nothing ✓ | − | My molotov burn with no enemy within 12 m for its whole duration, thrown after contact | Distinct from early throw |
| Plant smoke ✓ | + | My smoke detonates within 10 m of the plant spot in the 10 s before `bomb_planted` | |
| Smoke for the retake ✓ | + | CT post-plant: my smoke within 12 m of the bomb, then a teammate or I enter the site within 8 s | |
| HE on a stack (retired: an outcome, not a decision) | + | My HE damages ≥ 2 enemies | |
| Wasted HE ✓ | − | My HE with 0 enemy damage, thrown after contact | |
| Full buy, zero impact (retired: an outcome, not a decision) | − | Full buy, 0 damage, no grenade thrown, died | |

## 5. Economy

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| SMG on a full-buy round ✓ | − | CT/T equip ≥ 3000 with MP9/MP7/MAC-10 as primary while team average ≥ 4000 | Currently a review-only stat; not in the report yet |
| Bought against a team save ✓ | − | `cash_spent_this_round` ≥ 3500 while team average equip < 2000 | |
| Saved with money ✓ | − | `balance` ≥ 4750 but equip < 3000 on a round the team full-bought | |
| No defuse kit ✓ | − | CT full buy (equip ≥ 3700) with `has_defuser` false at freeze end | Cheap fix |
| No helmet on rifle ✓ | − | Rifle in inventory, `has_helmet` false, opponents on rifles | |
| Killed a full buy on eco (retired: an outcome, not a decision) | + | Victim `current_equip_value` ≥ 3700 while mine < 1500 | HLTV 3.0 economy-adjusted kill |
| Lost a full buy to a pistol (retired: an outcome, not a decision) | − | My death: killer equip < 1500, mine ≥ 3700 | |
| Saved the rifle ✓ | + | Survived a lost round with equip ≥ 3000 | |
| Exit frag (retired: an outcome, not a decision) | + | Kill on a lost round after ≤ 1 teammate remains, that denies the enemy a saved weapon or wins money | Economy value, not round value |
| Picked up a rifle on eco ✓ | + | `item_pickup` of a rifle when my freeze-time equip < 1500 | |
| Alone on eco ✓ | − | Eco round, nearest teammate > 25 m at death | |

## 6. Bomb and objective

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Bomb died with me ✓ | − | `inventory` has C4 at death, before 30 s, > 30 m from either site, plant not started | |
| Bomb abandoned ✓ | − | `bomb_dropped` by me; no `bomb_pickup` within 15 s while I am alive and > 10 m away | |
| Plant under pressure ✓ | + | `bomb_planted` by me with an enemy alive within 25 m | |
| Planted without cover ✓ | − | `bomb_beginplant` by me with a visible enemy within 25 m, no teammate within 15 m, and I die during the plant | |
| Fast plant (retired: an outcome, not a decision) | + | `bomb_planted` before 35 s of round time | |
| Defused under fire → Committed to the defuse ✓ | + | `bomb_defused` by me with ≥ 1 enemy alive | |
| Sneaky defuse → Committed to the defuse (merged) ✓ | + | `bomb_defused` by me while an enemy alive within 25 m never had me visible during the defuse | Ninja defuse |
| Defuse fake worked → Defuse fake ✓ | + | `bomb_begindefuse` then `is_defusing` drops without `bomb_defused`; an enemy dies to my team within 3 s | |
| Defuse started too late ✓ | − | `bomb_begindefuse` with bomb time remaining < defuse length (10 s, 5 with kit) | Uses `bomb_time`, `has_defuser` |
| Retake kill (retired: an outcome, not a decision) | + | CT kill after plant, round won | |
| Solo retake ✓ | − | CT post-plant: I enter within 20 m of the bomb with no teammate within 15 m and die | |
| Died while planting (retired: an outcome, not a decision) | − | My death between my `bomb_beginplant` and `bomb_planted` | |
| Clutch won (retired: an outcome, not a decision) | + | Last alive, round won | |
| Clutch lost without damage ✓ | − | Last alive, round lost, 0 damage after the last teammate died | |

## 7. Reloads, weapons, sound

| Flag | Sign | Detection | Notes |
|---|---|---|---|
| Died reloading ✓ | − | `weapon_reload` by me within 2.5 s before death with no `weapon_fire` after it | |
| Reloaded in the open ✓ | − | `weapon_reload` while visible with an enemy alive within 25 m, then died within 3 s | |
| Reloaded with a near-full clip in contact ✓ | − | `weapon_reload` with `clip` ≥ 80% of max while an enemy is within 25 m | Habit reload |
| Died with an empty clip ✓ | − | `active_weapon_ammo == 0` at the last tick alive (one tick before the death; at the death tick the weapon is already gone) and a `weapon_fire` in the last 2 s | Sprayed dry |
| Switched to pistol and won → Switched to pistol when dry ✓ | + | Kill with a pistol within 3 s of my primary's clip hitting 0 | |
| Crouch-peeked into a rifle ✓ | − | `ducking` true at death, killer ≥ 15 m, I was visible ≥ 1 s | Crouching in the open |
| Jumped into a fight ✓ | − | `is_airborne` at the last tick alive, killer within 15 m. Never read at the death tick: the demo marks about half of all dead players airborne for that one tick | A drop off a ledge counts too |

## Source basis

Leetify's glossary defines KAST, opening duels, trades, time to damage, utility damage and utility score, clutch and
multi-kill volatility. HLTV Rating 3.0 adds economy-adjusted kills, survival in difficult situations, multi-kill
weighting and round swing (how much a kill moved the win probability given alive counts, bomb and economy). The
coaching lists contribute re-peeking, multi-angle exposure, wide swings without support, chasing, isolated peeks,
panic and frozen rotations, unsupported flashes, mistimed molotovs, early utility spending, reload timing, and giving
away position by sound.
