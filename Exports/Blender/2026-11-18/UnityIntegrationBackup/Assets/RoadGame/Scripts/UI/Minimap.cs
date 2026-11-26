using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace RoadGame
{
    /// <summary>Round "glass" minimap in the top-right corner: painted map texture + live markers (like the reference).</summary>
    public class Minimap : MonoBehaviour
    {
        const float XMin = -112f, XMax = 112f;
        static float ZMin => World.SouthLimit - 2f;   // includes the intro canyon south of the first zone
        static float ZMax => Content.ZoneMaxZ(Content.ZoneCount - 1) + 8f;
        const float PxPerM = 2f;

        RectTransform root, mapR;
        RawImage map;
        Texture2D tex;
        Image playerArrow;
        readonly List<Image> dots = new List<Image>();
        readonly List<Image> icons = new List<Image>();
        readonly List<Image> routeDots = new List<Image>();
        float view = 120f;
        bool zoomed;
        int paintedUnlock = -1;
        float size;

        public static Minimap Create(Transform parent, float size)
        {
            var r = UI.Rect("Minimap", parent);
            var m = r.gameObject.AddComponent<Minimap>();
            m.root = r;
            m.size = size;
            r.sizeDelta = new Vector2(size, size);
            var border = UI.Img(r, "Border", Tex.Circle(), UI.Dark);
            UI.Stretch(border.rectTransform, -6, -6, -6, -6);
            var maskImg = UI.Img(r, "Mask", Tex.Circle(), Color.white);
            UI.Stretch(maskImg.rectTransform);
            var mask = maskImg.gameObject.AddComponent<Mask>();
            mask.showMaskGraphic = true;
            maskImg.color = new Color(0.2f, 0.18f, 0.16f, 1f);
            var mapGo = UI.Rect("Map", maskImg.transform);
            UI.Stretch(mapGo);
            m.map = mapGo.gameObject.AddComponent<RawImage>();
            m.map.raycastTarget = false;
            m.mapR = mapGo;
            var markers = UI.Rect("Markers", maskImg.transform);
            UI.Stretch(markers);
            m.playerArrow = UI.IconImg(markers, Icon.Arrow, size * 0.16f);
            m.playerArrow.rectTransform.anchorMin = m.playerArrow.rectTransform.anchorMax = new Vector2(0.5f, 0.5f);
            // glass highlight
            var glass = UI.Img(r, "Glass", Tex.Circle(), new Color(1, 1, 1, 0.10f));
            UI.Stretch(glass.rectTransform, size * 0.1f, size * 0.45f, size * 0.25f, size * 0.06f);
            var rim = UI.Img(r, "Rim", Tex.Ring(0.06f), new Color(1, 1, 1, 0.55f));
            UI.Stretch(rim.rectTransform, 2, 2, 2, 2);
            m.Paint();
            return m;
        }

        public void ToggleZoom()
        {
            zoomed = !zoomed;
            view = zoomed ? 260f : 120f;
        }

        void Paint()
        {
            int unlocked = Game.I.progress.d.unlockedZone;
            paintedUnlock = unlocked;
            int w = Mathf.CeilToInt((XMax - XMin) * PxPerM), h = Mathf.CeilToInt((ZMax - ZMin) * PxPerM);
            if (tex == null)
            {
                tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
                tex.wrapMode = TextureWrapMode.Clamp;
                tex.filterMode = FilterMode.Bilinear;
            }
            var px = new Color32[w * h];
            for (int y = 0; y < h; y++)
            {
                float wz = ZMin + y / PxPerM;
                int zi = Content.ZoneIndexAt(wz);
                var zc = Content.Zones[zi].minimap;
                bool locked = zi > unlocked;
                for (int x = 0; x < w; x++)
                {
                    float wx = XMin + x / PxPerM;
                    float n = Mathf.PerlinNoise(wx * 0.05f, wz * 0.05f) * 0.12f - 0.06f;
                    var c = new Color(zc.r + n, zc.g + n, zc.b + n, 1f);
                    if (Mathf.Abs(wx) > Content.ZoneHalfWidth) c = Color.Lerp(c, Content.Zones[zi].cliffDark, 0.75f);
                    // the intro canyon: only its road between the rock walls is open ground
                    if (wz < Content.ZoneMinZ(0) - 4f && Mathf.Abs(wx) > 9f) c = Color.Lerp(c, Content.Zones[0].cliffDark, 0.75f);
                    if (locked) c = Color.Lerp(c, new Color(0.15f, 0.13f, 0.12f), 0.55f);
                    px[y * w + x] = c;
                }
            }
            void Stamp(Vector3 p, float radiusM, Color c)
            {
                int cx = Mathf.RoundToInt((p.x - XMin) * PxPerM), cy = Mathf.RoundToInt((p.z - ZMin) * PxPerM);
                int rp = Mathf.CeilToInt(radiusM * PxPerM);
                for (int dy = -rp; dy <= rp; dy++)
                    for (int dx = -rp; dx <= rp; dx++)
                    {
                        if (dx * dx + dy * dy > rp * rp) continue;
                        int X = cx + dx, Y = cy + dy;
                        if (X < 0 || Y < 0 || X >= w || Y >= h) continue;
                        px[Y * w + X] = c;
                    }
            }
            var world = World.I;
            for (int zi = 0; zi < Content.ZoneCount; zi++)
            {
                bool locked = zi > unlocked;
                var roadC = locked ? new Color(0.3f, 0.27f, 0.25f) : new Color(0.45f, 0.38f, 0.33f);
                for (int r = 0; r < world.roads[zi].Count; r++)
                {
                    var road = world.roads[zi][r];
                    float rw = world.roadWidths[zi][r] * 0.5f;
                    foreach (var p in road) Stamp(p, rw, roadC);
                }
                foreach (var c in world.camps[zi]) Stamp(c, 7f, locked ? new Color(0.25f, 0.22f, 0.2f) : new Color(0.62f, 0.45f, 0.32f));
            }
            // hand-placed structures: buildings and rock dark, ramps yellow, underground routes as dashed paving
            foreach (var mk in Structures.Marks)
            {
                var bb = mk.r.Aabb;
                int x0 = Mathf.Max(0, Mathf.FloorToInt((bb.x - XMin) * PxPerM)), x1 = Mathf.Min(w - 1, Mathf.CeilToInt((bb.z - XMin) * PxPerM));
                int y0 = Mathf.Max(0, Mathf.FloorToInt((bb.y - ZMin) * PxPerM)), y1 = Mathf.Min(h - 1, Mathf.CeilToInt((bb.w - ZMin) * PxPerM));
                int zone = Content.ZoneIndexAt(mk.r.c.y);
                var col = zone > unlocked ? Color.Lerp(mk.c, new Color(0.15f, 0.13f, 0.12f), 0.55f) : mk.c;
                for (int Y = y0; Y <= y1; Y++)
                    for (int X = x0; X <= x1; X++)
                    {
                        float wx = XMin + X / PxPerM, wz = ZMin + Y / PxPerM;
                        if (!mk.r.Contains(wx, wz)) continue;
                        if (mk.underground && ((X / 3 + Y / 3) % 2 == 0)) continue;   // dashed: it runs under the ground
                        px[Y * w + X] = col;
                    }
            }
            // zone border walls (with gates)
            for (int b = 1; b < Content.ZoneCount; b++)
            {
                float zb = Content.ZoneMinZ(b);
                for (float x = XMin; x <= XMax; x += 1f)
                {
                    if (Mathf.Abs(x - World.GateX[b]) < 5f) continue;
                    Stamp(new Vector3(x, 0, zb), 2.2f, new Color(0.18f, 0.14f, 0.12f));
                }
            }
            tex.SetPixels32(px);
            tex.Apply(false, false);
            map.texture = tex;
        }

        Image Dot(int i)
        {
            while (dots.Count <= i)
            {
                var d = UI.Img(playerArrow.transform.parent, "Dot", Tex.Get(Icon.EnemyDot), Color.white);
                d.rectTransform.anchorMin = d.rectTransform.anchorMax = new Vector2(0.5f, 0.5f);
                d.rectTransform.sizeDelta = new Vector2(20, 20);
                d.transform.SetSiblingIndex(0);
                dots.Add(d);
            }
            return dots[i];
        }

        Image RouteDot(int i)
        {
            while (routeDots.Count <= i)
            {
                var d = UI.Img(playerArrow.transform.parent, "Route", Tex.Circle(), new Color(1f, 0.82f, 0.25f, 0.95f));
                d.rectTransform.anchorMin = d.rectTransform.anchorMax = new Vector2(0.5f, 0.5f);
                d.rectTransform.sizeDelta = new Vector2(11, 11);
                d.raycastTarget = false;
                d.transform.SetSiblingIndex(0);
                routeDots.Add(d);
            }
            return routeDots[i];
        }

        /// <summary>The way to the current goal: dots every few metres ahead of the car along the goal's route.</summary>
        void DrawRoute(Vector3 p, float scale)
        {
            int n = 0;
            var pts = Goals.ActiveRoute;
            var goal = Game.I.hud != null ? Game.I.hud.Goal : null;
            if (pts != null && pts.Count > 1 && goal != null && goal.hasTarget)
            {
                int seg = Goals.ClosestSegment(pts, p, out float segT, out _);
                var cur = pts[seg] + (pts[seg + 1] - pts[seg]) * segT;
                float half = view * 0.5f * 0.92f, step = view / 14f, carry = step * 0.5f;
                for (int i = seg; i < pts.Count - 1 && n < 60; i++)
                {
                    var next = pts[i + 1];
                    var s = next - cur; s.y = 0f;
                    float len = s.magnitude;
                    while (carry <= len && n < 60)
                    {
                        var q = cur + s * (carry / Mathf.Max(1e-4f, len));
                        var off = q - p;
                        if (Mathf.Abs(off.x) > half || Mathf.Abs(off.z) > half) { i = pts.Count; break; }
                        var d = RouteDot(n++);
                        d.enabled = true;
                        d.rectTransform.anchoredPosition = new Vector2(off.x, off.z) * scale;
                        carry += step;
                    }
                    carry -= len;
                    cur = next;
                }
            }
            for (int i = n; i < routeDots.Count; i++) routeDots[i].enabled = false;
        }

        Image IconAt(int i)
        {
            while (icons.Count <= i)
            {
                var d = UI.IconImg(playerArrow.transform.parent, Icon.Plus, 34);
                d.rectTransform.anchorMin = d.rectTransform.anchorMax = new Vector2(0.5f, 0.5f);
                icons.Add(d);
            }
            return icons[i];
        }

        void LateUpdate()
        {
            var g = Game.I;
            if (g == null || g.player == null || World.I == null) return;
            if (paintedUnlock != g.progress.d.unlockedZone) Paint();
            var p = g.player.Pos;
            float W = XMax - XMin, H = ZMax - ZMin;
            float u = (p.x - XMin) / W, v = (p.z - ZMin) / H;
            float uw = view / W, vh = view / H;
            map.uvRect = new Rect(u - uw * 0.5f, v - vh * 0.5f, uw, vh);
            playerArrow.rectTransform.localRotation = Quaternion.Euler(0, 0, -g.player.Heading);
            float scale = size / view; // ui px per meter

            int di = 0;
            foreach (var t in World.I.activeTargets)
            {
                if (t == null || !t.Targetable || !t.IsEnemy || t.IsBoss) continue;
                var off = t.Pos - p;
                if (Mathf.Abs(off.x) > view * 0.5f || Mathf.Abs(off.z) > view * 0.5f) continue;
                var d = Dot(di++);
                d.enabled = true;
                d.rectTransform.anchoredPosition = new Vector2(off.x, off.z) * scale;
            }
            for (int i = di; i < dots.Count; i++) dots[i].enabled = false;
            DrawRoute(p, scale);

            int ii = 0;
            foreach (var st in World.I.stations)
            {
                if (st.zone > g.progress.d.unlockedZone) continue;
                PlaceIcon(ii++, Icon.Plus, st.pos - p, scale, 30);
            }
            for (int zi = 0; zi < Content.ZoneCount; zi++)
            {
                var b = World.I.bossSpawns[zi];
                if (b == null || zi > g.progress.d.unlockedZone) continue;
                bool dead = b.IsDead(Progress.NowMs);
                PlaceIcon(ii++, Icon.Skull, b.pos - p, scale, dead ? 26 : 36, dead ? new Color(1, 1, 1, 0.45f) : Color.white);
            }
            foreach (var gate in World.I.gates)
            {
                if (gate.open) continue;
                PlaceIcon(ii++, Icon.Lock, gate.transform.position - p, scale, 30);
            }
            // the "try the new weapon" crowd: its weapon icon on the map
            var goal = g.hud != null ? g.hud.Goal : null;
            if (goal != null && goal.kind == Goals.Kind.TryWeapon && goal.hasTarget) PlaceIcon(ii++, goal.icon, goal.destination - p, scale, 38);
            for (int i = ii; i < icons.Count; i++) icons[i].enabled = false;
        }

        void PlaceIcon(int i, Icon icon, Vector3 off, float scale, float px, Color? tint = null)
        {
            var im = IconAt(i);
            float half = view * 0.5f;
            // clamp to the circle edge so important icons stay visible
            var v = new Vector2(off.x, off.z);
            float maxR = half * 0.86f;
            if (v.magnitude > maxR) v = v.normalized * maxR;
            im.enabled = true;
            im.sprite = Tex.Get(icon);
            im.color = tint ?? Color.white;
            im.rectTransform.sizeDelta = new Vector2(px, px);
            im.rectTransform.anchoredPosition = v * scale;
        }
    }
}
