using System;
using UnityEngine;
using UnityEngine.UI;

namespace RoadGame
{
    /// <summary>Modal panels: Garage (stats / weapons / armor), Shop (gems) and Settings (with the progress reset and its
    /// confirmation dialog).</summary>
    public class Panels : MonoBehaviour
    {
        RectTransform root;
        RectTransform modal;
        RectTransform content;
        RectTransform confirm;
        // the cards are laid out for a portrait phone; on a short screen (a phone turned sideways) they scale down so the
        // title and the close button always stay on screen
        RectTransform card, confirmCard;
        Text title;
        Action rebuild;
        int focusWeapon = -1;
        public bool IsOpen => modal != null && modal.gameObject.activeSelf;
        public bool ConfirmOpen => confirm != null && confirm.gameObject.activeSelf;

        // the progress reset (texts as asked for, in Russian, set in the Cyrillic font)
        // card titles: dark ink on the cream cards (white with a thin outline read poorly there, ~1.5:1)
        static readonly Color TitleInk = new Color(0.22f, 0.14f, 0.1f), TitleLocked = new Color(0.45f, 0.4f, 0.37f);

        public const string ResetButtonText = "Сбросить прогресс";
        public const string ResetQuestion = "Сбросить весь прогресс?";
        public const string ResetWarning = "Валюта, улучшения и прохождение будут удалены. Это действие нельзя отменить.";
        public const string ResetCancelText = "Отмена", ResetConfirmText = "Сбросить";

        public static Panels Create(RectTransform parent)
        {
            var r = UI.Rect("Panels", parent);
            UI.Stretch(r);
            var p = r.gameObject.AddComponent<Panels>();
            p.root = r;
            p.BuildFrame();
            return p;
        }

        void BuildFrame()
        {
            modal = UI.Rect("Modal", root);
            UI.Stretch(modal);
            var dim = modal.gameObject.AddComponent<Image>();
            dim.color = new Color(0, 0, 0, 0.6f);
            dim.raycastTarget = true;
            var dimBtn = modal.gameObject.AddComponent<Button>();
            dimBtn.transition = Selectable.Transition.None;
            dimBtn.onClick.AddListener(Close);

            var panel = UI.Panel(modal, "Panel", new Color(0.93f, 0.86f, 0.74f), 34, true, true);
            UI.Place(panel.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, -20), new Vector2(980, 1500));
            card = panel.rectTransform;
            var header = UI.Panel(panel.transform, "Header", new Color(0.86f, 0.42f, 0.2f), 30);
            UI.Place(header.rectTransform, new Vector2(0.5f, 1f), new Vector2(0, 40), new Vector2(640, 120), new Vector2(0.5f, 0.5f));
            title = UI.Txt(header.transform, "Title", "", 64, Color.white, TextAnchor.MiddleCenter, 4f);
            UI.Stretch(title.rectTransform, 0, 6, 0, 0);
            var close = UI.Btn(panel.transform, "Close", new Color(0.92f, 0.25f, 0.3f), Close, 26);
            UI.Place((RectTransform)close.transform, new Vector2(1, 1), new Vector2(20, 20), new Vector2(110, 110), new Vector2(1, 1));
            var x = UI.IconImg(close.transform, Icon.Close, 70);
            UI.Place(x.rectTransform, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(70, 70));

            // scroll view
            var view = UI.Rect("Viewport", panel.transform);
            UI.Stretch(view, 30, 30, 30, 110);
            view.gameObject.AddComponent<RectMask2D>();
            var viewImg = view.gameObject.AddComponent<Image>();
            viewImg.color = new Color(0, 0, 0, 0.001f);
            content = UI.Rect("Content", view);
            content.anchorMin = new Vector2(0, 1); content.anchorMax = new Vector2(1, 1);
            content.pivot = new Vector2(0.5f, 1f);
            content.offsetMin = content.offsetMax = Vector2.zero;
            var vl = content.gameObject.AddComponent<VerticalLayoutGroup>();
            vl.spacing = 16; vl.childControlHeight = true; vl.childControlWidth = true; vl.childForceExpandHeight = false; vl.childForceExpandWidth = true;
            vl.padding = new RectOffset(4, 4, 10, 30);
            var fit = content.gameObject.AddComponent<ContentSizeFitter>();
            fit.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            var sr = view.gameObject.AddComponent<ScrollRect>();
            sr.content = content; sr.viewport = view; sr.horizontal = false; sr.vertical = true;
            sr.movementType = ScrollRect.MovementType.Elastic; sr.scrollSensitivity = 30;
            modal.gameObject.SetActive(false);
            BuildConfirm();
        }

        /// <summary>"Reset all progress?" dialog over the settings: the question, what is lost, Cancel / Reset.</summary>
        void BuildConfirm()
        {
            confirm = UI.Rect("ResetConfirmDialog", root);
            UI.Stretch(confirm);
            var dim = confirm.gameObject.AddComponent<Image>();
            dim.color = new Color(0, 0, 0, 0.5f);
            dim.raycastTarget = true;     // nothing under the dialog can be pressed
            var panel = UI.Panel(confirm, "Panel", new Color(0.98f, 0.93f, 0.84f), 34, true, true);
            UI.Place(panel.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 30), new Vector2(920, 660));
            confirmCard = panel.rectTransform;
            var bar = UI.Panel(panel.transform, "Bar", UI.Red, 20, false);
            UI.Place(bar.rectTransform, new Vector2(0.5f, 1f), new Vector2(0, -26), new Vector2(820, 16), new Vector2(0.5f, 0.5f));
            var q = UI.TxtRu(panel.transform, "Question", ResetQuestion, 56, new Color(0.62f, 0.13f, 0.12f), TextAnchor.MiddleCenter, 0f);
            UI.Place(q.rectTransform, new Vector2(0.5f, 1f), new Vector2(0, -118), new Vector2(860, 100), new Vector2(0.5f, 0.5f));
            var w = UI.TxtRu(panel.transform, "Warning", ResetWarning, 40, new Color(0.3f, 0.2f, 0.15f), TextAnchor.MiddleCenter, 0f);
            UI.Place(w.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 40), new Vector2(800, 220));
            w.horizontalOverflow = HorizontalWrapMode.Wrap;
            w.lineSpacing = 1.12f;
            var cancel = UI.Btn(panel.transform, "ResetCancel", new Color(0.52f, 0.56f, 0.62f), HideResetConfirm, 26);
            UI.Place((RectTransform)cancel.transform, new Vector2(0.5f, 0f), new Vector2(-205, 112), new Vector2(370, 136));
            Label((RectTransform)cancel.transform, ResetCancelText, 48, Color.white, new Vector2(0.5f, 0.5f), new Vector2(0, 3), new Vector2(360, 120), TextAnchor.MiddleCenter, 3f).font = UI.fontCyrillic;
            var ok = UI.Btn(panel.transform, "ResetConfirm", UI.Red, ConfirmReset, 26);
            UI.Place((RectTransform)ok.transform, new Vector2(0.5f, 0f), new Vector2(205, 112), new Vector2(370, 136));
            Label((RectTransform)ok.transform, ResetConfirmText, 48, Color.white, new Vector2(0.5f, 0.5f), new Vector2(0, 3), new Vector2(360, 120), TextAnchor.MiddleCenter, 3f).font = UI.fontCyrillic;
            confirm.gameObject.SetActive(false);
        }

        public void ShowResetConfirm()
        {
            confirm.SetAsLastSibling();
            confirm.gameObject.SetActive(true);
            Fit();
        }

        void Update() { if (IsOpen || ConfirmOpen) Fit(); }

        /// <summary>Scales the cards into the safe part of the screen (title, close button and buttons always visible).</summary>
        void Fit()
        {
            var r = root.rect;
            if (r.width <= 0f || r.height <= 0f || Screen.width <= 0 || Screen.height <= 0) return;
            var sa = Screen.safeArea;
            float w = r.width * sa.width / Screen.width, h = r.height * sa.height / Screen.height;
            // the garage card is 980 x 1500 with the header and the close button reaching 100 units above it
            float s = Mathf.Min(1f, (w - 40f) / 1000f, (h - 40f) / 1640f);
            card.localScale = Vector3.one * Mathf.Max(0.3f, s);
            // keep it centred on the safe area (the 20-unit offset of the portrait layout made room for the header)
            card.anchoredPosition = new Vector2((sa.center.x / Screen.width - 0.5f) * r.width, (sa.center.y / Screen.height - 0.5f) * r.height - 20f * card.localScale.y);
            float sc = Mathf.Min(1f, (w - 40f) / 940f, (h - 40f) / 700f);
            confirmCard.localScale = Vector3.one * Mathf.Max(0.3f, sc);
        }

        public void HideResetConfirm() => confirm.gameObject.SetActive(false);

        void ConfirmReset()
        {
            confirm.gameObject.SetActive(false);
            Close();
            Game.I.ResetProgress();
        }

        void Open(string t, Action build)
        {
            title.text = t;
            rebuild = build;
            Rebuild();
            modal.gameObject.SetActive(true);
            modal.localScale = Vector3.one;
            Fit();
            Game.I.paused = true;
        }

        public void Close()
        {
            // Esc / the back button first closes the reset dialog (= Cancel), then the panel
            if (ConfirmOpen) { HideResetConfirm(); return; }
            modal.gameObject.SetActive(false);
            rebuild = null;
            Game.I.paused = false;
        }

        void Rebuild()
        {
            for (int i = content.childCount - 1; i >= 0; i--) Destroy(content.GetChild(i).gameObject);
            rebuild?.Invoke();
        }

        void LateRebuild() { if (IsOpen) { Rebuild(); } }

        // ---------------------------------------------------------------- building blocks
        RectTransform Row(float height, Color? bg = null)
        {
            Image img = bg.HasValue ? UI.Panel(content, "Row", bg.Value, 24) : null;
            RectTransform r = img != null ? img.rectTransform : UI.Rect("Row", content);
            var le = r.gameObject.AddComponent<LayoutElement>();
            le.preferredHeight = height; le.minHeight = height;
            return r;
        }

        void Section(string s)
        {
            var r = Row(70);
            var t = UI.Txt(r, "S", s, 46, new Color(0.45f, 0.22f, 0.1f), TextAnchor.MiddleLeft, 0f);
            UI.Stretch(t.rectTransform, 16, 0, 0, 0);
        }

        Text Label(RectTransform parent, string s, int size, Color c, Vector2 anchor, Vector2 pos, Vector2 sizeD, TextAnchor align = TextAnchor.MiddleLeft, float outline = 2.5f)
        {
            var t = UI.Txt(parent, "L", "", size, c, align, outline);
            UI.SetText(t, s);    // Russian lines get the Cyrillic font
            UI.Place(t.rectTransform, anchor, pos, sizeD, anchor);
            return t;
        }

        // ---------------------------------------------------------------- GARAGE
        public void ShowGarage(int focus = -1)
        {
            focusWeapon = focus;
            Open("GARAGE", BuildGarage);
        }

        void BuildGarage()
        {
            var P = Game.I.progress; var d = P.d;
            // stats card (DPS / HP / REGEN like the reference)
            var stats = Row(190, new Color(0.22f, 0.2f, 0.22f));
            string[] names = { "DPS", "HP", "REGEN" };
            Icon[] icons = { Tex.DamageIcon(BestType()), Icon.Heart, Icon.Regen };
            string[] vals = { Fmt.Num(P.TotalDps()), Fmt.Num(d.maxHp), Fmt.Num(d.regen) + "/s" };
            Color[] cols = { new Color(0.65f, 0.85f, 1f), new Color(1f, 0.45f, 0.5f), new Color(0.5f, 1f, 0.6f) };
            for (int i = 0; i < 3; i++)
            {
                float x = -300 + i * 300;
                var ic = UI.IconImg(stats, icons[i], 90);
                UI.Place(ic.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(x - 80, 14), new Vector2(90, 90));
                var v = UI.Txt(stats, "V", vals[i], 50, cols[i], TextAnchor.MiddleLeft, 2.5f);
                UI.Place(v.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(x - 30, 14), new Vector2(170, 70), new Vector2(0f, 0.5f));
                var n = UI.Txt(stats, "N", names[i], 30, Color.white, TextAnchor.MiddleCenter, 2.5f);
                UI.Place(n.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(x, -58), new Vector2(220, 40), new Vector2(0.5f, 0.5f));
            }

            Section("WEAPONS");
            for (int i = 0; i < Content.Weapons.Length; i++) WeaponRow(i);
            Section("ARMOR");
            for (int i = 0; i < Content.Armors.Length; i++) ArmorRow(i);
            Section("DETAILS");
            Detail("Critical chance", Fmt.Pct(Balance.CritChance), Icon.Crit);
            Detail("Critical damage", Fmt.Pct(Balance.CritMul), Icon.Crit);
            for (int t = 0; t < 4; t++) if (d.dmg[t] > 0) Detail(Content.DamageTypeNames[t] + " damage", Fmt.Num(d.dmg[t]), Tex.DamageIcon((DamageType)t));
            Detail("Damage reduction", Fmt.Pct(Balance.ArmorReduction(P.ArmorTotal)), Icon.Shield);
            Detail("Things devoured", d.totalKills.ToString(), Icon.Harpoon);
            Detail("Zones unlocked", (d.unlockedZone + 1) + " / " + Content.ZoneCount, Icon.Flag);
        }

        DamageType BestType()
        {
            var d = Game.I.progress.d; int best = 0;
            for (int i = 1; i < 4; i++) if (d.dmg[i] > d.dmg[best]) best = i;
            return (DamageType)best;
        }

        void Detail(string name, string value, Icon? icon = null)
        {
            var r = Row(64, new Color(1f, 0.97f, 0.9f));
            float x = 24;
            if (icon.HasValue)
            {
                var ic = UI.IconImg(r, icon.Value, 48);
                UI.Place(ic.rectTransform, new Vector2(0, 0.5f), new Vector2(16, 0), new Vector2(48, 48), new Vector2(0, 0.5f));
                x = 76;
            }
            var n = UI.Txt(r, "N", name, 36, new Color(0.3f, 0.2f, 0.15f), TextAnchor.MiddleLeft, 0f);
            UI.Place(n.rectTransform, new Vector2(0, 0.5f), new Vector2(x, 0), new Vector2(600, 60), new Vector2(0, 0.5f));
            var v = UI.Txt(r, "V", value, 38, new Color(0.15f, 0.45f, 0.75f), TextAnchor.MiddleRight, 0f);
            UI.Place(v.rectTransform, new Vector2(1, 0.5f), new Vector2(-24, 0), new Vector2(400, 60), new Vector2(1, 0.5f));
        }

        void WeaponRow(int id)
        {
            var P = Game.I.progress; var d = P.d; var w = Content.Weapons[id];
            int lvl = d.weaponLevel[id];
            bool owned = lvl > 0;
            var r = Row(owned ? 206 : 176, focusWeapon == id ? new Color(1f, 0.92f, 0.6f) : new Color(1f, 0.97f, 0.9f));
            var iconBg = UI.Panel(r, "IconBg", owned ? new Color(0.25f, 0.55f, 0.95f) : new Color(0.5f, 0.5f, 0.5f), 22);
            UI.Place(iconBg.rectTransform, new Vector2(0, 0.5f), new Vector2(16, 0), new Vector2(146, 146), new Vector2(0, 0.5f));
            var ic = UI.IconImg(iconBg.transform, Tex.DamageIcon(w.type), 116);
            UI.Place(ic.rectTransform, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(116, 116));
            if (!owned) ic.sprite = Tex.GetLocked(Tex.DamageIcon(w.type));
            Label(r, w.name + (owned ? "  Lv " + lvl : ""), 44, owned ? TitleInk : TitleLocked, new Vector2(0, 1), new Vector2(180, -12), new Vector2(560, 60), TextAnchor.MiddleLeft, 0f);
            if (owned)
            {
                // what the next level gives, in numbers: per-hit damage now -> after, and what that means
                double now = P.WeaponHitDamage(id), next = P.WeaponHitDamageAt(id, lvl + 1);
                int pct = Mathf.RoundToInt((float)((next / Math.Max(1e-9, now) - 1.0) * 100.0));
                int faster = Mathf.RoundToInt((float)((1.0 - now / Math.Max(1e-9, next)) * 100.0));
                var dark = new Color(0.3f, 0.2f, 0.15f);
                Label(r, "урон " + Fmt.Num(now) + " → <color=#1d8a34>" + Fmt.Num(next) + "</color>  (+" + pct + "%)", 34, dark,
                      new Vector2(0, 1), new Vector2(182, -64), new Vector2(470, 46), TextAnchor.MiddleLeft, 0f);
                Label(r, "цели ломаются на " + faster + "% быстрее", 26, new Color(0.45f, 0.32f, 0.22f),
                      new Vector2(0, 1), new Vector2(182, -106), new Vector2(470, 36), TextAnchor.MiddleLeft, 0f);
                var bar = UI.Rect("Copies", r);
                UI.Place(bar, new Vector2(0, 0), new Vector2(182, 18), new Vector2(380, 32), new Vector2(0, 0));
                var f = UI.Bar(bar, "B", new Color(1f, 0.72f, 0.2f), out var br, 14);
                UI.Stretch(br);
                int need = Balance.CopiesForLevel(lvl);
                UI.SetBar(f, d.weaponCopies[id] / (float)need);
                var ct = UI.Txt(bar, "T", "", 24, Color.white, TextAnchor.MiddleCenter, 2f);
                UI.SetText(ct, "копии " + d.weaponCopies[id] + " / " + need);
                UI.Stretch(ct.rectTransform);
                int cost = P.WeaponLevelCost(id);
                bool afford = d.gems >= cost;
                var b = UI.Btn(r, "LevelUp" + id, afford ? UI.Green : new Color(0.6f, 0.6f, 0.6f), () => BuyLevel(id), 24);
                UI.Place((RectTransform)b.transform, new Vector2(1, 0.5f), new Vector2(-16, 0), new Vector2(214, 140), new Vector2(1, 0.5f));
                Label((RectTransform)b.transform, "УЛУЧШИТЬ", 30, Color.white, new Vector2(0.5f, 0.5f), new Vector2(0, 26), new Vector2(206, 44), TextAnchor.MiddleCenter);
                var gi = UI.IconImg(b.transform, Icon.Gem, 42);
                UI.Place(gi.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(-44, -24), new Vector2(42, 42));
                Label((RectTransform)b.transform, cost.ToString(), 38, Color.white, new Vector2(0.5f, 0.5f), new Vector2(26, -24), new Vector2(110, 46), TextAnchor.MiddleCenter);
                if (focusWeapon == id && afford) b.gameObject.AddComponent<Pulse>().amount = 0.05f;
            }
            else
            {
                // what it does, then what opens it
                string how = "откроется за босса зоны";
                for (int z = 0; z < Content.ZoneCount; z++) if (Content.Zones[z].unlockWeapon == id) how = "откроется: победи " + Goals.BossAcc[z];
                Label(r, Goals.WeaponWhat[id], 30, new Color(0.3f, 0.2f, 0.15f), new Vector2(0, 1), new Vector2(182, -70), new Vector2(560, 42), TextAnchor.MiddleLeft, 0f);
                Label(r, how, 26, new Color(0.55f, 0.35f, 0.22f), new Vector2(0, 1), new Vector2(182, -112), new Vector2(560, 38), TextAnchor.MiddleLeft, 0f);
                var lk = UI.IconImg(r, Icon.Lock, 80);
                UI.Place(lk.rectTransform, new Vector2(1, 0.5f), new Vector2(-40, 0), new Vector2(80, 80), new Vector2(1, 0.5f));
            }
        }

        /// <summary>
        /// Buys the next weapon level. The first purchase closes the garage at once: the goal widget then says to look at
        /// the next hits, and those numbers come up green with the new damage.
        /// </summary>
        void BuyLevel(int id)
        {
            var g = Game.I; var P = g.progress;
            int cost = P.WeaponLevelCost(id);
            if (cost < 0) return;
            if (P.d.gems < cost)
            {
                g.hud.ShowPopup(Icon.Gem, "НЕ ХВАТАЕТ КРИСТАЛЛОВ", "Нужно ещё " + (cost - P.d.gems) + ": тайники на холмах, боссы, магазин");
                return;
            }
            double from = P.WeaponHitDamage(id);
            if (!P.BuyWeaponLevel(id)) return;
            g.OnUpgradeBought(id, from, P.WeaponHitDamage(id));
            g.SaveNow();
            if (P.d.upgradesBought == 1) Close();
            else LateRebuild();
        }

        void ArmorRow(int id)
        {
            var d = Game.I.progress.d; var a = Content.Armors[id];
            int lvl = d.armorLevel[id];
            bool owned = lvl > 0;
            var r = Row(140, new Color(1f, 0.97f, 0.9f));
            var iconBg = UI.Panel(r, "IconBg", owned ? new Color(0.35f, 0.6f, 0.85f) : new Color(0.5f, 0.5f, 0.5f), 22);
            UI.Place(iconBg.rectTransform, new Vector2(0, 0.5f), new Vector2(16, 0), new Vector2(116, 116), new Vector2(0, 0.5f));
            var ic = UI.IconImg(iconBg.transform, Tex.ArmorIcon(id), 90);
            UI.Place(ic.rectTransform, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(90, 90));
            if (!owned) ic.sprite = Tex.GetLocked(Tex.ArmorIcon(id));
            Label(r, a.name + (owned ? "  Lv " + lvl : ""), 42, owned ? TitleInk : TitleLocked, new Vector2(0, 1), new Vector2(150, -10), new Vector2(600, 60), TextAnchor.MiddleLeft, 0f);
            if (owned)
            {
                var bar = UI.Rect("Copies", r);
                UI.Place(bar, new Vector2(0, 0), new Vector2(152, 20), new Vector2(380, 32), new Vector2(0, 0));
                var f = UI.Bar(bar, "B", new Color(0.45f, 0.75f, 1f), out var br, 14);
                UI.Stretch(br);
                int need = Balance.CopiesForLevel(lvl);
                UI.SetBar(f, d.armorCopies[id] / (float)need);
                var ct = UI.Txt(bar, "T", d.armorCopies[id] + " / " + need, 26, Color.white, TextAnchor.MiddleCenter, 2f);
                UI.Stretch(ct.rectTransform);
            }
            else
            {
                string how = "детали падают с бронированных багги";
                for (int z = 0; z < Content.ZoneCount; z++) if (Content.Zones[z].unlockArmor == id) how = "откроется: победи " + Goals.BossAcc[z] + (z == 1 ? " или ломай живые двигатели" : " или ломай багги");
                var hl = Label(r, how, 26, new Color(0.45f, 0.3f, 0.2f), new Vector2(0, 0), new Vector2(152, 14), new Vector2(640, 64), TextAnchor.MiddleLeft, 0f);
                hl.horizontalOverflow = HorizontalWrapMode.Wrap;
            }
        }

        // ---------------------------------------------------------------- SHOP
        public void ShowShop() => Open("SHOP", BuildShop);

        void BuildShop()
        {
            var d = Game.I.progress.d;
            var bal = Row(110, new Color(0.24f, 0.18f, 0.3f));
            var gi = UI.IconImg(bal, Icon.Gem, 90);
            // the gem, then the number to its right (the number used to start under the gem)
            UI.Place(gi.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(-70, 0), new Vector2(90, 90));
            Label(bal, Fmt.Num(d.gems), 64, Color.white, new Vector2(0.5f, 0.5f), new Vector2(190, 0), new Vector2(400, 90));

            Section("FREE");
            long now = Progress.NowMs;
            bool freeReady = now >= Game.I.freeGemsAt;
            ShopItem(Icon.GemPile, "Free Gems", freeReady ? "+" + Balance.FreeGems + " кристаллов раз в " + Balance.FreeGemsHours.ToString("0") + " ч" : "Следующие через " + Fmt.Time((Game.I.freeGemsAt - now) / 1000.0), freeReady ? "CLAIM" : "WAIT", 0, freeReady, () =>
            {
                Game.I.progress.d.gems += Balance.FreeGems;
                Game.I.freeGemsAt = Progress.NowMs + (long)(Balance.FreeGemsHours * 3600L * 1000L);
                Game.I.SaveNow();
                Game.I.sfx.Play(Sfx.Kind.Chest, Vector3.zero, 0.8f);
            }, "Free");

            // one copy chosen in the garage costs Balance.GemsPerCopy; crates are cheaper per copy but random
            Section("CRATES");
            ShopItem(Icon.Chest, "Weapon Crate", Balance.CrateCopies + " случайные копии оружия · " + PerUnit(Balance.CratePrice, Balance.CrateCopies) + " за копию", "", Balance.CratePrice, true, () => GiveCopies(Balance.CrateCopies), "Crate");
            ShopItem(Icon.ChestBig, "Big Weapon Crate", Balance.BigCrateCopies + " случайных копий · " + PerUnit(Balance.BigCratePrice, Balance.BigCrateCopies) + " за копию", "", Balance.BigCratePrice, true, () => GiveCopies(Balance.BigCrateCopies), "BigCrate");
            ShopItem(Icon.ChestArmor, "Armor Crate", Balance.ArmorCrateParts + " случайные детали брони · " + PerUnit(Balance.ArmorCratePrice, Balance.ArmorCrateParts) + " за деталь", "", Balance.ArmorCratePrice, true, () =>
            {
                for (int i = 0; i < Balance.ArmorCrateParts; i++) Game.I.progress.AddArmorCopies(UnityEngine.Random.Range(0, 2), 1);
            }, "ArmorCrate");

            // stat packs: a fixed amount of farming (five minutes of the furthest zone), never a share of the stat
            Section("BOOSTS");
            var P = Game.I.progress;
            var bt = BestType();
            int zone = d.unlockedZone;
            double dmgBoost = Balance.PackDamage(zone);
            ShopItem(Tex.DamageIcon(bt), "Damage Pack", "+" + Fmt.Num(dmgBoost) + " к урону " + Content.DamageTypeNames[(int)bt] + " = " + Balance.PackFarmMinutes.ToString("0") + " мин фарма", "", Balance.PackPrice, true, () => P.Apply(Reward.Dmg(bt, dmgBoost)), "DmgPack");
            double hpBoost = Balance.PackHP(zone);
            ShopItem(Icon.Heart, "Armor Plating", "+" + Fmt.Num(hpBoost) + " к макс. HP = " + Balance.PackFarmMinutes.ToString("0") + " мин фарма", "", Balance.PackPrice, true, () => P.Apply(Reward.HP(hpBoost)), "HpPack");
        }

        static string PerUnit(int price, int units)
        {
            double v = price / (double)units;
            return Math.Abs(v - Math.Round(v)) < 0.05 ? Math.Round(v).ToString("0") : v.ToString("0.0", System.Globalization.CultureInfo.InvariantCulture);
        }

        void GiveCopies(int n)
        {
            var P = Game.I.progress;
            for (int i = 0; i < n; i++)
            {
                int id; int guard = 0;
                do { id = UnityEngine.Random.Range(0, 4); guard++; } while (!P.WeaponOwned(id) && guard < 20);
                if (!P.WeaponOwned(id)) id = 0;
                P.AddWeaponCopies(id, 1);
            }
        }

        void ShopItem(Icon icon, string name, string desc, string btnText, int cost, bool enabled, Action buy, string key = "")
        {
            var r = Row(160, new Color(1f, 0.97f, 0.9f));
            var iconBg = UI.Panel(r, "IconBg", new Color(0.95f, 0.6f, 0.2f), 22);
            UI.Place(iconBg.rectTransform, new Vector2(0, 0.5f), new Vector2(16, 0), new Vector2(130, 130), new Vector2(0, 0.5f));
            var ic = UI.IconImg(iconBg.transform, icon, 100);
            UI.Place(ic.rectTransform, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(100, 100));
            Label(r, name, 44, TitleInk, new Vector2(0, 1), new Vector2(166, -14), new Vector2(520, 60), TextAnchor.MiddleLeft, 0f);
            var dl = Label(r, desc, 28, new Color(0.3f, 0.2f, 0.15f), new Vector2(0, 0), new Vector2(166, 16), new Vector2(500, 74), TextAnchor.MiddleLeft, 0f);
            dl.horizontalOverflow = HorizontalWrapMode.Wrap;
            var d = Game.I.progress.d;
            bool afford = cost == 0 || d.gems >= cost;
            var b = UI.Btn(r, "Buy", enabled && afford ? UI.Green : new Color(0.6f, 0.6f, 0.6f), () =>
            {
                var dd = Game.I.progress.d;
                if (!enabled) return;
                if (cost > 0 && dd.gems < cost) { Game.I.hud.ShowPopup(Icon.Gem, "НЕ ХВАТАЕТ КРИСТАЛЛОВ", "Нужно ещё " + (cost - dd.gems) + ": тайники на холмах, боссы, бесплатные кристаллы"); return; }
                dd.gems -= cost;
                buy();
                Game.I.sfx.Play(Sfx.Kind.LevelUp, Vector3.zero, 0.7f);
                Game.I.SaveNow();
                LateRebuild();
            }, 24);
            b.gameObject.name = "Buy" + key;
            UI.Place((RectTransform)b.transform, new Vector2(1, 0.5f), new Vector2(-16, 0), new Vector2(210, 120), new Vector2(1, 0.5f));
            if (cost > 0)
            {
                var gi = UI.IconImg(b.transform, Icon.Gem, 46);
                UI.Place(gi.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(-50, 0), new Vector2(46, 46));
                Label((RectTransform)b.transform, cost.ToString(), 40, Color.white, new Vector2(0.5f, 0.5f), new Vector2(24, 0), new Vector2(130, 60), TextAnchor.MiddleCenter);
            }
            else Label((RectTransform)b.transform, btnText, 40, Color.white, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(200, 60), TextAnchor.MiddleCenter);
        }

        // ---------------------------------------------------------------- SETTINGS
        public void ShowSettings() => Open("SETTINGS", BuildSettings);

        void BuildSettings()
        {
            var d = Game.I.progress.d;
            Toggle("Sound", d.soundOn, v => { Game.I.progress.d.soundOn = v; Game.I.sfx.on = v; });
            Toggle("Music", d.musicOn, v => { Game.I.progress.d.musicOn = v; Game.I.sfx.musicOn = v; });
            Toggle("Vibration", d.vibrationOn, v => { Game.I.progress.d.vibrationOn = v; });
            // progress reset: a big red button, then the confirmation dialog
            var r = Row(160);
            var b = UI.Btn(r, "ResetProgress", UI.Red, ShowResetConfirm, 28);
            UI.Stretch((RectTransform)b.transform, 6, 10, 6, 10);
            var lbl = UI.TxtRu(b.transform, "Label", ResetButtonText, 50, Color.white, TextAnchor.MiddleCenter, 3f);
            UI.Stretch(lbl.rectTransform, 0, 4, 0, 0);

            var info = Row(220);
            var t = UI.Txt(info, "Info", "ROAD GAME\nDrive with the joystick. The hood machine gun and the weapon arms hit whatever is close.\nThe harpooner reels the scrap in: every wreck = permanent stats.\nFonts: Lilita One, Rubik (SIL Open Font License)", 30, new Color(0.35f, 0.25f, 0.2f), TextAnchor.MiddleCenter, 0f);
            UI.Stretch(t.rectTransform);
            t.horizontalOverflow = HorizontalWrapMode.Wrap;
        }

        void Toggle(string name, bool value, Action<bool> set)
        {
            var r = Row(130, new Color(1f, 0.97f, 0.9f));
            Label(r, name, 46, new Color(0.3f, 0.2f, 0.15f), new Vector2(0, 0.5f), new Vector2(30, 0), new Vector2(500, 60), TextAnchor.MiddleLeft, 0f);
            var b = UI.Btn(r, "Toggle", value ? UI.Green : new Color(0.6f, 0.6f, 0.6f), () => { set(!value); Game.I.SaveNow(); LateRebuild(); }, 24);
            UI.Place((RectTransform)b.transform, new Vector2(1, 0.5f), new Vector2(-16, 0), new Vector2(210, 100), new Vector2(1, 0.5f));
            Label((RectTransform)b.transform, value ? "ON" : "OFF", 44, Color.white, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(200, 60), TextAnchor.MiddleCenter);
        }
    }
}
