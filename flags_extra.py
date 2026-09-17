"""Additional flags from the flag catalog: openers and duels, peeks and positioning, teamplay, utility, economy, bomb, reloads and stance.

Every detector reads the same parsed demo dict D as mistake_report / impact_report and returns the same flag dicts.
negatives(D, me) feeds the mistake side, positives(D, me) the play side. Nothing here estimates: a flag fires only on
events and tick properties the demo records; where the catalog asked for something the demo lacks (footstep-based
silence, the bogus velocity prop) the rule text says what is measured instead.
"""
import math, collections as C
import numpy as np, pandas as pd

TICK = 64
M = 0.0254                      # units -> metres
RIFLES = ('ak47', 'm4a1', 'm4a4', 'famas', 'galil', 'aug', 'sg556', 'sg553')
SNIPERS = ('awp', 'ssg08', 'scar20', 'g3sg1')
SMGS = ('mp9', 'mp7', 'mac10', 'mp5', 'ump45', 'p90', 'bizon')
PISTOLS = ('glock', 'usp', 'p2000', 'p250', 'fiveseven', 'tec9', 'cz75', 'deagle', 'revolver', 'elite', 'hkp2000')
SHOTGUNS = ('nova', 'xm1014', 'mag7', 'sawedoff')
ONE_SHOT_HELMET = ('ak47', 'sg556', 'sg553', 'awp', 'ssg08', 'scar20', 'g3sg1', 'deagle', 'revolver')   # kill a helmeted head in one shot at any range; the AUG only up to mid range, so it counts as helmet-relevant


def best_gun(inv):
    """The strongest gun in an inventory list by class; None if only a knife or grenades."""
    rank = {'sniper': 5, 'rifle': 4, 'smg': 3, 'shotgun': 2, 'pistol': 1}
    best = None
    for w in inv:
        cls = wclass(w)
        if cls in rank and (best is None or rank[cls] > rank[best[1]]): best = (w, cls)
    return best
CLIP = {'ak47': 30, 'm4a1': 30, 'm4a4': 30, 'm4a1_silencer': 20, 'm4a1s': 20, 'usps': 12, 'cz75auto': 12, 'famas': 25, 'galilar': 35, 'aug': 30, 'sg556': 30, 'awp': 10, 'ssg08': 10,
        'scar20': 20, 'g3sg1': 20, 'mp9': 30, 'mp7': 30, 'mac10': 30, 'mp5sd': 30, 'ump45': 25, 'p90': 50, 'bizon': 64, 'glock': 20, 'usp_silencer': 12,
        'hkp2000': 13, 'p250': 13, 'fiveseven': 20, 'tec9': 18, 'cz75a': 12, 'deagle': 7, 'revolver': 8, 'elite': 30, 'nova': 8, 'xm1014': 7, 'mag7': 5, 'sawedoff': 7, 'm249': 100, 'negev': 150}

RULES_NEG = {
    'opener_untradeable': ("Untradeable opener", "You were the round's first death with no teammate within 15 m, and nobody traded you within 5 s. The opening duel was taken from a spot where losing it cost a full player.", "Take the first fight of the round inside trade range, or take it with utility so a loss still gives information."),
    'lost_opener_t': ("Lost T opener", "First death of the round on the T side. The attack starts a man down before any map control is taken.", "Open with utility and a teammate on your shoulder, or let a teammate with a better angle take the first duel."),
    'crosshair_off': ("Crosshair off at first sight", "When an enemy within 35 m first came into your view, your crosshair was more than 15° away from them, and that fight ended in a kill or death.", "Pre-aim the exact spot where the enemy will appear before you swing; moving the crosshair after you see them is the slowest way to start a duel."),
    'first_bullet_missed': ("First bullet missed", "Your first shot in the engagement was aimed at a visible enemy, hit nothing, and you lost the duel. The first bullet is the one fired with the most accuracy and the most surprise.", "Slow the first shot down: counter-strafe to a full stop and place it, then let the spray or burst follow."),
    'slow_to_damage': ("Slow to damage", "More than 0.7 s passed between an enemy becoming yours to shoot and your first damage on them, and you died to them. The clock starts when they came into your view, or later if they were still fighting a teammate at that moment or you were in a reload you needed. A reload started with 40% or more of the clip left does not excuse the delay; it is the cause of it.", "Decide before the peek. If the crosshair is placed, the first shot goes out on sight."),
    'shot_moving': ("Shot while moving", "More than half of your engagement shots were fired while you were moving faster than a rifle stays accurate (from your positions, not the demo's velocity field), and you died.", "Counter-strafe: tap the opposite key to stop dead, shoot, then move again. Practice it until it is not a decision."),
    'moving_scoped': ("Moving scoped shot", "You fired a scoped sniper shot while moving. A moving scoped shot is almost random.", "Stop fully before the shot, or unscope and reposition."),
    'died_through_smoke': ("Died through smoke", "You were killed by a shot through a smoke. Standing where a smoke can be sprayed is a free kill for the enemy.", "Never stand in the line a smoke covers unless you are the one shooting it. Cross it, or hold off it."),
    'died_to_jumper': ("Died to a jumping player", "Your killer was airborne when they killed you at close range: a jump peek you did not punish.", "Hold the crosshair where the jump lands, not where it starts, and shoot as they land."),
    'repeek': ("Re-peeked the same angle", "You fired or took damage at a spot, left it, and came back to the same spot within 8 s, then died there. The enemy was waiting for exactly that.", "After showing yourself, change the angle or the timing. Same angle twice is the enemy's easiest kill."),
    'wide_swing_alone': ("Wide swing alone", "You died at full speed, closing on your killer over the last second, with no teammate within 15 m to trade.", "Wide swings work with a trade partner or a flash. Alone, shoulder-peek for information instead."),
    'shot_in_back': ("Shot in the back", "At your death you were looking more than 100° away from your killer. The flank was not covered and nobody was watching it.", "Clear behind you before you commit forward, and ask a teammate to watch the flank you cannot."),
    'chased_and_died': ("Chased and died", "After a kill you pushed more than 15 m toward the remaining enemies within 5 s and died.", "After a kill, reset. The enemy knows where you are; let them come to you or re-peek with a teammate."),
    'ran_into_contact': ("Ran into contact", "You were running (over 200 u/s) toward an enemy within 20 m whom nobody on your team had seen yet and who had not seen you in the last 8 s, and you lost the fight that followed. Running makes noise the enemy hears before you see them. A sighting in the last 8 s still counts as seen even if line of sight broke since; an older one does not.", "Walk the last 20 m into any position an enemy could hold. Sound is information you give away."),
    'awp_line': ("Walked into an AWP line", "You died to a sniper from 30 m or more within 2 s of first becoming visible to them.", "Know the AWP lines on every map and cross them behind a smoke or after the shot."),
    'instant_death': ("Instant death", "You died within the first 10 s of the round.", "Nothing is gained in the first 10 s that is worth a player. Take the first fight with utility or a teammate."),
    'rotated_off_early': ("Rotated off site early", "As CT you moved more than 30 m from your starting spot before any enemy was within 40 m of it, and enemies then arrived where you had been within 15 s.", "Rotate on information, not on a hunch. If the site is quiet, it still needs someone on it."),
    'frozen_on_site': ("Frozen on site", "As CT, the bomb was planted (or two or more enemies were spotted) at the other site, and you stayed more than 40 m away for more than 15 s while alive. The round was lost.", "Once the hit is confirmed elsewhere, rotate. A late retake with one more player is better than a full-health player on an empty site."),
    'solo_rotation_lost': ("Solo rotation into a lost site", "As CT, two or more teammates had already died at a site, and you entered it alone with no teammate within 20 m and died.", "Wait for the other rotator. Two players retaking together beats two players retaking one after the other."),
    'missed_trade': ("Missed trade", "A teammate died within 15 m of you and their killer stayed in your view for 1.5 s or more afterwards. You fired nothing and did no damage in the next 5 s.", "When a teammate dies next to you, the killer is exposed for a moment. Swing them at once; that moment closes fast."),
    'baited': ("Baited a teammate", "A teammate died within 10 m of you while you were unspotted, you did not fire within 3 s, and you moved away from them.", "If you are close enough to be a trade partner, be one. Moving away after their death is the definition of a bait."),
    'flashed_myself': ("Flashed myself", "Your own flashbang blinded you for a second or more.", "Turn away or throw it further ahead; a self-flash gives the enemy a free peek."),
    'team_damage': ("Team damage", "You did damage to a teammate with a gun.", "Check the crossfire lines before you fire, and do not shoot past a teammate."),
    'flash_blinded_nobody': ("Flash blinded nobody", "Your flashbang popped with an enemy within 25 m of it and blinded nobody on their team for even half a second.", "Pop flashes go over cover and behind the enemy's line of sight, not in front of them where they can turn away."),
    'flash_no_swing': ("Flash without a swing", "Your flash blinded an enemy for a second or more, but neither you nor a teammate came into their view within 3 s and nobody damaged them.", "A flash is a timer. Somebody must swing while it runs, or it only tells the enemy where you are."),
    'molotov_on_nothing': ("Molotov on nothing", "Your molotov burned for its whole duration with no enemy within 12 m of it, thrown after your team had already seen the enemy.", "After contact, throw the molotov where the enemy is or must pass, not where they might have been."),
    'wasted_he': ("Wasted HE", "Your HE grenade did no damage, thrown after your team had already spotted the enemy within 30 m.", "After contact an HE goes on the stack or the choke the enemy is holding, not into an empty area."),
    'smg_full_buy': ("SMG on a full-buy round", "You bought an SMG as your primary with 3000 or more of equipment while your team averaged a full buy. Against rifles at range that is a losing duel every time.", "On a full buy, buy the rifle. Save the SMG for anti-eco and force rounds."),
    'bought_vs_save': ("Bought against a team save", "You spent 3500 or more while your team averaged under 2000 of equipment. One rifle among pistols does not win the round; it loses a rifle.", "Buy with the team. If the team saves, save."),
    'saved_with_money': ("Saved with money", "You had 4750 or more but under 3000 of equipment on a round where your team full-bought.", "When the team buys, buy. Money in the bank does not shoot."),
    'no_kit': ("No defuse kit", "A CT full buy without a defuse kit. The kit halves the defuse time and wins post-plants.", "Add the kit to every CT full buy. It is the cheapest round-winning item in the game."),
    'no_helmet': ("No helmet when it mattered", "You had no helmet, with the money to buy one, while three or more enemies carried weapons a helmet stops from killing with one headshot: pistols other than the Deagle and R8, SMGs, the M4s, Famas, Galil, shotguns, and the AUG beyond mid range. Against an AK, SG 553, AWP, or Scout the helmet changes nothing, so those rounds are not flagged.", "Buy the helmet on every round where the enemy is on pistols, SMGs, or M4-class rifles. It turns their headshot into a survivable hit."),
    'lost_full_buy_to_pistol': ("Lost a full buy to a pistol", "You died with 3700 or more of equipment to a player with under 1500. The eco player took your rifle.", "Against pistols hold range, hold together, and do not peek into a doorway where a pistol can get close."),
    'bomb_died_with_me': ("Bomb died with me", "You died carrying the bomb before 30 s, away from either site, with no plant started.", "The bomb carrier goes in behind the entry players, never first. If you take the first fight, hand the bomb off."),
    'bomb_abandoned': ("Bomb abandoned", "You dropped the bomb and nobody picked it up for 15 s while you were alive and more than 10 m away from it.", "If you drop the bomb on purpose, call it. If it is dropped by accident, go back for it."),
    'planted_without_cover': ("Planted without cover", "You started the plant with a visible enemy within 25 m and no teammate within 15 m, and died during the plant.", "Clear or smoke the angle first, or plant where the enemy cannot see. A plant with an enemy watching is a death, not a plant."),
    'defuse_too_late': ("Defuse started too late", "You started the defuse with less time on the bomb than the defuse takes (10 s, 5 with a kit).", "Know the bomb time. If the defuse cannot finish, save the weapon and leave."),
    'solo_retake': ("Solo retake", "As CT after the plant you came within 20 m of the bomb with no teammate within 15 m and died.", "Retake together. One player into a post-plant is a free kill and no defuse."),
    'died_planting': ("Died while planting", "You were killed between starting and finishing the plant.", "Plant only when the angles are held or smoked. If an enemy is still watching the site, kill or smoke them first."),
    'clutch_lost_no_damage': ("Clutch lost without damage", "You were the last player alive, the round was lost, and you did no damage after your last teammate died.", "In a clutch, either find the one fight you can win or save the weapon. Doing neither gives the enemy the round and the gun."),
    'died_reloading': ("Died reloading", "You reloaded within 2.5 s of your death and did not fire again before it.", "Reload behind cover, and only when the enemy is not about to peek. In contact, switch to the pistol."),
    'reloaded_in_open': ("Reloaded in the open", "You reloaded while visible to the enemy with one alive within 25 m, and died within 3 s.", "Step behind cover before the reload. Every reload in the open is a free peek for the enemy."),
    'reload_near_full': ("Reloaded with a near-full clip in contact", "You reloaded with 80% or more of the clip left while an enemy was within 25 m.", "Reload after fights, not during them. A near-full reload throws away the seconds a fight is decided in."),
    'died_empty_clip': ("Died with an empty clip", "Your clip was empty at death after firing in the last 2 s: you sprayed dry.", "Count the spray. Stop at a third of the clip and reset, or switch to the pistol."),
    'crouch_peek_rifle': ("Crouch-peeked into a rifle", "You were crouched at death, visible to your killer for a second or more, killed from 15 m or more.", "Crouching in the open only makes you a slower target. Crouch behind cover, never in a lane."),
    'jumped_into_fight': ("Jumped into a fight", "You were airborne at your death, or when you fired your last shots, with the killer within 15 m.", "Jumping into a duel gives up accuracy and movement. Land first, then fight."),
}
RULES_POS = {
    'watched_bomb': ("Watched the bomb post-plant", "An enemy started a defuse while you were alive and had them in view or within 15 m. Kill or not, you were in a position to stop it.", "Keep holding a line onto the bomb after the plant rather than hunting for picks."),
    'held_plant_spot': ("Held the plant spot", "An enemy started the plant while you were alive and had them in view or within 15 m. You were where the plant happens, not at the site entrance.", "Keep holding the plant spot itself; it is where the round is decided."),
    'committed_defuse': ("Committed to the defuse", "You started the defuse with enemies still alive. The card says whether any of them could see you and whether the defuse finished.", "Keep committing when the team has cleared enough, and use the fake when it has not."),
    'swung_own_flash': ("Swung your own flash", "Your flash blinded an enemy for a second or more and you came into their view while they were blind.", "Keep swinging your own flashes; a flash nobody swings only tells the enemy where you are."),
    'flash_in_fight': ("Flash blinded an enemy in a fight", "Your flash blinded an enemy for a second or more and a teammate damaged them while they were blind.", "Keep throwing the flash for the teammate who is about to swing."),
    'attacked_off_view': ("Attacked from off their view", "When you first damaged an enemy they were looking more than 90° away from you.", "Keep taking the angles the enemy is not watching."),
    'fought_with_cover': ("Fought with cover", "When you first damaged an enemy, a teammate within 20 m also had them in view: a crossfire set before the fight, not after it.", "Keep setting crossfires with a teammate rather than holding alone."),
    'pistol_switch': ("Switched to pistol when dry", "Your primary's clip ran out in a fight and you were firing the pistol within 3 s instead of reloading.", "Keep the switch; a reload in a close fight is a death."),
    'opener_traded': ("Opening death traded", "You were the round's first death and a teammate killed your killer within 5 s. The opening still cost a player, but the spacing was right.", "Keep taking the first duel from inside trade range."),
    'pre_aimed': ("Pre-aimed", "When an enemy within 35 m first came into your view, your crosshair was already within 5° of them, and that fight ended in your kill.", "Keep placing the crosshair on the exact spot before the swing."),
    'prefired': ("Pre-fired the angle", "Your first shot on the victim came before or within 0.3 s of them becoming visible to you, and it hit.", "Keep pre-firing the common spots when you know someone is there."),
    'first_bullet_hit': ("First bullet hit", "Your first shot in the engagement hit an enemy.", "Keep making the first bullet count: stop, place, fire."),
    'won_after_hit_first': ("Won after being hit first", "The enemy damaged you before you damaged them, and you still got the kill.", "Keep the composure. Return fire on target rather than moving off it."),
    'counter_strafed': ("Counter-strafed engagement", "85% or more of your engagement shots were fired while stationary (from your positions), and you got the kill.", "Keep the stop-shoot-move rhythm."),
    'wallbang_kill': ("Wallbang kill", "Your kill went through a surface.", "Keep punishing the common wallbang spots."),
    'kill_through_smoke': ("Kill through smoke", "Your kill went through a smoke.", "Keep spraying the smoke lines when the enemy is likely to cross."),
    'noscope_kill': ("Noscope kill", "A sniper kill without the scope.", "Keep it for the close fights where scoping would be too slow."),
    'unseen_kill': ("Unseen kill", "At your kill the victim was looking more than 90° away from you.", "Keep taking the angles the enemy is not watching."),
    'kill_with_cover': ("Kill with cover", "At your kill a teammate within 20 m also had the victim in view: a crossfire that was actually set.", "Keep setting crossfires with a teammate rather than holding alone."),
    'info_peek_survived': ("Info peek survived", "You were in an enemy's view for under half a second within 30 m, they fired, you took no damage and backed off more than 3 m.", "Keep the shoulder peeks short and the retreat immediate."),
    'caught_rotation': ("Caught the rotation", "A T-side kill after 30 s on a victim who had moved more than 20 m in the last 10 s, with no teammate within 40 m of you: the lurk caught the rotate.", "Keep timing the lurk to the moment the site is hit."),
    'post_plant_hold': ("Post-plant hold", "After the plant you survived 20 s or more in a post-plant position while enemies were alive to retake.", "Keep the post-plant positions that make the retake cost players."),
    'kill_down_a_man': ("Kill while down a man", "Your kill came while your team had fewer players alive than theirs, and it evened or flipped the count.", "Keep finding the fight that resets the round when the team is behind."),
    'weapon_drop': ("Weapon drop", "In freeze time a rifle left your inventory and appeared in a teammate's within 3 s.", "Keep sharing the buy so the team has five guns rather than four."),
    'stopped_defuse': ("Stopped the defuse", "You killed a defuser during their defuse.", "Keep watching the bomb from a spot you can shoot it from."),
    'killed_planter': ("Killed the planter", "You killed the planter between the start and the end of the plant.", "Keep holding the plant spot rather than the site entrance."),
    'molotov_retreat': ("Molotov forced a retreat", "Your molotov landed with an enemy within 8 m of it, and within 3 s they moved more than 5 m away from it or took damage.", "Keep using fire to move enemies off the spots they hold."),
    'plant_smoke': ("Plant smoke", "Your smoke landed within 10 m of the plant spot in the 10 s before the plant.", "Keep smoking the plant."),
    'retake_smoke': ("Smoke for the retake", "CT post-plant: your smoke landed within 12 m of the bomb and your team entered the site within 8 s of it.", "Keep leading the retake with the smoke."),
    'he_stack': ("HE on a stack", "Your HE damaged two or more enemies.", "Keep throwing the HE where they group."),
    'killed_full_buy_on_eco': ("Killed a full buy on eco", "You killed a player carrying 3700 or more of equipment while carrying under 1500.", "Keep taking the eco fights up close, where the pistol wins."),
    'exit_frag': ("Exit frag", "A kill in the last 10 s of a lost round with at most one teammate alive, on a victim carrying 2000 or more: a weapon the enemy did not get to save.", "Keep taking the exit kill when the round is gone."),
    'picked_rifle_on_eco': ("Picked up a rifle on eco", "You picked up a rifle on a round you started with under 1500 of equipment.", "Keep collecting the weapons on the floor."),
    'plant_under_pressure': ("Plant under pressure", "You planted with an enemy alive within 25 m.", "Keep getting the plant down under pressure; it turns the round into a retake."),
    'fast_plant': ("Fast plant", "You planted before 35 s of round time.", "Keep the fast hits when the read is right."),
    'defused_under_fire': ("Defused under fire", "You defused with at least one enemy still alive.", "Keep committing to the defuse when the team has cleared enough."),
    'sneaky_defuse': ("Sneaky defuse", "You defused with an enemy alive within 25 m who never had you in view during the defuse.", "Keep the quiet defuse when the enemy loses track of you."),
    'defuse_fake': ("Defuse fake", "You started a defuse with an enemy alive and stopped it without finishing: a fake that forces them to peek. Counts more when an enemy died to your team within 3 s of it.", "Keep faking when the enemy is holding the bomb from a spot a teammate can punish."),
    'pistol_switch_won': ("Switched to pistol and won", "Your primary's clip ran out within 3 s before a kill you got with the pistol.", "Keep the pistol switch instead of the reload in a close fight."),
}
BASE_NEG = {'opener_untradeable': 42, 'lost_opener_t': 45, 'crosshair_off': 12, 'first_bullet_missed': 10, 'slow_to_damage': 14, 'shot_moving': 18, 'moving_scoped': 18, 'died_through_smoke': 16,
            'died_to_jumper': 10, 'repeek': 36, 'wide_swing_alone': 34, 'shot_in_back': 30, 'chased_and_died': 34, 'ran_into_contact': 18, 'awp_line': 28, 'instant_death': 18, 'rotated_off_early': 34,
            'frozen_on_site': 40, 'solo_rotation_lost': 42, 'missed_trade': 38, 'baited': 42, 'flashed_myself': 12, 'team_damage': 14, 'flash_blinded_nobody': 12, 'flash_no_swing': 10,
            'molotov_on_nothing': 14, 'wasted_he': 12, 'smg_full_buy': 16, 'bought_vs_save': 25, 'saved_with_money': 22, 'no_kit': 14, 'no_helmet': 10, 'lost_full_buy_to_pistol': 20,
            'bomb_died_with_me': 45, 'bomb_abandoned': 34, 'planted_without_cover': 36, 'defuse_too_late': 18, 'solo_retake': 40, 'died_planting': 40, 'clutch_lost_no_damage': 35,
            'died_reloading': 32, 'reloaded_in_open': 28, 'reload_near_full': 10, 'died_empty_clip': 16, 'crouch_peek_rifle': 14, 'jumped_into_fight': 14}
BASE_POS = {'watched_bomb': 35, 'held_plant_spot': 35, 'committed_defuse': 45, 'swung_own_flash': 25, 'flash_in_fight': 25, 'attacked_off_view': 12, 'fought_with_cover': 12, 'pistol_switch': 12,
            'opener_traded': 25, 'pre_aimed': 8, 'prefired': 12, 'first_bullet_hit': 6, 'won_after_hit_first': 15, 'counter_strafed': 6, 'wallbang_kill': 15, 'kill_through_smoke': 15,
            'noscope_kill': 10, 'unseen_kill': 12, 'kill_with_cover': 12, 'info_peek_survived': 10, 'caught_rotation': 35, 'post_plant_hold': 30, 'kill_down_a_man': 40, 'weapon_drop': 10,
            'stopped_defuse': 55, 'killed_planter': 45, 'molotov_retreat': 15, 'plant_smoke': 15, 'retake_smoke': 15, 'he_stack': 18, 'killed_full_buy_on_eco': 30, 'exit_frag': 25,
            'picked_rifle_on_eco': 10, 'plant_under_pressure': 35, 'fast_plant': 10, 'defused_under_fire': 55, 'sneaky_defuse': 55, 'defuse_fake': 30, 'pistol_switch_won': 15}


RETIRED = set(['multi_kill', 'opening_kill', 'retake_kill', 'kill_down_a_man', 'killed_full_buy_on_eco', 'exit_frag', 'survived_damage', 'won_after_hit_first', 'wallbang_kill', 'kill_through_smoke', 'noscope_kill', 'caught_rotation', 'fast_plant', 'he_stack', 'util_damage', 'molotov_retreat', 'clutch', 'stopped_defuse', 'killed_planter', 'defused_under_fire', 'sneaky_defuse', 'flash_kill', 'flash_assist', 'unseen_kill', 'kill_with_cover', 'pistol_switch_won']) | set(['lost_opener_ct', 'lost_opener_t', 'instant_death', 'died_to_jumper', 'lost_full_buy_to_pistol', 'zero_impact_full_buy', 'died_planting', 'team_flash_death'])   # outcomes rather than decisions: no longer reported (kept in code for reference)
for _k in RETIRED:
    RULES_POS.pop(_k, None); RULES_NEG.pop(_k, None); BASE_POS.pop(_k, None); BASE_NEG.pop(_k, None)


# ----------------------------------------------------------------------------- helpers
def norm(name):
    """Weapon name in one form whether it came from an event ('m4a1_silencer', 'deagle') or an inventory ('M4A1-S', 'Desert Eagle')."""
    n = (name or '').lower().replace('weapon_', '').replace('-', '').replace(' ', '').replace('_', '')
    return {'deserteagle': 'deagle', 'r8revolver': 'revolver', 'dualberettas': 'elite', 'm4a1silencer': 'm4a1s', 'uspsilencer': 'usps', 'cz75a': 'cz75auto'}.get(n, n)


def wclass(name):
    n = norm(name)
    for cls, keys in (('sniper', SNIPERS), ('rifle', RIFLES), ('smg', SMGS), ('shotgun', SHOTGUNS), ('pistol', PISTOLS)):
        if any(k in n for k in keys): return cls
    return 'other'


def wkey(name):
    return (name or '').lower().replace('weapon_', '')


def ang(a, b):
    return abs((a - b + 180) % 360 - 180)


def bearing(frm, to):
    return math.degrees(math.atan2(to[1] - frm[1], to[0] - frm[0]))


def dist_m(a, b):
    return math.dist(a, b) * M


class Ctx:
    """Everything the detectors share for one player: caches, lookups, per-round context."""
    def __init__(self, D, me):
        from mistake_report import by_tick_of, ticktab_of
        import positioning as PS
        self.D = D; self.me = str(me); self.by_tick = by_tick_of(D); self.tab = ticktab_of(D)
        self.by, self.coarse = PS.prepare(D); self.speed = lambda c, sid: PS.speed(self.tab, c, sid)
        self.fz = D['fz']; self.deaths = D['deaths']; self.hurt = D['hurt']; self.fire = D['gunfire']; self.snap = D['snap']
        self.rend = D.get('round_end', {}) or {}
        self.xt = D.get('xt')
        self.xti = {}
        if self.xt is not None and len(self.xt):
            for r in self.xt.itertuples(): self.xti[(int(r.tick), str(r.steamid))] = r
        self._pos = {}
        self.mine = self.snap[self.snap['steamid'] == self.me].set_index('tick')
        self.names = {str(r.steamid): str(r.name) for r in self.snap[['steamid', 'name']].drop_duplicates('steamid').itertuples()}
        # bomb sites from the plants in this demo
        pl = D['plant']; self.sites = {}
        if len(pl) and 'site' in pl.columns:
            for s, g in pl.groupby('site'):
                if g['user_X'].notna().any(): self.sites[int(s)] = (float(g['user_X'].mean()), float(g['user_Y'].mean()))
        self.site_name = {}
        for s, g in (pl.groupby('site') if len(pl) and 'site' in pl.columns else []):
            self.site_name[int(s)] = 'A' if 'A' in str(g.iloc[0].get('user_last_place_name', '')) else ('B' if 'B' in str(g.iloc[0].get('user_last_place_name', '')) else str(s))

    def rt(self, tick, rn):
        return round((tick - self.fz[rn]) / TICK, 1) if rn in self.fz else None

    def end_of(self, rn):
        return int(self.rend.get(rn, self.fz.get(rn + 1, int(self.snap['tick'].max()))))

    def row(self, tick, sid):
        tk = tick if tick in self.by_tick else self.coarse(tick)
        g = self.by_tick.get(tk)
        if g is None: return None
        idx = self._pos.get(tk)
        if idx is None: idx = self._pos[tk] = dict(zip(g['steamid'].astype(str), range(len(g))))
        i = idx.get(str(sid))
        return g.iloc[i] if i is not None else None

    def x(self, tick, sid):
        """Extra tick props (ducking, ammo, economy ...) sampled at this exact tick, else None."""
        return self.xti.get((int(tick), str(sid)))

    def team(self, rn):
        r = self.row(self.fz[rn], self.me)
        if r is None or not (r['team_num'] == r['team_num']): return None
        t = int(r['team_num']); return t if t in (2, 3) else None

    def sees(self, r, sid):
        try: return str(sid) in [str(x) for x in r['approximate_spotted_by']]
        except TypeError: return False

    def alive_counts(self, tick, team):
        t = self.tab.get(self.coarse(tick))
        if t is None: return None, None
        return int(((t['team'] == team) & t['alive']).sum()), int(((t['team'] != team) & (t['team'] > 1) & t['alive']).sum())

    def nearest_mate(self, tick, team):
        t = self.tab.get(self.coarse(tick))
        if t is None: return None
        i = np.where(t['sid'] == self.me)[0]
        if not len(i): return None
        i = i[0]; mask = (t['team'] == team) & t['alive'] & (t['sid'] != self.me)
        if not mask.any(): return None
        d = np.hypot(t['X'][mask] - t['X'][i], t['Y'][mask] - t['Y'][i]) * M
        j = int(np.argmin(d)); return float(d[j]), str(t['name'][mask][j]), (float(t['X'][mask][j]), float(t['Y'][mask][j]))

    def base(self, rn, side, t, place, pos, **kw):
        d = dict(round=rn + 1, side=side, won=self.D['winner'].get(rn) == side, time=self.rt(t, rn), z=None, place=place, pos=pos, near=None, path=[], mate_path=[],
                 killer_path=[], victim_path=[], mates_alive=None, foes_alive=None, nades_thrown=[], order=None, dmg_round=None, equip=None, killer=None, kpos=None,
                 kplace=None, weapon=None, my_weapon=None, dist=0)
        d.update(kw); return d

    def first_seen(self, sid_seer, sid_seen, t_end, back_s=6.0):
        """First coarse tick in [t_end-back, t_end] at which sid_seer had sid_seen in view, after a sample where they had not. None if never."""
        prev = False; found = None
        for ct in range(self.coarse(t_end - int(back_s * TICK)), t_end + 1, 8):
            r = self.row(ct, sid_seen)
            if r is None: continue
            now = self.sees(r, sid_seer)
            if now and not prev: found = ct
            if now and found is not None: return found
            prev = now
        return found


# ----------------------------------------------------------------------------- negatives
def negatives(D, me):
    c = Ctx(D, me); me = c.me; out = []
    deaths = c.deaths; hurt = c.hurt; fire = c.fire; fz = c.fz
    for rn in sorted(fz):
        team = c.team(rn)
        if team is None: continue
        side = 'CT' if team == 3 else 'T'; ft = fz[rn]; end = c.end_of(rn); won = D['winner'].get(rn) == side
        rd = deaths[(deaths['total_rounds_played'] == rn) & (deaths['tick'] >= ft)].sort_values('tick')
        rdm = rd[rd['user_steamid'] == me]; rk = rd[rd['attacker_steamid'] == me]
        rh = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me)]
        rf = fire[(fire['total_rounds_played'] == rn) & (fire['user_steamid'] == me)]
        mates = set(); foes = set()
        g0 = c.by_tick.get(ft)
        if g0 is not None:
            mates = set(str(s) for s in g0[(g0['team_num'] == team) & (g0['steamid'] != me)]['steamid']); foes = set(str(s) for s in g0[(g0['team_num'] != team) & (g0['team_num'] > 1)]['steamid'])
        # ---------------- economy at freeze end
        xr = c.x(ft, me); r0_ = c.row(ft, me)
        spawn = (float(r0_.X), float(r0_.Y)) if r0_ is not None and r0_.X == r0_.X else None
        if xr is not None and g0 is not None and spawn is not None:
            my_eq = int(c.row(ft, me)['current_equip_value']) if c.row(ft, me) is not None else 0
            team_eq = [int(v) for v in g0[(g0['team_num'] == team) & (g0['steamid'] != me)]['current_equip_value'].dropna()]
            avg = (sum(team_eq) / len(team_eq)) if team_eq else 0
            inv = c.row(ft, me)['inventory'] if c.row(ft, me) is not None else []
            try: inv = [str(w) for w in inv]
            except TypeError: inv = []
            prim = [w for w in inv if wclass(w) in ('rifle', 'smg', 'sniper')]
            bal = int(xr.balance) if xr.balance == xr.balance else 0; spent = int(xr.cash_spent_this_round) if xr.cash_spent_this_round == xr.cash_spent_this_round else 0
            if my_eq >= 3000 and avg >= 4000 and prim and all(wclass(w) == 'smg' for w in prim):
                out.append(c.base(rn, side, ft, 'spawn', spawn, kind='smg_full_buy', facts=f"Round {rn+1}, {side}. You bought {', '.join(prim)} with ${my_eq} of equipment while your teammates averaged ${avg:.0f}."))
            if spent >= 3500 and avg < 2000 and len(team_eq) >= 3:
                out.append(c.base(rn, side, ft, 'spawn', spawn, kind='bought_vs_save', facts=f"Round {rn+1}, {side}. You spent ${spent} while your teammates averaged ${avg:.0f} of equipment."))
            if bal >= 4750 and my_eq < 3000 and avg >= 3500:
                out.append(c.base(rn, side, ft, 'spawn', spawn, kind='saved_with_money', facts=f"Round {rn+1}, {side}. You had ${bal} and ${my_eq} of equipment while your teammates averaged ${avg:.0f}."))
            if side == 'CT' and my_eq >= 3700 and xr.has_defuser == False:
                out.append(c.base(rn, side, ft, 'spawn', spawn, kind='no_kit', facts=f"Round {rn+1}, CT. ${my_eq} of equipment and no defuse kit."))
            if xr.has_helmet == False and bal >= 1000:
                sens = []
                for f_ in g0[(g0['team_num'] != team) & (g0['team_num'] > 1)].itertuples():
                    try: bg = best_gun([str(w) for w in f_.inventory])
                    except TypeError: bg = None
                    if bg and not any(k in norm(bg[0]) for k in ONE_SHOT_HELMET): sens.append(f"{f_.name} ({wkey(bg[0])})")
                if len(sens) >= 3:
                    out.append(c.base(rn, side, ft, 'spawn', spawn, kind='no_helmet', facts=f"Round {rn+1}, {side}. No helmet with ${bal} in the bank. Enemies carrying guns a helmet stops from one-shotting the head: {', '.join(sens)}."))
        # ---------------- my deaths
        for d in rdm.itertuples():
            t = int(d.tick); pos = (float(d.user_X), float(d.user_Y)) if d.user_X == d.user_X else None
            if pos is None or c.rt(t, rn) is None or c.rt(t, rn) < 0: continue
            killer = str(d.attacker_steamid) if pd.notna(d.attacker_steamid) else None
            kpos = (float(d.attacker_X), float(d.attacker_Y)) if d.attacker_X == d.attacker_X else None
            place = str(d.user_last_place_name); first_death = len(rd) and int(rd.iloc[0]['tick']) == t and str(rd.iloc[0]['user_steamid']) == me
            nm = c.nearest_mate(t - 1, team)
            traded = bool(len(rd[(rd['tick'] > t) & (rd['tick'] <= t + 5 * TICK) & (rd['user_steamid'] == killer) & (rd['attacker_team_num'] == team)])) if killer else False
            kw = dict(killer=str(d.attacker_name), kpos=kpos, weapon=str(d.weapon), my_weapon=str(d.user_active_weapon_name), dist=round(float(d.distance), 1) if pd.notna(d.distance) else 0)
            base_facts = f"Round {rn+1}, {side}, {c.rt(t, rn)} s. Died at {place} to {d.attacker_name} ({wkey(d.weapon)}, {kw['dist']} m)."
            if first_death and killer in foes:
                if side == 'T': out.append(c.base(rn, side, t, place, pos, kind='lost_opener_t', facts=base_facts + " This was the first death of the round.", order=1, **kw))
                if not traded and (nm is None or nm[0] > 15):
                    out.append(c.base(rn, side, t, place, pos, kind='opener_untradeable', facts=base_facts + f" First death of the round; nearest teammate {nm[0]:.0f} m away ({nm[1]}); nobody traded you within 5 s." if nm else base_facts + " First death of the round with no teammate alive nearby; not traded.", **kw))
            if c.rt(t, rn) < 10 and killer in foes:
                out.append(c.base(rn, side, t, place, pos, kind='instant_death', facts=base_facts + f" Only {c.rt(t, rn)} s into the round.", **kw))
            if bool(d.thrusmoke) and killer in foes:
                out.append(c.base(rn, side, t, place, pos, kind='died_through_smoke', facts=base_facts + " The killing shot came through a smoke.", **kw))
            if bool(d.attackerinair) and kw['dist'] <= 15 and killer in foes:
                out.append(c.base(rn, side, t, place, pos, kind='died_to_jumper', facts=base_facts + " Your killer was in the air when they fired.", **kw))
            # shot in the back: my yaw vs bearing to the killer
            mr = c.row(t, me)
            if mr is not None and kpos and mr['yaw'] == mr['yaw'] and killer in foes:
                off = ang(float(mr['yaw']), bearing(pos, kpos))
                if off > 100: out.append(c.base(rn, side, t, place, pos, kind='shot_in_back', facts=base_facts + f" You were looking {off:.0f}° away from your killer.", **kw))
            # AWP line
            if wclass(d.weapon) == 'sniper' and kw['dist'] >= 30 and killer in foes:
                fs = c.first_seen(killer, me, t, 6.0)
                if fs is not None and (t - fs) / TICK <= 2.0:
                    out.append(c.base(rn, side, t, place, pos, kind='awp_line', facts=base_facts + f" You had been visible to them for {(t - fs) / TICK:.1f} s.", **kw))
            # wide swing alone
            spd = c.speed(c.coarse(t), me)
            if spd > 200 and kpos and (nm is None or nm[0] > 15) and killer in foes:
                p1 = c.row(t - TICK, me)
                if p1 is not None and dist_m((float(p1.X), float(p1.Y)), kpos) - dist_m(pos, kpos) > 1.0:
                    out.append(c.base(rn, side, t, place, pos, kind='wide_swing_alone', facts=base_facts + f" You were moving at {spd:.0f} u/s toward them" + (f", nearest teammate {nm[0]:.0f} m away." if nm else ", no teammate alive nearby."), **kw))
            # re-peek: fired or took damage at P, left > 3 m, back within 8 s to within 2 m of P, died there
            ev_pts = [(int(r.tick), (float(r.user_X), float(r.user_Y))) for r in rf[(rf['tick'] < t) & (rf['tick'] >= t - 12 * TICK)].itertuples() if r.user_X == r.user_X]
            ev_pts += [(int(r.tick), (float(r.user_X), float(r.user_Y))) for r in hurt[(hurt['total_rounds_played'] == rn) & (hurt['user_steamid'] == me) & (hurt['tick'] < t) & (hurt['tick'] >= t - 12 * TICK)].itertuples() if r.user_X == r.user_X]
            done_rp = False
            for t0, P in sorted(ev_pts):
                if done_rp or dist_m(P, pos) > 2 or (t - t0) / TICK > 8: continue
                far = False
                for ct in range(c.coarse(t0), t, 8):
                    r = c.row(ct, me)
                    if r is not None and dist_m((float(r.X), float(r.Y)), P) > 3: far = True; break
                if far and killer in foes:
                    out.append(c.base(rn, side, t, place, pos, kind='repeek', facts=base_facts + f" You had fired or been hit here {(t - t0) / TICK:.1f} s earlier, left, and came back to the same spot.", **kw)); done_rp = True
            # ran into contact: running while unspotted with an unspotted enemy within 20 m in the 3 s before death.
            # "Spotted" is sticky for a short while: a sighting within the last SEEN_MEMORY_S seconds still counts even if line of
            # sight broke since, so a pair that saw each other moments ago never counts; an old sighting no longer does.
            ran = None
            SEEN_MEMORY_S = 8.0
            def ever_seen(a, b, t_to):
                for ct_ in range(max(ft, c.coarse(t_to - int(SEEN_MEMORY_S * TICK)) or ft), t_to + 1, 8):
                    rb = c.row(ct_, b)
                    if rb is not None and c.sees(rb, a): return True
                return False
            for ct in range(c.coarse(t - 3 * TICK), t, 8):
                r = c.row(ct, me); g = c.by_tick.get(ct)
                if r is None or g is None or bool(r['spotted']): continue
                if c.speed(ct, me) <= 200: continue
                fo = g[(g['team_num'] != team) & (g['is_alive'] == True) & (g['spotted'] == False)]
                near_f = [f for f in fo.itertuples() if dist_m((float(r.X), float(r.Y)), (float(f.X), float(f.Y))) < 20
                          and not ever_seen(str(f.steamid), me, ct) and not ever_seen(me, str(f.steamid), ct)]
                if near_f: ran = (ct, near_f[0].name); break
            if ran and killer in foes:
                out.append(c.base(rn, side, t, place, pos, kind='ran_into_contact', facts=base_facts + f" {(t - ran[0]) / TICK:.1f} s earlier you were running, unspotted, with {ran[1]} unspotted within 20 m.", **kw))
            # engagement shots: moving, first bullet, slow to damage, crosshair at first sight
            g4 = rf[(rf['tick'] >= t - 4 * TICK) & (rf['tick'] <= t)]
            if len(g4) >= 3 and killer in foes:
                cls = wclass(d.user_active_weapon_name); thr = 90 if cls == 'smg' else 60
                mv = sum(1 for r in g4.itertuples() if c.speed(c.coarse(int(r.tick)), me) > thr)
                if mv / len(g4) > 0.5 and cls in ('rifle', 'smg', 'sniper', 'pistol'):
                    out.append(c.base(rn, side, t, place, pos, kind='shot_moving', facts=base_facts + f" {mv} of your {len(g4)} shots in the last 4 s were fired while moving faster than {thr} u/s.", **kw))
            if len(g4) and killer in foes:
                f0 = g4.iloc[0]; hit0 = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & ((hurt['tick'] - int(f0['tick'])).abs() <= 1)]
                aimed0 = False
                g_ = c.by_tick.get(c.coarse(int(f0['tick'])))
                if g_ is not None and f0['user_yaw'] == f0['user_yaw'] and f0['user_X'] == f0['user_X']:
                    for f_ in g_[(g_['team_num'] != team) & (g_['is_alive'] == True) & (g_['spotted'] == True)].itertuples():
                        if ang(float(f0['user_yaw']), bearing((float(f0['user_X']), float(f0['user_Y'])), (float(f_.X), float(f_.Y)))) < 12: aimed0 = True; break
                if not len(hit0) and aimed0 and wclass(f0['weapon']) != 'other':
                    out.append(c.base(rn, side, t, place, pos, kind='first_bullet_missed', facts=base_facts + f" Your first shot of the engagement ({wkey(f0['weapon'])}, {c.rt(int(f0['tick']), rn)} s) hit nothing.", **kw))
            if killer in foes:
                fs = c.first_seen(me, killer, t, 6.0)
                if fs is not None:
                    hk = rh[(rh['user_steamid'] == killer) & (rh['tick'] >= fs)]
                    if len(hk) and (int(hk.iloc[0]['tick']) - fs) / TICK > 0.7:
                        t_hit = int(hk.iloc[0]['tick']); clock = fs; notes = []
                        # the fight was a teammate's first: the clock starts when it became yours (the teammate died or the exchange ended)
                        ex = hurt[(hurt['total_rounds_played'] == rn) & (hurt['tick'] >= fs - TICK) & (hurt['tick'] < t_hit) &
                                  (((hurt['attacker_steamid'] == killer) & (hurt['user_steamid'].isin(mates))) | ((hurt['user_steamid'] == killer) & (hurt['attacker_steamid'].isin(mates))))]
                        if len(ex):
                            t_ex = int(ex['tick'].max()); md_ = rd[(rd['attacker_steamid'] == killer) & (rd['user_steamid'].isin(mates)) & (rd['tick'] >= fs) & (rd['tick'] <= t_hit)]
                            if len(md_): t_ex = max(t_ex, int(md_.iloc[0]['tick'])); notes.append(f"{d.attacker_name} was fighting {md_.iloc[0]['user_name']}, who died at {c.rt(int(md_.iloc[0]['tick']), rn)} s")
                            else: notes.append(f"{d.attacker_name} was trading damage with a teammate until {c.rt(t_ex, rn)} s")
                            clock = max(clock, t_ex)
                        # a reload in progress: you cannot shoot, so its time does not count, unless it was a poorly timed reload
                        rl_ = D.get('reloads'); rl_ = rl_[(rl_['user_steamid'] == me) & (rl_['tick'] >= fs - int(2.5 * TICK)) & (rl_['tick'] < t_hit)] if rl_ is not None and len(rl_) else None
                        bad_reload = None
                        if rl_ is not None and len(rl_):
                            t_rl = int(rl_.iloc[-1]['tick']); xr_ = c.x(t_rl, me)
                            if not len(rf[(rf['tick'] > t_rl) & (rf['tick'] < t_hit)]) or t_rl >= fs - int(2.5 * TICK):
                                mx_ = None; left_ = None
                                if xr_ is not None and xr_.active_weapon_ammo == xr_.active_weapon_ammo:
                                    nm_ = norm(str(xr_.active_weapon_name)); mx_ = CLIP.get(nm_)
                                    if mx_ is None:
                                        for k_, v_ in CLIP.items():
                                            if norm(k_) in nm_: mx_ = v_; break
                                    left_ = float(xr_.active_weapon_ammo)
                                if mx_ and left_ is not None and left_ >= 0.4 * mx_:
                                    bad_reload = (t_rl, int(left_), mx_)
                                else:
                                    clock = max(clock, t_rl + int(2.5 * TICK)); notes.append(f"you were reloading (started {c.rt(t_rl, rn)} s" + (f" with {int(left_)} of {mx_} rounds left)" if mx_ and left_ is not None else ")"))
                        delay = (t_hit - clock) / TICK
                        if bad_reload:
                            out.append(c.base(rn, side, t, place, pos, kind='slow_to_damage', facts=base_facts + f" {d.attacker_name} came into your view at {c.rt(fs, rn)} s; your first damage on them came {(t_hit - fs) / TICK:.1f} s later. You had started a reload at {c.rt(bad_reload[0], rn)} s with {bad_reload[1]} of {bad_reload[2]} rounds still in the clip, so the delay came from a reload you did not need.", bad_reload=True, **kw))
                        elif delay > 0.7:
                            out.append(c.base(rn, side, t, place, pos, kind='slow_to_damage', facts=base_facts + f" {d.attacker_name} came into your view at {c.rt(fs, rn)} s" + (("; " + '; '.join(notes)) if notes else "") + f". Counting from {c.rt(clock, rn)} s, your first damage on them came {delay:.1f} s later.", **kw))
                    mr0 = c.row(fs, me); kr0 = c.row(fs, killer)
                    if mr0 is not None and kr0 is not None and mr0['yaw'] == mr0['yaw'] and dist_m((float(mr0.X), float(mr0.Y)), (float(kr0.X), float(kr0.Y))) <= 35:
                        off = ang(float(mr0['yaw']), bearing((float(mr0.X), float(mr0.Y)), (float(kr0.X), float(kr0.Y))))
                        if off > 15: out.append(c.base(rn, side, t, place, pos, kind='crosshair_off', facts=base_facts + f" When {d.attacker_name} first came into view ({c.rt(fs, rn)} s, {dist_m((float(mr0.X), float(mr0.Y)), (float(kr0.X), float(kr0.Y))):.0f} m) your crosshair was {off:.0f}° off them.", **kw))
            # stance and reloads at death
            xd = c.x(t, me)
            if xd is not None and killer in foes:
                if bool(xd.ducking) and kw['dist'] >= 15:
                    fs = c.first_seen(killer, me, t, 6.0)
                    if fs is not None and (t - fs) / TICK >= 1.0:
                        out.append(c.base(rn, side, t, place, pos, kind='crouch_peek_rifle', facts=base_facts + f" You were crouched, visible to them for {(t - fs) / TICK:.1f} s.", **kw))
                if bool(xd.is_airborne) and kw['dist'] <= 15:
                    out.append(c.base(rn, side, t, place, pos, kind='jumped_into_fight', facts=base_facts + " You were in the air when you died.", **kw))
                ammo = float(xd.active_weapon_ammo) if xd.active_weapon_ammo == xd.active_weapon_ammo else None
                if ammo == 0 and len(rf[(rf['tick'] >= t - 2 * TICK) & (rf['tick'] <= t)]) and wclass(d.user_active_weapon_name) in ('rifle', 'smg', 'pistol'):
                    out.append(c.base(rn, side, t, place, pos, kind='died_empty_clip', facts=base_facts + " Your clip was empty when you died.", **kw))
            rl = D.get('reloads'); rl = rl[(rl['user_steamid'] == me) & (rl['tick'] >= t - int(2.5 * TICK)) & (rl['tick'] < t)] if rl is not None and len(rl) else None
            if rl is not None and len(rl) and killer in foes:
                t_rl = int(rl.iloc[-1]['tick'])
                if not len(rf[(rf['tick'] > t_rl) & (rf['tick'] <= t)]):
                    out.append(c.base(rn, side, t, place, pos, kind='died_reloading', facts=base_facts + f" You started a reload {(t - t_rl) / TICK:.1f} s before dying and never fired again.", **kw))
            # lost a full buy to a pistol
            mr = c.row(t - 1, me); kr = c.row(t - 1, killer) if killer else None
            if mr is not None and kr is not None and killer in foes:
                my_eq = int(mr['current_equip_value']) if mr['current_equip_value'] == mr['current_equip_value'] else 0
                k_eq = int(kr['current_equip_value']) if kr['current_equip_value'] == kr['current_equip_value'] else 0
                if my_eq >= 3700 and k_eq < 1500:
                    out.append(c.base(rn, side, t, place, pos, kind='lost_full_buy_to_pistol', facts=base_facts + f" You carried ${my_eq} of equipment; they carried ${k_eq}.", equip=my_eq, **kw))
            # bomb died with me
            try: inv = [str(w) for w in (mr['inventory'] if mr is not None else [])]
            except TypeError: inv = []
            if side == 'T' and any('c4' in w.lower() for w in inv) and c.rt(t, rn) < 30 and place not in ('BombsiteA', 'BombsiteB'):
                pb = D.get('plant_begin'); started = pb is not None and len(pb) and ((pb['total_rounds_played'] == rn) & (pb['tick'] <= t)).any()
                if not started: out.append(c.base(rn, side, t, place, pos, kind='bomb_died_with_me', facts=base_facts + " You were carrying the bomb, away from both sites, and no plant had started.", **kw))
            # died while planting
            pb = D.get('plant_begin')
            if pb is not None and len(pb):
                mine_pb = pb[(pb['total_rounds_played'] == rn) & (pb['user_steamid'] == me) & (pb['tick'] <= t) & (pb['tick'] >= t - 4 * TICK)]
                planted = D['plant'][(D['plant']['total_rounds_played'] == rn) & (D['plant']['user_steamid'] == me) & (D['plant']['tick'] <= t)]
                if len(mine_pb) and not len(planted):
                    out.append(c.base(rn, side, t, place, pos, kind='died_planting', facts=base_facts + f" You had started the plant {(t - int(mine_pb.iloc[-1]['tick'])) / TICK:.1f} s earlier.", **kw))
                    g = c.by_tick.get(c.coarse(int(mine_pb.iloc[-1]['tick'])))
                    if g is not None:
                        vis = [f for f in g[(g['team_num'] != team) & (g['is_alive'] == True)].itertuples() if bool(f.spotted) and dist_m(pos, (float(f.X), float(f.Y))) <= 25]
                        nm2 = c.nearest_mate(int(mine_pb.iloc[-1]['tick']), team)
                        if vis and (nm2 is None or nm2[0] > 15):
                            out.append(c.base(rn, side, int(mine_pb.iloc[-1]['tick']), place, pos, kind='planted_without_cover', facts=f"Round {rn+1}, T, {c.rt(int(mine_pb.iloc[-1]['tick']), rn)} s. You started the plant with {vis[0].name} visible {dist_m(pos, (float(vis[0].X), float(vis[0].Y))):.0f} m away and " + (f"the nearest teammate {nm2[0]:.0f} m away" if nm2 else "no teammate alive nearby") + ", and died during the plant.", **kw))
            # solo retake / solo rotation into a lost site
            if side == 'CT' and killer in foes:
                pl = D['plant'][(D['plant']['total_rounds_played'] == rn) & (D['plant']['tick'] < t)]
                if len(pl) and pl.iloc[-1]['user_X'] == pl.iloc[-1]['user_X']:
                    bpos = (float(pl.iloc[-1]['user_X']), float(pl.iloc[-1]['user_Y']))
                    if dist_m(pos, bpos) <= 20 and (nm is None or nm[0] > 15):
                        out.append(c.base(rn, side, t, place, pos, kind='solo_retake', facts=base_facts + f" Post-plant, {dist_m(pos, bpos):.0f} m from the bomb, " + (f"nearest teammate {nm[0]:.0f} m away." if nm else "no teammate alive."), extra_pos=bpos, extra_label='bomb', **kw))
                site_deaths = rd[(rd['tick'] < t) & (rd['user_team_num'] == team) & (rd['user_last_place_name'] == place)]
                if place in ('BombsiteA', 'BombsiteB') and len(site_deaths) >= 2 and (nm is None or nm[0] > 20):
                    out.append(c.base(rn, side, t, place, pos, kind='solo_rotation_lost', facts=base_facts + f" {len(site_deaths)} teammates had already died at {place}; you entered alone" + (f", nearest teammate {nm[0]:.0f} m away." if nm else "."), **kw))
            # chased and died: a kill of mine in the previous 5 s, then I advanced > 15 m toward remaining enemies
            mk = rk[(rk['tick'] < t) & (rk['tick'] >= t - 5 * TICK)]
            if len(mk) and killer in foes:
                k0 = mk.iloc[-1]; p0 = (float(k0['attacker_X']), float(k0['attacker_Y'])) if k0['attacker_X'] == k0['attacker_X'] else None
                g = c.by_tick.get(c.coarse(int(k0['tick'])))
                if p0 and g is not None:
                    fo = g[(g['team_num'] != team) & (g['is_alive'] == True) & (g['steamid'] != str(k0['user_steamid']))]
                    if len(fo):
                        cen = (float(fo['X'].mean()), float(fo['Y'].mean()))
                        adv = dist_m(p0, cen) - dist_m(pos, cen)
                        if adv > 15: out.append(c.base(rn, side, t, place, pos, kind='chased_and_died', facts=base_facts + f" {(t - int(k0['tick'])) / TICK:.1f} s after killing {k0['user_name']} you had pushed {adv:.0f} m toward the remaining enemies.", **kw))
        # ---------------- clutch lost without damage
        mates_d = rd[rd['user_team_num'] == team]
        if not won and len(mates_d) >= 4 and not len(rdm[rdm['tick'] <= int(mates_d.iloc[-1]['tick'])]) if len(mates_d) else False:
            t_last = int(mates_d.iloc[-1]['tick'])
            if len(mates_d[mates_d['user_steamid'] != me]) >= 4:
                after = rh[rh['tick'] > t_last]
                if int(after['dmg_health'].sum()) == 0:
                    mr = c.row(t_last, me)
                    if mr is not None: out.append(c.base(rn, side, t_last, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), kind='clutch_lost_no_damage', facts=f"Round {rn+1}, {side}, {c.rt(t_last, rn)} s. Last alive from here; no damage dealt after that and the round was lost."))
        # ---------------- rotations (CT)
        if side == 'CT' and g0 is not None:
            r0 = c.row(ft, me)
            if r0 is not None and r0.X == r0.X:
                start = (float(r0.X), float(r0.Y)); left_t = None
                for ct in range(ft, min(ft + 20 * TICK, end), 8):
                    r = c.row(ct, me); g = c.by_tick.get(ct)
                    if r is None or g is None or not bool(r['is_alive']): break
                    fo = g[(g['team_num'] != team) & (g['is_alive'] == True)]
                    if any(dist_m(start, (float(f.X), float(f.Y))) < 40 for f in fo.itertuples()): break
                    if dist_m(start, (float(r.X), float(r.Y))) > 30: left_t = ct; break
                if left_t is not None:
                    for ct in range(left_t, min(left_t + 15 * TICK, end), 16):
                        g = c.by_tick.get(ct); r = c.row(ct, me)
                        if g is None or r is None: continue
                        fo = g[(g['team_num'] != team) & (g['is_alive'] == True)]
                        if any(dist_m(start, (float(f.X), float(f.Y))) < 20 for f in fo.itertuples()) and dist_m(start, (float(r.X), float(r.Y))) > 30:
                            out.append(c.base(rn, side, left_t, str(r0['last_place_name']), start, kind='rotated_off_early', facts=f"Round {rn+1}, CT, {c.rt(left_t, rn)} s. You left your start at {r0['last_place_name']} with no enemy within 40 m of it; enemies reached it {(ct - left_t) / TICK:.0f} s later while you were {dist_m(start, (float(r.X), float(r.Y))):.0f} m away.", extra_pos=(float(r.X), float(r.Y)), extra_label='you, when they arrived')); break
            # frozen on site
            if not won:
                pl = D['plant'][(D['plant']['total_rounds_played'] == rn)]
                hit_t = None; hit_pos = None
                if len(pl) and pl.iloc[0]['user_X'] == pl.iloc[0]['user_X']: hit_t = int(pl.iloc[0]['tick']); hit_pos = (float(pl.iloc[0]['user_X']), float(pl.iloc[0]['user_Y']))
                if hit_t is not None:
                    far = 0; last_pos = None
                    for ct in range(c.coarse(hit_t), min(hit_t + 40 * TICK, end), 8):
                        r = c.row(ct, me)
                        if r is None or not bool(r['is_alive']): break
                        if dist_m((float(r.X), float(r.Y)), hit_pos) > 40: far += 8; last_pos = (float(r.X), float(r.Y), str(r['last_place_name']))
                        else: break
                    if far / TICK > 15 and last_pos:
                        out.append(c.base(rn, side, hit_t, last_pos[2], (last_pos[0], last_pos[1]), kind='frozen_on_site', facts=f"Round {rn+1}, CT, {c.rt(hit_t, rn)} s. The bomb was planted {dist_m((last_pos[0], last_pos[1]), hit_pos):.0f} m from you and you stayed more than 40 m away for {far / TICK:.0f} s. Round lost.", extra_pos=hit_pos, extra_label='bomb'))
        # ---------------- teamplay: missed trade, baited, team damage, self flash
        for d in rd[(rd['user_team_num'] == team) & (rd['user_steamid'] != me)].itertuples():
            t = int(d.tick); killer = str(d.attacker_steamid) if pd.notna(d.attacker_steamid) else None
            if killer not in foes or not (d.user_X == d.user_X): continue
            mr = c.row(t, me)
            if mr is None or not bool(mr['is_alive']) or (len(rdm) and int(rdm.iloc[0]['tick']) <= t + 5 * TICK and int(rdm.iloc[0]['tick']) >= t): continue
            mpos = (float(mr.X), float(mr.Y)); dpos = (float(d.user_X), float(d.user_Y)); dm = dist_m(mpos, dpos)
            shots_after = rf[(rf['tick'] > t) & (rf['tick'] <= t + 5 * TICK)]; dmg_after = int(rh[(rh['tick'] > t) & (rh['tick'] <= t + 5 * TICK)]['dmg_health'].sum())
            if dm <= 15 and not len(shots_after) and dmg_after == 0:
                vis = 0
                for ct in range(c.coarse(t), t + 5 * TICK, 8):
                    kr = c.row(ct, killer)
                    if kr is not None and bool(kr['is_alive']) and c.sees(kr, me): vis += 8
                    elif vis: break
                if vis / TICK >= 1.5:
                    out.append(c.base(rn, side, t, str(mr['last_place_name']), mpos, kind='missed_trade', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. {d.user_name} died {dm:.0f} m from you to {d.attacker_name}, who stayed in your view for {vis / TICK:.1f} s afterwards. You fired nothing and did no damage in the next 5 s.", extra_pos=dpos, extra_label=f"{d.user_name} died", opponents=[(str(d.attacker_name), (float(d.attacker_X), float(d.attacker_Y)))] if d.attacker_X == d.attacker_X else []))
            if dm <= 10 and not bool(mr['spotted']) and not len(rf[(rf['tick'] > t - 3 * TICK) & (rf['tick'] <= t + 3 * TICK)]):
                r3 = c.row(t + 3 * TICK, me)
                if r3 is not None and dist_m((float(r3.X), float(r3.Y)), dpos) - dm > 5:
                    out.append(c.base(rn, side, t, str(mr['last_place_name']), mpos, kind='baited', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. {d.user_name} died {dm:.0f} m from you while you were unspotted; you did not fire and moved {dist_m((float(r3.X), float(r3.Y)), dpos) - dm:.0f} m further away in the next 3 s.", extra_pos=dpos, extra_label=f"{d.user_name} died"))
        td = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & (hurt['user_steamid'].isin(mates)) & (~hurt['weapon'].isin(['hegrenade', 'inferno']))]
        if len(td):
            dmg = int(td['dmg_health'].clip(upper=100).sum()); t = int(td.iloc[0]['tick']); mr = c.row(t, me)
            if dmg >= 5 and mr is not None:
                out.append(c.base(rn, side, t, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), kind='team_damage', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. {dmg} damage to " + ', '.join(f"{n} ({int(v)})" for n, v in td.groupby('user_name')['dmg_health'].sum().items()) + f" with {', '.join(sorted(set(wkey(w) for w in td['weapon'])))}.", dmg=dmg))
        bl = D['blind']
        if len(bl):
            sf = bl[(bl['total_rounds_played'] == rn) & (bl['attacker_steamid'] == me) & (bl['user_steamid'] == me) & (bl['blind_duration'] >= 1.0)]
            for r in sf.itertuples():
                mr = c.row(int(r.tick), me)
                if mr is not None: out.append(c.base(rn, side, int(r.tick), str(mr['last_place_name']), (float(mr.X), float(mr.Y)), kind='flashed_myself', facts=f"Round {rn+1}, {side}, {c.rt(int(r.tick), rn)} s. Your own flash blinded you for {float(r.blind_duration):.1f} s."))
        # ---------------- utility misuse
        contact_t = None
        for ct in range(ft, end, 16):
            g = c.by_tick.get(ct)
            if g is None: continue
            if ((g['team_num'] != team) & (g['is_alive'] == True) & (g['spotted'] == True)).any(): contact_t = ct; break
        dt = D['deton']; dt_r = dt[(dt['steamid'] == me) & (dt['tick'] >= ft) & (dt['tick'] < end)] if len(dt) else dt
        for r in dt_r.itertuples():
            t = int(r.tick); lp = (float(r.x), float(r.y)); g = c.by_tick.get(c.coarse(t))
            if g is None: continue
            fo = g[(g['team_num'] != team) & (g['is_alive'] == True)]
            mr = c.row(t, me); mpos = (float(mr.X), float(mr.Y)) if mr is not None else lp; mplace = str(mr['last_place_name']) if mr is not None else None
            if r.kind == 'flashbang':
                near = [f for f in fo.itertuples() if dist_m(lp, (float(f.X), float(f.Y))) <= 25]
                b = bl[(bl['attacker_steamid'] == me) & ((bl['tick'] - t).abs() <= 2)] if len(bl) else bl
                eb = b[(b['user_team_num'] != team) & (b['blind_duration'] >= 0.5)] if len(b) else b
                if near and not len(eb) and len(bl):
                    out.append(c.base(rn, side, t, mplace, mpos, kind='flash_blinded_nobody', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. Your flash popped with {', '.join(str(f.name) for f in near[:3])} within 25 m and blinded nobody for half a second.", extra_pos=lp, extra_label='flash popped', nades_thrown=[('flashbang', mpos)]))
                elif len(eb):
                    swung = False
                    for ct in range(c.coarse(t), t + 3 * TICK, 8):
                        g2 = c.by_tick.get(ct)
                        if g2 is None: continue
                        for x in eb.itertuples():
                            er = g2[g2['steamid'] == str(x.user_steamid)]
                            if len(er) and any(c.sees(er.iloc[0], s) for s in list(mates) + [me]): swung = True
                    dmg = int(hurt[(hurt['total_rounds_played'] == rn) & (hurt['tick'] >= t) & (hurt['tick'] <= t + 3 * TICK) & (hurt['user_steamid'].isin(set(str(x) for x in eb['user_steamid']))) & (hurt['attacker_steamid'].isin(mates | {me}))]['dmg_health'].sum())
                    if not swung and dmg == 0:
                        out.append(c.base(rn, side, t, mplace, mpos, kind='flash_no_swing', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. Your flash blinded {', '.join(f'{x.user_name} ({float(x.blind_duration):.1f} s)' for x in eb.itertuples())}, but nobody on your team came into their view or damaged them in the next 3 s.", extra_pos=lp, extra_label='flash popped', nades_thrown=[('flashbang', mpos)]))
            elif r.kind == 'molotov' and contact_t is not None and t > contact_t:
                fxr = D['fx'][(D['fx']['kind'] == 'molotov') & ((D['fx']['tick'] - t).abs() <= 2)]
                e_t = int(fxr.iloc[0]['end']) if len(fxr) else t + 7 * TICK
                close = False
                for ct in range(c.coarse(t), e_t, 16):
                    g2 = c.by_tick.get(ct)
                    if g2 is None: continue
                    if any(dist_m(lp, (float(f.X), float(f.Y))) <= 12 for f in g2[(g2['team_num'] != team) & (g2['is_alive'] == True)].itertuples()): close = True; break
                if not close:
                    out.append(c.base(rn, side, t, mplace, mpos, kind='molotov_on_nothing', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. Your molotov burned {(e_t - t) / TICK:.0f} s with no enemy within 12 m, thrown {(t - contact_t) / TICK:.0f} s after your team first saw the enemy.", extra_pos=lp, extra_label='molotov', nades_thrown=[('molotov', mpos)]))
            elif r.kind == 'hegrenade' and contact_t is not None and t > contact_t:
                dmg = int(hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & (hurt['weapon'] == 'hegrenade') & ((hurt['tick'] - t).abs() <= 8)]['dmg_health'].sum())
                spotted_near = [f for f in fo.itertuples() if bool(f.spotted) and dist_m(mpos, (float(f.X), float(f.Y))) <= 30]
                if dmg == 0 and spotted_near:
                    out.append(c.base(rn, side, t, mplace, mpos, kind='wasted_he', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. Your HE did no damage; {', '.join(str(f.name) for f in spotted_near[:3])} had been spotted within 30 m when it went off.", extra_pos=lp, extra_label='HE', nades_thrown=[('hegrenade', mpos)]))
        # ---------------- reloads in the open / near-full
        rl = D.get('reloads')
        if rl is not None and len(rl):
            for r in rl[(rl['user_steamid'] == me) & (rl['tick'] >= ft) & (rl['tick'] < end)].itertuples():
                t = int(r.tick); mr = c.row(t, me); g = c.by_tick.get(c.coarse(t))
                if mr is None or g is None or not bool(mr['is_alive']): continue
                mpos = (float(mr.X), float(mr.Y)); fo = g[(g['team_num'] != team) & (g['is_alive'] == True)]
                near_f = [f for f in fo.itertuples() if dist_m(mpos, (float(f.X), float(f.Y))) <= 25]
                if not near_f: continue
                died_soon = len(rdm) and t < int(rdm.iloc[0]['tick']) <= t + 3 * TICK
                if bool(mr['spotted']) and died_soon:
                    out.append(c.base(rn, side, t, str(mr['last_place_name']), mpos, kind='reloaded_in_open', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. You reloaded while spotted with {near_f[0].name} {dist_m(mpos, (float(near_f[0].X), float(near_f[0].Y))):.0f} m away, and died {(int(rdm.iloc[0]['tick']) - t) / TICK:.1f} s later."))
                xr2 = c.x(t, me)
                if xr2 is not None and xr2.active_weapon_ammo == xr2.active_weapon_ammo:
                    nm_ = norm(str(xr2.active_weapon_name)); mx = CLIP.get(nm_)
                    if mx is None:
                        for k_, v_ in CLIP.items():
                            if norm(k_) in nm_: mx = v_; break
                    if mx and float(xr2.active_weapon_ammo) >= 0.8 * mx:
                        out.append(c.base(rn, side, t, str(mr['last_place_name']), mpos, kind='reload_near_full', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. You reloaded your {xr2.active_weapon_name} with {int(xr2.active_weapon_ammo)} of {mx} rounds left while {near_f[0].name} was {dist_m(mpos, (float(near_f[0].X), float(near_f[0].Y))):.0f} m away."))
        # ---------------- moving scoped shots
        for r in rf[rf['weapon'].str.contains('awp|ssg08', na=False)].itertuples():
            t = int(r.tick); xr2 = c.x(t, me)
            if xr2 is not None and bool(xr2.is_scoped) and c.speed(c.coarse(t), me) > 50 and r.user_X == r.user_X:
                out.append(c.base(rn, side, t, str(r.user_last_place_name), (float(r.user_X), float(r.user_Y)), kind='moving_scoped', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. A scoped {wkey(r.weapon)} shot while moving at {c.speed(c.coarse(t), me):.0f} u/s."))
        # ---------------- bomb abandoned / defuse too late
        bd = D.get('bomb_drop')
        if bd is not None and len(bd):
            for r in bd[(bd['user_steamid'] == me) & (bd['tick'] >= ft) & (bd['tick'] < end)].itertuples():
                t = int(r.tick); bp = D.get('bomb_pick')
                picked = bp is not None and len(bp) and ((bp['tick'] > t) & (bp['tick'] <= t + 15 * TICK)).any()
                r15 = c.row(min(t + 15 * TICK, end - 1), me); dpos = (float(r.user_X), float(r.user_Y)) if r.user_X == r.user_X else None
                if not picked and dpos and r15 is not None and bool(r15['is_alive']) and dist_m((float(r15.X), float(r15.Y)), dpos) > 10 and (not len(rdm) or int(rdm.iloc[0]['tick']) > t + 15 * TICK):
                    out.append(c.base(rn, side, t, str(r.user_last_place_name) if 'user_last_place_name' in bd.columns else None, dpos, kind='bomb_abandoned', facts=f"Round {rn+1}, T, {c.rt(t, rn)} s. You dropped the bomb here; nobody picked it up for 15 s while you were alive {dist_m((float(r15.X), float(r15.Y)), dpos):.0f} m away.", extra_pos=dpos, extra_label='bomb dropped'))
        db = D.get('defuse_begin')
        if db is not None and len(db):
            for r in db[(db['user_steamid'] == me) & (db['tick'] >= ft) & (db['tick'] < end)].itertuples():
                t = int(r.tick); pl = D['plant'][(D['plant']['total_rounds_played'] == rn) & (D['plant']['tick'] < t)]
                if not len(pl): continue
                left = 40.0 - (t - int(pl.iloc[-1]['tick'])) / TICK; need = 5.0 if bool(r.haskit) else 10.0
                if left < need:
                    mr = c.row(t, me)
                    out.append(c.base(rn, side, t, str(mr['last_place_name']) if mr is not None else None, (float(mr.X), float(mr.Y)) if mr is not None else None, kind='defuse_too_late', facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. You started the defuse with {left:.1f} s on the bomb; the defuse takes {need:.0f} s" + (" with a kit." if bool(r.haskit) else " without a kit.")))
    return [o for o in out if o.get('pos') is not None and o['kind'] not in RETIRED]


# ----------------------------------------------------------------------------- positives
def positives(D, me):
    c = Ctx(D, me); me = c.me; out = []
    deaths = c.deaths; hurt = c.hurt; fire = c.fire; fz = c.fz
    for rn in sorted(fz):
        team = c.team(rn)
        if team is None: continue
        side = 'CT' if team == 3 else 'T'; ft = fz[rn]; end = c.end_of(rn); won = D['winner'].get(rn) == side
        rd = deaths[(deaths['total_rounds_played'] == rn) & (deaths['tick'] >= ft)].sort_values('tick')
        rdm = rd[rd['user_steamid'] == me]; rk = rd[rd['attacker_steamid'] == me]
        rh = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me)]
        rf = fire[(fire['total_rounds_played'] == rn) & (fire['user_steamid'] == me)]
        g0 = c.by_tick.get(ft); mates = set(); foes = set()
        if g0 is not None:
            mates = set(str(s) for s in g0[(g0['team_num'] == team) & (g0['steamid'] != me)]['steamid']); foes = set(str(s) for s in g0[(g0['team_num'] != team) & (g0['team_num'] > 1)]['steamid'])
        my_eq0 = int(c.row(ft, me)['current_equip_value']) if c.row(ft, me) is not None and c.row(ft, me)['current_equip_value'] == c.row(ft, me)['current_equip_value'] else 0
        # ---------------- opener traded
        if len(rd) and str(rd.iloc[0]['user_steamid']) == me and str(rd.iloc[0]['attacker_steamid']) in foes:
            d = rd.iloc[0]; t = int(d['tick']); later = rd[(rd['tick'] > t) & (rd['tick'] <= t + 5 * TICK) & (rd['user_steamid'] == str(d['attacker_steamid'])) & (rd['attacker_team_num'] == team)]
            if len(later) and d['user_X'] == d['user_X']:
                out.append(c.base(rn, side, t, str(d['user_last_place_name']), (float(d['user_X']), float(d['user_Y'])), kind='opener_traded', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. First death of the round, to {d['attacker_name']}; {later.iloc[0]['attacker_name']} traded them {(int(later.iloc[0]['tick']) - t) / TICK:.1f} s later.", killer=str(d['attacker_name']), kpos=(float(d['attacker_X']), float(d['attacker_Y'])) if d['attacker_X'] == d['attacker_X'] else None, extra_pos=(float(later.iloc[0]['attacker_X']), float(later.iloc[0]['attacker_Y'])) if later.iloc[0]['attacker_X'] == later.iloc[0]['attacker_X'] else None, extra_label=f"{later.iloc[0]['attacker_name']} traded"))
        # ---------------- my kills
        for k in rk.itertuples():
            t = int(k.tick); victim = str(k.user_steamid)
            if victim not in foes or not (k.attacker_X == k.attacker_X) or c.rt(t, rn) is None or c.rt(t, rn) < 0: continue
            pos = (float(k.attacker_X), float(k.attacker_Y)); vpos = (float(k.user_X), float(k.user_Y)) if k.user_X == k.user_X else None
            place = str(k.attacker_last_place_name); kw = dict(victim=str(k.user_name), vpos=vpos, victim_sid=victim, weapon=str(k.weapon), dist=round(float(k.distance), 1) if pd.notna(k.distance) else 0)
            bf = f"Round {rn+1}, {side}, {c.rt(t, rn)} s. Killed {k.user_name} ({wkey(k.weapon)}, {kw['dist']} m) from {place}."
            if int(k.penetrated or 0) > 0: out.append(c.base(rn, side, t, place, pos, kind='wallbang_kill', facts=bf + " The shot went through a surface.", **kw))
            if bool(k.thrusmoke): out.append(c.base(rn, side, t, place, pos, kind='kill_through_smoke', facts=bf + " The shot went through a smoke.", **kw))
            if bool(k.noscope) and wclass(k.weapon) == 'sniper': out.append(c.base(rn, side, t, place, pos, kind='noscope_kill', facts=bf + " No scope.", **kw))
            vr = c.row(t - 1, victim)
            if vr is not None and vpos and vr['yaw'] == vr['yaw']:
                off = ang(float(vr['yaw']), bearing(vpos, pos))
                if off > 90: out.append(c.base(rn, side, t, place, pos, kind='unseen_kill', facts=bf + f" They were looking {off:.0f}° away from you.", **kw))
                g = c.by_tick.get(c.coarse(t - 1))
                if g is not None:
                    cover = [m_ for m_ in g[(g['team_num'] == team) & (g['is_alive'] == True) & (g['steamid'] != me)].itertuples() if dist_m(pos, (float(m_.X), float(m_.Y))) <= 20 and c.sees(vr, str(m_.steamid))]
                    if cover: out.append(c.base(rn, side, t, place, pos, kind='kill_with_cover', facts=bf + f" {cover[0].name}, {dist_m(pos, (float(cover[0].X), float(cover[0].Y))):.0f} m from you, also had them in view.", extra_pos=(float(cover[0].X), float(cover[0].Y)), extra_label=f"{cover[0].name} covering", **kw))
            # engagement: first bullet, pre-aim, pre-fire, counter-strafe, hit first
            g4 = rf[(rf['tick'] >= t - 4 * TICK) & (rf['tick'] <= t)]
            if len(g4):
                f0 = g4.iloc[0]; hit0 = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & ((hurt['tick'] - int(f0['tick'])).abs() <= 1) & (hurt['user_steamid'].isin(foes))]
                if len(hit0) and wclass(f0['weapon']) != 'other':
                    out.append(c.base(rn, side, t, place, pos, kind='first_bullet_hit', facts=bf + f" Your first shot of the engagement ({c.rt(int(f0['tick']), rn)} s) hit {hit0.iloc[0]['user_name']}.", **kw))
                if len(g4) >= 3:
                    cls = wclass(k.weapon); thr = 90 if cls == 'smg' else 60
                    still = sum(1 for r in g4.itertuples() if c.speed(c.coarse(int(r.tick)), me) <= thr)
                    if still / len(g4) >= 0.85 and cls in ('rifle', 'smg', 'pistol'):
                        out.append(c.base(rn, side, t, place, pos, kind='counter_strafed', facts=bf + f" {still} of your {len(g4)} shots in the last 4 s were fired standing still.", **kw))
            fs = c.first_seen(me, victim, t, 6.0)
            if fs is not None:
                mr0 = c.row(fs, me); vr0 = c.row(fs, victim)
                if mr0 is not None and vr0 is not None and mr0['yaw'] == mr0['yaw'] and dist_m((float(mr0.X), float(mr0.Y)), (float(vr0.X), float(vr0.Y))) <= 35:
                    off = ang(float(mr0['yaw']), bearing((float(mr0.X), float(mr0.Y)), (float(vr0.X), float(vr0.Y))))
                    if off <= 5: out.append(c.base(rn, side, t, place, pos, kind='pre_aimed', facts=bf + f" When they first came into view ({c.rt(fs, rn)} s) your crosshair was {off:.0f}° off them.", **kw))
                hv = rh[(rh['user_steamid'] == victim) & (rh['tick'] >= fs - int(0.3 * TICK)) & (rh['tick'] <= t)]
                if len(hv):
                    t_h = int(hv.iloc[0]['tick'])
                    if t_h <= fs + int(0.3 * TICK): out.append(c.base(rn, side, t, place, pos, kind='prefired', facts=bf + f" Your first hit on them came {(t_h - fs) / TICK:+.1f} s from the moment they became visible.", **kw))
            hm = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == victim) & (hurt['user_steamid'] == me) & (hurt['tick'] >= t - 6 * TICK) & (hurt['tick'] <= t)]
            hv = rh[(rh['user_steamid'] == victim) & (rh['tick'] >= t - 6 * TICK) & (rh['tick'] <= t)]
            if len(hm) and len(hv) and int(hm.iloc[0]['tick']) < int(hv.iloc[0]['tick']):
                out.append(c.base(rn, side, t, place, pos, kind='won_after_hit_first', facts=bf + f" They hit you first ({int(hm['dmg_health'].sum())} damage) and you still won the duel.", **kw))
            # counts, economy, timing
            ma, fo = c.alive_counts(t - 1, team)
            if ma is not None and ma < fo and ma >= fo - 1:
                out.append(c.base(rn, side, t, place, pos, kind='kill_down_a_man', facts=bf + f" Your team was {ma} to {fo} before it; {ma} to {fo - 1} after.", **kw))
            mr = c.row(t - 1, me); vr1 = c.row(t - 1, victim)
            if mr is not None and vr1 is not None:
                my_eq = int(mr['current_equip_value']) if mr['current_equip_value'] == mr['current_equip_value'] else 0
                v_eq = int(vr1['current_equip_value']) if vr1['current_equip_value'] == vr1['current_equip_value'] else 0
                if v_eq >= 3700 and my_eq < 1500: out.append(c.base(rn, side, t, place, pos, kind='killed_full_buy_on_eco', facts=bf + f" They carried ${v_eq}; you carried ${my_eq}.", **kw))
                if not won and v_eq >= 2000 and ma is not None and ma <= 2 and (end - t) / TICK <= 10:
                    out.append(c.base(rn, side, t, place, pos, kind='exit_frag', facts=bf + f" Round lost; {(end - t) / TICK:.0f} s before it ended, with {ma - 1} teammates alive, on a player carrying ${v_eq}.", **kw))
            nm = c.nearest_mate(t - 1, team)
            if side == 'T' and c.rt(t, rn) > 30 and (nm is None or nm[0] > 40) and vpos:
                v10 = c.row(t - 10 * TICK, victim)
                if v10 is not None and dist_m((float(v10.X), float(v10.Y)), vpos) > 20:
                    out.append(c.base(rn, side, t, place, pos, kind='caught_rotation', facts=bf + f" {k.user_name} had moved {dist_m((float(v10.X), float(v10.Y)), vpos):.0f} m in the last 10 s; your nearest teammate was " + (f"{nm[0]:.0f} m away." if nm else "not alive."), **kw))
            # defuse / plant interactions
            db = D.get('defuse_begin'); dfd = D.get('defused')
            if db is not None and len(db):
                vd = db[(db['total_rounds_played'] == rn) & (db['user_steamid'] == victim) & (db['tick'] <= t) & (db['tick'] >= t - 10 * TICK)]
                if len(vd) and not (dfd is not None and len(dfd) and ((dfd['total_rounds_played'] == rn) & (dfd['tick'] <= t) & (dfd['tick'] >= int(vd.iloc[-1]['tick']))).any()):
                    out.append(c.base(rn, side, t, place, pos, kind='stopped_defuse', facts=bf + f" They had started the defuse {(t - int(vd.iloc[-1]['tick'])) / TICK:.1f} s earlier.", **kw))
            pb = D.get('plant_begin')
            if pb is not None and len(pb):
                vp = pb[(pb['total_rounds_played'] == rn) & (pb['user_steamid'] == victim) & (pb['tick'] <= t) & (pb['tick'] >= t - 4 * TICK)]
                planted = D['plant'][(D['plant']['total_rounds_played'] == rn) & (D['plant']['tick'] <= t) & (D['plant']['tick'] >= (int(vp.iloc[-1]['tick']) if len(vp) else t))]
                if len(vp) and not len(planted): out.append(c.base(rn, side, t, place, pos, kind='killed_planter', facts=bf + f" They had started the plant {(t - int(vp.iloc[-1]['tick'])) / TICK:.1f} s earlier.", **kw))
            # pistol switch
            if wclass(k.weapon) == 'pistol':
                prim = rf[(rf['tick'] >= t - 3 * TICK) & (rf['tick'] < t) & (~rf['weapon'].str.contains('|'.join(PISTOLS), na=False))]
                if len(prim):
                    xr2 = c.x(int(prim.iloc[-1]['tick']), me)
                    if xr2 is not None and xr2.active_weapon_ammo == xr2.active_weapon_ammo and float(xr2.active_weapon_ammo) <= 1:
                        out.append(c.base(rn, side, t, place, pos, kind='pistol_switch_won', facts=bf + f" Your {wkey(prim.iloc[-1]['weapon'])} ran dry {(t - int(prim.iloc[-1]['tick'])) / TICK:.1f} s earlier.", **kw))
        # ---------------- info peek survived
        for ct in range(ft, end, 8):
            mr = c.row(ct, me)
            if mr is None or not bool(mr['is_alive']): continue
            try: seers = [str(x) for x in mr['approximate_spotted_by']]
            except TypeError: seers = []
            seers = [s for s in seers if s in foes]
            if not seers: continue
            prev = c.row(ct - 8, me)
            try: pseers = [str(x) for x in prev['approximate_spotted_by']] if prev is not None else []
            except TypeError: pseers = []
            if any(s in pseers for s in seers): continue
            # first sample in an enemy's view: how long does it last?
            n = 0
            for ct2 in range(ct, ct + 2 * TICK, 8):
                r2 = c.row(ct2, me)
                try: s2 = [str(x) for x in r2['approximate_spotted_by']] if r2 is not None else []
                except TypeError: s2 = []
                if any(s in s2 for s in seers): n += 8
                else: break
            if n / TICK >= 0.5: continue
            e = seers[0]; er = c.row(ct, e)
            if er is None or dist_m((float(mr.X), float(mr.Y)), (float(er.X), float(er.Y))) > 30: continue
            ef = fire[(fire['user_steamid'] == e) & (fire['tick'] >= ct) & (fire['tick'] <= ct + TICK)]
            if not len(ef): continue
            hit = hurt[(hurt['user_steamid'] == me) & (hurt['tick'] >= ct) & (hurt['tick'] <= ct + 2 * TICK)]
            r3 = c.row(ct + 2 * TICK, me)
            if not len(hit) and r3 is not None and dist_m((float(r3.X), float(r3.Y)), (float(mr.X), float(mr.Y))) > 3:
                out.append(c.base(rn, side, ct, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), kind='info_peek_survived', facts=f"Round {rn+1}, {side}, {c.rt(ct, rn)} s. You were in {c.names.get(e, e)}'s view for {n / TICK:.2f} s at {dist_m((float(mr.X), float(mr.Y)), (float(er.X), float(er.Y))):.0f} m; they fired {len(ef)} shots, you took no damage and backed off {dist_m((float(r3.X), float(r3.Y)), (float(mr.X), float(mr.Y))):.0f} m.", opponents=[(c.names.get(e, e), (float(er.X), float(er.Y)))]))
                break
        # ---------------- bomb: plants, defuses, post-plant
        pl = D['plant'][(D['plant']['total_rounds_played'] == rn)]
        for r in pl[pl['user_steamid'] == me].itertuples():
            t = int(r.tick); bpos = (float(r.user_X), float(r.user_Y)) if r.user_X == r.user_X else None
            if bpos is None: continue
            g = c.by_tick.get(c.coarse(t)); near = [f for f in g[(g['team_num'] != team) & (g['is_alive'] == True)].itertuples() if dist_m(bpos, (float(f.X), float(f.Y))) <= 25] if g is not None else []
            if near: out.append(c.base(rn, side, t, 'bomb site', bpos, kind='plant_under_pressure', facts=f"Round {rn+1}, T, {c.rt(t, rn)} s. Planted with {', '.join(str(f.name) for f in near[:3])} within 25 m.", opponents=[(str(f.name), (float(f.X), float(f.Y))) for f in near[:3]]))
            if c.rt(t, rn) < 35: out.append(c.base(rn, side, t, 'bomb site', bpos, kind='fast_plant', facts=f"Round {rn+1}, T, {c.rt(t, rn)} s. Planted at {c.rt(t, rn)} s."))
        if len(pl) and pl.iloc[0]['user_X'] == pl.iloc[0]['user_X']:
            t_pl = int(pl.iloc[0]['tick']); bpos = (float(pl.iloc[0]['user_X']), float(pl.iloc[0]['user_Y']))
            if side == 'T':
                alive_at = (not len(rdm)) or int(rdm.iloc[0]['tick']) > t_pl + 20 * TICK
                ma0, fo0 = c.alive_counts(t_pl, team)
                if alive_at and fo0 and (t_pl + 20 * TICK) < end:
                    k_after = rk[rk['tick'] > t_pl]; ex = D.get('exploded'); boom = ex is not None and len(ex) and ((ex['total_rounds_played'] == rn)).any()
                    mr = c.row(t_pl + 20 * TICK, me)
                    if mr is not None: out.append(c.base(rn, side, t_pl + 20 * TICK, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), kind='post_plant_hold', facts=f"Round {rn+1}, T, plant at {c.rt(t_pl, rn)} s with {fo0} enemies alive. You survived 20 s after it" + (f"; {len(k_after)} kill(s) followed" if len(k_after) else "") + (" and the bomb exploded." if boom else "."), extra_pos=bpos, extra_label='bomb'))
                # plant smoke: my smoke within 10 m of the plant in the 10 s before it
                dt = D['deton']; sm = dt[(dt['steamid'] == me) & (dt['kind'] == 'smokegrenade') & (dt['tick'] >= t_pl - 10 * TICK) & (dt['tick'] <= t_pl)] if len(dt) else dt
                for s_ in sm.itertuples():
                    if dist_m((float(s_.x), float(s_.y)), bpos) <= 10:
                        out.append(c.base(rn, side, int(s_.tick), 'bomb site', (float(s_.x), float(s_.y)), kind='plant_smoke', facts=f"Round {rn+1}, T, {c.rt(int(s_.tick), rn)} s. Your smoke landed {dist_m((float(s_.x), float(s_.y)), bpos):.0f} m from the plant spot, {(t_pl - int(s_.tick)) / TICK:.0f} s before the plant.", extra_pos=bpos, extra_label='plant', nades_thrown=[('smokegrenade', (float(s_.x), float(s_.y)))]))
            else:
                dt = D['deton']; sm = dt[(dt['steamid'] == me) & (dt['kind'] == 'smokegrenade') & (dt['tick'] > t_pl) & (dt['tick'] < end)] if len(dt) else dt
                for s_ in sm.itertuples():
                    if dist_m((float(s_.x), float(s_.y)), bpos) > 12: continue
                    entered = None
                    for ct in range(c.coarse(int(s_.tick)), int(s_.tick) + 8 * TICK, 16):
                        g = c.by_tick.get(ct)
                        if g is None: continue
                        for m_ in g[(g['team_num'] == team) & (g['is_alive'] == True)].itertuples():
                            if dist_m((float(m_.X), float(m_.Y)), bpos) <= 15: entered = (ct, str(m_.name)); break
                        if entered: break
                    if entered: out.append(c.base(rn, side, int(s_.tick), 'bomb site', (float(s_.x), float(s_.y)), kind='retake_smoke', facts=f"Round {rn+1}, CT, {c.rt(int(s_.tick), rn)} s. Your smoke landed {dist_m((float(s_.x), float(s_.y)), bpos):.0f} m from the bomb; {entered[1]} entered the site {(entered[0] - int(s_.tick)) / TICK:.0f} s later.", extra_pos=bpos, extra_label='bomb', nades_thrown=[('smokegrenade', (float(s_.x), float(s_.y)))]))
        dfd = D.get('defused')
        if dfd is not None and len(dfd):
            for r in dfd[(dfd['total_rounds_played'] == rn) & (dfd['user_steamid'] == me)].itertuples():
                t = int(r.tick); ma, fo = c.alive_counts(t - 1, team); mr = c.row(t - 1, me)
                if mr is None: continue
                mpos = (float(mr.X), float(mr.Y))
                if fo: out.append(c.base(rn, side, t, str(mr['last_place_name']), mpos, kind='defused_under_fire', facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. Defused with {fo} enemies alive."))
                db = D.get('defuse_begin'); t0 = int(db[(db['total_rounds_played'] == rn) & (db['user_steamid'] == me) & (db['tick'] <= t)].iloc[-1]['tick']) if db is not None and len(db) and ((db['total_rounds_played'] == rn) & (db['user_steamid'] == me) & (db['tick'] <= t)).any() else t - 10 * TICK
                g = c.by_tick.get(c.coarse(t - 1))
                if g is not None and fo:
                    close = [f for f in g[(g['team_num'] != team) & (g['is_alive'] == True)].itertuples() if dist_m(mpos, (float(f.X), float(f.Y))) <= 25]
                    if close:
                        seen_any = False
                        for ct in range(c.coarse(t0), t, 8):
                            r2 = c.row(ct, me)
                            if r2 is not None and any(c.sees(r2, str(f.steamid)) for f in close): seen_any = True; break
                        if not seen_any: out.append(c.base(rn, side, t, str(mr['last_place_name']), mpos, kind='sneaky_defuse', facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. Defused with {close[0].name} alive {dist_m(mpos, (float(close[0].X), float(close[0].Y))):.0f} m away who never had you in view during the defuse.", opponents=[(str(f.name), (float(f.X), float(f.Y))) for f in close[:2]]))
        db = D.get('defuse_begin')
        if db is not None and len(db):
            for r in db[(db['total_rounds_played'] == rn) & (db['user_steamid'] == me)].itertuples():
                t = int(r.tick)
                finished = dfd is not None and len(dfd) and ((dfd['total_rounds_played'] == rn) & (dfd['tick'] >= t) & (dfd['tick'] <= t + 11 * TICK)).any()
                if finished: continue
                # the defuse stopped: did an enemy die to my team within 3 s of the start?
                alive_me = (not len(rdm)) or int(rdm.iloc[0]['tick']) > t + 3 * TICK
                kd = rd[(rd['tick'] > t) & (rd['tick'] <= t + 3 * TICK) & (rd['user_team_num'] != team) & (rd['attacker_team_num'] == team)]
                if alive_me and len(kd):
                    mr = c.row(t, me)
                    if mr is not None: out.append(c.base(rn, side, t, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), kind='defuse_fake', facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. You started the defuse, stopped, and {kd.iloc[0]['user_name']} died to {kd.iloc[0]['attacker_name']} {(int(kd.iloc[0]['tick']) - t) / TICK:.1f} s later.", extra_pos=(float(kd.iloc[0]['user_X']), float(kd.iloc[0]['user_Y'])) if kd.iloc[0]['user_X'] == kd.iloc[0]['user_X'] else None, extra_label=f"{kd.iloc[0]['user_name']} died"))
        # ---------------- decisions around the bomb, measured whether or not a kill followed
        db = D.get('defuse_begin'); dfd = D.get('defused'); pb = D.get('plant_begin')
        def my_row_at(t):
            mr = c.row(t, me)
            return mr if mr is not None and bool(mr['is_alive']) else None
        if db is not None and len(db):
            for r in db[db['total_rounds_played'] == rn].itertuples():
                t = int(r.tick); who = str(r.user_steamid)
                finished = bool(dfd is not None and len(dfd) and ((dfd['total_rounds_played'] == rn) & (dfd['tick'] >= t) & (dfd['tick'] <= t + 11 * TICK)).any())
                if who in foes:
                    mr = my_row_at(t); dr = c.row(t, who)
                    if mr is None or dr is None: continue
                    mpos = (float(mr.X), float(mr.Y)); dpos = (float(dr.X), float(dr.Y)); dm = dist_m(mpos, dpos)
                    if c.sees(dr, me) or dm <= 15:
                        killed = bool(len(rk[(rk['user_steamid'] == who) & (rk['tick'] >= t) & (rk['tick'] <= t + 10 * TICK)]))
                        out.append(c.base(rn, side, t, str(mr['last_place_name']), mpos, kind='watched_bomb', facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. {r.user_name} started the defuse {dm:.0f} m from you" + (" while you had them in view." if c.sees(dr, me) else ".") + (" You killed them." if killed else (" The defuse finished." if finished else " The defuse was stopped.")), got_kill=killed, opponents=[(str(r.user_name), dpos)]))
                elif who == me:
                    ma, fo = c.alive_counts(t - 1, team); mr = my_row_at(t)
                    if mr is None or not fo: continue
                    mpos = (float(mr.X), float(mr.Y))
                    try: seen = [c.names.get(x, x) for x in (str(v) for v in mr['approximate_spotted_by']) if x in foes]
                    except TypeError: seen = []
                    died_soon = bool(len(rdm) and t < int(rdm.iloc[0]['tick']) <= t + 11 * TICK)
                    if finished or died_soon:
                        out.append(c.base(rn, side, t, str(mr['last_place_name']), mpos, kind='committed_defuse', facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. Started the defuse with {fo} enemies alive" + (f", in view of {', '.join(seen)}" if seen else ", unseen") + (". It finished." if finished else ". You died before it finished."), finished=finished))
                    else:
                        kd = rd[(rd['tick'] > t) & (rd['tick'] <= t + 3 * TICK) & (rd['user_team_num'] != team) & (rd['attacker_team_num'] == team)]
                        out.append(c.base(rn, side, t, str(mr['last_place_name']), mpos, kind='defuse_fake', facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. Started a defuse with {fo} enemies alive and stopped it." + (f" {kd.iloc[0]['user_name']} died to {kd.iloc[0]['attacker_name']} {(int(kd.iloc[0]['tick']) - t) / TICK:.1f} s later." if len(kd) else " Nobody was punished for peeking it."), punished=bool(len(kd))))
        if pb is not None and len(pb):
            for r in pb[(pb['total_rounds_played'] == rn) & (pb['user_steamid'].isin(foes))].itertuples():
                t = int(r.tick); who = str(r.user_steamid); mr = my_row_at(t); pr = c.row(t, who)
                if mr is None or pr is None: continue
                mpos = (float(mr.X), float(mr.Y)); ppos = (float(pr.X), float(pr.Y)); dm = dist_m(mpos, ppos)
                if c.sees(pr, me) or dm <= 15:
                    killed = bool(len(rk[(rk['user_steamid'] == who) & (rk['tick'] >= t) & (rk['tick'] <= t + 5 * TICK)]))
                    planted = bool(((D['plant']['total_rounds_played'] == rn) & (D['plant']['tick'] >= t) & (D['plant']['tick'] <= t + 5 * TICK)).any())
                    out.append(c.base(rn, side, t, str(mr['last_place_name']), mpos, kind='held_plant_spot', facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. {r.user_name} started the plant {dm:.0f} m from you" + (" while you had them in view." if c.sees(pr, me) else ".") + (" You killed them." if killed else (" The plant went down." if planted else " The plant was aborted.")), got_kill=killed, opponents=[(str(r.user_name), ppos)]))
        # ---------------- fights: how they were started, measured at your first damage rather than at the kill
        last_hit = {}
        for hh in rh[rh['user_steamid'].isin(foes)].sort_values('tick').itertuples():
            t = int(hh.tick); v = str(hh.user_steamid)
            if v in last_hit and t - last_hit[v] <= 6 * TICK: last_hit[v] = t; continue
            last_hit[v] = t
            if not (hh.attacker_X == hh.attacker_X and hh.user_X == hh.user_X): continue
            mpos = (float(hh.attacker_X), float(hh.attacker_Y)); vpos = (float(hh.user_X), float(hh.user_Y)); vr = c.row(t - 1, v); mr = c.row(t - 1, me)
            killed = bool(len(rk[(rk['user_steamid'] == v) & (rk['tick'] >= t) & (rk['tick'] <= t + 6 * TICK)]))
            kw = dict(victim=str(hh.user_name), vpos=vpos, victim_sid=v, got_kill=killed)
            head = f"Round {rn+1}, {side}, {c.rt(t, rn)} s. First damage on {hh.user_name} ({wkey(hh.weapon)}, {dist_m(mpos, vpos):.0f} m)"
            if vr is not None and vr['yaw'] == vr['yaw']:
                off = ang(float(vr['yaw']), bearing(vpos, mpos))
                if off > 90: out.append(c.base(rn, side, t, str(mr['last_place_name']) if mr is not None else None, mpos, kind='attacked_off_view', facts=head + f": they were looking {off:.0f}° away from you." + (" You got the kill." if killed else ""), **kw))
            g = c.by_tick.get(c.coarse(t - 1))
            if g is not None and vr is not None:
                cover = [m_ for m_ in g[(g['team_num'] == team) & (g['is_alive'] == True) & (g['steamid'] != me)].itertuples() if dist_m(mpos, (float(m_.X), float(m_.Y))) <= 20 and c.sees(vr, str(m_.steamid))]
                if cover: out.append(c.base(rn, side, t, str(mr['last_place_name']) if mr is not None else None, mpos, kind='fought_with_cover', facts=head + f": {cover[0].name}, {dist_m(mpos, (float(cover[0].X), float(cover[0].Y))):.0f} m from you, also had them in view." + (" You got the kill." if killed else ""), **kw))
        # ---------------- pistol switch when the primary ran dry, kill or not
        last_flag = -10 ** 9
        for r in rf[rf['weapon'].str.contains('|'.join(PISTOLS), na=False)].itertuples():
            t = int(r.tick)
            if t - last_flag < 5 * TICK: continue
            prim = rf[(rf['tick'] >= t - 3 * TICK) & (rf['tick'] < t) & (~rf['weapon'].str.contains('|'.join(PISTOLS), na=False))]
            if not len(prim): continue
            xr2 = c.x(int(prim.iloc[-1]['tick']), me)
            if xr2 is None or not (xr2.active_weapon_ammo == xr2.active_weapon_ammo) or float(xr2.active_weapon_ammo) > 1: continue
            mr = c.row(t, me)
            if mr is None or not (r.user_X == r.user_X): continue
            killed = bool(len(rk[(rk['tick'] >= t) & (rk['tick'] <= t + 3 * TICK) & (rk['weapon'].str.contains('|'.join(PISTOLS), na=False))]))
            last_flag = t
            out.append(c.base(rn, side, t, str(r.user_last_place_name), (float(r.user_X), float(r.user_Y)), kind='pistol_switch', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. Your {wkey(prim.iloc[-1]['weapon'])} ran dry and you were firing the {wkey(r.weapon)} {(t - int(prim.iloc[-1]['tick'])) / TICK:.1f} s later." + (" You got the kill." if killed else ""), got_kill=killed))
        # ---------------- utility: molotov retreat, HE stack
        dt = D['deton']; dt_r = dt[(dt['steamid'] == me) & (dt['tick'] >= ft) & (dt['tick'] < end)] if len(dt) else dt
        for r in dt_r.itertuples():
            t = int(r.tick); lp = (float(r.x), float(r.y)); mr = c.row(t, me)
            mpos = (float(mr.X), float(mr.Y)) if mr is not None else lp; mplace = str(mr['last_place_name']) if mr is not None else None
            if r.kind == 'molotov':
                g = c.by_tick.get(c.coarse(t))
                if g is None: continue
                near = [f for f in g[(g['team_num'] != team) & (g['is_alive'] == True)].itertuples() if dist_m(lp, (float(f.X), float(f.Y))) <= 8]
                for f in near:
                    d0 = dist_m(lp, (float(f.X), float(f.Y))); r3 = c.row(t + 3 * TICK, str(f.steamid))
                    dmg = int(hurt[(hurt['attacker_steamid'] == me) & (hurt['user_steamid'] == str(f.steamid)) & (hurt['weapon'] == 'inferno') & (hurt['tick'] >= t) & (hurt['tick'] <= t + 3 * TICK)]['dmg_health'].sum())
                    moved = (dist_m(lp, (float(r3.X), float(r3.Y))) - d0) if r3 is not None else 0
                    if moved > 5 or dmg > 0:
                        out.append(c.base(rn, side, t, mplace, mpos, kind='molotov_retreat', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. Your molotov landed {d0:.0f} m from {f.name}; within 3 s they " + (f"moved {moved:.0f} m away" if moved > 5 else f"took {dmg} damage") + ".", extra_pos=lp, extra_label='molotov', nades_thrown=[('molotov', mpos)], opponents=[(str(f.name), (float(f.X), float(f.Y)))])); break
            elif r.kind == 'hegrenade':
                hh = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & (hurt['weapon'] == 'hegrenade') & ((hurt['tick'] - t).abs() <= 8) & (hurt['user_steamid'].isin(foes))]
                if hh['user_steamid'].nunique() >= 2:
                    out.append(c.base(rn, side, t, mplace, mpos, kind='he_stack', facts=f"Round {rn+1}, {side}, {c.rt(t, rn)} s. Your HE hit " + ', '.join(f"{n} ({int(v)})" for n, v in hh.groupby('user_name')['dmg_health'].sum().items()) + ".", extra_pos=lp, extra_label='HE', nades_thrown=[('hegrenade', mpos)], dmg=int(hh['dmg_health'].sum())))
        # ---------------- economy: rifle pickup on eco, weapon drop in freeze time
        pk = D.get('pickups')
        if pk is not None and len(pk) and my_eq0 < 1500:
            mine_pk = pk[(pk['total_rounds_played'] == rn) & (pk['user_steamid'] == me) & (pk['tick'] > ft) & (pk['item'].astype(str).str.lower().str.contains('|'.join(RIFLES), na=False))]
            for r in mine_pk.head(1).itertuples():
                mr = c.row(int(r.tick), me)
                if mr is not None: out.append(c.base(rn, side, int(r.tick), str(mr['last_place_name']), (float(mr.X), float(mr.Y)), kind='picked_rifle_on_eco', facts=f"Round {rn+1}, {side}, {c.rt(int(r.tick), rn)} s. Picked up a {r.item} on a round you started with ${my_eq0}."))
        r_pre = c.row(ft - 8 * TICK, me); r_at = c.row(ft, me)
        if r_pre is not None and r_at is not None:
            try:
                had = [str(w) for w in r_pre['inventory']]; have = [str(w) for w in r_at['inventory']]
            except TypeError: had, have = [], []
            lost = [w for w in had if wclass(w) == 'rifle' and w not in have]
            if lost:
                g_pre = c.by_tick.get(ft - 8 * TICK); g_at = c.by_tick.get(ft)
                if g_pre is not None and g_at is not None:
                    for m_ in g_at[(g_at['team_num'] == team) & (g_at['steamid'] != me)].itertuples():
                        try:
                            before = [str(w) for w in g_pre[g_pre['steamid'] == m_.steamid].iloc[0]['inventory']] if (g_pre['steamid'] == m_.steamid).any() else []
                            now = [str(w) for w in m_.inventory]
                        except (TypeError, IndexError): continue
                        if lost[0] in now and lost[0] not in before:
                            out.append(c.base(rn, side, ft, 'spawn', (float(r_at.X), float(r_at.Y)) if r_at.X == r_at.X else None, kind='weapon_drop', facts=f"Round {rn+1}, {side}. In freeze time your {lost[0]} went to {m_.name}.")); break
    return [o for o in out if o.get('pos') is not None and o['kind'] not in RETIRED]
