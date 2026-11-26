using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace RoadGame.EditorTools
{
    /// <summary>
    /// Bakes the UI icon sprites from the toy-like 3D models in <see cref="IconModels"/>: one studio for every icon
    /// (same camera angle, lens, key / fill / rim light, soft self-shadows), 4x supersampled, exact alpha from a
    /// black + white background pair, a soft drop shadow, and the same padding for every icon.
    /// Output: Assets/RoadGame/Resources/Icons/&lt;Icon&gt;.png (+ &lt;Icon&gt;_Locked.png for weapons / armor), imported by
    /// <see cref="IconImport"/> as mip-mapped sprites. Loaded at runtime by Tex.Get(Icon).
    /// Menu: RoadGame ▸ Icons ▸ Bake UI Icons. Batch: -executeMethod RoadGame.EditorTools.IconStudio.BakeBatch [-iconOnly Heart,Gem]
    /// </summary>
    public static class IconStudio
    {
        public const string OutDir = "Assets/RoadGame/Resources/Icons";
        public const int Size = 256;
        const int SS = 4;
        const int RenderSize = Size * SS;
        const float CamElevation = 16f, CamFov = 18f, CamDistance = 12f;
        const int StudioLayer = 30;

        /// <summary>Icons that also get a dimmed, desaturated "locked" sprite (weapon and armor slots).</summary>
        public static readonly Icon[] LockedVariants = { Icon.Gun, Icon.Smash, Icon.Pierce, Icon.Blast, Icon.BullBar, Icon.RoofPlates };

        [MenuItem("RoadGame/Icons/Bake UI Icons")]
        static void BakeMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            var setup = EditorSceneManager.GetSceneManagerSetup();
            try { Bake(null); }
            finally
            {
                if (setup != null && setup.Length > 0) EditorSceneManager.RestoreSceneManagerSetup(setup);
                else EditorSceneManager.OpenScene(ProjectSetup.ScenePath);
            }
        }

        public static void BakeBatch()
        {
            try
            {
                var args = Environment.GetCommandLineArgs();
                HashSet<Icon> only = null;
                for (int i = 0; i < args.Length - 1; i++)
                    if (args[i] == "-iconOnly")
                    {
                        only = new HashSet<Icon>();
                        foreach (var n in args[i + 1].Split(',')) only.Add((Icon)Enum.Parse(typeof(Icon), n.Trim()));
                    }
                Bake(only);
                EditorApplication.Exit(0);
            }
            catch (Exception e)
            {
                Debug.LogException(e);
                EditorApplication.Exit(1);
            }
        }

        static void SetStudioLighting()
        {
            Shader.SetGlobalVector("_IcoKeyColor", new Vector4(1.1f, 1.05f, 0.98f, 1f));
            Shader.SetGlobalVector("_IcoSkyColor", new Vector4(0.64f, 0.69f, 0.88f, 1f));
            Shader.SetGlobalVector("_IcoGroundColor", new Vector4(0.8f, 0.67f, 0.58f, 1f));
            Shader.SetGlobalVector("_IcoShadowTint", new Vector4(0.82f, 0.78f, 0.97f, 1f));
            Shader.SetGlobalVector("_IcoRimColor", new Vector4(1f, 0.96f, 0.9f, 0.55f));
            Shader.SetGlobalVector("_IcoRimDir", new Vector4(0.55f, 0.5f, 0.67f, 0f));
            Shader.SetGlobalVector("_IcoEnvTop", new Vector4(1.3f, 1.3f, 1.34f, 1f));
            Shader.SetGlobalVector("_IcoEnvBottom", new Vector4(0.3f, 0.29f, 0.34f, 1f));
            Shader.SetGlobalVector("_IcoParams", new Vector4(0.45f, 1f, 0.85f, 0.8f));
            Shader.SetGlobalVector("_IcoParams2", new Vector4(0.55f, 0.22f, 0f, 0f));
        }

        public static void Bake(HashSet<Icon> only)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.fog = false;
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.5f, 0.5f, 0.5f);

            var urp = GraphicsSettings.currentRenderPipeline as UniversalRenderPipelineAsset;
            float oldDist = urp != null ? urp.shadowDistance : 0f;
            int oldCascades = urp != null ? urp.shadowCascadeCount : 1, oldRes = urp != null ? urp.mainLightShadowmapResolution : 2048;
            if (urp != null) { urp.shadowDistance = 22f; urp.shadowCascadeCount = 1; urp.mainLightShadowmapResolution = 4096; }

            float oldQuality = MeshBuilder.Quality;
            MeshBuilder.Quality = 3f;
            var shader = Shader.Find("Hidden/RoadGame/IconStudio");
            if (shader == null) throw new Exception("IconStudio shader missing");
            var mat = new Material(shader) { name = "IconStudio" };
            SetStudioLighting();

            var lightGo = new GameObject("IconKeyLight");
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.color = Color.white;
            light.intensity = 1f;
            light.shadows = LightShadows.Soft;
            light.shadowStrength = 1f;
            light.shadowBias = 0.5f;
            light.shadowNormalBias = 0.4f;
            light.transform.rotation = Quaternion.LookRotation(new Vector3(0.5f, -0.72f, 0.48f).normalized, Vector3.up);
            var lightData = lightGo.AddComponent<UniversalAdditionalLightData>();
            lightData.usePipelineSettings = false;
            RenderSettings.sun = light;

            var camGo = new GameObject("IconCamera");
            var cam = camGo.AddComponent<Camera>();
            cam.fieldOfView = CamFov;
            cam.nearClipPlane = 1f;
            cam.farClipPlane = 40f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.allowHDR = false;
            cam.allowMSAA = true;
            cam.transform.rotation = Quaternion.Euler(CamElevation, 0f, 0f);
            cam.transform.position = -cam.transform.forward * CamDistance;
            var camData = cam.GetUniversalAdditionalCameraData();
            camData.renderPostProcessing = false;
            camData.antialiasing = AntialiasingMode.None;
            camData.renderShadows = true;
            var rt = new RenderTexture(RenderSize, RenderSize, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
            rt.Create();
            cam.targetTexture = rt;

            Directory.CreateDirectory(OutDir);
            int count = 0;
            try
            {
                foreach (Icon icon in Enum.GetValues(typeof(Icon)))
                {
                    if (only != null && !only.Contains(icon)) continue;
                    var root = BuildModel(icon, mat, out var pose);
                    root.transform.rotation = pose.Rotation;
                    Fit(root, cam, pose.fill);
                    var black = Grab(cam, rt, Color.black);
                    var white = Grab(cam, rt, Color.white);
                    UnityEngine.Object.DestroyImmediate(root);
                    Compose(black, white, out var premul, out var alpha);
                    Save(Path.Combine(OutDir, icon + ".png"), premul, alpha, false);
                    if (Array.IndexOf(LockedVariants, icon) >= 0) Save(Path.Combine(OutDir, icon + "_Locked.png"), premul, alpha, true);
                    count++;
                }
            }
            finally
            {
                cam.targetTexture = null;
                rt.Release();
                UnityEngine.Object.DestroyImmediate(camGo);
                UnityEngine.Object.DestroyImmediate(lightGo);
                MeshBuilder.Quality = oldQuality;
                if (urp != null) { urp.shadowDistance = oldDist; urp.shadowCascadeCount = oldCascades; urp.mainLightShadowmapResolution = oldRes; }
            }
            AssetDatabase.Refresh();
            Debug.Log($"RoadGame IconStudio: baked {count} icons into {OutDir} in {sw.ElapsedMilliseconds} ms");
        }

        // ------------------------------------------------------------------ models
        static GameObject BuildModel(Icon icon, Material mat, out IconPose pose)
        {
            GameObject root;
            if (icon == Icon.Car)
            {
                root = BuildCar();
                pose = new IconPose(-16f, 146f, 0f, 0.9f);
            }
            else
            {
                var mesh = IconModels.Build(icon, out pose);
                root = new GameObject("Icon_" + icon);
                root.AddComponent<MeshFilter>().sharedMesh = mesh;
                root.AddComponent<MeshRenderer>();
            }
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
            {
                if (!(r is MeshRenderer)) { r.enabled = false; continue; }
                var mats = new Material[r.sharedMaterials.Length];
                for (int i = 0; i < mats.Length; i++) mats[i] = mat;
                r.sharedMaterials = mats;
                r.shadowCastingMode = ShadowCastingMode.On;
                r.receiveShadows = true;
                r.gameObject.layer = StudioLayer;
            }
            return root;
        }

        /// <summary>The hero pickup (body, wheels, the hood machine gun, the harpoon turret with its operator) as in the
        /// game, for the Car icon.</summary>
        static GameObject BuildCar()
        {
            Mats.Init();
            var car = Models.PlayerCar(out var rig);
            Models.HoodGun(rig.body, 0, null);   // resting: level, straight ahead
            var h = Models.Harpooner(rig.body);
            h.yaw.localRotation = Quaternion.Euler(0, 15f, 0);   // the harpoon over the cab, turned a little
            Models.SolveHarpoonerArms(h);
            return car;
        }

        // ------------------------------------------------------------------ framing
        /// <summary>Scales and shifts the model so its projected silhouette is centered and its larger side = fill.</summary>
        static void Fit(GameObject root, Camera cam, float fill)
        {
            var filters = root.GetComponentsInChildren<MeshFilter>();
            var verts = new List<(Transform t, Vector3[] v)>();
            foreach (var f in filters) if (f.sharedMesh != null && f.GetComponent<Renderer>().enabled) verts.Add((f.transform, f.sharedMesh.vertices));
            // coarse normalization first: bounds center at the origin, ~3 units across
            var bounds = new Bounds();
            bool first = true;
            foreach (var (t, v) in verts)
                foreach (var p in v) { var w = t.TransformPoint(p); if (first) { bounds = new Bounds(w, Vector3.zero); first = false; } else bounds.Encapsulate(w); }
            float ext = Mathf.Max(bounds.size.x, Mathf.Max(bounds.size.y, bounds.size.z));
            root.transform.position -= bounds.center;
            float k0 = 3f / Mathf.Max(0.001f, ext);
            root.transform.localScale *= k0;
            root.transform.position *= k0;
            for (int iter = 0; iter < 6; iter++)
            {
                var (minX, minY, maxX, maxY) = Project(verts, cam);
                float k = fill / Mathf.Max(0.0001f, Mathf.Max(maxX - minX, maxY - minY));
                root.transform.localScale *= k;
                (minX, minY, maxX, maxY) = Project(verts, cam);
                float cx = (minX + maxX) * 0.5f - 0.5f, cy = (minY + maxY) * 0.5f - 0.5f;
                float depth = Vector3.Dot(root.transform.position - cam.transform.position, cam.transform.forward);
                float hgt = 2f * depth * Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad);
                root.transform.position -= cam.transform.right * (cx * hgt * cam.aspect) + cam.transform.up * (cy * hgt);
            }
        }

        static (float, float, float, float) Project(List<(Transform t, Vector3[] v)> verts, Camera cam)
        {
            float minX = 1e9f, minY = 1e9f, maxX = -1e9f, maxY = -1e9f;
            foreach (var (t, v) in verts)
            {
                var m = t.localToWorldMatrix;
                foreach (var p in v)
                {
                    var vp = cam.WorldToViewportPoint(m.MultiplyPoint3x4(p));
                    if (vp.x < minX) minX = vp.x;
                    if (vp.x > maxX) maxX = vp.x;
                    if (vp.y < minY) minY = vp.y;
                    if (vp.y > maxY) maxY = vp.y;
                }
            }
            return (minX, minY, maxX, maxY);
        }

        // ------------------------------------------------------------------ capture + compose
        static Color[] Grab(Camera cam, RenderTexture rt, Color bg)
        {
            cam.backgroundColor = bg;
            cam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var tex = new Texture2D(RenderSize, RenderSize, TextureFormat.RGBA32, false, false);
            tex.ReadPixels(new Rect(0, 0, RenderSize, RenderSize), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            var px = tex.GetPixels();
            UnityEngine.Object.DestroyImmediate(tex);
            return px;
        }

        /// <summary>Exact coverage from the black / white pair (linear), then a 4x4 box downsample (premultiplied).</summary>
        static void Compose(Color[] black, Color[] white, out Vector3[] premul, out float[] alpha)
        {
            premul = new Vector3[Size * Size];
            alpha = new float[Size * Size];
            const float inv = 1f / (SS * SS);
            for (int y = 0; y < Size; y++)
                for (int x = 0; x < Size; x++)
                {
                    Vector3 acc = Vector3.zero; float a = 0f;
                    for (int sy = 0; sy < SS; sy++)
                        for (int sx = 0; sx < SS; sx++)
                        {
                            int i = (y * SS + sy) * RenderSize + x * SS + sx;
                            var b = black[i]; var w = white[i];
                            var bl = new Vector3(Mathf.GammaToLinearSpace(b.r), Mathf.GammaToLinearSpace(b.g), Mathf.GammaToLinearSpace(b.b));
                            var wl = new Vector3(Mathf.GammaToLinearSpace(w.r), Mathf.GammaToLinearSpace(w.g), Mathf.GammaToLinearSpace(w.b));
                            float cov = Mathf.Clamp01(1f - ((wl.x - bl.x) + (wl.y - bl.y) + (wl.z - bl.z)) / 3f);
                            acc += bl;
                            a += cov;
                        }
                    premul[y * Size + x] = acc * inv;
                    alpha[y * Size + x] = a * inv;
                }
        }

        static float[] Blur(float[] src, float sigma)
        {
            int r = Mathf.CeilToInt(sigma * 3f);
            var kernel = new float[r * 2 + 1];
            float sum = 0f;
            for (int i = -r; i <= r; i++) { kernel[i + r] = Mathf.Exp(-i * i / (2f * sigma * sigma)); sum += kernel[i + r]; }
            for (int i = 0; i < kernel.Length; i++) kernel[i] /= sum;
            var tmp = new float[src.Length];
            var dst = new float[src.Length];
            for (int y = 0; y < Size; y++)
                for (int x = 0; x < Size; x++)
                {
                    float v = 0f;
                    for (int k = -r; k <= r; k++) { int xx = Mathf.Clamp(x + k, 0, Size - 1); v += src[y * Size + xx] * kernel[k + r]; }
                    tmp[y * Size + x] = v;
                }
            for (int y = 0; y < Size; y++)
                for (int x = 0; x < Size; x++)
                {
                    float v = 0f;
                    for (int k = -r; k <= r; k++) { int yy = Mathf.Clamp(y + k, 0, Size - 1); v += tmp[yy * Size + x] * kernel[k + r]; }
                    dst[y * Size + x] = v;
                }
            return dst;
        }

        /// <summary>Adds the shared soft drop shadow (same offset / blur / opacity for every icon) and writes the PNG.</summary>
        static void Save(string path, Vector3[] premulIn, float[] alphaIn, bool locked)
        {
            var premul = (Vector3[])premulIn.Clone();
            if (locked)
            {
                for (int i = 0; i < premul.Length; i++)
                {
                    float a = alphaIn[i];
                    if (a <= 0.0001f) continue;
                    var c = premul[i] / a;
                    float l = c.x * 0.2126f + c.y * 0.7152f + c.z * 0.0722f;
                    var g = new Vector3(l * 0.92f, l * 0.95f, l * 1.04f);
                    var outC = Vector3.Lerp(g, c, 0.12f) * 0.5f + new Vector3(0.025f, 0.027f, 0.032f);
                    premul[i] = outC * a;
                }
            }
            var blurred = Blur(alphaIn, 3.2f);
            const int dy = 5;
            const float shadowOpacity = 0.34f;
            var shadowCol = new Vector3(Mathf.GammaToLinearSpace(0.16f), Mathf.GammaToLinearSpace(0.1f), Mathf.GammaToLinearSpace(0.08f));
            var outPx = new Color32[Size * Size];
            for (int y = 0; y < Size; y++)
                for (int x = 0; x < Size; x++)
                {
                    int i = y * Size + x;
                    int sy = y + dy;   // texture rows go up: the shadow falls below the icon
                    float sa = sy < Size ? blurred[sy * Size + x] * shadowOpacity : 0f;
                    float a = alphaIn[i];
                    var p = premul[i] + shadowCol * (sa * (1f - a));
                    float oa = a + sa * (1f - a);
                    Color32 c;
                    if (oa <= 0.0001f) c = new Color32(0, 0, 0, 0);
                    else
                    {
                        var lin = p / oa;
                        c = new Color32(
                            (byte)Mathf.RoundToInt(Mathf.Clamp01(Mathf.LinearToGammaSpace(lin.x)) * 255f),
                            (byte)Mathf.RoundToInt(Mathf.Clamp01(Mathf.LinearToGammaSpace(lin.y)) * 255f),
                            (byte)Mathf.RoundToInt(Mathf.Clamp01(Mathf.LinearToGammaSpace(lin.z)) * 255f),
                            (byte)Mathf.RoundToInt(Mathf.Clamp01(oa) * 255f));
                    }
                    outPx[i] = c;
                }
            var tex = new Texture2D(Size, Size, TextureFormat.RGBA32, false);
            tex.SetPixels32(outPx);
            tex.Apply();
            File.WriteAllBytes(path, tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
        }
    }

    /// <summary>Import settings for the baked icons: mip-mapped single sprites, transparent, high quality compression.</summary>
    public class IconImport : AssetPostprocessor
    {
        void OnPreprocessTexture()
        {
            if (!assetPath.Replace('\\', '/').StartsWith(IconStudio.OutDir + "/")) return;
            var ti = (TextureImporter)assetImporter;
            ti.textureType = TextureImporterType.Sprite;
            ti.spriteImportMode = SpriteImportMode.Single;
            ti.spritePixelsPerUnit = 100f;
            ti.alphaSource = TextureImporterAlphaSource.FromInput;
            ti.alphaIsTransparency = true;
            ti.sRGBTexture = true;
            ti.mipmapEnabled = true;
            ti.mipmapFilter = TextureImporterMipFilter.KaiserFilter;
            ti.mipMapBias = -0.3f;
            ti.wrapMode = TextureWrapMode.Clamp;
            ti.filterMode = FilterMode.Trilinear;
            ti.npotScale = TextureImporterNPOTScale.None;
            ti.maxTextureSize = IconStudio.Size;
            ti.textureCompression = TextureImporterCompression.CompressedHQ;
            var s = new TextureImporterSettings();
            ti.ReadTextureSettings(s);
            s.spriteMeshType = SpriteMeshType.FullRect;
            s.spriteGenerateFallbackPhysicsShape = false;
            ti.SetTextureSettings(s);
            foreach (var platform in new[] { "Android", "iPhone" })
            {
                var p = ti.GetPlatformTextureSettings(platform);
                p.overridden = true;
                p.maxTextureSize = IconStudio.Size;
                p.format = TextureImporterFormat.ASTC_4x4;
                ti.SetPlatformTextureSettings(p);
            }
        }
    }
}
