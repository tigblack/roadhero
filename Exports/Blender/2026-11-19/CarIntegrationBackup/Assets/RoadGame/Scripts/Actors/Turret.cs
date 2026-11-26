using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// Hood machine gun (weapon slot 0, the starting weapon): a small light machine gun on a low turning base on the right
    /// half of the hood, beside the blower. Auto-aims at the nearest target in range and fires: tracer round, muzzle
    /// flash, the gun's kick on its cradle, smoke, ejected brass, impact effects. The base turns (yaw) and the gun tilts
    /// on its yoke (pitch); the aim is solved in the mount's own frame, so it stays right while the body pitches, rolls
    /// and flies. The gun keeps clear of the car: how far it may dip depends on where it points (it lifts over the blower
    /// to the left, over the windshield and the cab behind), and a round first leaves along the barrel before it turns
    /// onto its target. Damage per round = the slot 0 damage stat.
    /// </summary>
    public class Turret : MonoBehaviour
    {
        const int Slot = 0;
        const float ShellSpeed = 95f;
        const float TracerLength = 2.0f;
        /// <summary>A round flies this far straight along the barrel (over the blower / the cab) before it turns.</summary>
        public const float LaunchRun = 1.0f;
        const float RecoilTravel = 0.022f;
        const float FlashScale = 1f;
        Player player;
        Models.HoodGunRig gun;
        Transform yawT, pitchT, gunT, flash;
        int shownTier = -1;
        float yaw, pitch;
        float cooldown;
        float recoil, flashT;
        Target target;
        float popIn = 1f;
        bool visible = true;

        class Shell
        {
            public Target target;
            public Vector3 pos, dir, launchDir, kink;
            public float run;          // distance still to fly along the barrel
            public bool turned;        // past the straight launch run (kink = where it turned)
            public float traveled;
            public bool crit;
            public double dmg;
            public LineRenderer line;
            public float life;
        }
        readonly List<Shell> shells = new List<Shell>();
        readonly Stack<Shell> shellPool = new Stack<Shell>();

        class Casing
        {
            public Transform t;
            public Vector3 v, spin;
            public float life;
            public int bounces;
        }
        readonly List<Casing> casings = new List<Casing>();
        readonly Stack<Casing> casingPool = new Stack<Casing>();

        static Material flashMat, tracerMat, ringMat;
        Transform ring;
        float ringPulse, ringAlpha, ringSpin;

        public static Turret Create(Player p, Transform carBody)
        {
            if (flashMat == null)
            {
                flashMat = Mats.NewUnlit("MuzzleFlash", null, true);
                tracerMat = Mats.NewUnlit("Tracer", Tex.SoftCircle(), true);
            }
            if (ringMat == null)
            {
                ringMat = Mats.NewUnlit("TurretRange", Tex.DashedRing(), false);
                ringMat.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent - 45;
            }
            var g = Models.HoodGun(carBody, 0, flashMat);
            var t = g.root.gameObject.AddComponent<Turret>();
            t.player = p;
            t.gun = g;
            t.yawT = g.yaw;
            t.pitchT = g.pitch;
            t.gunT = g.gun;
            t.flash = g.flash;
            // weapon range shown on the ground around the car
            var rg = Models.MeshGO("TurretRangeRing", Models.FlatQuad(), ringMat, null, false);
            rg.GetComponent<MeshRenderer>().receiveShadows = false;
            t.ring = rg.transform;
            return t;
        }

        Progress P => Game.I.progress;

        /// <summary>Rounds fired / rounds that reached a live target since start (test telemetry).</summary>
        public static int ShotsFired, ShellHits;

        public static void ResetStatics() { flashMat = null; tracerMat = null; ringMat = null; ShotsFired = 0; ShellHits = 0; }

        /// <summary>Distance from the car's centre to the ring = how far the gun reaches (target edges inside it get shot).</summary>
        public float RangeRadius => Content.Weapons[Slot].range + (player != null ? player.Radius : 1.25f);

        void LateUpdate()
        {
            if (ring == null || player == null || Game.I == null || Game.I.progress == null) return;
            float dt = Time.deltaTime;
            bool show = player.Alive && visible;
            ringAlpha = Mathf.MoveTowards(ringAlpha, show ? 1f : 0f, dt * 3f);
            ringPulse = Mathf.MoveTowards(ringPulse, 0f, dt * 4f);
            ringSpin += dt * 4f;
            ring.gameObject.SetActive(ringAlpha > 0.01f);
            var p = player.transform.position;
            float r = RangeRadius / 0.972f * (1f + ringPulse * 0.025f);   // ring edge sits at uv radius 0.972
            ring.SetPositionAndRotation(new Vector3(p.x, player.GroundY + 0.07f, p.z), Quaternion.Euler(0, ringSpin, 0));
            ring.localScale = new Vector3(r, 1f, r);
            var c = target != null ? new Color(1f, 0.82f, 0.45f) : new Color(1f, 0.95f, 0.85f);
            c.a = ringAlpha * (0.62f + 0.35f * ringPulse + (target != null ? 0.1f : 0f));
            ringMat.SetColor("_BaseColor", c);
        }

        void SetVisible(bool v)
        {
            foreach (var r in GetComponentsInChildren<Renderer>(true)) if (!r.name.StartsWith("Flash")) r.enabled = v;
        }

        void Update()
        {
            if (Game.I == null || Game.I.progress == null || World.I == null || player == null) return;
            float dt = Time.deltaTime;
            bool owned = P.WeaponOwned(Slot);
            if (owned != visible) { visible = owned; SetVisible(owned); if (owned) popIn = 0f; }
            UpdateShells(dt);
            UpdateCasings(dt);
            if (!owned) return;

            int level = P.WeaponLevel(Slot);
            int tier = level >= 20 ? 3 : level >= 10 ? 2 : level >= 5 ? 1 : 0;
            if (tier != shownTier && !posedForCapture) ShowTier(tier);
            if (popIn < 1f)
            {
                popIn = Mathf.Min(1f, popIn + dt * 2.5f);
                yawT.localScale = Vector3.one * Mathf.Lerp(0.01f, 1f, popIn) * (1f + Mathf.Sin(popIn * Mathf.PI) * 0.3f);
            }

            var w = Content.Weapons[Slot];
            cooldown -= dt;
            // (re)acquire a target
            if (target == null || !target.Targetable || !InRange(target, w))
                target = player.Alive ? World.I.Nearest(player.Pos, w.range + player.Radius, Game.I.focusTarget) : null;

            float wantYaw, wantPitch;
            if (target != null)
            {
                // solved in the mount's frame: body pitch / roll / a jump's tilt are already in it
                SolveAim(transform.InverseTransformPoint(AimPoint(target)), out wantYaw, out wantPitch);
            }
            else
            {
                // at rest the gun looks ahead, drifting a little
                wantYaw = Mathf.Sin(Time.time * 0.35f) * 6f;
                wantPitch = 0f;
            }
            yaw = Mathf.MoveTowardsAngle(yaw, wantYaw, 430f * dt);
            // at rest the gun lies level, only kept clear of the car; on a target it lifts to its firing limit (over the
            // blower to the left, over the windshield and the cab behind) so the flash and the round clear the car too
            wantPitch = Mathf.Clamp(wantPitch, MaxUp, target != null ? FireLimit(yaw) : MaxDownBarrel(yaw));
            pitch = Mathf.MoveTowards(pitch, wantPitch, 160f * dt);
            pitch = Mathf.Clamp(pitch, MaxUp, MaxDownBarrel(yaw));
            yawT.localRotation = Quaternion.Euler(0, yaw, 0);
            pitchT.localRotation = Quaternion.Euler(pitch, 0, 0);

            if (target != null && cooldown <= 0f && player.CanFight && Mathf.Abs(Mathf.DeltaAngle(yaw, wantYaw)) < 9f
                && pitch <= FireLimit(yaw) + 0.25f)
                Fire(w);

            // the gun kicks back on its cradle + muzzle flash
            recoil = Mathf.MoveTowards(recoil, 0f, dt * 6f);
            gunT.localPosition = new Vector3(0f, 0f, -recoil * recoil * RecoilTravel);
            if (flashT > 0f)
            {
                flashT -= dt;
                if (flashT <= 0f) flash.gameObject.SetActive(false);
            }
        }

        /// <summary>Yaw and pitch (+ = down) that point the barrel at a point given in the mount's frame (before limits).</summary>
        public static void SolveAim(Vector3 local, out float yawDeg, out float pitchDeg)
        {
            yawDeg = Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;
            float horiz = new Vector2(local.x, local.z).magnitude;
            float dy = local.y - (Models.GunPivotY + Models.GunBoreY);
            pitchDeg = Mathf.Atan2(-dy, Mathf.Max(0.5f, horiz)) * Mathf.Rad2Deg;
        }

        /// <summary>Upgrade look: level 1 / 5 / 10 / 20 = tier 0..3 (gun, turntable, base plate).</summary>
        public void ShowTier(int tier)
        {
            shownTier = tier;
            gun.gunMesh.sharedMesh = Models.MachineGunMesh(tier);
            gun.turntable.sharedMesh = Models.GunTurntableMesh(tier);
            gun.mount.sharedMesh = Models.GunBaseMesh(tier);
        }

        bool posedForCapture;

        /// <summary>Capture / test hook: a fixed tier / aim / recoil. The pitch is clamped like the real aim (a firing pose,
        /// recoil &gt; 0.5, to the firing limit; a resting one to the gun's own limit) unless told not to.</summary>
        public void PoseForCapture(int tier, float yawDeg, float pitchDeg, float recoilAmount, bool clamp = true)
        {
            posedForCapture = true;
            ShowTier(tier);
            yaw = yawDeg;
            pitch = clamp ? Mathf.Clamp(pitchDeg, MaxUp, recoilAmount > 0.5f ? FireLimit(yawDeg) : MaxDownBarrel(yawDeg)) : pitchDeg;
            yawT.localRotation = Quaternion.Euler(0, yaw, 0);
            pitchT.localRotation = Quaternion.Euler(pitch, 0, 0);
            yawT.localScale = Vector3.one;
            float k = recoilAmount * recoilAmount;
            gunT.localPosition = new Vector3(0f, 0f, -k * RecoilTravel);
            flash.gameObject.SetActive(recoilAmount > 0.5f);
            flash.localScale = Vector3.one * FlashScale;
        }

        public float Yaw => yaw;
        public Target CurrentTarget => target;
        public float Pitch => pitch;
        /// <summary>The recoiling gun (barrel axis at y = GunBoreY, muzzle at z = GunMuzzleZ).</summary>
        public Transform Barrel => gunT;

        bool InRange(Target t, WeaponDef w)
        {
            var d = t.Pos - player.Pos;
            if (Mathf.Abs(d.y) > Ground.LevelGap) return false;
            d.y = 0;
            return d.magnitude - t.Radius <= w.range + player.Radius + 0.6f;
        }

        /// <summary>Gun up to 20° above level (pitch is positive downward): the short stock and the grip clear the hood
        /// up to 21.5° at every yaw.</summary>
        public const float MaxUp = -20f;

        // Pitch limits against the yaw (degrees from the nose, + = to the right; pitch + = down, - = has to point up).
        // The gun sits on the right half of the hood, so the two sides differ. Measured on the car's meshes by the
        // "cannoncheck" capture and kept 1-2 degrees inside what it found (Tools/guntables.py builds them from its log):
        //  - the gun itself (barrel, receiver, stock, grip, handle): it may dip a little everywhere except over the blower;
        //  - firing (+ the muzzle flash at its largest and the round's straight launch run): over the blower to the
        //    left, over the windshield and the cab behind.
        static readonly float[] BarrelYaw = { -180f, -162f, -150f, -116f, -46f, -40f, -32f, -28f, -26f, 6f, 150f, 158f, 170f, 174f, 180f };
        static readonly float[] BarrelPitch = { 7.5f, 8f, 9.5f, 10f, 14.5f, 10.5f, 10.5f, 13.5f, 16f, 18.5f, 18f, 14.5f, 13.5f, 9.5f, 8f };
        static readonly float[] FireYaw = { -180f, -172f, -150f, -130f, -110f, -78f, -68f, -62f, -60f, -56f, -42f, -28f, -22f, -20f, -16f, -14f, -10f, 12f, 22f, 32f, 146f, 158f, 166f, 170f, 174f, 176f, 178f, 180f };
        static readonly float[] FirePitch = { -11.5f, -12.5f, -12f, -9f, 4.5f, 6.5f, 7f, 5.5f, -7f, -10f, -13.5f, -13.5f, -9f, -9f, -5.5f, 4.5f, 9.5f, 12.5f, 16.5f, 18.5f, 18.5f, 11.5f, 7.5f, 3.5f, -3.5f, -8.5f, -10.5f, -10.5f };

        static float Table(float[] yaws, float[] pitches, float yawDeg)
        {
            float a = Mathf.DeltaAngle(0f, yawDeg);
            if (a <= yaws[0]) return pitches[0];
            for (int i = 1; i < yaws.Length; i++)
                if (a <= yaws[i]) return Mathf.Lerp(pitches[i - 1], pitches[i], (a - yaws[i - 1]) / (yaws[i] - yaws[i - 1]));
            return pitches[pitches.Length - 1];
        }

        /// <summary>How far the gun may dip at a yaw without touching the car (degrees, + = down; - = must stay raised).</summary>
        public static float MaxDownBarrel(float yawDeg) => Table(BarrelYaw, BarrelPitch, yawDeg);

        /// <summary>The lowest pitch the gun fires from at a yaw: the flash and the round's launch run clear the car too.</summary>
        public static float FireLimit(float yawDeg) => Mathf.Min(Table(FireYaw, FirePitch, yawDeg), MaxDownBarrel(yawDeg));

        public static Vector3 AimPoint(Target t) => t.Pos + Vector3.up * Mathf.Clamp(t.BarHeight * 0.38f, 0.5f, 1.6f);

        /// <summary>World position of the muzzle (the flash hider's end).</summary>
        public Vector3 Muzzle => gunT.TransformPoint(new Vector3(0, Models.GunBoreY, Models.GunMuzzleZ + 0.02f));

        void Fire(WeaponDef w)
        {
            cooldown = w.interval;
            ShotsFired++;
            bool crit = Random.value < Balance.CritChance;
            double dmg = P.WeaponHitDamage(Slot) * (crit ? Balance.CritMul : 1f);
            var muzzle = Muzzle;
            var aim = AimPoint(target);
            var launch = gunT.forward;   // out along the barrel first, then onto the target

            var s = shellPool.Count > 0 ? shellPool.Pop() : NewShell();
            s.target = target; s.pos = muzzle; s.dir = launch; s.launchDir = launch; s.kink = muzzle;
            s.run = LaunchRun; s.turned = false; s.traveled = 0f;
            s.crit = crit; s.dmg = dmg; s.life = 0f;
            s.line.gameObject.SetActive(true);
            for (int k = 0; k < 3; k++) s.line.SetPosition(k, muzzle);
            shells.Add(s);

            recoil = 1f;
            ringPulse = 1f;
            flashT = 0.05f;
            flash.gameObject.SetActive(true);
            flash.localRotation = Quaternion.Euler(0, 0, Random.Range(0f, 360f));
            flash.localScale = Vector3.one * (FlashScale * Random.Range(0.85f, 1.15f));
            Game.I.fx.MuzzleSmoke(muzzle, launch, 0.35f);
            Game.I.sfx.Play(Sfx.Kind.Cannon, muzzle, 0.8f, 1.22f);   // the hood gun's report, lighter for the small calibre
            Game.I.cameraRig.Shake(0.05f);
            player.Jolt(-(aim - muzzle).normalized, 0.04f);
            EjectCasing();
            Game.I.focusTarget = target;
        }

        Shell NewShell()
        {
            var s = new Shell();
            var lr = new GameObject("Tracer").AddComponent<LineRenderer>();
            lr.positionCount = 3;
            lr.widthMultiplier = 0.1f;
            lr.sharedMaterial = tracerMat;
            lr.textureMode = LineTextureMode.Stretch;
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            lr.receiveShadows = false;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(new Color(1f, 0.55f, 0.15f), 0f), new GradientColorKey(new Color(1f, 0.95f, 0.75f), 1f) },
                      new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 1f) });
            lr.colorGradient = g;
            s.line = lr;
            return s;
        }

        void UpdateShells(float dt)
        {
            float homing = 1f - Mathf.Exp(-40f * dt);
            for (int i = shells.Count - 1; i >= 0; i--)
            {
                var s = shells[i];
                s.life += dt;
                bool alive = s.target != null && s.target.Targetable;
                float step = ShellSpeed * dt;
                bool hit = false;
                if (s.run > 0f)
                {
                    // the launch run: straight along the barrel, clear of the blower and the cab
                    float a = Mathf.Min(step, s.run);
                    s.pos += s.launchDir * a;
                    s.run -= a; s.traveled += a; step -= a;
                    if (s.run <= 0f)
                    {
                        s.turned = true;
                        s.kink = s.pos;
                        if (alive) s.dir = (AimPoint(s.target) - s.pos).normalized;
                    }
                }
                if (step > 0f)
                {
                    Vector3 goal = alive ? AimPoint(s.target) : s.pos + s.dir * 30f;
                    var d = goal - s.pos;
                    hit = alive && d.magnitude <= step;
                    if (hit) { s.traveled += d.magnitude; s.pos = goal; }
                    else
                    {
                        if (alive) s.dir = Vector3.Slerp(s.dir, d.normalized, homing);
                        s.pos += s.dir * step;
                        s.traveled += step;
                    }
                }
                DrawTracer(s);
                if (hit)
                {
                    Impact(s);
                    Recycle(s, i);
                }
                else if (s.life > 0.5f || s.pos.y < player.GroundY - 0.2f)
                {
                    if (s.pos.y < player.GroundY + 0.3f) Game.I.fx.Puff(new Vector3(s.pos.x, player.GroundY + 0.1f, s.pos.z), 0.3f);
                    Recycle(s, i);
                }
            }
        }

        /// <summary>The tracer follows the round's real path: along the barrel, then the bend toward the target.</summary>
        static void DrawTracer(Shell s)
        {
            float len = Mathf.Min(TracerLength, s.traveled);
            var head = s.pos;
            Vector3 p0, p1;
            float sinceKink = s.turned ? Vector3.Distance(head, s.kink) : 0f;
            if (s.turned && sinceKink < len)
            {
                p1 = s.kink;
                p0 = s.kink - s.launchDir * (len - sinceKink);
            }
            else
            {
                p0 = head - s.dir * len;
                p1 = Vector3.Lerp(p0, head, 0.5f);
            }
            s.line.SetPosition(0, p0);
            s.line.SetPosition(1, p1);
            s.line.SetPosition(2, head);
        }

        void Impact(Shell s)
        {
            var t = s.target;
            var point = s.pos;
            if (t != null && t.Targetable)
            {
                ShellHits++;
                t.Hit(s.dmg, s.crit, player.Pos);
                Game.I.sfx.Impact(t, point, s.crit);
            }
            Game.I.fx.ShellImpact(point, -s.dir, s.crit);
        }

        void Recycle(Shell s, int index)
        {
            s.line.gameObject.SetActive(false);
            s.target = null;
            shells.RemoveAt(index);
            shellPool.Push(s);
        }

        // ------------------------------------------------------------------ brass (small, out of the receiver's right side)
        void EjectCasing()
        {
            Casing c;
            if (casingPool.Count > 0) c = casingPool.Pop();
            else
            {
                if (casings.Count >= 18) return;
                c = new Casing { t = Models.MeshGO("Casing", Models.CasingMesh(), Mats.Toon, null, false).transform };
                c.t.localScale = Vector3.one * 0.42f;
            }
            c.t.gameObject.SetActive(true);
            c.t.position = gunT.TransformPoint(new Vector3(0.045f, Models.GunBoreY, 0.02f));
            c.t.rotation = Random.rotation;
            c.v = gunT.right * Random.Range(1.3f, 2.2f) + Vector3.up * Random.Range(1.8f, 2.6f) - gunT.forward * Random.Range(0.1f, 0.5f) + player.Velocity * 0.9f;
            c.spin = Random.insideUnitSphere * 900f;
            c.life = 0f;
            c.bounces = 0;
            casings.Add(c);
        }

        void UpdateCasings(float dt)
        {
            for (int i = casings.Count - 1; i >= 0; i--)
            {
                var c = casings[i];
                c.life += dt;
                c.v += Vector3.down * 14f * dt;
                var p = c.t.position + c.v * dt;
                float floor = Ground.Sample(p.x, p.z, c.t.position.y).h + 0.03f;
                if (p.y < floor)
                {
                    p.y = floor;
                    if (c.bounces < 2 && c.v.y < -0.8f)
                    {
                        if (c.bounces == 0) Game.I.sfx.Play(Sfx.Kind.Casing, p, 0.3f);
                        c.v = new Vector3(c.v.x * 0.5f, -c.v.y * 0.35f, c.v.z * 0.5f);
                        c.spin *= 0.5f;
                        c.bounces++;
                    }
                    else { c.v = new Vector3(c.v.x * 0.8f, 0f, c.v.z * 0.8f); c.spin *= 0.9f; }
                }
                c.t.position = p;
                c.t.Rotate(c.spin * dt, Space.World);
                if (c.life > 1.8f)
                {
                    c.t.gameObject.SetActive(false);
                    casings.RemoveAt(i);
                    casingPool.Push(c);
                }
            }
        }

        public void ClearAll()
        {
            for (int i = shells.Count - 1; i >= 0; i--) Recycle(shells[i], i);
        }

        void OnDestroy()
        {
            foreach (var s in shells) if (s.line != null) Destroy(s.line.gameObject);
            foreach (var s in shellPool) if (s.line != null) Destroy(s.line.gameObject);
            foreach (var c in casings) if (c.t != null) Destroy(c.t.gameObject);
            foreach (var c in casingPool) if (c.t != null) Destroy(c.t.gameObject);
            if (ring != null) Destroy(ring.gameObject);
        }
    }
}
