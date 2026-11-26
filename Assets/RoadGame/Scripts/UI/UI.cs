using System;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;

namespace RoadGame
{
    /// <summary>Small helper toolkit to build a chunky cartoon uGUI from code.</summary>
    public static class UI
    {
        public static Font font;
        /// <summary>Font for Russian text: Lilita One has no Cyrillic, Rubik ExtraBold is close to it in weight and shape.</summary>
        public static Font fontCyrillic;
        public static readonly Color Dark = new Color(0.1f, 0.07f, 0.06f, 1f);
        public static readonly Color PanelBg = new Color(0.16f, 0.13f, 0.12f, 0.92f);
        public static readonly Color Cream = new Color(1f, 0.95f, 0.85f, 1f);
        public static readonly Color Green = new Color(0.33f, 0.85f, 0.35f, 1f);
        public static readonly Color Red = new Color(0.95f, 0.26f, 0.3f, 1f);
        public static readonly Color Gold = new Color(1f, 0.8f, 0.25f, 1f);
        public static readonly Color Blue = new Color(0.35f, 0.65f, 0.98f, 1f);

        public static Canvas CreateCanvas(string name, int order)
        {
            if (font == null) font = Resources.Load<Font>("Fonts/LilitaOne-Regular");
            if (font == null) font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (fontCyrillic == null) fontCyrillic = Resources.Load<Font>("Fonts/Rubik-ExtraBold");
            if (fontCyrillic == null) fontCyrillic = font;
            var go = new GameObject(name);
            var c = go.AddComponent<Canvas>();
            c.renderMode = RenderMode.ScreenSpaceOverlay;
            c.sortingOrder = order;
            c.pixelPerfect = false;
            var s = go.AddComponent<CanvasScaler>();
            s.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            s.referenceResolution = new Vector2(1080, 1920);
            s.screenMatchMode = CanvasScaler.ScreenMatchMode.MatchWidthOrHeight;
            s.matchWidthOrHeight = 0.5f;
            go.AddComponent<GraphicRaycaster>();
            return c;
        }

        public static void EnsureEventSystem()
        {
            if (EventSystem.current != null) return;
            var go = new GameObject("EventSystem");
            go.AddComponent<EventSystem>();
            var m = go.AddComponent<InputSystemUIInputModule>();
            m.AssignDefaultActions();
        }

        public static RectTransform Rect(string name, Transform parent)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);
            return (RectTransform)go.transform;
        }

        /// <summary>anchor = normalized anchor point (both min & max), pos = offset in reference pixels, size in reference pixels.</summary>
        public static RectTransform Place(RectTransform r, Vector2 anchor, Vector2 pos, Vector2 size, Vector2? pivot = null)
        {
            r.anchorMin = r.anchorMax = anchor;
            r.pivot = pivot ?? anchor;
            r.anchoredPosition = pos;
            r.sizeDelta = size;
            return r;
        }

        public static RectTransform Stretch(RectTransform r, float l = 0, float b = 0, float rr = 0, float t = 0)
        {
            r.anchorMin = Vector2.zero; r.anchorMax = Vector2.one;
            r.offsetMin = new Vector2(l, b); r.offsetMax = new Vector2(-rr, -t);
            return r;
        }

        public static Image Img(Transform parent, string name, Sprite sprite, Color color, bool raycast = false)
        {
            var r = Rect(name, parent);
            var i = r.gameObject.AddComponent<Image>();
            i.sprite = sprite;
            i.color = color;
            i.raycastTarget = raycast;
            if (sprite != null && sprite.border != Vector4.zero) i.type = Image.Type.Sliced;
            return i;
        }

        public static Image Panel(Transform parent, string name, Color fill, int radius = 22, bool outline = true, bool raycast = false)
        {
            Image outer = null;
            if (outline)
            {
                outer = Img(parent, name, Tex.RoundRect(radius), Dark, raycast);
                var inner = Img(outer.transform, "Fill", Tex.RoundRect(radius), fill);
                Stretch(inner.rectTransform, 5, 5, 5, 5);
                return outer;
            }
            return Img(parent, name, Tex.RoundRect(radius), fill, raycast);
        }

        public static Text Txt(Transform parent, string name, string text, int size, Color color, TextAnchor align = TextAnchor.MiddleCenter, float outline = 3f)
        {
            var r = Rect(name, parent);
            var t = r.gameObject.AddComponent<Text>();
            t.font = font;
            t.text = text;
            t.fontSize = size;
            t.color = color;
            t.alignment = align;
            t.raycastTarget = false;
            t.horizontalOverflow = HorizontalWrapMode.Overflow;
            t.verticalOverflow = VerticalWrapMode.Overflow;
            if (outline > 0)
            {
                var o = r.gameObject.AddComponent<Outline>();
                o.effectColor = Dark;
                o.effectDistance = new Vector2(outline, -outline);
                var s = r.gameObject.AddComponent<Shadow>();
                s.effectColor = new Color(0, 0, 0, 0.55f);
                s.effectDistance = new Vector2(0, -outline * 1.6f);
            }
            return t;
        }

        /// <summary>Sets a text and picks the font by its letters: Lilita has no Cyrillic, Russian goes in Rubik.</summary>
        public static void SetText(Text t, string s)
        {
            var f = HasCyrillic(s) && fontCyrillic != null ? fontCyrillic : font;
            if (t.font != f) t.font = f;
            t.text = s;
        }

        public static bool HasCyrillic(string s)
        {
            if (string.IsNullOrEmpty(s)) return false;
            for (int i = 0; i < s.Length; i++) if (s[i] >= '\u0400' && s[i] <= '\u04FF') return true;
            return false;
        }

        /// <summary>Text in Russian (the Cyrillic font), otherwise like Txt.</summary>
        public static Text TxtRu(Transform parent, string name, string text, int size, Color color, TextAnchor align = TextAnchor.MiddleCenter, float outline = 3f)
        {
            var t = Txt(parent, name, text, size, color, align, outline);
            t.font = fontCyrillic != null ? fontCyrillic : font;
            return t;
        }

        public static Button Btn(Transform parent, string name, Color fill, Action onClick, int radius = 24)
        {
            var bg = Panel(parent, name, fill, radius, true, true);
            var b = bg.gameObject.AddComponent<Button>();
            b.targetGraphic = bg;
            var cb = b.colors;
            cb.normalColor = Color.white; cb.highlightedColor = Color.white; cb.pressedColor = new Color(0.8f, 0.8f, 0.8f, 1f); cb.selectedColor = Color.white;
            cb.fadeDuration = 0.05f;
            b.colors = cb;
            b.onClick.AddListener(() => { Game.I?.sfx.Play(Sfx.Kind.Click, Vector3.zero, 0.5f); onClick?.Invoke(); });
            bg.gameObject.AddComponent<PressScale>();
            return b;
        }

        /// <summary>Round icon button (circle bg + icon).</summary>
        public static Button IconBtn(Transform parent, string name, Icon icon, Color bg, Action onClick, float size = 120f)
        {
            var outer = Img(parent, name, Tex.Circle(), Dark, true);
            outer.rectTransform.sizeDelta = new Vector2(size, size);
            var inner = Img(outer.transform, "Bg", Tex.Circle(), bg);
            Stretch(inner.rectTransform, 6, 6, 6, 6);
            var ic = Img(outer.transform, "Icon", Tex.Get(icon), Color.white);
            Stretch(ic.rectTransform, size * 0.16f, size * 0.16f, size * 0.16f, size * 0.16f);
            var b = outer.gameObject.AddComponent<Button>();
            b.targetGraphic = outer;
            b.onClick.AddListener(() => { Game.I?.sfx.Play(Sfx.Kind.Click, Vector3.zero, 0.5f); onClick?.Invoke(); });
            outer.gameObject.AddComponent<PressScale>();
            return b;
        }

        public static Image IconImg(Transform parent, Icon icon, float size)
        {
            var i = Img(parent, icon.ToString(), Tex.Get(icon), Color.white);
            i.rectTransform.sizeDelta = new Vector2(size, size);
            i.preserveAspect = true;
            return i;
        }

        /// <summary>Horizontal bar: dark rounded background + colored fill (anchor-scaled). Returns fill image.</summary>
        public static Image Bar(Transform parent, string name, Color fill, out RectTransform root, int radius = 14)
        {
            var bg = Img(parent, name, Tex.RoundRect(radius), Dark);
            root = bg.rectTransform;
            var back = Img(bg.transform, "Back", Tex.RoundRect(radius), new Color(0.3f, 0.08f, 0.1f, 1f));
            Stretch(back.rectTransform, 4, 4, 4, 4);
            var f = Img(back.transform, "Fill", Tex.RoundRect(radius), fill);
            var fr = f.rectTransform;
            fr.anchorMin = new Vector2(0, 0); fr.anchorMax = new Vector2(1, 1);
            fr.offsetMin = Vector2.zero; fr.offsetMax = Vector2.zero;
            var hl = Img(f.transform, "Highlight", Tex.RoundRect(radius), new Color(1, 1, 1, 0.25f));
            var hr = hl.rectTransform;
            hr.anchorMin = new Vector2(0, 0.55f); hr.anchorMax = new Vector2(1, 1);
            hr.offsetMin = new Vector2(4, 0); hr.offsetMax = new Vector2(-4, -2);
            return f;
        }

        public static void SetBar(Image fill, float k)
        {
            var r = fill.rectTransform;
            r.anchorMax = new Vector2(Mathf.Clamp01(k), 1);
            fill.enabled = k > 0.001f;
        }
    }

    /// <summary>Juicy press feedback for buttons.</summary>
    public class PressScale : MonoBehaviour, IPointerDownHandler, IPointerUpHandler, IPointerExitHandler
    {
        float target = 1f, cur = 1f;
        public void OnPointerDown(PointerEventData e) { target = 0.9f; }
        public void OnPointerUp(PointerEventData e) { target = 1f; }
        public void OnPointerExit(PointerEventData e) { target = 1f; }
        void Update()
        {
            cur = Mathf.MoveTowards(cur, target, Time.unscaledDeltaTime * 4f);
            transform.localScale = Vector3.one * cur;
        }
    }

    /// <summary>Simple tween helpers driven by a MonoBehaviour (unscaled time).</summary>
    public class Pulse : MonoBehaviour
    {
        public float speed = 3f, amount = 0.06f;
        Vector3 baseScale;
        void Awake() { baseScale = transform.localScale; }
        /// <summary>The size it pulses around (a layout that scales the element, e.g. on a landscape screen).</summary>
        public void SetBase(Vector3 s) { baseScale = s; transform.localScale = s; }
        void Update() { transform.localScale = baseScale * (1f + Mathf.Sin(Time.unscaledTime * speed) * amount); }
    }
}
