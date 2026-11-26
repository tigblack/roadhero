using UnityEngine;
using UnityEngine.Rendering;

namespace RoadGame
{
    /// <summary>Material factory for the second zone's murky water (shader RoadGame/SwampWater, loaded through
    /// Resources so WebGL builds keep it). The Blender bundle supplies the scum noise map and vertex colours.</summary>
    public static class SwampWater
    {
        public static Material CreateSurfaceMaterial(string name, Color artTint, float opacity)
        {
            var shader = Resources.Load<Shader>("Shaders/SwampWater");
            if (shader == null)
            {
                Debug.LogError("RoadGame: missing swamp water shader.");
                return RiverWaterFx.CreateSurfaceMaterial(name, artTint, opacity);
            }
            var m = new Material(shader) { name = name };
            m.SetColor("_BaseColor", artTint);
            m.SetFloat("_Alpha", Mathf.Clamp(opacity, 0.5f, 0.95f));
            m.renderQueue = (int)RenderQueue.Transparent - 80;
            return m;
        }
    }
}
