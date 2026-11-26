using System;
using UnityEngine;

namespace RoadGame
{
    /// <summary>Session-only playtest controls. They never change saved weapon stats or player preferences.</summary>
    public static class DevOptions
    {
        public static float Speed { get; private set; } = 1f;
        public static bool JohnWick { get; private set; }
        public static event Action Changed;

        public static void SetSpeed(float multiplier)
        {
            float next = multiplier == 4f ? 4f : multiplier == 2f ? 2f : 1f;
            if (Mathf.Approximately(next, Speed)) return;
            Speed = next;
            if (Game.I != null) Game.I.RefreshTimeScale();
            Changed?.Invoke();
        }

        public static void SetJohnWick(bool enabled)
        {
            if (JohnWick == enabled) return;
            JohnWick = enabled;
            Changed?.Invoke();
        }

        internal static void ResetForPlay()
        {
            Speed = 1f;
            JohnWick = false;
            Changed = null;
        }
    }
}
