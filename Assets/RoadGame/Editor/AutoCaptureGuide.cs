using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// v10 test: a newcomer's natural route from a clean save, played by a bot that does what the screen says.
    /// "introplay": the intro (stick north, the jump), then it reads the goal widget, taps it, buys the upgrade the garage
    /// offers, drives to the nearest target to see the new numbers, farms with the stock autopilot (leaving the boss
    /// alone) while claiming the free bonus, any affordable weapon level and the free gems, follows the pointer to the
    /// Mammoth once the widget says "ready", fights it, then follows the pointer to a crowd to try the hammer, and
    /// finally reads the next goal. Real-time play (wall-clock timers drive bonuses and respawns). Shots at each step.
    /// </summary>
    public static partial class AutoCapture
    {
        static bool IsGuideScenario(string s) => s == "introplay" || s == "routetest";

        enum GStep { Intro, ReadGoal, OpenGarage, InGarage, SeeUpgrade, Farm, ToBoss, Boss, TryWeapon, NextGoal, Done }
        static GStep gStep = GStep.Intro;
        static float gStepAt;
        static double gRealAt;
        static Vector2 gInput;
        static float gNextLog, gNextFarmShot = 60f, gUnstuck, gStuckFor;
        static int gFrame = -1;
        static float gReadyShotAt = -1f;
        static Vector3 gLastPos;
        static int gBonusClaims, gFreeClaims, gDeaths;
        static bool gWasAlive = true, gSeeShot, gBossShot, gDemoShot, gNewWeaponShot;
        static float gLandAt = -1f, gBuyAt = -1f, gReadyAt = -1f, gBossEngagedAt = -1f, gBossKillAt = -1f, gDemoAt = -1f;
        static float gBoostSeenAt = -1f;

        static void GStepTo(GStep s)
        {
            var g = Game.I;
            gStep = s; gStepAt = g.SessionTime; gRealAt = EditorApplication.timeSinceStartup;
            var d = g.progress.d;
            Debug.Log($"RoadGame GUIDE step={s} t={g.SessionTime:0.0} pos={g.player.Pos} hp={d.hp:0}/{d.maxHp:0} dmg0={d.dmg[0]:0.0} hit={g.progress.DisplayDamage():0.0} " +
                      $"lvl={string.Join(",", d.weaponLevel)} gems={d.gems} kills={d.totalKills}");
        }

        static void GuideSetup(SaveData d)
        {
            if (cfg.scenario == "routetest")
            {
                // strong enough for the Mammoth (the goal says "ready"): only the way there is tested
                d.maxHp = d.hp = 5000; d.regen = 50; d.dmg[0] = 40; d.tutorialDone = true; d.introPending = false;
                d.landingRewardGiven = true; d.upgradesBought = 1; d.weaponLevel[0] = 2; d.uiVersion = 1; d.seenGarage = true;
                Game.ScriptedInput = t => gInput;
                Game.Autopilot = false;
                return;
            }
            // a brand-new game exactly as a newcomer gets it (the intro stays on)
            Game.ScriptedInput = t => gInput;
            Game.Autopilot = false;
        }

        static void GuideTick()
        {
            var g = Game.I;
            if (g == null || !g.Ready || g.player == null || g.hud == null || World.I == null) return;
            // the editor may tick several times per game frame: the bot acts once per frame (its timers use deltaTime)
            if (Time.frameCount == gFrame) return;
            gFrame = Time.frameCount;
            if (cfg.scenario == "routetest") { RouteTestTick(g); return; }
            var pl = g.player; var d = g.progress.d;
            float t = g.SessionTime;
            var goal = g.hud.Goal;

            // deaths: count them, then let the step logic go on (the car respawns at a repair pad)
            if (gWasAlive && !pl.Alive) { gDeaths++; Debug.Log($"RoadGame GUIDE died t={t:0.0} step={gStep}"); }
            gWasAlive = pl.Alive;

            if (t >= gNextLog)
            {
                gNextLog = t + 5f;
                var o = g.overlay;
                Debug.Log($"RoadGame GUIDE t={t:0.0} step={gStep} pos={pl.Pos} hp={d.hp:0}/{d.maxHp:0} regen={d.regen:0.0} dmg0={d.dmg[0]:0.0} dmg1={d.dmg[1]:0.0} hit={g.progress.DisplayDamage():0.0} " +
                          $"lvl={string.Join(",", d.weaponLevel)} copies={string.Join(",", d.weaponCopies)} gems={d.gems} kills={d.totalKills} bonus={gBonusClaims} free={gFreeClaims} deaths={gDeaths} " +
                          $"labels full={o.LabelsFull} thin={o.LabelsCompact} hiddenByHud={o.LabelsHiddenByHud} goal={(goal != null ? goal.kind.ToString() : "-")} " +
                          $"dist={(goal != null ? goal.distance : 0):0} ready={(goal != null && goal.ready)} title=\"{goal?.title}\" sub=\"{goal?.sub}\"");
            }

            switch (gStep)
            {
                case GStep.Intro:
                    // a person on the stick: look for a moment, then full north through the canyon and over the ramp
                    gInput = t < 0.9f ? Vector2.zero : (t < 17f ? new Vector2(0f, 1f) : new Vector2(0.15f, 0.7f));
                    if (gInput.sqrMagnitude > 0.01f) g.OnFirstInput();
                    if (t > 3f && !d.introPending && Intro.Active == null && !pl.Airborne)
                    {
                        gInput = Vector2.zero;
                        gLandAt = t;
                        ShootNamed("01_landing");
                        GStepTo(GStep.ReadGoal);
                    }
                    if (t > 60f && d.introPending) { Debug.Log("RoadGame GUIDE FAIL intro not finished"); GuideEnd(); }
                    break;

                case GStep.ReadGoal:
                    gInput = Vector2.zero;
                    if (t - gStepAt > 3.2f)
                    {
                        ShootNamed("02_next_goal");
                        if (goal != null && goal.kind == Goals.Kind.Upgrade) GStepTo(GStep.OpenGarage);
                        else { Debug.Log("RoadGame GUIDE FAIL no upgrade goal after landing: " + goal?.kind); GStepTo(GStep.Farm); }
                    }
                    break;

                case GStep.OpenGarage:
                    Tap(g.hud.GoalPanel);   // the widget is tappable: it opens the garage on the hood gun
                    GStepTo(GStep.InGarage);
                    break;

                case GStep.InGarage:
                    if (EditorApplication.timeSinceStartup - gRealAt > 1.2)
                    {
                        ShootNamed("03_garage");
                        var btn = FindDeep(g.hud.panels.transform, "LevelUp0");
                        if (btn == null) { Debug.Log("RoadGame GUIDE FAIL no LevelUp0 button"); GuideEnd(); break; }
                        gShellHitsAtBuy = Turret.ShellHits;
                        Tap((RectTransform)btn);
                        gBuyAt = t;
                        Debug.Log($"RoadGame GUIDE bought: panelOpen={g.hud.panels.IsOpen} lvl0={d.weaponLevel[0]} gems={d.gems} goal={g.hud.Goal?.kind}");
                        GStepTo(GStep.SeeUpgrade);
                    }
                    break;

                case GStep.SeeUpgrade:
                    // drive to what the widget points at and watch the numbers
                    if (goal != null && goal.kind == Goals.Kind.SeeUpgrade && goal.hasTarget) gInput = Steer(pl, goal.target, 6.5f);
                    else gInput = Vector2.zero;
                    // the gun's next hits come up as green numbers with the new damage
                    if (gBoostSeenAt < 0f && g.BoostUntil > t && Turret.ShellHits > gShellHitsAtBuy) gBoostSeenAt = t;
                    if (!gSeeShot && gBoostSeenAt > 0f && t - gBoostSeenAt > 0.35f) { gSeeShot = true; ShootNamed("04_upgrade_result"); }
                    if (t - gStepAt > 4f && !gSeeShot) { gSeeShot = true; ShootNamed("04_upgrade_result"); }
                    if (t - gStepAt > 0.5f && (goal == null || goal.kind != Goals.Kind.SeeUpgrade))
                    {
                        Debug.Log($"RoadGame GUIDE see-upgrade over after {t - gStepAt:0.0}s, boosted numbers seen at {(gBoostSeenAt > 0 ? (gBoostSeenAt - gStepAt).ToString("0.0") : "never")}s");
                        ShootNamed("05_goal_boss");
                        StartFarm();
                    }
                    break;

                case GStep.Farm:
                    ClaimThings(g);
                    if (t >= gNextFarmShot) { ShootNamed("farm_" + Mathf.RoundToInt(t / 60f).ToString("00") + "min"); gNextFarmShot += 120f; }
                    if (goal != null && goal.kind == Goals.Kind.Boss && goal.ready && pl.Alive && !g.hud.panels.IsOpen)
                    {
                        gReadyAt = t;
                        gReadyShotAt = t + 0.6f;     // the widget's "ready" line, a moment later (the pointer has turned too)
                        Game.ScriptedInput = tt => gInput;
                        Game.Autopilot = false;
                        GStepTo(GStep.ToBoss);
                    }
                    if (d.bossKills[0] > 0) { GStepTo(GStep.TryWeapon); Game.ScriptedInput = tt => gInput; Game.Autopilot = false; }
                    break;

                case GStep.ToBoss:
                    if (gReadyShotAt > 0f && t >= gReadyShotAt) { gReadyShotAt = -1f; ShootNamed("06_ready"); }
                    ClaimBonusOnly(g);
                    if (goal != null && goal.kind == Goals.Kind.Boss && goal.hasTarget) gInput = Unstick(pl, Steer(pl, goal.target, 0.5f));
                    var boss = World.I.bossSpawns[0] != null ? World.I.bossSpawns[0].target : null;
                    bool near = boss != null && boss.Targetable && Ground.SameLevel(boss.Pos, pl.Pos) && (boss.Pos - pl.Pos).magnitude < 24f;
                    if (g.EngagedBoss != null || near)
                    {
                        gBossEngagedAt = t;
                        Game.ScriptedInput = null;
                        Game.Autopilot = true; Game.AutopilotAvoidBoss = false; Game.AutopilotBoss = true; Game.AutopilotStayInFight = true;
                        GStepTo(GStep.Boss);
                    }
                    if (!pl.Alive || t - gStepAt > 240f) { Debug.Log("RoadGame GUIDE route to the boss failed/timed out"); StartFarm(); }
                    break;

                case GStep.Boss:
                    ClaimBonusOnly(g);
                    if (!gBossShot && t - gStepAt > 6f && g.EngagedBoss != null) { gBossShot = true; ShootNamed("07_boss_fight"); }
                    if (d.bossKills[0] > 0)
                    {
                        gBossKillAt = t;
                        Game.AutopilotBoss = false; Game.AutopilotStayInFight = false;
                        GStepTo(GStep.TryWeapon);
                        Game.ScriptedInput = tt => gInput; Game.Autopilot = false;
                    }
                    else if (!pl.Alive)
                    {
                        Debug.Log("RoadGame GUIDE lost the boss fight");
                        StartFarm();
                    }
                    else if (t - gStepAt > 300f) { Debug.Log("RoadGame GUIDE boss fight timed out"); StartFarm(); }
                    break;

                case GStep.TryWeapon:
                    ClaimBonusOnly(g);
                    if (!gNewWeaponShot && gBossKillAt > 0f && t - gBossKillAt > 1.6f) { gNewWeaponShot = true; ShootNamed("08_new_weapon"); }
                    if (Game.LastDemoAt > 0f)
                    {
                        if (gDemoAt < 0f) gDemoAt = Game.LastDemoAt;
                        if (!gDemoShot && t - gDemoAt > 0.12f) { gDemoShot = true; ShootNamed("09_hammer_demo"); }
                        if (t - gDemoAt > 2.5f) { GStepTo(GStep.NextGoal); gInput = Vector2.zero; Game.ScriptedInput = tt => gInput; Game.Autopilot = false; }
                        break;
                    }
                    if (goal != null && goal.kind == Goals.Kind.TryWeapon && goal.hasTarget)
                    {
                        float dist = Flat(goal.destination - pl.Pos);
                        bool under = pl.Pos.y < -1.5f;
                        if (dist > 14f || under)
                        {
                            Game.ScriptedInput = tt => gInput; Game.Autopilot = false;
                            gInput = Unstick(pl, Steer(pl, goal.target, 0.5f));
                        }
                        else
                        {
                            // in the crowd: let the autopilot weave between the targets (the hammer swings by itself)
                            Game.ScriptedInput = null; Game.Autopilot = true; Game.AutopilotAvoidBoss = true; Game.AutopilotEnemiesOnly = false;
                        }
                    }
                    if (t - gStepAt > 240f) { Debug.Log("RoadGame GUIDE FAIL no hammer demo in 240 s"); GStepTo(GStep.NextGoal); }
                    break;

                case GStep.NextGoal:
                    gInput = Vector2.zero;
                    if (t - gStepAt > 3f)
                    {
                        ShootNamed("10_next_boss_goal");
                        if (goal != null && goal.hasTarget) { Game.ScriptedInput = tt => gInput; gInput = Unstick(pl, Steer(pl, goal.target, 0.5f)); }
                    }
                    if (t - gStepAt > 12f) { ShootNamed("11_on_the_way"); GuideEnd(); }
                    break;
            }
            if (t > 1500f && gStep != GStep.Done) { Debug.Log("RoadGame GUIDE session cap"); GuideEnd(); }
        }

        // ------------------------------------------------------------------ routetest: follow the arrow from awkward spots
        static int rtIndex = -1, rtStuck;
        static float rtAt, rtOnRoadAt, rtRampAt;
        static bool rtShot;
        static readonly System.Collections.Generic.List<(string name, Vector3 p, float yaw)> rtStarts = new System.Collections.Generic.List<(string, Vector3, float)>();
        static int rtOk;

        static void RouteTestTick(Game g)
        {
            var pl = g.player; float t = g.SessionTime;
            if (rtIndex < 0)
            {
                if (t < 1.5f) return;
                // inside each camp of the Dust Flats (palisade all round, one opening), where the first run got stuck,
                // and a few places off the roads
                var camps = World.I.camps[0];
                for (int i = 0; i < camps.Count; i++) rtStarts.Add(("camp" + i, camps[i] + new Vector3(0f, 0f, 2f), 90f * i));
                rtStarts.Add(("stuckspot", new Vector3(-59f, 0f, -36.4f), 80f));
                rtStarts.Add(("east_desert", new Vector3(88f, 0f, -40f), 270f));
                rtStarts.Add(("west_north", new Vector3(-80f, 0f, 30f), 180f));
                rtStarts.Add(("south_east", new Vector3(70f, 0f, -85f), 0f));
                rtStarts.Add(("works_east", new Vector3(90f, 0f, 52f), 270f));     // the guided run came this way and got stuck
                // beside the ramp's trench, by the tunnel lid. The strip between the trench wall (z 47.6) and the hangar's
                // south wall (z 53) is 5.4 m: a car only gets in along it (it cannot turn round in there), so it starts
                // facing along it. Facing across it (the old start, 180) it was boxed in between the two walls for good.
                rtStarts.Add(("works_lid", new Vector3(33f, 0f, 50f), 270f));
                // after the Mammoth fell: in the hangar, the goal is the new weapon up on the surface; the newcomer run
                // ended its boss fight pressed into the south-west corner and drove into the wall for 4 minutes there
                rtStarts.Add(("exit_corner_sw", new Vector3(30.4f, -4.5f, 55.3f), 200f));
                rtStarts.Add(("exit_center", new Vector3(52f, -4.5f, 66f), 180f));
                var only = HArg("-routeStarts");                                    // optional subset (diagnostics)
                if (!string.IsNullOrEmpty(only)) rtStarts.RemoveAll(st => System.Array.IndexOf(only.Split(','), st.name) < 0);
                NextRouteStart(g);
                return;
            }
            if (rtIndex >= rtStarts.Count) return;
            var goal = g.hud.Goal;
            float el = t - rtAt;
            if (el < 0.6f) { gInput = Vector2.zero; return; }
            if (!rtShot && el > 3f) { rtShot = true; ShootNamed($"route_{rtIndex}_{rtStarts[rtIndex].name}"); }
            // a player who just follows the arrow (and backs off when wedged)
            bool exitRun = rtStarts[rtIndex].name.StartsWith("exit_");
            if (goal != null && (goal.kind == Goals.Kind.Boss || exitRun) && goal.hasTarget) gInput = Unstick(pl, Steer(pl, goal.target, 0.5f));
            float onRoad = OffRoute(pl.Pos);
            if (rtOnRoadAt < 0f && onRoad < 8f) rtOnRoadAt = el;
            if (rtRampAt < 0f && Flat(pl.Pos - Structures.WorksRoute[0]) < 10f) rtRampAt = el;
            bool arrived = exitRun ? pl.Pos.y > -0.6f : pl.Pos.y < -3f && Flat(pl.Pos - Structures.WorksBossHome) < 30f;
            if (arrived || el > 150f || !pl.Alive)
            {
                if (arrived) rtOk++;
                Debug.Log($"RoadGame ROUTE start={rtStarts[rtIndex].name} at={rtStarts[rtIndex].p} result={(arrived ? "ARRIVED" : (pl.Alive ? "TIMEOUT" : "DIED"))} " +
                          $"time={el:0.0}s onRoad={rtOnRoadAt:0.0}s worksTurnoff={rtRampAt:0.0}s stuckEvents={gStuckCount} end={pl.Pos}");
                ShootNamed($"route_{rtIndex}_{rtStarts[rtIndex].name}_end");
                rtIndex++;
                if (rtIndex >= rtStarts.Count)
                {
                    Debug.Log($"RoadGame ROUTE SUMMARY arrived {rtOk} of {rtStarts.Count}");
                    nextShot = cfg.times.Length;
                    return;
                }
                NextRouteStart(g);
            }
        }

        static void NextRouteStart(Game g)
        {
            if (rtIndex < 0) rtIndex = 0;
            var st = rtStarts[rtIndex];
            var p = st.p;
            if (st.name.StartsWith("exit_"))
            {
                // the state right after the first boss: it is down, the hammer is new, the goal says "try it"
                var d = g.progress.d;
                var boss = World.I.bossSpawns[0] != null ? World.I.bossSpawns[0].target : null;
                if (boss != null && !boss.dead) boss.Hit(boss.hp + 1d, false, boss.Pos);
                if (d.bossKills[0] < 1) d.bossKills[0] = 1;
                if (d.weaponLevel[1] < 1) d.weaponLevel[1] = 1;
                d.tryWeapon = 1;
                g.progress.UnlockZone(1);
            }
            // a free spot near the wanted one
            for (int k = 0; k < 24 && World.SpawnBlocked(p, 1.6f); k++) p = st.p + Quaternion.Euler(0f, k * 47f, 0f) * Vector3.forward * (1.5f + k * 0.6f);
            g.player.Teleport(p, st.yaw);
            g.cameraRig.Snap();
            rtAt = g.SessionTime; rtOnRoadAt = -1f; rtRampAt = -1f; rtShot = false;
            gStuckCount = 0; gUnstuck = 0f; gStuckFor = 0f;
            Debug.Log($"RoadGame ROUTE begin {st.name} at {p}");
        }

        /// <summary>Distance from the Dust Flats main road (the way to the Works turn-off).</summary>
        static float OffRoute(Vector3 p)
        {
            var r = World.I.roads[0][0];
            if (r == null || r.Count < 2) return 999f;
            Goals.ClosestSegment(r, p, out _, out float off);
            return off;
        }

        static void StartFarm()
        {
            Game.AutopilotStayInFight = false;
            Game.ScriptedInput = null;
            Game.Autopilot = true; Game.AutopilotAvoidBoss = true; Game.AutopilotBoss = false; Game.AutopilotEnemiesOnly = false;
            GStepTo(GStep.Farm);
        }

        static void GuideEnd()
        {
            var g = Game.I; var d = g.progress.d;
            Debug.Log($"RoadGame GUIDE SUMMARY landing={gLandAt:0.0} bought={gBuyAt:0.0} ready={gReadyAt:0.0} bossEngaged={gBossEngagedAt:0.0} bossKilled={gBossKillAt:0.0} demo={gDemoAt:0.0} demoHits={Game.LastDemoHits} " +
                      $"bonus={gBonusClaims} free={gFreeClaims} deaths={gDeaths} upgrades={d.upgradesBought} lvl={string.Join(",", d.weaponLevel)} gems={d.gems} dmg0={d.dmg[0]:0.0} dmg1={d.dmg[1]:0.0} hp={d.maxHp:0} kills={d.totalKills} t={g.SessionTime:0.0}");
            gStep = GStep.Done;
            nextShot = cfg.times.Length;   // the main tick wraps up and quits
        }

        /// <summary>The free bonus, an affordable weapon level (garage dot), the free gems (shop dot): a player taps them.</summary>
        static void ClaimThings(Game g)
        {
            ClaimBonusOnly(g);
            if (g.hud.panels.IsOpen || !g.player.Alive) return;
            var P = g.progress;
            int up = P.AffordableUpgrade();
            if (up >= 0 && g.hud.GarageButton.gameObject.activeInHierarchy)
            {
                Tap(g.hud.GarageButton);
                var b = FindDeep(g.hud.panels.transform, "LevelUp" + up);
                if (b != null) Tap((RectTransform)b);
                Debug.Log($"RoadGame GUIDE garage: bought weapon {up} -> lvl {P.d.weaponLevel[up]} gems={P.d.gems}");
                if (g.hud.panels.IsOpen) g.hud.panels.Close();
                return;
            }
            if (g.hud.ShopButton.gameObject.activeInHierarchy && Progress.NowMs >= g.freeGemsAt)
            {
                Tap(g.hud.ShopButton);
                var b = FindDeep(g.hud.panels.transform, "BuyFree");
                if (b != null) { Tap((RectTransform)b); gFreeClaims++; Debug.Log($"RoadGame GUIDE shop: free gems, gems={P.d.gems}"); }
                if (g.hud.panels.IsOpen) g.hud.panels.Close();
            }
        }

        static void ClaimBonusOnly(Game g)
        {
            if (g.hud.panels.IsOpen || !g.player.Alive) return;
            if (g.BonusReady && g.hud.BonusButton.gameObject.activeInHierarchy)
            {
                double v = g.BonusValue; bool hp = g.BonusIsHp;
                Tap(g.hud.BonusButton);
                gBonusClaims++;
                Debug.Log($"RoadGame GUIDE bonus #{gBonusClaims}: +{v:0.#} {(hp ? "maxHP" : "damage")} t={g.SessionTime:0.0}");
            }
        }

        static int gShellHitsAtBuy = int.MaxValue;

        static float Flat(Vector3 v) { v.y = 0f; return v.magnitude; }

        /// <summary>Stick towards a point (world XZ = stick XY), easing off close to it; a point behind the car is
        /// reached with a three-point turn from a stop or a forward U-turn on the move, as a player would.</summary>
        static Vector2 Steer(Player pl, Vector3 to, float stopAt)
        {
            var off = to - pl.Pos; off.y = 0f;
            float m = off.magnitude;
            if (m < stopAt) return Vector2.zero;
            return CarDriver.TowardTarget(new Vector2(off.x, off.z) / m * SpeedStick(Mathf.Clamp01(m / 6f + 0.4f)), pl.Heading, pl.ForwardSpeed, pl.GearDirection, m);
        }

        static float gUnstuckDur, gEscapeSign = 1f;
        static int gStuckCount, gStuckShots;
        static Vector3 gStuckAt;

        /// <summary>
        /// Wedged against something: back away, then swing out to one side (the side alternates, each try longer); a
        /// screenshot if it keeps happening at the same spot.
        /// </summary>
        static Vector2 Unstick(Player pl, Vector2 want)
        {
            float dt = Time.deltaTime;
            if (gUnstuck > 0f)
            {
                // a three-point turn by the car's own heading: straight back (stick behind the car), then forward
                // turning out to one side of the wanted way (the side and the order alternate on every try)
                gUnstuck -= dt;
                var w = want.sqrMagnitude > 1e-4f ? want.normalized : new Vector2(0f, 1f);
                var f3 = pl.transform.forward; var f = new Vector2(f3.x, f3.z).normalized;
                bool first = gUnstuck > gUnstuckDur * 0.45f;
                bool backFirst = gStuckCount % 4 < 2;
                // a multi-point turn like a player's: back with the stick behind and to one side (the tail swings that
                // way, the nose towards the wanted way), then forward on full lock the same way round. Straight back
                // only shuffled the car between two walls (the strip between the Works and its trench).
                float a = Vector2.SignedAngle(f, w);
                float side = Mathf.Abs(a) > 20f ? Mathf.Sign(a) : gEscapeSign;
                var back = (Vector2)(Quaternion.Euler(0f, 0f, 40f * side) * (-f));
                var fwd = CarDriver.TowardForward((Vector2)(Quaternion.Euler(0f, 0f, 60f * side) * f), pl.Heading);
                return first == backFirst ? back : fwd;
            }
            if (want.sqrMagnitude > 0.04f && pl.Speed < 0.8f && !pl.Airborne && pl.Alive) gStuckFor += dt; else gStuckFor = 0f;
            if (Flat(pl.Pos - gStuckAt) > 10f) gStuckCount = 0;
            if (gStuckFor > 1.2f)
            {
                gStuckFor = 0f;
                if (gStuckCount == 0) gStuckAt = pl.Pos;
                gStuckCount++;
                gEscapeSign = gStuckCount % 2 == 1 ? 1f : -1f;
                gUnstuckDur = Mathf.Min(1.6f + 0.7f * gStuckCount, 6f);
                gUnstuck = gUnstuckDur;
                Debug.Log($"RoadGame GUIDE unstick #{gStuckCount} at {pl.Pos} goal={Game.I.hud.Goal?.kind} target={Game.I.hud.Goal?.target}");
                if (gStuckCount == 4 && gStuckShots < 3) { gStuckShots++; ShootNamed("stuck_" + gStuckShots); }
            }
            return want;
        }

        static void Tap(RectTransform r)
        {
            if (r == null) return;
            var b = r.GetComponent<Button>();
            if (b != null && b.interactable && r.gameObject.activeInHierarchy) b.onClick.Invoke();
            else Debug.Log("RoadGame GUIDE tap missed " + r.name + " active=" + r.gameObject.activeInHierarchy);
        }

        static Transform FindDeep(Transform root, string name)
        {
            if (root.name == name) return root;
            for (int i = 0; i < root.childCount; i++)
            {
                var f = FindDeep(root.GetChild(i), name);
                if (f != null) return f;
            }
            return null;
        }

        /// <summary>A screenshot with a name (the guided run shoots at its steps, not at fixed times).</summary>
        static void ShootNamed(string name)
        {
            var g = Game.I;
            g.cam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            var path = Path.Combine(cfg.outDir, $"{cfg.scenario}_{name}.png");
            File.WriteAllBytes(path, tex.EncodeToPNG());
            Object.DestroyImmediate(tex);
            var d = g.progress.d; var o = g.overlay; var goal = g.hud.Goal;
            Debug.Log($"RoadGame AutoCapture: {path} | t={g.SessionTime:0.0} hp={d.hp:0}/{d.maxHp:0} dmg={d.dmg[0]:0.0} hit={g.progress.DisplayDamage():0.0} gems={d.gems} kills={d.totalKills} " +
                      $"labels full={o.LabelsFull} thin={o.LabelsCompact} hiddenByHud={o.LabelsHiddenByHud} goal={goal?.kind} \"{goal?.title}\" / \"{goal?.sub}\"");
        }
    }
}
