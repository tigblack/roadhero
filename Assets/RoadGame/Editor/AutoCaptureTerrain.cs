using System.Collections.Generic;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// Terrain and flip tests:
    ///  - "flip": a slow fall off the mesa onto the roof (put back on the wheels after 2 s), a fast drive off it (lands on
    ///    the wheels), a roll that lands on the roof and carries on back onto the wheels (timer resets), a full barrel roll
    ///    over the big jump, a kicker taken at an angle, a drive across a hill's flank (lean), a roof landing half over a
    ///    ledge (moved to the nearest safe spot), a slide off a hairpin;
    ///  - "terrain": runs over the hills, bumps, kickers, big jumps, the ridge pass and the mesa jump (take-offs, landings);
    ///  - "mesa": the switchback road from the foot of the mesa to its summit and the jump back down (autopilot);
    ///  - "terraintour": one game-camera shot per new place.
    /// </summary>
    public static partial class AutoCapture
    {
        static bool IsTerrainScenario(string s) => s == "flip" || s == "terrain" || s == "mesa" || s == "terraintour";

        // ------------------------------------------------------------------ shared: a run = place the car, drive, log the flight
        struct TerrRun { public string name; public Vector3 p; public float yaw; public float speed; public Vector2 stick; public float stickSecs; public float secs; public System.Action<Player> setup; public System.Action<Player> onTakeoff; }
        static readonly List<TerrRun> runs = new List<TerrRun>();
        static int runIndex = -1;
        static float runT0;
        static bool runWasAir, runSpun;
        static float runTakeoffT, runMaxY, runMaxTumble, runRoofMax, runMaxTilt;
        static Vector3 runTakeoffP;
        static int runFlipBacks0, runSelfRights0, runCrest0, runLandings;
        static double runHp0;
        static Vector3 runRoofPos;
        static Vector2 runStick;

        static Vector2 TerrainInput(float t) => runStick;

        static float RunStart(int i)
        {
            float s = 1.5f;
            for (int k = 0; k < i; k++) s += runs[k].secs;
            return s;
        }

        static void TerrainTick(Player pl)
        {
            if (runs.Count == 0) BuildRuns();
            float t = Game.I.SessionTime;
            if (cfg.scenario == "mesa") { MesaTick(pl, t); return; }
            int want = -1;
            for (int i = 0; i < runs.Count; i++) if (t >= RunStart(i)) want = i;
            if (want != runIndex)
            {
                EndRun(pl);
                runIndex = want;
                if (runIndex >= 0) StartRun(pl, runIndex);
            }
            if (runIndex < 0) return;
            var r = runs[runIndex];
            float local = t - RunStart(runIndex);
            runStick = local < r.stickSecs ? r.stick : Vector2.zero;
            if (pl.Airborne && !runWasAir)
            {
                runWasAir = true; runTakeoffT = t; runTakeoffP = pl.Pos; runMaxY = pl.Pos.y;
                Debug.Log($"RoadGame RUN {r.name} takeoff v={pl.Speed:0.0} vy={pl.VerticalSpeed:0.0} at={pl.Pos} crest={pl.CrestJumps > runCrest0}");
                if (r.onTakeoff != null && !runSpun) { runSpun = true; r.onTakeoff(pl); }
            }
            if (pl.Airborne) { runMaxY = Mathf.Max(runMaxY, pl.Pos.y); runMaxTumble = Mathf.Max(runMaxTumble, Mathf.Abs(pl.TumbleDeg)); if (pl.RoofTime > 0f) Debug.Log("RoadGame RUN ERROR roof timer running in the air"); }
            if (!pl.Airborne && runWasAir)
            {
                runWasAir = false;
                runLandings++;
                var d = pl.Pos - runTakeoffP; d.y = 0;
                Debug.Log($"RoadGame RUN {r.name} land air={t - runTakeoffT:0.00}s apex={runMaxY:0.00} dist={d.magnitude:0.0} impact={pl.LastLandingImpact:0.0} kind={pl.LastLandingKind} spin={pl.LastAirSpinDeg:0} maxTumbleAir={pl.LastAirMaxTumbleDeg:0} at={pl.Pos}");
            }
            if (pl.OnRoof) { runRoofMax = Mathf.Max(runRoofMax, pl.RoofTime); runRoofPos = pl.Pos; }
            if (pl.WheelsDown && pl.GroundPiece != null)
            {
                var n = Ground.Sample(pl.Pos.x, pl.Pos.z, pl.Pos.y + 0.3f).normal;
                runMaxTilt = Mathf.Max(runMaxTilt, Vector3.Angle(n, Vector3.up));
            }
            runMaxTumble = Mathf.Max(runMaxTumble, Mathf.Abs(pl.TumbleDeg));
        }

        static void StartRun(Player pl, int i)
        {
            var r = runs[i];
            pl.Teleport(r.p, r.yaw);
            pl.SetSpeed(r.speed);
            r.setup?.Invoke(pl);
            Game.I.cameraRig.Snap();
            runWasAir = false; runSpun = false;
            runMaxTumble = runRoofMax = runMaxTilt = 0f; runLandings = 0;
            runFlipBacks0 = pl.FlipBacks; runSelfRights0 = pl.SelfRights; runCrest0 = pl.CrestJumps;
            runHp0 = Game.I.progress.d.hp;
            runRoofPos = Vector3.zero;
            Debug.Log($"RoadGame RUN {r.name} start={r.p} yaw={r.yaw} v={r.speed}");
        }

        static void EndRun(Player pl)
        {
            if (runIndex < 0 || runIndex >= runs.Count) return;
            var r = runs[runIndex];
            var moved = runRoofPos != Vector3.zero ? new Vector2(pl.Pos.x - runRoofPos.x, pl.Pos.z - runRoofPos.z).magnitude : 0f;
            Debug.Log($"RoadGame RUN {r.name} end pos={pl.Pos} landings={runLandings} crestJumps={pl.CrestJumps - runCrest0} maxTumble={runMaxTumble:0} roofTimeMax={runRoofMax:0.00} flipBacks={pl.FlipBacks - runFlipBacks0} " +
                      $"selfRights={pl.SelfRights - runSelfRights0} maxSlopeTilt={runMaxTilt:0.0} onWheels={pl.WheelsDown} hpChange={Game.I.progress.d.hp - runHp0:0.0} flipMovedFromRoof={moved:0.0}m");
        }

        static void BuildRuns()
        {
            runs.Clear();
            Vector3 Fw(float yaw) => new Vector3(Mathf.Sin(yaw * Mathf.Deg2Rad), 0f, Mathf.Cos(yaw * Mathf.Deg2Rad));
            Vector2 St(float yaw, float m) => new Vector2(Mathf.Sin(yaw * Mathf.Deg2Rad), Mathf.Cos(yaw * Mathf.Deg2Rad)) * SpeedStick(m);
            if (cfg.scenario == "flip")
            {
                // 1) creeping off the summit's south edge: an 8 m fall, the nose goes over -> the roof -> back on the wheels after 2 s
                runs.Add(new TerrRun { name = "roof_fall_slow", p = new Vector3(-78f, Terrain.MesaTop, 65f), yaw = 180f, speed = 2.2f, stick = St(180f, 0.2f), stickSecs = 1.6f, secs = 9f });
                // 2) the same edge at speed: the car flies out and lands on its wheels
                runs.Add(new TerrRun { name = "drive_off_fast", p = new Vector3(-76f, Terrain.MesaTop, 78f), yaw = 180f, speed = 10f, stick = St(180f, 0.8f), stickSecs = 2.5f, secs = 6.5f });
                // 3) a roll that lands on the roof with spin left: it carries on over onto the wheels before the timer runs out
                runs.Add(new TerrRun { name = "roof_roll_selfright", p = new Vector3(-84f, 0f, 46f), yaw = 0f, speed = 0f, secs = 6.5f,
                    setup = pl => { pl.DebugSetTumble(-130f, Vector3.forward, 6.2f); pl.DebugDrop(5.5f); } });
                // 4) the big jump with a full barrel roll in the air: upside down in the air, back on the wheels at the landing
                var bj = Terrain.BigJumps.Find(j => j.name == "BigJump0");
                runs.Add(new TerrRun { name = "air_barrel_roll", p = bj.lip - Fw(bj.yaw) * 34f, yaw = bj.yaw, speed = 13.6f, stick = St(bj.yaw, 1f), stickSecs = 4f, secs = 7f,
                    onTakeoff = pl => pl.DebugTumble(new Vector3(0f, 0f, 2f * Mathf.PI / 0.88f)) });
                // 5) a kicker taken at 25 degrees: one wheel leaves first and the car rolls a little in the air
                var k0 = Terrain.Kickers.Find(k => k.p.name == "Kicker0c").p;
                float ky = k0.rect.Yaw;
                var lipC = k0.rect.World(0f, k0.rect.half.y - 0.8f, 0f);
                runs.Add(new TerrRun { name = "kicker_at_angle", p = lipC - Fw(ky + 25f) * 15f, yaw = ky + 25f, speed = 12f, stick = St(ky + 25f, 1f), stickSecs = 2.2f, secs = 6f });
                // 6) across the flank of the big hill: the car leans with the slope, nothing else happens
                var h0 = Terrain.Hills.Find(h => h.p.name == "Hill0a").p;
                runs.Add(new TerrRun { name = "hill_flank_lean", p = h0.rect.World(-17f, -3f, 0f), yaw = h0.rect.Yaw + 90f, speed = 7f, stick = St(h0.rect.Yaw + 90f, 0.55f), stickSecs = 4.5f, secs = 6f });
                // 7) on the roof half over a ledge (the hairpin's open edge): put back on the wheels at the nearest safe spot
                runs.Add(new TerrRun { name = "roof_on_ledge", p = new Vector3(-43.6f, Terrain.MesaH1, 89f), yaw = 90f, speed = 0f, secs = 6f,
                    setup = pl => pl.DebugSetTumble(180f, Vector3.forward, 0f) });
                // 8) sliding off a hairpin's edge at an angle (a fall from 5.4 m with some roll)
                runs.Add(new TerrRun { name = "hairpin_slide_off", p = new Vector3(-63f, Terrain.MesaH2, 50f), yaw = 235f, speed = 4f, stick = St(235f, 0.3f), stickSecs = 2f, secs = 8f });
                // 9) straight over the first ramp of the game: no roll at all
                runs.Add(new TerrRun { name = "intro_ramp_straight", p = new Vector3(0f, 0f, -150f), yaw = 0f, speed = 13.6f, stick = St(0f, 1f), stickSecs = 4f, secs = 6f });
            }
            else
            {
                // the main road over a hill at full speed
                var rh = Terrain.Hills.Find(h => h.p.name == "RoadHill0a").p;
                runs.Add(new TerrRun { name = "road_hill_full", p = rh.rect.Center - rh.rect.Forward * 22f, yaw = rh.rect.Yaw, speed = 13.6f, stick = St(rh.rect.Yaw, 1f), stickSecs = 4f, secs = 5.5f });
                // a row of bumps: a hop over each
                var b0 = Terrain.Hills.Find(h => h.p.name == "Bumps0a0").p;
                runs.Add(new TerrRun { name = "bumps_row", p = b0.rect.Center - new Vector3(0f, 0f, 8.5f), yaw = 0f, speed = 12f, stick = St(0f, 1f), stickSecs = 4.5f, secs = 6f });
                // kickers
                foreach (var kn in new[] { "Kicker0a", "Kicker0b" })
                {
                    var k = Terrain.Kickers.Find(x => x.p.name == kn).p;
                    runs.Add(new TerrRun { name = kn, p = k.rect.Center - k.rect.Forward * 16f, yaw = k.rect.Yaw, speed = 11f, stick = St(k.rect.Yaw, 0.9f), stickSecs = 3f, secs = 5.5f });
                    runs.Add(new TerrRun { name = kn + "_slow", p = k.rect.Center - k.rect.Forward * 10f, yaw = k.rect.Yaw, speed = 5f, stick = St(k.rect.Yaw, 0.4f), stickSecs = 3f, secs = 5.5f });
                }
                // big jumps: full speed and slow (the ramp's minimum take-off speed still clears the barrier)
                foreach (var bj in Terrain.BigJumps)
                {
                    runs.Add(new TerrRun { name = bj.name + "_full", p = bj.lip - Fw(bj.yaw) * (12f + bj.runUp), yaw = bj.yaw, speed = 13.6f, stick = St(bj.yaw, 1f), stickSecs = 4f, secs = 6.5f });
                    if (bj.name == "BigJump0")
                        runs.Add(new TerrRun { name = bj.name + "_slow", p = bj.lip - Fw(bj.yaw) * 16f, yaw = bj.yaw, speed = 5f, stick = St(bj.yaw, 0.45f), stickSecs = 4f, secs = 6.5f });
                }
                // the narrow pass through the ridge
                runs.Add(new TerrRun { name = "ridge_pass", p = new Vector3(56f, 0f, -72f), yaw = 0f, speed = 9f, stick = St(0f, 0.75f), stickSecs = 4f, secs = 5.5f });
                // the big hill's crest at full speed
                var h0 = Terrain.Hills.Find(h => h.p.name == "Hill0a").p;
                runs.Add(new TerrRun { name = "hill_crest_full", p = h0.rect.Center - new Vector3(26f, 0f, 0f), yaw = 90f, speed = 13.6f, stick = St(90f, 1f), stickSecs = 3f, secs = 5.5f });
                // the jump down from the mesa's summit
                runs.Add(new TerrRun { name = "mesa_summit_jump", p = new Vector3(-86f, Terrain.MesaTop, 86f), yaw = 180f, speed = 10f, stick = St(180f, 0.85f), stickSecs = 3.5f, secs = 6.5f });
                // the second road hill
                var rh2 = Terrain.Hills.Find(h => h.p.name == "RoadHill0b").p;
                runs.Add(new TerrRun { name = "road_hill_b_full", p = rh2.rect.Center - rh2.rect.Forward * 22f, yaw = rh2.rect.Yaw, speed = 13.6f, stick = St(rh2.rect.Yaw, 1f), stickSecs = 4f, secs = 5.5f });
            }
        }

        // ------------------------------------------------------------------ mesa: the switchback road to the summit
        static int mesaWp = -1;
        static float mesaStageT;
        static bool mesaJumped;

        static Vector2 MesaInput(float t)
        {
            var pl = Game.I != null ? Game.I.player : null;
            if (pl == null || t < 1f || mesaWp < 0) return Vector2.zero;
            var route = Terrain.MesaRoute;
            if (mesaWp >= route.Length)
            {
                // on the summit: line up with the jump ramp, then full speed off it
                var target = mesaJumped ? pl.Pos : new Vector3(-86f, 0f, 60f);
                var to = target - pl.Pos; to.y = 0f;
                if (pl.Pos.z > 80f && Mathf.Abs(pl.Pos.x + 86f) > 1.5f) to = new Vector3(-86f, 0f, 82f) - pl.Pos;
                return mesaJumped ? Vector2.zero : CarDriver.TowardTarget(new Vector2(to.x, to.z).normalized * SpeedStick(0.9f), pl.Heading, pl.ForwardSpeed, pl.GearDirection);
            }
            var d = route[mesaWp] - pl.Pos; d.y = 0f;
            // slow into the hairpins, faster on the ramps; a waypoint behind: a three-point turn or a forward U-turn
            bool hairpin = mesaWp == 3 || mesaWp == 4 || mesaWp == 5 || mesaWp == 7 || mesaWp == 8 || mesaWp == 9 || mesaWp == 12;
            return CarDriver.TowardTarget(new Vector2(d.x, d.z).normalized * SpeedStick(hairpin ? 0.36f : 0.62f), pl.Heading, pl.ForwardSpeed, pl.GearDirection, d.magnitude);
        }

        static void MesaTick(Player pl, float t)
        {
            if (mesaWp < 0 && t > 1f)
            {
                mesaWp = 0;
                pl.Teleport(Terrain.MesaRoute[0] - new Vector3(0f, 0f, 8f), 0f);
                Game.I.cameraRig.Snap();
                mesaStageT = t;
                Debug.Log("RoadGame MESA start at " + pl.Pos);
            }
            if (mesaWp < 0) return;
            var route = Terrain.MesaRoute;
            if (mesaWp < route.Length)
            {
                var d = route[mesaWp] - pl.Pos; d.y = 0f;
                if (d.magnitude < 3.2f)
                {
                    Debug.Log($"RoadGame MESA waypoint {mesaWp} t={t - mesaStageT:0.0}s pos={pl.Pos} floor={pl.GroundY:0.00} piece={(pl.GroundPiece != null ? pl.GroundPiece.name : "ground")}");
                    mesaWp++;
                    if (mesaWp == route.Length) Debug.Log($"RoadGame MESA summit reached t={t - mesaStageT:0.0}s height={pl.Pos.y:0.00}");
                }
            }
            if (pl.Airborne && !runWasAir) { runWasAir = true; runTakeoffP = pl.Pos; runTakeoffT = t; runMaxY = pl.Pos.y; Debug.Log($"RoadGame MESA takeoff at={pl.Pos} v={pl.Speed:0.0} piece={(pl.GroundPiece != null ? pl.GroundPiece.name : "-")}"); }
            if (pl.Airborne) runMaxY = Mathf.Max(runMaxY, pl.Pos.y);
            if (!pl.Airborne && runWasAir)
            {
                runWasAir = false;
                var dd = pl.Pos - runTakeoffP; dd.y = 0f;
                if (mesaWp >= route.Length && runTakeoffP.y > Terrain.MesaTop - 0.5f) mesaJumped = true;
                Debug.Log($"RoadGame MESA land air={t - runTakeoffT:0.00}s dist={dd.magnitude:0.0} impact={pl.LastLandingImpact:0.0} kind={pl.LastLandingKind} at={pl.Pos}");
            }
        }

        // ------------------------------------------------------------------ tour of the new places (game camera)
        static readonly (Vector3 p, float yaw, float zoom, string name)[] TerrainStops =
        {
            (new Vector3(0f, 0f, -232f), 0f, 1f, "intro_start_wide"),
            (new Vector3(0f, 0f, -198f), 0f, 1.35f, "intro_straight_overview"),
            (new Vector3(0f, 0f, -152f), 0f, 1f, "intro_runup_arrows"),
            (new Vector3(0f, 0f, -128f), 0f, 1f, "intro_ramp"),
            (new Vector3(-46.5f, 0f, 44f), 0f, 1.5f, "mesa_foot"),
            (new Vector3(-50f, Terrain.MesaH1, 89f), 270f, 1f, "mesa_hairpin1"),
            (new Vector3(-54.5f, 4f, 66f), 180f, 1f, "mesa_ramp2"),
            (new Vector3(-63.5f, 7f, 76f), 0f, 1f, "mesa_ramp3"),
            (new Vector3(-82f, Terrain.MesaTop, 80f), 180f, 1.35f, "mesa_summit"),
            (new Vector3(-82f, 0f, 40f), 0f, 1.5f, "mesa_south_face"),
            (new Vector3(38f, 0f, -92f), 0f, 1.35f, "bigjump0_runup"),
            (new Vector3(56f, 0f, -62f), 0f, 1.2f, "ridge0_pass"),
            (new Vector3(57f, 0f, -100f), 0f, 1.2f, "bumps0a"),
            (new Vector3(22f, 0f, -94f), 20f, 1f, "kicker0a"),
            (new Vector3(70f, 0f, -98f), 0f, 1.3f, "hill0a"),
            (new Vector3(-10f, 0f, -70f), -38f, 1.2f, "road_hill0a"),
            (new Vector3(-28.5f, 0f, -30f), 9f, 1.2f, "road_hill0b"),
            (new Vector3(10f, 0f, 245f), 90f, 1.35f, "bigjump1"),
            (new Vector3(65f, 0f, 134f), 0f, 1.3f, "hill1a"),
            (new Vector3(50f, 0f, 404f), 0f, 1.3f, "ridge2"),
            (new Vector3(-30f, 0f, 515f), 0f, 1.35f, "bigjump3"),
        };

        static int terrainTourIndex = -1;

        static void TerrainTourTick(Player pl, double t)
        {
            int want = (int)((t - TourStart) / TourStep);
            if (want > terrainTourIndex && want < TerrainStops.Length)
            {
                terrainTourIndex = want;
                var st = TerrainStops[want];
                pl.Teleport(st.p, st.yaw);
                Game.I.cameraRig.zoom = st.zoom;
                Game.I.cameraRig.Snap();
                World.I.Tick();
                Debug.Log($"RoadGame TTOUR stop={want} {st.name} at {pl.Pos} floor={pl.GroundY:0.00}");
            }
        }
    }
}
