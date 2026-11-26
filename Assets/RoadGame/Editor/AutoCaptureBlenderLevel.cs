using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>Exercises the actual car controller on the imported ford and both bridge decks.</summary>
    public static partial class AutoCapture
    {
        [Serializable]
        class BlenderLevelReport
        {
            public string source = "DustFlats_Level_v13_SmoothPass.blend";
            public bool editorMasterMuted;
            public List<string> checks = new List<string>();
            public List<string> failures = new List<string>();
            public List<string> drives = new List<string>();
        }

        static BlenderLevelReport blenderReport;
        static int blenderStage = -1;
        static float blenderStart, blenderNextLog;
        static Vector3[] blenderPath;
        static Vector3 blenderDriveStart;
        static float blenderMinY, blenderMaxY;
        static bool blenderSawRiver, blenderSawBridge;
        static int blenderRecovered;
        static Vector2 blenderStick;
        static bool blenderPropChecked;
        static bool blenderReachedEnd;
        static readonly float[] BlenderStageStarts = { 1f, 9f, 18f, 27f, 32f, 37f, 42f };
        static readonly string[] BlenderStageNames = { "ford_crossing", "main_bridge", "track_bridge", "garage", "hangar", "intro_ramp", "rust_canyon" };

        static void BlenderLevelSetup(Progress p)
        {
            var d = p.d;
            d.maxHp = d.hp = 1000000; d.regen = 10000; d.dmg[0] = 6;
            d.tutorialDone = true; d.introPending = false; d.unlockedZone = 3;
            d.px = -21.25f; d.py = 0f; d.pz = -8.79f; d.heading = 80f;
            Game.ScriptedInput = t => blenderStick;
            blenderReport = new BlenderLevelReport();
            blenderStage = -1; blenderStick = Vector2.zero;
            blenderPropChecked = false;
        }

        static void BlenderCheck(bool ok, string message)
        {
            if (ok) blenderReport.checks.Add(message);
            else blenderReport.failures.Add(message);
            Debug.Log("RoadGame BLENDER_CHECK " + (ok ? "PASS " : "FAIL ") + message);
        }

        static void BlenderValidateSurfaces()
        {
            blenderReport.editorMasterMuted = WorkAudioMute.Apply();
            BlenderCheck(blenderReport.editorMasterMuted, "work run is muted");
            BlenderCheck(DustFlatsSurfaces.Active, "imported river surfaces are active");
            BlenderCheck(ImportedLevel.Active != null && ImportedLevel.Active.Applied && ImportedLevel.Active.UnmappedOriginalCount == 0,
                "all imported source IDs resolve to their original gameplay objects");
            BlenderCheck(ImportedLevel.Active != null && ImportedLevel.Active.ReplacedStaticCount == 129 && ImportedLevel.Active.AddedStaticCount >= 100,
                "edited static geometry replaces the procedural first zone");
            var ford = Ground.Sample(-5.5f, -6f, 0.2f);
            BlenderCheck(ford.valid && ford.h < -0.26f && ford.h > -0.36f, "ford bed is drivable at approximately -0.31m: " + ford.h);
            var channel = Ground.Sample(-22.0414f, 33.1791f, 0.2f);
            BlenderCheck(channel.valid && channel.h < -0.37f && channel.h > -0.49f, "main channel bed is approximately -0.44m: " + channel.h);
            var bridge0 = Ground.Sample(-12.32f, 20.628f, 2f);
            BlenderCheck(bridge0.valid && bridge0.h > 1.0f && bridge0.h < 1.18f, "main bridge has a supported deck: " + bridge0.h);
            var bridge1 = Ground.Sample(26.544f, -35.539f, 2f);
            BlenderCheck(bridge1.valid && bridge1.h > 0.82f && bridge1.h < 1.0f, "track bridge has a supported deck: " + bridge1.h);
            BlenderCheck(!DustFlatsSurfaces.TrySampleBase(0f, 220f, out _, out _), "river does not modify other zones");
            int frozen = 0;
            foreach (var t in World.I.GetComponentsInChildren<Transform>(true))
                if (t.name.StartsWith("Spawn_00", StringComparison.Ordinal)) frozen++;
            BlenderCheck(frozen == 0, "no frozen spawn visuals duplicate live targets: " + frozen);
            BlenderCheck(World.I.spawns.Count > 600, "world progression spawns retained: " + World.I.spawns.Count);
        }

        static Vector3[] BlenderRoute(int stage)
        {
            if (stage == 0)
            {
                var c = new Vector3(-5.5f, 0, -6f);
                var across = new Vector3(0.9846645f, 0, 0.1744588f);
                return new[] { c - across * 17f, c, c + across * 17f };
            }
            if (stage == 1) return new[] {
                new Vector3(-25.5f,0,1.5f), new Vector3(-24.219f,0.041f,5.122f),
                new Vector3(-22.704f,0.443f,8.823f),new Vector3(-20.879f,1.021f,12.378f),
                new Vector3(-18.492f,1.091f,15.577f),new Vector3(-15.567f,1.091f,18.296f),
                new Vector3(-12.32f,1.091f,20.628f),new Vector3(-8.874f,1.091f,22.656f),
                new Vector3(-5.325f,1.091f,24.499f),new Vector3(-1.725f,0.683f,26.243f),
                new Vector3(2.777f,0.048f,28.418f),new Vector3(6.4f,0,30.2f)};
            if (stage == 2) return new[] {
                new Vector3(28.35f,0,-51.4f),new Vector3(27.896f,0.004f,-47.462f),
                new Vector3(26.995f,0.9f,-39.513f),new Vector3(26.093f,0.9f,-31.564f),
                new Vector3(25.191f,0.9f,-23.615f),new Vector3(24.402f,0.041f,-16.66f),
                new Vector3(23.95f,0,-12.7f)};
            if (stage == 3) return new[] { World.I.stations[0].pos + new Vector3(5f,0,-8f) };
            if (stage == 4) return new[] { World.I.bossSpawns[0].pos + new Vector3(6f,0,-12f) };
            if (stage == 5) return new[] { new Vector3(0,0,-143f) };
            return new[] { new Vector3(0f,0,Content.ZoneMinZ(1) + 45f) };
        }

        static Vector2 BlenderFollow(Vector3 pos)
        {
            float best = float.PositiveInfinity;
            int segment = 0; float along = 0;
            for (int i = 0; i < blenderPath.Length - 1; i++)
            {
                var a = blenderPath[i]; var d = blenderPath[i + 1] - a; d.y = 0;
                var v = pos - a; v.y = 0;
                float t = Mathf.Clamp01(Vector3.Dot(v,d) / Mathf.Max(0.001f,d.sqrMagnitude));
                var delta = v - d*t;
                if (delta.sqrMagnitude < best) { best = delta.sqrMagnitude; segment = i; along = t; }
            }
            Vector3 target = blenderPath[segment] + (blenderPath[segment+1] - blenderPath[segment])*along;
            float remaining = 4.5f;
            for (int i = segment; i < blenderPath.Length-1; i++)
            {
                var delta = blenderPath[i+1]-target; delta.y = 0;
                float length = delta.magnitude;
                if (length >= remaining) { target += delta/length*remaining; break; }
                remaining -= length; target = blenderPath[i+1];
            }
            var direction = target-pos; direction.y = 0;
            return direction.sqrMagnitude > 0.5f ? new Vector2(direction.x,direction.z).normalized * 0.65f : Vector2.zero;
        }

        static void BlenderEndDrive(Player pl)
        {
            if (blenderStage < 0 || blenderStage > 2) return;
            var end = blenderPath[blenderPath.Length-1];
            float remaining = Vector2.Distance(new Vector2(end.x,end.z),new Vector2(pl.Pos.x,pl.Pos.z));
            var summary = $"{BlenderStageNames[blenderStage]} start={blenderDriveStart} end={pl.Pos} remaining={remaining:0.00}m height=[{blenderMinY:0.00},{blenderMaxY:0.00}] recovered={blenderRecovered}";
            blenderReport.drives.Add(summary); Debug.Log("RoadGame BLENDER_DRIVE " + summary);
            BlenderCheck((blenderReachedEnd || remaining < 5f) && blenderRecovered == 0, BlenderStageNames[blenderStage] + " traversed with car controller");
            if (!blenderReachedEnd && remaining >= 5f)
            {
                var collisions = Physics.OverlapBox(pl.Pos + Vector3.up * 0.82f, new Vector3(1.18f, 0.6f, 2.6f),
                    Quaternion.Euler(0, pl.Heading, 0), Player.ObstacleMask, QueryTriggerInteraction.Ignore);
                foreach (var collider in collisions)
                {
                    var target = collider.GetComponentInParent<Target>();
                    string path = collider.name;
                    for (var parent = collider.transform.parent; parent != null; parent = parent.parent) path = parent.name + "/" + path;
                    Debug.Log("RoadGame BLENDER_OBSTACLE " + path + " bounds=" + collider.bounds +
                        " spawn=" + (target != null ? target.spawn.id.ToString() : "static"));
                }
            }
            if (blenderStage == 0) BlenderCheck(blenderSawRiver, "car wheels follow the submerged bed during ford crossing");
            else BlenderCheck(blenderSawBridge, "car wheels follow the elevated deck during bridge crossing");
        }

        static void BlenderLevelTick(Player pl)
        {
            float t = Game.I.SessionTime;
            int want = -1;
            for (int i = 0; i < BlenderStageStarts.Length; i++) if (t >= BlenderStageStarts[i]) want = i;
            if (want != blenderStage)
            {
                BlenderEndDrive(pl);
                blenderStage = want;
                if (want < 0) return;
                if (want == 0)
                {
                    BlenderValidateSurfaces();
                    pl.Recovered += () => blenderRecovered++;
                }
                blenderPath = BlenderRoute(want);
                var direction = blenderPath.Length > 1 ? blenderPath[1] - blenderPath[0] : Vector3.forward;
                float yaw = Mathf.Atan2(direction.x,direction.z)*Mathf.Rad2Deg;
                pl.Teleport(blenderPath[0],yaw); pl.SetSpeed(want <= 2 ? 6.5f : 0f);
                Game.I.cameraRig.Snap();
                blenderDriveStart = pl.Pos; blenderStart = t;
                blenderMinY = blenderMaxY = pl.Pos.y; blenderRecovered = 0;
                blenderSawRiver = blenderSawBridge = false;
                blenderReachedEnd = false;
                Debug.Log("RoadGame BLENDER_STAGE " + BlenderStageNames[want] + " at=" + pl.Pos);
            }
            if (blenderStage < 0) return;
            if (blenderStage <= 2)
            {
                var end = blenderPath[blenderPath.Length-1];
                if (Vector2.Distance(new Vector2(pl.Pos.x, pl.Pos.z), new Vector2(end.x, end.z)) < 3f)
                    blenderReachedEnd = true;
            }
            blenderStick = blenderStage <= 2 && !blenderReachedEnd ? BlenderFollow(pl.Pos) : Vector2.zero;
            blenderMinY = Mathf.Min(blenderMinY,pl.Pos.y); blenderMaxY = Mathf.Max(blenderMaxY,pl.Pos.y);
            if (!pl.Airborne && pl.GroundY < -0.22f) blenderSawRiver = true;
            if (!pl.Airborne && pl.GroundY > 0.75f) blenderSawBridge = true;
            if (t >= blenderNextLog)
            {
                blenderNextLog = t+0.5f;
                Debug.Log($"RoadGame BLENDER_TELEMETRY stage={blenderStage} t={t:0.00} pos={pl.Pos} floor={pl.GroundY:0.000} v={pl.Speed:0.00} air={pl.Airborne}");
            }
            if (blenderStage == 4 && t > blenderStart+2f && !blenderReport.checks.Exists(s=>s.StartsWith("hangar roof")))
            {
                bool faded = false;
                if (OcclusionFader.I != null) foreach (var o in OcclusionFader.I.All)
                    if (o.name.ToLowerInvariant().Contains("hangar") && o.alpha < 0.8f) faded = true;
                BlenderCheck(faded,"hangar roof still fades for the car");
            }
            if (blenderStage == 3 && t > blenderStart+1f && !blenderPropChecked)
            {
                blenderPropChecked = true;
                Target prop = null;
                foreach (var candidate in World.I.activeTargets)
                    if (candidate is Prop && candidate.zone.index == 0 && !candidate.dead &&
                        candidate.GetComponent("ImportedPropSurface") != null) { prop = candidate; break; }
                BlenderCheck(prop != null, "live destructible props use imported Blender geometry");
                if (prop != null)
                {
                    double before = prop.hp;
                    prop.Hit(1d, false, pl.Pos);
                    BlenderCheck(prop.hp < before && Time.time - prop.lastHitTime < 0.1f, "imported prop retains damage and hit feedback");
                    prop.Kill();
                    BlenderCheck(prop.dead && prop.hp == 0d && !prop.GetComponent<Collider>().enabled, "imported prop retains destruction and removes its blocker");
                    prop.ResetForSpawn(false);
                    BlenderCheck(!prop.dead && prop.hp == prop.maxHp && prop.GetComponent<Collider>().enabled, "imported prop retains respawn");
                }
                BlenderCheck(World.I.gates[0].open && !World.I.gates[0].barrier.gameObject.activeSelf, "gate animation/progression state retained");
            }
        }

        static void BlenderLevelFinish()
        {
            if (blenderReport == null) return;
            File.WriteAllText(Path.Combine(cfg.outDir,"integration-checks.json"),JsonUtility.ToJson(blenderReport,true));
            Debug.Log($"RoadGame BLENDER_RESULT checks={blenderReport.checks.Count} failures={blenderReport.failures.Count}");
        }
    }
}
