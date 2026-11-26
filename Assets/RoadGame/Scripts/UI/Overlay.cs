using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace RoadGame
{
    /// <summary>
    /// World-anchored UI drawn on its own canvas. Only where the action is gets the full HP bar with its number and
    /// reward: the target the weapons are on, the enemies attacking the car and the nearest few things. Other enemies and
    /// damaged things nearby get a thin bar, everything else no label at all; nothing is drawn over the HUD's buttons.
    /// Rewards reeled in within a short spell add up into one line over the car. Also: respawn rings close by, the car's
    /// HP bar, damage numbers (the boosted ones after an upgrade stand out).
    /// </summary>
    public class Overlay : MonoBehaviour
    {
        class Bar
        {
            public bool compact;
            public RectTransform r;
            public Image fill;
            public Text hp;
            public RectTransform reward;
            public Image rewardIcon;
            public Text rewardTxt;
            public string hpStr, rewStr;
            public Icon rewIcon = (Icon)(-1);
        }

        class Timer
        {
            public RectTransform r;
            public Image ring;
            public Text txt;
            public string str;
        }

        class Floater
        {
            public RectTransform r;
            public Text txt;
            public Image icon;
            public Vector3 world;
            public float age, life, rise, popScale;
            public bool active, damage, hurt;
            public float keepIn;     // half width (canvas units) to keep on screen: long lines near the edge
        }

        Canvas canvas;
        RectTransform root;
        readonly List<Bar> bars = new List<Bar>();
        readonly List<Timer> timers = new List<Timer>();
        readonly List<Floater> floaters = new List<Floater>();
        RectTransform playerBar;
        Image playerFill;
        Text playerHp, playerDmg;
        Image playerDmgIcon;
        string playerHpStr, playerDmgStr;
        RectTransform bossMarker;

        // detail levels
        const float CloseRadius = 9f;        // this close to the car: full bar (up to MaxFull, by priority)
        const int MaxFull = 5;
        const float CompactRadius = 24f;     // within this: enemies / damaged things get a thin bar
        readonly HashSet<Target> full = new HashSet<Target>();
        readonly List<Target> nearList = new List<Target>();
        // HUD areas the labels keep out of
        readonly List<Rect> blocked = new List<Rect>();
        readonly Dictionary<RectTransform, Canvas> blockerCanvas = new Dictionary<RectTransform, Canvas>();
        static readonly Vector3[] corners = new Vector3[4];
        // gains reeled in within a short spell, added up into one line over the car
        RectTransform gainRow;
        readonly Image[] gainIcons = new Image[3];
        readonly Text[] gainTxts = new Text[3];
        readonly List<(string key, Reward r, double sum, float at)> gains = new List<(string, Reward, double, float)>();
        float gainLast = -99f, gainPop;
        int damageFloaters;
        public int LabelsFull { get; private set; }
        public int LabelsCompact { get; private set; }
        public int LabelsHiddenByHud { get; private set; }

        public static Overlay Create()
        {
            var c = UI.CreateCanvas("OverlayCanvas", 0);
            var o = c.gameObject.AddComponent<Overlay>();
            o.canvas = c;
            o.root = (RectTransform)c.transform;
            o.BuildPlayerBar();
            o.BuildGainRow();
            return o;
        }

        void BuildGainRow()
        {
            gainRow = UI.Rect("Gains", root);
            gainRow.anchorMin = gainRow.anchorMax = Vector2.zero;
            gainRow.sizeDelta = new Vector2(420, 48);
            for (int i = 0; i < 3; i++)
            {
                gainTxts[i] = UI.Txt(gainRow, "G" + i, "", 36, Color.white, TextAnchor.MiddleRight, 2.5f);
                UI.Place(gainTxts[i].rectTransform, new Vector2(0.5f, 0.5f), new Vector2(-140 + i * 140 + 10, 0), new Vector2(110, 48), new Vector2(1f, 0.5f));
                gainIcons[i] = UI.IconImg(gainRow, Icon.Heart, 40);
                UI.Place(gainIcons[i].rectTransform, new Vector2(0.5f, 0.5f), new Vector2(-140 + i * 140 + 14, 0), new Vector2(40, 40), new Vector2(0f, 0.5f));
            }
            gainRow.gameObject.SetActive(false);
        }

        static string GainKey(Reward r) => r.kind + ":" + r.dmgType + ":" + r.itemId;

        /// <summary>A reeled-in reward: joins the running total of its kind (up to three kinds) shown over the car.</summary>
        public void QueueGain(Reward r)
        {
            string key = GainKey(r);
            float now = Time.time;
            if (now - gainLast > 1.6f) gains.Clear();
            int i = gains.FindIndex(x => x.key == key);
            if (i >= 0) gains[i] = (key, r, gains[i].sum + r.amount, now);
            else
            {
                if (gains.Count >= 3) gains.RemoveAt(0);
                gains.Add((key, r, r.amount, now));
            }
            gainLast = now;
            gainPop = 1f;
            for (int k = 0; k < 3; k++)
            {
                bool on = k < gains.Count;
                gainTxts[k].enabled = on; gainIcons[k].enabled = on;
                if (!on) continue;
                var g = gains[k];
                bool count = g.r.kind == RewardKind.WeaponCopy || g.r.kind == RewardKind.ArmorCopy;
                gainTxts[k].text = "+" + (count ? ((int)g.sum).ToString() : Fmt.Num(g.sum));
                gainTxts[k].color = Tex.RewardColor(g.r);
                gainIcons[k].sprite = Tex.Get(Tex.RewardIcon(g.r));
            }
            // centre the used entries
            float w = gains.Count * 140f;
            for (int k = 0; k < gains.Count; k++)
            {
                float x = -w * 0.5f + k * 140f;
                gainTxts[k].rectTransform.anchoredPosition = new Vector2(x + 96f, 0f);
                gainIcons[k].rectTransform.anchoredPosition = new Vector2(x + 100f, 0f);
            }
            gainRow.gameObject.SetActive(true);
        }

        void BuildPlayerBar()
        {
            playerBar = UI.Rect("PlayerBar", root);
            playerBar.anchorMin = playerBar.anchorMax = Vector2.zero;
            playerBar.sizeDelta = new Vector2(150, 36);
            playerFill = UI.Bar(playerBar, "Bar", new Color(0.36f, 0.88f, 0.32f), out var br);
            UI.Stretch(br);
            playerHp = UI.Txt(playerBar, "Hp", "100", 30, Color.white, TextAnchor.MiddleCenter, 2.5f);
            UI.Stretch(playerHp.rectTransform, 0, 2, 0, 0);
            var dmg = UI.Rect("Dmg", playerBar);
            UI.Place(dmg, new Vector2(1, 0.5f), new Vector2(12, 0), new Vector2(120, 40), new Vector2(0, 0.5f));
            playerDmgIcon = UI.IconImg(dmg, Icon.Gun, 40);
            UI.Place(playerDmgIcon.rectTransform, new Vector2(0, 0.5f), Vector2.zero, new Vector2(40, 40), new Vector2(0, 0.5f));
            playerDmg = UI.Txt(dmg, "DmgTxt", "5.5", 30, Color.white, TextAnchor.MiddleLeft, 2.5f);
            UI.Place(playerDmg.rectTransform, new Vector2(0, 0.5f), new Vector2(44, 0), new Vector2(100, 40), new Vector2(0, 0.5f));
        }

        Bar GetBar(int i)
        {
            while (bars.Count <= i)
            {
                var b = new Bar();
                b.r = UI.Rect("TBar", root);
                b.r.anchorMin = b.r.anchorMax = Vector2.zero;
                b.r.sizeDelta = new Vector2(128, 30);
                b.fill = UI.Bar(b.r, "Bar", new Color(0.95f, 0.27f, 0.3f), out var br, 12);
                UI.Stretch(br);
                b.hp = UI.Txt(b.r, "Hp", "", 25, Color.white, TextAnchor.MiddleCenter, 2f);
                UI.Stretch(b.hp.rectTransform, 0, 2, 0, 0);
                b.reward = UI.Rect("Reward", b.r);
                UI.Place(b.reward, new Vector2(0.5f, 1f), new Vector2(0, 4), new Vector2(150, 40), new Vector2(0.5f, 0f));
                b.rewardTxt = UI.Txt(b.reward, "Txt", "", 29, Color.white, TextAnchor.MiddleRight, 2.5f);
                UI.Place(b.rewardTxt.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(4, 0), new Vector2(100, 40), new Vector2(1f, 0.5f));
                b.rewardIcon = UI.IconImg(b.reward, Icon.Heart, 38);
                UI.Place(b.rewardIcon.rectTransform, new Vector2(0.5f, 0.5f), new Vector2(8, 0), new Vector2(38, 38), new Vector2(0f, 0.5f));
                bars.Add(b);
            }
            return bars[i];
        }

        Timer GetTimer(int i)
        {
            while (timers.Count <= i)
            {
                var t = new Timer();
                t.r = UI.Rect("Timer", root);
                t.r.anchorMin = t.r.anchorMax = Vector2.zero;
                t.r.sizeDelta = new Vector2(70, 70);
                var bg = UI.Img(t.r, "Bg", Tex.Circle(), new Color(0.08f, 0.08f, 0.08f, 0.55f));
                UI.Stretch(bg.rectTransform, 6, 6, 6, 6);
                var back = UI.Img(t.r, "Back", Tex.Ring(0.22f), new Color(0, 0, 0, 0.45f));
                UI.Stretch(back.rectTransform);
                t.ring = UI.Img(t.r, "Ring", Tex.Ring(0.22f), new Color(0.4f, 0.95f, 0.45f));
                UI.Stretch(t.ring.rectTransform);
                t.ring.type = Image.Type.Filled;
                t.ring.fillMethod = Image.FillMethod.Radial360;
                t.ring.fillOrigin = (int)Image.Origin360.Top;
                t.ring.fillClockwise = true;
                t.txt = UI.Txt(t.r, "Time", "", 26, Color.white, TextAnchor.LowerCenter, 2f);
                UI.Place(t.txt.rectTransform, new Vector2(0.5f, 1f), new Vector2(0, 2), new Vector2(160, 34), new Vector2(0.5f, 0f));
                timers.Add(t);
            }
            return timers[i];
        }

        Floater GetFloater()
        {
            foreach (var f in floaters)
                if (!f.active)
                {
                    f.damage = false; f.hurt = false; f.keepIn = 0f;
                    if (f.txt.font != UI.font) f.txt.font = UI.font;   // a Russian line used it last
                    return f;
                }
            var n = new Floater();
            n.r = UI.Rect("Float", root);
            n.r.anchorMin = n.r.anchorMax = Vector2.zero;
            n.r.sizeDelta = new Vector2(200, 50);
            n.txt = UI.Txt(n.r, "Txt", "", 34, Color.white, TextAnchor.MiddleCenter, 2.5f);
            UI.Stretch(n.txt.rectTransform);
            n.icon = UI.IconImg(n.r, Icon.Heart, 40);
            n.icon.rectTransform.anchorMin = n.icon.rectTransform.anchorMax = new Vector2(0.5f, 0.5f);
            floaters.Add(n);
            return n;
        }

        // ---------------------------------------------------------------- public API
        public void DamageNumber(Vector3 world, double dmg, bool crit, bool boosted = false)
        {
            // a dense fight: ordinary numbers give way once there are many in the air (crits and boosted ones stay)
            if (damageFloaters >= 7 && !crit && !boosted) return;
            var f = GetFloater();
            f.world = world + new Vector3(Random.Range(-0.5f, 0.5f), 0, Random.Range(-0.2f, 0.2f));
            f.txt.text = Fmt.Num(dmg) + (crit ? "!" : "");
            f.txt.fontSize = boosted ? 48 : (crit ? 46 : 34);
            f.txt.color = boosted ? new Color(0.45f, 1f, 0.45f) : (crit ? new Color(1f, 0.82f, 0.2f) : Color.white);
            f.icon.enabled = false;
            f.damage = true;
            Begin(f, boosted ? 1.0f : 0.75f, 1.6f, crit || boosted ? 1.9f : 1.4f);
        }

        /// <summary>
        /// Damage the car takes: blows within 0.7 s add up into one red number beside the car (a crowd hitting it
        /// shows "-12" once, not a stack of "-3"s over its own HP bar).
        /// </summary>
        public void PlayerDamage(Vector3 world, double dmg)
        {
            if (hurtFloater != null && hurtFloater.active && hurtFloater.hurt && hurtFloater.age < 1.2f)
            {
                hurtSum += dmg;
                hurtFloater.txt.text = "-" + Fmt.Num(hurtSum);
                hurtFloater.life = Mathf.Max(hurtFloater.life, hurtFloater.age + 0.7f);
                return;
            }
            var f = GetFloater();
            f.hurt = true;
            hurtFloater = f; hurtSum = dmg;
            f.world = world + new Vector3(-2.2f, -0.6f, -0.4f);
            f.txt.text = "-" + Fmt.Num(dmg);
            f.txt.fontSize = 38;
            f.txt.color = new Color(1f, 0.25f, 0.25f);
            f.icon.enabled = false;
            Begin(f, 0.9f, 1.0f, 1.5f);
        }

        Floater hurtFloater;
        double hurtSum;

        /// <summary>A short line over a spot in the world (the new weapon's demo): pops, rises, fades.</summary>
        public void WorldText(Vector3 world, string text, Color color, int size)
        {
            var f = GetFloater();
            f.world = world;
            UI.SetText(f.txt, text);
            f.txt.fontSize = size;
            f.txt.color = color;
            f.icon.enabled = false;
            f.keepIn = text.Length * size * 0.31f + 12f;
            Begin(f, 1.8f, 1.2f, 1.8f);
        }

        public void RewardPop(Vector3 world, Reward r)
        {
            var f = GetFloater();
            f.world = world + new Vector3(Random.Range(-0.4f, 0.4f), 0, 0);
            string s = r.kind == RewardKind.WeaponCopy || r.kind == RewardKind.ArmorCopy ? "+" + (int)r.amount : "+" + Fmt.Num(r.amount);
            f.txt.text = s;
            f.txt.fontSize = 40;
            f.txt.color = Tex.RewardColor(r);
            f.txt.alignment = TextAnchor.MiddleRight;
            f.icon.enabled = true;
            f.icon.sprite = Tex.Get(Tex.RewardIcon(r));
            f.icon.rectTransform.anchoredPosition = new Vector2(24, 0);
            f.icon.rectTransform.sizeDelta = new Vector2(44, 44);
            f.txt.rectTransform.offsetMax = new Vector2(-104, 0);
            Begin(f, 1.1f, 2.4f, 1.6f);
        }

        public void Alert(Vector3 world)
        {
            var f = GetFloater();
            f.world = world;
            f.txt.text = "!";
            f.txt.fontSize = 54;
            f.txt.color = new Color(1f, 0.3f, 0.2f);
            f.icon.enabled = false;
            Begin(f, 0.6f, 0.4f, 1.8f);
        }

        public void ShowText(Vector3 world, string s, Color c, int size = 40)
        {
            var f = GetFloater();
            f.world = world;
            f.txt.text = s;
            f.txt.fontSize = size;
            f.txt.color = c;
            f.icon.enabled = false;
            Begin(f, 1.2f, 1.5f, 1.4f);
        }

        void Begin(Floater f, float life, float rise, float pop)
        {
            f.age = 0; f.life = life; f.rise = rise; f.popScale = pop; f.active = true;
            if (!f.icon.enabled)
            {
                f.txt.alignment = TextAnchor.MiddleCenter;
                f.txt.rectTransform.offsetMax = Vector2.zero;
            }
            f.r.gameObject.SetActive(true);
            f.r.SetAsLastSibling();
        }

        // ---------------------------------------------------------------- per frame
        void LateUpdate()
        {
            var g = Game.I;
            if (g == null || g.cam == null || g.player == null || World.I == null) return;
            var cam = g.cam;
            float sf = canvas.scaleFactor;
            var ppos = g.player.Pos;
            int used = 0;
            float sw = cam.pixelWidth, sh = cam.pixelHeight;

            CollectBlockers(g);
            PickFull(g, ppos);
            nFull = nCompact = nHidden = nDown = 0;
            // labels never cover the car's own bar (and the gains line over it) or each other: the most important first
            placed.Clear();
            if (g.player.Alive)
            {
                var psp = cam.WorldToScreenPoint(ppos + Vector3.up * 2.6f + Vector3.forward * 2.4f);
                float top = gainRow.gameObject.activeSelf ? 92f : 22f;
                placed.Add(Rect.MinMaxRect(psp.x - 80f * sf, psp.y - 22f * sf, psp.x + 210f * sf, psp.y + top * sf));
            }
            var list = World.I.activeTargets;
            engagedBoss = g.EngagedBoss;
            for (int i = 0; i < list.Count; i++) { var t = list[i]; if (t != null && t.IsBoss && t != engagedBoss) Label(t, true, ref used); }
            for (int k = 0; k < fullOrder.Count; k++) Label(fullOrder[k], true, ref used);
            for (int i = 0; i < list.Count; i++) { var t = list[i]; if (t != null && !t.IsBoss && !full.Contains(t)) Label(t, false, ref used); }
            for (int i = used; i < bars.Count; i++) if (bars[i].r.gameObject.activeSelf) bars[i].r.gameObject.SetActive(false);
            LabelsFull = nFull; LabelsCompact = nCompact; LabelsHiddenByHud = nHidden;
            LabelsDowngraded = nDown;

            // respawn timers (destroyed spots close by: a ring, the time only on the nearest few)
            int tu = 0;
            long now = Progress.NowMs;
            int pz = Content.ZoneIndexAt(ppos.z);
            for (int zi = Mathf.Max(0, pz - 1); zi <= Mathf.Min(Content.ZoneCount - 1, pz + 1); zi++)
            {
                var sps = World.I.zoneSpawns[zi];
                for (int i = 0; i < sps.Count; i++)
                {
                    var s = sps[i];
                    if (!s.IsDead(now) || s.spec.oneTime) continue;
                    if (s.target != null && s.target.gameObject.activeSelf) continue; // wreck still there
                    var off = s.pos - ppos;
                    if (Mathf.Abs(off.y) > Ground.LevelGap) continue;
                    off.y = 0;
                    if (off.sqrMagnitude > 16f * 16f) continue;
                    var sp = cam.WorldToScreenPoint(s.pos + Vector3.up * 0.6f);
                    if (sp.z < 0 || sp.x < -60 || sp.x > sw + 60 || sp.y < -60 || sp.y > sh + 60) continue;
                    var timerRect = new Rect(sp.x - 35f * sf, sp.y - 35f * sf, 70f * sf, 104f * sf);
                    if (HitsHud(timerRect) || Overlaps(timerRect)) continue;
                    var tm = GetTimer(tu++);
                    if (!tm.r.gameObject.activeSelf) tm.r.gameObject.SetActive(true);
                    tm.r.anchoredPosition = new Vector2(sp.x, sp.y) / sf;
                    tm.ring.fillAmount = s.Progress01(now);
                    var str = off.sqrMagnitude < 8f * 8f ? Fmt.Time(s.Remaining(now)) : "";
                    if (str != tm.str) { tm.str = str; tm.txt.text = str; }
                }
            }
            for (int i = tu; i < timers.Count; i++) if (timers[i].r.gameObject.activeSelf) timers[i].r.gameObject.SetActive(false);

            // player bar
            var pl = g.player;
            playerBar.gameObject.SetActive(pl.Alive);
            if (pl.Alive)
            {
                var psp = cam.WorldToScreenPoint(ppos + Vector3.up * 2.6f + Vector3.forward * 2.4f);
                playerBar.anchoredPosition = new Vector2(psp.x, psp.y) / sf;
                var d = g.progress.d;
                UI.SetBar(playerFill, (float)(d.hp / d.maxHp));
                var hs = Fmt.Num(d.hp);
                if (hs != playerHpStr) { playerHpStr = hs; playerHp.text = hs; }
                var ds = Fmt.Num(g.progress.DisplayDamage());
                if (ds != playerDmgStr) { playerDmgStr = ds; playerDmg.text = ds; }
            }

            // the gains line over the car: pops on every new reward, fades 1.4 s after the last one
            if (gainRow.gameObject.activeSelf)
            {
                float since = Time.time - gainLast;
                if (since > 1.9f || !pl.Alive) { gainRow.gameObject.SetActive(false); gains.Clear(); }
                else
                {
                    var gsp = cam.WorldToScreenPoint(ppos + Vector3.up * 2.6f + Vector3.forward * 2.4f);
                    gainRow.anchoredPosition = new Vector2(gsp.x, gsp.y) / sf + new Vector2(0f, 52f);
                    gainPop = Mathf.MoveTowards(gainPop, 0f, Time.deltaTime * 5f);
                    gainRow.localScale = Vector3.one * (1f + gainPop * 0.18f);
                    float a = since > 1.4f ? 1f - (since - 1.4f) / 0.5f : 1f;
                    for (int k = 0; k < 3; k++)
                    {
                        var c = gainTxts[k].color; c.a = a; gainTxts[k].color = c;
                        gainIcons[k].color = new Color(1, 1, 1, a);
                    }
                }
            }

            // floaters
            float dt = Time.deltaTime;
            damageFloaters = 0;
            foreach (var f in floaters)
            {
                if (!f.active) continue;
                if (f.damage) damageFloaters++;
                f.age += dt;
                if (f.age >= f.life) { f.active = false; f.r.gameObject.SetActive(false); continue; }
                float k = f.age / f.life;
                var w = f.world + Vector3.up * (f.rise * Mathf.Sqrt(k) * 1.6f + 1.4f);
                var sp = cam.WorldToScreenPoint(w);
                var fp = new Vector2(sp.x, sp.y) / sf;
                if (f.keepIn > 0f)
                {
                    float cw = root.rect.width;
                    fp.x = cw > 2f * f.keepIn ? Mathf.Clamp(fp.x, f.keepIn, cw - f.keepIn) : cw * 0.5f;
                }
                f.r.anchoredPosition = fp;
                float pop = k < 0.12f ? Mathf.Lerp(f.popScale, 1f, k / 0.12f) : 1f;
                f.r.localScale = Vector3.one * pop;
                float a = k > 0.7f ? 1f - (k - 0.7f) / 0.3f : 1f;
                var c = f.txt.color; c.a = a; f.txt.color = c;
                if (f.icon.enabled) f.icon.color = new Color(1, 1, 1, a);
            }
        }

        int nFull, nCompact, nHidden, nDown;
        Target engagedBoss;
        readonly List<Rect> placed = new List<Rect>(24);
        readonly List<Target> fullOrder = new List<Target>(8);
        public int LabelsDowngraded { get; private set; }

        /// <summary>
        /// One target's label. Full = HP bar with its number and the reward over it; compact = a thin bar only (other
        /// enemies and damaged things nearby). A full label that would cover one already placed (or the car's bar) drops
        /// to a thin bar; a thin bar that would cover a full one is left out.
        /// </summary>
        void Label(Target t, bool wantFull, ref int used)
        {
            var g = Game.I; var cam = g.cam; float sf = canvas.scaleFactor;
            var ppos = g.player.Pos;
            if (t == null || !t.Targetable) return;
            var off = t.Pos - ppos;
            if (Mathf.Abs(off.y) > Ground.LevelGap) return;   // another level (under / over the car): no bar
            off.y = 0;
            float dist = off.magnitude;
            if (dist > 38f) return;
            bool damaged = t.hp < t.maxHp - 1e-6;
            if (!wantFull && !(dist < CompactRadius && (t.IsEnemy || damaged))) return;   // far / untouched: the scene speaks for itself
            // underground, walls and roofs hide what is behind them (the boss in its hangar seen from the tunnel)
            if ((t.Pos.y < -1.5f || ppos.y < -1.5f) && !World.InSight(ppos, t)) return;
            var sp = cam.WorldToScreenPoint(t.Pos + Vector3.up * (t.BarHeight + 0.35f));
            float sw = cam.pixelWidth, sh = cam.pixelHeight;
            if (sp.z < 0 || sp.x < -80 || sp.x > sw + 80 || sp.y < -80 || sp.y > sh + 60) return;
            float scale = t.IsBoss ? 1.6f : 1f;
            var fullRect = new Rect(sp.x - 75f * sf * scale, sp.y - 15f * sf * scale, 150f * sf * scale, (t.IsBoss ? 30f : 74f) * sf * scale);
            var thinRect = new Rect(sp.x - 48f * sf, sp.y - 6f * sf, 96f * sf, 12f * sf);
            bool compact = !wantFull;
            float lift = 0f;
            if (wantFull && !t.IsBoss && Overlaps(fullRect))
            {
                // lift it over the crowd (the car's bar, other labels) one or two steps; else a thin bar
                compact = true;
                for (int step = 1; step <= 2; step++)
                {
                    var up = fullRect; up.y += step * 40f * sf;
                    if (!Overlaps(up)) { fullRect = up; lift = step * 40f; compact = false; break; }
                }
                if (compact) nDown++;
            }
            var lr = compact ? thinRect : fullRect;
            // keep clear of the HUD's buttons, minimap, widget and slot bar
            if (HitsHud(lr)) { nHidden++; return; }
            if (compact && Overlaps(thinRect)) return;
            if (!compact) placed.Add(fullRect);
            var b = GetBar(used++);
            if (!b.r.gameObject.activeSelf) b.r.gameObject.SetActive(true);
            b.r.anchoredPosition = new Vector2(sp.x, sp.y) / sf + new Vector2(0f, lift);
            b.r.localScale = Vector3.one * scale;
            if (b.compact != compact)
            {
                b.compact = compact;
                b.r.sizeDelta = compact ? new Vector2(96, 12) : new Vector2(128, 30);
                b.hp.enabled = !compact;
            }
            UI.SetBar(b.fill, (float)(t.hp / t.maxHp));
            if (compact) { nCompact++; if (b.reward.gameObject.activeSelf) b.reward.gameObject.SetActive(false); return; }
            nFull++;
            string hs = Fmt.Num(System.Math.Max(0, t.hp));
            if (hs != b.hpStr) { b.hpStr = hs; b.hp.text = hs; }
            var r = t.spawn.RewardNow;
            if (t.IsBoss) { b.reward.gameObject.SetActive(false); return; }
            if (!b.reward.gameObject.activeSelf) b.reward.gameObject.SetActive(true);
            string rs = (r.kind == RewardKind.WeaponCopy || r.kind == RewardKind.ArmorCopy) ? "+" + (int)r.amount : "+" + Fmt.Num(r.amount);
            if (rs != b.rewStr) { b.rewStr = rs; b.rewardTxt.text = rs; }
            var ic = Tex.RewardIcon(r);
            if (ic != b.rewIcon) { b.rewIcon = ic; b.rewardIcon.sprite = Tex.Get(ic); b.rewardTxt.color = Color.white; }
        }

        bool Overlaps(Rect r)
        {
            for (int i = 0; i < placed.Count; i++) if (placed[i].Overlaps(r)) return true;
            return false;
        }

        /// <summary>Screen rects of the HUD elements shown this frame (labels keep out of them, with a small margin).</summary>
        void CollectBlockers(Game g)
        {
            blocked.Clear();
            if (g.hud == null) return;
            foreach (var r in g.hud.Blockers)
            {
                if (r == null || !r.gameObject.activeInHierarchy) continue;
                if (!blockerCanvas.TryGetValue(r, out var c) || c == null) { c = r.GetComponentInParent<Canvas>()?.rootCanvas; blockerCanvas[r] = c; }
                if (c == null) continue;
                Camera ccam = c.renderMode == RenderMode.ScreenSpaceOverlay ? null : c.worldCamera;
                r.GetWorldCorners(corners);
                Vector2 a = RectTransformUtility.WorldToScreenPoint(ccam, corners[0]), b = RectTransformUtility.WorldToScreenPoint(ccam, corners[2]);
                var rr = Rect.MinMaxRect(Mathf.Min(a.x, b.x) - 6f, Mathf.Min(a.y, b.y) - 6f, Mathf.Max(a.x, b.x) + 6f, Mathf.Max(a.y, b.y) + 6f);
                blocked.Add(rr);
            }
        }

        bool HitsHud(Rect r)
        {
            for (int i = 0; i < blocked.Count; i++) if (blocked[i].Overlaps(r)) return true;
            return false;
        }

        /// <summary>
        /// The few things that get the full bar: what the weapons are on, the enemies attacking the car (nearest
        /// first), then the nearest things within CloseRadius.
        /// </summary>
        // attacking enemies first, then the nearest (a cached delegate: no allocation per frame)
        static Vector3 sortFrom;
        static System.Comparison<Target> byPriority;
        static int ByPriority(Target a, Target b)
        {
            bool ea = a is Enemy x && x.Engaged, eb = b is Enemy y && y.Engaged;
            if (ea != eb) return ea ? -1 : 1;
            float da = (a.Pos - sortFrom).sqrMagnitude, db = (b.Pos - sortFrom).sqrMagnitude;
            return da.CompareTo(db);
        }

        void PickFull(Game g, Vector3 ppos)
        {
            full.Clear(); fullOrder.Clear();
            var pl = g.player;
            if (pl.turret != null && pl.turret.CurrentTarget != null && full.Add(pl.turret.CurrentTarget)) fullOrder.Add(pl.turret.CurrentTarget);
            if (g.focusTarget != null && full.Add(g.focusTarget)) fullOrder.Add(g.focusTarget);
            nearList.Clear();
            var list = World.I.activeTargets;
            for (int i = 0; i < list.Count; i++)
            {
                var t = list[i];
                if (t == null || !t.Targetable || t.IsBoss) continue;
                var off = t.Pos - ppos; off.y = 0f;
                if (Mathf.Abs(t.Pos.y - ppos.y) > Ground.LevelGap) continue;
                bool attacking = t is Enemy e && e.Engaged;
                if (attacking || off.sqrMagnitude < CloseRadius * CloseRadius) nearList.Add(t);
            }
            sortFrom = ppos;
            nearList.Sort(byPriority ??= ByPriority);
            for (int i = 0; i < nearList.Count && full.Count < MaxFull; i++) if (full.Add(nearList[i])) fullOrder.Add(nearList[i]);
        }

        public void SetPlayerDamageIcon(DamageType t)
        {
            playerDmgIcon.sprite = Tex.Get(Tex.DamageIcon(t));
        }
    }
}
