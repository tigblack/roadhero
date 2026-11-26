using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>Runs the real controller through dry/wet coast, restart, ford and both bridge crossings.</summary>
    public static partial class AutoCapture
    {
        [Serializable] class WaterDriveResult
        {
            public string name;
            public Vector3 start, end;
            public float elapsed, startSpeed, endSpeed, maxWetSpeed, maxWetReverseSpeed, maxDepth, maxImmersion, wetTime;
            public float maxWaterDragForce;
            public float remaining;
            public int entries, recoveries, splashBursts, sprayParticles, ripples;
            public bool reachedEnd, sawElevatedDeck, sawDryAfterWater;
        }

        [Serializable] class WaterReport
        {
            public bool editorMasterMuted;
            public List<string> checks = new List<string>();
            public List<string> failures = new List<string>();
            public List<WaterDriveResult> drives = new List<WaterDriveResult>();
        }

        static readonly float[] WaterStageStarts = { 1f, 2.2f, 3.4f, 8.2f, 22.2f, 32.2f, 42.2f, 47.2f };
        static readonly float[] WaterStageDurations = { 0.8f, 0.8f, 4f, 13.5f, 9.5f, 9.5f, 4f };
        static readonly string[] WaterStageNames = { "dry_coast", "channel_coast", "restart_in_channel", "ford_crossing", "main_bridge", "track_bridge", "reverse_in_channel" };
        static readonly Vector3 WaterFordCenter = new Vector3(-5.5f, 0f, -6f);
        static readonly Vector3 WaterFordAcross = new Vector3(0.9846645f, 0f, 0.1744588f);
        static readonly Vector3 WaterChannel = new Vector3(-22.0414f, 0f, 33.1791f);
        static WaterReport waterReport;
        static WaterDriveResult waterDrive;
        static Vector3[] waterPath;
        static Vector3[] waterDryPath;
        static RiverWaterFx waterFx;
        static Vector2 waterStick;
        static int waterStage, waterEntriesAtStart, waterRecoveries;
        static int waterSplashAtStart, waterSprayAtStart, waterRipplesAtStart;
        static float waterStageStart, waterLastTime, waterNextLog;
        static bool waterStageDone, waterSawWet;

        static void WaterSetup(Progress progress)
        {
            var data = progress.d;
            data.maxHp = data.hp = 1000000; data.regen = 10000; data.dmg[0] = 6;
            data.tutorialDone = true; data.introPending = false; data.unlockedZone = 3;
            var start = WaterFordCenter - WaterFordAcross * 17f;
            data.px = start.x; data.py = 0f; data.pz = start.z; data.heading = 80f;
            Game.ScriptedInput = t => waterStick;
            waterReport = new WaterReport();
            waterStage = -1; waterStick = Vector2.zero; waterDrive = null;
            waterStageDone = false; waterNextLog = 0f;
        }

        static bool WaterSelectDryCoast(Player player)
        {
            // Choose a level, clear corridor so gravity and prop contacts cannot explain the coast comparison.
            var candidates = new[] { new Vector3(0f,0f,-90f), new Vector3(0f,0f,-80f),
                new Vector3(-10f,0f,-80f), new Vector3(10f,0f,-80f), new Vector3(0f,0f,-65f),
                new Vector3(40f,0f,-70f), new Vector3(-40f,0f,-70f) };
            foreach (var candidate in candidates)
            {
                bool flat = true;
                for (int z = -3; z <= 11 && flat; z++)
                    for (int side = -1; side <= 1; side++)
                    {
                        var point = candidate + new Vector3(side * 1.3f, 0f, z);
                        var ground = Ground.Sample(point.x, point.z, 2f);
                        if (!ground.valid || Mathf.Abs(ground.h) > 0.02f || ground.normal.y < 0.999f ||
                            WaterPhysics.TryContact(new Vector3(point.x, ground.h, point.z), out _)) { flat = false; break; }
                    }
                if (!flat) continue;
                var obstacles = Physics.OverlapBox(candidate + new Vector3(0f,0.85f,4f),
                    new Vector3(1.35f,0.6f,7.5f), Quaternion.identity, Player.ObstacleMask, QueryTriggerInteraction.Ignore);
                foreach (var obstacle in obstacles)
                    if (!obstacle.transform.IsChildOf(player.transform)) { flat = false; break; }
                if (!flat) continue;
                waterDryPath = new[] { candidate, candidate + Vector3.forward * 8f };
                return true;
            }
            waterDryPath = new[] { candidates[0], candidates[0] + Vector3.forward * 8f };
            return false;
        }

        static void WaterCheck(bool ok, string message)
        {
            if (ok) waterReport.checks.Add(message); else waterReport.failures.Add(message);
            Debug.Log("RoadGame WATER_CHECK " + (ok ? "PASS " : "FAIL ") + message);
        }

        static Vector3 WaterBed(Vector3 point)
        {
            var ground = Ground.Sample(point.x, point.z, 0.2f);
            return new Vector3(point.x, ground.h, point.z);
        }

        static void WaterValidateVolume()
        {
            waterReport.editorMasterMuted = WorkAudioMute.Apply();
            WaterCheck(waterReport.editorMasterMuted, "work run is muted");
            WaterCheck(DustFlatsSurfaces.Active, "imported river is active");
            var ford = WaterBed(WaterFordCenter);
            var channel = WaterBed(WaterChannel);
            bool fordWet = WaterPhysics.TryContact(ford, out var fordContact);
            bool channelWet = WaterPhysics.TryContact(channel, out var channelContact);
            WaterCheck(fordWet && fordContact.depth > 0.04f && fordContact.depth < 0.15f,
                "ford has shallow water contact: " + fordContact.depth.ToString("0.000") + "m");
            WaterCheck(channelWet && channelContact.depth > 0.15f && channelContact.depth < 0.28f,
                "main channel has deeper water contact: " + channelContact.depth.ToString("0.000") + "m");
            WaterCheck(channelWet && fordWet && channelContact.wetness > fordContact.wetness,
                "channel immersion exceeds ford immersion");
            WaterCheck(!WaterPhysics.TryContact(WaterBed(WaterFordCenter - WaterFordAcross * 17f), out _),
                "dry river bank has no water contact");
            WaterCheck(!WaterPhysics.TryContact(new Vector3(channel.x, DustFlatsSurfaces.WaterLevel + 0.3f, channel.z), out _),
                "car above water does not receive underwater forces");
            WaterCheck(!WaterPhysics.TryContact(channel - Vector3.up * 0.25f, out _),
                "space below river bed is outside the water volume");
            WaterCheck(!WaterPhysics.TryContact(new Vector3(0f, -0.35f, 220f), out _),
                "other zones do not inherit first-zone water");
            for (int i = 0; i < DustFlatsSurfaces.BridgeCount; i++)
            {
                var path = DustFlatsSurfaces.GetBridgePath(i);
                var deck = path[path.Count / 2];
                WaterCheck(!WaterPhysics.TryContact(deck, out _), "bridge " + i + " deck is dry above the river");
            }
        }

        static Vector3[] WaterBridgeRoute(int index)
        {
            var source = DustFlatsSurfaces.GetBridgePath(index);
            if (source.Count < 2) return new[] { Vector3.zero, Vector3.forward };
            // The track bridge's six-metre bank extension crosses unrelated scenery. Start at its real foot.
            int prefix = index == 1 ? 0 : 1;
            var points = new Vector3[source.Count + prefix + 1];
            var entry = source[1] - source[0]; entry.y = 0f; entry.Normalize();
            var exit = source[source.Count - 1] - source[source.Count - 2]; exit.y = 0f; exit.Normalize();
            if (prefix > 0) points[0] = source[0] - entry * 6f;
            for (int i = 0; i < source.Count; i++) points[i + prefix] = source[i];
            points[points.Length - 1] = source[source.Count - 1] + exit * 6f;
            return points;
        }

        static Vector3[] WaterRoute(int stage)
        {
            if (stage == 0) return waterDryPath;
            if (stage == 1 || stage == 2 || stage == 6)
            {
                // Upriver avoids the bridge underside while measuring the actual water resistance.
                var along = new Vector3(-0.5684f, 0f, 0.8228f);
                return new[] { WaterChannel, WaterChannel + along * 25f };
            }
            if (stage == 3)
                return new[] { WaterFordCenter - WaterFordAcross * 17f, WaterFordCenter,
                    WaterFordCenter + WaterFordAcross * 17f };
            return WaterBridgeRoute(stage - 4);
        }

        static Vector2 WaterFollow(Vector3 position)
        {
            float best = float.PositiveInfinity, along = 0f;
            int segment = 0;
            for (int i = 0; i < waterPath.Length - 1; i++)
            {
                var delta = waterPath[i + 1] - waterPath[i]; delta.y = 0f;
                var from = position - waterPath[i]; from.y = 0f;
                float t = Mathf.Clamp01(Vector3.Dot(from, delta) / Mathf.Max(0.001f, delta.sqrMagnitude));
                float distance = (from - delta * t).sqrMagnitude;
                if (distance >= best) continue;
                best = distance; segment = i; along = t;
            }
            var target = Vector3.Lerp(waterPath[segment], waterPath[segment + 1], along);
            float remaining = 4.5f;
            for (int i = segment; i < waterPath.Length - 1; i++)
            {
                var delta = waterPath[i + 1] - target; delta.y = 0f;
                float distance = delta.magnitude;
                if (distance >= remaining) { target += delta / distance * remaining; break; }
                remaining -= distance; target = waterPath[i + 1];
            }
            var direction = target - position; direction.y = 0f;
            return direction.sqrMagnitude > 0.25f ? new Vector2(direction.x, direction.z).normalized * 0.85f : Vector2.zero;
        }

        static void WaterEndDrive(Player player)
        {
            if (waterDrive == null || waterStageDone) return;
            waterStageDone = true;
            waterDrive.end = player.Pos;
            waterDrive.elapsed = Game.I.SessionTime - waterStageStart;
            waterDrive.endSpeed = player.Speed;
            waterDrive.entries = player.WaterEntries - waterEntriesAtStart;
            waterDrive.recoveries = waterRecoveries;
            if (waterFx != null)
            {
                waterDrive.splashBursts = waterFx.SplashBursts - waterSplashAtStart;
                waterDrive.sprayParticles = waterFx.SprayParticles - waterSprayAtStart;
                waterDrive.ripples = waterFx.RipplesEmitted - waterRipplesAtStart;
            }
            var end = waterPath[waterPath.Length - 1];
            waterDrive.remaining = Vector2.Distance(new Vector2(end.x, end.z), new Vector2(player.Pos.x, player.Pos.z));
            waterReport.drives.Add(waterDrive);
            Debug.Log("RoadGame WATER_DRIVE " + JsonUtility.ToJson(waterDrive));
            WaterCheck(waterRecoveries == 0, waterDrive.name + " has no recovery or out-of-bounds reset");
            if (waterStage == 0 || waterStage == 4 || waterStage == 5)
            {
                WaterCheck(waterDrive.maxWaterDragForce == 0f, waterDrive.name + " receives no water drag");
                WaterCheck(waterFx != null && waterDrive.splashBursts == 0 && waterDrive.sprayParticles == 0 && waterDrive.ripples == 0,
                    waterDrive.name + " emits no water spray, splashes or ripples");
            }
            else
            {
                WaterCheck(waterDrive.maxWaterDragForce > 50f, waterDrive.name + " receives measurable water resistance");
                WaterCheck(waterFx != null && waterDrive.sprayParticles > 0 && waterDrive.ripples > 0,
                    waterDrive.name + " emits water spray and ripples");
            }
            if (waterStage == 0)
                WaterCheck(waterDrive.wetTime == 0f && waterDrive.maxImmersion == 0f, "dry coast remains outside water");
            else if (waterStage == 1)
            {
                WaterCheck(waterDrive.wetTime > 0.5f, "channel coast stays immersed during measurement");
                var dry = waterReport.drives.Find(d => d.name == "dry_coast");
                WaterCheck(dry != null && waterDrive.endSpeed < dry.endSpeed - 0.15f,
                    "water slows equal-input 10m/s coast more than dry ground: wet=" + waterDrive.endSpeed.ToString("0.00") +
                    " dry=" + (dry != null ? dry.endSpeed.ToString("0.00") : "missing"));
            }
            else if (waterStage == 2)
                WaterCheck(waterDrive.maxWetSpeed > 1.5f && Vector3.Distance(waterDrive.start, waterDrive.end) > 2f,
                    "car restarts and drives from rest in the main channel");
            else if (waterStage == 3)
            {
                WaterCheck(waterDrive.reachedEnd || waterDrive.remaining < 4f, "car traverses the shallow ford");
                WaterCheck(waterDrive.wetTime > 0.2f && waterDrive.maxDepth > 0.04f, "ford crossing physically enters water");
                WaterCheck(waterDrive.sawDryAfterWater && !player.InWater && player.WaterImmersion < 0.01f,
                    "water contact clears after driving onto the far bank");
                WaterCheck(waterDrive.splashBursts > 0, "ford entry or exit produces a splash burst");
            }
            else if (waterStage == 4 || waterStage == 5)
            {
                WaterCheck(waterDrive.reachedEnd || waterDrive.remaining < 4f, waterDrive.name + " is traversed");
                WaterCheck(waterDrive.sawElevatedDeck, waterDrive.name + " uses its elevated driving deck");
                WaterCheck(waterDrive.wetTime == 0f && waterDrive.maxImmersion == 0f && waterDrive.entries == 0,
                    waterDrive.name + " produces no submerged handling or splash entries");
            }
            else if (waterStage == 6)
                WaterCheck(waterDrive.wetTime > 0.5f && waterDrive.maxWetReverseSpeed > 0.35f &&
                    Vector3.Distance(waterDrive.start, waterDrive.end) > 0.5f,
                    "car engages reverse and moves from rest while submerged");
            waterStick = Vector2.zero;
        }

        static void WaterTick(Player player)
        {
            float time = Game.I.SessionTime;
            int next = -1;
            for (int i = 0; i < WaterStageStarts.Length; i++) if (time >= WaterStageStarts[i]) next = i;
            if (next != waterStage)
            {
                WaterEndDrive(player);
                waterStage = next;
                if (next < 0) return;
                if (next == 0)
                {
                    WaterValidateVolume();
                    WaterCheck(WaterSelectDryCoast(player), "dry coast corridor is level, dry and clear of props");
                    player.Recovered += () => waterRecoveries++;
                }
                if (next >= WaterStageNames.Length) { waterStick = Vector2.zero; waterDrive = null; return; }
                waterPath = WaterRoute(next);
                var direction = waterPath[1] - waterPath[0]; direction.y = 0f;
                if (next == 6) direction = -direction;
                player.Teleport(waterPath[0], Mathf.Atan2(direction.x, direction.z) * Mathf.Rad2Deg);
                float startSpeed = next <= 1 ? 10f : next == 2 || next == 6 ? 0f : 6.5f;
                player.SetSpeed(startSpeed);
                Game.I.cameraRig.Snap();
                waterDrive = new WaterDriveResult { name = WaterStageNames[next], start = player.Pos, startSpeed = startSpeed };
                waterStageStart = waterLastTime = time;
                waterStageDone = waterSawWet = false;
                waterRecoveries = 0; waterEntriesAtStart = player.WaterEntries;
                waterFx = player.GetComponent<RiverWaterFx>();
                waterSplashAtStart = waterFx != null ? waterFx.SplashBursts : 0;
                waterSprayAtStart = waterFx != null ? waterFx.SprayParticles : 0;
                waterRipplesAtStart = waterFx != null ? waterFx.RipplesEmitted : 0;
                waterStick = next <= 1 ? Vector2.zero : WaterFollow(player.Pos);
                Debug.Log("RoadGame WATER_STAGE " + waterDrive.name + " at=" + player.Pos);
            }
            if (waterStage < 0 || waterDrive == null || waterStageDone) return;
            float elapsed = time - waterStageStart;
            float deltaTime = Mathf.Max(0f, time - waterLastTime); waterLastTime = time;
            if (player.InWater)
            {
                waterSawWet = true; waterDrive.wetTime += deltaTime;
                waterDrive.maxWetSpeed = Mathf.Max(waterDrive.maxWetSpeed, player.Speed);
                if (player.Gear < 0) waterDrive.maxWetReverseSpeed = Mathf.Max(waterDrive.maxWetReverseSpeed, -player.ForwardSpeed);
            }
            else if (waterSawWet) waterDrive.sawDryAfterWater = true;
            waterDrive.maxDepth = Mathf.Max(waterDrive.maxDepth, player.WaterDepth);
            waterDrive.maxImmersion = Mathf.Max(waterDrive.maxImmersion, player.WaterImmersion);
            waterDrive.maxWaterDragForce = Mathf.Max(waterDrive.maxWaterDragForce, player.WaterDragForce);
            waterDrive.sawElevatedDeck |= !player.Airborne && player.GroundY > 0.75f;
            var end = waterPath[waterPath.Length - 1];
            if (Vector2.Distance(new Vector2(end.x, end.z), new Vector2(player.Pos.x, player.Pos.z)) < 3f)
                waterDrive.reachedEnd = true;
            waterStick = waterStage <= 1 || waterDrive.reachedEnd ? Vector2.zero : WaterFollow(player.Pos);
            if (time >= waterNextLog)
            {
                waterNextLog = time + 0.25f;
                Debug.Log($"RoadGame WATER_TELEMETRY stage={waterStage} t={time:0.00} pos={player.Pos} v={player.Speed:0.00} wet={player.InWater} depth={player.WaterDepth:0.000} immersion={player.WaterImmersion:0.000} entries={player.WaterEntries} floor={player.GroundY:0.000}");
            }
            if (elapsed >= WaterStageDurations[waterStage]) WaterEndDrive(player);
        }

        static void WaterFinish()
        {
            if (waterReport == null) return;
            if (Game.I != null && Game.I.player != null) WaterEndDrive(Game.I.player);
            WaterCheck(waterReport.drives.Count == WaterStageNames.Length, "all seven physical water/bridge runs completed");
            File.WriteAllText(Path.Combine(cfg.outDir, "water-checks.json"), JsonUtility.ToJson(waterReport, true));
            Debug.Log($"RoadGame WATER_RESULT checks={waterReport.checks.Count} failures={waterReport.failures.Count}");
        }

        [Serializable] class WaterDropReport
        {
            public WaterReport validation;
            public Vector3 release, landing, end;
            public float impact, maxHorizontalTravel, maxHorizontalSpeed, maxWetDepth;
            public int landings, recoveries, splashes, sprayParticles, ripples, landingDustParticles, maxTireDustParticles;
            public bool airborneObserved, submergedAfterLanding;
        }

        static WaterDropReport waterDrop;
        static bool waterDropStarted;
        static int waterDropLandings, waterDropSplashStart, waterDropSprayStart, waterDropRippleStart;
        static RiverWaterFx waterDropFx;

        static void WaterDropSetup(Progress progress)
        {
            WaterSetup(progress);
            progress.d.px = WaterChannel.x; progress.d.py = -0.44f; progress.d.pz = WaterChannel.z;
            waterDrop = new WaterDropReport { validation = waterReport };
            waterDropStarted = false;
        }

        static int WaterDropNearbyDust()
        {
            if (Game.I.fx == null) return 0;
            var puffs = Game.I.fx.transform.Find("Puffs");
            if (puffs == null) return 0;
            var system = puffs.GetComponent<ParticleSystem>();
            var particles = new ParticleSystem.Particle[system.main.maxParticles];
            int count = system.GetParticles(particles), nearby = 0;
            for (int i = 0; i < count; i++)
                if (Vector3.Distance(particles[i].position, Game.I.player.Pos) < 4f) nearby++;
            return nearby;
        }

        static void WaterDropTick(Player player)
        {
            if (!waterDropStarted)
            {
                if (Game.I.SessionTime < 1f) return;
                waterDropStarted = true;
                waterReport.editorMasterMuted = WorkAudioMute.Apply();
                WaterCheck(waterReport.editorMasterMuted, "vertical drop work run is muted");
                WaterCheck(DustFlatsSurfaces.Active, "vertical drop uses the imported river");
                player.Teleport(new Vector3(WaterChannel.x,-0.44f,WaterChannel.z), 0f);
                player.SetSpeed(0f);
                // Isolate landing particles from the car's own weapon puffs during this focused six-second run.
                if (player.turret != null) player.turret.enabled = false;
                if (player.harpooner != null) player.harpooner.enabled = false;
                foreach (var arm in player.arms) if (arm != null) arm.enabled = false;
                foreach (var system in player.GetComponentsInChildren<ParticleSystem>())
                    if (system.name == "Dust" || system.name == "TireSmoke") system.Clear();
                if (Game.I.fx != null)
                {
                    var puffs = Game.I.fx.transform.Find("Puffs");
                    if (puffs != null) puffs.GetComponent<ParticleSystem>().Clear();
                }
                waterDropFx = player.GetComponent<RiverWaterFx>();
                waterDropLandings = player.Landings;
                waterDropSplashStart = waterDropFx != null ? waterDropFx.SplashBursts : 0;
                waterDropSprayStart = waterDropFx != null ? waterDropFx.SprayParticles : 0;
                waterDropRippleStart = waterDropFx != null ? waterDropFx.RipplesEmitted : 0;
                player.Recovered += () => waterDrop.recoveries++;
                player.Landed += impact =>
                {
                    waterDrop.impact = impact;
                    waterDrop.landing = player.Pos;
                    waterDrop.landingDustParticles = Mathf.Max(waterDrop.landingDustParticles, WaterDropNearbyDust());
                };
                player.DebugDrop(2f);
                waterDrop.release = player.Pos;
                Game.I.cameraRig.Snap();
                Debug.Log("RoadGame WATER_DROP release=" + player.Pos);
            }
            waterDrop.airborneObserved |= player.Airborne;
            if (player.Landings > waterDropLandings && !player.Airborne && player.InWater)
                waterDrop.submergedAfterLanding = true;
            var distance = player.Pos - waterDrop.release; distance.y = 0f;
            waterDrop.maxHorizontalTravel = Mathf.Max(waterDrop.maxHorizontalTravel, distance.magnitude);
            waterDrop.maxHorizontalSpeed = Mathf.Max(waterDrop.maxHorizontalSpeed, player.Speed);
            waterDrop.maxWetDepth = Mathf.Max(waterDrop.maxWetDepth, player.WaterDepth);
            foreach (var system in player.GetComponentsInChildren<ParticleSystem>())
                if (system.name == "Dust" || system.name == "TireSmoke")
                    waterDrop.maxTireDustParticles = Mathf.Max(waterDrop.maxTireDustParticles, system.particleCount);
        }

        static void WaterDropFinish()
        {
            var player = Game.I != null ? Game.I.player : null;
            WaterCheck(waterDropStarted && player != null, "vertical drop was executed");
            if (player != null)
            {
                waterDrop.end = player.Pos;
                waterDrop.landings = player.Landings - waterDropLandings;
                waterDrop.splashes = waterDropFx != null ? waterDropFx.SplashBursts - waterDropSplashStart : 0;
                waterDrop.sprayParticles = waterDropFx != null ? waterDropFx.SprayParticles - waterDropSprayStart : 0;
                waterDrop.ripples = waterDropFx != null ? waterDropFx.RipplesEmitted - waterDropRippleStart : 0;
                WaterCheck(waterDrop.airborneObserved && waterDrop.landings > 0 && waterDrop.impact > 3f,
                    "car falls vertically and registers a physical landing");
                WaterCheck(waterDrop.submergedAfterLanding && player.InWater && waterDrop.maxWetDepth > 0.15f,
                    "car lands on the shallow channel bed and remains immersed");
                WaterCheck(waterDrop.splashes > 0 && waterDrop.sprayParticles > 0,
                    "vertical water impact produces a splash with zero commanded horizontal input");
                WaterCheck(waterDrop.ripples > 0, "vertical water impact produces expanding ripples");
                WaterCheck(waterDrop.maxHorizontalTravel < 0.5f && waterDrop.maxHorizontalSpeed < 0.5f,
                    "water landing has little horizontal motion");
                WaterCheck(waterDrop.recoveries == 0, "vertical water landing needs no recovery");
                WaterCheck(waterDrop.landingDustParticles == 0 && waterDrop.maxTireDustParticles == 0,
                    "water landing emits no sand puff or tire dust");
            }
            File.WriteAllText(Path.Combine(cfg.outDir,"waterdrop-checks.json"),JsonUtility.ToJson(waterDrop,true));
            Debug.Log($"RoadGame WATER_DROP_RESULT checks={waterReport.checks.Count} failures={waterReport.failures.Count}");
        }
    }
}
