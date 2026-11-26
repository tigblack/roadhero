using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// The creature zones in the real game: second-zone mutants (ArtSource/Characters/ToxicWetlandsMutants, scenario
    /// 'mutants') or the third zone's Ashen Winter enemies (ArtSource/Characters/AshenWinterEnemies, scenario 'ashen').
    /// One stop per enemy type next to a live spawn (game-camera shots while it approaches and attacks, structure
    /// checks, hit flash, death, harpoon, respawn), then the boss fight (blow, slam special, kill -> rewards + next zone),
    /// a camp perf stop.
    /// Run: -captureScenario mutants|ashen -captureTimes 92 (session time; the scenario takes its own labelled shots).
    /// </summary>
    public static partial class AutoCapture
    {
        [Serializable]
        class MutantsReport
        {
            public bool editorMasterMuted;
            public List<string> checks = new List<string>();
            public List<string> failures = new List<string>();
            public List<string> creatures = new List<string>();
            public List<string> shots = new List<string>();
        }

        static readonly ModelId[] MutModels = { ModelId.Scav, ModelId.Raider, ModelId.Spearman, ModelId.Crossbow, ModelId.Brute, ModelId.Buggy };
        const float MutStop = 10f, MutStart = 2.5f;
        static MutantsReport mutReport;
        static int mutStop = -1;
        static float mutStopT0;
        static Enemy mutTarget;
        static SpawnPoint mutSpawn;
        static bool mutGlobalDone, mutShotApproach, mutShotAttack, mutShotAttack2, mutHitDone, mutKillDone, mutDeathShot, mutReelDone, mutRespawnDone, mutPerfDone;
        static int mutRenderersBefore, mutReeledBefore, mutStrikesBefore;
        static float mutKillT, mutMaxGroundErr;
        static string mutPartsBefore = "";
        // boss phase
        static Enemy mutBoss;
        static bool mutBossPlaced, mutBossKilled, mutBossShotStomp, mutBossShotSlam, mutBossShotDeath, mutBossShotApproach, mutBossReel;
        static double mutMaxHpBefore;
        static int mutBossSpecials;
        static float mutBossKillT;
        static long mutGemsBefore;

        static float MutBossStart => MutStart + MutStop * MutModels.Length;
        /// <summary>The zone under test: 1 = swamp mutants, 2 = Ashen Winter.</summary>
        static int mutZone = 1;
        static string MutPrefix => mutZone == 2 ? "ashen" : "mutants";
        static ModelId MutBossModel => mutZone == 2 ? ModelId.BossColossus : ModelId.BossBaron;
        static string MutBossTag => mutZone == 2 ? "07_BossColossus" : "07_BossBaron";
        static string MutBossName => mutZone == 2 ? "the Black Reactor" : "the Mire Mother";

        static void MutantsSetup(Progress p, int zone = 1)
        {
            mutZone = zone;
            var d = p.d;
            d.maxHp = d.hp = 5000000; d.regen = 50000; d.dmg[0] = 0.01; d.weaponLevel[0] = 1;
            d.unlockedZone = zone; d.tutorialDone = true; d.introPending = false;
            for (int z = 0; z < zone; z++) d.bossKills[z] = 1;
            if (zone == 2) { d.px = -11f; d.pz = 318f; } else { d.px = 22f; d.pz = 104f; }
            d.heading = 0f;
            Game.ScriptedInput = t => Vector2.zero;
            mutReport = new MutantsReport();
            mutStop = -1; mutGlobalDone = false; mutBossPlaced = mutBossKilled = false;
            mutBossShotStomp = mutBossShotSlam = mutBossShotDeath = mutBossShotApproach = mutBossReel = false;
            mutBossSpecials = 0; mutPerfDone = false;
        }

        static void MutCheck(bool ok, string message)
        {
            if (ok) mutReport.checks.Add(message); else mutReport.failures.Add(message);
            Debug.Log("RoadGame MUTANTS_CHECK " + (ok ? "PASS " : "FAIL ") + message);
        }

        static void MutShot(string label)
        {
            var g = Game.I;
            g.cam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            File.WriteAllBytes(Path.Combine(cfg.outDir, $"{MutPrefix}_{label}.png"), tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
            string line = $"{label} t={g.SessionTime:0.00} draws={UnityEditor.UnityStats.drawCalls} setpass={UnityEditor.UnityStats.setPassCalls} tris={UnityEditor.UnityStats.triangles} active={World.I.activeTargets.Count}";
            mutReport.shots.Add(line);
            Debug.Log("RoadGame MUTANTS_SHOT " + line);
        }

        static Camera mutCam;
        static bool mutCloseIdle, mutCloseWind, mutCloseStrike, mutCloseDeath, mutNudged;

        static RenderTexture mutSquareRT, mutVideoRT;

        static RenderTexture MutRT(ref RenderTexture tex, int w, int h)
        {
            if (tex == null) { tex = new RenderTexture(w, h, 24) { antiAliasing = 4, name = "MutantCloseRT" }; tex.Create(); }
            return tex;
        }

        static void MutEnsureCam()
        {
            if (mutCam != null) return;
            mutCam = new GameObject("MutantCloseCam").AddComponent<Camera>();
            mutCam.CopyFrom(Game.I.cam);
            var data = mutCam.GetComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
            if (data == null) data = mutCam.gameObject.AddComponent<UnityEngine.Rendering.Universal.UniversalAdditionalCameraData>();
            data.renderPostProcessing = true;
            mutCam.enabled = false;
        }

        /// <summary>Close-up of a creature with a second camera (game look, no HUD): 3/4 front-right, 24 deg down.</summary>
        static void MutClose(string label, Target tg, float azimuth = 38f, float elev = 24f)
        {
            MutEnsureCam();
            var b = MutBounds(tg);
            float size = Mathf.Max(b.size.x, b.size.y, b.size.z);
            var focus = b.center;
            float dist = size * 2.0f + 1.4f;
            var dir = MutCloseDir(tg, b, dist, azimuth, elev);
            var target = MutRT(ref mutSquareRT, 900, 900);
            mutCam.targetTexture = target;
            mutCam.ResetAspect();
            mutCam.fieldOfView = 30f;
            mutCam.nearClipPlane = 0.1f;
            mutCam.transform.position = focus + dir * dist;
            mutCam.transform.LookAt(focus);
            mutCam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = target;
            var tex = new Texture2D(target.width, target.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, target.width, target.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            File.WriteAllBytes(Path.Combine(cfg.outDir, $"{MutPrefix}_close_{label}.png"), tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
            mutReport.shots.Add("close " + label);
            Debug.Log("RoadGame MUTANTS_CLOSE " + label);
        }

        /// <summary>Camera direction for a close-up: the asked 3/4 view, or the nearest azimuth around the creature from
        /// which the sight lines to its centre, top and feet pass no rock, building or car (colliders) and no other
        /// creature or prop (enemies have no colliders: their drawn bounds, slightly shrunk).</summary>
        static Vector3 MutCloseDir(Target tg, Bounds b, float dist, float azimuth, float elev)
        {
            var face = tg.transform.forward; face.y = 0f;
            face = face.sqrMagnitude > 1e-4f ? face.normalized : Vector3.forward;
            var others = new List<Bounds>();
            foreach (var o in World.I.activeTargets)
            {
                if (o == null || o == tg || !o.gameObject.activeInHierarchy) continue;
                var ob = MutBounds(o);
                if (ob.size.sqrMagnitude < 0.01f || (ob.center - b.center).sqrMagnitude > (dist + 8f) * (dist + 8f)) continue;
                ob.extents *= 0.85f;
                others.Add(ob);
            }
            float[] tries = { azimuth, -azimuth, azimuth + 35f, -azimuth - 35f, 0f, azimuth + 80f, -azimuth - 80f, 180f };
            var probes = new[] { b.center, b.center + Vector3.up * b.extents.y * 0.6f, new Vector3(b.center.x, b.min.y + 0.3f, b.center.z) };
            var best = Vector3.zero;
            int bestClear = -1;
            foreach (var az in tries)
            {
                var h = Quaternion.AngleAxis(az, Vector3.up) * face;
                var dir = h * Mathf.Cos(elev * Mathf.Deg2Rad) + Vector3.up * Mathf.Sin(elev * Mathf.Deg2Rad);
                var cam = b.center + dir * dist;
                int clear = 0;
                if (!Physics.CheckSphere(cam, 0.3f, ~0, QueryTriggerInteraction.Ignore))
                    foreach (var p in probes)
                        if (!Physics.Linecast(p, cam, ~0, QueryTriggerInteraction.Ignore) && !MutBlocked(others, p, cam)) clear++;
                if (clear > bestClear) { bestClear = clear; best = dir; }
                if (clear == probes.Length) break;
            }
            return best;
        }

        static bool MutBlocked(List<Bounds> others, Vector3 from, Vector3 to)
        {
            var d = to - from;
            float len = d.magnitude;
            var ray = new Ray(from, d / len);
            foreach (var ob in others)
                if (ob.IntersectRay(ray, out float hit) && hit < len) return true;
            return false;
        }

        static int mutVideoFrame = -1, mutVideoIndex;
        static Vector3 mutVideoCamPos;
        static Target mutVideoTarget;

        /// <summary>With -captureVideo a,b: a close-up frame of the current creature on every rendered frame (smoothed
        /// camera from the car's side, 30 deg around), written to video_close/ for ffmpeg.</summary>
        static void MutVideoTick(Player pl, Target tg)
        {
            float st = Game.I.SessionTime;
            if (cfg.videoFrom < 0f || st < cfg.videoFrom || st > cfg.videoTo || tg == null || Time.frameCount == mutVideoFrame) return;
            mutVideoFrame = Time.frameCount;
            var vis = tg.GetComponentInChildren<MutantVisual>(true);
            if (vis == null || vis.info == null) return;
            MutEnsureCam();
            float size = Mathf.Max(vis.info.size[0], vis.info.size[1], vis.info.size[2]);
            var focus = tg.Pos + Vector3.up * vis.info.height * 0.42f;
            var toCar = pl.Pos - tg.Pos; toCar.y = 0f;
            if (toCar.sqrMagnitude < 0.01f) toCar = tg.transform.forward;
            var h = Quaternion.AngleAxis(32f, Vector3.up) * toCar.normalized;
            var want = focus + (h * Mathf.Cos(0.40f) + Vector3.up * Mathf.Sin(0.40f)) * (size * 1.55f + 2.2f);
            if (tg != mutVideoTarget) { mutVideoTarget = tg; mutVideoCamPos = want; }
            mutVideoCamPos = Vector3.Lerp(mutVideoCamPos, want, 0.08f);
            var target = MutRT(ref mutVideoRT, 1280, 720);
            mutCam.targetTexture = target;
            mutCam.ResetAspect();
            mutCam.fieldOfView = 30f;
            mutCam.transform.position = mutVideoCamPos;
            mutCam.transform.LookAt(focus);
            mutCam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = target;
            var tex = new Texture2D(target.width, target.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, target.width, target.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            var dir = Path.Combine(cfg.outDir, "video_close");
            Directory.CreateDirectory(dir);
            File.WriteAllBytes(Path.Combine(dir, $"f{mutVideoIndex++:00000}.jpg"), tex.EncodeToJPG(90));
            UnityEngine.Object.DestroyImmediate(tex);
        }

        /// <summary>World bounds of the drawn LOD0 meshes of a target.</summary>
        static Bounds MutBounds(Target t)
        {
            bool any = false;
            var b = new Bounds(t.Pos, Vector3.zero);
            foreach (var r in t.GetComponentsInChildren<MeshRenderer>(false))
            {
                if (r.name.EndsWith("_LOD1", StringComparison.Ordinal)) continue;
                if (!any) { b = r.bounds; any = true; } else b.Encapsulate(r.bounds);
            }
            return b;
        }

        static string MutParts(Target t, out int renderers, out bool onlyMutant, out int tris)
        {
            renderers = 0; tris = 0; onlyMutant = true;
            var vis = t.GetComponentInChildren<MutantVisual>(true);
            var names = new List<string>();
            foreach (var r in t.GetComponentsInChildren<MeshRenderer>(true))
            {
                renderers++;
                var f = r.GetComponent<MeshFilter>();
                string mesh = f != null && f.sharedMesh != null ? f.sharedMesh.name : "-";
                if (vis == null || !r.transform.IsChildOf(vis.transform) || !mesh.StartsWith(mutZone == 2 ? "AW_" : "Mut_", StringComparison.Ordinal)) onlyMutant = false;
                if (!r.name.EndsWith("_LOD1", StringComparison.Ordinal) && f != null && f.sharedMesh != null)
                {
                    for (int sm = 0; sm < f.sharedMesh.subMeshCount; sm++) tris += (int)(f.sharedMesh.GetIndexCount(sm) / 3);
                    names.Add(r.name);
                }
            }
            names.Sort();
            return string.Join(",", names);
        }

        static bool MutPlaceCar(Player pl, Vector3 at, float dist)
        {
            // a dry, clear spot around the creature: preferred distance first, then nearer / farther rings
            for (int k = 0; k < 48; k++)
            {
                float a = (k % 12) * 30f * Mathf.Deg2Rad;
                float dd = dist * (k < 12 ? 1f : k < 24 ? 0.8f : k < 36 ? 1.25f : 1.5f);
                float clear = k < 24 ? 2.0f : 1.6f;
                var p = at + new Vector3(Mathf.Sin(a), 0f, Mathf.Cos(a)) * dd;
                var g = Ground.Sample(p.x, p.z, at.y + 1f);
                if (!g.valid || Mathf.Abs(g.h - at.y) > 0.6f || g.h < -0.05f) continue;
                if (Physics.CheckSphere(new Vector3(p.x, g.h + 1.4f, p.z), clear, Player.ObstacleMask, QueryTriggerInteraction.Ignore)) continue;
                var to = at - p;
                pl.Teleport(new Vector3(p.x, g.h, p.z), Mathf.Atan2(to.x, to.z) * Mathf.Rad2Deg);
                pl.SetSpeed(0f);
                Game.I.cameraRig.zoom = 1f;
                Game.I.cameraRig.Snap();
                return true;
            }
            return false;
        }

        static void MutantsTick(Player pl)
        {
            float t = Game.I.SessionTime;
            if (!mutGlobalDone && t > 1.5f) MutGlobalChecks();
            if (t >= MutStart && t < MutBossStart) MutModelTick(pl, t);
            if (t >= MutBossStart) MutBossTick(pl, t);
            MutVideoTick(pl, t >= MutBossStart ? (Target)mutBoss : mutTarget);
            // creatures keep to the ground while they move (no floating / sinking on slopes, ramps and banks)
            if (World.I != null)
                foreach (var a in World.I.activeTargets)
                    if (a is Enemy e && e.zone.index == mutZone && !e.dead && !e.beingEaten && e.mutant != null && e.spec.kind != TargetKind.Boss)
                    {
                        var g = Ground.Sample(e.Pos.x, e.Pos.z, e.Pos.y + 0.5f);
                        if (g.valid) mutMaxGroundErr = Mathf.Max(mutMaxGroundErr, Mathf.Abs(g.h - e.Pos.y));
                    }
            if (World.I != null) MutStackTick();
        }

        static readonly Dictionary<long, float> mutStack = new Dictionary<long, float>();
        static float mutMaxStack;
        static string mutStackWho = "-";
        static int mutStackFrame = -1;

        /// <summary>Engaged zone-2 mutants are eased apart: the longest time two of them on the same level stay deep inside
        /// each other (centres closer than half the separation distance). Once per game frame.</summary>
        static void MutStackTick()
        {
            if (Time.frameCount == mutStackFrame) return;
            mutStackFrame = Time.frameCount;
            var list = World.I.activeTargets;
            float dt = Time.deltaTime;
            var pl = Game.I.player;
            for (int i = 0; i < list.Count; i++)
            {
                if (!(list[i] is Enemy a) || !a.Engaged || a.mutant == null || a.spec.kind == TargetKind.Boss) continue;
                for (int j = i + 1; j < list.Count; j++)
                {
                    if (!(list[j] is Enemy b) || !b.Engaged || b.mutant == null || b.spec.kind == TargetKind.Boss) continue;
                    long key = ((long)a.spawn.id << 32) ^ (uint)b.spawn.id;
                    var d = a.Pos - b.Pos;
                    float dy = Mathf.Abs(d.y);
                    d.y = 0f;
                    float min = (a.mutant.Footprint + b.mutant.Footprint) * 0.85f;
                    bool deep = dy < 1.5f && d.magnitude < min * 0.5f;
                    float run = deep ? (mutStack.TryGetValue(key, out var r) ? r : 0f) + dt : 0f;
                    mutStack[key] = run;
                    if (run > mutMaxStack)
                    {
                        mutMaxStack = run;
                        if (run > 1.5f)
                            mutStackWho = $"{a.spec.model}#{a.spawn.id}({(a.AnimAttackState ? "attack" : "chase")}, car {Vector3.Distance(a.Pos, pl.Pos):0.0} m) + " +
                                          $"{b.spec.model}#{b.spawn.id}({(b.AnimAttackState ? "attack" : "chase")}, car {Vector3.Distance(b.Pos, pl.Pos):0.0} m) " +
                                          $"apart {d.magnitude:0.00}/{min:0.00} m at ({a.Pos.x:0.0}, {a.Pos.z:0.0}) t={Game.I.SessionTime:0.0}";
                    }
                }
            }
        }

        static void MutGlobalChecks()
        {
            mutGlobalDone = true;
            mutReport.editorMasterMuted = WorkAudioMute.Apply();
            MutCheck(mutReport.editorMasterMuted, "work run is muted");
            MutCheck(Mutants.AvailableFor(mutZone), "creature bundle loads (" + Mutants.SourceFileFor(mutZone) + ")");
            foreach (var m in MutModels)
            {
                var info = Mutants.InfoFor(mutZone, m);
                MutCheck(info != null, $"{m} has a creature ({(info != null ? info.name + ", " + info.tris + " tris" : "-")})");
            }
            var bossInfo = Mutants.InfoFor(mutZone, MutBossModel);
            MutCheck(bossInfo != null, MutBossModel + " has a creature (" + (bossInfo != null ? bossInfo.name : "-") + ")");
            if (mutZone == 2)
                MutCheck(Content.Zones[2].boss.name == "BLACK REACTOR" && Goals.BossAcc[2] == "ЧЁРНЫЙ РЕАКТОР" && Content.Zones[2].name == "ASHEN WINTER",
                         "names: ASHEN WINTER, BLACK REACTOR / ЧЁРНЫЙ РЕАКТОР");
            else
                MutCheck(Content.Zones[1].boss.name == "MIRE MOTHER" && Goals.BossAcc[1] == "МАТКУ ТРЯСИНЫ", "boss names: MIRE MOTHER / МАТКУ ТРЯСИНЫ");
            // zones without a creature bundle keep their own enemies: a zone 0 / zone 3 spawn is never converted
            foreach (int zi in new[] { 0, 3 })
            {
                var sp = new SpawnPoint { id = -1, spec = Content.Zones[zi].specs.Find(s => s.model == ModelId.Raider), zone = Content.Zones[zi], pos = Vector3.zero };
                var go = new GameObject("MutProbe");
                bool applied = Mutants.Apply(sp, go);
                UnityEngine.Object.DestroyImmediate(go);
                MutCheck(!applied, $"zone {zi} raider stays a raider (no creature)");
            }
            int other = 0, converted = 0;
            foreach (var a in World.I.activeTargets)
            {
                bool mv = a.GetComponentInChildren<MutantVisual>(true) != null;
                if (a.zone.index != 1 && a.zone.index != 2 && mv) other++;
                if (a.zone.index == mutZone && a.spec.kind != TargetKind.Prop && mv) converted++;
            }
            MutCheck(other == 0, $"no live target outside the creature zones carries a creature ({other})");
            MutCheck(Content.Zones[mutZone].specs.TrueForAll(s => s.kind == TargetKind.Prop || s.hp > 0), "zone balance table intact");
        }

        static float mutDiagNext;
        static readonly System.Reflection.BindingFlags MutBF = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
        static object MutF(Enemy e, string n) { var f = typeof(Enemy).GetField(n, MutBF); return f != null ? f.GetValue(e) : null; }
        static void MutDiag(Enemy e, Player pl, ModelId model, float s)
        {
            var toP = pl.Pos - e.Pos; toP.y = 0f;
            float reach = e.spec.attackRange + pl.Radius;
            Debug.Log($"RoadGame MUTDIAG {model} s={s:0.00} state={MutF(e, "state")} dist={toP.magnitude:0.00} reach={reach:0.00} canSee={MutF(e, "canSee")} windup={MutF(e, "windup"):0.00} atkT={MutF(e, "attackTimer"):0.00} spd={MutF(e, "speedNow"):0.00} pos={e.Pos} home={MutF(e, "home")} car={pl.Pos} carSpeed={pl.Speed:0.0} obst={Enemy.ObstacleContacts} flips={Enemy.StuckFlips} meleeBlocked={Enemy.MeleeBlocked} dead={e.dead} strikes={(e.mutant != null ? e.mutant.Strikes : -1)}");
            if (model == ModelId.Brute && Mathf.Abs(s - 2.0f) < 0.13f)
            {
                var cols = Physics.OverlapSphere(e.Pos + Vector3.up * 1.2f, 3.5f, Player.ObstacleMask, QueryTriggerInteraction.Ignore);
                foreach (var c in cols)
                    Debug.Log($"RoadGame MUTDIAG near {c.name} layer={c.gameObject.layer} type={c.GetType().Name} rb={(c.attachedRigidbody != null)} center={c.bounds.center} size={c.bounds.size} parent={(c.transform.parent != null ? c.transform.parent.name : "-")} target={(c.GetComponentInParent<Target>() != null ? c.GetComponentInParent<Target>().spec.name : "-")}");
            }
        }

        static void MutModelTick(Player pl, float t)
        {
            int k = Mathf.FloorToInt((t - MutStart) / MutStop);
            if (k >= MutModels.Length) return;
            var model = MutModels[k];
            string tag = $"{k + 1:00}_{model}";
            if (k != mutStop)
            {
                mutStop = k;
                mutStopT0 = t;
                mutTarget = null; mutSpawn = null;
                mutShotApproach = mutShotAttack = mutShotAttack2 = mutHitDone = mutKillDone = mutDeathShot = mutReelDone = mutRespawnDone = false;
                mutCloseIdle = mutCloseWind = mutCloseStrike = mutCloseDeath = mutNudged = false;
                long now = Progress.NowMs;
                var cands = World.I.zoneSpawns[mutZone].FindAll(s => s.spec.model == model && !s.IsDead(now));
                // a spawn on open dry ground in the middle of the zone (away from the dams, gates and the zone edge)
                float zc = Content.ZoneCenterZ(mutZone);
                cands.Sort((a, b) => (Mathf.Abs(a.pos.x) + Mathf.Abs(a.pos.z - zc) * 0.7f).CompareTo(Mathf.Abs(b.pos.x) + Mathf.Abs(b.pos.z - zc) * 0.7f));
                foreach (var sp in cands)
                    if (MutPlaceCar(pl, sp.pos, model == ModelId.Buggy ? 11f : model == ModelId.Crossbow ? 8.5f : 6.5f)) { mutSpawn = sp; break; }
                if (mutSpawn == null)
                    foreach (var sp in World.I.zoneSpawns[mutZone])
                        if (sp.spec.model == model)
                        {
                            var g0 = Ground.Sample(sp.pos.x, sp.pos.z, sp.pos.y + 1f);
                            Debug.Log($"RoadGame MUTANTS candidate {model} id={sp.id} pos={sp.pos} dead={sp.IsDead(now)} ground={(g0.valid ? g0.h : float.NaN):0.00} target={(sp.target != null ? sp.target.gameObject.activeSelf + "/" + sp.target.dead : "none")}");
                        }
                World.I.Tick();
                mutTarget = mutSpawn != null ? mutSpawn.target as Enemy : null;
                MutCheck(mutTarget != null, $"{model}: a live zone-{mutZone} {model} next to the car (spawn {(mutSpawn != null ? mutSpawn.id : -1)})");
                if (mutTarget == null) return;
                if (mutTarget.dead || !mutTarget.gameObject.activeSelf) mutTarget.ResetForSpawn(false);
                MutStructure(mutTarget, model);
                mutStrikesBefore = mutTarget.mutant != null ? mutTarget.mutant.Strikes : 0;
                return;
            }
            if (mutTarget == null) return;
            float s = t - mutStopT0;
            var e = mutTarget;
            var an = e.mutant;
            if (s < 6.4f && t >= mutDiagNext) { mutDiagNext = t + 0.25f; MutDiag(e, pl, model, s); }
            if (!mutShotApproach && s > 1.1f) { mutShotApproach = true; MutShot(tag + "_a_approach"); }
            // a creature that has not engaged after 3 s gets the car right next to it
            if (!mutNudged && s > 3.2f && !e.dead && an != null && an.Strikes == mutStrikesBefore && !e.Engaged)
            {
                mutNudged = true;
                MutPlaceCar(pl, e.Pos, 3.6f);
                Debug.Log($"RoadGame MUTANTS nudged the car next to {model} at {e.Pos}");
            }
            if (!mutCloseIdle && s > 0.3f) { mutCloseIdle = true; MutClose(tag + "_1_rest", e); }
            if (!mutCloseWind && s > 1.2f && !e.dead && (e.AnimWindup > 0.62f || (e.spec.ranged && e.AnimWindup > 0.75f))) { mutCloseWind = true; MutClose(tag + "_2_windup", e); }
            if (!mutCloseStrike && mutCloseWind && s > 1.3f && !e.dead && Time.time - e.AnimStrikeTime < 0.07f) { mutCloseStrike = true; MutClose(tag + "_3_strike", e); }
            // attack shots: the frame of a wind-up past half (melee) / the volley (ranged)
            if (!mutShotAttack && s > 1.4f && !e.dead && an != null && (e.AnimWindup > 0.55f || (e.spec.ranged && e.AnimBurst)))
            {
                mutShotAttack = true;
                MutShot(tag + "_b_attack");
            }
            if (mutShotAttack && !mutShotAttack2 && !e.dead && an != null && Time.time - e.AnimStrikeTime < 0.09f && s > 1.6f)
            {
                mutShotAttack2 = true;
                MutShot(tag + "_c_strike");
            }
            if (!mutHitDone && s > 6.3f)
            {
                mutHitDone = true;
                MutCheck(an != null && an.Strikes > mutStrikesBefore, $"{model} attacked the car with its new body ({(an != null ? an.Strikes - mutStrikesBefore : 0)} strikes / volleys, enemy shots so far {Projectile.Fired})");
                if (!mutShotAttack) MutShot(tag + "_b_attack");
                MutCheck(e.AnimStrikeTime > 0f, $"{model} wind-up -> damage frame reached (last at {e.AnimStrikeTime:0.00}, landed={e.AnimStrikeLanded})");
                e.Hit(0.001, false, pl.Pos);
                bool flash = false;
                var block = new MaterialPropertyBlock();
                foreach (var r in e.GetComponentsInChildren<MeshRenderer>(false))
                {
                    r.GetPropertyBlock(block);
                    if (block.GetColor("_FlashColor").a > 0.5f) { flash = true; break; }
                }
                MutCheck(flash, $"{model} flashes when hit (property blocks on the creature)");
            }
            if (!mutKillDone && s > 6.6f)
            {
                mutKillDone = true;
                mutReeledBefore = Harpooner.Reeled;
                MutParts(e, out mutRenderersBefore, out _, out _);
                mutPartsBefore = MutParts(e, out _, out _, out _);
                // the harpooner waits 0.75 s so the death pose can be photographed; then it reels the wreck in as always
                if (pl.harpooner != null) pl.harpooner.enabled = false;
                e.Hit(e.hp + 1d, false, pl.Pos);
                mutKillT = t;
                MutCheck(e.dead && an != null && an.Dying, $"{model} dies through the normal damage handler and plays its death");
                MutCheck(Vector3.Dot(e.transform.up, Vector3.up) > 0.999f, $"{model} root stays upright on death (the creature falls inside its own hierarchy; the harpoon takes the root)");
            }
            if (mutKillDone && !mutCloseDeath && t - mutKillT > 0.7f) { mutCloseDeath = true; MutClose(tag + "_4_death", e); }
            if (mutKillDone && !mutDeathShot && t - mutKillT > 0.62f)
            {
                mutDeathShot = true;
                MutShot(tag + "_d_death");
            }
            if (mutKillDone && t - mutKillT > 0.75f && pl.harpooner != null && !pl.harpooner.enabled) pl.harpooner.enabled = true;
            if (mutKillDone && !mutReelDone && t - mutKillT > 3.2f)
            {
                mutReelDone = true;
                bool eaten = !e.gameObject.activeSelf || e.beingEaten;
                MutCheck(eaten && Harpooner.Reeled > mutReeledBefore, $"{model} wreck is harpooned and reeled in (reeled {Harpooner.Reeled - mutReeledBefore})");
            }
            if (mutReelDone && !mutRespawnDone && t - mutKillT > 3.3f)
            {
                mutRespawnDone = true;
                e.ResetForSpawn(true);
                string after = MutParts(e, out int rAfter, out bool only, out _);
                var an2 = e.mutant;
                MutCheck(!e.dead && only && rAfter == mutRenderersBefore && after == mutPartsBefore && an2 != null && !an2.Dying,
                    $"respawned {model} (spawn {e.spawn.id}) is the same creature in its rest pose ({rAfter} renderers)");
                World.I.Tick();
            }
        }

        static void MutStructure(Enemy e, ModelId model)
        {
            string parts = MutParts(e, out int renderers, out bool only, out int tris);
            var vis = e.GetComponentInChildren<MutantVisual>(true);
            MutCheck(vis != null && e.mutant != null, $"{model} is a mutant ({(vis != null ? vis.info.name : "-")}) with an animator ({(e.mutant != null ? e.mutant.GetType().Name : "-")})");
            MutCheck(only && renderers > 0, $"{model} draws only mutant meshes, no leftover body or weapon ({renderers} renderers)");
            bool leftovers = false;
            foreach (var tr in e.GetComponentsInChildren<Transform>(true))
                if ((vis == null || !tr.IsChildOf(vis.transform)) && tr != e.transform) leftovers = true;
            MutCheck(!leftovers, $"{model} has no generated humanoid / buggy transforms left");
            MutCheck(e.GetComponent<ImportedActorSurface>() != null && e.rig != null && e.rig.CollectedImported(), $"{model} rig flashes / burns the creature with property blocks");
            var b = MutBounds(e);
            float top = b.max.y - e.Pos.y;
            float bar = e.BarHeight;
            MutCheck(bar >= top - 0.05f && bar <= top + 1.0f, $"{model} HP bar at {bar:0.00} m sits just over the body (top {top:0.00} m)");
            var aim = Turret.AimPoint(e);
            var bb = b; bb.Expand(0.3f);
            MutCheck(bb.Contains(aim), $"{model} gun aim point {aim - e.Pos} is on the body");
            if (e.spec.ranged)
            {
                var mz = e.rig.muzzle;
                bool ok = mz != null && bb.Contains(mz.position) && mz.position.y - e.Pos.y > 0.35f;
                MutCheck(ok, $"{model} shots leave from its mouth ({(mz != null ? (mz.position - e.Pos).ToString("0.00") : "no muzzle")})");
            }
            float fp = vis != null ? vis.info.footprint : 0f;
            string line = $"{model} -> {(vis != null ? vis.info.name : "-")} spawn={e.spawn.id} name='{e.spec.name}' renderers={renderers} tris={tris} height={top:0.00} bar={bar:0.00} radius={e.Radius:0.00} footprint={fp:0.00} ranged={e.spec.ranged} proj={e.spec.proj} range={e.spec.attackRange:0.0} speed={e.spec.speed:0.0} windup={e.spec.windupTime:0.00} parts=[{parts}]";
            mutReport.creatures.Add(line);
            Debug.Log("RoadGame MUTANTS " + line);
        }

        static void MutBossTick(Player pl, float t)
        {
            var bsp = World.I.bossSpawns[mutZone];
            if (!mutBossPlaced)
            {
                mutBossPlaced = true;
                MutCheck(bsp != null, $"zone-{mutZone} boss spawn exists");
                if (bsp == null) return;
                var dir = (pl.Pos - bsp.pos); dir.y = 0f;
                MutPlaceCar(pl, bsp.pos, 11f);
                World.I.Tick();
                mutBoss = bsp.target as Enemy;
                MutCheck(mutBoss != null, MutBossName + " is active next to the car");
                if (mutBoss != null) MutStructure(mutBoss, MutBossModel);
                mutMaxHpBefore = Game.I.progress.d.maxHp;
                return;
            }
            if (mutBoss == null) return;
            float s = t - MutBossStart;
            var e = mutBoss;
            string bt = MutBossTag;
            if (!mutBossShotApproach && s > 1.2f) { mutBossShotApproach = true; MutShot(bt + "_a_approach"); MutClose(bt + "_1_rest", e, 30f, 18f); }
            if (!e.dead)
            {
                if (e.AnimSpecial && e.AnimSpecialKind == 1)
                {
                    if (!mutBossShotSlam && e.AnimSpecialT > 0.75f) { mutBossShotSlam = true; mutBossSpecials++; MutShot(bt + "_c_special_slam"); MutClose(bt + "_3_special", e, 30f, 18f); }
                }
                else if (!mutBossShotStomp && e.AnimWindup > 0.6f) { mutBossShotStomp = true; MutShot(bt + "_b_blow"); MutClose(bt + "_2_blow", e, 30f, 18f); }
            }
            if (!mutBossKilled && s > 16f)
            {
                mutBossKilled = true;
                MutCheck(mutBossShotStomp || mutBossShotSlam, $"{MutBossName} wound up a blow / slam (blow={mutBossShotStomp}, slam={mutBossShotSlam})");
                int kills = Game.I.progress.d.bossKills[mutZone];
                long gemsBefore = Game.I.progress.d.gems;
                if (pl.harpooner != null) pl.harpooner.enabled = false;
                e.Hit(e.hp + 1d, false, pl.Pos);
                mutBossKillT = t;
                var d = Game.I.progress.d;
                MutCheck(e.dead && e.mutant != null && e.mutant.Dying, MutBossName + " dies through the normal damage handler and plays its death");
                MutCheck(d.bossKills[mutZone] == kills + 1 && d.unlockedZone >= mutZone + 1, $"boss win counts and opens the next zone (bossKills={d.bossKills[mutZone]}, unlockedZone={d.unlockedZone})");
                if (mutZone == 2)
                {
                    MutCheck(d.weaponLevel.Length > 3 && d.weaponLevel[3] > 0, "the Black Reactor unlocks " + Content.Weapons[3].name + " as before");
                    MutCheck(d.armorLevel[1] > 0, "the Black Reactor gives " + Content.Armors[1].name + " as before");
                }
                else MutCheck(d.weaponLevel.Length > 2 && d.weaponLevel[2] > 0, "the boss win unlocks Scrap Spear as before");
                mutGemsBefore = gemsBefore;
            }
            if (mutBossKilled && !mutBossShotDeath && t - mutBossKillT > 1.05f) { mutBossShotDeath = true; MutShot(MutBossTag + "_d_death"); MutClose(MutBossTag + "_4_death", e, 30f, 18f); }
            if (mutBossKilled && t - mutBossKillT > 1.15f && pl.harpooner != null && !pl.harpooner.enabled) pl.harpooner.enabled = true;
            if (mutBossKilled && !mutBossReel && t - mutBossKillT > 6f)
            {
                mutBossReel = true;
                var d = Game.I.progress.d;
                MutCheck(d.maxHp > mutMaxHpBefore, $"the boss wreck is reeled in and its reward applies (max HP {mutMaxHpBefore:0} -> {d.maxHp:0})");
                if (mutZone == 2) MutCheck(d.gems >= mutGemsBefore + Content.Zones[2].bossGems, $"first win pays {Content.Zones[2].bossGems} gems ({mutGemsBefore} -> {d.gems})");
                MutCheck(mutMaxGroundErr < 0.25f, $"creatures stay on the ground while they move (max error {mutMaxGroundErr:0.000} m)");
                MutCheck(mutMaxStack < 1.5f, $"engaged mutants do not stand inside each other (longest deep overlap {mutMaxStack:0.00} s; {mutStackWho})");
            }
            if (mutBossReel && !mutPerfDone && t - mutBossKillT > 6.5f)
            {
                mutPerfDone = true;
                // a camp full of mutants for the performance stop
                var camps = World.I.camps[mutZone];
                if (camps.Count > 0)
                {
                    MutPlaceCar(pl, camps[0], 9f);
                    World.I.Tick();
                }
            }
        }

        static void MutantsFinish()
        {
            if (mutReport == null) return;
            File.WriteAllText(Path.Combine(cfg.outDir, MutPrefix + "-checks.json"), JsonUtility.ToJson(mutReport, true));
            Debug.Log($"RoadGame MUTANTS_RESULT checks={mutReport.checks.Count} failures={mutReport.failures.Count}");
        }
    }
}
