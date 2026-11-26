using UnityEngine;
using UnityEngine.UI;

namespace RoadGame
{
    /// <summary>Public, session-only gameplay controls: game speed, John Wick and «Локации» (a DEV move straight to a
    /// zone, DevTravel). Opening this modal owns only its own pause.</summary>
    public sealed class DevPanel : MonoBehaviour
    {
        static readonly float[] Speeds = { 1f, 2f, 4f };
        static readonly Color Idle = new Color(0.38f, 0.4f, 0.47f);
        static readonly Color Ink = new Color(0.3f, 0.2f, 0.15f);
        readonly Image[] speedFills = new Image[3];
        readonly Text[] speedLabels = new Text[3];
        readonly Text[] speedStates = new Text[3];
        const float CardW = 900f, CardH = 1330f;
        readonly Text[] travelStates = new Text[3];
        Text travelHint;
        RectTransform modal, safe, card;
        Image wickFill;
        Text wickState, launcherState;
        Hud hud;
        Game pauseOwner;
        bool pausedBefore, joystickEnabledBefore;

        public bool IsOpen => modal != null && modal.gameObject.activeSelf;

        public static DevPanel Create(RectTransform parent, Hud owner, Text launcherLabel)
        {
            var r = UI.Rect("DevPanel", parent);
            UI.Stretch(r);
            var p = r.gameObject.AddComponent<DevPanel>();
            p.hud = owner;
            p.launcherState = launcherLabel;
            p.Build(r);
            p.Refresh();
            return p;
        }

        void OnEnable() { DevOptions.Changed += Refresh; }

        void OnDisable()
        {
            DevOptions.Changed -= Refresh;
            Close();
        }

        void Build(RectTransform parent)
        {
            modal = UI.Rect("Modal", parent);
            UI.Stretch(modal);
            // The backdrop is a sibling of the card: empty space inside the card does not close it.
            var dim = UI.Img(modal, "Backdrop", null, new Color(0f, 0f, 0f, 0.65f), true);
            UI.Stretch(dim.rectTransform);
            var outside = dim.gameObject.AddComponent<Button>();
            outside.transition = Selectable.Transition.None;
            outside.onClick.AddListener(Close);
            safe = UI.Rect("Safe", modal);
            UI.Stretch(safe);
            safe.gameObject.AddComponent<SafeArea>();
            card = UI.Panel(safe, "Card", new Color(0.93f, 0.86f, 0.74f), 34, true, true).rectTransform;
            UI.Place(card, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(CardW, CardH));
            var title = UI.Txt(card, "Title", "DEV", 64, Ink, TextAnchor.MiddleLeft, 0f);
            UI.Place(title.rectTransform, new Vector2(0, 1), new Vector2(44, -30), new Vector2(600, 90), new Vector2(0, 1));
            var close = UI.Btn(card, "Close", UI.Red, Close);
            UI.Place((RectTransform)close.transform, Vector2.one, new Vector2(-24, -24), new Vector2(110, 110), Vector2.one);
            var cross = UI.IconImg(close.transform, Icon.Close, 66);
            UI.Place(cross.rectTransform, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(66, 66));
            var heading = UI.TxtRu(card, "SpeedTitle", "Скорость игры", 44, Ink, TextAnchor.MiddleLeft, 0f);
            UI.Place(heading.rectTransform, new Vector2(0, 1), new Vector2(46, -150), new Vector2(808, 70), new Vector2(0, 1));
            for (int i = 0; i < Speeds.Length; i++)
            {
                float speed = Speeds[i];
                var button = UI.Btn(card, "Speed" + (int)speed, Idle, () => DevOptions.SetSpeed(speed));
                UI.Place((RectTransform)button.transform, new Vector2(0.5f, 1), new Vector2((i - 1) * 266, -286), new Vector2(244, 142), new Vector2(0.5f, 0.5f));
                speedFills[i] = button.transform.Find("Fill").GetComponent<Image>();
                speedLabels[i] = UI.Txt(button.transform, "Label", ((int)speed) + "x", 56, Color.white);
                UI.Place(speedLabels[i].rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 18), new Vector2(220, 70));
                speedStates[i] = UI.TxtRu(button.transform, "Selected", "", 23, Ink, TextAnchor.MiddleCenter, 0f);
                UI.Place(speedStates[i].rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, -38), new Vector2(220, 36));
            }
            var hint = UI.TxtRu(card, "SpeedHint", "Движение и бой идут быстрее.", 30, Ink, TextAnchor.MiddleCenter, 0f);
            UI.Place(hint.rectTransform, new Vector2(0.5f, 1), new Vector2(0, -386), new Vector2(808, 54), new Vector2(0.5f, 0.5f));
            var row = UI.Panel(card, "JohnWick", new Color(1f, 0.97f, 0.9f), 24).rectTransform;
            UI.Place(row, new Vector2(0.5f, 1), new Vector2(0, -440), new Vector2(808, 220), new Vector2(0.5f, 1));
            var name = UI.Txt(row, "Name", "John Wick", 46, Ink, TextAnchor.MiddleLeft, 0f);
            UI.Place(name.rectTransform, new Vector2(0, 1), new Vector2(26, -18), new Vector2(480, 70), new Vector2(0, 1));
            var desc = UI.TxtRu(row, "Description", "Все цели уничтожаются\nс одного попадания.", 30, Ink, TextAnchor.MiddleLeft, 0f);
            UI.Place(desc.rectTransform, new Vector2(0, 0), new Vector2(26, 24), new Vector2(500, 108), Vector2.zero);
            var toggle = UI.Btn(row, "JohnWickToggle", Idle, () => DevOptions.SetJohnWick(!DevOptions.JohnWick));
            UI.Place((RectTransform)toggle.transform, new Vector2(1, 0.5f), new Vector2(-24, 0), new Vector2(220, 124), new Vector2(1, 0.5f));
            wickFill = toggle.transform.Find("Fill").GetComponent<Image>();
            wickState = UI.TxtRu(toggle.transform, "State", "", 42, Color.white);
            UI.Stretch(wickState.rectTransform, 10, 10, 10, 10);
            // «Локации»: straight to a zone's repair pad (a test visit when the save has not unlocked it)
            var locTitle = UI.TxtRu(card, "TravelTitle", "Локации", 44, Ink, TextAnchor.MiddleLeft, 0f);
            UI.Place(locTitle.rectTransform, new Vector2(0, 1), new Vector2(46, -684), new Vector2(808, 66), new Vector2(0, 1));
            for (int i = 0; i < 3; i++)
            {
                int zone = i;
                var b = UI.Btn(card, "TravelZone" + (i + 1), i == 2 ? new Color(0.36f, 0.42f, 0.52f) : Idle, () => Travel(zone));
                UI.Place((RectTransform)b.transform, new Vector2(0.5f, 1), new Vector2(0, -760 - i * 122), new Vector2(808, 108), new Vector2(0.5f, 1));
                var lbl = UI.TxtRu(b.transform, "Label", DevTravel.ZoneLabel(i), 40, Color.white, TextAnchor.MiddleLeft, 0f);
                UI.Place(lbl.rectTransform, new Vector2(0, 0.5f), new Vector2(28, 10), new Vector2(560, 60), new Vector2(0, 0.5f));
                travelStates[i] = UI.TxtRu(b.transform, "State", "", 24, UI.Cream, TextAnchor.MiddleLeft, 0f);
                UI.Place(travelStates[i].rectTransform, new Vector2(0, 0.5f), new Vector2(30, -30), new Vector2(560, 34), new Vector2(0, 0.5f));
                var go = UI.TxtRu(b.transform, "Go", "→", 54, Color.white, TextAnchor.MiddleRight, 0f);
                UI.Place(go.rectTransform, new Vector2(1, 0.5f), new Vector2(-28, 4), new Vector2(120, 80), new Vector2(1, 0.5f));
            }
            travelHint = UI.TxtRu(card, "TravelHint", "", 26, Ink, TextAnchor.MiddleCenter, 0f);
            UI.Place(travelHint.rectTransform, new Vector2(0.5f, 1), new Vector2(0, -1132), new Vector2(808, 44), new Vector2(0.5f, 1));
            var done = UI.Btn(card, "Done", UI.Blue, Close);
            UI.Place((RectTransform)done.transform, new Vector2(0.5f, 0), new Vector2(0, 42), new Vector2(420, 116), new Vector2(0.5f, 0));
            var doneText = UI.TxtRu(done.transform, "Label", "ГОТОВО", 46, Color.white);
            UI.Stretch(doneText.rectTransform, 12, 6, 12, 6);
            modal.gameObject.SetActive(false);
        }

        public void Open()
        {
            if (IsOpen || Game.I == null) return;
            pauseOwner = Game.I;
            pausedBefore = pauseOwner.paused;
            joystickEnabledBefore = hud != null && hud.joystick != null && hud.joystick.enabled;
            if (hud != null && hud.joystick != null) hud.joystick.enabled = false;
            pauseOwner.paused = true;
            transform.SetAsLastSibling();
            modal.gameObject.SetActive(true);
            Fit();
            Refresh();
        }

        public void Close()
        {
            if (!IsOpen) return;
            modal.gameObject.SetActive(false);
            if (pauseOwner != null && Game.I == pauseOwner)
                pauseOwner.paused = pausedBefore || (hud != null && hud.panels != null && hud.panels.IsOpen);
            if (hud != null && hud.joystick != null) hud.joystick.enabled = joystickEnabledBefore;
            pauseOwner = null;
        }

        void Update() { if (IsOpen) Fit(); }

        void Fit()
        {
            float scale = Mathf.Min(1f, (safe.rect.width - 48f) / CardW, (safe.rect.height - 48f) / CardH);
            card.localScale = Vector3.one * Mathf.Max(0.1f, scale);
        }

        void Travel(int zone)
        {
            if (!DevTravel.Go(zone) && travelHint != null) travelHint.text = "Сейчас нельзя: " + DevTravel.LastResult;
        }

        void Refresh()
        {
            if (launcherState != null)
                launcherState.text = ((int)DevOptions.Speed) + "x" + (DevOptions.JohnWick ? " / JW" : "");
            for (int i = 0; i < Speeds.Length; i++)
            {
                if (speedFills[i] == null) continue;
                bool selected = Mathf.Approximately(DevOptions.Speed, Speeds[i]);
                speedFills[i].color = selected ? UI.Green : Idle;
                speedLabels[i].color = selected ? UI.Cream : Color.white;
                speedStates[i].text = selected ? "ВЫБРАНО" : "";
            }
            if (wickFill != null) wickFill.color = DevOptions.JohnWick ? UI.Green : Idle;
            if (wickState != null) wickState.text = DevOptions.JohnWick ? "ВКЛ" : "ВЫКЛ";
            var g = Game.I;
            if (g != null && g.progress != null)
                for (int i = 0; i < travelStates.Length; i++)
                    if (travelStates[i] != null)
                        travelStates[i].text = i <= g.progress.d.unlockedZone ? "открыта" : "тест: закрыта сюжетом, прогресс не засчитывается";
            if (travelHint != null)
                travelHint.text = DevTravel.InTestZone(g) ? "Сейчас тестовый визит: сохранение помнит прошлую точку" : "";
        }
    }
}
