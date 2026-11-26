using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// Shallow-water forces for the existing tire/rigid-body controller. A heavy pickup fords on the bed,
    /// rather than floating; each submerged tire displaces water and experiences flow-relative drag.
    /// </summary>
    public static class WaterPhysics
    {
        public struct Contact
        {
            public float depth;           // submerged height of this tire, metres
            public float wetness;         // fraction of the river's deepest 22 cm immersion
            public Vector3 flow;          // current in world m/s
            public float level;           // water surface height of this volume
        }

        public const float ReferenceDepth = 0.22f;
        const float Density = 1000f;       // fresh water, kg/m3
        const float TireWidth = 0.32f;
        const float DragCoefficient = 1.15f;

        /// <summary>
        /// Probe a wheel's bottom in world space. Water occupies only [bed, surface]: a bridge, an airborne
        /// wheel, or a tunnel below the bed must not acquire river drag from its X/Z coordinates alone.
        /// </summary>
        public static bool TryContact(Vector3 wheelBottom, out Contact contact)
        {
            contact = default;
            float level, bed;
            Vector3 flow = Vector3.zero;
            if (DustFlatsSurfaces.TrySampleWater(wheelBottom.x, wheelBottom.z, out bed, out flow)) level = DustFlatsSurfaces.WaterLevel;
            else if (WetlandSurfaces.TrySampleWater(wheelBottom.x, wheelBottom.z, out bed)) level = WetlandSurfaces.WaterLevel;
            else return false;
            if (wheelBottom.y >= level - 0.002f || wheelBottom.y < bed - 0.12f) return false;
            float depth = Mathf.Min(level - bed, level - wheelBottom.y);
            if (depth <= 0.002f) return false;
            contact.depth = depth;
            contact.wetness = Mathf.Clamp01(depth / ReferenceDepth);
            contact.flow = flow;
            contact.level = level;
            return true;
        }

        /// <summary>Water surface height of whichever shallow-water volume covers x, z (NaN when none).</summary>
        public static float LevelAt(float x, float z)
        {
            if (DustFlatsSurfaces.TrySampleWater(x, z, out _, out _)) return DustFlatsSurfaces.WaterLevel;
            if (WetlandSurfaces.TrySampleWater(x, z, out _)) return WetlandSurfaces.WaterLevel;
            return float.NaN;
        }

        /// <summary>Quadratic pressure drag on a submerged tire's frontal area, plus low-speed viscous drag.</summary>
        public static Vector3 TireDrag(Vector3 relativeVelocity, float depth, float step)
        {
            relativeVelocity.y = 0f;
            float speed = relativeVelocity.magnitude;
            if (depth <= 0f || speed < 0.0001f) return Vector3.zero;
            float area = TireWidth * depth;
            float force = 0.5f * Density * DragCoefficient * area * speed * speed + 90f * depth * speed;
            // At most a quarter of the car's relative momentum per tire/substep; no numerical reversal.
            force = Mathf.Min(force, CarTuning.Mass * speed / (4f * Mathf.Max(0.001f, step)));
            return -relativeVelocity * (force / speed);
        }
    }
}
