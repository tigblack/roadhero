using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// A telescopic mechanical arm mounted on the car holding one weapon (the reference's tentacle-held weapon).
    /// Auto-attacks the nearest target in range: overhead smash (hammer), thrust (spear / lance). Slot 0 is the roof Turret.
    /// </summary>
    public class WeaponArm : MonoBehaviour
    {
        public int slot;
        Player player;
        Transform yawT, pitchT, boom, tip, weaponT;
        MeshFilter weaponMF;
        Vector3 mountLocal;
        float side;
        int shownLevel = -1;
        float cooldown;
        float anim = -1f;
        float dur;
        bool impactDone;
        Target target;
        Vector3 lastTargetPos;
        float aimYaw, reach;
        float curYaw, curPitch, curLen;
        float fromYaw, fromPitch, fromLen;
        float popIn = 1f;
        bool crit;

        float RestYaw => side > 0 ? 150f : -150f;
        const float RestPitch = -30f;
        const float RestLen = 0.7f;
        const float ArmScale = 1.15f;

        public static WeaponArm Create(Player p, int slot, Transform carBody, Vector3 mountPos)
        {
            var go = new GameObject("Arm" + slot);
            go.transform.SetParent(carBody, false);
            go.transform.localPosition = mountPos;
            go.transform.localScale = Vector3.one * ArmScale;
            var a = go.AddComponent<WeaponArm>();
            a.player = p;
            a.slot = slot;
            a.mountLocal = mountPos;
            a.side = Mathf.Sign(mountPos.x);
            Models.MeshGO("Joint", Models.ArmJointMesh(), Mats.Toon, go.transform);
            a.yawT = new GameObject("Yaw").transform; a.yawT.SetParent(go.transform, false);
            a.pitchT = new GameObject("Pitch").transform; a.pitchT.SetParent(a.yawT, false);
            a.boom = Models.MeshGO("Boom", Models.ArmBoomMesh(), Mats.Toon, a.pitchT).transform;
            a.tip = new GameObject("Tip").transform; a.tip.SetParent(a.pitchT, false);
            var w = Models.MeshGO("Weapon", Models.WeaponMesh(slot, 1), Mats.Toon, a.tip);
            a.weaponT = w.transform;
            a.weaponT.localScale = Vector3.one * 1.3f;
            a.weaponMF = w.GetComponent<MeshFilter>();
            a.curYaw = a.RestYaw; a.curPitch = RestPitch; a.curLen = RestLen;
            a.ApplyPose();
            return a;
        }

        Progress P => Game.I.progress;

        void SetVisible(bool v)
        {
            foreach (var r in GetComponentsInChildren<Renderer>(true)) r.enabled = v;
        }

        bool visible = true;

        void Update()
        {
            if (Game.I == null || Game.I.progress == null || World.I == null || player == null) return;
            bool owned = P.WeaponOwned(slot);
            if (owned != visible) { visible = owned; SetVisible(owned); if (owned) popIn = 0f; }
            if (!owned) return;
            float dt = Time.deltaTime;
            int level = P.WeaponLevel(slot);
            if (level != shownLevel)
            {
                shownLevel = level;
                weaponMF.sharedMesh = Models.WeaponMesh(slot, level);
            }
            if (popIn < 1f)
            {
                popIn = Mathf.Min(1f, popIn + dt * 2.5f);
                transform.localScale = Vector3.one * ArmScale * Mathf.Lerp(0.01f, 1f, popIn) * (1f + Mathf.Sin(popIn * Mathf.PI) * 0.4f);
            }

            var w = Content.Weapons[slot];
            cooldown -= dt;
            if (anim < 0f)
            {
                if (cooldown <= 0f && player.CanFight)
                {
                    var t = World.I.Nearest(player.Pos, w.range + player.Radius, Game.I.focusTarget);
                    if (t != null) StartSwing(t, w);
                }
                // idle: relax toward rest with a little sway
                float sway = Mathf.Sin(Time.time * 2.2f + slot) * 6f;
                curYaw = Mathf.LerpAngle(curYaw, RestYaw + sway, 1f - Mathf.Exp(-6f * dt));
                curPitch = Mathf.Lerp(curPitch, RestPitch + Mathf.Sin(Time.time * 3f + slot * 2) * 4f, 1f - Mathf.Exp(-6f * dt));
                curLen = Mathf.Lerp(curLen, RestLen, 1f - Mathf.Exp(-6f * dt));
            }
            else
            {
                anim += dt / dur;
                UpdateSwing(w);
                if (anim >= 1f) anim = -1f;
            }
            ApplyPose();
        }

        void StartSwing(Target t, WeaponDef w)
        {
            target = t;
            lastTargetPos = t.Pos;
            anim = 0f;
            impactDone = false;
            dur = Mathf.Min(0.58f, w.interval * 0.8f);
            cooldown = w.interval;
            fromYaw = curYaw; fromPitch = curPitch; fromLen = curLen;
            crit = Random.value < Balance.CritChance;
            Aim();
            Game.I.focusTarget = t;
        }

        void Aim()
        {
            if (target != null && target.Targetable) lastTargetPos = target.Pos;
            var parent = transform.parent;
            var local = parent.InverseTransformPoint(lastTargetPos) - mountLocal;
            local.y = 0;
            aimYaw = Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;
            float tr = target != null ? target.Radius : 0.5f;
            reach = Mathf.Clamp(local.magnitude - tr * 0.55f, 0.8f, Content.Weapons[slot].range + 2.2f) / ArmScale - 0.9f;
            reach = Mathf.Max(0.5f, reach);
        }

        void UpdateSwing(WeaponDef w)
        {
            Aim();
            float a = Mathf.Clamp01(anim);
            float wYaw, wPitch, wLen, sYaw, sPitch, sLen;
            float impactAt;
            switch (w.type)
            {
                case DamageType.Smash:
                    wYaw = aimYaw; wPitch = -100f; wLen = reach * 0.85f;
                    sYaw = aimYaw; sPitch = 18f; sLen = reach;
                    impactAt = 0.6f;
                    break;
                case DamageType.Pierce:
                case DamageType.Blast:
                    wYaw = aimYaw; wPitch = -12f; wLen = 0.35f;
                    sYaw = aimYaw; sPitch = 4f; sLen = reach + 0.25f;
                    impactAt = 0.58f;
                    break;
                default: // slash sweep
                    wYaw = aimYaw + side * 70f; wPitch = -38f; wLen = reach * 0.75f;
                    sYaw = aimYaw - side * 40f; sPitch = 6f; sLen = reach;
                    impactAt = 0.52f;
                    break;
            }
            const float windEnd = 0.4f, strikeEnd = 0.64f;
            if (a < windEnd)
            {
                float k = EaseOut(a / windEnd);
                curYaw = Mathf.LerpAngle(fromYaw, wYaw, k);
                curPitch = Mathf.Lerp(fromPitch, wPitch, k);
                curLen = Mathf.Lerp(fromLen, wLen, k);
            }
            else if (a < strikeEnd)
            {
                float k = EaseIn((a - windEnd) / (strikeEnd - windEnd));
                curYaw = Mathf.LerpAngle(wYaw, sYaw, k);
                curPitch = Mathf.Lerp(wPitch, sPitch, k);
                curLen = Mathf.Lerp(wLen, sLen, k);
            }
            else
            {
                float k = EaseOut((a - strikeEnd) / (1f - strikeEnd));
                curYaw = Mathf.LerpAngle(sYaw, RestYaw, k);
                curPitch = Mathf.Lerp(sPitch, RestPitch, k);
                curLen = Mathf.Lerp(sLen, RestLen, k);
            }
            if (!impactDone && a >= impactAt)
            {
                impactDone = true;
                Impact(w);
            }
        }

        void Impact(WeaponDef w)
        {
            double dmg = P.WeaponHitDamage(slot) * (crit ? Balance.CritMul : 1f);
            Vector3 point = tip.position;
            int hits = 0;
            Vector3 hitAt = target != null ? target.Pos : tip.position;
            if (target != null && target.Targetable)
            {
                point = target.Pos + Vector3.up * Mathf.Min(1.2f, target.BarHeight * 0.4f);
                target.Hit(dmg, crit, player.Pos);
                hits++;
            }
            if (w.aoe > 0f)
            {
                var center = target != null ? target.Pos : tip.position;
                var main = target;
                World.I.ForEachInRadius(center, w.aoe, t => { if (t != main) { t.Hit(dmg * 0.7, false, player.Pos); hits++; } });
                Game.I.fx.Slam(center, w.aoe * (w.type == DamageType.Blast ? 1f : 0.7f), w.type == DamageType.Blast);
                Game.I.cameraRig.Shake(w.type == DamageType.Blast ? 0.35f : 0.2f);
                Game.I.sfx.Play(w.type == DamageType.Blast ? Sfx.Kind.Explode : Sfx.Kind.Smash, center, 0.7f);
            }
            else if (target != null)
            {
                Game.I.sfx.Impact(target, point, crit, 0.9f);
            }
            Game.I.fx.Sparks(point, crit);
            Game.I.OnWeaponImpact(slot, hits, hitAt);
        }

        void ApplyPose()
        {
            yawT.localRotation = Quaternion.Euler(0, curYaw, 0);
            pitchT.localRotation = Quaternion.Euler(curPitch, 0, 0);
            boom.localScale = new Vector3(1, 1, Mathf.Max(0.05f, curLen));
            tip.localPosition = new Vector3(0, 0, curLen);
            // keep the weapon slightly upright so the head reads from the top-down camera
            tip.localRotation = Quaternion.Euler(-curPitch * 0.35f, 0, 0);
        }

        static float EaseOut(float t) { t = Mathf.Clamp01(t); return 1f - (1f - t) * (1f - t); }
        static float EaseIn(float t) { t = Mathf.Clamp01(t); return t * t; }
    }
}
