using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// DEV «Локации»: takes the car straight to a zone (its repair pad, heading north), even from a new save with the
    /// story gates closed. The visit is a test: it counts no boss, gives no reward and never changes the save's
    /// unlocked zones; the access it grants lives in session memory only (TestZone). The move:
    ///  1. checks the world is ready (built, car alive, not already moving);
    ///  2. closes the DEV panel and clears the input (the touch stick is released, input is held for a moment);
    ///  3. puts the car on the zone's pad at the floor's height, heading north;
    ///  4. resets velocities, rotation, a jump in progress and a flip (Player.Teleport);
    ///  5. clears harpoons, the gun's rounds and the aim tied to the old place (and enemy shots in flight);
    ///  6. updates the camera, the zone look (palette, banner), the minimap and the goal widget;
    ///  7. keeps the selected game speed and John Wick (DevOptions are not touched).
    /// An unfinished intro is set aside (Intro.Suspend): no intro jump, no tutorial completion; the save still has the
    /// intro ahead. Game.SaveNow never stores a position in a zone the save has not unlocked.
    /// </summary>
    public static class DevTravel
    {
        /// <summary>The highest zone a DEV move took the car to beyond the save's unlocked zones (-1: none). Session only.</summary>
        public static int TestZone { get; private set; } = -1;
        /// <summary>The intro was set aside by a DEV move this session (the save still has it ahead).</summary>
        public static bool IntroSuspended { get; private set; }
        /// <summary>Input is held until this unscaled time after a move (no stick carried over from the menu).</summary>
        public static float InputBlockedUntil { get; private set; } = -1f;
        public static int Moves { get; private set; }
        public static string LastResult { get; private set; } = "";
        const float HoldInput = 0.35f;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        public static void ResetForPlay() { TestZone = -1; IntroSuspended = false; InputBlockedUntil = -1f; Moves = 0; LastResult = ""; }

        public static bool InputHeld => Time.unscaledTime < InputBlockedUntil;

        /// <summary>The zones the car may use this session: the save's unlocked ones plus a DEV test visit.</summary>
        public static int AccessZone(SaveData d) => d == null ? 0 : Mathf.Max(d.unlockedZone, TestZone);

        /// <summary>Intro pending and still running (not set aside by a DEV move).</summary>
        public static bool IntroRunning(SaveData d) => Intro.Active != null || (d != null && d.introPending && !IntroSuspended);

        /// <summary>The car is in a zone the save has not unlocked (a DEV test visit).</summary>
        public static bool InTestZone(Game g) => g != null && g.player != null && g.progress != null
            && Content.ZoneIndexAt(g.player.Pos.z) > g.progress.d.unlockedZone;

        public static string ZoneLabel(int zone)
        {
            switch (zone)
            {
                case 0: return "Зона 1 — Dust Flats";
                case 1: return "Зона 2 — Toxic Wetlands";
                case 2: return "Зона 3 — Пепельная зима";
                default: return "Зона " + (zone + 1);
            }
        }

        /// <summary>Why a move cannot happen now (null when it can).</summary>
        public static string Blocker(int zone)
        {
            var g = Game.I;
            if (g == null || !g.Ready || g.world == null || g.player == null || g.progress == null || World.I == null) return "мир ещё строится";
            if (zone < 0 || zone >= Content.ZoneCount) return "нет такой зоны";
            if (!g.player.Alive) return "машина восстанавливается";
            if (InputHeld) return "переход уже идёт";
            if (Station(zone) == null) return "нет точки прибытия";
            return null;
        }

        static RepairStation Station(int zone)
        {
            if (World.I == null) return null;
            foreach (var s in World.I.stations) if (s.zone == zone) return s;
            return null;
        }

        /// <summary>The safe arrival point of a zone: its repair pad (where the game also respawns the car), heading north.</summary>
        public static bool ArrivalPoint(int zone, out Vector3 pos, out float yaw)
        {
            var st = Station(zone);
            pos = st != null ? st.pos : Vector3.zero;
            yaw = 0f;
            if (st == null) return false;
            var g = Ground.Sample(pos.x, pos.z, pos.y + 1.5f);
            if (g.valid) pos.y = g.h;
            return true;
        }

        /// <summary>Moves the car to a zone (see the class summary). Returns false with LastResult set when it cannot.</summary>
        public static bool Go(int zone)
        {
            string why = Blocker(zone);
            if (why != null) { LastResult = why; Debug.Log("RoadGame DEV travel refused: " + why); return false; }
            var g = Game.I;
            var d = g.progress.d;
            // 2. the menu closes, the stick lets go, input waits a moment
            if (g.hud != null)
            {
                if (g.hud.devPanel != null) g.hud.devPanel.Close();
                if (g.hud.joystick != null) g.hud.joystick.Release();
            }
            InputBlockedUntil = Time.unscaledTime + HoldInput;
            // an unfinished intro is set aside: no intro jump, no tutorial completion (the save keeps it ahead)
            if (Intro.Active != null) { Intro.Active.Suspend(); IntroSuspended = true; }
            else if (d.introPending) IntroSuspended = true;
            // test access (session only): never written into the save
            if (zone > d.unlockedZone) TestZone = Mathf.Max(TestZone, zone);
            // 3-4. the car on the pad: floor height, heading north, velocities / rotation / jump / flip reset
            ArrivalPoint(zone, out var pos, out float yaw);
            var pl = g.player;
            pl.Teleport(pos, yaw);
            // 5. nothing tied to the old place: harpoons, the gun's rounds, the aim, enemy shots in flight
            if (pl.harpooner != null) pl.harpooner.ClearAll();
            if (pl.turret != null) pl.turret.ClearAll();
            g.focusTarget = null;
            Projectile.ResetPool();
            // 6. camera, zone look, minimap, goals
            World.I.Tick();
            g.cameraRig.Snap();
            g.SnapZoneLook();
            Goals.ResetStatics();
            Moves++;
            LastResult = ZoneLabel(zone) + (zone > d.unlockedZone ? " (тестовый визит)" : "");
            Debug.Log($"RoadGame DEV travel to zone {zone} at {pos} (unlocked {d.unlockedZone}, test access {TestZone}, intro suspended {IntroSuspended}, speed {DevOptions.Speed}x, JW {DevOptions.JohnWick})");
            return true;
        }
    }
}
