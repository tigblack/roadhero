using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace RoadGame
{
    /// <summary>
    /// Floating joystick: appears where the finger touches (anywhere below the top HUD) and stays there until the
    /// finger lifts; the knob follows the finger inside the ring. Value is the raw knob offset (length 0..1, screen
    /// directions); the driver applies the radial dead zone and the response curve. One finger owns the stick: other
    /// fingers (on buttons or on the same area) never take it over. Lifting the finger, losing the app focus and
    /// opening a menu all let go.
    /// </summary>
    public class Joystick : MonoBehaviour, IPointerDownHandler, IDragHandler, IPointerUpHandler, IInitializePotentialDragHandler
    {
        RectTransform area, baseR, knob;
        Image baseImg, knobImg, arrowImg;
        Canvas canvas;
        Vector2 restPos;
        int pointerId = int.MinValue;
        public const float Radius = 120f;
        public Vector2 Value { get; private set; }
        public bool Active => pointerId != int.MinValue;
        /// <summary>The finger that owns the stick (tests).</summary>
        public int PointerId => pointerId;
        /// <summary>Times the stick let go without the finger lifting (focus loss, a menu) - tests.</summary>
        public int ForcedReleases { get; private set; }

        /// <summary>Lets go: no input until the next touch (focus loss, a menu opening).</summary>
        public void Release()
        {
            if (Active) ForcedReleases++;
            pointerId = int.MinValue;
            if (baseR != null) SetIdle();
        }

        // the knob answers the first pixel of movement: without this the EventSystem's drag threshold would swallow
        // small, precise deflections and then jump
        public void OnInitializePotentialDrag(PointerEventData e)
        {
            if (e.pointerId == pointerId) e.useDragThreshold = false;
        }

        void OnApplicationFocus(bool focus) { if (!focus) Release(); }
        void OnApplicationPause(bool pause) { if (pause) Release(); }

        public static Joystick Create(Canvas canvas)
        {
            var area = UI.Rect("JoystickArea", canvas.transform);
            UI.Stretch(area, 0, 0, 0, 250);
            var catcher = area.gameObject.AddComponent<Image>();
            catcher.color = new Color(0, 0, 0, 0);
            catcher.raycastTarget = true;
            var j = area.gameObject.AddComponent<Joystick>();
            j.area = area;
            j.canvas = canvas;
            j.baseImg = UI.Img(area, "Base", Tex.Ring(0.09f), new Color(1, 1, 1, 0.55f));
            j.baseR = j.baseImg.rectTransform;
            j.baseR.anchorMin = j.baseR.anchorMax = new Vector2(0.5f, 0f);
            j.baseR.sizeDelta = new Vector2(Radius * 2.15f, Radius * 2.15f);
            j.restPos = new Vector2(0, 330);
            j.baseR.anchoredPosition = j.restPos;
            var inner = UI.Img(j.baseR, "Inner", Tex.Circle(), new Color(0, 0, 0, 0.12f));
            UI.Stretch(inner.rectTransform, 10, 10, 10, 10);
            j.arrowImg = UI.Img(j.baseR, "Arrow", Tex.Get(Icon.Arrow), new Color(1, 1, 1, 0.0f));
            j.arrowImg.rectTransform.sizeDelta = new Vector2(46, 46);
            j.knobImg = UI.Img(j.baseR, "Knob", Tex.Circle(), new Color(1, 1, 1, 0.75f));
            j.knob = j.knobImg.rectTransform;
            j.knob.sizeDelta = new Vector2(96, 96);
            var knobRing = UI.Img(j.knob, "KnobRing", Tex.Ring(0.12f), new Color(0.1f, 0.07f, 0.06f, 0.35f));
            UI.Stretch(knobRing.rectTransform);
            j.SetIdle();
            return j;
        }

        /// <summary>Where the idle ring waits (bottom centre on a portrait screen, bottom left on a landscape one, away
        /// from the car). Anchored to the bottom centre of the touch area.</summary>
        public void SetRest(Vector2 pos)
        {
            restPos = pos;
            if (!Active && baseR != null) baseR.anchoredPosition = restPos;
        }

        void SetIdle()
        {
            baseR.anchoredPosition = restPos;
            knob.anchoredPosition = Vector2.zero;
            baseImg.color = new Color(1, 1, 1, 0.35f);
            knobImg.color = new Color(1, 1, 1, 0.45f);
            arrowImg.color = new Color(1, 1, 1, 0f);
            Value = Vector2.zero;
        }

        Vector2 ToLocal(PointerEventData e)
        {
            // an overlay canvas maps screen points without a camera; a camera-space canvas needs its camera
            var cam = canvas != null && canvas.renderMode != RenderMode.ScreenSpaceOverlay ? canvas.worldCamera : null;
            RectTransformUtility.ScreenPointToLocalPointInRectangle((RectTransform)baseR.parent, e.position, cam, out var lp);
            // convert from parent's local (pivot at center of area) to anchored position relative to bottom-center anchor
            var parentR = (RectTransform)baseR.parent;
            var anchorRef = new Vector2((0.5f - parentR.pivot.x) * parentR.rect.width, (0f - parentR.pivot.y) * parentR.rect.height);
            return lp - anchorRef;
        }

        public void OnPointerDown(PointerEventData e)
        {
            if (Active) return;
            pointerId = e.pointerId;
            baseR.anchoredPosition = ToLocal(e);
            baseImg.color = new Color(1, 1, 1, 0.7f);
            knobImg.color = new Color(1, 1, 1, 0.92f);
            OnDrag(e);
            Game.I?.OnFirstInput();
        }

        public void OnDrag(PointerEventData e)
        {
            if (e.pointerId != pointerId) return;
            var d = ToLocal(e) - baseR.anchoredPosition;
            // the base stays where the finger first touched until release: past the rim the knob stops at the edge
            // and only the direction follows the finger
            if (d.magnitude > Radius) d = d.normalized * Radius;
            knob.anchoredPosition = d;
            Value = d / Radius;
            if (d.magnitude > 8f)
            {
                arrowImg.color = new Color(1, 1, 1, 0.8f);
                var dir = d.normalized;
                arrowImg.rectTransform.anchoredPosition = dir * (Radius + 26f);
                arrowImg.rectTransform.localRotation = Quaternion.Euler(0, 0, Mathf.Atan2(dir.y, dir.x) * Mathf.Rad2Deg - 90f);
            }
        }

        public void OnPointerUp(PointerEventData e)
        {
            if (e.pointerId != pointerId) return;
            pointerId = int.MinValue;
            SetIdle();
        }

        void OnDisable()
        {
            pointerId = int.MinValue;
            if (baseR != null) SetIdle();
        }
    }
}
