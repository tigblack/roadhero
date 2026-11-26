using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// See-through roofs, lids and walls (OcclusionFader) in the real game: the car is put under / behind every occluder of
    /// the intro and the first two zones in turn (a game-camera shot each), then taken away. Measures how much the faded
    /// pieces over the car still cover together (several overlapping pieces add up), and checks that every piece that
    /// faded comes back to its own opaque materials after the car has left.
    /// Run: -captureScenario occlusion -captureTimes 600 (session time; the scenario ends by itself when all stops ran).
    /// </summary>
    public static partial class AutoCapture
    {
        [Serializable]
        class OcclusionReport
        {
            public bool editorMasterMuted;
            public List<string> checks = new List<string>();
            public List<string> failures = new List<string>();
            public List<string> stops = new List<string>();
        }

        class OStop
        {
            public string name;
            public Occluder occ;
            public Vector3 at;
            public float yaw;
            public readonly List<Occluder> faded = new List<Occluder>();
        }

        static OcclusionReport oReport;
        static readonly List<OStop> oStops = new List<OStop>();
        static readonly Dictionary<Occluder, Material[][]> oBaseline = new Dictionary<Occluder, Material[][]>();
        static readonly Dictionary<Occluder, UnityEngine.Rendering.ShadowCastingMode[]> oShadowBase = new Dictionary<Occluder, UnityEngine.Rendering.ShadowCastingMode[]>();
        static int oIndex = -1, oFrame = -1, oMulti;
        static float oT0, oWorst;
        static string oWorstName = "";
        static bool oDone, oMeasured, oLeft, oChecked;
        const float OStopDur = 5.2f;
        /// <summary>Most the faded pieces over the car may cover together (one faded roof is about 0.2).</summary>
        const float OMaxCover = 0.3f;

        static void OcclusionSetup(Progress p)
        {
            var d = p.d;
            d.maxHp = d.hp = 1e9; d.regen = 1e7; d.dmg[0] = 0.01; d.tutorialDone = true; d.introPending = false;
            d.unlockedZone = 1; d.bossKills[0] = 1;
            Game.ScriptedInput = t => Vector2.zero;
            Game.Autopilot = false;
            oReport = new OcclusionReport();
            oStops.Clear(); oBaseline.Clear(); oShadowBase.Clear();
            oIndex = -1; oFrame = -1; oDone = false; oMulti = 0; oWorst = 0f; oWorstName = "";
        }

        static void OCheck(bool ok, string message)
        {
            if (ok) oReport.checks.Add(message); else oReport.failures.Add(message);
            Debug.Log("RoadGame OCCLUSION_CHECK " + (ok ? "PASS " : "FAIL ") + message);
        }

        static string StripDigits(string s)
        {
            int n = s.Length;
            while (n > 0 && (char.IsDigit(s[n - 1]) || s[n - 1] == '_')) n--;
            return s.Substring(0, n);
        }

        /// <summary>One stop per kind of occluder (at most two of a kind), in the intro and the first two zones.</summary>
        static void OBuildStops(Player pl)
        {
            var perKind = new Dictionary<string, int>();
            foreach (var o in OcclusionFader.I.All)
            {
                if (o == null || o.renderers == null || o.renderers.Length == 0) continue;
                var b = o.bounds;
                int zone = Content.ZoneIndexAt(b.center.z);
                if (b.center.z > Content.ZoneMaxZ(1)) continue;
                if (zone > 1) continue;
                string kind = StripDigits(o.name);
                perKind.TryGetValue(kind, out int count);
                if (count >= 2) continue;
                if (!OFindSpot(o, out var at, out float yaw)) { Debug.Log($"RoadGame OCCLUSION no spot for {o.name} bounds={b}"); continue; }
                perKind[kind] = count + 1;
                oStops.Add(new OStop { name = o.name, occ = o, at = at, yaw = yaw });
            }
            // the materials every piece has while the car is far away (all opaque)
            foreach (var o in OcclusionFader.I.All)
            {
                var m = new Material[o.renderers.Length][];
                var sh = new UnityEngine.Rendering.ShadowCastingMode[o.renderers.Length];
                for (int i = 0; i < o.renderers.Length; i++)
                {
                    m[i] = o.renderers[i] != null ? o.renderers[i].sharedMaterials : null;
                    sh[i] = o.renderers[i] != null ? o.renderers[i].shadowCastingMode : UnityEngine.Rendering.ShadowCastingMode.On;
                }
                oBaseline[o] = m;
                oShadowBase[o] = sh;
            }
            Debug.Log($"RoadGame OCCLUSION stops={oStops.Count} occluders={OcclusionFader.I.All.Count}");
        }

        /// <summary>A free spot for the car: under a roof / lid (on the floor below it), or just north of a wall (the camera
        /// looks from the south, so the wall stands between them).</summary>
        static bool OFindSpot(Occluder o, out Vector3 at, out float yaw)
        {
            var b = o.bounds;
            yaw = 0f; at = Vector3.zero;
            var tries = new List<Vector3>();
            if (o.onlyWhenBelow)
            {
                foreach (var dx in new[] { 0f, -0.25f, 0.25f })
                    foreach (var dz in new[] { 0f, -0.25f, 0.25f })
                        tries.Add(new Vector3(b.center.x + dx * b.size.x, b.min.y - 0.4f, b.center.z + dz * b.size.z));
            }
            else
            {
                foreach (var dx in new[] { 0f, -0.3f, 0.3f })
                    tries.Add(new Vector3(b.center.x + dx * b.size.x, b.center.y, b.max.z + 3f));
            }
            foreach (var p in tries)
            {
                var g = Ground.Sample(p.x, p.z, p.y);
                if (!g.valid) continue;
                if (o.onlyWhenBelow && g.h > b.min.y - 1.2f) continue;           // no room under it
                var c = new Vector3(p.x, g.h + 0.95f, p.z);
                if (Physics.CheckBox(c, new Vector3(1.1f, 0.7f, 2.4f), Quaternion.identity, Player.ObstacleMask, QueryTriggerInteraction.Ignore)) continue;
                at = new Vector3(p.x, g.h, p.z);
                return true;
            }
            return false;
        }

        static void OStart(Player pl, float t)
        {
            var st = oStops[oIndex];
            oT0 = t; oMeasured = oLeft = oChecked = false;
            st.faded.Clear();
            pl.Teleport(st.at, st.yaw);
            Game.I.cameraRig.Snap();
            World.I.Tick();
            Debug.Log($"RoadGame OCCLUSION stop={oIndex} {st.name} at={pl.Pos} below={st.occ.onlyWhenBelow} minAlpha={st.occ.minAlpha:0.00}");
        }

        static void OcclusionTick(Player pl)
        {
            if (Time.frameCount == oFrame) return;
            oFrame = Time.frameCount;
            float t = Game.I.SessionTime;
            if (oDone) return;
            if (oIndex < 0)
            {
                if (t < 2.5f || OcclusionFader.I == null) return;
                OBuildStops(pl);
                if (oStops.Count == 0) { OCheck(false, "found occluders to visit"); oDone = true; OSummary(); return; }
                oIndex = 0;
                OStart(pl, t);
                return;
            }
            var st = oStops[oIndex];
            float s = t - oT0;
            if (!oMeasured && s > 2.3f) { oMeasured = true; OMeasure(st, pl); }
            if (!oLeft && s > 2.6f)
            {
                // away to the nearest repair pad (open ground): every piece over the old spot must turn solid again
                oLeft = true;
                var pad = World.I.NearestStation(st.at, 1);
                pl.Teleport(pad != null ? pad.pos : World.I.startPos, 0f);
                Game.I.cameraRig.Snap();
            }
            if (!oChecked && s > 4.9f) { oChecked = true; OCheckRestored(st); }
            if (s > OStopDur)
            {
                oIndex++;
                if (oIndex >= oStops.Count) { oDone = true; OSummary(); }
                else OStart(pl, t);
            }
        }

        static void OMeasure(OStop st, Player pl)
        {
            var cam = Game.I.cam.transform.position;
            var car = pl.Pos + Vector3.up * 0.9f;
            float clear = 1f;
            var names = new List<string>();
            foreach (var o in OcclusionFader.I.All)
            {
                if (o.alpha < 0.99f) st.faded.Add(o);
                if (OcclusionFader.SegmentBoxDistance(cam, car, o.bounds) > 0f) continue;
                if (o.onlyWhenBelow && car.y > o.bounds.max.y - 0.15f) continue;
                clear *= 1f - o.alpha;
                names.Add($"{o.name}:{o.alpha:0.00}");
            }
            float cover = 1f - clear;
            if (names.Count >= 2) oMulti++;
            if (cover > oWorst) { oWorst = cover; oWorstName = st.name; }
            string label = $"occlusion_{oIndex:00}_{st.name}";
            HShot(label);
            oReport.stops.Add($"{st.name} at {pl.Pos} over the car: {names.Count} piece(s) [{string.Join(", ", names)}] cover={cover:0.00} faded={st.faded.Count}");
            Debug.Log($"RoadGame OCCLUSION measure {st.name} pieces={names.Count} cover={cover:0.00} [{string.Join(", ", names)}] faded={st.faded.Count}");
            OCheck(st.occ.alpha < 0.99f, $"{st.name}: fades when the car is {(st.occ.onlyWhenBelow ? "under it" : "behind it")} (alpha {st.occ.alpha:0.00})");
            OCheck(cover <= OMaxCover, $"{st.name}: the faded pieces over the car cover {cover:0.00} together ({names.Count} piece(s), limit {OMaxCover:0.00})");
            var hard = OHardBlockers(pl);
            int worst = 0;
            foreach (var h in hard) { int x = h.LastIndexOf('x'); if (x > 0 && int.TryParse(h.Substring(x + 1), out int n)) worst = Mathf.Max(worst, n); }
            Debug.Log($"RoadGame OCCLUSION hard {st.name}: [{string.Join(", ", hard)}] worst={worst}/5");
            // the car must stay mostly visible: something solid may cover a corner (a pillar by a wall), not most of it
            OCheck(worst <= 2, $"{st.name}: nothing solid (not see-through) hides most of the car ({worst} of 5 sight lines blocked by one object{(hard.Count > 0 ? ": " + string.Join(", ", hard) : "")})");
        }

        /// <summary>Opaque things that are not see-through pieces yet stand between the camera and the car's top
        /// (five points: centre and corners), found by exact ray / triangle tests on the meshes along the line.</summary>
        static List<string> OHardBlockers(Player pl)
        {
            var cam = Game.I.cam.transform.position;
            var hits = new Dictionary<string, int>();
            var occ = new HashSet<Renderer>();
            foreach (var o in OcclusionFader.I.All) foreach (var r in o.renderers) if (r != null) occ.Add(r);
            var tf = pl.transform;
            var pts = new[] { new Vector3(0f, 1.45f, 0f), new Vector3(0.8f, 1.0f, 1.8f), new Vector3(-0.8f, 1.0f, 1.8f), new Vector3(0.8f, 1.0f, -1.8f), new Vector3(-0.8f, 1.0f, -1.8f) };
            foreach (var mr in UnityEngine.Object.FindObjectsByType<MeshRenderer>())
            {
                if (!mr.enabled || !mr.gameObject.activeInHierarchy || occ.Contains(mr) || mr.transform.IsChildOf(tf)) continue;
                // the car's own model, its gun and the harpoon crew are separate objects that ride with it
                if (pl.rig != null && mr.transform.IsChildOf(pl.rig.transform)) continue;
                if (pl.turret != null && mr.transform.IsChildOf(pl.turret.transform)) continue;
                if (pl.harpooner != null && mr.transform.IsChildOf(pl.harpooner.transform)) continue;
                if (mr.GetComponentInParent<ImportedCar>() != null) continue;
                // enemies and props are gameplay objects (a boss standing over the car is a fight, not the level)
                if (mr.GetComponentInParent<Target>() != null) continue;
                if (mr.sharedMaterial != null && mr.sharedMaterial.renderQueue >= 3000) continue;   // transparent (water, fx)
                var mf = mr.GetComponent<MeshFilter>();
                if (mf == null || mf.sharedMesh == null || !mf.sharedMesh.isReadable) continue;
                int n = 0;
                foreach (var lp in pts)
                {
                    var target = tf.TransformPoint(lp);
                    var dir = target - cam; float len = dir.magnitude; dir /= len;
                    var ray = new Ray(cam, dir);
                    if (!mr.bounds.IntersectRay(ray, out float bd) || bd > len) continue;
                    if (ORayHitsMesh(ray, mf, len - 0.05f)) n++;
                }
                if (n > 0) hits[mr.name] = n;
            }
            var list = new List<string>();
            foreach (var kv in hits) list.Add(kv.Key + "x" + kv.Value);
            return list;
        }

        static bool ORayHitsMesh(Ray worldRay, MeshFilter mf, float maxDist)
        {
            var m = mf.sharedMesh;
            var toLocal = mf.transform.worldToLocalMatrix;
            var o = toLocal.MultiplyPoint3x4(worldRay.origin);
            var far = toLocal.MultiplyPoint3x4(worldRay.origin + worldRay.direction * maxDist);
            var d = far - o; float L = d.magnitude; if (L < 1e-6f) return false; d /= L;
            var v = m.vertices; var t = m.triangles;
            for (int i = 0; i < t.Length; i += 3)
            {
                Vector3 a = v[t[i]], b = v[t[i + 1]], c = v[t[i + 2]];
                var e1 = b - a; var e2 = c - a; var p = Vector3.Cross(d, e2); float det = Vector3.Dot(e1, p);
                if (Mathf.Abs(det) < 1e-9f) continue;
                float inv = 1f / det; var s = o - a; float u = Vector3.Dot(s, p) * inv; if (u < 0f || u > 1f) continue;
                var q = Vector3.Cross(s, e1); float w = Vector3.Dot(d, q) * inv; if (w < 0f || u + w > 1f) continue;
                float dist = Vector3.Dot(e2, q) * inv;
                if (dist > 0.01f && dist < L) return true;
            }
            return false;
        }

        static void OCheckRestored(OStop st)
        {
            int bad = 0;
            var which = new List<string>();
            foreach (var o in st.faded)
            {
                bool solid = o.alpha >= 0.999f && !o.Faded;
                bool same = true;
                if (oBaseline.TryGetValue(o, out var mats))
                    for (int i = 0; i < o.renderers.Length && same; i++)
                    {
                        var r = o.renderers[i];
                        if (r == null || mats[i] == null) continue;
                        var now = r.sharedMaterials;
                        if (now.Length != mats[i].Length) { same = false; break; }
                        for (int k = 0; k < now.Length; k++) if (now[k] != mats[i][k]) { same = false; break; }
                    }
                bool shadows = true;
                if (oShadowBase.TryGetValue(o, out var sh))
                    for (int i = 0; i < o.renderers.Length; i++)
                        if (o.renderers[i] != null && o.renderers[i].shadowCastingMode != sh[i]) shadows = false;
                if (!solid || !same || !shadows) { bad++; which.Add($"{o.name}(alpha {o.alpha:0.00}, materials {(same ? "own" : "CHANGED")}, shadows {(shadows ? "back" : "OFF")})"); }
            }
            OCheck(bad == 0, $"{st.name}: all {st.faded.Count} faded piece(s) solid again with their own materials and shadows after the car left{(bad > 0 ? ": " + string.Join(", ", which) : "")}");
        }

        static void OSummary()
        {
            OCheck(oMulti > 0, $"stops with two or more pieces over the car were measured ({oMulti})");
            Debug.Log($"RoadGame OCCLUSION worst cover {oWorst:0.00} at {oWorstName}");
            oReport.editorMasterMuted = UnityEditor.EditorUtility.audioMasterMute;
            Debug.Log($"RoadGame OCCLUSION_RESULT checks={oReport.checks.Count + oReport.failures.Count} failures={oReport.failures.Count}");
            File.WriteAllText(Path.Combine(cfg.outDir, "occlusion-checks.json"), JsonUtility.ToJson(oReport, true));
        }

        static void OcclusionFinish()
        {
            if (oReport == null) return;
            if (!oDone) { OCheck(false, $"all stops ran in the capture time (stopped at {oIndex} of {oStops.Count})"); OSummary(); }
        }
    }
}
