using System.IO;
using UnityEngine;

namespace RoadGame.EditorTools
{
    /// <summary>Renders the player's car (with the harpooner) into a square app icon PNG. Used by the editor capture tool.</summary>
    public static class IconMaker
    {
        public const int IconLayer = 31;

        public static void Render(string path, int size = 1024)
        {
            var g = Game.I;
            if (g == null || g.player == null) return;
            var car = g.player.transform;
            var layers = new System.Collections.Generic.Dictionary<Transform, int>();
            foreach (var t in car.GetComponentsInChildren<Transform>(true)) { layers[t] = t.gameObject.layer; t.gameObject.layer = IconLayer; }

            var camGo = new GameObject("IconCam");
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.98f, 0.62f, 0.2f, 1f);
            cam.cullingMask = 1 << IconLayer;
            cam.fieldOfView = 30f;
            cam.nearClipPlane = 0.3f;
            cam.farClipPlane = 60f;
            var focus = car.position + Vector3.up * 0.9f;
            var dir = Quaternion.Euler(32f, car.eulerAngles.y + 145f, 0f) * Vector3.forward;
            cam.transform.position = focus - dir * 11.5f;
            cam.transform.LookAt(focus);

            var rt = new RenderTexture(size, size, 24, RenderTextureFormat.ARGB32) { antiAliasing = 8 };
            rt.Create();
            cam.targetTexture = rt;
            cam.Render();
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var tex = new Texture2D(size, size, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, size, size), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;

            // soft radial vignette for depth
            var px = tex.GetPixels();
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float dx = (x + 0.5f) / size - 0.5f, dy = (y + 0.5f) / size - 0.5f;
                    float d = Mathf.Sqrt(dx * dx + dy * dy) * 1.6f;
                    px[y * size + x] *= Mathf.Lerp(1.08f, 0.62f, Mathf.Clamp01(d * d));
                }
            tex.SetPixels(px);
            tex.Apply();
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllBytes(path, tex.EncodeToPNG());

            cam.targetTexture = null;
            Object.DestroyImmediate(camGo);
            rt.Release();
            foreach (var kv in layers) if (kv.Key != null) kv.Key.gameObject.layer = kv.Value;
        }
    }
}
