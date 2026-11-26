using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

namespace RoadGame
{
    /// <summary>
    /// The Blender art passes replace generated render meshes, not gameplay objects. Keeping the existing
    /// transforms/renderers preserves gates, repair glows and roof fading; live targets receive their edited
    /// meshes when spawned instead of leaving frozen destructible copies in the world.
    /// Bundles: Dust Flats v13 (first zone: statics + destructible props), Toxic Wetlands (second zone: statics,
    /// props, enemies, buggies and the boss) and Ashen Winter (third zone: statics and props; its enemies come from
    /// their own creature bundle, Mutants.cs). All use the IDs of the 2026-11-17 snapshot, so the generated hierarchy
    /// is captured once, before any bundle changes it.
    /// </summary>
    public sealed class ImportedLevel : MonoBehaviour
    {
        public const string ManifestResource = "Levels/DustFlatsV13/manifest";
        public const string WetlandsManifestResource = "Levels/ToxicWetlandsZ1/manifest";
        public const string AshenManifestResource = "Levels/AshenWinterZ2/manifest";
        static readonly string[] BundleResources = { ManifestResource, WetlandsManifestResource, AshenManifestResource };
        const long MeshBatchBytes = 4L * 1024 * 1024;
        public static bool SuppressIntegration;
        /// <summary>The first zone's bundle (Dust Flats v13).</summary>
        public static ImportedLevel Active { get; private set; }
        /// <summary>The second zone's bundle (Toxic Wetlands).</summary>
        public static ImportedLevel Wetlands { get; private set; }
        /// <summary>The third zone's bundle (Ashen Winter).</summary>
        public static ImportedLevel Ashen { get; private set; }
        public bool Applied { get; private set; }
        public int Zone => data != null ? data.zone : 0;
        public string Resource { get; private set; }
        public int AppliedActorCount { get; private set; }
        public int ReplacedRenderers { get; private set; }
        public int AddedRenderers { get; private set; }
        public int ReplacedStaticCount { get; private set; }
        public int AddedStaticCount { get; private set; }
        public int AppliedPropCount { get; private set; }
        public int UnmappedOriginalCount { get; private set; }
        public int PreloadedStaticMeshCount { get; private set; }
        public int StaticMeshPreloadBatches { get; private set; }
        public int ReleasedStaticMeshCount { get; private set; }
        public int ImportedPropCount => spawnRoots.Count;
        public string SourceFile => data != null ? data.sourceFile : "";

        [Serializable] public sealed class Manifest
        {
            public int version;
            public int zone;
            public string sourceFile;
            public Node[] nodes;
            public MeshInfo[] meshes;
            public MaterialInfo[] materials;
            public string[] replacementNodeIds;
            // Toxic Wetlands: first-zone perimeter meshes that reach into the second zone are cut back at clipZone0MaxZ
            public string[] clipZone0;
            public float clipZone0MaxZ;
        }
        [Serializable] public sealed class Node
        {
            public string id, name, originalName, originalParentId, sourcePath, category, lodOf;
            public int parent = -1, mesh = -1, spawnId = -1, lodLevel, colliderMesh = -1;
            public int[] materials;
            public float[] position, rotation, scale;
            public bool active = true, rendererEnabled = true, spawnRoot, isRoof, isLod, colliderConvex;
            public bool fadeOnlyBelow = true, castShadows = true;
            // Ashen Winter: a hidden original whose colliders go too (the old canopy's posts under the bunker)
            public bool disableColliders;
            public float minAlpha = 0.2f, lodScreenSize;
        }
        [Serializable] public sealed class MeshInfo
        {
            public string name, resource, sourceId;
            public int vertexCount, triangles, submeshes;
        }
        [Serializable] public sealed class MaterialInfo
        {
            public string name, unityId, shader, texture;
            public float[] color, tiling, offset;
            public float worldUV, alpha = 1f, roughness = 0.75f, metallic;
            public bool unlit, water, additive;
            // Toxic Wetlands additions (empty / negative = the Dust Flats rules by material name)
            public string baseKind;
            public float dust = -1f, aoFloor = -1f;
            public int zone;
        }

        Manifest data;
        Mesh[] meshes;
        Material[] materials;
        Transform[] resolved;
        bool[] builtStatic;
        Color lastShade;
        readonly Dictionary<int, int> spawnRoots = new Dictionary<int, int>();
        readonly Dictionary<int, List<int>> spawnNodes = new Dictionary<int, List<int>>();
        readonly Dictionary<Renderer, List<Renderer>> lodRenderers = new Dictionary<Renderer, List<Renderer>>();
        readonly Dictionary<string, int> nodeById = new Dictionary<string, int>();
        readonly Dictionary<ModelId, int> modelTemplates = new Dictionary<ModelId, int>();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { Active = null; Wetlands = null; Ashen = null; SuppressIntegration = false; }

        /// <summary>The applied bundle for a zone index, or null.</summary>
        public static ImportedLevel ForZone(int zone)
        {
            var level = zone == 0 ? Active : zone == 1 ? Wetlands : zone == 2 ? Ashen : null;
            return level != null && level.Applied ? level : null;
        }

        /// <summary>The generated hierarchy before any bundle changes it (preorder IDs of the snapshot export).</summary>
        sealed class Original
        {
            public readonly Dictionary<string, Transform> ids = new Dictionary<string, Transform>();
            public readonly Dictionary<string, List<Transform>> paths = new Dictionary<string, List<Transform>>();
            public int count;

            public static Original Capture(Transform root)
            {
                var all = new List<Transform>();
                CaptureOriginal(root, all);
                var o = new Original { count = all.Count };
                for (int i = 0; i < all.Count; i++)
                {
                    o.ids.Add("node_" + i.ToString("000000"), all[i]);
                    string path = HierarchyPath(all[i], root);
                    if (!o.paths.TryGetValue(path, out var list)) o.paths.Add(path, list = new List<Transform>());
                    list.Add(all[i]);
                }
                return o;
            }
        }

        /// <summary>Call after the original generator has finished, before adding other world children.</summary>
        public static bool TryApply(World world)
        {
            if (SuppressIntegration || world == null) return false;
            Original original = null;
            bool any = false;
            var present = world.GetComponents<ImportedLevel>();
            foreach (string resource in BundleResources)
            {
                ImportedLevel existing = null;
                foreach (var c in present) if (c.Resource == resource || (c.Resource == null && resource == ManifestResource)) existing = c;
                if (existing != null && existing.Applied) { Register(existing); any = true; continue; }
                var asset = Resources.Load<TextAsset>(resource);
                if (asset == null) continue;
                if (original == null) original = Original.Capture(world.transform);
                var imported = existing != null ? existing : world.gameObject.AddComponent<ImportedLevel>();
                imported.Resource = resource;
                try
                {
                    imported.Load(asset.text);
                    imported.ApplyWorld(world, original);
                    imported.Applied = true;
                    Register(imported);
                    any = true;
                    if (imported.Zone == 1 && Active != null && Active.Applied && imported.data.clipZone0 != null)
                        Active.ClipNorth(imported.data.clipZone0, imported.data.clipZone0MaxZ);
                    Debug.Log($"RoadGame BLENDER imported {imported.SourceFile} (zone {imported.Zone}): replaced={imported.ReplacedRenderers}, added={imported.AddedRenderers}, propTemplates={imported.ImportedPropCount}, meshes={imported.data.meshes.Length}");
                }
                catch (Exception e)
                {
                    Debug.LogError("RoadGame: Blender level could not be applied (" + resource + "): " + e);
                }
                finally { Resources.UnloadAsset(asset); }
            }
            return any;
        }

        /// <summary>
        /// Runtime import with frame boundaries for WebGL's end-of-frame GC. Preloads only the render/collision
        /// buffers consumed by ApplyWorld, in batches of about 4 MiB of source mesh data. A single larger mesh
        /// gets a frame of its own. Target meshes remain lazy, and the synchronous TryApply remains available
        /// to editor utilities that must finish in one call.
        /// </summary>
        public static IEnumerator TryApplyRoutine(World world, Action<float> progress = null)
        {
            if (SuppressIntegration || world == null) { progress?.Invoke(1f); yield break; }
            progress?.Invoke(0f);
            // The procedural generator also allocates mesh-building scratch data in its final frame.
            yield return null;
            Original original = null;
            bool allSucceeded = true;
            var present = world.GetComponents<ImportedLevel>();
            for (int bundle = 0; bundle < BundleResources.Length; bundle++)
            {
                string resource = BundleResources[bundle];
                ImportedLevel existing = null;
                foreach (var c in present)
                    if (c.Resource == resource || (c.Resource == null && resource == ManifestResource)) existing = c;
                if (existing != null && existing.Applied)
                {
                    Register(existing);
                    ImportProgress(progress, bundle, 1f);
                    yield return null;
                    continue;
                }
                var asset = Resources.Load<TextAsset>(resource);
                if (asset == null) { ImportProgress(progress, bundle, 1f); continue; }
                // Capture once, before either bundle changes any of the original preorder transforms.
                if (original == null) original = Original.Capture(world.transform);
                var imported = existing != null ? existing : world.gameObject.AddComponent<ImportedLevel>();
                imported.Resource = resource;
                List<int> startupMeshes = null;
                try
                {
                    imported.Load(asset.text);
                    startupMeshes = imported.StartupMeshIndices();
                }
                catch (Exception e)
                {
                    allSucceeded = false;
                    Debug.LogError("RoadGame: Blender level could not be loaded (" + resource + "): " + e);
                }
                finally { Resources.UnloadAsset(asset); }
                asset = null;
                ImportProgress(progress, bundle, 0.05f);
                // Do not carry the JSON conversion and the first mesh batch in the same managed allocation frame.
                yield return null;
                if (startupMeshes == null) { ImportProgress(progress, bundle, 1f); continue; }

                long batchBytes = 0;
                bool preloadSucceeded = true;
                for (int i = 0; i < startupMeshes.Count; i++)
                {
                    int index = startupMeshes[i];
                    if (imported.meshes[index] != null) continue;
                    long size = imported.EstimatedMeshBytes(index);
                    if (batchBytes > 0 && batchBytes + size > MeshBatchBytes)
                    {
                        imported.StaticMeshPreloadBatches++;
                        ImportProgress(progress, bundle, 0.05f + 0.7f * i / Mathf.Max(1, startupMeshes.Count));
                        yield return null;
                        batchBytes = 0;
                    }
                    try
                    {
                        imported.MeshAt(index);
                        imported.PreloadedStaticMeshCount++;
                    }
                    catch (Exception e)
                    {
                        preloadSucceeded = allSucceeded = false;
                        Debug.LogError("RoadGame: Blender static mesh could not be loaded (" + resource + "): " + e);
                    }
                    if (!preloadSucceeded) break;
                    batchBytes += size;
                }
                if (batchBytes > 0) imported.StaticMeshPreloadBatches++;
                ImportProgress(progress, bundle, 0.75f);
                // MeshAt's byte[] and temporary vertex/index arrays are now collectible before ApplyWorld.
                yield return null;
                if (!preloadSucceeded) { ImportProgress(progress, bundle, 1f); continue; }

                bool applied = false;
                try
                {
                    imported.ApplyWorld(world, original);
                    imported.Applied = true;
                    Register(imported);
                    applied = true;
                }
                catch (Exception e)
                {
                    allSucceeded = false;
                    Debug.LogError("RoadGame: Blender level could not be applied (" + resource + "): " + e);
                }
                ImportProgress(progress, bundle, 0.9f);
                yield return null;
                if (applied)
                {
                    try
                    {
                        if (imported.Zone == 1 && Active != null && Active.Applied && imported.data.clipZone0 != null)
                            Active.ClipNorth(imported.data.clipZone0, imported.data.clipZone0MaxZ);
                        Debug.Log($"RoadGame BLENDER imported {imported.SourceFile} (zone {imported.Zone}): replaced={imported.ReplacedRenderers}, added={imported.AddedRenderers}, propTemplates={imported.ImportedPropCount}, meshes={imported.data.meshes.Length}, preloadBatches={imported.StaticMeshPreloadBatches}");
                    }
                    catch (Exception e)
                    {
                        allSucceeded = false;
                        Debug.LogError("RoadGame: Blender boundary could not be clipped (" + resource + "): " + e);
                    }
                }
                ImportProgress(progress, bundle, 1f);
                // Release clip scratch data before importing another bundle or uploading render-only buffers.
                yield return null;
            }

            if (allSucceeded)
            {
#if UNITY_WEBGL && !UNITY_EDITOR
                // Art/export utilities and Editor captures read these vertices after World.Generate(). Keep their
                // CPU buffers; only the Web player needs this memory reduction. Frame-bounded preload runs everywhere.
                var levels = new[] { Active, Wetlands, Ashen };
                for (int i = 0; i < levels.Length; i++)
                {
                    var level = levels[i];
                    // An absent second bundle might be applied later by an editor utility. Its first-zone clip
                    // would still need readable source geometry, so defer first-zone stripping in that case.
                    if (level == null || !level.Applied || (level.Zone == 0 && (Wetlands == null || !Wetlands.Applied))) continue;
                    int phase = i;
                    yield return level.ReleaseStaticCpuCopiesRoutine(world, k => progress?.Invoke(0.9f + 0.1f / levels.Length * (phase + k)));
                }
#endif
            }
            progress?.Invoke(1f);
        }

        static void ImportProgress(Action<float> progress, int bundle, float phase)
            => progress?.Invoke(0.9f * (bundle + Mathf.Clamp01(phase)) / BundleResources.Length);

        static bool IsStaticNode(Node n)
            => n.spawnId < 0 && n.category != "spawn_visual" && n.category != "reference";

        List<int> StartupMeshIndices()
        {
            var result = new List<int>();
            var seen = new bool[data.meshes.Length];
            void Add(int index)
            {
                if (index < 0) return;
                if (index >= seen.Length) throw new InvalidDataException("Static mesh index out of range: " + index);
                if (seen[index]) return;
                seen[index] = true;
                result.Add(index);
            }
            foreach (var n in data.nodes)
            {
                if (!IsStaticNode(n)) continue;
                Add(n.mesh);
                Add(n.colliderMesh);
                // AP_River_GapBoulders use their render buffer as a collider; n.mesh already covers that case.
            }
            return result;
        }

        long EstimatedMeshBytes(int index)
        {
            var d = data.meshes[index];
            return Math.Max(1L, 8L + Math.Max(0, d.submeshes) * 4L
                + Math.Max(0, d.vertexCount) * 56L + Math.Max(0, d.triangles) * 12L);
        }

        IEnumerator ReleaseStaticCpuCopiesRoutine(World world, Action<float> progress)
        {
            var protectedIndices = new bool[meshes.Length];
            foreach (var n in data.nodes)
            {
                // Some buffers are shared by a static object and a future target. Keep every target/reference
                // mesh readable for ApplyProp / ApplySpawn and World.FitRockRadius, including future respawns.
                if (!IsStaticNode(n) && n.mesh >= 0 && n.mesh < protectedIndices.Length) protectedIndices[n.mesh] = true;
                if (n.colliderMesh >= 0 && n.colliderMesh < protectedIndices.Length) protectedIndices[n.colliderMesh] = true;
                if (n.name != null && n.name.StartsWith("AP_River_GapBoulders", StringComparison.Ordinal)
                    && n.mesh >= 0 && n.mesh < protectedIndices.Length) protectedIndices[n.mesh] = true;
            }
            var colliderMeshes = new HashSet<Mesh>();
            foreach (var collider in world.GetComponentsInChildren<MeshCollider>(true))
                if (collider.sharedMesh != null) colliderMeshes.Add(collider.sharedMesh);
            var candidates = new List<Mesh>();
            var sizes = new List<long>();
            for (int i = 0; i < meshes.Length; i++)
            {
                var mesh = meshes[i];
                if (mesh == null || !mesh.isReadable || protectedIndices[i] || colliderMeshes.Contains(mesh)) continue;
                candidates.Add(mesh);
                sizes.Add(EstimatedMeshBytes(i));
            }
            // ClipCopy creates distinct render and collision buffers. The live colliders protect the latter.
            foreach (var mesh in clippedMeshes)
            {
                if (mesh == null || !mesh.isReadable || colliderMeshes.Contains(mesh)) continue;
                long indices = 0;
                for (int i = 0; i < mesh.subMeshCount; i++) indices += (long)mesh.GetIndexCount(i);
                candidates.Add(mesh);
                sizes.Add(mesh.vertexCount * 56L + indices * 4L);
            }
            long batchBytes = 0;
            for (int i = 0; i < candidates.Count; i++)
            {
                if (batchBytes > 0 && batchBytes + sizes[i] > MeshBatchBytes)
                {
                    progress?.Invoke((float)i / candidates.Count);
                    yield return null;
                    batchBytes = 0;
                }
                try
                {
                    candidates[i].UploadMeshData(true);
                    ReleasedStaticMeshCount++;
                }
                catch (Exception e)
                {
                    // Keeping an exceptional mesh readable costs memory but does not invalidate the imported level.
                    Debug.LogWarning("RoadGame: retained readable Blender mesh " + candidates[i].name + ": " + e.Message);
                }
                batchBytes += sizes[i];
            }
            progress?.Invoke(1f);
            yield return null;
        }

        /// <summary>Snapshot position (Unity) of a spawn root in this bundle: where the generator first put it.</summary>
        public bool TryGetSnapshotSpawn(int spawnId, out Vector3 position)
        {
            position = Vector3.zero;
            if (data == null || !spawnRoots.TryGetValue(spawnId, out int i)) return false;
            var p = data.nodes[i].position;
            if (p == null || p.Length < 3) return false;
            position = new Vector3(p[0], p[1], p[2]);
            return true;
        }

        public int ClippedMeshCount { get; private set; }
        readonly List<Mesh> clippedMeshes = new List<Mesh>();

        /// <summary>
        /// The v13 Dust Flats perimeter (its plateau's outer slopes, scree and drifts) and its collision proxies extend
        /// far past the first zone's north edge, over the second zone's south strip (up to z ~ 146, up to 11 m high),
        /// burying second-zone spawns and part of its main road. With the second zone's bundle the triangles north of
        /// maxZ are dropped from those meshes and colliders; everything at or south of maxZ, i.e. all of the first
        /// zone and its boundary, is unchanged.
        /// </summary>
        void ClipNorth(string[] names, float maxZ)
        {
            var set = new HashSet<string>(names);
            var ids = new HashSet<string>();
            for (int i = 0; i < data.nodes.Length; i++) if (set.Contains(data.nodes[i].name)) ids.Add(data.nodes[i].id);
            for (int i = 0; i < data.nodes.Length; i++)
            {
                var n = data.nodes[i];
                if (!set.Contains(n.name) && (string.IsNullOrEmpty(n.lodOf) || !ids.Contains(n.lodOf))) continue;
                var t = resolved[i];
                if (t == null) continue;
                var filter = t.GetComponent<MeshFilter>();
                if (filter != null && filter.sharedMesh != null) filter.sharedMesh = ClipCopy(filter.sharedMesh, t.localToWorldMatrix, maxZ);
                for (int c = 0; c < t.childCount; c++)
                {
                    var mc = t.GetChild(c).GetComponent<MeshCollider>();
                    if (mc != null && mc.sharedMesh != null && mc.name.StartsWith("BlenderCollision_", StringComparison.Ordinal))
                        mc.sharedMesh = ClipCopy(mc.sharedMesh, mc.transform.localToWorldMatrix, maxZ);
                }
                var group = t.GetComponent<LODGroup>();
                if (group != null) group.RecalculateBounds();
            }
            Debug.Log($"RoadGame BLENDER first-zone perimeter clipped north of z={maxZ}: meshes={ClippedMeshCount}");
        }

        Mesh ClipCopy(Mesh source, Matrix4x4 toWorld, float maxZ)
        {
            var vertices = source.vertices;
            var mesh = Instantiate(source);
            mesh.name = source.name + "_clip";
            var keep = new List<int>();
            for (int s = 0; s < source.subMeshCount; s++)
            {
                var tris = source.GetTriangles(s);
                keep.Clear();
                for (int k = 0; k + 2 < tris.Length; k += 3)
                {
                    float z = (toWorld.MultiplyPoint3x4(vertices[tris[k]]).z + toWorld.MultiplyPoint3x4(vertices[tris[k + 1]]).z
                               + toWorld.MultiplyPoint3x4(vertices[tris[k + 2]]).z) / 3f;
                    if (z <= maxZ) { keep.Add(tris[k]); keep.Add(tris[k + 1]); keep.Add(tris[k + 2]); }
                }
                mesh.SetTriangles(keep, s, false);
            }
            mesh.RecalculateBounds();
            clippedMeshes.Add(mesh);
            ClippedMeshCount++;
            return mesh;
        }

        static void Register(ImportedLevel level)
        {
            switch (level.Zone)
            {
                case 0: Active = level; break;
                case 1: Wetlands = level; break;
                case 2: Ashen = level; break;
                default: Debug.LogWarning("RoadGame: Blender bundle for an unknown zone " + level.Zone + " (" + level.Resource + ")"); break;
            }
        }

        void Load(string json)
        {
            data = JsonUtility.FromJson<Manifest>(json);
            if (data == null || data.nodes == null || data.meshes == null || data.materials == null)
                throw new InvalidDataException("Incomplete Blender level manifest");
            meshes = new Mesh[data.meshes.Length];
            materials = new Material[data.materials.Length];
            resolved = new Transform[data.nodes.Length];
            builtStatic = new bool[data.nodes.Length];
            for (int i = 0; i < data.nodes.Length; i++)
            {
                var n = data.nodes[i];
                if (!string.IsNullOrEmpty(n.id)) nodeById[n.id] = i;
                if (n.spawnId < 0) continue;
                if (n.spawnRoot)
                {
                    spawnRoots[n.spawnId] = i;
                    // "Spawn_10133_Scav": the first root of each model also serves spawns missing from the snapshot
                    int us = n.name != null ? n.name.IndexOf('_', 6) : -1;
                    if (us > 0 && Enum.TryParse(n.name.Substring(us + 1).Split('.')[0], out ModelId model) && !modelTemplates.ContainsKey(model))
                        modelTemplates.Add(model, i);
                }
                if (!spawnNodes.TryGetValue(n.spawnId, out var list))
                    spawnNodes.Add(n.spawnId, list = new List<int>());
                list.Add(i);
            }
        }

        static void CaptureOriginal(Transform t, List<Transform> nodes)
        {
            nodes.Add(t);
            for (int i = 0; i < t.childCount; i++) CaptureOriginal(t.GetChild(i), nodes);
        }

        static string HierarchyPath(Transform t, Transform root)
        {
            var path = t.name;
            while (t != root && t.parent != null) { t = t.parent; path = t.name + "/" + path; }
            return path;
        }

        void ApplyWorld(World world, Original snapshot)
        {
            var originalIds = snapshot.ids;
            var originalPaths = snapshot.paths;
            // Capture first, then change the hierarchy. IDs are the original export's preorder traversal.
            for (int i = 0; i < data.nodes.Length; i++)
            {
                var n = data.nodes[i];
                if (!IsStaticNode(n)) continue;
                if (!string.IsNullOrEmpty(n.id) && originalIds.TryGetValue(n.id, out var match)
                    && (string.IsNullOrEmpty(n.originalName) || match.name == n.originalName)
                    && (string.IsNullOrEmpty(n.sourcePath) || HierarchyPath(match, world.transform) == n.sourcePath))
                    resolved[i] = match;
                else if (!string.IsNullOrEmpty(n.sourcePath) && originalPaths.TryGetValue(n.sourcePath, out var byPath) && byPath.Count == 1)
                    resolved[i] = byPath[0];
                else if (!string.IsNullOrEmpty(n.originalName))
                {
                    UnmappedOriginalCount++;
                    Debug.LogWarning("RoadGame Blender mapping missed original node " + n.id + " (" + n.sourcePath + ")");
                }
            }
            if (data.replacementNodeIds != null)
                foreach (string id in data.replacementNodeIds)
                    if (originalIds.TryGetValue(id, out var t))
                    {
                        var renderer = t.GetComponent<Renderer>();
                        if (renderer != null) renderer.enabled = false;
                    }
            for (int i = 0; i < data.nodes.Length; i++)
            {
                var n = data.nodes[i];
                if (!IsStaticNode(n)) continue;
                ResolveStatic(i, world.transform);
            }
            BuildLods(resolved);
            RefreshOccluders();
            ReplacedStaticCount = ReplacedRenderers;
            AddedStaticCount = AddedRenderers;
            Debug.Log($"RoadGame BLENDER mapping (zone {Zone}): originalNodes={snapshot.count}, replaced={ReplacedStaticCount}, added={AddedStaticCount}, unmapped={UnmappedOriginalCount}");
        }

        Transform ResolveStatic(int i, Transform root)
        {
            if (builtStatic[i]) return resolved[i];
            builtStatic[i] = true;
            var n = data.nodes[i];
            bool reused = resolved[i] != null;
            Transform parent = n.parent >= 0 ? ResolveParent(n.parent, root) : root;
            var t = resolved[i];
            if (t == null)
            {
                t = new GameObject(n.name ?? "BlenderObject").transform;
                t.SetParent(parent, false);
                resolved[i] = t;
            }
            if (t != root) ApplyTransform(t, n);
            // Generated gameplay groups decide their own active state (intro guide and gate barrier).
            if (!reused) t.gameObject.SetActive(n.isLod || n.lodLevel > 0 || n.active);
            ApplyRenderer(t, n, reused);
            // These rectangular source walls no longer follow the edited outline. The imported proxy and
            // DustFlatsSurfaces' continuous outline replace their old box and convex rock hulls together.
            // (first zone only: the second zone keeps its generated wall colliders; its berms are drawn on them)
            if (reused && n.originalName == "Cliff" && Zone == 0)
                foreach (var collider in t.GetComponentsInChildren<Collider>(true)) collider.enabled = false;
            if (reused && n.disableColliders)
                foreach (var collider in t.GetComponentsInChildren<Collider>(true)) collider.enabled = false;
            if (n.colliderMesh >= 0) ApplyCollider(t, n.colliderMesh, n.colliderConvex);
            else if (n.name != null && n.name.StartsWith("AP_River_GapBoulders", StringComparison.Ordinal) && n.mesh >= 0)
                ApplyCollider(t, n.mesh, false);
            return t;
        }

        Transform ResolveParent(int i, Transform root)
        {
            if (resolved[i] != null) return resolved[i];
            var n = data.nodes[i];
            if (n.spawnId >= 0 || n.category == "spawn_visual") return root;
            return ResolveStatic(i, root);
        }

        void ApplyRenderer(Transform t, Node n, bool reused)
        {
            if (n.mesh < 0) return;
            var filter = t.GetComponent<MeshFilter>();
            if (filter == null) filter = t.gameObject.AddComponent<MeshFilter>();
            filter.sharedMesh = MeshAt(n.mesh);
            var renderer = t.GetComponent<MeshRenderer>();
            if (renderer == null) renderer = t.gameObject.AddComponent<MeshRenderer>();
            renderer.sharedMaterials = MaterialsFor(n);
            renderer.enabled = n.isLod || n.lodLevel > 0 || n.rendererEnabled;
            renderer.shadowCastingMode = n.castShadows && !IsWater(n) ? ShadowCastingMode.On : ShadowCastingMode.Off;
            renderer.receiveShadows = true;
            renderer.lightProbeUsage = LightProbeUsage.Off;
            renderer.reflectionProbeUsage = ReflectionProbeUsage.Off;
            if (reused) ReplacedRenderers++; else AddedRenderers++;
            if (!reused && n.isRoof && n.lodLevel == 0)
                OcclusionFader.Register(n.name, t.gameObject, n.fadeOnlyBelow, n.minAlpha > 0f ? n.minAlpha : 0.2f);
        }

        bool IsWater(Node n)
        {
            if (n.materials != null)
                foreach (int m in n.materials) if (m >= 0 && m < data.materials.Length && data.materials[m].water) return true;
            return false;
        }

        Material[] MaterialsFor(Node n)
        {
            if (n.materials == null || n.materials.Length == 0) return new[] { Mats.Toon };
            var result = new Material[n.materials.Length];
            for (int k = 0; k < result.Length; k++) result[k] = MaterialAt(n.materials[k]);
            return result;
        }

        Material MaterialAt(int index)
        {
            if (index < 0 || index >= materials.Length) return Mats.Toon;
            if (materials[index] != null) return materials[index];
            Mats.Init();
            var d = data.materials[index];
            var color = ColorOf(d.color);
            Material m;
            if (d.water)
                m = Zone == 1 ? SwampWater.CreateSurfaceMaterial("Blender_" + d.name, color, d.alpha)
                              : RiverWaterFx.CreateSurfaceMaterial("Blender_" + d.name, color, d.alpha);
            else if (d.unlit)
                m = Mats.NewUnlit("Blender_" + d.name, null, d.additive);
            else if (!string.IsNullOrEmpty(d.baseKind))
            {
                var zoneDef = Content.Zones[Mathf.Clamp(d.zone, 0, Content.ZoneCount - 1)];
                var source = d.baseKind == "ground" ? Mats.Ground : d.baseKind == "flat" ? Mats.ToonFlat
                    : d.baseKind == "road" ? Mats.Road(zoneDef) : Mats.Toon;
                m = new Material(source) { name = "Blender_" + d.name, enableInstancing = true };
                if (d.baseKind == "toon")
                {
                    m.SetFloat("_DustAmount", d.dust >= 0f ? d.dust : 0.08f);
                    m.SetFloat("_AOFloor", d.aoFloor >= 0f ? d.aoFloor : 0.88f);
                    m.SetFloat("_AOHeight", 0.65f);
                }
                else if (d.baseKind == "actor" && d.dust >= 0f) m.SetFloat("_DustAmount", d.dust);
                m.SetFloat("_WorldUV", d.worldUV);
            }
            else
            {
                bool flat = d.name == "Ground" || d.name == "ToonFlat" || (d.name != null && d.name.StartsWith("Road", StringComparison.Ordinal));
                var source = d.name == "Ground" ? Mats.Ground : d.name == "ToonFlat" ? Mats.ToonFlat
                    : flat ? Mats.Road(Content.Zones[0]) : Mats.Toon;
                m = new Material(source) { name = "Blender_" + d.name, enableInstancing = true };
                if (!flat)
                {
                    m.SetFloat("_DustAmount", 0.08f);
                    m.SetFloat("_AOFloor", 0.88f);
                    m.SetFloat("_AOHeight", 0.65f);
                }
                m.SetFloat("_WorldUV", d.worldUV);
            }
            m.SetColor("_BaseColor", color);
            if (!string.IsNullOrEmpty(d.texture))
            {
                var tex = Resources.Load<Texture2D>(d.texture);
                if (tex != null) m.SetTexture("_BaseMap", tex);
                else Debug.LogWarning("RoadGame imported texture missing: " + d.texture);
            }
            if (d.tiling != null && d.tiling.Length >= 2) m.SetTextureScale("_BaseMap", new Vector2(d.tiling[0], d.tiling[1]));
            if (d.offset != null && d.offset.Length >= 2) m.SetTextureOffset("_BaseMap", new Vector2(d.offset[0], d.offset[1]));
            materials[index] = m;
            return m;
        }

        Mesh MeshAt(int index)
        {
            if (index < 0 || index >= meshes.Length) throw new InvalidDataException("Mesh index out of range: " + index);
            if (meshes[index] != null) return meshes[index];
            var d = data.meshes[index];
            var bytes = Resources.Load<TextAsset>(d.resource);
            if (bytes == null) throw new FileNotFoundException("Imported mesh not found", d.resource);
            try
            {
                using (var stream = new MemoryStream(bytes.bytes, false))
                using (var reader = new BinaryReader(stream))
                {
                    int count = reader.ReadInt32(), submeshes = reader.ReadInt32();
                    if (count < 1 || count > 5000000 || submeshes < 1 || submeshes > 256)
                        throw new InvalidDataException("Invalid mesh header: " + d.resource);
                    var vertices = new Vector3[count]; var normals = new Vector3[count];
                    var colors = new Color[count]; var uv = new Vector2[count]; var parameters = new Vector2[count];
                    for (int i = 0; i < count; i++)
                    {
                        vertices[i] = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
                        normals[i] = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
                        colors[i] = new Color(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
                        uv[i] = new Vector2(reader.ReadSingle(), reader.ReadSingle());
                        parameters[i] = new Vector2(reader.ReadSingle(), reader.ReadSingle());
                    }
                    var mesh = new Mesh { name = d.name, indexFormat = count > 65535 ? IndexFormat.UInt32 : IndexFormat.UInt16 };
                    mesh.vertices = vertices; mesh.normals = normals; mesh.colors = colors; mesh.uv = uv; mesh.uv2 = parameters;
                    mesh.subMeshCount = submeshes;
                    for (int k = 0; k < submeshes; k++)
                    {
                        int indices = reader.ReadInt32();
                        if (indices < 0 || indices % 3 != 0 || indices > 30000000) throw new InvalidDataException("Invalid triangle buffer: " + d.resource);
                        var triangles = new int[indices];
                        for (int j = 0; j < indices; j++)
                        {
                            triangles[j] = reader.ReadInt32();
                            if (triangles[j] < 0 || triangles[j] >= count) throw new InvalidDataException("Triangle outside vertex buffer: " + d.resource);
                        }
                        mesh.SetTriangles(triangles, k, false);
                    }
                    if (stream.Position != stream.Length) throw new InvalidDataException("Extra mesh bytes: " + d.resource);
                    mesh.RecalculateBounds();
                    // Keep read access: static collision proxies and the target collider fitting use these meshes.
                    meshes[index] = mesh;
                    return mesh;
                }
            }
            finally { Resources.UnloadAsset(bytes); }
        }

        void ApplyCollider(Transform t, int mesh, bool convex)
        {
            foreach (var c in t.GetComponents<Collider>()) c.enabled = false;
            // Generated rock hulls are siblings below the model's group, rather than below its renderer.
            Transform group = t.parent;
            if (group != null && (t.name.StartsWith("Ridge", StringComparison.Ordinal) || t.name == "MesaRock" || t.name == "Plateau"))
                foreach (var c in group.GetComponentsInChildren<Collider>(true))
                    if (c is MeshCollider && c.transform.name.IndexOf("Rock", StringComparison.OrdinalIgnoreCase) >= 0) c.enabled = false;
            var go = new GameObject("BlenderCollision_" + t.name) { layer = Ground.BlockerLayer };
            go.transform.SetParent(t, false);
            var collider = go.AddComponent<MeshCollider>();
            collider.sharedMesh = MeshAt(mesh);
            collider.convex = convex;
        }

        void BuildLods(Transform[] nodes)
        {
            for (int i = 0; i < data.nodes.Length; i++)
            {
                var n = data.nodes[i];
                if (n.lodLevel != 1 || nodes[i] == null || string.IsNullOrEmpty(n.lodOf)) continue;
                if (!nodeById.TryGetValue(n.lodOf, out int source)) continue;
                var t = nodes[source];
                if (t == null) continue;
                var baseRenderer = t.GetComponent<Renderer>();
                if (baseRenderer == null || !baseRenderer.enabled) continue;
                var levels = new List<LOD>();
                var all = new List<Renderer> { baseRenderer };
                levels.Add(new LOD(n.lodScreenSize > 0f ? n.lodScreenSize : 0.25f, new[] { baseRenderer }));
                for (int level = 1; level <= 2; level++)
                {
                    var renderers = new List<Renderer>();
                    for (int j = 0; j < data.nodes.Length; j++)
                        if (data.nodes[j].lodOf == n.lodOf && data.nodes[j].lodLevel == level && nodes[j] != null)
                        {
                            nodes[j].gameObject.SetActive(true);
                            var r = nodes[j].GetComponent<Renderer>();
                            if (r != null) { r.enabled = true; renderers.Add(r); all.Add(r); }
                        }
                    if (renderers.Count > 0) levels.Add(new LOD(level == 1 ? 0.10f : 0.005f, renderers.ToArray()));
                }
                var group = t.GetComponent<LODGroup>();
                if (group == null) group = t.gameObject.AddComponent<LODGroup>();
                group.SetLODs(levels.ToArray());
                group.RecalculateBounds();
                lodRenderers[baseRenderer] = all;
            }
        }

        void RefreshOccluders()
        {
            if (OcclusionFader.I == null) return;
            foreach (var occluder in OcclusionFader.I.All)
            {
                var rs = new List<Renderer>();
                foreach (var r in occluder.renderers)
                    if (r != null)
                    {
                        if (lodRenderers.TryGetValue(r, out var lods)) rs.AddRange(lods);
                        else rs.Add(r);
                    }
                occluder.renderers = rs.ToArray();
                occluder.Init();
            }
        }

        /// <summary>Call immediately after Models.Create for a live target, before its collider/rig is configured.
        /// First zone: destructible props only (as before). Third zone (Ashen Winter): props here, the enemies, buggies
        /// and the boss are its creatures (Mutants.Apply). Second zone: props, enemies, buggies and the boss; a spawn
        /// missing from the snapshot uses the first snapshot spawn of its model. The swap happens once per target
        /// object, and World reuses that object for every respawn, so respawned enemies keep the new models.</summary>
        public static bool ApplyTarget(SpawnPoint spawn, GameObject target)
        {
            if (spawn.zone.index == 0)
            {
                var level = Active;
                if (level == null || !level.Applied || spawn.spec.kind != TargetKind.Prop
                    || !level.spawnRoots.TryGetValue(spawn.id, out int rootIndex)) return false;
                return level.ApplyProp(spawn.id, target, rootIndex);
            }
            // second-zone enemies, buggies and the boss are the swamp mutants (their own bundle and animators)
            if ((spawn.zone.index == 1 || spawn.zone.index == 2) && spawn.spec.kind != TargetKind.Prop && Mutants.Apply(spawn, target)) return true;
            var wet = spawn.zone.index == 1 ? Wetlands : spawn.zone.index == 2 ? Ashen : null;
            if (wet == null || !wet.Applied) return false;
            if (!wet.spawnRoots.TryGetValue(spawn.id, out int root) && !wet.modelTemplates.TryGetValue(spawn.spec.model, out root)) return false;
            return wet.ApplySpawn(spawn, target, root);
        }

        /// <summary>Second-zone targets: the spawn's snapshot hierarchy is matched to the live rig (Scale, Torso, LegL /
        /// LegLMesh, ArmR / Weapon, Body / Gun / WheelSteer / Wheel). Matching reuses the live transforms, so the rig's
        /// references (legs, arms, weapon, wheels, turret, muzzle) keep driving the new meshes.</summary>
        bool ApplySpawn(SpawnPoint spawn, GameObject target, int rootIndex)
        {
            if (target.GetComponent<ImportedPropSurface>() != null || target.GetComponent<ImportedActorSurface>() != null) return true;
            int spawnId = data.nodes[rootIndex].spawnId;
            if (!spawnNodes.TryGetValue(spawnId, out var indices)) return false;
            foreach (var renderer in target.GetComponentsInChildren<Renderer>(true)) renderer.enabled = false;
            var nodes = new Transform[data.nodes.Length];
            nodes[rootIndex] = target.transform;
            var used = new HashSet<Transform> { target.transform };
            Transform Resolve(int i)
            {
                if (nodes[i] != null) return nodes[i];
                var n = data.nodes[i];
                var parent = n.parent >= 0 && data.nodes[n.parent].spawnId == spawnId ? Resolve(n.parent) : target.transform;
                Transform t = null;
                if (!string.IsNullOrEmpty(n.originalName))
                {
                    // duplicate names (four WheelSteer pivots): the free child closest to the node's local position
                    var want = VectorOf(n.position, Vector3.zero);
                    float best = float.MaxValue;
                    for (int c = 0; c < parent.childCount; c++)
                    {
                        var ch = parent.GetChild(c);
                        if (ch.name != n.originalName || used.Contains(ch)) continue;
                        float dd = (ch.localPosition - want).sqrMagnitude;
                        if (dd < best) { best = dd; t = ch; }
                    }
                }
                if (t == null)
                {
                    t = new GameObject(n.name ?? "Part").transform;
                    t.SetParent(parent, false);
                }
                used.Add(t);
                nodes[i] = t;
                ApplyTransform(t, n);
                t.gameObject.SetActive(n.isLod || n.lodLevel > 0 || n.active);
                ApplyRenderer(t, n, false);
                return t;
            }
            foreach (int i in indices) if (i != rootIndex) Resolve(i);
            BuildLods(nodes);
            if (spawn.spec.kind == TargetKind.Prop) { target.AddComponent<ImportedPropSurface>(); AppliedPropCount++; }
            else { target.AddComponent<ImportedActorSurface>(); AppliedActorCount++; }
            var rig = target.GetComponent<Rig>();
            if (rig != null) rig.CollectRenderers();
            return true;
        }

        bool ApplyProp(int spawnId, GameObject target, int rootIndex)
        {
            if (target.GetComponent<ImportedPropSurface>() != null) return true;
            foreach (var renderer in target.GetComponentsInChildren<Renderer>(true)) renderer.enabled = false;
            var nodes = new Transform[data.nodes.Length];
            nodes[rootIndex] = target.transform;
            var indices = spawnNodes[spawnId];
            foreach (int i in indices)
            {
                if (i == rootIndex) continue;
                var n = data.nodes[i];
                var parent = n.parent >= 0 && nodes[n.parent] != null ? nodes[n.parent] : target.transform;
                // Prop source models have one Body. Reusing it also lets FitRockRadius inspect the edited mesh.
                var t = !string.IsNullOrEmpty(n.originalName) ? parent.Find(n.originalName) : null;
                if (t == null)
                {
                    t = new GameObject(n.name ?? "PropPart").transform;
                    t.SetParent(parent, false);
                }
                ApplyTransform(t, n);
                nodes[i] = t;
                t.gameObject.SetActive(n.isLod || n.lodLevel > 0 || n.active);
                ApplyRenderer(t, n, false);
            }
            BuildLods(nodes);
            var rig = target.GetComponent<Rig>();
            if (rig != null) rig.CollectRenderers();
            target.AddComponent<ImportedPropSurface>();
            AppliedPropCount++;
            return true;
        }

        static void ApplyTransform(Transform t, Node n)
        {
            // v13's hidden LODs share the source's local geometry; Blender saved stale world matrices for
            // some hidden children. Their intended local transform is identity (see step13_lod.py).
            if (n.lodLevel > 0)
            {
                t.localPosition = Vector3.zero; t.localRotation = Quaternion.identity; t.localScale = Vector3.one;
                return;
            }
            t.localPosition = VectorOf(n.position, Vector3.zero);
            t.localScale = VectorOf(n.scale, Vector3.one);
            t.localRotation = n.rotation != null && n.rotation.Length >= 4
                ? new Quaternion(n.rotation[0], n.rotation[1], n.rotation[2], n.rotation[3]) : Quaternion.identity;
        }
        static Vector3 VectorOf(float[] v, Vector3 fallback) => v != null && v.Length >= 3 ? new Vector3(v[0], v[1], v[2]) : fallback;
        static Color ColorOf(float[] c) => c != null && c.Length >= 3 ? new Color(c[0], c[1], c[2], c.Length > 3 ? c[3] : 1f) : Color.white;

        void LateUpdate()
        {
            // Mats owns the zone transition. Imported copies follow its shade while retaining their own textures.
            if (materials == null || Mats.Toon == null) return;
            var shade = Mats.Toon.GetColor("_ShadeColor");
            if (shade == lastShade) return;
            lastShade = shade;
            foreach (var material in materials)
                if (material != null && material.HasProperty("_ShadeColor")) material.SetColor("_ShadeColor", shade);
        }

        void OnDestroy()
        {
            if (Active == this) Active = null;
            if (Wetlands == this) Wetlands = null;
            if (Ashen == this) Ashen = null;
            if (meshes != null) foreach (var m in meshes) if (m != null) Release(m);
            foreach (var m in clippedMeshes) if (m != null) Release(m);
            if (materials != null) foreach (var m in materials) if (m != null) Release(m);
        }
        static void Release(UnityEngine.Object o)
        {
            if (Application.isPlaying) Destroy(o); else DestroyImmediate(o);
        }
    }

    /// <summary>Marks an enemy / buggy / boss whose meshes come from a Blender bundle: Rig flashes and burns it with
    /// property blocks (like the imported car) so the imported textures and material slots stay.</summary>
    public sealed class ImportedActorSurface : MonoBehaviour { }

    /// <summary>Hit/burnt feedback without discarding the imported prop's textures or material slots.</summary>
    public sealed class ImportedPropSurface : MonoBehaviour
    {
        Renderer[] renderers;
        Material[][] originals;
        MaterialPropertyBlock block;
        Target target;
        int previousState = -1;

        void Awake()
        {
            renderers = GetComponentsInChildren<Renderer>(true);
            originals = new Material[renderers.Length][];
            for (int i = 0; i < renderers.Length; i++) originals[i] = renderers[i].sharedMaterials;
            block = new MaterialPropertyBlock();
        }
        void OnEnable() { previousState = -1; }
        void LateUpdate()
        {
            if (target == null) target = GetComponent<Target>();
            if (target == null) return;
            int state = target.dead ? 2 : Time.time - target.lastHitTime < 0.08f ? 1 : 0;
            if (state == previousState) return;
            previousState = state;
            for (int r = 0; r < renderers.Length; r++)
            {
                if (renderers[r] == null) continue;
                for (int k = 0; k < originals[r].Length; k++)
                {
                    var material = originals[r][k];
                    if (material == null || !material.HasProperty("_FlashColor")) continue;
                    block.Clear();
                    if (state == 1) block.SetColor("_FlashColor", new Color(1f, 0.96f, 0.86f, 0.6f));
                    else if (state == 2)
                    {
                        block.SetColor("_BaseColor", material.GetColor("_BaseColor") * new Color(0.5f, 0.46f, 0.44f, 1f));
                        block.SetFloat("_Saturation", 0.35f);
                        block.SetFloat("_GlossMul", 0.25f);
                    }
                    renderers[r].SetPropertyBlock(state == 0 ? null : block, k);
                }
            }
        }
    }
}
