using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace RoadGame.EditorTools
{
    /// <summary>Builds native, inspectable car assets from the read-only Blender export.</summary>
    public static class ImportedCarSetup
    {
        public const string Art = "Assets/RoadGame/Art/Cars/ScarboundDetailed";
        public const string Prefab = "Assets/RoadGame/Resources/Cars/ScarboundDetailed.prefab";
        const string DefaultInput = "Exports/Blender/2026-11-19/DetailedCar";
        static readonly string[] Sets = { "CarBody", "CarDetails", "Wheels", "HoodGun", "Harpoon", "Quasimodo" };

        [Serializable] class Manifest { public int version; public string source, sourceSha256; public Node[] nodes; public int[] lodTriangles; }
        [Serializable] class Node
        {
            public string name, sourceName, material;
            public int parent;
            public float[] position, rotation, scale;
            public MeshInput[] lods;
        }
        [Serializable] class MeshInput { public string file, sha256; public int vertices, triangles, removedDegenerates; }
        [Serializable] class Report
        {
            public string source, sourceSha256, prefab;
            public int nodes, meshObjects, serializedMeshes, materials;
            public int[] triangles;
            public Vector3 boundsCenter, dimensions;
            public bool hierarchyVerified, texturesVerified, tangentsVerified;
        }

        static string Arg(string key, string fallback)
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == key) return args[i + 1];
            return fallback;
        }

        [MenuItem("RoadGame/Blender/Build Detailed Car")]
        public static void Build()
        {
            WorkAudioMute.Apply();
            string input = Path.GetFullPath(Arg("-carInput", DefaultInput));
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(Path.Combine(input, "manifest.json")));
            if (manifest.version != 1 || manifest.nodes.Length != 52) throw new InvalidDataException("Unexpected car manifest");
            Directory.CreateDirectory(Art + "/Meshes");
            Directory.CreateDirectory(Art + "/Materials");
            Directory.CreateDirectory(Path.GetDirectoryName(Prefab));
            AssetDatabase.Refresh();
            var materials = BuildMaterials();
            var transforms = new Transform[manifest.nodes.Length];
            var renderers = new[] { new List<Renderer>(), new List<Renderer>(), new List<Renderer>() };
            var root = new GameObject("PlayerCar");
            try
            {
                transforms[0] = root.transform;
                root.AddComponent<ImportedCar>();
                // Resolve parents separately; Blender's subtree order need not be topological.
                for (int i = 1; i < transforms.Length; i++) transforms[i] = new GameObject(manifest.nodes[i].name).transform;
                for (int i = 1; i < transforms.Length; i++)
                {
                    var n = manifest.nodes[i];
                    transforms[i].SetParent(transforms[n.parent], false);
                    transforms[i].localPosition = V3(n.position);
                    transforms[i].localRotation = new Quaternion(n.rotation[0], n.rotation[1], n.rotation[2], n.rotation[3]);
                    transforms[i].localScale = V3(n.scale);
                }
                int meshObjects = 0;
                for (int i = 1; i < transforms.Length; i++)
                {
                    var n = manifest.nodes[i];
                    if (n.lods.Length == 0) continue;
                    if (n.lods.Length != 3) throw new InvalidDataException("Missing LOD: " + n.sourceName);
                    meshObjects++;
                    for (int level = 0; level < 3; level++)
                    {
                        var target = transforms[i].gameObject;
                        if (level > 0)
                        {
                            target = new GameObject("LOD" + level);
                            target.transform.SetParent(transforms[i], false);
                        }
                        string name = i.ToString("00") + "_" + n.name + "_LOD" + level;
                        string asset = Art + "/Meshes/" + name + ".asset";
                        var mesh = ReadMesh(Path.Combine(input, n.lods[level].file), n.lods[level], name);
                        var saved = AssetDatabase.LoadAssetAtPath<Mesh>(asset);
                        if (saved != null) { EditorUtility.CopySerialized(mesh, saved); UnityEngine.Object.DestroyImmediate(mesh); mesh = saved; }
                        else AssetDatabase.CreateAsset(mesh, asset);
                        target.AddComponent<MeshFilter>().sharedMesh = mesh;
                        var renderer = target.AddComponent<MeshRenderer>();
                        renderer.sharedMaterial = materials[n.material];
                        renderer.shadowCastingMode = ShadowCastingMode.On;
                        renderer.receiveShadows = true;
                        renderers[level].Add(renderer);
                    }
                }
                if (meshObjects != 29) throw new InvalidDataException("Expected 29 car mesh objects");
                var group = root.AddComponent<LODGroup>();
                group.fadeMode = LODFadeMode.None;
                group.SetLODs(new[] { new LOD(.55f, renderers[0].ToArray()), new LOD(.28f, renderers[1].ToArray()), new LOD(.001f, renderers[2].ToArray()) });
                group.RecalculateBounds();
                AssetDatabase.SaveAssets();
                PrefabUtility.SaveAsPrefabAsset(root, Prefab);
                AssetDatabase.SaveAssets();
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
            Validate();
        }

        public static void BuildAndBakeIcon()
        {
            Build();
            IconStudio.Bake(new HashSet<Icon> { Icon.Car });
        }

        static Vector3 V3(float[] v) => new Vector3(v[0], v[1], v[2]);

        static Dictionary<string, Material> BuildMaterials()
        {
            Mats.Init();
            var result = new Dictionary<string, Material>();
            foreach (var set in Sets)
            {
                string path = Art + "/Materials/M_" + set + ".mat";
                var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (mat == null)
                {
                    mat = new Material(set == "CarBody" ? Mats.CarPaint : Mats.Toon) { name = "M_" + set };
                    AssetDatabase.CreateAsset(mat, path);
                }
                mat.SetFloat("_VertexColorWeight", 0f);
                mat.SetFloat("_UseBakedMaps", 1f);
                mat.SetFloat("_BumpScale", 1f);
                mat.SetFloat("_OcclusionStrength", 1f);
                mat.SetFloat("_DustAmount", .02f); // wear/dust is already baked in Blender
                mat.SetColor("_BaseColor", Color.white);
                mat.EnableKeyword("_BAKED_MAPS");
                SetMap(mat, set, "BaseColor", "_BaseMap");
                SetMap(mat, set, "Normal", "_BumpMap");
                SetMap(mat, set, "MetallicSmoothness", "_MetallicGlossMap");
                SetMap(mat, set, "AO", "_OcclusionMap");
                EditorUtility.SetDirty(mat);
                result.Add(set, mat);
            }
            return result;
        }

        static void SetMap(Material mat, string set, string suffix, string property)
        {
            string path = Art + "/Textures/T_" + set + "_" + suffix + ".png";
            var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            if (texture == null) throw new FileNotFoundException("Missing car texture", path);
            mat.SetTexture(property, texture);
        }

        static Mesh ReadMesh(string path, MeshInput expected, string name)
        {
            using var reader = new BinaryReader(File.OpenRead(path));
            int vc = reader.ReadInt32(), ic = reader.ReadInt32();
            if (vc != expected.vertices || ic != expected.triangles * 3) throw new InvalidDataException(path);
            var positions = new Vector3[vc]; var normals = new Vector3[vc]; var colors = new Color[vc];
            var uv0 = new Vector2[vc]; var uv1 = new Vector2[vc]; var indices = new int[ic];
            for (int i = 0; i < vc; i++)
            {
                positions[i] = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
                normals[i] = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
                colors[i] = new Color(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
                uv0[i] = new Vector2(reader.ReadSingle(), reader.ReadSingle());
                uv1[i] = new Vector2(reader.ReadSingle(), reader.ReadSingle());
            }
            for (int i = 0; i < ic; i++)
            {
                indices[i] = reader.ReadInt32();
                if (indices[i] < 0 || indices[i] >= vc) throw new InvalidDataException("Bad car index: " + path);
            }
            if (reader.BaseStream.Position != reader.BaseStream.Length) throw new InvalidDataException("Trailing car data: " + path);
            var mesh = new Mesh { name = name, indexFormat = vc > 65535 ? IndexFormat.UInt32 : IndexFormat.UInt16 };
            mesh.vertices = positions; mesh.normals = normals; mesh.colors = colors; mesh.uv = uv0; mesh.uv2 = uv1;
            mesh.triangles = indices;
            mesh.RecalculateBounds();
            mesh.RecalculateTangents();
            return mesh;
        }

        public static void Validate()
        {
            string input = Path.GetFullPath(Arg("-carInput", DefaultInput));
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(Path.Combine(input, "manifest.json")));
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Prefab);
            if (prefab == null || prefab.GetComponent<ImportedCar>() == null) throw new InvalidDataException("Car prefab/marker missing");
            var group = prefab.GetComponent<LODGroup>();
            var lods = group.GetLODs();
            if (lods.Length != 3) throw new InvalidDataException("Car LODs missing");
            int[] triangles = new int[3];
            var all = new HashSet<Mesh>();
            for (int l = 0; l < lods.Length; l++)
            {
                if (lods[l].renderers.Length != 29) throw new InvalidDataException("LOD renderer count");
                foreach (var r in lods[l].renderers)
                {
                    var mesh = r.GetComponent<MeshFilter>().sharedMesh;
                    all.Add(mesh);
                    triangles[l] += (int)mesh.GetIndexCount(0) / 3;
                    if (mesh.normals.Length != mesh.vertexCount || mesh.colors.Length != mesh.vertexCount || mesh.uv.Length != mesh.vertexCount || mesh.uv2.Length != mesh.vertexCount || mesh.tangents.Length != mesh.vertexCount)
                        throw new InvalidDataException("Car vertex stream missing: " + mesh.name);
                    foreach (var t in mesh.tangents)
                        if (float.IsNaN(t.x) || float.IsNaN(t.y) || float.IsNaN(t.z) || Mathf.Abs(t.w) < .5f)
                            throw new InvalidDataException("Car tangent invalid: " + mesh.name);
                    var mat = r.sharedMaterial;
                    foreach (string property in new[] { "_BaseMap", "_BumpMap", "_MetallicGlossMap", "_OcclusionMap" })
                        if (mat.GetTexture(property) == null) throw new InvalidDataException("Car texture missing: " + mat.name);
                }
                if (triangles[l] != manifest.lodTriangles[l]) throw new InvalidDataException("Car triangle count changed");
            }
            foreach (string path in new[] { "Body", "WheelSteer_FL/Wheel", "WheelSteer_FR/Wheel", "Wheel_RL/Wheel", "Wheel_RR/Wheel", "Body/TurretBase/TurretYaw/TurretPitch/Barrel0/HoodGun_Muzzle", "Body/Harpooner/TurretYaw/Launcher/GripR", "Body/Harpooner/TurretYaw/Quasimodo/Body/ShoulderL" })
                if (prefab.transform.Find(path) == null) throw new InvalidDataException("Car animation hook missing: " + path);
            var bounds = lods[0].renderers[0].bounds;
            foreach (var r in lods[0].renderers) bounds.Encapsulate(r.bounds);
            if (bounds.size.x < 2f || bounds.size.x > 2.6f || bounds.size.y < 1.8f || bounds.size.y > 2.3f || bounds.size.z < 4.7f || bounds.size.z > 5.4f)
                throw new InvalidDataException("Car dimensions incorrect: " + bounds.size);
            var report = new Report { source = manifest.source, sourceSha256 = manifest.sourceSha256, prefab = Prefab,
                nodes = manifest.nodes.Length, meshObjects = 29, serializedMeshes = all.Count, materials = 6,
                triangles = triangles, boundsCenter = bounds.center, dimensions = bounds.size,
                hierarchyVerified = true, texturesVerified = true, tangentsVerified = true };
            Directory.CreateDirectory("Docs/screenshots/blender-car-integration");
            File.WriteAllText("Docs/screenshots/blender-car-integration/import_report.json", JsonUtility.ToJson(report, true));
            Debug.Log("RoadGame IMPORTEDCAR VERIFIED " + JsonUtility.ToJson(report));
        }
    }

    public sealed class ImportedCarTextureSettings : AssetPostprocessor
    {
        void OnPreprocessTexture()
        {
            if (!assetPath.StartsWith(ImportedCarSetup.Art + "/Textures/", StringComparison.Ordinal)) return;
            var importer = (TextureImporter)assetImporter;
            bool normal = assetPath.EndsWith("_Normal.png", StringComparison.Ordinal);
            importer.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
            importer.sRGBTexture = assetPath.EndsWith("_BaseColor.png", StringComparison.Ordinal);
            importer.convertToNormalmap = false;
            importer.flipGreenChannel = false;
            importer.alphaSource = TextureImporterAlphaSource.FromInput;
            importer.alphaIsTransparency = false; // metallic map alpha is smoothness
            importer.mipmapEnabled = true;
            importer.filterMode = FilterMode.Trilinear;
            importer.wrapMode = TextureWrapMode.Clamp;
            importer.maxTextureSize = assetPath.Contains("T_CarBody_") ? 4096 : 2048;
            importer.isReadable = false;
            importer.textureCompression = TextureImporterCompression.CompressedHQ;
        }
    }
}
