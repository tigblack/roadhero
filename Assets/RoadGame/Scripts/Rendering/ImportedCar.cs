using System;
using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>The authored Blender car, bound to the existing driving and weapon animation hooks.</summary>
    public sealed class ImportedCar : MonoBehaviour
    {
        public const string PrefabResource = "Cars/ScarboundDetailed";
        readonly List<Renderer> surfaces = new List<Renderer>();
        MaterialPropertyBlock properties;
        Color shade;
        bool hasShade;
        MeshFilter upgradeBadge;

        public static bool TryCreate(out GameObject car, out Rig rig)
        {
            car = null;
            rig = null;
            var prefab = Resources.Load<GameObject>(PrefabResource);
            if (prefab == null) return false;
            var instance = Instantiate(prefab);
            try
            {
                var imported = instance.GetComponent<ImportedCar>();
                if (imported == null) throw new InvalidOperationException("Imported car prefab has no ImportedCar marker");
                rig = instance.GetComponent<Rig>();
                if (rig == null) rig = instance.AddComponent<Rig>();
                rig.body = Need(instance.transform, "Body");
                rig.wheels.Clear();
                rig.steer.Clear();
                foreach (var path in new[] { "WheelSteer_FL", "WheelSteer_FR", "Wheel_RL", "Wheel_RR" })
                {
                    var pivot = Need(instance.transform, path);
                    rig.wheels.Add(Need(pivot, "Wheel"));
                    if (rig.wheels.Count <= 2) rig.steer.Add(pivot);
                }
                rig.wheelRadius = Models.CarRearWheelR;
                rig.height = 2.4f;
                instance.name = "PlayerCar";
                car = instance;
                imported.RefreshSurfaces();
#if UNITY_WEBGL && !UNITY_EDITOR
                // Runtime car code uses bounds and transforms; vertex copies are only needed by editor art tools.
                var uploaded = new HashSet<Mesh>();
                foreach (var filter in instance.GetComponentsInChildren<MeshFilter>(true))
                    if (filter.sharedMesh != null && filter.sharedMesh.isReadable && uploaded.Add(filter.sharedMesh))
                        filter.sharedMesh.UploadMeshData(true);
#endif
                return true;
            }
            catch (Exception error)
            {
                Debug.LogError("RoadGame: invalid Blender car prefab: " + error);
                if (Application.isPlaying) Destroy(instance); else DestroyImmediate(instance);
                rig = null;
                return false;
            }
        }

        static Transform Need(Transform parent, string path)
        {
            var result = parent.Find(path);
            if (result == null) throw new InvalidOperationException("Missing Blender car hook: " + parent.name + "/" + path);
            return result;
        }

        public static bool TryBindHoodGun(Transform body, int tier, Material flashMaterial, out Models.HoodGunRig rig)
        {
            rig = null;
            var imported = body.GetComponentInParent<ImportedCar>();
            if (imported == null) return false;
            var r = new Models.HoodGunRig { imported = imported };
            r.root = Need(body, "TurretBase");
            r.yaw = Need(r.root, "TurretYaw");
            r.pitch = Need(r.yaw, "TurretPitch");
            r.gun = Need(r.pitch, "Barrel0");
            r.gunRest = r.gun.localPosition;
            r.muzzle = Need(r.gun, "HoodGun_Muzzle");
            r.mount = Need(r.root, "HoodMount").GetComponent<MeshFilter>();
            r.turntable = Need(r.yaw, "Turntable").GetComponent<MeshFilter>();
            r.gunMesh = Need(r.gun, "GunMesh").GetComponent<MeshFilter>();
            if (flashMaterial != null)
            {
                var existing = r.muzzle.Find("Flash");
                var flash = existing != null ? existing.gameObject : Models.MeshGO("Flash", Models.MgFlashMesh(), flashMaterial, r.muzzle, false);
                flash.transform.localPosition = Vector3.zero;
                flash.SetActive(false);
                r.flash = flash.transform;
            }
            imported.EnsureBadge(r.turntable);
            imported.SetGunTier(tier);
            rig = r;
            return true;
        }

        public static bool TryBindHarpooner(Transform body, out Models.HarpoonerRig rig)
        {
            rig = null;
            if (body.GetComponentInParent<ImportedCar>() == null) return false;
            var r = new Models.HarpoonerRig();
            r.root = Need(body, "Harpooner");
            r.yaw = Need(r.root, "TurretYaw");
            r.gun = Need(r.yaw, "Launcher");
            r.gunRest = r.gun.localPosition;
            r.muzzle = Need(r.gun, "Muzzle");
            r.tip = Need(r.muzzle, "HarpoonTip");
            r.crew = Need(r.yaw, "Quasimodo");
            r.body = Need(r.crew, "Body");
            r.bodyRest = r.body.localPosition;
            r.head = Need(r.body, "Head");
            for (int i = 0; i < 2; i++)
            {
                string side = i == 0 ? "R" : "L";
                r.leg[i] = Need(r.crew, "Leg" + side);
                r.shoulder[i] = Need(r.body, "Shoulder" + side);
                r.grip[i] = Need(r.gun, "Grip" + side);
                r.upperArm[i] = Need(r.crew, "UpperArm" + side);
                r.foreArm[i] = Need(r.crew, "ForeArm" + side);
                r.glove[i] = Need(r.crew, "Hand" + side);
            }
            Models.SolveHarpoonerArms(r);
            rig = r;
            return true;
        }

        void EnsureBadge(MeshFilter turntable)
        {
            if (upgradeBadge != null || turntable == null || turntable.sharedMesh == null) return;
            var badge = Models.MeshGO("GunUpgradeBadge", BadgeMesh(1), Mats.Toon, turntable.transform);
            upgradeBadge = badge.GetComponent<MeshFilter>();
            var bounds = turntable.sharedMesh.bounds;
            badge.transform.localPosition = bounds.center + Vector3.right * (bounds.extents.x + 0.008f);
            var group = GetComponent<LODGroup>();
            if (group != null)
            {
                var lods = group.GetLODs();
                var renderer = badge.GetComponent<Renderer>();
                for (int i = 0; i < lods.Length; i++)
                {
                    var list = new List<Renderer>(lods[i].renderers) { renderer };
                    lods[i].renderers = list.ToArray();
                }
                group.SetLODs(lods);
            }
        }

        static Mesh BadgeMesh(int tier)
        {
            return Models.Cached("imported_car_gun_badge_" + tier, b =>
            {
                b.Material(0.45f, 0.6f);
                b.BevelBox(Vector3.zero, new Vector3(0.014f, 0.055f, 0.085f), 0.004f, new Color(0.2f, 0.23f, 0.25f));
                var color = tier == 3 ? new Color(0.95f, 0.76f, 0.31f) : tier == 2 ? new Color(0.65f, 0.48f, 0.92f) : new Color(0.37f, 0.68f, 0.91f);
                b.Material(0.7f, 0.5f);
                for (int i = 0; i < tier; i++)
                    b.BevelBox(new Vector3(0.008f, (i - (tier - 1) * 0.5f) * 0.014f, 0), new Vector3(0.005f, 0.007f, 0.065f), 0.002f, color);
            });
        }

        /// <summary>Small rank marks retain the authored weapon geometry at every upgrade tier.</summary>
        public void SetGunTier(int tier)
        {
            if (upgradeBadge == null) return;
            tier = Mathf.Clamp(tier, 0, 3);
            upgradeBadge.gameObject.SetActive(tier > 0);
            if (tier > 0) upgradeBadge.sharedMesh = BadgeMesh(tier);
        }

        void Awake() { RefreshSurfaces(); }

        void RefreshSurfaces()
        {
            surfaces.Clear();
            GetComponentsInChildren(true, surfaces);
            hasShade = false;
            ApplyShade();
        }

        void LateUpdate() { ApplyShade(); }

        void ApplyShade()
        {
            if (Mats.Toon == null) return;
            var next = Mats.Toon.GetColor("_ShadeColor");
            if (hasShade && shade == next) return;
            hasShade = true;
            shade = next;
            if (properties == null) properties = new MaterialPropertyBlock();
            foreach (var renderer in surfaces)
            {
                if (renderer == null || renderer.sharedMaterial == null || !renderer.sharedMaterial.HasProperty("_ShadeColor")) continue;
                renderer.GetPropertyBlock(properties);
                properties.SetColor("_ShadeColor", shade);
                renderer.SetPropertyBlock(properties);
            }
        }
    }
}
