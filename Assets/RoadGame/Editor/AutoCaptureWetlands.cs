using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// Second zone (Toxic Wetlands) checks with the real game: game-camera stops across the zone, the Blender bundle's
    /// mapping, imported enemies / buggies / boss / props on live targets (and again after a respawn), hit feedback,
    /// and the drivable shallow water. Run: -captureScenario wetlands -captureTimes 4,8,... (session time).
    /// </summary>
    public static partial class AutoCapture
    {
        [Serializable]
        class WetlandsReport
        {
            public bool editorMasterMuted;
            public List<string> checks = new List<string>();
            public List<string> failures = new List<string>();
            public List<string> stops = new List<string>();
            public List<string> actors = new List<string>();
        }

        struct WetStop { public string name; public Vector3 p; public float yaw; public float zoom; }

        static readonly WetStop[] WetStops =
        {
            new WetStop { name = "01_entry_gate", p = new Vector3(22f, 0f, 112f), yaw = 0f, zoom = 1f },
            new WetStop { name = "02_camp_west", p = new Vector3(-44f, 0f, 160f), yaw = 270f, zoom = 1f },
            new WetStop { name = "03_pipe_tunnel", p = new Vector3(-14.5f, 0f, 170f), yaw = 0f, zoom = 1f },
            new WetStop { name = "04_underpass", p = new Vector3(8f, 0f, 196f), yaw = 90f, zoom = 1f },
            new WetStop { name = "05_camp_east", p = new Vector3(44f, 0f, 196f), yaw = 60f, zoom = 1f },
            new WetStop { name = "06_arena_approach", p = new Vector3(-15.6f, 0f, 236f), yaw = 0f, zoom = 1f },
            new WetStop { name = "07_arena_fight", p = new Vector3(-8f, 0f, 252f), yaw = 300f, zoom = 1f },
            new WetStop { name = "08_north_east", p = new Vector3(36f, 0f, 276f), yaw = 0f, zoom = 1f },
            new WetStop { name = "09_north_west", p = new Vector3(-62f, 0f, 252f), yaw = 0f, zoom = 1f },
            new WetStop { name = "10_camp_west_south", p = new Vector3(-40f, 0f, 228f), yaw = 270f, zoom = 1f },
        };
        public const float WetStopStep = 4f;

        static WetlandsReport wetReport;
        static int wetStop = -1;
        static bool wetChecked, wetRespawnChecked;

        static Vector2 wetStick;
        static bool wetDriveStarted, wetDriveDone;
        static float wetDriveMinFloor, wetDriveMaxDepth, wetDriveMinSpeedInWater = 99f;
        static int wetDriveWetFrames;

        /// <summary>Stop "11_ford": the car starts north of the big south-west pool and drives straight into it.</summary>
        static void WetlandsDrive(Player pl, float t)
        {
            float t0 = WetStopStep * WetStops.Length;
            if (t < t0) return;
            if (!wetDriveStarted)
            {
                wetDriveStarted = true;
                var g = Ground.Sample(-58f, 136f, 2f);
                pl.Teleport(new Vector3(-58f, g.valid ? g.h : 0f, 136f), 200f);
                pl.SetSpeed(5f);
                Game.I.cameraRig.Snap();
                wetDriveMinFloor = 9f; wetDriveMaxDepth = 0f; wetDriveWetFrames = 0;
                Debug.Log("RoadGame WETLANDS_STOP 11_ford drive from=" + pl.Pos);
            }
            if (t < t0 + 6f)
            {
                wetStick = new Vector2(-0.34f, -0.94f) * 0.7f;
                if (!pl.Airborne) wetDriveMinFloor = Mathf.Min(wetDriveMinFloor, pl.GroundY);
                if (pl.InWater) { wetDriveWetFrames++; wetDriveMaxDepth = Mathf.Max(wetDriveMaxDepth, pl.WaterDepth); wetDriveMinSpeedInWater = Mathf.Min(wetDriveMinSpeedInWater, pl.Speed); }
                return;
            }
            if (!wetDriveDone)
            {
                wetDriveDone = true;
                wetStick = Vector2.zero;
                string line = $"ford end={pl.Pos} minFloor={wetDriveMinFloor:0.000} wetFrames={wetDriveWetFrames} maxDepth={wetDriveMaxDepth:0.000} speedInWater>={wetDriveMinSpeedInWater:0.0}";
                wetReport.stops.Add(line);
                Debug.Log("RoadGame WETLANDS_DRIVE " + line);
                WetCheck(wetDriveWetFrames > 10 && wetDriveMinFloor < -0.2f, "the car fords the pool on its bed (wheels in water, floor below the water level)");
                WetCheck(wetDriveMaxDepth > 0.1f && wetDriveMaxDepth < 0.3f, $"ford depth stays shallow ({wetDriveMaxDepth:0.00} m)");
            }
        }

        static void WetlandsSetup(Progress p)
        {
            var d = p.d;
            d.maxHp = d.hp = 5000000; d.regen = 50000; d.dmg[0] = 20; d.weaponLevel[0] = 2;
            d.unlockedZone = 1; d.bossKills[0] = 1; d.tutorialDone = true; d.introPending = false;
            d.px = 22f; d.pz = 104f; d.heading = 0f;
            Game.ScriptedInput = t => wetStick;
            wetStick = Vector2.zero; wetDriveStarted = wetDriveDone = false; wetDriveMinSpeedInWater = 99f;
            wetReport = new WetlandsReport();
            wetStop = -1; wetChecked = wetRespawnChecked = false;
        }

        static void WetCheck(bool ok, string message)
        {
            if (ok) wetReport.checks.Add(message); else wetReport.failures.Add(message);
            Debug.Log("RoadGame WETLANDS_CHECK " + (ok ? "PASS " : "FAIL ") + message);
        }

        /// <summary>Renderers that draw a target and whether every one of them shows a Blender mesh (TW_ zone bundle, Mut_ mutants).</summary>
        static string ActorSummary(Target t, out bool allImported, out int drawn)
        {
            allImported = true; drawn = 0;
            var names = new List<string>();
            foreach (var r in t.GetComponentsInChildren<MeshRenderer>(true))
            {
                if (!r.enabled || !r.gameObject.activeInHierarchy) continue;
                drawn++;
                var f = r.GetComponent<MeshFilter>();
                string n = f != null && f.sharedMesh != null ? f.sharedMesh.name : "-";
                // props: the zone bundle (TW_); enemies, buggies and the boss: the mutant bundle (Mut_)
                if (!n.StartsWith("TW_", StringComparison.Ordinal) && !n.StartsWith("Mut_", StringComparison.Ordinal)) allImported = false;
                if (names.Count < 8) names.Add(r.name + ":" + n);
            }
            return string.Join(" ", names);
        }

        static void WetlandsTick(Player pl)
        {
            float t = Game.I.SessionTime;
            int want = Mathf.FloorToInt(t / WetStopStep);
            WetlandsDrive(pl, t);
            if (want != wetStop && want < WetStops.Length)
            {
                wetStop = want;
                var st = WetStops[want];
                var g = Ground.Sample(st.p.x, st.p.z, 2f);
                var pos = new Vector3(st.p.x, g.valid ? g.h : 0f, st.p.z);
                pl.Teleport(pos, st.yaw);
                pl.SetSpeed(0f);
                Game.I.cameraRig.zoom = st.zoom;
                Game.I.cameraRig.Snap();
                World.I.Tick();
                int active = 0, imported = 0;
                foreach (var a in World.I.activeTargets) if (a.zone.index == 1) { active++; if (a.GetComponent<ImportedActorSurface>() != null || a.GetComponent<ImportedPropSurface>() != null) imported++; }
                string line = $"{st.name} at={pos} floor={(g.valid ? g.h : float.NaN):0.000} activeZone1={active} importedZone1={imported}";
                wetReport.stops.Add(line);
                Debug.Log("RoadGame WETLANDS_STOP " + line);
            }
            if (!wetChecked && t > 1.5f)
            {
                wetChecked = true;
                wetReport.editorMasterMuted = WorkAudioMute.Apply();
                WetCheck(wetReport.editorMasterMuted, "work run is muted");
                var wet = ImportedLevel.Wetlands;
                WetCheck(wet != null && wet.Applied, "Toxic Wetlands bundle applied");
                if (wet != null)
                {
                    WetCheck(wet.UnmappedOriginalCount == 0, $"every snapshot ID of the second zone resolves (unmapped={wet.UnmappedOriginalCount})");
                    Debug.Log($"RoadGame WETLANDS bundle replaced={wet.ReplacedStaticCount} added={wet.AddedStaticCount} spawnTemplates={wet.ImportedPropCount}");
                }
                var dust = ImportedLevel.Active;
                WetCheck(dust != null && dust.Applied && dust.UnmappedOriginalCount == 0, "Dust Flats v13 bundle still applied, all IDs resolve");
                if (dust != null) WetCheck(dust.ReplacedStaticCount == 129 && dust.AddedStaticCount >= 100,
                    $"Dust Flats static counts unchanged (replaced={dust.ReplacedStaticCount}, added={dust.AddedStaticCount})");
                WetCheck(Content.Zones[1].index == 1, "second zone keeps index 1");
                WetCheck(WetlandSurfaces.Active, "swamp water surfaces are active");
                var bed = Ground.Sample(-62f, 124f, 1f);
                WetCheck(bed.valid && bed.h < -0.25f && bed.h > -0.35f, $"pool bed under (-62, 124) at {bed.h:0.000} m (water level {WetlandSurfaces.WaterLevel:0.00})");
                bool wetContact = WaterPhysics.TryContact(new Vector3(-62f, bed.h + 0.02f, 124f), out var wc);
                WetCheck(wetContact && wc.depth > 0.15f && wc.depth < 0.26f && Mathf.Abs(wc.level - WetlandSurfaces.WaterLevel) < 1e-4f,
                    $"a wheel on that bed is in {wc.depth:0.00} m of still water (level {wc.level:0.00}, flow {wc.flow.magnitude:0.00})");
                var island = Ground.Sample(-15.6f, 264f, 1f);
                WetCheck(island.valid && Mathf.Abs(island.h) < 1e-4f && !WaterPhysics.TryContact(new Vector3(-15.6f, -0.1f, 264f), out _),
                    "the arena island is dry, flat ground");
                int wetSpawns = 0, wetRoad = 0, roadPts = 0;
                foreach (var sp in World.I.zoneSpawns[1])
                {
                    var g = Ground.Sample(sp.pos.x, sp.pos.z, sp.pos.y + 0.5f);
                    if (g.valid && g.h < -0.002f && !g.Underground) { wetSpawns++; Debug.Log($"RoadGame WETLANDS spawn in water id={sp.id} at={sp.pos} h={g.h:0.000}"); }
                }
                foreach (var road in World.I.roads[1])
                    foreach (var pt in road)
                    {
                        roadPts++;
                        if (WetlandSurfaces.Height(pt.x, pt.z) < -0.002f) wetRoad++;
                    }
                WetCheck(wetSpawns == 0, $"every second-zone spawn stands on dry ground ({World.I.zoneSpawns[1].Count} spawns)");
                WetCheck(wetRoad == 0, $"every second-zone road point is dry ({roadPts} points, wet {wetRoad})");
                int movedSpawns = 0, movedByNew = 0;
                foreach (var sp in World.I.zoneSpawns[1])
                {
                    if (wet == null || !wet.TryGetSnapshotSpawn(sp.id, out var snap)) continue;
                    var d = new Vector2(sp.pos.x - snap.x, sp.pos.z - snap.z).magnitude;
                    if (d < 0.05f) continue;
                    movedSpawns++;
                    float r = Mathf.Max(0.4f, sp.spec.radius * sp.scale * (sp.spec.kind == TargetKind.Prop ? 0.85f : 0.75f));
                    var hits = Physics.OverlapCapsule(snap + Vector3.up * (0.3f + r), snap + Vector3.up * (1.3f + r), r, Player.ObstacleMask, QueryTriggerInteraction.Ignore);
                    var names = new List<string>();
                    foreach (var h in hits)
                    {
                        string path = h.name;
                        for (var up = h.transform.parent; up != null && names.Count < 6; up = up.parent) path = up.name + "/" + path;
                        names.Add(path);
                    }
                    bool byNew = names.Exists(n => n.Contains("BlenderCollision_TW") || n.Contains("/TW_"));
                    if (byNew) movedByNew++;
                    Debug.Log($"RoadGame WETLANDS spawn moved id={sp.id} {sp.spec.model} from={snap} to={sp.pos} by={d:0.0}m byNewGeometry={byNew} blockers=[{string.Join(", ", names)}]");
                }
                WetCheck(movedByNew == 0, $"no second-zone spawn moved away from the new swamp geometry (moved by new={movedByNew}; by generated colliders as before={movedSpawns - movedByNew})");
            }
            // per-stop actor audit (first time each model is seen)
            if (World.I != null)
                foreach (var a in World.I.activeTargets)
                {
                    if (a.zone.index != 1 || a.dead) continue;
                    string key = a.spec.model.ToString();
                    if (wetReport.actors.Exists(s => s.StartsWith(key + " "))) continue;
                    if (a.spec.kind == TargetKind.Prop && a.spec.model != ModelId.Barrels && a.spec.model != ModelId.Shack) continue;
                    string sum = ActorSummary(a, out bool all, out int drawn);
                    wetReport.actors.Add($"{key} spawn={a.spawn.id} drawn={drawn} imported={all} {sum}");
                    WetCheck(all && drawn > 0, $"{key} (spawn {a.spawn.id}) draws only Blender meshes ({drawn} renderers)");
                    if (a is Enemy && a.rig != null)
                        WetCheck(a.rig.CollectedImported(), $"{key} rig flashes imported surfaces with property blocks");
                }
            if (!wetRespawnChecked && t > WetStopStep * 2 + 2.5f)
            {
                wetRespawnChecked = true;
                Enemy victim = null;
                foreach (var a in World.I.activeTargets)
                    if (a is Enemy e && a.zone.index == 1 && !a.dead && a.spec.kind == TargetKind.Foot) { victim = e; break; }
                WetCheck(victim != null, "found a live second-zone foot enemy for the respawn check");
                if (victim != null)
                {
                    string before = ActorSummary(victim, out bool allBefore, out int drawnBefore);
                    victim.Hit(1d, false, pl.Pos);
                    victim.Kill();
                    WetCheck(victim.dead, $"{victim.spec.model} dies");
                    victim.ResetForSpawn(true);
                    string after = ActorSummary(victim, out bool allAfter, out int drawnAfter);
                    WetCheck(!victim.dead && allAfter && drawnAfter == drawnBefore && after == before,
                        $"respawned {victim.spec.model} (spawn {victim.spawn.id}) keeps the Blender meshes ({drawnAfter} renderers)");
                    Debug.Log("RoadGame WETLANDS respawn before=[" + before + "] after=[" + after + "]");
                }
            }
        }

        static void WetlandsFinish()
        {
            if (wetReport == null) return;
            File.WriteAllText(Path.Combine(cfg.outDir, "wetlands-checks.json"), JsonUtility.ToJson(wetReport, true));
            Debug.Log($"RoadGame WETLANDS_RESULT checks={wetReport.checks.Count} failures={wetReport.failures.Count}");
        }
    }
}
