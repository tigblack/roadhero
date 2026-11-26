using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// The harpoon turret in the pickup bed and its hooded operator ("Quasimodo"). Every destroyed target is harpooned
    /// and reeled into the car, which is when its permanent stat reward is granted (the reference's "devour" moment).
    /// The turret turns on its column toward the next wreck - the operator walks round the column with it, holding the
    /// two rear handles - and fires only once it points at the wreck. The launcher pitches and recoils; the operator's
    /// body leans from the hips against the car's acceleration and the recoil, breathes, bobs its head and steps when the
    /// turret turns fast, and the arms are re-solved every frame so the hands never let go of the handles.
    /// </summary>
    public class Harpooner : MonoBehaviour
    {
        class Shot
        {
            public Target target;
            public Transform head;
            public LineRenderer rope, ropeHi;
            public int phase;            // 0 = flying out, 1 = reeling in
            public Vector3 headPos;
            public Vector3 wreckStart;
            public Quaternion wreckRot;
            public Vector3 wreckScale;
            public float reel;
            public float spin;
        }

        Player player;
        Models.HarpoonerRig rig;
        Transform turret, gun, muzzle, gunTip;
        Vector3 prevPos, prevVel, accel;
        bool hasPrev;
        float leanPitch, leanRoll, leanPitchVel, leanRollVel;
        readonly Queue<Target> queue = new Queue<Target>();
        readonly List<Shot> shots = new List<Shot>();
        readonly Stack<Shot> pool = new Stack<Shot>();
        float fireCooldown;
        float yaw, yawVel, lastYaw;
        float recoil;
        float stepPhase, stepAmount;
        const int MaxShots = 4;
        /// <summary>Turret turn: smoothing time (s) and top speed (deg/s). It fires once within FireCone of the wreck.</summary>
        const float TurnSmooth = 0.11f, TurnMaxSpeed = 420f, FireCone = 8f;

        /// <summary>Harpoons fired, wrecks reeled in and the worst aim error at a shot (deg) since start (test telemetry).</summary>
        public static int Fired, Reeled;
        public static float WorstFireError;
        public static void ResetStatics() { Fired = 0; Reeled = 0; WorstFireError = 0f; }

        public int Pending => queue.Count + shots.Count;
        public Models.HarpoonerRig Rig => rig;
        /// <summary>The operator; he lets go while the car lies on its side or roof.</summary>
        public Transform crewRoot => rig != null ? rig.crew : null;
        public void SetCrewVisible(bool on) { if (rig != null && rig.crew != null) rig.crew.gameObject.SetActive(on); }
        /// <summary>Turret yaw on the car (0 = over the cab, 180 = over the tailgate).</summary>
        public float Yaw => Mathf.DeltaAngle(0f, yaw);

        /// <summary>Test / capture helper: puts the turret, the launcher and the operator into a given pose right now.</summary>
        public void PoseForCapture(float localYaw, float recoilAmount)
        {
            yaw = lastYaw = localYaw;
            yawVel = 0f;
            recoil = recoilAmount;
            turret.localRotation = Quaternion.Euler(0, yaw, 0);
            PoseGun();
            rig.body.localRotation = Quaternion.Euler(-recoil * 7f, 0, 0);
            rig.body.localPosition = rig.bodyRest;
            rig.head.localRotation = Quaternion.Euler(recoil * 4f, 0, 0);
            for (int i = 0; i < 2; i++) rig.leg[i].localRotation = Quaternion.identity;
            Models.SolveHarpoonerArms(rig);
        }

        void PoseGun()
        {
            gun.localRotation = Quaternion.Euler(Models.HarpoonRestPitch - recoil * 12f, 0, 0);
            gun.localPosition = rig.gunRest + new Vector3(0, recoil * 0.012f, -recoil * 0.08f);
        }

        public static Harpooner Create(Player p, Rig carRig)
        {
            var r = Models.Harpooner(carRig.body);
            var h = r.root.gameObject.AddComponent<Harpooner>();
            h.player = p;
            h.rig = r;
            h.turret = r.yaw;
            h.gun = r.gun;
            h.muzzle = r.muzzle;
            h.gunTip = r.tip;
            return h;
        }

        public void Enqueue(Target t)
        {
            if (t != null) queue.Enqueue(t);
        }

        void Update()
        {
            if (Game.I == null || player == null) return;
            float dt = Time.deltaTime;
            fireCooldown -= dt;
            recoil = Mathf.MoveTowards(recoil, 0, dt * 4f);

            // aim: first queued wreck, else the one being reeled in, else the weapons' focus target, else ahead
            Vector3? aimAt = null;
            while (queue.Count > 0 && (queue.Peek() == null || !queue.Peek().gameObject.activeInHierarchy)) queue.Dequeue();
            // a wreck on another level (the car went into a tunnel) or behind a wall waits; take one in reach first
            for (int k = queue.Count; k > 0 && queue.Count > 0 && !Reachable(queue.Peek()); k--) queue.Enqueue(queue.Dequeue());
            bool headOk = queue.Count > 0 && Reachable(queue.Peek());
            if (headOk) aimAt = queue.Peek().Pos;
            else if (shots.Count > 0) aimAt = shots[shots.Count - 1].headPos;
            else if (Game.I.focusTarget != null && Game.I.focusTarget.Targetable) aimAt = Game.I.focusTarget.Pos;

            float wantLocal;
            if (aimAt.HasValue)
            {
                var local = turret.parent.InverseTransformPoint(aimAt.Value) - turret.localPosition;
                wantLocal = Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;
            }
            else wantLocal = Mathf.Sin(Time.time * 0.45f) * 28f;   // at rest the harpoon looks ahead over the cab
            yaw = Mathf.SmoothDampAngle(yaw, wantLocal, ref yawVel, TurnSmooth, TurnMaxSpeed, dt);
            turret.localRotation = Quaternion.Euler(0, yaw, 0);
            PoseGun();

            // fire once the turret points at the wreck
            float err = Mathf.Abs(Mathf.DeltaAngle(yaw, wantLocal));
            if (headOk && shots.Count < MaxShots && fireCooldown <= 0f && err < FireCone && player.CanFight)
            {
                var t = queue.Dequeue();
                if (t != null && t.gameObject.activeInHierarchy && !t.beingEaten)
                {
                    Fire(t);
                    WorstFireError = Mathf.Max(WorstFireError, err);
                }
            }

            for (int i = shots.Count - 1; i >= 0; i--) UpdateShot(shots[i], dt, i);
            gunTip.gameObject.SetActive(shots.Count == 0);
        }

        /// <summary>Body language, steps and arms, after the turret has been posed for this frame.</summary>
        void LateUpdate()
        {
            if (rig == null) return;
            float dt = Mathf.Max(1e-4f, Time.deltaTime);
            // car acceleration seen from the operator (smoothed); inertia tips the body the other way
            var p = turret.position;
            if (hasPrev && Time.deltaTime > 0f)
            {
                var v = (p - prevPos) / dt;
                var a = (v - prevVel) / dt;
                a.y = 0f;
                if (a.sqrMagnitude > 2500f) a = a.normalized * 50f;   // teleports / respawns
                accel = Vector3.Lerp(accel, a, 1f - Mathf.Exp(-dt * 5f));
                prevVel = v;
            }
            prevPos = p;
            hasPrev = true;
            var la = turret.InverseTransformDirection(accel);
            float wantPitch = Mathf.Clamp(-la.z * 0.8f, -8f, 8f) - recoil * 7f;
            float wantRoll = Mathf.Clamp(la.x * 0.8f, -7f, 7f);
            leanPitch = Mathf.SmoothDamp(leanPitch, wantPitch, ref leanPitchVel, 0.12f, Mathf.Infinity, dt);
            leanRoll = Mathf.SmoothDamp(leanRoll, wantRoll, ref leanRollVel, 0.14f, Mathf.Infinity, dt);

            // steps: he walks round the column while the turret turns
            float walk = Mathf.Abs(Mathf.DeltaAngle(lastYaw, yaw)) / dt * Mathf.Deg2Rad * Models.HarpoonCrewBack;   // m/s
            lastYaw = yaw;
            stepAmount = Mathf.MoveTowards(stepAmount, Mathf.Clamp01(walk / 0.7f), dt * 5f);
            stepPhase += Mathf.PI * Mathf.Max(walk, stepAmount * 0.6f) / 0.3f * dt;
            for (int i = 0; i < 2; i++)
            {
                float lift = Mathf.Max(0f, Mathf.Sin(stepPhase + i * Mathf.PI)) * stepAmount;
                rig.leg[i].localRotation = Quaternion.Euler(-lift * 22f, 0f, 0f);
            }

            float t = Time.time;
            float breathe = Mathf.Sin(t * 2.1f);
            float bob = stepAmount * Mathf.Abs(Mathf.Sin(stepPhase)) * 0.018f;
            rig.body.localRotation = Quaternion.Euler(leanPitch + breathe * 0.8f, 0f, leanRoll);
            rig.body.localPosition = rig.bodyRest + new Vector3(0f, breathe * 0.006f + bob, 0f);
            rig.head.localRotation = Quaternion.Euler(-leanPitch * 0.4f + Mathf.Sin(t * 1.3f) * 2f + recoil * 4f, Mathf.Sin(t * 0.55f) * 6f, -leanRoll * 0.3f);
            Models.SolveHarpoonerArms(rig);
        }

        bool Reachable(Target t)
        {
            if (t == null) return false;
            if (!Ground.SameLevel(t.Pos, player.Pos)) return false;
            return !Ground.Blocked(muzzle.position, t.Pos + Vector3.up * 0.6f);
        }

        void Fire(Target t)
        {
            var s = pool.Count > 0 ? pool.Pop() : NewShot();
            s.target = t;
            s.phase = 0;
            s.reel = 0;
            s.headPos = muzzle.position;
            s.spin = Random.Range(-540f, 540f);
            s.head.gameObject.SetActive(true);
            s.rope.gameObject.SetActive(true);
            s.ropeHi.gameObject.SetActive(true);
            shots.Add(s);
            fireCooldown = 0.11f;
            recoil = 1f;
            Fired++;
            Game.I.sfx.Play(Sfx.Kind.Harpoon, muzzle.position, 0.7f);
        }

        Shot NewShot()
        {
            var s = new Shot();
            s.head = Models.MeshGO("HarpoonHead", Models.HarpoonHeadMesh(), Mats.Toon, null, false).transform;
            s.head.localScale = Vector3.one * 2.3f;
            // two-tone rope: a dark core with a light strand on top reads on pale sand and on dark asphalt alike
            s.rope = NewRope("Rope", 0.2f, new Color(0.22f, 0.15f, 0.1f, 1f), 0);
            s.ropeHi = NewRope("RopeHi", 0.08f, new Color(0.95f, 0.88f, 0.7f, 1f), 1);
            return s;
        }

        static LineRenderer NewRope(string name, float width, Color c, int order)
        {
            var lr = new GameObject(name).AddComponent<LineRenderer>();
            lr.positionCount = 6;
            lr.widthMultiplier = width;
            lr.sharedMaterial = Mats.Rope;
            lr.startColor = lr.endColor = c;
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            lr.receiveShadows = false;
            lr.numCapVertices = 2;
            lr.sortingOrder = order;
            return lr;
        }

        void UpdateShot(Shot s, float dt, int index)
        {
            var t = s.target;
            bool targetOk = t != null && t.gameObject.activeInHierarchy;
            Vector3 mpos = muzzle.position;
            if (s.phase == 0)
            {
                if (!targetOk) { Recycle(s, index); return; }
                var goal = t.Pos + Vector3.up * Mathf.Min(1.0f, t.BarHeight * 0.35f);
                var d = goal - s.headPos;
                float step = Balance.HarpoonSpeed * dt;
                if (d.magnitude <= step + 0.2f)
                {
                    s.headPos = goal;
                    s.phase = 1;
                    s.reel = 0;
                    t.beingEaten = true;
                    s.wreckStart = t.transform.position;
                    s.wreckRot = t.transform.rotation;
                    s.wreckScale = t.transform.localScale;
                    Game.I.fx.HookHit(goal);
                    Game.I.sfx.Play(Sfx.Kind.Hook, t.Pos, 0.8f);
                    Game.I.sfx.Play(Sfx.Kind.Reel, muzzle.position, 0.8f);
                }
                else s.headPos += d.normalized * step;
                s.head.position = s.headPos;
                s.head.rotation = Quaternion.LookRotation(d.sqrMagnitude > 0.0001f ? d.normalized : Vector3.forward);
            }
            else
            {
                if (!targetOk) { Recycle(s, index); return; }
                float dist = (mpos - s.wreckStart).magnitude;
                float reelTime = Mathf.Clamp(Balance.HarpoonReelTime + dist * 0.012f, 0.25f, 0.6f);
                s.reel += dt / reelTime;
                float k = Mathf.Clamp01(s.reel);
                float e = k * k * (3f - 2f * k);
                var p = Vector3.Lerp(s.wreckStart, mpos, e) + Vector3.up * Mathf.Sin(k * Mathf.PI) * (1.2f + dist * 0.08f);
                t.transform.position = p;
                t.transform.rotation = s.wreckRot * Quaternion.Euler(0, s.spin * k, s.spin * 0.3f * k);
                t.transform.localScale = s.wreckScale * Mathf.Lerp(1f, 0.12f, k * k);
                s.headPos = p + Vector3.up * 0.3f;
                s.head.position = s.headPos;
                var dir = mpos - s.headPos;
                if (dir.sqrMagnitude > 0.0001f) s.head.rotation = Quaternion.LookRotation(-dir.normalized);
                if (k >= 1f)
                {
                    Reeled++;
                    Game.I.OnTargetEaten(t);
                    t.OnEaten();
                    Recycle(s, index);
                    return;
                }
            }
            // rope with a little sag
            var a = mpos; var b = s.headPos;
            float len = (b - a).magnitude;
            for (int i = 0; i < s.rope.positionCount; i++)
            {
                float u = i / (float)(s.rope.positionCount - 1);
                var p = Vector3.Lerp(a, b, u);
                p.y -= Mathf.Sin(u * Mathf.PI) * Mathf.Min(1.2f, len * 0.06f) * (s.phase == 0 ? 0.4f : 1f);
                s.rope.SetPosition(i, p);
                s.ropeHi.SetPosition(i, p + Vector3.up * 0.03f);
            }
        }

        void Recycle(Shot s, int index)
        {
            s.head.gameObject.SetActive(false);
            s.rope.gameObject.SetActive(false);
            s.ropeHi.gameObject.SetActive(false);
            s.target = null;
            shots.RemoveAt(index);
            pool.Push(s);
        }

        public void ClearAll()
        {
            queue.Clear();
            for (int i = shots.Count - 1; i >= 0; i--)
            {
                var s = shots[i];
                if (s.target != null && s.phase == 1) { s.target.OnEaten(); }
                Recycle(s, i);
            }
        }

        void OnDestroy()
        {
            foreach (var s in shots) DestroyShot(s);
            foreach (var s in pool) DestroyShot(s);
        }

        static void DestroyShot(Shot s)
        {
            if (s.head != null) Destroy(s.head.gameObject);
            if (s.rope != null) Destroy(s.rope.gameObject);
            if (s.ropeHi != null) Destroy(s.ropeHi.gameObject);
        }
    }
}
