using System;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.UI;

namespace RoadGame.EditorTools
{
    /// <summary>Renders the actual native loading canvas at exact viewports without starting gameplay.</summary>
    public static class LoadingPreview
    {
        const BindingFlags AnyInstance = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;

        public static void Run()
        {
            try
            {
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                Capture(390, 844, "native-portrait.png");
                Capture(1920, 1080, "native-desktop.png");
                Debug.Log("RoadGame LoadingPreview: captured both native loading layouts.");
                EditorApplication.Exit(0);
            }
            catch (Exception error)
            {
                Debug.LogException(error);
                EditorApplication.Exit(1);
            }
        }

        static void Capture(int width, int height, string filename)
        {
            var loading = LoadingScreen.Create();
            loading.SetProgress(0.9f);
            var canvas = loading.GetComponent<Canvas>();
            var cameraObject = new GameObject("LoadingPreviewCamera");
            var camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Color.black;
            camera.orthographic = true;
            camera.transform.position = new Vector3(0f, 0f, -10f);
            camera.nearClipPlane = 0.01f;
            var target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            target.Create();
            camera.targetTexture = target;
            canvas.renderMode = RenderMode.ScreenSpaceCamera;
            canvas.worldCamera = camera;
            canvas.planeDistance = 1f;
            typeof(CanvasScaler).GetMethod("Handle", AnyInstance).Invoke(canvas.GetComponent<CanvasScaler>(), null);
            typeof(LoadingScreen).GetMethod("Layout", AnyInstance).Invoke(loading, null);
            Canvas.ForceUpdateCanvases();
            LayoutRebuilder.ForceRebuildLayoutImmediate((RectTransform)canvas.transform);
            Canvas.ForceUpdateCanvases();
            if (Mathf.RoundToInt(canvas.pixelRect.width) != width || Mathf.RoundToInt(canvas.pixelRect.height) != height)
                throw new Exception("Canvas viewport differs from requested capture size: " + canvas.pixelRect);
            camera.Render();
            var previous = RenderTexture.active;
            RenderTexture.active = target;
            var image = new Texture2D(width, height, TextureFormat.RGB24, false);
            image.ReadPixels(new Rect(0f, 0f, width, height), 0, 0);
            image.Apply();
            RenderTexture.active = previous;
            string directory = Path.GetFullPath("Docs/screenshots/loading-refresh");
            Directory.CreateDirectory(directory);
            File.WriteAllBytes(Path.Combine(directory, filename), image.EncodeToPNG());
            Debug.Log($"RoadGame LoadingPreview: saved {filename}, Canvas={canvas.pixelRect}, poster={loading.transform.Find("CompletePortraitPoster").GetComponent<RectTransform>().rect}");
            UnityEngine.Object.DestroyImmediate(image);
            UnityEngine.Object.DestroyImmediate(loading.gameObject);
            UnityEngine.Object.DestroyImmediate(cameraObject);
            target.Release();
            UnityEngine.Object.DestroyImmediate(target);
        }
    }
}
