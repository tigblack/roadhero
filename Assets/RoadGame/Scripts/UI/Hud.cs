using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace RoadGame
{
    /// <summary>Screen HUD laid out like the reference: settings top-left, glass minimap top-right, side buttons,
    /// floating joystick, weapon/armor slot bar at the bottom, boss bar, banners and popups.</summary>
    public class Hud : MonoBehaviour
    {
        public Canvas canvas;
        public RectTransform root;
        RectTransform safeRect;
        public Joystick joystick;
        public Minimap minimap;
        public Panels panels;
        public DevPanel devPanel;

        Text gemsTxt;
        RectTransform bossBar;
        Image bossFill;
        Text bossHp, bossName;
        RectTransform banner;
        Text bannerTitle, bannerSub;
        float bannerTime;
        RectTransform popup;
        Image popupIcon;
        Text popupTitle, popupSub;
        float popupTime;
        readonly Queue<(Icon icon, string title, string sub)> popupQueue = new Queue<(Icon, string, string)>();
        RectTransform deathPanel;
        Text deathCount;
        RectTransform hint;
        RectTransform bonusBtn;
        Image bonusIcon;
        Text bonusTxt;
        Image lowHpVignette;
        RectTransform healArrow;
        readonly Slot[] weaponSlots = new Slot[4];
        readonly Slot[] armorSlots = new Slot[2];
        string gemsStr;
        // progressive HUD: what is shown grows with the game (garage with the first affordable upgrade, the shop
        // after the first purchase, the next locked weapon with its condition, armor when it comes close)
        RectTransform gemsPanel, garageBtn, shopBtn, slotSep, settingsBtn, zoomBtn, devBtn;
        Image garageDot, shopDot;
        // the goal widget (top left, under the settings) and its route pointer in the world
        RectTransform goalPanel;
        Image goalIcon;
        Text goalTitle, goalSub, goalDist;
        string goalTitleStr, goalSubStr;
        Icon goalIconShown = (Icon)(-1);
        int goalDistShown = -2;
        Transform pointer;
        float pointerShow;
        /// <summary>HUD areas world labels must keep out of (buttons, minimap, widget, slot bar).</summary>
        public readonly List<RectTransform> Blockers = new List<RectTransform>();
        public Goals.Goal Goal { get; private set; }
        readonly List<RectTransform> shownSlots = new List<RectTransform>(6);
        // the buttons a player taps (the guided test bot taps them the same way)
        public RectTransform GoalPanel => goalPanel;
        public RectTransform GarageButton => garageBtn;
        public RectTransform ShopButton => shopBtn;
        public RectTransform BonusButton => bonusBtn;
        public RectTransform DevButton => devBtn;
        static readonly string[] BossNom = { "МАМОНТ", "МАТКА", "РЕАКТОР", "ПОЛКОВОДЕЦ" };

        class Slot
        {
            public RectTransform r;
            public Image icon, lockIcon, progFill;
            public Icon baseIcon;
            public Text level;
            public RectTransform prog;
            public RectTransform cond;          // locked: "skull + boss name" over the slot = what opens it
            public Text condTxt;
            public int shownLevel = -1, shownCopies = -1;
            public float pulse;
        }

        public static Hud Create()
        {
            var c = UI.CreateCanvas("HudCanvas", 10);
            var h = c.gameObject.AddComponent<Hud>();
            h.canvas = c;
            h.root = (RectTransform)c.transform;
            h.Build();
            return h;
        }

        void Build()
        {
            // safe area container
            var safe = UI.Rect("Safe", root);
            UI.Stretch(safe);
            safe.gameObject.AddComponent<SafeArea>();
            safeRect = safe;

            joystick = Joystick.Create(canvas);
            joystick.transform.SetParent(safe, false);
            joystick.transform.SetAsFirstSibling();

            // low HP vignette
            lowHpVignette = UI.Img(root, "LowHp", Tex.FromTexture(Tex.Vignette()), new Color(0.8f, 0f, 0f, 0f));
            UI.Stretch(lowHpVignette.rectTransform);
            lowHpVignette.transform.SetAsFirstSibling();
            lowHpVignette.enabled = false;

            // top-left: settings + gems
            var settings = UI.IconBtn(safe, "Settings", Icon.Gear, new Color(0.35f, 0.38f, 0.44f), () => panels.ShowSettings(), 104);
            UI.Place((RectTransform)settings.transform, new Vector2(0, 1), new Vector2(26, -26), new Vector2(104, 104), new Vector2(0, 1));
            settingsBtn = (RectTransform)settings.transform;
            var gems = UI.Panel(safe, "Gems", new Color(0.2f, 0.16f, 0.24f, 0.9f), 26);
            gemsPanel = gems.rectTransform;
            UI.Place(gems.rectTransform, new Vector2(0, 1), new Vector2(146, -40), new Vector2(210, 76), new Vector2(0, 1));
            var gi = UI.IconImg(gems.transform, Icon.Gem, 64);
            UI.Place(gi.rectTransform, new Vector2(0, 0.5f), new Vector2(-10, 0), new Vector2(64, 64), new Vector2(0, 0.5f));
            gemsTxt = UI.Txt(gems.transform, "Txt", "0", 40, Color.white, TextAnchor.MiddleLeft);
            UI.Place(gemsTxt.rectTransform, new Vector2(0, 0.5f), new Vector2(62, 2), new Vector2(140, 60), new Vector2(0, 0.5f));

            // top-right: minimap + zoom
            minimap = Minimap.Create(safe, 300f);
            UI.Place((RectTransform)minimap.transform, new Vector2(1, 1), new Vector2(-30, -30), new Vector2(300, 300), new Vector2(1, 1));
            var zoom = UI.IconBtn(safe, "Zoom", Icon.Zoom, new Color(0.35f, 0.38f, 0.44f), () => minimap.ToggleZoom(), 78);
            UI.Place((RectTransform)zoom.transform, new Vector2(1, 1), new Vector2(-14, -14), new Vector2(78, 78), new Vector2(1, 1));
            zoomBtn = (RectTransform)zoom.transform;

            // right side buttons (garage = green, shop = orange) like the reference
            var garage = UI.IconBtn(safe, "Garage", Icon.Wrench, new Color(0.3f, 0.75f, 0.38f), () => panels.ShowGarage(Game.I.progress.AffordableUpgrade()), 128);
            UI.Place((RectTransform)garage.transform, new Vector2(1, 1), new Vector2(-30, -372), new Vector2(128, 128), new Vector2(1, 1));
            AddLabel(garage.transform, "GARAGE");
            garageBtn = (RectTransform)garage.transform;
            garageDot = Dot(garageBtn);
            var shop = UI.IconBtn(safe, "Shop", Icon.Chest, new Color(0.95f, 0.6f, 0.2f), () => panels.ShowShop(), 128);
            UI.Place((RectTransform)shop.transform, new Vector2(1, 1), new Vector2(-30, -540), new Vector2(128, 128), new Vector2(1, 1));
            AddLabel(shop.transform, "SHOP");
            shopBtn = (RectTransform)shop.transform;
            shopDot = Dot(shopBtn);

            var dev = UI.Btn(safe, "Dev", new Color(0.4f, 0.32f, 0.65f), () => devPanel.Open(), 22);
            devBtn = (RectTransform)dev.transform;
            UI.Place(devBtn, new Vector2(1, 1), new Vector2(-30, -738), new Vector2(128, 112), Vector2.one);
            var devTitle = UI.Txt(devBtn, "Title", "DEV", 38, Color.white);
            UI.Place(devTitle.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 20), new Vector2(120, 50));
            var devState = UI.Txt(devBtn, "State", "1x", 24, UI.Cream);
            UI.Place(devState.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, -26), new Vector2(124, 38));

            // left side: bonus offer (the reference's rewarded bubble)
            bonusBtn = (RectTransform)UI.IconBtn(safe, "Bonus", Icon.Heart, new Color(0.2f, 0.17f, 0.16f), () => Game.I.ClaimBonus(), 132).transform;
            UI.Place(bonusBtn, new Vector2(0, 0.5f), new Vector2(26, 120), new Vector2(132, 132), new Vector2(0, 0.5f));
            bonusIcon = bonusBtn.Find("Icon").GetComponent<Image>();
            var ad = UI.IconImg(bonusBtn, Icon.Ad, 50);
            UI.Place(ad.rectTransform, new Vector2(0, 1), new Vector2(-8, 8), new Vector2(50, 50), new Vector2(0, 1));
            bonusTxt = UI.Txt(bonusBtn, "Val", "+0", 36, Color.white);
            UI.Place(bonusTxt.rectTransform, new Vector2(0.5f, 0), new Vector2(0, -22), new Vector2(200, 44), new Vector2(0.5f, 0));
            bonusBtn.gameObject.AddComponent<Pulse>().amount = 0.05f;

            // boss bar
            bossBar = UI.Rect("BossBar", safe);
            UI.Place(bossBar, new Vector2(0.5f, 1), new Vector2(-40, -150), new Vector2(560, 64), new Vector2(0.5f, 1));
            bossFill = UI.Bar(bossBar, "Bar", new Color(0.95f, 0.25f, 0.32f), out var bbr, 20);
            UI.Stretch(bbr, 50, 0, 0, 0);
            var skull = UI.IconImg(bossBar, Icon.Skull, 104);
            UI.Place(skull.rectTransform, new Vector2(0, 0.5f), new Vector2(-14, 0), new Vector2(104, 104), new Vector2(0, 0.5f));
            bossHp = UI.Txt(bossBar, "Hp", "", 40, Color.white);
            UI.Stretch(bossHp.rectTransform, 50, 2, 0, 0);
            bossName = UI.Txt(bossBar, "Name", "", 34, new Color(1f, 0.85f, 0.7f));
            UI.Place(bossName.rectTransform, new Vector2(0.5f, 0), new Vector2(25, -6), new Vector2(500, 44), new Vector2(0.5f, 1));
            bossBar.gameObject.SetActive(false);

            // weapon / armor slot bar
            var barRoot = UI.Rect("SlotBar", safe);
            UI.Place(barRoot, new Vector2(0.5f, 0), new Vector2(0, 30), new Vector2(980, 150), new Vector2(0.5f, 0));
            for (int i = 0; i < 4; i++) weaponSlots[i] = MakeSlot(barRoot, new Vector2(-400 + i * 140, 0), Tex.DamageIcon(Content.Weapons[i].type), i, false);
            var sep = UI.Img(barRoot, "Sep", Tex.RoundRect(4), new Color(1, 1, 1, 0.5f));
            UI.Place(sep.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(170, 0), new Vector2(8, 110));
            slotSep = sep.rectTransform;
            for (int i = 0; i < 2; i++) armorSlots[i] = MakeSlot(barRoot, new Vector2(260 + i * 140, 0), Tex.ArmorIcon(i), i, true);

            BuildGoalWidget(safe);

            // zone banner
            banner = UI.Rect("Banner", root);
            UI.Place(banner, new Vector2(0.5f, 0.79f), Vector2.zero, new Vector2(1000, 200));
            bannerTitle = UI.Txt(banner, "Title", "", 92, new Color(1f, 0.86f, 0.35f), TextAnchor.MiddleCenter, 5f);
            UI.Place(bannerTitle.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 30), new Vector2(960, 120));
            bannerTitle.horizontalOverflow = HorizontalWrapMode.Wrap;
            bannerTitle.verticalOverflow = VerticalWrapMode.Truncate;
            bannerTitle.resizeTextForBestFit = true;
            bannerTitle.resizeTextMinSize = 40;
            bannerTitle.resizeTextMaxSize = 92;
            bannerSub = UI.Txt(banner, "Sub", "", 46, Color.white, TextAnchor.MiddleCenter, 3f);
            UI.Place(bannerSub.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, -50), new Vector2(1000, 60));
            banner.gameObject.SetActive(false);

            // popup (new weapon / level up)
            popup = UI.Rect("Popup", root);
            UI.Place(popup, new Vector2(0.5f, 0.6f), Vector2.zero, new Vector2(700, 300));
            var glow = UI.Img(popup, "Glow", Tex.FromTexture(Tex.SoftCircle()), new Color(1f, 0.85f, 0.3f, 0.6f));
            UI.Place(glow.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 50), new Vector2(420, 420));
            var frame = UI.Panel(popup, "Frame", new Color(0.25f, 0.55f, 0.95f), 30);
            UI.Place(frame.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 50), new Vector2(190, 190));
            popupIcon = UI.IconImg(frame.transform, Icon.Gun, 150);
            UI.Place(popupIcon.rectTransform, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(150, 150));
            popupTitle = UI.Txt(popup, "Title", "", 70, new Color(0.45f, 1f, 0.5f), TextAnchor.MiddleCenter, 4f);
            UI.Place(popupTitle.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, -95), new Vector2(940, 90));
            popupTitle.horizontalOverflow = HorizontalWrapMode.Wrap;
            popupTitle.resizeTextForBestFit = true;
            popupTitle.resizeTextMinSize = 36;
            popupTitle.resizeTextMaxSize = 70;
            popupSub = UI.Txt(popup, "Sub", "", 40, Color.white, TextAnchor.MiddleCenter, 3f);
            UI.Place(popupSub.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, -160), new Vector2(900, 60));
            popup.gameObject.SetActive(false);

            // death overlay
            deathPanel = UI.Rect("Death", root);
            UI.Stretch(deathPanel);
            var dim = deathPanel.gameObject.AddComponent<Image>();
            dim.color = new Color(0.15f, 0.02f, 0.02f, 0.55f);
            dim.raycastTarget = true;
            var dt = UI.Txt(deathPanel, "Title", "WRECKED!", 120, new Color(1f, 0.35f, 0.3f), TextAnchor.MiddleCenter, 6f);
            UI.Place(dt.rectTransform, new Vector2(0.5f, 0.6f), Vector2.zero, new Vector2(1000, 160));
            var ds = UI.Txt(deathPanel, "Sub", "Your stats are permanent. Towing you to the garage...", 40, Color.white);
            UI.Place(ds.rectTransform, new Vector2(0.5f, 0.6f), new Vector2(0, -110), new Vector2(1000, 60));
            deathCount = UI.Txt(deathPanel, "Count", "", 80, Color.white);
            UI.Place(deathCount.rectTransform, new Vector2(0.5f, 0.45f), Vector2.zero, new Vector2(400, 120));
            deathPanel.gameObject.SetActive(false);

            // tutorial hint
            hint = UI.Rect("Hint", safe);
            UI.Place(hint, new Vector2(0.5f, 0), new Vector2(0, 520), new Vector2(900, 120));
            var ht = UI.Txt(hint, "Txt", "DRAG ANYWHERE TO DRIVE", 54, Color.white, TextAnchor.MiddleCenter, 4f);
            UI.Stretch(ht.rectTransform);
            var ht2 = UI.Txt(hint, "Txt2", "Smash everything. Harpoon the scrap. Grow forever.", 36, new Color(1f, 0.9f, 0.7f), TextAnchor.MiddleCenter, 3f);
            UI.Place(ht2.rectTransform, new Vector2(0.5f, 0), new Vector2(0, -40), new Vector2(1000, 50));
            hint.gameObject.AddComponent<Pulse>();

            // heal direction arrow (shown when HP is low)
            healArrow = UI.Rect("HealArrow", root);
            healArrow.anchorMin = healArrow.anchorMax = Vector2.zero;
            healArrow.sizeDelta = new Vector2(90, 90);
            var ha = UI.IconImg(healArrow, Icon.Plus, 70);
            UI.Place(ha.rectTransform, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(70, 70));
            var harr = UI.IconImg(healArrow, Icon.Arrow, 44);
            harr.color = new Color(0.4f, 1f, 0.5f);
            UI.Place(harr.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 58), new Vector2(44, 44));
            healArrow.gameObject.SetActive(false);

            panels = Panels.Create(root);
            devPanel = DevPanel.Create(root, this, devState);

            Blockers.AddRange(new[] { settingsBtn, gemsPanel, (RectTransform)minimap.transform, zoomBtn, garageBtn, shopBtn, devBtn, bonusBtn, goalPanel, bossBar, hint });
            foreach (var sl in weaponSlots) Blockers.Add(sl.r);
            foreach (var sl in armorSlots) Blockers.Add(sl.r);
        }

        static Image Dot(RectTransform parent)
        {
            var d = UI.Img(parent, "Dot", Tex.Circle(), new Color(0.95f, 0.18f, 0.2f));
            UI.Place(d.rectTransform, new Vector2(1, 1), new Vector2(4, 4), new Vector2(40, 40), new Vector2(1, 1));
            d.gameObject.AddComponent<Pulse>().amount = 0.14f;
            d.gameObject.SetActive(false);
            return d;
        }

        /// <summary>The goal widget: what to do next, how, what it gives, how far (Russian, the Cyrillic font).</summary>
        void BuildGoalWidget(RectTransform safe)
        {
            var bg = UI.Btn(safe, "Goal", new Color(0.12f, 0.1f, 0.12f, 0.84f), OnGoalTap, 26);
            goalPanel = (RectTransform)bg.transform;
            // stretches from the left edge to just short of the minimap: never under it on tall or narrow screens
            goalPanel.anchorMin = new Vector2(0f, 1f); goalPanel.anchorMax = new Vector2(1f, 1f); goalPanel.pivot = new Vector2(0f, 1f);
            goalPanel.offsetMin = new Vector2(26f, -300f); goalPanel.offsetMax = new Vector2(-(30f + 300f + 16f), -150f);
            var iconBg = UI.Panel(goalPanel, "IconBg", new Color(0.95f, 0.72f, 0.2f), 20, false);
            UI.Place(iconBg.rectTransform, new Vector2(0, 0.5f), new Vector2(12, 0), new Vector2(94, 94), new Vector2(0, 0.5f));
            goalIcon = UI.IconImg(iconBg.transform, Icon.Skull, 76);
            UI.Place(goalIcon.rectTransform, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(76, 76));
            goalTitle = UI.TxtRu(goalPanel, "Title", "", 30, Color.white, TextAnchor.MiddleLeft, 2f);
            var tr = goalTitle.rectTransform;
            tr.anchorMin = new Vector2(0f, 1f); tr.anchorMax = new Vector2(1f, 1f); tr.pivot = new Vector2(0f, 1f);
            tr.offsetMin = new Vector2(120f, -78f); tr.offsetMax = new Vector2(-14f, -8f);
            FitLine(goalTitle, 20, 30);
            goalSub = UI.TxtRu(goalPanel, "Sub", "", 24, new Color(1f, 0.88f, 0.6f), TextAnchor.MiddleLeft, 1.6f);
            var sr = goalSub.rectTransform;
            sr.anchorMin = new Vector2(0f, 0f); sr.anchorMax = new Vector2(1f, 0f); sr.pivot = new Vector2(0f, 0f);
            sr.offsetMin = new Vector2(120f, 8f); sr.offsetMax = new Vector2(-112f, 72f);
            FitLine(goalSub, 20, 25);
            goalDist = UI.TxtRu(goalPanel, "Dist", "", 30, new Color(0.55f, 1f, 0.55f), TextAnchor.MiddleRight, 2f);
            UI.Place(goalDist.rectTransform, new Vector2(1, 0), new Vector2(-12, 10), new Vector2(106, 46), new Vector2(1, 0));
            goalPanel.gameObject.SetActive(false);

            // route pointer: a small floating arrow ahead of the car, pointing along the way to the goal
            var go = new GameObject("GoalPointer");
            pointer = go.transform;
            Models.MeshGO("Arrow", Structures.GuideArrowMesh(), Mats.Toon, pointer, false);
            go.SetActive(false);
        }

        static void FitLine(Text t, int min, int max)
        {
            t.horizontalOverflow = HorizontalWrapMode.Wrap;
            t.verticalOverflow = VerticalWrapMode.Truncate;
            t.resizeTextForBestFit = true;
            t.resizeTextMinSize = min;
            t.resizeTextMaxSize = max;
        }

        void OnGoalTap()
        {
            var g = Goal;
            if (g == null) return;
            if (g.kind == Goals.Kind.Upgrade) panels.ShowGarage(0);
        }

        void AddLabel(Transform parent, string s)
        {
            var t = UI.Txt(parent, "Label", s, 30, Color.white, TextAnchor.MiddleCenter, 2.5f);
            UI.Place(t.rectTransform, new Vector2(0.5f, 0), new Vector2(0, -18), new Vector2(200, 40), new Vector2(0.5f, 0));
        }

        Slot MakeSlot(RectTransform parent, Vector2 pos, Icon icon, int index, bool armor)
        {
            var s = new Slot();
            var b = UI.Btn(parent, (armor ? "Armor" : "Weapon") + index, new Color(0.24f, 0.22f, 0.22f, 0.92f), () =>
            {
                var d = Game.I.progress.d;
                bool owned = armor ? d.armorLevel[index] > 0 : d.weaponLevel[index] > 0;
                if (!owned) { ShowLockedInfo(armor, index); return; }
                if (armor) panels.ShowGarage(); else panels.ShowGarage(index);
            }, 22);
            s.r = (RectTransform)b.transform;
            s.baseIcon = icon;
            UI.Place(s.r, new Vector2(0.5f, 0.5f), pos, new Vector2(124, 124));
            s.icon = UI.IconImg(s.r, icon, 92);
            UI.Place(s.icon.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 6), new Vector2(92, 92));
            s.level = UI.Txt(s.r, "Lvl", "1", 38, Color.white, TextAnchor.LowerRight, 3f);
            UI.Place(s.level.rectTransform, new Vector2(1, 0), new Vector2(-6, 2), new Vector2(80, 50), new Vector2(1, 0));
            s.prog = UI.Rect("Prog", s.r);
            UI.Place(s.prog, new Vector2(0.5f, 0), new Vector2(0, -8), new Vector2(104, 16), new Vector2(0.5f, 0.5f));
            s.progFill = UI.Bar(s.prog, "Bar", new Color(1f, 0.75f, 0.25f), out var pr, 8);
            UI.Stretch(pr);
            s.lockIcon = UI.IconImg(s.r, Icon.Lock, 56);
            UI.Place(s.lockIcon.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(0, 0), new Vector2(64, 64));
            if (!armor)
            {
                var pill = UI.Panel(s.r, "Cond", new Color(0.12f, 0.1f, 0.12f, 0.88f), 18);
                s.cond = pill.rectTransform;
                UI.Place(s.cond, new Vector2(0.5f, 1f), new Vector2(0, 12), new Vector2(176, 44), new Vector2(0.5f, 0f));
                var sk = UI.IconImg(s.cond, Icon.Skull, 34);
                UI.Place(sk.rectTransform, new Vector2(0, 0.5f), new Vector2(8, 0), new Vector2(34, 34), new Vector2(0, 0.5f));
                s.condTxt = UI.TxtRu(s.cond, "T", "", 22, new Color(1f, 0.85f, 0.55f), TextAnchor.MiddleLeft, 1.5f);
                UI.Place(s.condTxt.rectTransform, new Vector2(0, 0.5f), new Vector2(46, 1), new Vector2(124, 40), new Vector2(0, 0.5f));
                s.cond.gameObject.SetActive(false);
            }
            return s;
        }

        /// <summary>Tap on a locked slot: what it is and how it opens.</summary>
        void ShowLockedInfo(bool armor, int index)
        {
            for (int z = 0; z < Content.ZoneCount; z++)
            {
                var zd = Content.Zones[z];
                if ((!armor && zd.unlockWeapon == index) || (armor && zd.unlockArmor == index))
                {
                    string name = armor ? Content.Armors[index].name : Content.Weapons[index].name + ": " + Goals.WeaponWhat[index];
                    ShowPopup(armor ? Tex.ArmorIcon(index) : Tex.DamageIcon(Content.Weapons[index].type), name,
                              "Откроется, когда победишь " + Goals.BossAcc[z] + (z == 0 ? " в подземном цехе" : ""));
                    return;
                }
            }
        }

        /// <summary>The next weapon to unlock (the one the lowest boss still alive gives), -1 when all are owned.</summary>
        static int NextLockedWeapon(SaveData d)
        {
            for (int z = 0; z < Content.ZoneCount; z++)
            {
                int w = Content.Zones[z].unlockWeapon;
                if (w >= 0 && d.weaponLevel[w] <= 0) return w;
            }
            return -1;
        }

        // ---------------------------------------------------------------- public API
        public void ShowBanner(string title, string sub)
        {
            banner.gameObject.SetActive(true);
            UI.SetText(bannerTitle, title);
            UI.SetText(bannerSub, sub);
            bannerTime = 0f;
        }

        public void ShowPopup(Icon icon, string title, string sub)
        {
            popupQueue.Enqueue((icon, title, sub));
            if (!popup.gameObject.activeSelf) NextPopup();
        }

        void NextPopup()
        {
            if (popupQueue.Count == 0) { popup.gameObject.SetActive(false); return; }
            var (icon, title, sub) = popupQueue.Dequeue();
            popup.gameObject.SetActive(true);
            popupIcon.sprite = Tex.Get(icon);
            UI.SetText(popupTitle, title);
            UI.SetText(popupSub, sub);
            popupTime = 0f;
        }

        public void PulseWeapon(int id) { if (id >= 0 && id < 4) weaponSlots[id].pulse = 1f; }
        public void PulseArmor(int id) { if (id >= 0 && id < 2) armorSlots[id].pulse = 1f; }

        public void HideHint() { if (hint != null) hint.gameObject.SetActive(false); }

        /// <summary>Short one-line hint in the tutorial slot (the intro's "hit the ramp").</summary>
        public void ShowHint(string title, string sub)
        {
            if (hint == null) return;
            var t1 = hint.Find("Txt"); var t2 = hint.Find("Txt2");
            if (t1 != null) UI.SetText(t1.GetComponent<Text>(), title);
            if (t2 != null) UI.SetText(t2.GetComponent<Text>(), sub);
            hint.gameObject.SetActive(true);
        }

        // ---- orientation: the HUD is drawn for a portrait phone; a phone turned sideways (the web build allows it) gets
        // its own placement of the few things that sit over the middle of the screen, so the car stays in the clear
        int layoutLandscape = -1;
        float layoutWidth = -1f;

        void ApplyOrientation()
        {
            var r = safeRect != null ? safeRect.rect : root.rect;
            if (r.width <= 0f || r.height <= 0f) return;
            bool land = r.width > r.height * 1.05f;
            if ((land ? 1 : 0) == layoutLandscape && Mathf.Abs(r.width - layoutWidth) < 1f) return;
            layoutLandscape = land ? 1 : 0;
            layoutWidth = r.width;
            float w = r.width;
            if (!land)
            {
                joystick.SetRest(new Vector2(0, 330));
                UI.Place(hint, new Vector2(0.5f, 0), new Vector2(0, 520), new Vector2(900, 120));
                hint.GetComponent<Pulse>()?.SetBase(Vector3.one);
                UI.Place(banner, new Vector2(0.5f, 0.79f), Vector2.zero, new Vector2(1000, 200));
                UI.Place(popup, new Vector2(0.5f, 0.6f), Vector2.zero, new Vector2(700, 300));
                goalPanel.anchorMax = new Vector2(1f, 1f);
                goalPanel.offsetMin = new Vector2(26f, -300f); goalPanel.offsetMax = new Vector2(-(30f + 300f + 16f), -150f);
                return;
            }
            // landscape: the joystick waits bottom left (the thumb's natural spot), its hint above it; the zone banner
            // sits in the gap between the goal widget and the minimap; popups to the right of the car
            // (clear of the web page's fullscreen button, which sits in the bottom-left corner)
            joystick.SetRest(new Vector2(-w * 0.5f + 400f, 270f));
            // the hint (two lines, the second 1000 wide) a little smaller, left of the car and above the joystick
            UI.Place(hint, new Vector2(0f, 0f), new Vector2(560f, 430f), new Vector2(640f, 90f), new Vector2(0.5f, 0f));
            hint.GetComponent<Pulse>()?.SetBase(Vector3.one * 0.78f);
            const float goalW = 860f;
            goalPanel.anchorMax = new Vector2(0f, 1f);
            goalPanel.offsetMin = new Vector2(26f, -300f); goalPanel.offsetMax = new Vector2(26f + goalW, -150f);
            // banner and popup live on the full canvas (not the safe area): measure the gap in canvas units
            float full = root.rect.width;
            float insetL = safeRect != null ? safeRect.anchorMin.x * full : 0f, insetR = safeRect != null ? (1f - safeRect.anchorMax.x) * full : 0f;
            float gapL = insetL + 26f + goalW + 20f, gapR = full - insetR - 30f - 300f - 20f;
            UI.Place(banner, new Vector2(0f, 1f), new Vector2((gapL + gapR) * 0.5f, -40f), new Vector2(Mathf.Max(400f, gapR - gapL), 200f), new Vector2(0.5f, 1f));
            UI.Place(popup, new Vector2(0.5f, 0.5f), new Vector2(full * 0.25f - 30f, -10f), new Vector2(700, 300));
        }

        void Update()
        {
            ApplyOrientation();
            var g = Game.I;
            if (g == null || g.player == null || g.progress == null) return;
            var d = g.progress.d;
            float dt = Time.unscaledDeltaTime;

            var gs = Fmt.Num(d.gems);
            if (gs != gemsStr) { gemsStr = gs; gemsTxt.text = gs; }

            // progressive HUD
            bool intro = DevTravel.IntroRunning(d);
            int affordable = g.progress.AffordableUpgrade();
            if (!intro && !d.seenGarage && (affordable >= 0 || d.upgradesBought > 0)) d.seenGarage = true;
            if (!intro && !d.seenShop && (d.upgradesBought > 0 || d.bossKills[0] > 0 || d.gems >= Balance.CratePrice + Balance.LevelUpCost(1, 0))) d.seenShop = true;
            if (!d.seenArmor && (d.armorLevel[0] > 0 || d.armorLevel[1] > 0 || d.unlockedZone >= 1)) d.seenArmor = true;
            SetActive(gemsPanel, d.seenGarage || d.gems > 0);
            SetActive(garageBtn, d.seenGarage);
            SetActive(shopBtn, d.seenShop);
            SetActive(garageDot.rectTransform, d.seenGarage && affordable >= 0 && !panels.IsOpen);
            SetActive(shopDot.rectTransform, d.seenShop && Progress.NowMs >= g.freeGemsAt && !panels.IsOpen);
            int nextLocked = NextLockedWeapon(d);
            LayoutSlots(d, nextLocked);
            UpdateGoal(g, intro);

            // weapon slots
            for (int i = 0; i < 4; i++)
            {
                var s = weaponSlots[i];
                int lvl = d.weaponLevel[i];
                bool owned = lvl > 0;
                if (lvl != s.shownLevel || d.weaponCopies[i] != s.shownCopies)
                {
                    s.shownLevel = lvl; s.shownCopies = d.weaponCopies[i];
                    s.icon.sprite = owned ? Tex.Get(s.baseIcon) : Tex.GetLocked(s.baseIcon);
                    s.lockIcon.enabled = !owned;
                    s.level.text = owned ? lvl.ToString() : "";
                    s.prog.gameObject.SetActive(owned);
                    if (owned) UI.SetBar(s.progFill, d.weaponCopies[i] / (float)Balance.CopiesForLevel(lvl));
                    int bz = -1;
                    for (int z = 0; z < Content.ZoneCount; z++) if (Content.Zones[z].unlockWeapon == i) bz = z;
                    if (s.cond != null && bz >= 0) s.condTxt.text = BossNom[bz];
                }
                if (s.cond != null) SetActive(s.cond, !owned && i == nextLocked && !intro);
                Animate(s, dt);
            }
            for (int i = 0; i < 2; i++)
            {
                var s = armorSlots[i];
                int lvl = d.armorLevel[i];
                bool owned = lvl > 0;
                if (lvl != s.shownLevel || d.armorCopies[i] != s.shownCopies)
                {
                    s.shownLevel = lvl; s.shownCopies = d.armorCopies[i];
                    s.icon.sprite = owned ? Tex.Get(s.baseIcon) : Tex.GetLocked(s.baseIcon);
                    s.lockIcon.enabled = !owned;
                    s.level.text = owned ? lvl.ToString() : "";
                    s.prog.gameObject.SetActive(owned);
                    if (owned) UI.SetBar(s.progFill, d.armorCopies[i] / (float)Balance.CopiesForLevel(lvl));
                }
                Animate(s, dt);
            }

            // boss bar (the fight is the goal itself: the widget steps aside)
            var boss = g.EngagedBoss;
            bossBar.gameObject.SetActive(boss != null);
            if (boss != null) SetActive(goalPanel, false);
            if (boss != null)
            {
                UI.SetBar(bossFill, (float)(boss.hp / boss.maxHp));
                bossHp.text = Fmt.Num(boss.hp);
                // the same name as on the locked slot and in the goal ("МАМОНТ", "МАТКА"), not the English spec name
                int bz = boss.zone != null ? Mathf.Clamp(boss.zone.index, 0, BossNom.Length - 1) : 0;
                if (bossName.text != BossNom[bz]) UI.SetText(bossName, BossNom[bz]);
            }

            // banner
            if (banner.gameObject.activeSelf)
            {
                bannerTime += dt;
                float k = bannerTime;
                float s = k < 0.25f ? Mathf.Lerp(1.6f, 1f, k / 0.25f) : 1f;
                banner.localScale = Vector3.one * s;
                float a = k > 2.4f ? 1f - (k - 2.4f) / 0.6f : 1f;
                SetAlpha(bannerTitle, a); SetAlpha(bannerSub, a);
                if (k > 3f) banner.gameObject.SetActive(false);
            }

            // popup
            if (popup.gameObject.activeSelf)
            {
                popupTime += dt;
                float k = popupTime;
                float s = k < 0.3f ? Mathf.Lerp(0.2f, 1f, Back(k / 0.3f)) : 1f;
                popup.localScale = Vector3.one * s;
                if (k > 2.6f) NextPopup();
            }

            // death overlay
            deathPanel.gameObject.SetActive(!g.player.Alive);
            if (!g.player.Alive) deathCount.text = Mathf.CeilToInt(Mathf.Max(0, g.RespawnIn)).ToString();

            // bonus offer (not during the intro)
            bool bonusReady = g.BonusReady && !intro;
            bonusBtn.gameObject.SetActive(bonusReady && g.player.Alive);
            if (bonusReady)
            {
                bonusIcon.sprite = Tex.Get(g.BonusIsHp ? Icon.Heart : Tex.DamageIcon(g.BonusDamageType));
                bonusTxt.text = "+" + Fmt.Num(g.BonusValue);
            }

            // low HP feedback + direction to the nearest repair pad
            float hpk = (float)(d.hp / d.maxHp);
            bool low = g.player.Alive && hpk < 0.35f;
            lowHpVignette.enabled = low;
            if (low) lowHpVignette.color = new Color(0.85f, 0f, 0f, 0.55f + Mathf.Sin(Time.time * 6f) * 0.2f);
            UpdateHealArrow(low && !g.player.OnRepairPad);
        }

        static void SetActive(RectTransform r, bool on) { if (r != null && r.gameObject.activeSelf != on) r.gameObject.SetActive(on); }

        /// <summary>Owned weapons, then the next locked one (with its lock), then the armor once it is near: centred.</summary>
        void LayoutSlots(SaveData d, int nextLocked)
        {
            var shown = shownSlots;
            shown.Clear();
            for (int i = 0; i < 4; i++)
            {
                bool on = d.weaponLevel[i] > 0 || i == nextLocked;
                SetActive(weaponSlots[i].r, on);
                if (on) shown.Add(weaponSlots[i].r);
            }
            bool armorOn = d.seenArmor;
            int armorStart = shown.Count;
            for (int i = 0; i < 2; i++)
            {
                SetActive(armorSlots[i].r, armorOn);
                if (armorOn) shown.Add(armorSlots[i].r);
            }
            SetActive(slotSep, armorOn && armorStart > 0);
            float total = shown.Count * 140f + (armorOn ? 40f : 0f) - 16f;
            float x = -total * 0.5f + 62f;
            for (int k = 0; k < shown.Count; k++)
            {
                if (k == armorStart && armorOn) { slotSep.anchoredPosition = new Vector2(x - 34f, 0f); x += 40f; }
                shown[k].anchoredPosition = new Vector2(x, 0f);
                x += 140f;
            }
        }

        /// <summary>The goal widget and the route pointer, every frame.</summary>
        void UpdateGoal(Game g, bool intro)
        {
            var goal = Goals.Evaluate(g);
            Goal = goal;
            bool show = !intro && goal.kind != Goals.Kind.None && g.player.Alive;
            SetActive(goalPanel, show);
            if (show)
            {
                if (goal.title != goalTitleStr) { goalTitleStr = goal.title; goalTitle.text = goal.title; }
                if (goal.sub != goalSubStr) { goalSubStr = goal.sub; goalSub.text = goal.sub; }
                if (goal.icon != goalIconShown) { goalIconShown = goal.icon; goalIcon.sprite = Tex.Get(goal.icon); }
                int dm = goal.hasTarget && goal.distance > 12f ? Mathf.RoundToInt(goal.distance / 5f) * 5 : -1;
                if (dm != goalDistShown) { goalDistShown = dm; goalDist.text = dm > 0 ? dm + " м" : ""; }
                goalSub.color = goal.kind == Goals.Kind.Boss && !goal.ready ? new Color(1f, 0.78f, 0.45f) : new Color(0.7f, 1f, 0.6f);
            }
            // the pointer: ahead of the car along the route while the goal is out of the close view
            bool point = show && goal.hasTarget && goal.distance > 16f && !panels.IsOpen && g.EngagedBoss == null;
            pointerShow = Mathf.MoveTowards(pointerShow, point ? 1f : 0f, Time.unscaledDeltaTime * 3f);
            if (pointer.gameObject.activeSelf != pointerShow > 0.01f) pointer.gameObject.SetActive(pointerShow > 0.01f);
            if (pointerShow > 0.01f)
            {
                var p = g.player.Pos;
                var dir = goal.target - p; dir.y = 0f;
                if (dir.sqrMagnitude < 0.01f) dir = g.player.transform.forward;
                dir.Normalize();
                // low over the ground well ahead of the car: clear of the bars and numbers floating over things
                float bob = Mathf.Sin(Time.time * 4f) * 0.4f;
                pointer.position = p + dir * (6.6f + bob) + Vector3.up * 0.7f;
                pointer.rotation = Quaternion.LookRotation(dir, Vector3.up);
                pointer.localScale = Vector3.one * 0.72f * pointerShow;
            }
        }

        void UpdateHealArrow(bool show)
        {
            var g = Game.I;
            var st = show ? World.I.NearestStation(g.player.Pos, DevTravel.AccessZone(g.progress.d)) : null;
            if (st == null) { healArrow.gameObject.SetActive(false); return; }
            var sp = g.cam.WorldToScreenPoint(st.pos);
            float sf = canvas.scaleFactor;
            var screen = new Vector2(g.cam.pixelWidth, g.cam.pixelHeight);
            var center = screen * 0.5f;
            var p = new Vector2(sp.x, sp.y);
            if (sp.z < 0) p = center - (p - center);
            bool onScreen = p.x > 60 && p.x < screen.x - 60 && p.y > 200 && p.y < screen.y - 200;
            if (onScreen) { healArrow.gameObject.SetActive(false); return; }
            var dir = (p - center).normalized;
            float m = Mathf.Min((screen.x * 0.5f - 90) / Mathf.Max(0.01f, Mathf.Abs(dir.x)), (screen.y * 0.5f - 260) / Mathf.Max(0.01f, Mathf.Abs(dir.y)));
            var pos = center + dir * m;
            healArrow.gameObject.SetActive(true);
            healArrow.anchoredPosition = pos / sf;
            healArrow.localRotation = Quaternion.Euler(0, 0, Mathf.Atan2(dir.y, dir.x) * Mathf.Rad2Deg - 90f);
        }

        static void Animate(Slot s, float dt)
        {
            if (s.pulse > 0)
            {
                s.pulse = Mathf.Max(0, s.pulse - dt * 1.5f);
                s.r.localScale = Vector3.one * (1f + Mathf.Sin(s.pulse * Mathf.PI * 3f) * 0.15f * s.pulse);
            }
        }

        static void SetAlpha(Text t, float a) { var c = t.color; c.a = Mathf.Clamp01(a); t.color = c; }
        static float Back(float t) { const float c1 = 1.70158f, c3 = c1 + 1f; return 1f + c3 * Mathf.Pow(t - 1f, 3) + c1 * Mathf.Pow(t - 1f, 2); }
    }

    /// <summary>Keeps children inside the device safe area (notches).</summary>
    public class SafeArea : MonoBehaviour
    {
        Rect last;
        void Update()
        {
            var sa = Screen.safeArea;
            if (sa == last || Screen.width <= 0 || Screen.height <= 0) return;
            last = sa;
            var r = (RectTransform)transform;
            r.anchorMin = new Vector2(sa.xMin / Screen.width, sa.yMin / Screen.height);
            r.anchorMax = new Vector2(sa.xMax / Screen.width, sa.yMax / Screen.height);
            r.offsetMin = r.offsetMax = Vector2.zero;
        }
    }
}
