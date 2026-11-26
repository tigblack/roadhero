using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// A frozen modelling snapshot of the procedural world, made without entering Play Mode or reading/writing a save.
    /// Unity -batchmode -disableaudio -projectPath P -executeMethod RoadGame.EditorTools.LevelBlenderExport.Run
    ///       -exportOut /absolute/output/directory -logFile /absolute/export.log
    /// scene.json keeps Unity's original local coordinates. The Blender importer converts (x,y,z) to (x,z,y).
    /// This is an art/layout handoff; it does not replace Ground's analytical driving surfaces or the runtime generator.
    /// </summary>
    public static class LevelBlenderExport
    {
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        public static void Run()
        {
            WorkAudioMute.Apply();
            int result = 1;
            var previousGame = Game.I;
            var previousWorld = World.I;
            var previousRandom = UnityEngine.Random.state;
            var previousScene = SceneManager.GetActiveScene();
            Scene preview = default;
            try
            {
                if (EditorApplication.isPlayingOrWillChangePlaymode)
                    throw new InvalidOperationException("Stop Play Mode before exporting a level.");
                string output = Path.GetFullPath(Arg("-exportOut", "Exports/Blender/Current"));
                Directory.CreateDirectory(output);
                Directory.CreateDirectory(Path.Combine(output, "textures"));

                AshenSurfaces.ForceForExport = Array.IndexOf(Environment.GetCommandLineArgs(), "-ashenLayout") >= 0;
                preview = EditorSceneManager.NewPreviewScene();
                UnityEngine.Random.InitState(17421);
                Mats.Init();
                var context = new GameObject("ExportContext");
                SceneManager.MoveGameObjectToScene(context, preview);
                var game = context.AddComponent<Game>();
                game.enabled = false;
                Game.I = game;
                game.progress = new Progress(SaveSystem.NewGame(null));

                var worldObject = new GameObject("World");
                SceneManager.MoveGameObjectToScene(worldObject, preview);
                var world = worldObject.AddComponent<World>();
                world.enabled = false;
                World.I = world;
                game.world = world;
                world.Generate();
                // Closed gates model a new game's visible state, without calling Update/Tick or spawning actors.
                world.ApplyGateStates(false);

                var spawnRoot = new GameObject("Spawn_Visuals").transform;
                SceneManager.MoveGameObjectToScene(spawnRoot.gameObject, preview);
                spawnRoot.SetParent(world.transform, false);
                var zoneRoots = new Transform[Content.ZoneCount];
                for (int i = 0; i < zoneRoots.Length; i++)
                {
                    var g = new GameObject("Zone_" + (i + 1).ToString("00") + "_" + Content.Zones[i].name);
                    SceneManager.MoveGameObjectToScene(g, preview);
                    g.transform.SetParent(spawnRoot, false);
                    zoneRoots[i] = g.transform;
                }
                var spawnObjects = new Dictionary<int, Transform>();
                foreach (var sp in world.spawns)
                    spawnObjects.Add(sp.id, MakeSpawnVisual(sp, zoneRoots[sp.zone.index], preview));
                // Intro.Begin also starts gameplay and UI; add only its two model/spawn records here.
                var scoutSpec = Content.IntroScout(game.progress.WeaponHitDamage(0));
                var scoutA = world.AddIntroSpawn(9600, scoutSpec, Structures.IntroScoutA, 180f);
                var scoutB = world.AddIntroSpawn(9601, scoutSpec, Structures.IntroScoutB, 168f);
                spawnObjects.Add(scoutA.id, MakeSpawnVisual(scoutA, zoneRoots[0], preview));
                spawnObjects.Add(scoutB.id, MakeSpawnVisual(scoutB, zoneRoots[0], preview));
                if (Structures.IntroGuide != null) Structures.IntroGuide.SetActive(true);

                var car = Models.PlayerCar(out var rig);
                car.name = "REFERENCE_PlayerCar_DoNotMerge";
                SceneManager.MoveGameObjectToScene(car, preview);
                car.transform.position = Structures.IntroStart;
                Models.HoodGun(rig.body, 1, null);
                Models.Harpooner(rig.body);

                var export = new Export(output, world, spawnObjects);
                export.AddTree(world.transform);
                export.AddTree(car.transform);
                export.Write();
                Debug.Log($"RoadGame LevelBlenderExport: SUCCESS out={output} nodes={export.nodes.Count} meshes={export.meshes.Count} materials={export.materials.Count} instances={export.meshInstances} uniqueVertices={export.vertexCount} uniqueTriangles={export.triangleCount} bounds={export.bounds} editorMasterMuted={EditorUtility.audioMasterMute}");
                result = 0;
            }
            catch (Exception error)
            {
                Debug.LogException(error);
            }
            finally
            {
                if (preview.IsValid()) EditorSceneManager.ClosePreviewScene(preview);
                if (previousScene.IsValid() && previousScene.isLoaded) SceneManager.SetActiveScene(previousScene);
                Game.I = previousGame;
                World.I = previousWorld;
                UnityEngine.Random.state = previousRandom;
                WorkAudioMute.Apply();
            }
            if (Application.isBatchMode) EditorApplication.Exit(result);
            else if (result != 0) throw new InvalidOperationException("Level export failed; see the Console.");
        }

        static Transform MakeSpawnVisual(SpawnPoint sp, Transform parent, Scene scene)
        {
            var g = Models.Create(sp.spec.model, sp.variant + sp.id, sp.zone, sp.spec.scale);
            SceneManager.MoveGameObjectToScene(g, scene);
            g.name = "Spawn_" + sp.id.ToString("00000") + "_" + sp.spec.model;
            g.transform.SetParent(parent, false);
            g.transform.localPosition = sp.pos;
            g.transform.localRotation = Quaternion.Euler(0, sp.yaw, 0);
            g.transform.localScale = Vector3.one * sp.scale;
            foreach (var component in g.GetComponentsInChildren<MonoBehaviour>(true)) component.enabled = false;
            return g.transform;
        }

        static string Arg(string name, string fallback)
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == name) return args[i + 1];
            return fallback;
        }

        sealed class Export
        {
            readonly string output;
            readonly World world;
            readonly Dictionary<int, Transform> spawnObjects;
            public readonly List<Transform> nodes = new List<Transform>();
            public readonly List<Mesh> meshes = new List<Mesh>();
            public readonly List<Material> materials = new List<Material>();
            readonly Dictionary<Transform, string> nodeIds = new Dictionary<Transform, string>();
            readonly Dictionary<Mesh, string> meshIds = new Dictionary<Mesh, string>();
            readonly Dictionary<Material, string> materialIds = new Dictionary<Material, string>();
            public Bounds bounds;
            bool hasBounds;
            public int meshInstances;
            public long vertexCount, triangleCount;

            public Export(string output, World world, Dictionary<int, Transform> spawnObjects)
            { this.output = output; this.world = world; this.spawnObjects = spawnObjects; }

            public void AddTree(Transform t)
            {
                nodeIds.Add(t, "node_" + nodes.Count.ToString("000000"));
                nodes.Add(t);
                var mf = t.GetComponent<MeshFilter>();
                var renderer = t.GetComponent<MeshRenderer>();
                if (mf != null && mf.sharedMesh != null)
                {
                    var mesh = mf.sharedMesh;
                    meshInstances++;
                    if (!meshIds.ContainsKey(mesh))
                    {
                        meshIds.Add(mesh, "mesh_" + meshes.Count.ToString("000000"));
                        meshes.Add(mesh);
                        vertexCount += mesh.vertexCount;
                        for (int s = 0; s < mesh.subMeshCount; s++) triangleCount += mesh.GetIndexCount(s) / 3;
                    }
                    if (renderer != null)
                    {
                        foreach (var material in renderer.sharedMaterials)
                            if (material != null && !materialIds.ContainsKey(material))
                            { materialIds.Add(material, "material_" + materials.Count.ToString("000")); materials.Add(material); }
                        if (!hasBounds) { bounds = renderer.bounds; hasBounds = true; }
                        else bounds.Encapsulate(renderer.bounds);
                    }
                }
                for (int i = 0; i < t.childCount; i++) AddTree(t.GetChild(i));
            }

            public void Write()
            {
                using (var w = new Json(Path.Combine(output, "scene.json")))
                {
                    w.Raw("{\"schema\":1,\"unity_units_meters\":true,\"coordinate_system\":\"Unity left-handed Y-up\",\"materials\":[");
                    for (int i = 0; i < materials.Count; i++)
                    {
                        if (i > 0) w.Raw(",");
                        var material = materials[i];
                        var id = materialIds[material];
                        var color = material.HasProperty("_BaseColor") ? material.GetColor("_BaseColor") : material.HasProperty("_Color") ? material.color : Color.white;
                        w.Raw("{"); w.Field("id", id); w.Field("name", material.name); w.Field("shader", material.shader != null ? material.shader.name : "");
                        w.Raw("\"color\":"); w.Color(color); w.Raw(",\"metallic\":"); w.Number(Float(material, "_Metallic", 0));
                        w.Raw(",\"roughness\":"); w.Number(1f - Float(material, "_Smoothness", 0.25f));
                        w.Raw(",\"alpha_blend\":"); w.Bool(material.renderQueue >= 3000);
                        // Texture PNGs preserve road markings and ground detail; toon lighting itself is Unity-specific.
                        var texture = material.HasProperty("_BaseMap") ? material.GetTexture("_BaseMap") as Texture2D : null;
                        if (texture != null)
                        {
                            try
                            {
                                string texturePath = "textures/" + id + ".png";
                                File.WriteAllBytes(Path.Combine(output, texturePath), texture.EncodeToPNG());
                                w.Raw(","); w.Field("baseMap", texturePath, false);
                                w.Raw(",\"baseMapScale\":"); w.Vector(material.GetTextureScale("_BaseMap"));
                                w.Raw(",\"baseMapOffset\":"); w.Vector(material.GetTextureOffset("_BaseMap"));
                                w.Raw(",\"world_uv_scale\":"); w.Number(Float(material, "_WorldUV", 0));
                                w.Raw(",\"worldUV\":"); w.Number(Float(material, "_WorldUV", 0));
                            }
                            catch (Exception e) { Debug.LogWarning("Level export: texture skipped for " + material.name + ": " + e.Message); }
                        }
                        w.Raw("}");
                    }
                    w.Raw("],\"meshes\":[");
                    for (int i = 0; i < meshes.Count; i++)
                    {
                        if (i > 0) w.Raw(",");
                        var mesh = meshes[i];
                        w.Raw("{"); w.Field("id", meshIds[mesh]); w.Field("name", mesh.name);
                        w.Raw("\"vertices\":"); w.Vectors(mesh.vertices);
                        w.Raw(",\"normals\":"); w.Vectors(mesh.normals);
                        w.Raw(",\"colors\":"); w.Colors(mesh.colors);
                        w.Raw(",\"uv0\":"); w.Vectors(mesh.uv);
                        w.Raw(",\"uv1\":"); w.Vectors(mesh.uv2);
                        w.Raw(",\"submeshes\":[");
                        for (int s = 0; s < mesh.subMeshCount; s++)
                        {
                            if (s > 0) w.Raw(",");
                            if (mesh.GetTopology(s) != MeshTopology.Triangles) throw new InvalidOperationException("Non-triangle mesh: " + mesh.name);
                            w.Raw("{\"materialSlot\":"); w.Number(s); w.Raw(",\"triangles\":"); w.Integers(mesh.GetTriangles(s)); w.Raw("}");
                        }
                        w.Raw("]}");
                    }
                    w.Raw("],\"nodes\":[");
                    for (int i = 0; i < nodes.Count; i++)
                    {
                        if (i > 0) w.Raw(",");
                        var node = nodes[i];
                        w.Raw("{"); w.Field("id", nodeIds[node]); w.Field("name", node.name);
                        w.Raw("\"parentId\":"); w.String(node.parent != null && nodeIds.TryGetValue(node.parent, out var parentId) ? parentId : null);
                        w.Raw(",\"position\":"); w.Vector(node.localPosition);
                        w.Raw(",\"rotation\":"); var q = node.localRotation; w.Numbers(q.x, q.y, q.z, q.w);
                        w.Raw(",\"scale\":"); w.Vector(node.localScale);
                        var mf = node.GetComponent<MeshFilter>();
                        w.Raw(",\"meshId\":"); w.String(mf != null && mf.sharedMesh != null ? meshIds[mf.sharedMesh] : null);
                        w.Raw(",\"materialIds\":[");
                        var renderer = node.GetComponent<MeshRenderer>();
                        if (renderer != null)
                        {
                            var mats = renderer.sharedMaterials;
                            for (int m = 0; m < mats.Length; m++) { if (m > 0) w.Raw(","); w.String(mats[m] != null ? materialIds[mats[m]] : null); }
                        }
                        w.Raw("],\"category\":"); w.String(Category(node));
                        w.Raw(",\"active\":"); w.Bool(node.gameObject.activeSelf);
                        w.Raw(",\"renderer_enabled\":"); w.Bool(renderer == null || renderer.enabled);
                        w.Raw("}");
                    }
                    w.Raw("],\"metadata\":"); WriteMetadata(w); w.Raw("}");
                }
            }

            void WriteMetadata(Json w)
            {
                w.Raw("{"); w.Field("generated_utc", DateTime.UtcNow.ToString("o", Inv));
                w.Field("source", "RoadGame.World.Generate + frozen Models.Create spawn visuals; edit-mode export, no game save used");
                w.Field("unity_version", Application.unityVersion);
                w.Field("vertex_color_space", QualitySettings.activeColorSpace == ColorSpace.Linear ? "linear" : "srgb");
                w.Field("color_space", QualitySettings.activeColorSpace == ColorSpace.Linear ? "linear" : "srgb");
                w.Field("uv1_usage", "RoadToon shader uses UV1.x for gloss and UV1.y for metal; not a lightmap UV");
                w.Field("limitations", "Static geometry/model snapshot. Runtime scripts, analytical Ground driving, AI, progression and occlusion are not exported as Blender behaviour. Shader lighting is approximated.");
                w.Raw("\"bounds\":"); WriteBounds(w, bounds.min, bounds.max);
                w.Raw(",\"firstZoneBounds\":"); WriteBounds(w, new Vector3(-Content.ZoneHalfWidth, -8, Structures.IntroSouthZ), new Vector3(Content.ZoneHalfWidth, 24, Content.ZoneMaxZ(0)));
                w.Raw(",\"focusPoint\":"); w.Vector(new Vector3(0, 0, -80));
                w.Raw(",\"playerStart\":"); w.Vector(Structures.IntroStart);
                w.Raw(",\"normalStart\":"); w.Vector(world.startPos);
                w.Raw(",\"zones\":[");
                for (int i = 0; i < Content.ZoneCount; i++)
                {
                    if (i > 0) w.Raw(",");
                    w.Raw("{\"index\":"); w.Number(i); w.Raw(","); w.Field("name", Content.Zones[i].name);
                    w.Raw("\"bounds\":"); WriteBounds(w, new Vector3(-Content.ZoneHalfWidth, -8, Content.ZoneMinZ(i)), new Vector3(Content.ZoneHalfWidth, 24, Content.ZoneMaxZ(i))); w.Raw("}");
                }
                w.Raw("],\"roads\":["); bool first = true;
                for (int z = 0; z < Content.ZoneCount; z++)
                    for (int r = 0; r < world.roads[z].Count; r++)
                    {
                        if (!first) w.Raw(","); first = false;
                        w.Raw("{\"zone\":"); w.Number(z); w.Raw(",\"index\":"); w.Number(r); w.Raw(",\"width\":"); w.Number(world.roadWidths[z][r]);
                        w.Raw(",\"points\":"); w.Vectors(world.roads[z][r]); w.Raw("}");
                    }
                w.Raw("],\"spawns\":[");
                for (int i = 0; i < world.spawns.Count; i++)
                {
                    if (i > 0) w.Raw(","); var sp = world.spawns[i];
                    w.Raw("{\"id\":"); w.Number(sp.id); w.Raw(","); w.Field("nodeId", nodeIds[spawnObjects[sp.id]]); w.Field("name", sp.spec.name);
                    w.Field("model", sp.spec.model.ToString()); w.Field("kind", sp.spec.kind.ToString());
                    w.Raw("\"zone\":"); w.Number(sp.zone.index); w.Raw(",\"position\":"); w.Vector(sp.pos);
                    w.Raw(",\"yaw\":"); w.Number(sp.yaw); w.Raw(",\"scale\":"); w.Number(sp.scale); w.Raw(",\"radius\":"); w.Number(sp.spec.radius); w.Raw("}");
                }
                w.Raw("],\"floors\":[");
                for (int i = 0; i < Ground.Pieces.Count; i++)
                {
                    if (i > 0) w.Raw(","); var p = Ground.Pieces[i];
                    w.Raw("{"); w.Field("name", p.name); w.Field("type", p.GetType().Name); w.Field("surface", p.surface.ToString());
                    w.Raw("\"rect\":"); WriteRect(w, p.rect); w.Raw(",\"h0\":"); w.Number(p.h0); w.Raw(",\"h1\":"); w.Number(p.h1);
                    w.Raw(",\"easeIn\":"); w.Number(p.easeIn); w.Raw(",\"easeOut\":"); w.Number(p.easeOut);
                    w.Raw(",\"launch\":"); w.Bool(p.launch); w.Raw(",\"boost\":"); w.Number(p.boost);
                    w.Raw(",\"underground\":"); w.Bool(p.underground); w.Raw(",\"enemyWalkable\":"); w.Bool(p.enemyWalkable);
                    if (p is MoundPiece mound) { w.Raw(",\"top\":"); w.Number(mound.top); w.Raw(",\"plateau\":"); w.Number(mound.plateau); }
                    w.Raw("}");
                }
                w.Raw("],\"holes\":[");
                for (int i = 0; i < Ground.Holes.Count; i++) { if (i > 0) w.Raw(","); WriteRect(w, Ground.Holes[i]); }
                w.Raw("],\"keepouts\":[");
                for (int i = 0; i < Structures.Exclusions.Count; i++) { if (i > 0) w.Raw(","); WriteRect(w, Structures.Exclusions[i]); }
                w.Raw("],\"worksRoute\":"); w.Vectors(Structures.WorksRoute);
                w.Raw(",\"mesaRoute\":"); w.Vectors(Terrain.MesaRoute);
                w.Raw(",\"counts\":{\"nodes\":"); w.Number(nodes.Count); w.Raw(",\"meshes\":"); w.Number(meshes.Count);
                w.Raw(",\"meshInstances\":"); w.Number(meshInstances); w.Raw(",\"uniqueVertices\":"); w.Number(vertexCount);
                w.Raw(",\"uniqueTriangles\":"); w.Number(triangleCount); w.Raw("}}");
            }

            static float Float(Material m, string property, float fallback) => m.HasProperty(property) ? m.GetFloat(property) : fallback;
            static void WriteBounds(Json w, Vector3 min, Vector3 max) { w.Raw("{\"min\":"); w.Vector(min); w.Raw(",\"max\":"); w.Vector(max); w.Raw("}"); }
            static void WriteRect(Json w, ORect r)
            { w.Raw("{\"center\":"); w.Vector(r.Center); w.Raw(",\"half\":"); w.Vector(r.half); w.Raw(",\"yaw\":"); w.Number(r.Yaw); w.Raw("}"); }
            static string Category(Transform t)
            {
                for (var p = t; p != null; p = p.parent)
                {
                    if (p.name.StartsWith("REFERENCE_", StringComparison.Ordinal)) return "reference";
                    if (p.name == "Spawn_Visuals") return "spawn_visual";
                    if (p.name == "Structures") return "structure";
                    if (p.name == "Terrain") return "terrain";
                }
                return "environment";
            }
        }

        /// <summary>Stream the large vertex arrays rather than building a second copy of the whole scene in memory.</summary>
        sealed class Json : IDisposable
        {
            readonly StreamWriter writer;
            public Json(string path) { writer = new StreamWriter(path, false, new UTF8Encoding(false), 1 << 20); }
            public void Dispose() => writer.Dispose();
            public void Raw(string s) => writer.Write(s);
            public void String(string s)
            {
                if (s == null) { Raw("null"); return; }
                writer.Write('"');
                foreach (char c in s)
                {
                    switch (c)
                    {
                        case '"': Raw("\\\""); break;
                        case '\\': Raw("\\\\"); break;
                        case '\n': Raw("\\n"); break;
                        case '\r': Raw("\\r"); break;
                        case '\t': Raw("\\t"); break;
                        default: if (c < 32) Raw("\\u" + ((int)c).ToString("x4", Inv)); else writer.Write(c); break;
                    }
                }
                writer.Write('"');
            }
            public void Field(string name, string value, bool comma = true) { String(name); Raw(":"); String(value); if (comma) Raw(","); }
            public void Number(float n) { if (float.IsNaN(n) || float.IsInfinity(n)) throw new InvalidDataException("Non-finite value in exported geometry"); writer.Write(n.ToString("R", Inv)); }
            public void Number(long n) => writer.Write(n.ToString(Inv));
            public void Bool(bool value) => Raw(value ? "true" : "false");
            public void Numbers(params float[] values) { Raw("["); for (int i = 0; i < values.Length; i++) { if (i > 0) Raw(","); Number(values[i]); } Raw("]"); }
            public void Vector(Vector2 v) => Numbers(v.x, v.y);
            public void Vector(Vector3 v) => Numbers(v.x, v.y, v.z);
            public void Color(Color v) => Numbers(v.r, v.g, v.b, v.a);
            public void Vectors(IList<Vector3> values) { Raw("["); for (int i = 0; i < values.Count; i++) { if (i > 0) Raw(","); var v = values[i]; Number(v.x); Raw(","); Number(v.y); Raw(","); Number(v.z); } Raw("]"); }
            public void Vectors(IList<Vector2> values) { Raw("["); for (int i = 0; i < values.Count; i++) { if (i > 0) Raw(","); var v = values[i]; Number(v.x); Raw(","); Number(v.y); } Raw("]"); }
            public void Colors(IList<Color> values) { Raw("["); for (int i = 0; i < values.Count; i++) { if (i > 0) Raw(","); var v = values[i]; Number(v.r); Raw(","); Number(v.g); Raw(","); Number(v.b); Raw(","); Number(v.a); } Raw("]"); }
            public void Integers(IList<int> values) { Raw("["); for (int i = 0; i < values.Count; i++) { if (i > 0) Raw(","); Number(values[i]); } Raw("]"); }
        }
    }
}
