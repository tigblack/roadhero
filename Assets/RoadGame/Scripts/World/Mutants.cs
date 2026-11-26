using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

namespace RoadGame
{
    /// <summary>
    /// The creatures of the zones with their own enemy bundle. Second zone (Toxic Wetlands): seven swamp mutants from
    /// ArtSource/Characters/ToxicWetlandsMutants (bundle Resources/Creatures/WetlandsMutants). Third zone (Ashen Winter):
    /// seven enemies from ArtSource/Characters/AshenWinterEnemies (bundle Resources/Creatures/AshenWinterEnemies, their
    /// animators are in AshenEnemies.cs). Only the visuals change:
    /// the spawn keeps its logical ModelId, ID, balance and rewards. Each creature is a hierarchy of rigid parts at their
    /// joints, driven by a per-anatomy procedural animator (rest, move, wind-up, strike in step with the game's damage
    /// moment, hit reaction, death). The generated humanoid / buggy of the spawn is removed completely.
    /// </summary>
    public static class Mutants
    {
        public const string ManifestResource = "Creatures/WetlandsMutants/manifest";
        /// <summary>Third zone (index 2, Ashen Winter): ArtSource/Characters/AshenWinterEnemies.</summary>
        public const string AshenManifestResource = "Creatures/AshenWinterEnemies/manifest";
        /// <summary>LOD0 is used while the creature's bounds take more than this share of the screen height.</summary>
        public const float Lod0ScreenHeight = 0.045f;

        [Serializable] sealed class Manifest
        {
            public int version;
            public string sourceFile;
            public CreatureInfo[] creatures;
            public Node[] nodes;
            public MeshInfo[] meshes;
            public MaterialInfo[] materials;
        }
        [Serializable] public sealed class CreatureInfo
        {
            public string model, name;
            public int root, nodeCount, tris;
            public float height, footprint;
            public float[] size;
        }
        [Serializable] sealed class Node
        {
            public string name;
            public int parent = -1, mesh = -1, lodLevel, lodOf = -1;
            public int[] materials;
            public float[] position, rotation, scale;
            public bool castShadows = true;
        }
        [Serializable] sealed class MeshInfo
        {
            public string name, resource;
            public int vertexCount, triangles, submeshes;
        }
        [Serializable] sealed class MaterialInfo
        {
            public string name, shader, texture, baseKind;
            public float[] color;
            public float dust = -1f;
        }

        /// <summary>One creature bundle (a zone's enemies). Loaded on first use; meshes and materials are lazy.</summary>
        sealed class Bundle
        {
            public readonly int zone;
            public readonly string resource, prefix;
            public Manifest data;
            public Mesh[] meshes;
            public Material[] materials;
            public bool loadFailed;
            public int built;
            public Bundle(int zone, string resource, string prefix) { this.zone = zone; this.resource = resource; this.prefix = prefix; }

            public bool Load()
            {
                if (data != null) return true;
                if (loadFailed) return false;
                var asset = Resources.Load<TextAsset>(resource);
                if (asset == null) { loadFailed = true; return false; }
                try
                {
                    data = JsonUtility.FromJson<Manifest>(asset.text);
                    if (data == null || data.creatures == null || data.nodes == null || data.meshes == null || data.materials == null)
                        throw new InvalidDataException("Incomplete creature manifest");
                    meshes = new Mesh[data.meshes.Length];
                    materials = new Material[data.materials.Length];
                }
                catch (Exception e)
                {
                    Debug.LogError("RoadGame: creature bundle could not be loaded (" + resource + "): " + e);
                    data = null;
                    loadFailed = true;
                }
                finally { Resources.UnloadAsset(asset); }
                return data != null;
            }

            public void Reset() { data = null; meshes = null; materials = null; loadFailed = false; built = 0; }
        }

        static readonly Bundle[] bundles =
        {
            new Bundle(1, ManifestResource, "Mutant_"),
            new Bundle(2, AshenManifestResource, "Ashen_"),
        };
        static Color lastShade;
        /// <summary>Creatures built since start (tests), all zones.</summary>
        public static int Built { get; private set; }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { foreach (var b in bundles) b.Reset(); Built = 0; lastShade = default; }

        static Bundle BundleFor(int zone)
        {
            foreach (var b in bundles) if (b.zone == zone) return b;
            return null;
        }

        /// <summary>The swamp mutants' bundle (second zone) loads.</summary>
        public static bool Available => AvailableFor(1);
        public static string SourceFile => SourceFileFor(1);
        public static bool AvailableFor(int zone) { var b = BundleFor(zone); return b != null && b.Load(); }
        public static string SourceFileFor(int zone) { var b = BundleFor(zone); return b != null && b.Load() ? b.data.sourceFile : ""; }
        /// <summary>Creatures of one zone's bundle built since start (tests).</summary>
        public static int BuiltFor(int zone) { var b = BundleFor(zone); return b != null ? b.built : 0; }

        /// <summary>The swamp mutant (second zone) that replaces a model.</summary>
        public static CreatureInfo InfoFor(ModelId model) => InfoFor(1, model);

        public static CreatureInfo InfoFor(int zone, ModelId model)
        {
            var b = BundleFor(zone);
            if (b == null || !b.Load()) return null;
            string key = model.ToString();
            foreach (var c in b.data.creatures) if (c.model == key) return c;
            return null;
        }

        /// <summary>Foot enemies, buggies and the boss of a zone with a creature bundle (second: swamp mutants, third:
        /// Ashen Winter): called right after Models.Create (before the Enemy component exists). The object is reused for
        /// every respawn, so the swap happens once.</summary>
        public static bool Apply(SpawnPoint spawn, GameObject target)
        {
            if (spawn == null || spawn.zone == null || spawn.spec.kind == TargetKind.Prop) return false;
            var bundle = BundleFor(spawn.zone.index);
            if (bundle == null) return false;
            if (target.GetComponentInChildren<MutantVisual>(true) != null) return true;
            var info = InfoFor(spawn.zone.index, spawn.spec.model);
            if (info == null) return false;
            // the generated humanoid / buggy goes away entirely: no hidden old body or weapon stays under the creature
            var root = target.transform;
            for (int i = root.childCount - 1; i >= 0; i--)
            {
                var child = root.GetChild(i).gameObject;
                child.SetActive(false);
                child.transform.SetParent(null, false);
                if (Application.isPlaying) UnityEngine.Object.Destroy(child); else UnityEngine.Object.DestroyImmediate(child);
            }
            foreach (var r in target.GetComponents<Renderer>()) r.enabled = false;
            var visual = Build(bundle, info, root);
            var rig = target.GetComponent<Rig>() ?? target.AddComponent<Rig>();
            rig.body = visual.Part("Body") ?? visual.Part("Pelvis") ?? visual.transform;
            rig.legL = rig.legR = rig.armL = rig.armR = rig.weapon = rig.turret = null;
            rig.muzzle = visual.Part("Muzzle");
            rig.wheels.Clear();
            rig.steer.Clear();
            rig.height = info.height;
            if (target.GetComponent<ImportedActorSurface>() == null) target.AddComponent<ImportedActorSurface>();
            var anim = AddAnimator(spawn.zone.index, spawn.spec.model, target);
            anim.Bind(visual, spawn);
            rig.CollectRenderers();
            EnsureShadeSync();
            Built++;
            bundle.built++;
            return true;
        }

        static MutantAnimator AddAnimator(int zone, ModelId model, GameObject go)
        {
            if (zone == 2)
                switch (model)
                {
                    case ModelId.Scav: return go.AddComponent<AshPeckerAnimator>();
                    case ModelId.Raider: return go.AddComponent<SnowReaperAnimator>();
                    case ModelId.Spearman: return go.AddComponent<NeedleWalkerAnimator>();
                    case ModelId.Crossbow: return go.AddComponent<BoilerSpitterAnimator>();
                    case ModelId.Brute: return go.AddComponent<ExecutionerAnimator>();
                    case ModelId.Buggy: return go.AddComponent<WhiteoutRaiderAnimator>();
                    default: return go.AddComponent<BlackReactorAnimator>();
                }
            switch (model)
            {
                case ModelId.Scav: return go.AddComponent<LeechlingAnimator>();
                case ModelId.Raider: return go.AddComponent<MireCrabAnimator>();
                case ModelId.Spearman: return go.AddComponent<ReedStalkerAnimator>();
                case ModelId.Crossbow: return go.AddComponent<BileToadAnimator>();
                case ModelId.Brute: return go.AddComponent<SporeBruteAnimator>();
                case ModelId.Buggy: return go.AddComponent<FleshEngineAnimator>();
                default: return go.AddComponent<MireMotherAnimator>();
            }
        }

        static MutantVisual Build(Bundle b, CreatureInfo info, Transform parent)
        {
            int n = info.nodeCount;
            var ts = new Transform[n];
            var lod0 = new List<Renderer>();
            var lod1 = new List<Renderer>();
            for (int k = 0; k < n; k++)
            {
                var nd = b.data.nodes[info.root + k];
                var go = new GameObject(nd.name);
                var t = go.transform;
                t.SetParent(k == 0 ? parent : ts[nd.parent - info.root], false);
                if (k == 0) { t.localPosition = Vector3.zero; t.localRotation = Quaternion.identity; t.localScale = Vector3.one; }
                else
                {
                    t.localPosition = V3(nd.position, Vector3.zero);
                    t.localRotation = nd.rotation != null && nd.rotation.Length >= 4
                        ? new Quaternion(nd.rotation[0], nd.rotation[1], nd.rotation[2], nd.rotation[3]) : Quaternion.identity;
                    t.localScale = V3(nd.scale, Vector3.one);
                }
                ts[k] = t;
                if (nd.mesh < 0) continue;
                go.AddComponent<MeshFilter>().sharedMesh = MeshAt(b, nd.mesh);
                var r = go.AddComponent<MeshRenderer>();
                r.sharedMaterials = MaterialsFor(b, nd);
                r.shadowCastingMode = nd.castShadows && nd.lodLevel == 0 ? ShadowCastingMode.On : ShadowCastingMode.Off;
                r.receiveShadows = true;
                r.lightProbeUsage = LightProbeUsage.Off;
                r.reflectionProbeUsage = ReflectionProbeUsage.Off;
                (nd.lodLevel > 0 ? lod1 : lod0).Add(r);
            }
            var v = ts[0].gameObject.AddComponent<MutantVisual>();
            v.Init(ts, info);
            if (lod1.Count > 0)
            {
                // LOD1 (half the triangles) keeps the shadow casters of LOD0 off: shadows of small far creatures are dropped
                var g = ts[0].gameObject.AddComponent<LODGroup>();
                g.SetLODs(new[] { new LOD(Lod0ScreenHeight, lod0.ToArray()), new LOD(0.003f, lod1.ToArray()) });
                g.RecalculateBounds();
            }
            return v;
        }

        static Vector3 V3(float[] v, Vector3 fallback) => v != null && v.Length >= 3 ? new Vector3(v[0], v[1], v[2]) : fallback;

        static Material[] MaterialsFor(Bundle b, Node n)
        {
            if (n.materials == null || n.materials.Length == 0) return new[] { MaterialAt(b, 0) };
            var result = new Material[n.materials.Length];
            for (int k = 0; k < result.Length; k++) result[k] = MaterialAt(b, n.materials[k]);
            return result;
        }

        static Material MaterialAt(Bundle b, int index)
        {
            if (index < 0 || index >= b.materials.Length) return Mats.Toon;
            if (b.materials[index] != null) return b.materials[index];
            Mats.Init();
            var d = b.data.materials[index];
            var m = new Material(Mats.Toon) { name = b.prefix + d.name, enableInstancing = true };
            if (d.dust >= 0f && m.HasProperty("_DustAmount")) m.SetFloat("_DustAmount", d.dust);
            if (m.HasProperty("_WorldUV")) m.SetFloat("_WorldUV", 0f);
            var c = d.color != null && d.color.Length >= 3 ? new Color(d.color[0], d.color[1], d.color[2], d.color.Length > 3 ? d.color[3] : 1f) : Color.white;
            m.SetColor("_BaseColor", c);
            if (!string.IsNullOrEmpty(d.texture))
            {
                var tex = Resources.Load<Texture2D>(d.texture);
                if (tex != null) m.SetTexture("_BaseMap", tex);
                else Debug.LogWarning("RoadGame creature texture missing: " + d.texture);
            }
            b.materials[index] = m;
            return m;
        }

        static Mesh MeshAt(Bundle b, int index)
        {
            if (b.meshes[index] != null) return b.meshes[index];
            var d = b.data.meshes[index];
            var bytes = Resources.Load<TextAsset>(d.resource);
            if (bytes == null) throw new FileNotFoundException("Creature mesh not found", d.resource);
            try
            {
                using (var stream = new MemoryStream(bytes.bytes, false))
                using (var reader = new BinaryReader(stream))
                {
                    int count = reader.ReadInt32(), submeshes = reader.ReadInt32();
                    if (count < 1 || count > 2000000 || submeshes < 1 || submeshes > 64) throw new InvalidDataException("Invalid mesh header: " + d.resource);
                    var vertices = new Vector3[count]; var normals = new Vector3[count];
                    var colors = new Color[count]; var uv = new Vector2[count]; var prm = new Vector2[count];
                    for (int i = 0; i < count; i++)
                    {
                        vertices[i] = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
                        normals[i] = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
                        colors[i] = new Color(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
                        uv[i] = new Vector2(reader.ReadSingle(), reader.ReadSingle());
                        prm[i] = new Vector2(reader.ReadSingle(), reader.ReadSingle());
                    }
                    var mesh = new Mesh { name = d.name, indexFormat = count > 65535 ? IndexFormat.UInt32 : IndexFormat.UInt16 };
                    mesh.vertices = vertices; mesh.normals = normals; mesh.colors = colors; mesh.uv = uv; mesh.uv2 = prm;
                    mesh.subMeshCount = submeshes;
                    for (int k = 0; k < submeshes; k++)
                    {
                        int indices = reader.ReadInt32();
                        if (indices < 0 || indices % 3 != 0) throw new InvalidDataException("Invalid triangle buffer: " + d.resource);
                        var tris = new int[indices];
                        for (int j = 0; j < indices; j++)
                        {
                            tris[j] = reader.ReadInt32();
                            if (tris[j] < 0 || tris[j] >= count) throw new InvalidDataException("Triangle outside vertex buffer: " + d.resource);
                        }
                        mesh.SetTriangles(tris, k, false);
                    }
                    if (stream.Position != stream.Length) throw new InvalidDataException("Extra mesh bytes: " + d.resource);
                    mesh.RecalculateBounds();
                    mesh.UploadMeshData(true);
                    b.meshes[index] = mesh;
                    return mesh;
                }
            }
            finally { Resources.UnloadAsset(bytes); }
        }

        // the zone look (Mats.ApplyZone) changes the toon shade colour: the creature material copies follow it
        static void EnsureShadeSync()
        {
            if (ShadeSync.I != null) return;
            var go = new GameObject("MutantShadeSync") { hideFlags = HideFlags.HideInHierarchy };
            ShadeSync.I = go.AddComponent<ShadeSync>();
        }

        sealed class ShadeSync : MonoBehaviour
        {
            public static ShadeSync I;
            void LateUpdate()
            {
                if (Mats.Toon == null) return;
                var shade = Mats.Toon.GetColor("_ShadeColor");
                if (shade == lastShade) return;
                lastShade = shade;
                foreach (var b in bundles)
                    if (b.materials != null)
                        foreach (var m in b.materials) if (m != null && m.HasProperty("_ShadeColor")) m.SetColor("_ShadeColor", shade);
            }
            void OnDestroy() { if (I == this) I = null; }
        }
    }

    /// <summary>The instantiated creature: named parts and their rest pose.</summary>
    public sealed class MutantVisual : MonoBehaviour
    {
        public Mutants.CreatureInfo info;
        readonly Dictionary<string, Transform> parts = new Dictionary<string, Transform>();
        Transform[] all;
        Vector3[] restPos, restScale;
        Quaternion[] restRot;

        public void Init(Transform[] ts, Mutants.CreatureInfo i)
        {
            info = i;
            all = ts;
            restPos = new Vector3[ts.Length]; restRot = new Quaternion[ts.Length]; restScale = new Vector3[ts.Length];
            for (int k = 0; k < ts.Length; k++)
            {
                restPos[k] = ts[k].localPosition; restRot[k] = ts[k].localRotation; restScale[k] = ts[k].localScale;
                if (k > 0 && !parts.ContainsKey(ts[k].name)) parts.Add(ts[k].name, ts[k]);
            }
        }

        public Transform Part(string name) => parts.TryGetValue(name, out var t) ? t : null;
        public IEnumerable<string> PartNames => parts.Keys;

        public void ResetPose()
        {
            if (all == null) return;
            for (int k = 1; k < all.Length; k++)
                if (all[k] != null) { all[k].localPosition = restPos[k]; all[k].localRotation = restRot[k]; all[k].localScale = restScale[k]; }
            transform.localRotation = Quaternion.identity;
            transform.localPosition = Vector3.zero;
        }
    }

    /// <summary>
    /// Procedural animation of one creature. The Enemy calls Tick every frame it lives (after its AI step), so the wind-up,
    /// the strike and the shots line up with the frames the game deals damage in; death runs on its own Update.
    /// </summary>
    public abstract class MutantAnimator : MonoBehaviour
    {
        protected struct P
        {
            public Transform t;
            public Vector3 pos, scl;
            public Quaternion rot;
            public void R(Quaternion q) { if (t != null) t.localRotation = rot * q; }
            public void R(float x, float y, float z) { if (t != null) t.localRotation = rot * Quaternion.Euler(x, y, z); }
            public void T(Vector3 d) { if (t != null) t.localPosition = pos + d; }
            public void S(Vector3 s) { if (t != null) t.localScale = Vector3.Scale(scl, s); }
            public void S(float s) { if (t != null) t.localScale = scl * s; }
            public Vector3 World => t != null ? t.position : Vector3.zero;
        }

        protected Enemy enemy;
        protected MutantVisual v;
        protected SpawnPoint spawn;
        protected float phase, tm, deathT = -1f, lastHeading, turnRate, yawLag, recoverDur = 0.35f;
        protected float speed, moving, wind, rec, hitK;
        protected int strikeCount;
        protected Vector3 hitDir;
        /// <summary>Seconds the death animation takes.</summary>
        protected virtual float DeathDuration => 0.7f;
        /// <summary>Max degrees per second the body follows the logical heading (heavy creatures turn slower).</summary>
        protected virtual float VisualTurnRate => 0f;

        public MutantVisual Visual => v;
        /// <summary>Ground radius of the model in metres: the furthest vertex from the root in the rest pose.</summary>
        public float Footprint => v != null && v.info != null ? v.info.footprint * v.transform.lossyScale.x : 1f;
        public bool Dying => deathT >= 0f;
        public float DeathProgress => deathT < 0f ? 0f : Mathf.Clamp01(deathT / DeathDuration);
        /// <summary>Visual strikes / shots played (tests).</summary>
        public int Strikes => strikeCount;

        public void Bind(MutantVisual vis, SpawnPoint sp)
        {
            v = vis;
            spawn = sp;
            OnBind();
        }

        protected abstract void OnBind();
        protected abstract void Animate(float dt);
        protected abstract void Die(float k);

        protected P Get(string name)
        {
            var tr = v != null ? v.Part(name) : null;
            return tr == null ? default : new P { t = tr, pos = tr.localPosition, rot = tr.localRotation, scl = tr.localScale };
        }

        public void Attach(Enemy e) { enemy = e; lastHeading = e.AnimHeading; }

        public void Tick(float dt)
        {
            if (enemy == null) enemy = GetComponent<Enemy>();
            if (v == null || enemy == null) return;
            if (deathT >= 0f) return;
            tm += dt;
            speed = enemy.AnimSpeed;
            moving = Mathf.Clamp01(speed / Mathf.Max(0.5f, Mathf.Min(enemy.spec.speed, 7f)));
            wind = enemy.AnimWindup;
            float since = Time.time - enemy.AnimStrikeTime;
            rec = since >= 0f && since < recoverDur ? since / recoverDur : -1f;
            float hs = Time.time - enemy.lastHitTime;
            hitK = hs >= 0f && hs < 0.28f ? Mathf.Sin(Mathf.Clamp01(hs / 0.28f) * Mathf.PI) : 0f;
            float h = enemy.AnimHeading;
            float d = Mathf.DeltaAngle(lastHeading, h);
            lastHeading = h;
            turnRate = Mathf.Lerp(turnRate, dt > 1e-5f ? d / dt : 0f, Mathf.Clamp01(dt * 8f));
            if (VisualTurnRate > 0f)
            {
                // the root has already turned: the body lags behind and catches up at its own pace
                yawLag = Mathf.Clamp(Mathf.MoveTowards(yawLag - d, 0f, VisualTurnRate * dt), -75f, 75f);
                v.transform.localRotation = Quaternion.Euler(0f, yawLag, 0f);
            }
            Animate(dt);
        }

        void Update()
        {
            if (enemy == null || v == null) return;
            if (enemy.dead && !enemy.beingEaten)
            {
                if (deathT < 0f) deathT = 0f;
                if (deathT <= DeathDuration + 0.05f)
                {
                    deathT += Time.deltaTime;
                    Die(Ease(Mathf.Clamp01(deathT / DeathDuration)));
                }
            }
        }

        public void OnDeath() { if (deathT < 0f) deathT = 0f; }

        public void ResetPose()
        {
            deathT = -1f;
            yawLag = 0f;
            phase = UnityEngine.Random.value * 6.28f;
            if (v != null) v.ResetPose();
            if (enemy != null) lastHeading = enemy.AnimHeading;
            OnReset();
        }

        protected virtual void OnReset() { }
        public virtual void OnStrike(bool landed) { strikeCount++; }
        public virtual void OnShot() { strikeCount++; }
        public virtual void OnHit(Vector3 source) { hitDir = transform.InverseTransformDirection((transform.position - source).normalized); }

        // ------------------------------------------------------------------ helpers
        protected static float Ease(float k) { k = Mathf.Clamp01(k); return k * k * (3f - 2f * k); }
        protected static float EaseOut(float k) { k = Mathf.Clamp01(k); return 1f - (1f - k) * (1f - k); }
        /// <summary>Wind-up split into an anticipation (0..a: rises 0 -> 1) and a strike (a..1: 1 -> 0) curve.</summary>
        protected static void Split(float w, float a, out float antic, out float strike)
        {
            if (w < 0f) { antic = 0f; strike = 0f; return; }
            antic = Ease(w / a);
            strike = w > a ? Ease((w - a) / (1f - a)) : 0f;
        }
        protected static Quaternion Yaw(float a) => Quaternion.AngleAxis(a, Vector3.up);
        protected static Quaternion Pitch(float a) => Quaternion.AngleAxis(a, Vector3.right);
        protected static Quaternion Roll(float a) => Quaternion.AngleAxis(a, Vector3.forward);
        /// <summary>A leg splayed to the side (side = +1 right, -1 left): swing moves the foot forward, lift raises it.</summary>
        protected static Quaternion SideLeg(float swing, float lift, float side) => Yaw(-swing * side) * Roll(lift * side);
        protected Vector3 PlayerLocal()
        {
            if (Game.I == null || Game.I.player == null) return Vector3.forward;
            return transform.InverseTransformPoint(Game.I.player.Pos);
        }
        protected void Dust(Vector3 p, float size)
        {
            if (Game.I == null || Game.I.fx == null) return;
            Game.I.fx.Slam(p, size);
        }
    }

    // ========================================================================================== 01 Leechling (Scav)
    public sealed class LeechlingAnimator : MutantAnimator
    {
        P body, head, mouth, rear;
        readonly P[] legs = new P[4];
        static readonly float[] Side = { 1f, -1f, 1f, -1f };

        protected override void OnBind()
        {
            body = Get("Body"); head = Get("Head"); mouth = Get("Mouth"); rear = Get("Rear");
            legs[0] = Get("LegFR"); legs[1] = Get("LegFL"); legs[2] = Get("LegBR"); legs[3] = Get("LegBL");
        }

        protected override void Animate(float dt)
        {
            phase += dt * (2.2f + speed * 2.4f);
            float m = moving;
            Split(wind, 0.72f, out float antic, out float strike);
            float rearUp = antic * (1f - strike);
            float lunge = strike;
            if (rec >= 0f) lunge = 1f - Ease(rec);
            float snap = wind >= 0f ? strike : (rec >= 0f ? 1f - Ease(rec * 1.6f) : 0f);
            float wig = Mathf.Sin(phase) * 13f * m + Mathf.Sin(tm * 1.3f) * 3f * (1f - m);
            float bob = Mathf.Abs(Mathf.Sin(phase)) * 0.028f * m;
            body.R(Pitch(-3f * rearUp + hitK * 6f) * Yaw(wig * 0.25f) * Roll(Mathf.Sin(phase * 2f) * 2.5f * m));
            body.T(new Vector3(0f, bob, -0.10f * rearUp + 0.30f * lunge - 0.10f * hitK));
            head.R(Pitch(-24f * rearUp + 14f * lunge + hitK * 8f) * Yaw(wig + hitK * 10f));
            rear.R(Pitch(5f * rearUp) * Yaw(-wig * 1.1f));
            float gape = 1f + 0.05f * Mathf.Sin(tm * 2.3f) + 0.36f * rearUp - 0.32f * snap;
            mouth.S(new Vector3(gape, gape, 1f + 0.2f * rearUp));
            for (int i = 0; i < 4; i++)
            {
                float ph = phase + ((i == 0 || i == 3) ? 0f : Mathf.PI);
                float sw = Mathf.Sin(ph) * 26f * m;
                float lift = Mathf.Max(0f, Mathf.Cos(ph)) * 24f * m + 10f * rearUp * (i < 2 ? 1f : 0f);
                legs[i].R(SideLeg(sw, lift, Side[i]));
            }
        }

        protected override void Die(float k)
        {
            body.R(Roll(168f * k) * Pitch(-6f * k));
            body.T(new Vector3(0f, 0.06f * Mathf.Sin(k * Mathf.PI), 0f));
            head.R(Pitch(18f * k) * Yaw(14f * k));
            rear.R(Yaw(-18f * k));
            mouth.S(new Vector3(1.15f, 1.15f, 1f));
            for (int i = 0; i < 4; i++) legs[i].R(SideLeg(10f * Side[i], 55f * k, Side[i]));
        }
    }

    // ========================================================================================== 02 Mire Crab (Raider)
    public sealed class MireCrabAnimator : MutantAnimator
    {
        P body, clawR, pincerR, fingerR, clawL, pincerL, fingerL;
        readonly P[] legs = new P[4];
        static readonly float[] Side = { 1f, 1f, -1f, -1f };

        protected override void OnBind()
        {
            body = Get("Body");
            legs[0] = Get("Leg1R"); legs[1] = Get("Leg2R"); legs[2] = Get("Leg1L"); legs[3] = Get("Leg2L");
            clawR = Get("ClawR"); pincerR = Get("PincerR"); fingerR = Get("FingerR");
            clawL = Get("ClawL"); pincerL = Get("PincerL"); fingerL = Get("FingerL");
            recoverDur = 0.3f;
        }

        protected override void Animate(float dt)
        {
            phase += dt * (3.0f + speed * 2.2f);
            float m = moving;
            bool ready = enemy.AnimAttackState;
            Split(wind, 0.55f, out float antic, out float strike);
            float raise = ready ? 0.45f : 0f;
            raise = Mathf.Max(raise, antic * (1f - strike));
            float slam = strike;
            if (rec >= 0f) slam = 1f - Ease(rec);
            for (int i = 0; i < 4; i++)
            {
                // alternating tetrapod: right-front + left-back, then right-back + left-front
                float ph = phase + ((i == 0 || i == 3) ? 0f : Mathf.PI);
                float sw = Mathf.Sin(ph) * 22f * m;
                float lift = Mathf.Max(0f, Mathf.Cos(ph)) * 20f * m;
                legs[i].R(SideLeg(sw, lift, Side[i]));
            }
            float sway = Mathf.Sin(phase) * 3f * m;
            body.R(Pitch(-4f * raise + 6f * slam + hitK * 7f) * Roll(sway + hitDir.x * hitK * 6f));
            body.T(new Vector3(0f, Mathf.Abs(Mathf.Sin(phase)) * 0.03f * m - 0.04f * slam, 0.12f * slam - 0.08f * hitK));
            float idle = Mathf.Sin(tm * 1.7f);
            clawR.R(Pitch(-10f - 38f * raise + 46f * slam + idle * 3f) * Yaw(-12f * raise + 10f * slam));
            pincerR.R(Pitch(-14f * raise + 10f * slam) * Roll(idle * 4f));
            fingerR.R(Pitch(-30f * raise + 6f * slam + (1f + idle) * 3f));
            clawL.R(Pitch(-8f - 16f * raise + idle * 4f + hitK * 10f) * Yaw(10f * raise));
            pincerL.R(Roll(-idle * 5f));
            fingerL.R(Pitch(-6f - 10f * Mathf.Max(0f, Mathf.Sin(tm * 3.1f))));
        }

        protected override void Die(float k)
        {
            body.R(Roll(-176f * k) * Pitch(8f * k));
            body.T(new Vector3(0f, 0.55f * Mathf.Sin(k * Mathf.PI) * 0.6f + 0.05f * k, 0f));
            for (int i = 0; i < 4; i++) legs[i].R(SideLeg(-8f * Side[i], 62f * k, Side[i]));
            clawR.R(Pitch(-50f * k) * Yaw(-20f * k));
            fingerR.R(Pitch(-20f * k));
            clawL.R(Pitch(-40f * k) * Yaw(20f * k));
        }
    }

    // ========================================================================================== 03 Reed Stalker (Spearman)
    public sealed class ReedStalkerAnimator : MutantAnimator
    {
        P pelvis, torso, head, jaw, thighR, thighL, shinR, shinL, armSpike, spike, armClaw, handClaw;

        protected override void OnBind()
        {
            pelvis = Get("Pelvis"); torso = Get("Torso"); head = Get("Head"); jaw = Get("Jaw");
            thighR = Get("ThighR"); thighL = Get("ThighL"); shinR = Get("ShinR"); shinL = Get("ShinL");
            armSpike = Get("ArmSpike"); spike = Get("Spike"); armClaw = Get("ArmClaw"); handClaw = Get("HandClaw");
            recoverDur = 0.4f;
        }

        protected override void Animate(float dt)
        {
            phase += dt * (2.0f + speed * 1.6f);
            float m = moving;
            Split(wind, 0.68f, out float antic, out float strike);
            float crouch = antic * (1f - strike * 0.6f);
            float lunge = strike;
            if (rec >= 0f) { lunge = 1f - Ease(rec); crouch = 0f; }
            for (int s = 0; s < 2; s++)
            {
                float ph = phase + s * Mathf.PI;
                float sw = Mathf.Sin(ph) * 26f * m;
                float knee = Mathf.Max(0f, Mathf.Cos(ph)) * 34f * m;
                var thigh = s == 0 ? thighR : thighL;
                var shin = s == 0 ? shinR : shinL;
                // crouch: thighs swing forward (negative pitch), shins fold back (positive pitch)
                thigh.R(Pitch(-sw - 26f * crouch + 18f * lunge * (s == 0 ? 1f : 0.3f)));
                shin.R(Pitch(knee + 40f * crouch - 10f * lunge));
            }
            float bob = Mathf.Abs(Mathf.Cos(phase)) * 0.07f * m;
            pelvis.T(new Vector3(0f, bob - 0.26f * crouch, 0.62f * lunge));
            pelvis.R(Yaw(Mathf.Sin(phase) * 4f * m) * Roll(Mathf.Sin(phase) * 3f * m));
            float headBob = Mathf.Sin(phase * 2f) * 6f * m;
            torso.R(Pitch(-14f * crouch + 24f * lunge + hitK * -10f + Mathf.Sin(tm * 0.9f) * 1.5f));
            float scan = Mathf.Sin(tm * 0.7f) * 18f * (1f - m) * (1f - antic);
            head.R(Pitch(headBob + 10f * crouch - 8f * lunge + hitK * -14f) * Yaw(scan));
            jaw.R(Pitch(4f + 6f * Mathf.Max(0f, Mathf.Sin(tm * 2.3f)) * (1f - m) + 26f * antic * (1f - strike) + 10f * hitK));
            armSpike.R(Pitch(-58f * crouch + 30f * lunge + Mathf.Sin(phase) * 6f * m));
            spike.R(Pitch(-20f * crouch + 14f * lunge));
            armClaw.R(Pitch(Mathf.Sin(phase + 1f) * 12f * m - 20f * crouch) * Roll(-6f));
            handClaw.R(Pitch(18f + 10f * Mathf.Sin(tm * 1.9f)));
        }

        protected override void Die(float k)
        {
            pelvis.T(new Vector3(0.10f * k, -0.95f * k, 0f));
            pelvis.R(Roll(-72f * k) * Pitch(10f * k));
            thighR.R(Pitch(-70f * k)); thighL.R(Pitch(-50f * k));
            shinR.R(Pitch(95f * k)); shinL.R(Pitch(80f * k));
            torso.R(Pitch(30f * k));
            head.R(Pitch(25f * k) * Yaw(20f * k));
            jaw.R(Pitch(28f * k));
            armSpike.R(Pitch(20f * k) * Roll(15f * k));
            armClaw.R(Pitch(30f * k));
        }
    }

    // ========================================================================================== 04 Bile Toad (Crossbow)
    public sealed class BileToadAnimator : MutantAnimator
    {
        P body, head, sac, armR, armL, thighR, thighL, shinR, shinL;
        float shotT = -9f;

        protected override void OnBind()
        {
            body = Get("Body"); head = Get("Head"); sac = Get("Sac");
            armR = Get("ArmR"); armL = Get("ArmL"); thighR = Get("ThighR"); thighL = Get("ThighL"); shinR = Get("ShinR"); shinL = Get("ShinL");
        }

        public override void OnShot() { base.OnShot(); shotT = 0f; }

        protected override void Animate(float dt)
        {
            phase += dt * (1.6f + speed * 2.0f);
            shotT += dt;
            float m = moving;
            float swell = wind >= 0f ? Ease(wind) : 0f;
            float spit = shotT < 0.45f ? 1f - Ease(shotT / 0.45f) : 0f;
            float breathe = Mathf.Sin(tm * 4.4f) * 0.05f + Mathf.Sin(tm * 1.3f) * 0.03f;
            float s = 1f + breathe + 0.55f * swell - 0.38f * spit * (1f - swell);
            sac.S(new Vector3(s, s * 0.96f, s));
            // aim the head up at the car while swelling; recoil when it spits
            var pl = PlayerLocal();
            float aimYaw = Mathf.Clamp(Mathf.Atan2(pl.x, pl.z) * Mathf.Rad2Deg, -20f, 20f) * (enemy.AnimAttackState ? 1f : 0f);
            head.R(Pitch(-12f * swell + 14f * spit + hitK * -8f + Mathf.Sin(phase * 2f) * 3f * m) * Yaw(aimYaw));
            float heave = Mathf.Max(0f, Mathf.Sin(phase)) * m;
            body.R(Pitch(-5f * swell + 4f * spit - 4f * heave + hitK * 5f) * Roll(Mathf.Sin(phase * 0.5f) * 3f * m));
            body.T(new Vector3(0f, 0.06f * heave + 0.02f * swell - 0.05f * hitK, 0.08f * heave));
            body.S(new Vector3(1f + 0.05f * hitK, 1f - 0.08f * hitK, 1f + 0.05f * hitK));
            for (int i = 0; i < 2; i++)
            {
                float side = i == 0 ? 1f : -1f;
                float ph = phase + i * Mathf.PI;
                var arm = i == 0 ? armR : armL;
                arm.R(SideLeg(Mathf.Sin(ph) * 22f * m, Mathf.Max(0f, Mathf.Cos(ph)) * 22f * m, side));
                var thigh = i == 0 ? thighR : thighL;
                var shin = i == 0 ? shinR : shinL;
                float push = Mathf.Max(0f, Mathf.Sin(ph + Mathf.PI * 0.5f)) * m;
                thigh.R(SideLeg(-18f * push, 10f * push, side));
                shin.R(SideLeg(10f * push, -8f * push, side));
            }
        }

        protected override void Die(float k)
        {
            sac.S(Mathf.Lerp(1f, 0.32f, k));
            body.T(new Vector3(0f, -0.24f * k, 0f));
            body.R(Roll(14f * k) * Pitch(6f * k));
            head.R(Pitch(22f * k));
            armR.R(SideLeg(10f, -18f * k, 1f)); armL.R(SideLeg(10f, -18f * k, -1f));
            thighR.R(SideLeg(-30f * k, -10f * k, 1f)); thighL.R(SideLeg(-30f * k, -10f * k, -1f));
        }
    }

    // ========================================================================================== 05 Spore Brute (Brute)
    public sealed class SporeBruteAnimator : MutantAnimator
    {
        P pelvis, torso, armR, clubR, armL, handL, thighR, thighL, shinR, shinL;
        protected override float DeathDuration => 0.95f;
        protected override float VisualTurnRate => 160f;

        protected override void OnBind()
        {
            pelvis = Get("Pelvis"); torso = Get("Torso"); armR = Get("ArmR"); clubR = Get("ClubR"); armL = Get("ArmL"); handL = Get("HandL");
            thighR = Get("ThighR"); thighL = Get("ThighL"); shinR = Get("ShinR"); shinL = Get("ShinL");
            recoverDur = 0.55f;
        }

        public override void OnStrike(bool landed)
        {
            base.OnStrike(landed);
            // the club hits the ground in front: a dust ring under it
            if (clubR.t != null) Dust(clubR.t.TransformPoint(new Vector3(0.05f, -0.9f, 0.3f)), 1.6f);
        }

        protected override void Animate(float dt)
        {
            phase += dt * (1.3f + speed * 1.5f);
            float m = moving;
            Split(wind, 0.78f, out float antic, out float strike);
            float lift = antic * (1f - strike);
            float smash = strike;
            if (rec >= 0f) { smash = 1f - Ease(rec); lift = 0f; }
            for (int s = 0; s < 2; s++)
            {
                float ph = phase + s * Mathf.PI;
                var thigh = s == 0 ? thighR : thighL;
                var shin = s == 0 ? shinR : shinL;
                thigh.R(Pitch(-Mathf.Sin(ph) * 20f * m - 10f * smash) * Roll((s == 0 ? 1f : -1f) * 3f * m));
                shin.R(Pitch(Mathf.Max(0f, Mathf.Cos(ph)) * 26f * m + 14f * smash));
            }
            float sway = Mathf.Sin(phase) * 7f * m + Mathf.Sin(tm * 0.6f) * 1.5f;
            pelvis.T(new Vector3(0f, Mathf.Abs(Mathf.Cos(phase)) * 0.07f * m - 0.12f * smash, 0f));
            pelvis.R(Roll(-sway * 0.5f));
            torso.R(Pitch(-16f * lift + 24f * smash + hitK * -9f + Mathf.Sin(tm * 1.1f) * 1.2f) * Roll(sway) * Yaw(10f * lift - 6f * smash));
            // the club arm: pendulum while walking, raised overhead (negative pitch) for the smash, slammed down
            float pend = Mathf.Sin(phase - 0.6f) * 14f * m;
            armR.R(Pitch(pend - 150f * lift + 20f * smash) * Roll(18f * lift));
            clubR.R(Pitch(-30f * lift - 10f * smash));
            armL.R(Pitch(-pend * 0.8f - 20f * lift + hitK * 14f) * Roll(-8f));
            handL.R(Pitch(-24f + 8f * Mathf.Sin(tm * 1.6f)));
        }

        protected override void Die(float k)
        {
            pelvis.T(new Vector3(0f, -0.65f * k, 0.2f * k));
            thighR.R(Pitch(-60f * k)); thighL.R(Pitch(-48f * k));
            shinR.R(Pitch(85f * k)); shinL.R(Pitch(72f * k));
            torso.R(Pitch(58f * k) * Roll(10f * k));
            armR.R(Pitch(-20f * k) * Roll(25f * k));
            armL.R(Pitch(-40f * k));
        }
    }

    // ========================================================================================== 06 Flesh Engine (Buggy)
    public sealed class FleshEngineAnimator : MutantAnimator
    {
        P body, engine, eye, jaw, steerR, steerL, wheelFR, wheelFL, wheelBR, wheelBL;
        float spinF, spinB, blinkT = 2f, shotT = -9f, pulse;
        const float FrontR = 0.52f, RearR = 0.58f;

        protected override void OnBind()
        {
            body = Get("Body"); engine = Get("Engine"); eye = Get("Eye"); jaw = Get("Jaw");
            steerR = Get("SteerFR"); steerL = Get("SteerFL");
            wheelFR = Get("WheelFR"); wheelFL = Get("WheelFL"); wheelBR = Get("WheelBR"); wheelBL = Get("WheelBL");
        }

        public override void OnShot() { base.OnShot(); shotT = 0f; }

        protected override void Animate(float dt)
        {
            float sp = speed;
            spinF += sp * dt / FrontR * Mathf.Rad2Deg;
            spinB += sp * dt / RearR * Mathf.Rad2Deg;
            wheelFR.R(Pitch(spinF)); wheelFL.R(Pitch(spinF));
            wheelBR.R(Pitch(spinB)); wheelBL.R(Pitch(spinB));
            float steer = Mathf.Clamp(turnRate * 0.22f, -28f, 28f);
            steerR.R(Yaw(steer)); steerL.R(Yaw(steer));
            // the living engine: a heartbeat (two beats) that races while it fights
            bool engaged = enemy.Engaged;
            pulse += dt * (engaged ? 2.4f : 1.1f);
            float beat = Mathf.Pow(Mathf.Max(0f, Mathf.Sin(pulse * Mathf.PI * 2f)), 6f) + 0.6f * Mathf.Pow(Mathf.Max(0f, Mathf.Sin(pulse * Mathf.PI * 2f - 0.9f)), 6f);
            engine.S(1f + 0.10f * beat);
            // the jaw opens for the wind-up, stays open through the burst, then snaps shut
            shotT += dt;
            float open = wind >= 0f ? Ease(wind) : 0f;
            if (enemy.AnimBurst || shotT < 0.12f) open = 1f;
            else if (shotT < 0.4f) open = Mathf.Max(open, 1f - Ease((shotT - 0.12f) / 0.28f));
            float chomp = Mathf.Max(0f, Mathf.Sin(tm * 2.1f)) * 5f * (engaged ? 1f : 0.5f);
            jaw.R(Pitch(chomp + 28f * open + (enemy.AnimBurst ? Mathf.Sin(tm * 40f) * 3f : 0f)));
            // the eye watches the car while it fights; blinks now and then
            var pl = PlayerLocal();
            float ey = engaged ? Mathf.Clamp(Mathf.Atan2(pl.x, pl.z) * Mathf.Rad2Deg, -30f, 30f) : Mathf.Sin(tm * 0.5f) * 15f;
            blinkT -= dt;
            if (blinkT < -0.14f) blinkT = UnityEngine.Random.Range(1.5f, 4f);
            float lid = blinkT < 0f ? 0.15f : 1f - 0.5f * hitK;
            eye.R(Yaw(ey));
            eye.S(new Vector3(1f, lid, 1f));
            float acc = Mathf.Clamp(sp * 0.4f, 0f, 4f);
            float bounce = Mathf.Sin(tm * 11f) * 0.012f * Mathf.Clamp01(sp / 4f);
            body.R(Pitch(-acc * 0.6f - 3f * open + hitK * -5f) * Roll(-steer * 0.12f + Mathf.Sin(tm * 9f) * 0.6f * Mathf.Clamp01(sp / 4f)));
            body.T(new Vector3(0f, bounce + 0.008f * beat, -0.06f * hitK));
        }

        protected override void Die(float k)
        {
            jaw.R(Pitch(36f * k));
            eye.S(new Vector3(1f, Mathf.Lerp(1f, 0.12f, k), 1f));
            engine.S(Mathf.Lerp(1f, 0.72f, k));
            body.R(Roll(11f * k) * Pitch(-5f * k));
            body.T(new Vector3(0f, -0.14f * k, 0f));
            steerR.R(Yaw(20f * k)); steerL.R(Yaw(20f * k));
        }
    }

    // ========================================================================================== 07 Mire Mother (BossBaron)
    public sealed class MireMotherAnimator : MutantAnimator
    {
        P body, core, crown;
        readonly P[] legs = new P[4], shins = new P[4];
        static readonly string[] Names = { "FR", "FL", "BR", "BL" };
        static readonly float[] SideX = { 1f, -1f, 1f, -1f };
        int stompLeg;
        protected override float DeathDuration => 1.0f;
        protected override float VisualTurnRate => 70f;

        protected override void OnBind()
        {
            body = Get("Body"); core = Get("Core"); crown = Get("Crown");
            for (int i = 0; i < 4; i++) { legs[i] = Get("Leg" + Names[i]); shins[i] = Get("Shin" + Names[i]); }
            recoverDur = 0.5f;
        }

        public override void OnStrike(bool landed)
        {
            base.OnStrike(landed);
            var foot = shins[stompLeg].t != null ? shins[stompLeg].t.TransformPoint(new Vector3(0.4f * SideX[stompLeg], -2.3f, 0.4f)) : transform.position;
            Dust(foot, 2.6f);
            if (Game.I != null && Game.I.cameraRig != null) Game.I.cameraRig.Shake(0.25f);
            stompLeg = 1 - stompLeg;
        }

        protected override void Animate(float dt)
        {
            phase += dt * (0.9f + speed * 0.75f);
            float m = moving;
            bool special = enemy.AnimSpecial && enemy.AnimSpecialKind == 1;
            float st = enemy.AnimSpecialT;
            // the slam special: rears up on the hind legs for 1.1 s, then both front legs come down on the telegraph
            float rear = special ? Ease(Mathf.Clamp01(st / 0.95f)) : 0f;
            float slamDown = special && st > 0.95f ? Ease((st - 0.95f) / 0.15f) : 0f;
            Split(wind, 0.7f, out float antic, out float strike);
            float stompUp = antic * (1f - strike);
            float stomp = strike;
            if (rec >= 0f) { stomp = 1f - Ease(rec); stompUp = 0f; }
            for (int i = 0; i < 4; i++)
            {
                bool frontLeg = i < 2;
                // heavy gait: one leg at a time (FR, BL, FL, BR)
                float ph = phase - (i == 0 ? 0f : i == 3 ? 0.5f : i == 1 ? 1f : 1.5f) * Mathf.PI;
                float swing = Mathf.Sin(ph) * 14f * m;
                float lift = Mathf.Max(0f, Mathf.Cos(ph)) * 16f * m;
                if (frontLeg)
                {
                    lift += 58f * rear * (1f - slamDown) - 8f * slamDown;
                    if (i == stompLeg) lift += 46f * stompUp - 10f * stomp;
                }
                else lift -= 10f * rear * (1f - slamDown);
                float fwd = frontLeg ? 1f : -1f;
                legs[i].R(Pitch(-swing * fwd - (frontLeg ? 12f : 0f) * rear * (1f - slamDown)) * Roll(lift * SideX[i]));
                shins[i].R(Roll(-lift * 0.55f * SideX[i]));
            }
            float breathe = Mathf.Sin(tm * 2.1f);
            body.T(new Vector3(0f, 0.07f * breathe + 0.45f * rear * (1f - slamDown) - 0.18f * slamDown - 0.08f * stomp, -0.3f * rear * (1f - slamDown)));
            body.R(Pitch(-14f * rear * (1f - slamDown) + 5f * slamDown + 4f * stomp + hitK * -2.5f + Mathf.Sin(phase) * 1.5f * m)
                   * Roll(Mathf.Sin(phase * 0.5f) * 2.5f * m + (stompUp - stomp) * 3f * (stompLeg == 0 ? -1f : 1f) + hitK * Mathf.Sin(tm * 40f) * 1.2f));
            float rate = enemy.Engaged ? 1.8f : 0.9f;
            if (special) rate = 3.4f;
            float beat = Mathf.Pow(Mathf.Max(0f, Mathf.Sin(tm * rate * Mathf.PI * 2f)), 5f);
            core.S(1f + 0.07f * beat + 0.08f * rear);
            crown.R(Pitch(Mathf.Sin(tm * 0.8f) * 2.5f - 10f * rear) * Roll(Mathf.Sin(tm * 0.6f + 1f) * 2.5f));
            crown.S(1f + 0.06f * rear);
        }

        protected override void Die(float k)
        {
            body.T(new Vector3(0f, -1.25f * k, 0f));
            body.R(Pitch(7f * k) * Roll(-4f * k));
            for (int i = 0; i < 4; i++)
            {
                legs[i].R(Roll(-24f * k * SideX[i]));
                shins[i].R(Roll(30f * k * SideX[i]));
            }
            crown.R(Pitch(22f * k));
            core.S(Mathf.Lerp(1f, 0.68f, k));
        }
    }
}
