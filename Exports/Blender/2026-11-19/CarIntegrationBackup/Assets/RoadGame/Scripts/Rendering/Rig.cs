using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>References to the animatable parts of a procedural model + material swapping (hit flash / burnt).</summary>
    public class Rig : MonoBehaviour
    {
        public Transform body;            // main body (bob / tilt)
        public Transform legL, legR, armL, armR;
        public Transform weapon;          // held weapon
        public Transform turret;          // rotating top part
        public Transform muzzle;
        public readonly List<Transform> wheels = new List<Transform>();
        public readonly List<Transform> steer = new List<Transform>();
        public readonly List<Renderer> renderers = new List<Renderer>();
        public float height = 2f;
        public float wheelRadius = 0.4f;

        Material[] baseMats;
        float flashUntil;
        bool burnt;

        public void CollectRenderers()
        {
            renderers.Clear();
            GetComponentsInChildren(true, renderers);
            baseMats = new Material[renderers.Count];
            for (int i = 0; i < renderers.Count; i++) baseMats[i] = renderers[i].sharedMaterial;
        }

        public void Flash(float duration = 0.08f)
        {
            if (burnt || baseMats == null) return;
            flashUntil = Time.time + duration;
            for (int i = 0; i < renderers.Count; i++)
                if (renderers[i] != null && IsToon(baseMats[i])) renderers[i].sharedMaterial = Mats.Flash;
            enabled = true;
        }

        public void SetBurnt(bool on)
        {
            burnt = on;
            if (baseMats == null) return;
            for (int i = 0; i < renderers.Count; i++)
            {
                if (renderers[i] == null || !IsToon(baseMats[i])) continue;
                renderers[i].sharedMaterial = on ? Mats.Burnt : baseMats[i];
            }
        }

        static bool IsToon(Material m) => m == Mats.Toon || m == Mats.CarPaint;

        void Update()
        {
            if (flashUntil > 0 && Time.time >= flashUntil)
            {
                flashUntil = 0;
                if (!burnt && baseMats != null)
                    for (int i = 0; i < renderers.Count; i++)
                        if (renderers[i] != null) renderers[i].sharedMaterial = baseMats[i];
                enabled = false;
            }
        }

        public void SetShadows(bool cast)
        {
            foreach (var r in renderers)
                if (r != null) r.shadowCastingMode = cast ? UnityEngine.Rendering.ShadowCastingMode.On : UnityEngine.Rendering.ShadowCastingMode.Off;
        }
    }
}
