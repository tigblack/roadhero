using UnityEngine;
using UnityEngine.UI;
#if UNITY_WEBGL && !UNITY_EDITOR
using System.Runtime.InteropServices;
#endif

namespace RoadGame
{
    /// <summary>One complete illustrated poster, with real build progress in a separate compact footer.</summary>
    public class LoadingScreen : MonoBehaviour
    {
        static readonly Color Ink = new Color(0.035f, 0.045f, 0.055f, 1f);
        static readonly Color Amber = new Color(1f, 0.73f, 0.2f, 1f);
        const float FooterHeight = 220f;
        RectTransform poster, footerContent;
        RawImage artwork;
        Text posterTitle, posterSubtitle, posterGenre;
        Text status, percent;
        Image fill;
        float progress;
        int screenWidth, screenHeight;

#if UNITY_WEBGL && !UNITY_EDITOR
        [DllImport("__Internal")] static extern void RoadGameLoadingProgress(float value);
        [DllImport("__Internal")] static extern void RoadGameLoadingReady();
#endif

        public static LoadingScreen Create()
        {
            var canvas = UI.CreateCanvas("LoadingCanvas", 100);
            var loading = canvas.gameObject.AddComponent<LoadingScreen>();
#if UNITY_WEBGL && !UNITY_EDITOR
            // HTML displays the same full poster before Unity downloads, and remains the only Web cover.
            canvas.enabled = false;
#else
            loading.Build(canvas);
#endif
            loading.SetProgress(0f);
            return loading;
        }

        void Build(Canvas canvas)
        {
            var scaler = canvas.GetComponent<CanvasScaler>();
            scaler.referenceResolution = new Vector2(1080f, 1920f);
            scaler.screenMatchMode = CanvasScaler.ScreenMatchMode.Expand;
            var root = (RectTransform)canvas.transform;
            var bg = UI.Img(root, "DarkSides", null, Ink, true);
            UI.Stretch(bg.rectTransform);

            poster = UI.Rect("CompletePortraitPoster", root);
            poster.anchorMin = poster.anchorMax = poster.pivot = new Vector2(0.5f, 0.5f);
            artwork = poster.gameObject.AddComponent<RawImage>();
            artwork.texture = Resources.Load<Texture2D>("Loading/loading-poster");
            artwork.color = artwork.texture != null ? Color.white : Ink;
            artwork.raycastTarget = false;
            artwork.uvRect = new Rect(0f, 0f, 1f, 1f); // Always preserve every story fragment.
            posterTitle = PosterText("PosterTitle", "SCARBOUND");
            posterSubtitle = PosterText("PosterSubtitle", "CAR COMBAT");
            posterGenre = PosterText("PosterGenre", "IDLE RPG");

            var footer = UI.Img(root, "LoadingFooter", null, Ink, true);
            footer.rectTransform.anchorMin = footer.rectTransform.anchorMax = Vector2.zero;
            footer.rectTransform.anchorMax = Vector2.right;
            footer.rectTransform.pivot = Vector2.zero;
            footer.rectTransform.sizeDelta = new Vector2(0f, FooterHeight);
            footer.rectTransform.anchoredPosition = Vector2.zero;
            footerContent = UI.Rect("FooterContent", footer.transform);
            UI.Place(footerContent, new Vector2(0.5f, 0f), Vector2.zero,
                new Vector2(1000f, FooterHeight), new Vector2(0.5f, 0f));

            var title = UI.Txt(footerContent, "Title", "SCARBOUND", 44, Color.white, TextAnchor.UpperLeft, 0f);
            UI.Place(title.rectTransform, Vector2.up, new Vector2(0f, -14f), new Vector2(460f, 58f), Vector2.up);
            var subtitle = UI.Txt(footerContent, "Subtitle", "SMASH  /  HARPOON  /  GROW", 24,
                Amber, TextAnchor.UpperRight, 0f);
            UI.Place(subtitle.rectTransform, Vector2.one, new Vector2(0f, -26f), new Vector2(560f, 42f), Vector2.one);
            status = UI.Txt(footerContent, "Status", "Starting the engine", 34, Color.white, TextAnchor.MiddleLeft, 0f);
            percent = UI.Txt(footerContent, "Percent", "0%", 34, Amber, TextAnchor.MiddleRight, 0f);
            UI.Place(status.rectTransform, Vector2.up, new Vector2(0f, -88f), new Vector2(850f, 56f), Vector2.up);
            UI.Place(percent.rectTransform, Vector2.one, new Vector2(0f, -88f), new Vector2(130f, 56f), Vector2.one);
            var track = UI.Img(footerContent, "Track", null, new Color(0.16f, 0.2f, 0.22f));
            track.rectTransform.anchorMin = Vector2.zero;
            track.rectTransform.anchorMax = Vector2.right;
            track.rectTransform.pivot = Vector2.zero;
            track.rectTransform.sizeDelta = new Vector2(0f, 10f);
            track.rectTransform.anchoredPosition = new Vector2(0f, 36f);
            fill = UI.Img(track.transform, "Progress", null, Amber);
            UI.Stretch(fill.rectTransform);
            Layout();
        }

        Text PosterText(string name, string text)
        {
            var label = UI.Txt(poster, name, text, 100, new Color(1f, 0.97f, 0.88f), TextAnchor.MiddleCenter, 7f);
            label.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            label.fontStyle = FontStyle.Bold;
            foreach (var shadow in label.GetComponents<Shadow>())
                shadow.effectColor = new Color(0.015f, 0.02f, 0.025f, 1f);
            return label;
        }

        void LayoutPosterText(Text label, float fontSize, float y, float width, float outline)
        {
            label.fontSize = Mathf.RoundToInt(fontSize);
            UI.Place(label.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0f, y),
                new Vector2(width, fontSize * 1.55f), new Vector2(0.5f, 0.5f));
            label.GetComponent<Outline>().effectDistance = new Vector2(outline, -outline);
            foreach (var shadow in label.GetComponents<Shadow>())
                if (!(shadow is Outline)) shadow.effectDistance = new Vector2(0f, -outline * 1.3f);
        }

        void Layout()
        {
            // The root Canvas is the authoritative viewport, including camera-backed native previews.
            var viewport = GetComponent<Canvas>().pixelRect;
            if (viewport.width <= 0f || viewport.height <= 0f) viewport = new Rect(0f, 0f, Screen.width, Screen.height);
            screenWidth = Mathf.Max(1, Mathf.RoundToInt(viewport.width));
            screenHeight = Mathf.Max(1, Mathf.RoundToInt(viewport.height));
            if (poster == null) return;
            // Expand uses the smaller scale factor. Fit the whole source image above the footer;
            // on wide viewports the extra space stays dark instead of cropping the vertical story.
            float scale = Mathf.Max(0.001f, Mathf.Min(screenWidth / 1080f, screenHeight / 1920f));
            float canvasWidth = screenWidth / scale;
            float canvasHeight = screenHeight / scale;
            float availableHeight = Mathf.Max(1f, canvasHeight - FooterHeight);
            float aspect = artwork.texture != null ? (float)artwork.texture.width / artwork.texture.height : 9f / 16f;
            float width = Mathf.Min(canvasWidth, availableHeight * aspect);
            poster.sizeDelta = new Vector2(width, width / aspect);
            poster.anchoredPosition = new Vector2(0f, FooterHeight * 0.5f);
            float titleSize = width * 0.132f;
            LayoutPosterText(posterTitle, titleSize, titleSize * 0.45f, width * 0.96f, width * 0.008f);
            LayoutPosterText(posterSubtitle, titleSize * 0.37f, -titleSize * 0.55f, width * 0.9f, width * 0.005f);
            LayoutPosterText(posterGenre, titleSize * 0.26f, -titleSize * 0.97f, width * 0.8f, width * 0.004f);
            footerContent.sizeDelta = new Vector2(Mathf.Min(1040f, canvasWidth - 80f), FooterHeight);
        }

        public void SetProgress(float value)
        {
            progress = Mathf.Max(progress, Mathf.Clamp01(value));
            if (fill != null) UI.SetBar(fill, progress);
            if (percent != null) percent.text = Mathf.RoundToInt(progress * 100f) + "%";
            if (status != null) status.text = progress >= 1f ? "Ready" : progress >= 0.85f ? "Preparing your garage" :
                progress >= 0.25f ? "Building the wasteland" : progress >= 0.1f ? "Loading audio and effects" : "Starting the engine";
#if UNITY_WEBGL && !UNITY_EDITOR
            RoadGameLoadingProgress(progress);
#endif
        }

        /// <summary>No display timer or fade: the actual ready flag releases the loading screen.</summary>
        public void Hide()
        {
            gameObject.SetActive(false);
            Destroy(gameObject);
        }

        /// <summary>Called by Game after readiness and the first gameplay frame have actually rendered.</summary>
        public static void SignalReady()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            RoadGameLoadingReady();
#endif
        }

        void Update()
        {
            if (poster == null) return;
            var viewport = GetComponent<Canvas>().pixelRect;
            if (screenWidth != Mathf.RoundToInt(viewport.width) || screenHeight != Mathf.RoundToInt(viewport.height)) Layout();
        }
    }
}
