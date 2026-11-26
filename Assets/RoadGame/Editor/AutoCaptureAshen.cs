using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// Third zone (Ashen Winter) with the real game: the Blender bundle and its mapping (all three zone bundles), the
    /// layout floors (raised arena deck and its ramps, the jump, the ravine), spawns clear of the new solids, the old
    /// canopy's colliders gone, game-camera stops across the zone, and drives with the real car: the jump over the
    /// ravine onto the pad, the bunker tunnel (its roof fades over the car), up the arena ramp onto the deck, into the
    /// parapet, across and down the far ramp, and into the deck's face from below.
    /// Run: -captureScenario ashenlevel -captureTimes 3.3,6.3,... (session time; drive shots are taken by the scenario).
    /// </summary>
    public static partial class AutoCapture
    {
        [Serializable]
        class AshenLevelReport
        {
            public bool editorMasterMuted;
            public List<string> checks = new List<string>();
            public List<string> failures = new List<string>();
            public List<string> stops = new List<string>();
            public List<string> drives = new List<string>();
        }

        struct AshStop { public string name; public Vector3 p; public float yaw; }

        static readonly AshStop[] AshStops =
        {
            new AshStop { name = "01_entry", p = new Vector3(-18f, 0f, 318f), yaw = 20f },
            new AshStop { name = "02_bunker_approach", p = new Vector3(3.5f, 0f, 349f), yaw = 0f },
            new AshStop { name = "03_bunker_inside", p = new Vector3(3f, 0f, 369f), yaw = 0f },
            new AshStop { name = "04_jump_runup", p = new Vector3(28f, 0f, 310f), yaw = 0f },
            new AshStop { name = "05_landing_pad", p = new Vector3(28f, 0f, 349f), yaw = 0f },
            new AshStop { name = "06_arena_ramp", p = new Vector3(9.7f, 0f, 428f), yaw = 0f },
            new AshStop { name = "07_arena_deck", p = new Vector3(8.4f, 1.2f, 452f), yaw = 0f },
            new AshStop { name = "08_arena_north", p = new Vector3(8.2f, 1.2f, 478f), yaw = 0f },
            new AshStop { name = "09_tower_workshop", p = new Vector3(-22f, 0f, 468f), yaw = 300f },
            new AshStop { name = "10_viaduct", p = new Vector3(-78f, 0f, 360f), yaw = 0f },
            new AshStop { name = "11_camp_east", p = new Vector3(55f, 0f, 372f), yaw = 0f },
            new AshStop { name = "12_pylons_north_east", p = new Vector3(62f, 0f, 462f), yaw = 0f },
        };
        public const float AshStopStep = 3f;
        static float AshDriveStart => AshStopStep * (AshStops.Length + 1);

        static AshenLevelReport ashReport;
        static int ashStop = -1, ashPhase = -1;
        static bool ashChecked;
        static Vector2 ashStick;
        static float ashPhaseT0;
        // drive measurements
        static bool ashAir, ashLanded, ashRecovered, ashShotA, ashShotB, ashShotC;
        static float ashTakeoffZ, ashLandZ, ashMaxAir, ashMinSpeed, ashMaxX, ashMinX, ashRoofMinAlpha, ashMaxFloor, ashMinFloor;
        static int ashFramesOnDeck;
        static Vector3 ashStartPos;

        static void AshenLevelSetup(Progress p)
        {
            var d = p.d;
            d.maxHp = d.hp = 5000000; d.regen = 50000; d.dmg[0] = 20; d.weaponLevel[0] = 2;
            d.unlockedZone = 2; d.bossKills[0] = 1; d.bossKills[1] = 1; d.tutorialDone = true; d.introPending = false;
            d.px = -18f; d.pz = 318f; d.heading = 20f;
            Game.ScriptedInput = t => ashStick;
            ashStick = Vector2.zero;
            ashReport = new AshenLevelReport();
            ashStop = -1; ashPhase = -1; ashChecked = false;
        }

        static void AshCheck(bool ok, string message)
        {
            if (ok) ashReport.checks.Add(message); else ashReport.failures.Add(message);
            Debug.Log("RoadGame ASHEN_CHECK " + (ok ? "PASS " : "FAIL ") + message);
        }

        static void AshShot(string label)
        {
            var g = Game.I;
            g.cam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            File.WriteAllBytes(Path.Combine(cfg.outDir, $"ashenlevel_{label}.png"), tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
            string line = $"{label} t={g.SessionTime:0.00} car={g.player.Pos} draws={UnityEditor.UnityStats.drawCalls} tris={UnityEditor.UnityStats.triangles} active={World.I.activeTargets.Count}";
            ashReport.stops.Add(line);
            Debug.Log("RoadGame ASHEN_SHOT " + line);
        }

        static void AshPlace(Player pl, Vector3 p, float yaw, float speed = 0f)
        {
            var g = Ground.Sample(p.x, p.z, p.y + 0.6f);
            pl.Teleport(new Vector3(p.x, g.valid ? g.h : p.y, p.z), yaw);
            pl.SetSpeed(speed);
            Game.I.cameraRig.zoom = 1f;
            Game.I.cameraRig.Snap();
            World.I.Tick();
        }

        static Occluder AshOccluder(string name)
        {
            if (OcclusionFader.I == null) return null;
            foreach (var o in OcclusionFader.I.All) if (o.name == name) return o;
            return null;
        }

        static void AshenLevelTick(Player pl)
        {
            float t = Game.I.SessionTime;
            if (!ashChecked && t > 1.5f) AshGlobalChecks(pl);
            int want = Mathf.FloorToInt(t / AshStopStep) - 1;
            if (want >= 0 && want != ashStop && want < AshStops.Length)
            {
                ashStop = want;
                var st = AshStops[want];
                ashStick = Vector2.zero;
                AshPlace(pl, st.p, st.yaw);
                int active = 0, imported = 0;
                foreach (var a in World.I.activeTargets)
                    if (a.zone.index == 2) { active++; if (a.GetComponent<ImportedActorSurface>() != null || a.GetComponent<ImportedPropSurface>() != null) imported++; }
                string line = $"{st.name} at={pl.Pos} floor={pl.GroundY:0.000} activeZone2={active} imported={imported}";
                ashReport.stops.Add(line);
                Debug.Log("RoadGame ASHEN_STOP " + line);
                if (st.name == "03_bunker_inside")
                {
                    var roof = AshOccluder("AW_Bunker_Roof");
                    AshCheck(roof != null, "the bunker's roof is a registered occluder (fades over the car)");
                }
            }
            if (t >= AshDriveStart) AshDrives(pl, t);
        }

        static void AshGlobalChecks(Player pl)
        {
            ashChecked = true;
            ashReport.editorMasterMuted = WorkAudioMute.Apply();
            AshCheck(ashReport.editorMasterMuted, "work run is muted");
            var ash = ImportedLevel.Ashen;
            AshCheck(ash != null && ash.Applied && ash.Zone == 2, "Ashen Winter bundle applied as the third zone's (zone index 2)");
            if (ash != null) AshCheck(ash.UnmappedOriginalCount == 0, $"every snapshot ID of the third zone resolves (unmapped={ash.UnmappedOriginalCount}, replaced={ash.ReplacedStaticCount}, added={ash.AddedStaticCount})");
            var dust = ImportedLevel.Active;
            AshCheck(dust != null && dust.Applied && dust.Zone == 0 && dust.UnmappedOriginalCount == 0 && dust.ReplacedStaticCount == 129,
                $"Dust Flats bundle still the first zone's, all IDs resolve (replaced={(dust != null ? dust.ReplacedStaticCount : -1)})");
            var wet = ImportedLevel.Wetlands;
            AshCheck(wet != null && wet.Applied && wet.Zone == 1 && wet.UnmappedOriginalCount == 0 && wet.ReplacedStaticCount == 62,
                $"Toxic Wetlands bundle still the second zone's, all IDs resolve (replaced={(wet != null ? wet.ReplacedStaticCount : -1)})");
            AshCheck(ImportedLevel.ForZone(0) == dust && ImportedLevel.ForZone(1) == wet && ImportedLevel.ForZone(2) == ash && ImportedLevel.ForZone(3) == null,
                "ForZone maps 0 / 1 / 2 to their own bundles, the fourth zone to none");
            AshCheck(Content.Zones[2].name == "ASHEN WINTER" && Content.ZoneCount == 4, "the third zone is ASHEN WINTER, still four zones");
            AshCheck(AshenSurfaces.Active && AshenSurfaces.DeckFloor != null && AshenSurfaces.JumpFloor != null && AshenSurfaces.RampFloors.Count == 2,
                "Ashen Winter floors: the arena deck, its two ramps and the jump");
            var L = AshenSurfaces.Data;
            if (L != null)
            {
                var c = new Vector3(L.arena.x, 0f, L.arena.z);
                var top = Ground.Sample(c.x, c.z, L.arena.height + 0.3f);
                var under = Ground.Sample(c.x + L.arena.radius + 1.5f, c.z, 0.3f);
                AshCheck(top.valid && Mathf.Abs(top.h - L.arena.height) < 1e-3f && top.piece == AshenSurfaces.DeckFloor, $"the arena deck is {top.h:0.00} m high");
                AshCheck(under.valid && Mathf.Abs(under.h) < 1e-3f, "outside the deck the valley floor is at 0");
                foreach (var rp in AshenSurfaces.RampFloors)
                {
                    float lo = rp.HeightLocal(-rp.rect.half.y), hi = rp.HeightLocal(rp.rect.half.y);
                    var midW = rp.rect.World(0f, 0f, 0f);
                    var mid = Ground.Sample(midW.x, midW.z, 1.0f);
                    AshCheck(Mathf.Abs(lo) < 1e-3f && Mathf.Abs(hi - L.arena.height) < 1e-3f && mid.valid && mid.h > 0.3f && mid.h < 0.9f,
                        $"arena ramp at {rp.rect.Center} rises 0 -> {hi:0.00} m (middle {mid.h:0.00})");
                }
                var j = AshenSurfaces.JumpFloor;
                AshCheck(j.launch && Mathf.Abs(j.h1 - L.jump.height) < 1e-3f && j.boost > 10f, $"jump ramp: launch floor {j.h1:0.0} m, boost {j.boost:0.0}");
                var rv = Ground.Sample(28f, 335.5f, 0.3f);
                AshCheck(rv.valid && rv.h < -0.6f && rv.h > -0.95f, $"the ravine under the jump dips to {rv.h:0.00} m");
                var boss = World.I.bossSpawns[2];
                AshCheck(boss != null && Mathf.Abs(boss.pos.y - L.arena.height) < 1e-3f, $"the boss stands on the deck (spawn y {(boss != null ? boss.pos.y : -1):0.00})");
            }
            // the old canopy's posts are gone (the bunker's tunnel walls stand there)
            int canopyOn = 0, canopyAll = 0;
            foreach (var c in World.I.GetComponentsInChildren<Collider>(true))
                if (c.name == "CanopyPost") { canopyAll++; if (c.enabled) canopyOn++; }
            AshCheck(canopyAll > 0 && canopyOn == 0, $"old canopy colliders off ({canopyAll - canopyOn}/{canopyAll})");
            // spawns: IDs unchanged, none inside a new solid
            int z2 = 0, blocked = 0, differ = 0;
            foreach (var sp in World.I.zoneSpawns[2])
            {
                z2++;
                if (sp.spec.kind == TargetKind.Boss) continue;
                float r = Mathf.Max(0.4f, sp.spec.radius * sp.scale * (sp.spec.kind == TargetKind.Prop ? 0.85f : 0.75f));
                // colliders of the level only (live targets carry their own colliders)
                var hits = Physics.OverlapCapsule(sp.pos + Vector3.up * (0.3f + r), sp.pos + Vector3.up * (1.3f + r), r, Player.ObstacleMask, QueryTriggerInteraction.Ignore);
                foreach (var h in hits)
                    if (h.GetComponentInParent<Target>() == null && h.attachedRigidbody == null)
                    {
                        blocked++;
                        Debug.Log($"RoadGame ASHEN spawn blocked id={sp.id} {sp.spec.model} at={sp.pos} by={h.name}/{(h.transform.parent != null ? h.transform.parent.name : "-")}");
                        break;
                    }
                if (ash != null && ash.TryGetSnapshotSpawn(sp.id, out var snap) && new Vector2(sp.pos.x - snap.x, sp.pos.z - snap.z).magnitude > 0.05f) differ++;
            }
            AshCheck(z2 == 187, $"third zone keeps its 187 spawns ({z2})");
            AshCheck(blocked == 0, $"no third-zone spawn stands inside a collider ({blocked})");
            AshCheck(differ <= 25, $"only the spawns that stood in a new structure moved ({differ}, IDs kept)");
            // the zone's repair pad (respawn and DEV arrival): no level solid on it or next to it
            foreach (var st in World.I.stations)
            {
                if (st.zone != 2) continue;
                int onPad = 0;
                foreach (var h in Physics.OverlapCapsule(st.pos + Vector3.up * 0.8f, st.pos + Vector3.up * 2.5f, 9f, Player.ObstacleMask, QueryTriggerInteraction.Ignore))
                    if (h.name.StartsWith("BlenderCollision_", StringComparison.Ordinal))
                    {
                        onPad++;
                        Debug.Log($"RoadGame ASHEN pad blocked by {h.name}/{(h.transform.parent != null ? h.transform.parent.name : "-")} at {h.bounds.center}");
                    }
                AshCheck(onPad == 0, $"the repair pad at {st.pos} is clear of level solids within 9 m ({onPad})");
            }
            // every live prop / creature of the zone draws the new art
            int props = 0, propsArt = 0, foes = 0, foesArt = 0;
            foreach (var a in World.I.activeTargets)
            {
                if (a.zone.index != 2 || a.dead) continue;
                bool art = true;
                foreach (var mr in a.GetComponentsInChildren<MeshRenderer>(false))
                {
                    var f = mr.GetComponent<MeshFilter>();
                    string n = f != null && f.sharedMesh != null ? f.sharedMesh.name : "-";
                    if (mr.enabled && !n.StartsWith("AW_", StringComparison.Ordinal)) art = false;
                }
                if (a.spec.kind == TargetKind.Prop) { props++; if (art) propsArt++; } else { foes++; if (art) foesArt++; }
            }
            AshCheck(props > 0 && propsArt == props, $"live third-zone props draw the Ashen Winter meshes ({propsArt}/{props})");
            AshCheck(foes == 0 || foesArt == foes, $"live third-zone enemies draw the Ashen Winter creatures ({foesArt}/{foes})");
        }

        static void AshDrives(Player pl, float t)
        {
            float s = t - AshDriveStart;
            int phase = s < 7f ? 0 : s < 13f ? 1 : s < 22f ? 2 : s < 26f ? 3 : s < 31f ? 4 : 5;
            if (phase != ashPhase)
            {
                if (ashPhase >= 0) AshEndPhase(pl, ashPhase);
                ashPhase = phase;
                ashPhaseT0 = t;
                ashAir = ashLanded = ashRecovered = ashShotA = ashShotB = ashShotC = false;
                ashMaxAir = 0f; ashMinSpeed = 99f; ashMaxX = -999f; ashMinX = 999f; ashRoofMinAlpha = 1f; ashMaxFloor = -9f; ashMinFloor = 9f;
                ashFramesOnDeck = 0; ashTakeoffZ = ashLandZ = 0f;
                pl.Landed -= AshOnLanded; pl.Landed += AshOnLanded;
                pl.Recovered -= AshOnRecovered; pl.Recovered += AshOnRecovered;
                switch (phase)
                {
                    case 0: AshPlace(pl, new Vector3(28f, 0f, 307.5f), 0f, 12f); ashStick = new Vector2(0f, 1f); break;             // the jump
                    case 1:                                                                                                           // the tunnel
                        {
                            var b = AshenSurfaces.Data.bunker;
                            float a = b.yaw * Mathf.Deg2Rad;
                            var start = new Vector3(b.x + Mathf.Sin(a) * (352f - b.z), 0f, 352f);
                            AshPlace(pl, start, b.yaw, 8f);
                            ashStick = new Vector2(Mathf.Sin(a), Mathf.Cos(a));
                            break;
                        }
                    case 2:                                                                                                           // the arena
                        var boss = World.I.bossSpawns[2];
                        if (boss != null && boss.target != null && boss.target.gameObject.activeSelf) boss.target.gameObject.SetActive(false);
                        {
                            var rp = AshenSurfaces.RampFloors[0];
                            foreach (var r in AshenSurfaces.RampFloors) if (r.rect.Center.z < rp.rect.Center.z) rp = r;
                            var start = rp.rect.World(0f, -rp.rect.half.y - 3f, 0f);
                            AshPlace(pl, start, rp.rect.Yaw, 6f);
                            var f = rp.rect.Forward;
                            ashStick = new Vector2(f.x, f.z);
                            break;
                        }
                    case 3: AshPlace(pl, new Vector3(8.4f, 1.2f, 464f), 90f, 4f); ashStick = new Vector2(1f, 0f); break;              // into the parapet
                    case 4: AshPlace(pl, new Vector3(44f, 0f, 464f), 270f, 4f); ashStick = new Vector2(-1f, 0f); break;              // into the face from below
                    default: ashStick = Vector2.zero; break;
                }
                ashStartPos = pl.Pos;
                Debug.Log($"RoadGame ASHEN_DRIVE start phase={phase} at={pl.Pos}");
            }
            float u = t - ashPhaseT0;
            var p = pl.Pos;
            if (!pl.Airborne) { ashMaxFloor = Mathf.Max(ashMaxFloor, pl.GroundY); ashMinFloor = Mathf.Min(ashMinFloor, pl.GroundY); }
            switch (phase)
            {
                case 0:
                    if (pl.Airborne && !ashAir && p.z > 322f) { ashAir = true; ashTakeoffZ = p.z; }
                    if (ashAir) ashMaxAir = Mathf.Max(ashMaxAir, pl.MaxAirHeight);
                    if (!ashShotA && ashAir && p.z > 333f) { ashShotA = true; AshShot("drive_jump_flight"); }
                    if (!ashShotB && ashLanded && u > 0.2f) { ashShotB = true; AshShot("drive_jump_landed"); }
                    if (u > 4.5f) ashStick = Vector2.zero;
                    break;
                case 1:
                    if (p.z > 359f && p.z < 379f)
                    {
                        ashMinSpeed = Mathf.Min(ashMinSpeed, pl.Speed);
                        ashMaxX = Mathf.Max(ashMaxX, p.x); ashMinX = Mathf.Min(ashMinX, p.x);
                        var roof = AshOccluder("AW_Bunker_Roof");
                        if (roof != null) ashRoofMinAlpha = Mathf.Min(ashRoofMinAlpha, roof.alpha);
                        if (!ashShotA && p.z > 368f) { ashShotA = true; AshShot("drive_tunnel_inside"); }
                    }
                    if (p.z > 384f) ashStick = Vector2.zero;
                    break;
                case 2:
                    if (Mathf.Abs(pl.GroundY - 1.2f) < 0.05f && !pl.Airborne) ashFramesOnDeck++;
                    if (!ashShotA && p.z > 436f && pl.GroundY > 0.4f) { ashShotA = true; AshShot("drive_arena_ramp_up"); }
                    if (!ashShotB && p.z > 458f) { ashShotB = true; AshShot("drive_arena_deck"); }
                    if (!ashShotC && p.z > 490f) { ashShotC = true; AshShot("drive_arena_ramp_down"); }
                    if (p.z > 498f) ashStick = Vector2.zero;
                    break;
                case 3:
                    ashMaxX = Mathf.Max(ashMaxX, p.x);
                    if (!ashShotA && u > 2.5f) { ashShotA = true; AshShot("drive_arena_parapet"); }
                    break;
                case 4:
                    ashMinX = Mathf.Min(ashMinX, p.x);
                    if (!ashShotA && u > 3.0f) { ashShotA = true; AshShot("drive_arena_face"); }
                    break;
            }
        }

        static void AshOnLanded(float impact)
        {
            if (ashPhase == 0 && ashAir && !ashLanded)
            {
                ashLanded = true;
                ashLandZ = Game.I.player.Pos.z;
                Debug.Log($"RoadGame ASHEN jump landed z={ashLandZ:0.0} impact={impact:0.0}");
            }
        }

        static void AshOnRecovered() { ashRecovered = true; }

        static void AshEndPhase(Player pl, int phase)
        {
            var L = AshenSurfaces.Data;
            string line;
            switch (phase)
            {
                case 0:
                    line = $"jump takeoffZ={ashTakeoffZ:0.0} maxAir={ashMaxAir:0.00} landZ={ashLandZ:0.0} landed={ashLanded} recovered={ashRecovered} end={pl.Pos}";
                    AshCheck(ashAir && ashTakeoffZ > 326f && ashTakeoffZ < 333f, $"the car takes off at the jump's lip (z {ashTakeoffZ:0.0})");
                    AshCheck(ashLanded && ashLandZ > 337f && ashLandZ < 362f, $"it clears the ravine and lands on the pad side (z {ashLandZ:0.0}, air {ashMaxAir:0.0} m)");
                    AshCheck(!ashRecovered && pl.Alive, "no recovery teleport, the car is fine after the jump");
                    break;
                case 1:
                    line = $"tunnel minSpeed={ashMinSpeed:0.0} x={ashMinX:0.0}..{ashMaxX:0.0} roofMinAlpha={ashRoofMinAlpha:0.00} end={pl.Pos}";
                    AshCheck(pl.Pos.z > 380f && ashMinSpeed > 3f, $"the car drives through the bunker without hitting it (min speed {ashMinSpeed:0.0}, end z {pl.Pos.z:0.0})");
                    AshCheck(ashRoofMinAlpha < 0.6f, $"the bunker roof fades over the car (min alpha {ashRoofMinAlpha:0.00})");
                    break;
                case 2:
                    line = $"arena framesOnDeck={ashFramesOnDeck} maxFloor={ashMaxFloor:0.00} end={pl.Pos} recovered={ashRecovered}";
                    AshCheck(ashFramesOnDeck > 20 && Mathf.Abs(ashMaxFloor - 1.2f) < 0.05f, $"up the ramp onto the deck ({ashFramesOnDeck} frames at 1.2 m)");
                    AshCheck(pl.Pos.z > 492f && pl.GroundY < 0.3f && !ashRecovered, $"across the deck and down the north ramp (end {pl.Pos}, floor {pl.GroundY:0.00})");
                    break;
                case 3:
                    line = $"parapet maxX={ashMaxX:0.0} floor={pl.GroundY:0.00} end={pl.Pos}";
                    AshCheck(L == null || (ashMaxX < L.arena.x + L.arena.radius - 0.2f && Mathf.Abs(pl.GroundY - 1.2f) < 0.05f),
                        $"the parapet keeps the car on the deck (max x {ashMaxX:0.0}, floor {pl.GroundY:0.00})");
                    break;
                case 4:
                    line = $"face minX={ashMinX:0.0} floor={pl.GroundY:0.00} end={pl.Pos}";
                    AshCheck(L == null || (ashMinX > L.arena.x + L.arena.radius + 0.2f && pl.GroundY < 0.05f),
                        $"the deck's face stops a car below (min x {ashMinX:0.0}, floor {pl.GroundY:0.00})");
                    break;
                default:
                    line = "end";
                    break;
            }
            ashReport.drives.Add(line);
            Debug.Log("RoadGame ASHEN_DRIVE " + line);
        }

        static void AshenLevelFinish()
        {
            if (ashReport == null) return;
            if (ashPhase >= 0 && ashPhase < 5) AshEndPhase(Game.I.player, ashPhase);
            File.WriteAllText(Path.Combine(cfg.outDir, "ashenlevel-checks.json"), JsonUtility.ToJson(ashReport, true));
            Debug.Log($"RoadGame ASHEN_RESULT checks={ashReport.checks.Count} failures={ashReport.failures.Count}");
        }
    }
}
