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
        bool[] importedSurface;
        MaterialPropertyBlock appearance;
        float flashUntil;
        bool burnt;

        public void CollectRenderers()
        {
            renderers.Clear();
            GetComponentsInChildren(true, renderers);
            baseMats = new Material[renderers.Count];
            importedSurface = new bool[renderers.Count];
            for (int i = 0; i < renderers.Count; i++)
            {
                baseMats[i] = renderers[i].sharedMaterial;
                importedSurface[i] = (renderers[i].GetComponentInParent<ImportedCar>() != null
                                      || renderers[i].GetComponentInParent<ImportedActorSurface>() != null)
                    && baseMats[i] != null && baseMats[i].HasProperty("_FlashColor");
            }
        }

        /// <summary>True when at least one drawn renderer takes the imported (property block) hit / burn path.</summary>
        public bool CollectedImported()
        {
            if (importedSurface == null) return false;
            for (int i = 0; i < renderers.Count; i++)
                if (importedSurface[i] && renderers[i] != null && renderers[i].enabled) return true;
            return false;
        }

        public void Flash(float duration = 0.08f)
        {
            if (burnt || baseMats == null) return;
            flashUntil = Time.time + duration;
            for (int i = 0; i < renderers.Count; i++)
            {
                if (renderers[i] == null) continue;
                if (importedSurface[i]) ApplyImportedAppearance(i, true);
                else if (IsToon(baseMats[i])) renderers[i].sharedMaterial = Mats.Flash;
            }
            enabled = true;
        }

        public void SetBurnt(bool on)
        {
            burnt = on;
            if (baseMats == null) return;
            for (int i = 0; i < renderers.Count; i++)
            {
                if (renderers[i] == null) continue;
                if (importedSurface[i]) ApplyImportedAppearance(i, !on && flashUntil > Time.time);
                else if (IsToon(baseMats[i])) renderers[i].sharedMaterial = on ? Mats.Burnt : baseMats[i];
            }
        }

        static bool IsToon(Material m) => m == Mats.Toon || m == Mats.CarPaint;

        // Per-renderer overrides retain the Blender texture set and the same appearance across all LODs.
        void ApplyImportedAppearance(int index, bool flash)
        {
            var renderer = renderers[index];
            var material = baseMats[index];
            if (appearance == null) appearance = new MaterialPropertyBlock();
            renderer.GetPropertyBlock(appearance);
            appearance.SetColor("_FlashColor", flash ? new Color(1f, 0.96f, 0.86f, 0.6f) : material.GetColor("_FlashColor"));
            if (material.HasProperty("_BaseColor"))
            {
                var color = material.GetColor("_BaseColor");
                appearance.SetColor("_BaseColor", burnt ? color * new Color(0.5f, 0.46f, 0.44f, 1f) : color);
            }
            if (material.HasProperty("_Saturation")) appearance.SetFloat("_Saturation", material.GetFloat("_Saturation") * (burnt ? 0.35f : 1f));
            if (material.HasProperty("_GlossMul")) appearance.SetFloat("_GlossMul", material.GetFloat("_GlossMul") * (burnt ? 0.25f : 1f));
            renderer.SetPropertyBlock(appearance);
        }

        void Update()
        {
            if (flashUntil > 0 && Time.time >= flashUntil)
            {
                flashUntil = 0;
                if (baseMats != null)
                    for (int i = 0; i < renderers.Count; i++)
                    {
                        if (renderers[i] == null) continue;
                        if (importedSurface[i]) ApplyImportedAppearance(i, false);
                        else if (!burnt) renderers[i].sharedMaterial = baseMats[i];
                    }
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
