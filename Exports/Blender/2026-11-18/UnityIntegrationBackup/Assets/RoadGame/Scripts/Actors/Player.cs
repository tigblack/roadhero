using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    /// <summary>Vehicle tuning: planar rigid body with a tire model, RWD drivetrain and a sprung body for the visuals.</summary>
    public static class CarTuning
    {
        public const float Mass = 1450f;
        public const float YawInertia = 2350f;
        public const float CgToFront = 1.45f, CgToRear = 1.42f, WheelBase = 2.87f;
        public const float CgHeight = 0.55f;
        public const float MaxSteerLow = 38f, MaxSteerHigh = 14f;   // deg (speed sensitive)
        public const float SteerRate = 220f;                         // deg/s at the wheels
        public const float PeakSlip = 0.12f;                         // rad (~7°)
        public const float GripAsphalt = 1.08f, GripSand = 0.9f, GripSalt = 0.95f, GripMud = 0.8f;
        public const float BrakeDecel = 10.5f;                       // m/s² at full brake (grip permitting)
        public const float EngineBrake = 1.5f;                       // m/s² off-throttle at high rpm
        public const float DragLin = 60f, DragQuad = 7.5f;           // N/(m/s), N/(m/s)²
        public const float IdleRpm = 850f, RedlineRpm = 6600f, ShiftUpRpm = 6150f, ShiftDownRpm = 2500f;
        /// <summary>Accel (m/s²) available in each gear at peak torque, and the speed (m/s) at the shift-up rpm.</summary>
        public static readonly float[] GearAccel = { 6.0f, 4.9f, 3.9f, 3.1f };
        public static readonly float[] GearTopSpeed = { 4.6f, 7.9f, 11.2f, 15.8f };
        public const float ReverseAccel = 3.4f, ReverseTopSpeed = 5.2f;
        public const float TopSpeed = 13.6f;                          // used for UI / camera / effects scaling
        // vertical motion (ramps, jumps, tunnels): arcade gravity a bit above 1 g keeps jumps short and weighty
        public const float Gravity = 13.5f;
        public const float AirDrag = 0.08f;                           // 1/s, planar speed lost in the air
        public const float LandHard = 7.5f;                           // m/s vertical impact for the big landing response
    }

    /// <summary>
    /// The player's car. Joystick gives a desired direction + throttle; a driver model turns it into steering,
    /// throttle, brake and handbrake for a planar vehicle simulation (tire slip, weight transfer, wheelspin,
    /// gears). The body rides on a spring-damper suspension (pitch / roll / heave) over procedurally bumpy ground.
    /// Also: HP / regen / death, repair pad healing.
    /// </summary>
    public class Player : MonoBehaviour
    {
        public Rig rig;
        public Rigidbody body;
        public WeaponArm[] arms = new WeaponArm[4];
        public Turret turret;
        public Harpooner harpooner;

        public Vector3 Pos => transform.position;
        public float Radius => 1.25f;
        public bool Alive => !dead;
        public Vector3 Velocity => planarVel;
        public float Speed => planarVel.magnitude;
        public float ForwardSpeed => fwdSpeed;
        public float Heading => transform.eulerAngles.y;
        public bool OnRepairPad { get; private set; }

        // ---- vertical state (ramps, jumps, tunnels)
        public bool Airborne => !grounded;
        public float AirTime => grounded ? 0f : airTime;
        /// <summary>Height of the floor under the car (its own level), also while it flies.</summary>
        public float GroundY => groundBelowY;
        /// <summary>Smoothed height the camera follows: the floor, plus a little of the jump height.</summary>
        public float CameraY => camY;
        public bool Underground => groundBelowY < -1.5f || (groundPiece != null && groundPiece.underground);
        public FloorPiece GroundPiece => groundPiece;
        public float VerticalSpeed => grounded ? lastGroundVy : yVel;
        public int Landings { get; private set; }
        public float LastLandingImpact { get; private set; }
        public float MaxAirHeight { get; private set; }
        public event System.Action<float> Landed;            // impact speed (m/s)
        public event System.Action Recovered;
        /// <summary>The car was put back on its wheels after lying on its roof (see <see cref="RoofRecoverTime"/>).</summary>
        public event System.Action FlippedBack;

        // ---- tumble: flips off ledges and ramps, lying on the side or the roof, the automatic flip back
        /// <summary>Seconds on the roof (with ground contact) before the car is put back on its wheels.</summary>
        public const float RoofRecoverTime = 2f;
        const float WheelsAngle = 0.35f;       // rad: closer to upright than this the car stands on its wheels
        const float RoofAngle = 2.2f;          // rad (126 deg): further over than this it lies on its roof
        const float TipAngle = 1.75f;          // rad (100 deg): on the ground, less falls back onto the wheels, more onto the roof
        const float TumbleUpK = 30f, TumbleRoofK = 5f;   // rad/s^2: how hard it falls into either rest
        const float FlipDuration = 0.55f;
        /// <summary>Signed angle the car is turned over (deg): 0 on its wheels, +-180 on its roof.</summary>
        public float TumbleDeg => Wrap(tumbleAngle) * Mathf.Rad2Deg;
        /// <summary>On the ground and on its wheels (the tires drive, steer and brake).</summary>
        public bool WheelsDown => grounded && flipAnim < 0f && Mathf.Abs(Wrap(tumbleAngle)) < WheelsAngle;
        /// <summary>Lying on its roof with ground contact (the flip-back timer runs).</summary>
        public bool OnRoof => grounded && flipAnim < 0f && Mathf.Abs(Wrap(tumbleAngle)) > RoofAngle;
        /// <summary>Turned well over (in the air, on its side or roof, being flipped back): the weapons hold fire.</summary>
        public bool Upset => flipAnim >= 0f || Mathf.Abs(Wrap(tumbleAngle)) > 0.6f;
        public bool CanFight => !dead && !Upset;
        public float RoofTime => roofTimer;
        public bool FlippingBack => flipAnim >= 0f;
        public int FlipBacks { get; private set; }
        public int SelfRights { get; private set; }
        public int CrestJumps { get; private set; }
        /// <summary>Total rotation (deg) of the latest flight, and the biggest turn-over angle it reached.</summary>
        public float LastAirSpinDeg { get; private set; }
        public float LastAirMaxTumbleDeg { get; private set; }
        /// <summary>How the latest touch-down went: 0 = on the wheels, 1 = on the side (settles either way), 2 = on the roof.</summary>
        public int LastLandingKind { get; private set; }
        /// <summary>Test hook: capture scenes parked beyond the map edge (clean ground) skip the out-of-bounds recovery.</summary>
        public static bool AllowOutOfBounds;

        // ---- drivetrain / audio state
        public float Rpm => rpm;
        public float Throttle => throttleOut;
        public float Load => load;
        public int Gear => reverseMode ? -1 : gear + 1;
        public float WheelSpin => wheelSpin;
        public float Slide => slide;
        public bool OnAsphalt => onAsphalt;
        public int ShiftCount => shiftCount;

        Vector3 planarVel;
        float fwdSpeed;
        float steerDeg;           // actual front wheel angle
        float throttleOut, brakeOut;
        bool handbrake;
        bool reverseMode;
        float reverseTimer;
        int gear;
        float rpm = CarTuning.IdleRpm;
        float shiftTimer;
        int shiftCount;
        float load;
        float wheelSpin, slide;
        float axFilt, ayFilt;
        bool onAsphalt;
        float grip = CarTuning.GripSand;
        float rearSpinAngle, frontSpinAngle;
        float surfaceTimer;

        // ---- suspension (visual sprung body)
        float heave, heaveV, pitch, pitchV, roll, rollV;
        readonly float[] wheelBump = new float[4];
        readonly Vector3[] wheelBase = new Vector3[4];
        float squash;

        // ---- vertical
        Transform chassis;                 // body + wheels: tilts with the slope / in the air
        bool grounded = true;
        float yVel, lastGroundVy, airTime, lastCmdY;
        float groundBelowY;
        FloorPiece groundPiece;
        Vector3 groundNormal = Vector3.up;
        float pendingLanding = -1f;
        float camY, camYVel;
        float droop;
        Quaternion tilt = Quaternion.identity;
        float airPitch;
        float launchY, launchFloorY;
        Vector3 lastSafePos;
        float lastSafeYaw, safeTimer, lostTimer;
        bool recovering;

        // ---- tumble state
        /// <summary>The car turns over about its centre of mass.</summary>
        static readonly Vector3 TumblePivot = new Vector3(0f, 0.75f, 0f);
        /// <summary>Hull points (root frame, car upright): when it is not on its wheels the lowest one rests on the ground.</summary>
        static readonly Vector3[] Hull =
        {
            new Vector3(-1.02f, 0f, 1.45f), new Vector3(1.02f, 0f, 1.45f), new Vector3(-1.2f, 0f, -1.42f), new Vector3(1.2f, 0f, -1.42f),
            new Vector3(-1.02f, 0.76f, 1.45f), new Vector3(1.02f, 0.76f, 1.45f), new Vector3(-1.2f, 0.88f, -1.42f), new Vector3(1.2f, 0.88f, -1.42f),
            new Vector3(-1.04f, 0.3f, 2.37f), new Vector3(1.04f, 0.3f, 2.37f), new Vector3(-1.04f, 0.3f, -2.37f), new Vector3(1.04f, 0.3f, -2.37f),
            new Vector3(-1.0f, 0.86f, 2.3f), new Vector3(1.0f, 0.86f, 2.3f), new Vector3(-1.04f, 0.99f, -2.3f), new Vector3(1.04f, 0.99f, -2.3f),
            new Vector3(-0.75f, 1.33f, 0.55f), new Vector3(0.75f, 1.33f, 0.55f), new Vector3(-0.75f, 1.33f, -0.7f), new Vector3(0.75f, 1.33f, -0.7f),
        };
        static readonly Vector3[] WheelContact =
        {
            new Vector3(-0.86f, 0f, 1.45f), new Vector3(0.86f, 0f, 1.45f), new Vector3(-0.97f, 0f, -1.42f), new Vector3(0.97f, 0f, -1.42f)
        };
        Vector3 tumbleAxis = Vector3.right;    // horizontal axis in the root frame
        float tumbleAngle, tumbleRate;         // rad, rad/s about tumbleAxis
        Quaternion tumbleQ = Quaternion.identity;
        float bodyLift;                        // root height above the floor the current attitude needs (0 on the wheels)
        float roofTimer, upsetTimer, airSpin, airMaxTumble, roofSpell;
        bool wasOnRoof, crewHidden;
        float flipAnim = -1f;                  // 0..1 while the car is being flipped back onto its wheels
        Quaternion flipFrom = Quaternion.identity;
        static readonly Collider[] overlapBuf = new Collider[16];
        Collider[] ownCols;
        readonly List<Collider> ignoredLedges = new List<Collider>();
        public static int ObstacleMask => (1 << 0) | Ground.BlockerMask;

        bool dead;
        float deadTimer;
        float lastHurt = -99f;
        TrailRenderer[] ruts = new TrailRenderer[2];
        TrailRenderer[] skids = new TrailRenderer[2];
        readonly MeshFilter[] armorMF = new MeshFilter[2];
        readonly int[] armorShown = { -1, -1 };
        ParticleSystem dust, tireSmoke;
        ParticleSystem[] exhaust = new ParticleSystem[2];
        Progress P => Game.I.progress;

        public static Player Create(Vector3 pos, float yaw)
        {
            var go = Models.PlayerCar(out var rig);
            go.name = "PlayerCar";
            var p = go.AddComponent<Player>();
            p.rig = rig;
            go.transform.position = pos;
            go.transform.rotation = Quaternion.Euler(0, yaw, 0);

            var rb = go.AddComponent<Rigidbody>();
            rb.useGravity = false;
            rb.mass = CarTuning.Mass;
            rb.linearDamping = 0f;
            rb.angularDamping = 0f;
            rb.interpolation = RigidbodyInterpolation.Interpolate;
            rb.collisionDetectionMode = CollisionDetectionMode.ContinuousSpeculative;
            // height is driven by the script (floors, ramps, ballistic flight), so only the tilt axes are frozen
            rb.constraints = RigidbodyConstraints.FreezeRotationX | RigidbodyConstraints.FreezeRotationZ;
            rb.inertiaTensor = new Vector3(CarTuning.YawInertia, CarTuning.YawInertia, CarTuning.YawInertia);
            rb.inertiaTensorRotation = Quaternion.identity;
            p.body = rb;
            // collision shape of the pickup: the body up to the bed rails (with the rear haunches), the short cab on it
            var slide = new PhysicsMaterial("CarSlide") { dynamicFriction = 0f, staticFriction = 0f, frictionCombine = PhysicsMaterialCombine.Minimum, bounciness = 0.05f, bounceCombine = PhysicsMaterialCombine.Maximum };
            var col = go.AddComponent<BoxCollider>();
            col.size = new Vector3(2.08f, 0.74f, 4.75f);
            col.center = new Vector3(0, 0.62f, 0);
            col.sharedMaterial = slide;
            var cab = go.AddComponent<BoxCollider>();
            cab.size = new Vector3(1.5f, 0.36f, 1.32f);
            cab.center = new Vector3(0, 1.15f, -0.05f);
            cab.sharedMaterial = slide;
            rb.centerOfMass = new Vector3(0, 0.75f, 0);   // as with the old single box: the handling stays the same
            p.ownCols = new Collider[] { col, cab };

            // chassis = body + wheels: tilts as one piece on slopes and in the air (the root keeps a level yaw frame)
            p.chassis = new GameObject("Chassis").transform;
            p.chassis.SetParent(go.transform, false);
            rig.body.SetParent(p.chassis, false);
            foreach (var w in rig.wheels) w.parent.SetParent(p.chassis, false);

            // weapons: hood machine gun (slot 0), telescopic arms for the melee weapons (slots 1..3: the left fender, the
            // front corners of the bed rails)
            p.turret = Turret.Create(p, rig.body);
            var mounts = new[] { Vector3.zero, new Vector3(-0.8f, 0.97f, 0.66f), new Vector3(0.82f, 0.99f, -0.58f), new Vector3(-0.82f, 0.99f, -0.58f) };
            for (int i = 1; i < 4; i++) p.arms[i] = WeaponArm.Create(p, i, rig.body, mounts[i]);
            p.harpooner = Harpooner.Create(p, rig);

            for (int i = 0; i < 4 && i < rig.wheels.Count; i++) p.wheelBase[i] = rig.wheels[i].parent.localPosition;

            // tire tracks: sand ruts (always when moving off-road) + dark skid marks (when sliding)
            for (int i = 0; i < 2; i++)
            {
                float x = i == 0 ? -Models.CarRearTrack : Models.CarRearTrack;
                p.ruts[i] = MakeTrail(go.transform, new Vector3(x, 0.04f, Models.CarRearAxleZ), 0.34f, new Color(0.3f, 0.21f, 0.13f), 0.26f, 2.6f);
                p.skids[i] = MakeTrail(go.transform, new Vector3(x, 0.045f, Models.CarRearAxleZ), 0.3f, new Color(0.08f, 0.07f, 0.07f), 0.55f, 4.5f);
            }
            for (int i = 0; i < 2; i++)
            {
                var a = Models.MeshGO("Armor" + i, Models.CarArmorMesh(i, 0), Mats.Toon, rig.body);
                p.armorMF[i] = a.GetComponent<MeshFilter>();
                a.SetActive(false);
            }
            p.dust = Fx.MakeDust(go.transform, new Vector3(0, 0.25f, Models.CarRearAxleZ - 0.4f));
            p.tireSmoke = Fx.MakeTireSmoke(go.transform, new Vector3(0, 0.3f, Models.CarRearAxleZ));
            for (int i = 0; i < 2; i++) p.exhaust[i] = Fx.MakeExhaust(rig.body, Models.CarPipeTips[i] + new Vector3(0, 0, -0.05f));
            rig.CollectRenderers();
            rig.enabled = false;
            p.SnapToGround();
            return p;
        }

        /// <summary>Puts the car on the floor under its current position (spawn, teleport, recovery).</summary>
        void SnapToGround()
        {
            var pos = transform.position;
            var g = Ground.Sample(pos.x, pos.z, pos.y + 1.5f);
            if (g.valid) pos.y = g.h;
            transform.position = pos;
            if (body != null) body.position = pos;
            grounded = true;
            yVel = lastGroundVy = airTime = 0f;
            lastCmdY = pos.y;
            groundBelowY = pos.y;
            groundPiece = g.piece;
            groundNormal = g.valid ? g.normal : Vector3.up;
            camY = pos.y; camYVel = 0f;
            pendingLanding = -1f;
            droop = 0f; airPitch = 0f;
            tilt = Quaternion.identity;
            if (g.valid) { lastSafePos = pos; lastSafeYaw = transform.eulerAngles.y; }
            lostTimer = 0f;
            ResetTumble();
        }

        void ResetTumble()
        {
            tumbleAngle = tumbleRate = 0f;
            tumbleAxis = Vector3.right;
            tumbleQ = Quaternion.identity;
            bodyLift = 0f;
            roofTimer = upsetTimer = roofSpell = 0f;
            wasOnRoof = false;
            flipAnim = -1f;
            if (crewHidden) SetCrewHidden(false);
        }

        static TrailRenderer MakeTrail(Transform parent, Vector3 local, float width, Color c, float alpha, float time)
        {
            var t = new GameObject("Track").AddComponent<TrailRenderer>();
            t.transform.SetParent(parent, false);
            t.transform.localPosition = local;
            t.transform.localRotation = Quaternion.Euler(90, 0, 0);
            t.time = time;
            t.minVertexDistance = 0.35f;
            t.widthMultiplier = width;
            t.alignment = LineAlignment.TransformZ;
            t.sharedMaterial = Mats.TireTrack;
            t.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            t.receiveShadows = false;
            t.emitting = false;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(c, 0), new GradientColorKey(c, 1) },
                      new[] { new GradientAlphaKey(alpha, 0), new GradientAlphaKey(alpha * 0.7f, 0.5f), new GradientAlphaKey(0f, 1) });
            t.colorGradient = g;
            return t;
        }

        // ================================================================== physics
        void FixedUpdate()
        {
            if (Game.I == null || Game.I.progress == null) return;
            float dt = Time.fixedDeltaTime;
            var v = body.linearVelocity; v.y = 0;
            float r = body.angularVelocity.y;                       // rad/s, + = clockwise from above (turning right)
            float psi = body.rotation.eulerAngles.y * Mathf.Deg2Rad;

            UpdateSurface(dt);
            DriverInput(v, psi, r, dt, out float steerTarget);
            steerDeg = Mathf.MoveTowards(steerDeg, steerTarget, CarTuning.SteerRate * dt);

            if (WheelsDown)
            {
                const int Sub = 4;
                float h = dt / Sub;
                float spinAcc = 0f, slideAcc = 0f;
                float axSum = 0f, aySum = 0f;
                for (int s = 0; s < Sub; s++)
                {
                    Step(ref v, ref r, ref psi, h, out float spinNow, out float slideNow, out float ax, out float ay);
                    spinAcc += spinNow; slideAcc += slideNow; axSum += ax; aySum += ay;
                }
                wheelSpin = Mathf.Lerp(wheelSpin, spinAcc / Sub, 1f - Mathf.Exp(-12f * dt));
                slide = Mathf.Lerp(slide, slideAcc / Sub, 1f - Mathf.Exp(-10f * dt));
                axFilt = Mathf.Lerp(axFilt, axSum / Sub, 1f - Mathf.Exp(-8f * dt));
                ayFilt = Mathf.Lerp(ayFilt, aySum / Sub, 1f - Mathf.Exp(-8f * dt));
                // gravity along the slope: climbing costs speed, descending adds it
                if (groundNormal.y < 0.999f)
                {
                    var downhill = new Vector3(groundNormal.x, 0f, groundNormal.z);   // horizontal part of the normal points downhill
                    v += downhill * (CarTuning.Gravity * 0.75f * dt);
                }
            }
            else if (grounded)
            {
                // on its side or roof (or being flipped back): no tire forces, it scrapes along on the body to a stop
                float sp = v.magnitude;
                float dv = (5f + 1.8f * sp) * dt;
                v = sp > dv ? v * (1f - dv / sp) : Vector3.zero;
                r *= Mathf.Exp(-5f * dt);
                psi += r * dt;
                wheelSpin = Mathf.Lerp(wheelSpin, 0f, 1f - Mathf.Exp(-6f * dt));
                slide = Mathf.Lerp(slide, 0f, 1f - Mathf.Exp(-6f * dt));
                axFilt = Mathf.Lerp(axFilt, 0f, 1f - Mathf.Exp(-4f * dt));
                ayFilt = Mathf.Lerp(ayFilt, 0f, 1f - Mathf.Exp(-4f * dt));
            }
            else
            {
                // in the air: no tire forces, the car keeps its momentum; the spin of the body slowly settles
                v *= 1f - CarTuning.AirDrag * dt;
                r *= 1f - 1.2f * dt;
                psi += r * dt;
                wheelSpin = Mathf.Lerp(wheelSpin, 0f, 1f - Mathf.Exp(-6f * dt));
                slide = Mathf.Lerp(slide, 0f, 1f - Mathf.Exp(-6f * dt));
                axFilt = Mathf.Lerp(axFilt, 0f, 1f - Mathf.Exp(-4f * dt));
                ayFilt = Mathf.Lerp(ayFilt, 0f, 1f - Mathf.Exp(-4f * dt));
            }

            float vyCmd = VerticalStep(ref v, dt);
            TumbleStep(dt);
            SyncLedges();
            body.linearVelocity = new Vector3(v.x, vyCmd, v.z);
            body.angularVelocity = new Vector3(0, r, 0);
            planarVel = v;
            var fwd = new Vector3(Mathf.Sin(psi), 0, Mathf.Cos(psi));
            fwdSpeed = Vector3.Dot(v, fwd);
            UpdateDrivetrain(dt);
        }

        /// <summary>
        /// Height of the car for the coming physics step: it follows the floor it drives on (slopes, ramps, tunnels),
        /// takes off when the floor falls away faster than a step (a jump ramp's lip, a ledge) or, on natural terrain,
        /// curves down faster than gravity can follow (a hill's crest at speed), and flies ballistically until it meets
        /// its floor again. A car lying on its side or roof rests on its lowest hull point. Returns the vertical
        /// velocity to hand to the rigidbody.
        /// </summary>
        float VerticalStep(ref Vector3 v, float dt)
        {
            var pos = body.position;
            float bodyY = pos.y;
            // the floor logic runs on the height it commanded last step: contacts (a prop's rounded collider, a wall
            // edge) may nudge the body up or down a little, that noise is corrected below instead of being followed
            float y = lastCmdY;
            // something above stopped the last upward move (a ceiling): kill the climb
            if (!grounded && yVel > 0f && bodyY < lastCmdY - 0.05f) { yVel = 0f; y = bodyY; }
            var next = pos + v * dt;
            var gNext = Ground.Sample(next.x, next.z, y - bodyLift);
            float floorNext = gNext.valid ? gNext.h : Ground.Void;
            float rest = floorNext + bodyLift;            // where the root sits on that floor in the current attitude
            float yNew;
            if (grounded)
            {
                float drop = y - rest;
                bool lip = groundPiece != null && groundPiece.launch && gNext.piece != groundPiece && drop > 0.05f;
                float vyFloor = (rest - y) / dt;
                // natural terrain: over a crest the floor drops away faster than gravity pulls the car down -> it flies
                bool crest = !lip && drop <= Ground.StepUp && WheelsDown && gNext.valid
                             && ((groundPiece != null && groundPiece.crestAir) || (gNext.piece != null && gNext.piece.crestAir))
                             && lastGroundVy - vyFloor > CarTuning.Gravity * dt * 1.15f;
                if (drop > Ground.StepUp || lip || crest)
                {
                    // take-off: keep the vertical speed the slope was giving
                    launchFloorY = y - bodyLift;
                    grounded = false;
                    airTime = 0f;
                    launchY = y;
                    MaxAirHeight = 0f;
                    airSpin = 0f;
                    airMaxTumble = Mathf.Abs(Wrap(tumbleAngle));
                    yVel = crest ? lastGroundVy : Mathf.Max(lastGroundVy, 0f);
                    if (crest) CrestJumps++;
                    if (lip && groundPiece.boost > 0f)
                    {
                        // launch ramps guarantee a clean jump: minimum take-off speed along the ramp
                        var dir = groundPiece.rect.Forward;
                        float along = Vector3.Dot(v, dir);
                        if (along > 0.5f && along < groundPiece.boost)
                        {
                            v += dir * (groundPiece.boost - along);
                            float slope = Mathf.Max(0.05f, groundPiece.SlopeLocal(groundPiece.rect.half.y - 0.2f));
                            yVel = Mathf.Max(yVel, groundPiece.boost * slope);
                        }
                    }
                    if (lip) LipRoll(v);
                    else if (!crest) LedgeTumble(pos, v, y, floorNext);
                    yVel -= CarTuning.Gravity * dt;
                    yNew = y + yVel * dt;
                    if (yNew < rest) yNew = rest;
                }
                else
                {
                    yNew = rest;
                    lastGroundVy = vyFloor;
                    groundPiece = gNext.piece;
                    groundNormal = gNext.valid ? gNext.normal : Vector3.up;
                }
            }
            else
            {
                airTime += dt;
                yVel -= CarTuning.Gravity * dt;
                yNew = y + yVel * dt;
                MaxAirHeight = Mathf.Max(MaxAirHeight, y - floorNext);
                if (gNext.valid && yNew <= rest)
                {
                    pendingLanding = Mathf.Max(pendingLanding, -yVel);
                    yNew = rest;
                    grounded = true;
                    yVel = 0f;
                    lastGroundVy = 0f;
                    groundPiece = gNext.piece;
                    groundNormal = gNext.normal;
                    Touchdown();
                }
            }
            groundBelowY = floorNext > Ground.Void + 1f ? floorNext : groundBelowY;
            lastCmdY = yNew;
            return (yNew - bodyY) / dt;
        }

        // ================================================================== tumble (flips, roof, flip back)
        static float Wrap(float a) => Mathf.Repeat(a + Mathf.PI, 2f * Mathf.PI) - Mathf.PI;

        /// <summary>Lowest hull point (height above the root) with the car turned by q about its centre of mass.</summary>
        static float LowestPoint(Quaternion q)
        {
            float lo = float.MaxValue;
            for (int i = 0; i < Hull.Length; i++)
            {
                float y = (TumblePivot + q * (Hull[i] - TumblePivot)).y;
                if (y < lo) lo = y;
            }
            return lo;
        }

        /// <summary>Adds a turn-over rate (vector in the root frame, rad/s, horizontal axis).</summary>
        void AddTumble(Vector3 w)
        {
            w.y = 0f;
            float m = w.magnitude;
            if (m < 1e-3f) return;
            if (Mathf.Abs(Wrap(tumbleAngle)) < 0.15f && Mathf.Abs(tumbleRate) < 0.3f)
            {
                tumbleAxis = w / m;
                tumbleAngle = 0f;
                tumbleRate = m;
            }
            else tumbleRate += Vector3.Dot(w, tumbleAxis);
        }

        /// <summary>
        /// Driving off a ledge: the wheels still on the edge hold that side up while the rest drops, so the car starts
        /// to turn over toward the drop - a lot when it creeps off slowly, little at speed, nothing on a small step.
        /// </summary>
        void LedgeTumble(Vector3 pos, Vector3 v, float y, float floorBelow)
        {
            float h = y - floorBelow;
            float f = Mathf.Clamp01((h - 1.4f) / 4f);
            if (f <= 0f || Upset) return;
            Vector3 cu = Vector3.zero, cs = Vector3.zero;
            int nu = 0, ns = 0;
            var rot = body.rotation;
            for (int i = 0; i < WheelContact.Length; i++)
            {
                var wp = pos + rot * WheelContact[i];
                var g = Ground.Sample(wp.x, wp.z, y);
                if (!g.valid || g.h < y - 0.3f) { cu += WheelContact[i]; nu++; }
                else { cs += WheelContact[i]; ns++; }
            }
            if (nu == 0 || ns == 0) return;
            var d = cu / nu - cs / ns;
            d.y = 0f;
            if (d.sqrMagnitude < 1e-4f) return;
            d.Normalize();
            var vLocal = Quaternion.Inverse(rot) * v;
            float vd = Mathf.Max(1.5f, Vector3.Dot(vLocal, d));
            float k = Mathf.Lerp(4.5f, 6f, Mathf.Abs(d.z));
            float w = Mathf.Min(3.2f, k / vd) * f;
            // rotation that lowers the side over the drop: axis = up x d
            AddTumble(new Vector3(d.z, 0f, -d.x) * w);
            Debug.Log($"RoadGame TUMBLE ledge drop={h:0.0} v={vd:0.0} rate={w:0.00} dir={d}");
        }

        /// <summary>Hitting a jump ramp at an angle: one front wheel leaves the lip first and the car rolls a little in the air.</summary>
        void LipRoll(Vector3 v)
        {
            if (groundPiece == null || groundPiece.steady) return;
            var fwd = body.rotation * Vector3.forward;
            float dpsi = Vector3.SignedAngle(groundPiece.rect.Forward, fwd, Vector3.up) * Mathf.Deg2Rad;   // + = car turned right of the ramp
            float w = Mathf.Clamp(Mathf.Sin(dpsi) * 1.6f, -1.1f, 1.1f);
            if (Mathf.Abs(w) > 0.05f) AddTumble(new Vector3(0f, 0f, w));                                // + about +z lowers the left side
        }

        /// <summary>Touch-down with the car turned over: the hit takes some of the spin, then it settles either way.</summary>
        void Touchdown()
        {
            float a = Mathf.Abs(Wrap(tumbleAngle));
            LastAirSpinDeg = airSpin * Mathf.Rad2Deg;
            LastAirMaxTumbleDeg = airMaxTumble * Mathf.Rad2Deg;
            LastLandingKind = a < WheelsAngle ? 0 : a > RoofAngle ? 2 : 1;
            tumbleRate *= 0.75f;
            if (LastLandingKind != 0 || LastAirSpinDeg > 25f)
                Debug.Log($"RoadGame TUMBLE land kind={LastLandingKind} angle={TumbleDeg:0} rate={tumbleRate:0.00} spin={LastAirSpinDeg:0} maxAir={LastAirMaxTumbleDeg:0} at={Pos}");
        }

        void TumbleStep(float dt)
        {
            if (flipAnim >= 0f) { FlipBackStep(dt); return; }
            if (grounded)
            {
                float a = Wrap(tumbleAngle);
                if (Mathf.Abs(a) > 1e-4f || Mathf.Abs(tumbleRate) > 1e-4f)
                {
                    // the car falls into the nearer rest: back onto its wheels below the tipping angle, onto its roof above
                    float abs = Mathf.Abs(a), sgn = a >= 0f ? 1f : -1f;
                    float acc = abs < TipAngle ? -sgn * TumbleUpK * Mathf.Sin(Mathf.PI * abs / TipAngle)
                                               : sgn * TumbleRoofK * Mathf.Sin(Mathf.PI * (abs - TipAngle) / (Mathf.PI - TipAngle));
                    // balanced on the tipping edge: it goes back onto the wheels
                    if (Mathf.Abs(abs - TipAngle) < 0.04f && Mathf.Abs(tumbleRate) < 0.05f) acc = -sgn * 2f;
                    // settling into a rest is well damped; a car still rolling hard keeps rolling over
                    float damp = (abs < 0.35f || abs > Mathf.PI - 0.35f) && Mathf.Abs(tumbleRate) < 1.5f ? 7f : 0.8f;
                    tumbleRate += (acc - damp * tumbleRate) * dt;
                    float na = Wrap(a + tumbleRate * dt);
                    // thumping down onto the wheels takes most of the swing
                    if (abs < 1f && na * a < 0f) tumbleRate *= 0.3f;
                    tumbleAngle = na;
                    if (Mathf.Abs(na) < 0.01f && Mathf.Abs(tumbleRate) < 0.15f) { tumbleAngle = 0f; tumbleRate = 0f; }
                }
            }
            else
            {
                // free rotation in the air (a little drag)
                tumbleAngle = Wrap(tumbleAngle + tumbleRate * dt);
                tumbleRate *= 1f - 0.12f * dt;
                airSpin += Mathf.Abs(tumbleRate) * dt;
                airMaxTumble = Mathf.Max(airMaxTumble, Mathf.Abs(tumbleAngle));
            }
            tumbleQ = Mathf.Abs(tumbleAngle) < 1e-5f ? Quaternion.identity : Quaternion.AngleAxis(tumbleAngle * Mathf.Rad2Deg, tumbleAxis);
            bodyLift = -LowestPoint(tumbleQ);

            // roof down with ground contact: after a while it is put back on its wheels. Never in the air, never on
            // the wheels or a slope; going back onto the wheels by itself resets the timer.
            if (OnRoof)
            {
                roofTimer += dt;
                roofSpell = Mathf.Max(roofSpell, roofTimer);
                wasOnRoof = true;
            }
            else
            {
                if (wasOnRoof && WheelsDown)
                {
                    SelfRights++;
                    wasOnRoof = false;
                    Debug.Log($"RoadGame FLIP self-righted: back on the wheels after {roofSpell:0.00}s on the roof (timer reset) at={Pos}");
                    roofSpell = 0f;
                }
                roofTimer = 0f;
            }
            // safety net: not on the wheels for long (stuck on a side against something) -> also put it back
            upsetTimer = grounded && !WheelsDown && !dead ? upsetTimer + dt : 0f;
            if (!dead && (roofTimer >= RoofRecoverTime || upsetTimer > RoofRecoverTime + 3f)) StartFlipBack();
        }

        /// <summary>
        /// Puts the car back on its wheels where it lies (same place, the direction its nose shows) when that spot is
        /// safe; otherwise at the nearest safe spot around, or at the last stable position. HP and progress stay as they are.
        /// </summary>
        void StartFlipBack()
        {
            float tookRoof = roofTimer;
            roofTimer = upsetTimer = roofSpell = 0f;
            wasOnRoof = false;
            var nose = transform.rotation * (tumbleQ * Vector3.forward);
            nose.y = 0f;
            float heading = nose.sqrMagnitude > 0.04f ? Mathf.Atan2(nose.x, nose.z) * Mathf.Rad2Deg : Heading;
            var here = Pos;
            var worldAtt = transform.rotation * tumbleQ;
            bool moved = false;
            if (!FindSafeSpot(here, heading, out var spot))
            {
                moved = true;
                spot = lastSafePos;
                heading = lastSafeYaw;
                var g = Ground.Sample(spot.x, spot.z, spot.y + 0.5f);
                if (!g.valid)
                {
                    var st = World.I != null ? World.I.NearestStation(Pos, P.d.unlockedZone) : null;
                    spot = st != null ? st.pos : (World.I != null ? World.I.startPos : here);
                    heading = 0f;
                }
            }
            else moved = (new Vector2(spot.x - here.x, spot.z - here.z)).magnitude > 0.3f;
            if (moved) Game.I.fx?.Puff(here + Vector3.up * 0.5f, 1.6f);
            var rot = Quaternion.Euler(0f, heading, 0f);
            body.position = spot; transform.position = spot;
            body.rotation = rot; transform.rotation = rot;
            body.linearVelocity = Vector3.zero;
            body.angularVelocity = Vector3.zero;
            planarVel = Vector3.zero; fwdSpeed = 0f;
            var gs = Ground.Sample(spot.x, spot.z, spot.y + 0.5f);
            grounded = true;
            yVel = lastGroundVy = 0f;
            groundPiece = gs.piece;
            groundNormal = gs.valid ? gs.normal : Vector3.up;
            groundBelowY = gs.valid ? gs.h : spot.y;
            lastCmdY = groundBelowY;
            // the chassis keeps its attitude in the world for the first frame of the animation
            flipFrom = moved ? Quaternion.AngleAxis(180f, Vector3.forward) : Quaternion.Inverse(rot) * worldAtt;
            tumbleAngle = tumbleRate = 0f;
            flipAnim = 0f;
            FlipBacks++;
            Game.I.fx?.Puff(spot + Vector3.up * 0.4f, 1.4f);
            Game.I.sfx?.Play(Sfx.Kind.Crash, spot, 0.4f, 1.3f);
            Debug.Log($"RoadGame FLIP back after {tookRoof:0.00}s on the roof at={spot} from={here} heading={heading:0} moved={moved} hp={P.d.hp:0.0}");
            FlippedBack?.Invoke();
        }

        void FlipBackStep(float dt)
        {
            flipAnim += dt / FlipDuration;
            float t = Mathf.Clamp01(flipAnim);
            float s = t * t * (3f - 2f * t);
            tumbleQ = Quaternion.Slerp(flipFrom, Quaternion.identity, s);
            // it hops up while it turns over, then sets down on its wheels
            bodyLift = Mathf.Max(0f, -LowestPoint(tumbleQ)) + Mathf.Sin(t * Mathf.PI) * 0.9f;
            if (t >= 1f)
            {
                flipAnim = -1f;
                tumbleQ = Quaternion.identity;
                tumbleAngle = tumbleRate = 0f;
                bodyLift = 0f;
                squash = 0.7f;
                heaveV -= 1.2f;
                if (crewHidden) SetCrewHidden(false);
                Debug.Log($"RoadGame FLIP done on the wheels at={Pos} hp={P.d.hp:0.0}");
            }
        }

        bool FindSafeSpot(Vector3 from, float heading, out Vector3 spot)
        {
            float[] rings = { 0f, 1.5f, 3f, 4.5f, 6f, 8f, 10f };
            foreach (float d in rings)
            {
                int n = d <= 0f ? 1 : 12;
                for (int k = 0; k < n; k++)
                {
                    float a = (k / (float)n) * Mathf.PI * 2f;
                    var p = from + new Vector3(Mathf.Sin(a), 0f, Mathf.Cos(a)) * d;
                    if (SpotOk(p, heading, from.y, out float h)) { spot = new Vector3(p.x, h, p.z); return true; }
                }
            }
            spot = from;
            return false;
        }

        /// <summary>A spot where the car can stand on its wheels: one even floor under all four, no rock / wall / prop in the body.</summary>
        bool SpotOk(Vector3 p, float heading, float refY, out float h)
        {
            var g = Ground.Sample(p.x, p.z, refY + 0.6f);
            h = g.h;
            if (!g.valid || Mathf.Abs(g.h - refY) > 1.8f || g.normal.y < 0.87f) return false;
            if (g.piece != null && g.piece.launch) return false;
            var rot = Quaternion.Euler(0f, heading, 0f);
            for (int i = 0; i < WheelContact.Length; i++)
            {
                var wp = p + rot * WheelContact[i];
                var gw = Ground.Sample(wp.x, wp.z, g.h + 0.4f);
                if (!gw.valid || Mathf.Abs(gw.h - g.h) > 0.45f) return false;
            }
            int n = Physics.OverlapBoxNonAlloc(new Vector3(p.x, g.h + 0.82f, p.z), new Vector3(1.12f, 0.52f, 2.45f), overlapBuf, rot, ObstacleMask, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                var c = overlapBuf[i];
                if (c.attachedRigidbody == body || !c.enabled) continue;
                return false;
            }
            return true;
        }

        /// <summary>
        /// The ledges of the floor the car stands on (or took off from) do not collide with it: it drives off the edge
        /// freely and falls past them. Back on the ground, a ledge of another floor collides again once the car is clear
        /// of it (landed against a cliff's foot: the car is moved out of the face first).
        /// </summary>
        void SyncLedges()
        {
            if (ownCols == null) return;
            var owner = groundPiece;
            float floorY = grounded ? groundBelowY : launchFloorY;
            var p = body.position;
            for (int k = 0; k < Ground.Ledges.Count; k++)
            {
                var (c, own, top) = Ground.Ledges[k];
                if (c == null || ignoredLedges.Contains(c)) continue;
                if (!((owner != null && own == owner) || top <= floorY + 0.05f)) continue;
                if ((c.bounds.ClosestPoint(p) - p).sqrMagnitude > 144f) continue;
                foreach (var oc in ownCols) Physics.IgnoreCollision(oc, c, true);
                ignoredLedges.Add(c);
            }
            if (!grounded) return;
            for (int i = ignoredLedges.Count - 1; i >= 0; i--)
            {
                var c = ignoredLedges[i];
                if (c != null)
                {
                    var (own, top) = LedgeInfo(c);
                    if ((owner != null && own == owner) || top <= floorY + 0.05f) continue;    // still a ledge under this car
                }
                bool overlap = false;
                if (c != null)
                    foreach (var oc in ownCols)
                    {
                        if (!Physics.ComputePenetration(oc, body.position, body.rotation, c, c.transform.position, c.transform.rotation, out var dir, out float dist)) continue;
                        overlap = true;
                        dir.y = 0f;
                        if (dir.sqrMagnitude > 1e-4f)
                        {
                            var np = body.position + dir.normalized * Mathf.Min(dist + 0.03f, 1.5f);
                            body.position = np; transform.position = np;
                        }
                    }
                if (overlap) continue;
                if (c != null) foreach (var oc in ownCols) Physics.IgnoreCollision(oc, c, false);
                ignoredLedges.RemoveAt(i);
            }
        }

        static (FloorPiece owner, float top) LedgeInfo(Collider c)
        {
            foreach (var (lc, own, top) in Ground.Ledges) if (lc == c) return (own, top);
            return (null, float.MaxValue);
        }

        void ClearIgnoredLedges()
        {
            foreach (var c in ignoredLedges)
                if (c != null && ownCols != null) foreach (var oc in ownCols) Physics.IgnoreCollision(oc, c, false);
            ignoredLedges.Clear();
        }

        void SetCrewHidden(bool hide)
        {
            crewHidden = hide;
            if (harpooner != null) harpooner.SetCrewVisible(!hide);
        }

        /// <summary>Test hook: sets the car turning over (rad/s about a horizontal axis in the car's frame), e.g. a spin in the air.</summary>
        public void DebugTumble(Vector3 rate) => AddTumble(rate);

        /// <summary>Test hook: the car turned over by angleDeg about a horizontal axis of its own frame, turning at rate (rad/s).</summary>
        public void DebugSetTumble(float angleDeg, Vector3 axis, float rate)
        {
            axis.y = 0f;
            tumbleAxis = axis.sqrMagnitude > 1e-4f ? axis.normalized : Vector3.forward;
            tumbleAngle = Wrap(angleDeg * Mathf.Deg2Rad);
            tumbleRate = rate;
            tumbleQ = Quaternion.AngleAxis(tumbleAngle * Mathf.Rad2Deg, tumbleAxis);
            bodyLift = -LowestPoint(tumbleQ);
        }

        /// <summary>Test hook: lifts the car height metres above its floor, at rest, and lets it fall.</summary>
        public void DebugDrop(float height)
        {
            var p = body.position;
            p.y += height;
            body.position = p; transform.position = p;
            grounded = false;
            airTime = 0f; yVel = 0f; lastCmdY = p.y; launchY = p.y; MaxAirHeight = 0f;
            airSpin = 0f; airMaxTumble = Mathf.Abs(Wrap(tumbleAngle));
        }

        void UpdateSurface(float dt)
        {
            surfaceTimer -= dt;
            if (surfaceTimer > 0f || World.I == null) return;
            surfaceTimer = 0.15f;
            int zi = Content.ZoneIndexAt(Pos.z);
            // paved floors (tunnels, ramps, garages) grip like asphalt
            onAsphalt = (groundPiece != null && groundPiece.surface != SurfaceKind.Sand) || World.I.DistToRoads(zi, Pos) < 0.4f;
            float offroad = zi == 2 ? CarTuning.GripSalt : zi == 3 ? CarTuning.GripMud : CarTuning.GripSand;
            grip = onAsphalt ? CarTuning.GripAsphalt : offroad;
        }

        /// <summary>Driver model: joystick direction/magnitude -> steering, throttle, brake, handbrake, reverse.</summary>
        void DriverInput(Vector3 v, float psi, float r, float dt, out float steerTarget)
        {
            var fwd = new Vector3(Mathf.Sin(psi), 0, Mathf.Cos(psi));
            float u = Vector3.Dot(v, fwd);
            steerTarget = 0f;
            throttleOut = 0f; brakeOut = 0f; handbrake = false;
            if (dead) { brakeOut = 0.6f; reverseMode = false; return; }

            Vector2 input = Game.I.MoveInput;
            float mag = Mathf.Clamp01(input.magnitude);
            float speed01 = Mathf.Clamp01((Mathf.Abs(u) - 3f) / 11f);
            float maxSteer = Mathf.Lerp(CarTuning.MaxSteerLow, CarTuning.MaxSteerHigh, speed01);
            if (mag < 0.12f)
            {
                brakeOut = Mathf.Abs(u) > 0.3f ? 0.3f : 1f;
                reverseMode = false;
                return;
            }
            float want = Mathf.Atan2(input.x, input.y) * Mathf.Rad2Deg;          // joystick up = world +Z
            float err = Mathf.DeltaAngle(psi * Mathf.Rad2Deg, want);              // + = target is to the right
            float absErr = Mathf.Abs(err);
            float yawDeg = r * Mathf.Rad2Deg;

            // reverse (three-point turn) when the stick points behind a (nearly) stopped car
            if (!reverseMode && absErr > 128f && u < 2.0f) { reverseMode = true; reverseTimer = 0f; }
            if (reverseMode)
            {
                reverseTimer += dt;
                if (absErr < 62f || reverseTimer > 2.6f) reverseMode = false;
            }

            if (reverseMode)
            {
                // backing up: steer the opposite way so the nose swings toward the target direction
                steerTarget = Mathf.Clamp(-err * 0.9f, -CarTuning.MaxSteerLow, CarTuning.MaxSteerLow);
                if (u > 0.4f) brakeOut = 1f;
                else throttleOut = -mag;
                return;
            }

            // forward driving: PD steering toward the stick direction (yaw-rate damping = natural counter-steer)
            steerTarget = Mathf.Clamp(err * 0.85f - yawDeg * 0.11f, -maxSteer, maxSteer);
            float targetSpeed = CarTuning.TopSpeed * Mathf.Clamp01(mag * 1.15f);
            float turnLimit = absErr > 65f ? Mathf.Lerp(1f, 0.3f, (absErr - 65f) / 60f) : 1f;
            targetSpeed *= turnLimit;
            if (u < targetSpeed) throttleOut = Mathf.Clamp01((targetSpeed - u) * 0.45f + 0.35f) * Mathf.Clamp01(mag * 1.3f);
            else if (u > targetSpeed + 1.5f) brakeOut = Mathf.Clamp01((u - targetSpeed - 1.5f) * 0.18f);
            // on a climb the driver adds the throttle the slope takes away (even a light stick gets up a ramp)
            if (grounded && groundNormal.y < 0.999f && u < targetSpeed + 0.5f)
            {
                float uphill = -Vector3.Dot(new Vector3(groundNormal.x, 0f, groundNormal.z), fwd) * CarTuning.Gravity * 0.75f;
                if (uphill > 0f) throttleOut = Mathf.Clamp01(throttleOut + uphill / (CarTuning.GearAccel[gear] * 0.8f));
            }
            // the driver feathers the throttle when the rear tires break loose (short burnout, then they hook up)
            throttleOut *= 1f - Mathf.Clamp01(wheelSpin - 0.2f) * 0.75f;
            // big direction change at speed: handbrake turn - full lock, front wheels free, the rear steps out and swings round
            if (absErr > 95f && u > 6f)
            {
                handbrake = true;
                throttleOut = 0f;
                brakeOut = 0f;
                steerTarget = Mathf.Sign(err) * CarTuning.MaxSteerLow;
            }
            else if (absErr > 100f && u > 2.5f)
            {
                // slower: brake into a tight full-lock turn
                brakeOut = Mathf.Max(brakeOut, 0.35f);
                throttleOut *= 0.3f;
                steerTarget = Mathf.Sign(err) * CarTuning.MaxSteerLow;
            }
        }

        /// <summary>One integration step of the planar vehicle (bicycle model with tire saturation and friction circles).</summary>
        void Step(ref Vector3 v, ref float r, ref float psi, float dt, out float spin, out float slideAmt, out float axOut, out float ayOut)
        {
            float m = CarTuning.Mass, a = CarTuning.CgToFront, bR = CarTuning.CgToRear, L = CarTuning.WheelBase, hcg = CarTuning.CgHeight;
            var fwd = new Vector3(Mathf.Sin(psi), 0, Mathf.Cos(psi));
            var right = new Vector3(Mathf.Cos(psi), 0, -Mathf.Sin(psi));
            float u = Vector3.Dot(v, fwd), vl = Vector3.Dot(v, right);
            const float g = 9.81f;
            // loads with longitudinal weight transfer
            float fzF = Mathf.Max(800f, m * g * bR / L - m * axFilt * hcg / L);
            float fzR = Mathf.Max(800f, m * g * a / L + m * axFilt * hcg / L);
            float mu = grip;

            // ---- front axle
            float d = steerDeg * Mathf.Deg2Rad;
            float cd = Mathf.Cos(d), sd = Mathf.Sin(d);
            float vcR = vl + a * r, vcF = u;                         // contact velocity (right, fwd) at the front
            float vLonF = vcR * sd + vcF * cd, vLatF = vcR * cd - vcF * sd;
            float alphaF = Mathf.Atan2(vLatF, Mathf.Max(Mathf.Abs(vLonF), 1.0f));
            float latF = -mu * fzF * TireCurve(alphaF / CarTuning.PeakSlip);
            float brakeF = brakeOut * CarTuning.BrakeDecel * m * 0.6f;
            float lonF = -Mathf.Sign(vLonF) * Mathf.Min(brakeF, Mathf.Abs(vLonF) / dt * m * 0.5f);
            Friction(ref lonF, ref latF, mu * fzF, out _);

            // ---- rear axle (driven)
            float vLatR = vl - bR * r, vLonR = u;
            float alphaR = Mathf.Atan2(vLatR, Mathf.Max(Mathf.Abs(vLonR), 1.0f));
            float latR = -mu * fzR * TireCurve(alphaR / CarTuning.PeakSlip);
            float drive = DriveForce(u);
            float brakeRmax = brakeOut * CarTuning.BrakeDecel * m * 0.4f + (handbrake ? mu * fzR * 0.75f : 0f);
            float lonR = drive;
            if (brakeRmax > 0f) lonR += -Mathf.Sign(vLonR) * Mathf.Min(brakeRmax, Mathf.Abs(vLonR) / dt * m * 0.5f);
            // engine braking off-throttle
            if (Mathf.Abs(throttleOut) < 0.05f && Mathf.Abs(u) > 0.5f && !reverseMode)
                lonR -= Mathf.Sign(u) * CarTuning.EngineBrake * m * Mathf.Clamp01(rpm / CarTuning.RedlineRpm + 0.25f);
            Friction(ref lonR, ref latR, mu * fzR, out bool rearSliding);
            if (handbrake) latR *= 0.4f;
            spin = 0f;
            if (rearSliding && Mathf.Abs(drive) > 10f) spin = Mathf.Clamp01((Mathf.Abs(drive) - mu * fzR * 0.9f) / (mu * fzR * 0.45f) + 0.2f);

            // ---- sum forces in the car frame
            float fFwd = lonR + lonF * cd - latF * sd;
            float fRight = latR + lonF * sd + latF * cd;
            float drag = CarTuning.DragLin * Mathf.Abs(u) + CarTuning.DragQuad * u * u + (onAsphalt ? 0f : 160f * Mathf.Clamp01(Mathf.Abs(u)));
            fFwd -= Mathf.Sign(u) * drag;
            float yawM = a * (lonF * sd + latF * cd) - bR * latR;

            float axl = fFwd / m, ayl = fRight / m;
            v += (fwd * fFwd + right * fRight) / m * dt;
            r += yawM / CarTuning.YawInertia * dt;
            r *= 1f - 0.4f * dt;
            // low-speed settling (keeps a parked car from creeping)
            if (v.magnitude < 0.15f && Mathf.Abs(throttleOut) < 0.05f) { v *= 0.8f; r *= 0.8f; }
            psi += r * dt;
            axOut = axl;
            ayOut = ayl;                 // lateral accel of the CG in the car frame (centripetal in a steady turn)
            slideAmt = Mathf.Clamp01((Mathf.Abs(vLatR) - 1.2f) / 4f) * Mathf.Clamp01(Mathf.Abs(u) / 3f + Mathf.Abs(vl) / 3f);
        }

        static float TireCurve(float x)
        {
            float ax = Mathf.Abs(x);
            float y = (float)System.Math.Tanh(ax * 1.3f);
            float t = Mathf.Clamp01((ax - 1.2f) / 2.3f);
            y *= 1f - 0.2f * t * t * (3f - 2f * t);
            return Mathf.Sign(x) * y;
        }

        /// <summary>Friction circle: longitudinal force first, lateral gets what is left. Sliding drops grip.</summary>
        static void Friction(ref float lon, ref float lat, float max, out bool sliding)
        {
            sliding = false;
            if (Mathf.Abs(lon) > max * 0.98f)
            {
                lon = Mathf.Sign(lon) * max * 0.85f;
                sliding = true;
            }
            float latMax = Mathf.Sqrt(Mathf.Max(0f, max * max - lon * lon));
            if (sliding) latMax *= 0.55f;
            if (Mathf.Abs(lat) > latMax) lat = Mathf.Sign(lat) * latMax;
        }

        float DriveForce(float u)
        {
            if (Mathf.Abs(throttleOut) < 0.01f || shiftTimer > 0f) return 0f;
            if (throttleOut < 0f)
            {
                if (u < -CarTuning.ReverseTopSpeed) return 0f;
                return throttleOut * CarTuning.ReverseAccel * CarTuning.Mass;
            }
            float tq = Torque01(rpm);
            if (rpm > CarTuning.RedlineRpm) tq = 0f; // limiter
            return throttleOut * tq * CarTuning.GearAccel[gear] * CarTuning.Mass;
        }

        static float Torque01(float rpm)
        {
            float x = Mathf.Clamp01((rpm - 900f) / 5600f);
            return 0.74f + 0.26f * Mathf.Sin(x * Mathf.PI);
        }

        void UpdateDrivetrain(float dt)
        {
            float u = fwdSpeed;
            if (shiftTimer > 0f) shiftTimer -= dt;
            float wheelRpm;
            if (reverseMode || u < -0.5f)
                wheelRpm = Mathf.Abs(u) / CarTuning.ReverseTopSpeed * 5200f;
            else
                wheelRpm = Mathf.Max(0f, u) / CarTuning.GearTopSpeed[gear] * CarTuning.ShiftUpRpm;
            // clutch slip at launch / wheelspin flares the revs
            float slipRpm = 0f;
            if (Mathf.Abs(throttleOut) > 0.05f && gear == 0 && u < 3f) slipRpm = Mathf.Lerp(3400f, 0f, Mathf.Clamp01(u / 3f)) * Mathf.Abs(throttleOut);
            slipRpm = Mathf.Max(slipRpm, wheelSpin * 2600f);
            // in the air the driven wheels spin free: the engine flares on the throttle
            if (!WheelsDown) slipRpm = Mathf.Max(slipRpm, wheelRpm + Mathf.Abs(throttleOut) * 1800f);
            float target = Mathf.Max(CarTuning.IdleRpm, Mathf.Max(wheelRpm, slipRpm));
            if (dead) target = 0f;
            if (shiftTimer > 0f) target = Mathf.Min(target, rpm);
            float rate = target > rpm ? 9f : 6f;
            rpm = Mathf.Lerp(rpm, target, 1f - Mathf.Exp(-rate * dt));
            if (rpm > CarTuning.RedlineRpm + 150f) rpm = CarTuning.RedlineRpm + 150f;
            load = Mathf.Lerp(load, Mathf.Abs(throttleOut) * (shiftTimer > 0f ? 0.1f : 1f), 1f - Mathf.Exp(-14f * dt));

            // automatic gearbox
            if (!reverseMode && shiftTimer <= 0f && !dead)
            {
                if (gear < CarTuning.GearAccel.Length - 1 && wheelRpm > CarTuning.ShiftUpRpm && throttleOut > 0.2f && wheelSpin < 0.5f)
                {
                    gear++; shiftTimer = 0.16f; shiftCount++;
                }
                else if (gear > 0)
                {
                    float lowerRpm = Mathf.Max(0f, u) / CarTuning.GearTopSpeed[gear - 1] * CarTuning.ShiftUpRpm;
                    if (wheelRpm < CarTuning.ShiftDownRpm && lowerRpm < CarTuning.ShiftUpRpm * 0.9f) { gear--; shiftTimer = 0.1f; }
                }
            }
            if (reverseMode) gear = 0;
        }

        // ================================================================== frame update
        void Update()
        {
            if (Game.I == null || Game.I.progress == null) return;
            float dt = Time.deltaTime;
            UpdateCameraHeight(dt);
            if (dead)
            {
                deadTimer -= dt;
                if (deadTimer <= 0) Respawn();
                AnimateSuspension(dt);
                return;
            }
            if (pendingLanding >= 0f)
            {
                float impact = pendingLanding;
                pendingLanding = -1f;
                OnLanding(impact);
            }
            // Quasimodo lets go while the car lies on its side or roof, and climbs back once it is on its wheels
            bool hideCrew = flipAnim >= 0f ? flipAnim < 0.75f : (grounded && Mathf.Abs(Wrap(tumbleAngle)) > 1.3f);
            if (hideCrew != crewHidden)
            {
                SetCrewHidden(hideCrew);
                if (harpooner != null && harpooner.crewRoot != null) Game.I.fx?.Puff(harpooner.crewRoot.position, 0.9f);
            }
            UpdateRecovery(dt);

            // regen + repair pad
            var d = P.d;
            OnRepairPad = false;
            foreach (var s in World.I.stations)
            {
                var off = s.pos - Pos; off.y = 0;
                if (off.magnitude < s.radius && Mathf.Abs(Pos.y - s.pos.y) < 1.5f) { OnRepairPad = true; break; }
            }
            double heal = d.regen * dt;
            if (OnRepairPad) heal += d.maxHp * Balance.RepairHealFraction * dt;
            if (d.hp < d.maxHp) d.hp = System.Math.Min(d.maxHp, d.hp + heal);
            if (OnRepairPad && d.hp < d.maxHp && Random.value < dt * 10f) Game.I.fx.HealSparkle(Pos);

            AnimateSuspension(dt);
            AnimateEffects(dt);
        }

        /// <summary>The camera follows the floor smoothly; during a jump it rises only a little with the car.</summary>
        void UpdateCameraHeight(float dt)
        {
            float y = Pos.y;
            float goal = grounded ? y : groundBelowY + Mathf.Max(0f, y - groundBelowY) * 0.3f;
            camY = Mathf.SmoothDamp(camY, goal, ref camYVel, grounded ? 0.32f : 0.45f, 30f, dt);
        }

        /// <summary>Touch-down: suspension compression, dust from all wheels, a short jolt of the camera and a thud.</summary>
        void OnLanding(float impact)
        {
            Landings++;
            LastLandingImpact = impact;
            if (impact < 1.2f) { Landed?.Invoke(impact); return; }
            float k = Mathf.Clamp01(impact / CarTuning.LandHard);
            if (LastLandingKind != 0) k = Mathf.Max(k, 0.8f);        // on the side or the roof: a crash, whatever the speed
            heaveV -= 0.9f + k * 2.6f;                 // springs compress, then rebound
            pitchV += -airPitch * Mathf.Deg2Rad * 4f;   // the nose that hit first gets pushed back up
            squash = Mathf.Max(squash, 0.45f + k * 0.55f);
            var fx = Game.I.fx;
            if (fx != null)
            {
                for (int i = 0; i < 4 && i < rig.wheels.Count; i++)
                {
                    var wp = rig.wheels[i].parent.position;
                    fx.Puff(new Vector3(wp.x, Pos.y + 0.15f, wp.z), 0.55f + k * 0.9f);
                }
                if (k > 0.45f) fx.Ring(Pos + Vector3.up * 0.08f, 2.4f + k * 1.6f, new Color(1f, 0.92f, 0.78f, 0.55f), 0.45f);
            }
            if (Game.I.sfx != null) Game.I.sfx.Crash(Pos, 0.25f + k * 0.55f);
            if (Game.I.cameraRig != null) Game.I.cameraRig.Shake(0.08f + k * 0.22f);
            Landed?.Invoke(impact);
        }

        /// <summary>
        /// Keeps a recent safe spot (on a floor, not on a jump ramp) and puts the car back there if it ever leaves the
        /// playable world: falls below every floor, leaves the map bounds or stays without any floor under it.
        /// </summary>
        void UpdateRecovery(float dt)
        {
            var p = Pos;
            if (WheelsDown && (groundPiece == null || !groundPiece.launch) && groundNormal.y > 0.97f && !recovering)
            {
                safeTimer += dt;
                if (safeTimer > 0.6f && Speed < 15f && Mathf.Abs(p.x) < Content.ZoneHalfWidth - 2f)
                {
                    safeTimer = 0f;
                    lastSafePos = p;
                    lastSafeYaw = Heading;
                }
            }
            bool noFloor = groundBelowY < Ground.Void + 2f || !Ground.Sample(p.x, p.z, p.y + 0.5f).valid;
            lostTimer = noFloor ? lostTimer + dt : 0f;
            bool outOfBounds = !AllowOutOfBounds && (Mathf.Abs(p.x) > Content.ZoneHalfWidth + 6f || p.z < World.SouthLimit || p.z > Content.ZoneMaxZ(Content.ZoneCount - 1) + 6f);
            if (p.y < -16f || lostTimer > 1.2f || outOfBounds) Recover();
        }

        public void Recover()
        {
            var to = lastSafePos;
            var g = Ground.Sample(to.x, to.z, to.y + 0.5f);
            if (!g.valid || Mathf.Abs(to.x) > Content.ZoneHalfWidth)
            {
                var st = World.I.NearestStation(Pos, P.d.unlockedZone);
                to = st != null ? st.pos : World.I.startPos;
                lastSafeYaw = 0f;
            }
            Teleport(to, lastSafeYaw);
            Game.I.fx?.Puff(Pos + Vector3.up * 0.4f, 2f);
            Game.I.cameraRig?.Snap();
            Recovered?.Invoke();
            Debug.Log("RoadGame: car recovered to " + to);
        }

        /// <summary>Ground height bumps under a wheel (sand dunes/ripples off-road, almost smooth asphalt).</summary>
        float GroundBump(Vector3 wp)
        {
            float amp = onAsphalt ? 0.006f : 0.03f;
            float big = Mathf.PerlinNoise(wp.x * 0.13f + 31.7f, wp.z * 0.13f + 7.3f) - 0.5f;
            float mid = Mathf.PerlinNoise(wp.x * 0.55f + 3.1f, wp.z * 0.55f + 91.4f) - 0.5f;
            float fine = Mathf.PerlinNoise(wp.x * 1.9f + 17.7f, wp.z * 1.9f + 5.9f) - 0.5f;
            return big * amp * 2.6f + mid * amp * 1.4f + fine * amp * 0.7f;
        }

        void AnimateSuspension(float dt)
        {
            if (rig == null || rig.body == null) return;
            dt = Mathf.Min(dt, 0.05f);
            // chassis (body + wheels) follows the slope on the ground and the flight path in the air
            bool wheels = WheelsDown;
            if (chassis != null)
            {
                var ln = transform.InverseTransformDirection(grounded ? groundNormal : Vector3.up);
                var slopeRot = Quaternion.FromToRotation(Vector3.up, ln);
                float wantAirPitch = grounded ? 0f : Mathf.Clamp(-Mathf.Atan2(yVel, Mathf.Max(4f, Speed)) * Mathf.Rad2Deg * 0.55f, -15f, 15f);
                // the trajectory pitch is only a flourish on a level flight: it fades while the car turns over
                wantAirPitch *= Mathf.Clamp01(1f - Mathf.Abs(Wrap(tumbleAngle)) / 0.5f);
                airPitch = Mathf.Lerp(airPitch, wantAirPitch, 1f - Mathf.Exp(-(grounded ? 12f : 3.2f) * dt));
                tilt = Quaternion.Slerp(tilt, slopeRot, 1f - Mathf.Exp(-14f * dt));
                // flips turn the car about its centre of mass; on the ground it rests on its lowest point (bodyLift)
                chassis.localRotation = tilt * tumbleQ * Quaternion.Euler(airPitch, 0, 0);
                chassis.localPosition = tilt * (TumblePivot - tumbleQ * TumblePivot);
                droop = Mathf.MoveTowards(droop, wheels ? 0f : 0.11f, dt * (wheels ? 3f : 0.8f));
            }
            // ground under each wheel
            float hFL = 0, hFR = 0, hRL = 0, hRR = 0;
            for (int i = 0; i < 4 && i < rig.wheels.Count; i++)
            {
                var wp = transform.TransformPoint(wheelBase[i]);
                wheelBump[i] = wheels ? GroundBump(wp) : 0f;
            }
            // wheel order (see Models.PlayerCar): FL, FR, RL, RR
            hFL = wheelBump[0]; hFR = wheelBump[1]; hRL = wheelBump[2]; hRR = wheelBump[3];
            float trackW = Models.CarFrontTrack + Models.CarRearTrack;
            float heaveTarget = (hFL + hFR + hRL + hRR) * 0.25f;
            float pitchTarget = ((hFL + hFR) - (hRL + hRR)) * 0.5f / CarTuning.WheelBase;
            float rollTarget = ((hRR + hFR) - (hRL + hFL)) * 0.5f / trackW * -1f;   // + = right side down
            // inertial loads: squat / dive, body roll away from the turn, engine torque reaction
            pitchTarget += axFilt * 0.0046f;
            rollTarget += -ayFilt * 0.0072f;
            rollTarget += load * Torque01(rpm) * 0.012f * (gear == 0 ? 1.4f : 1f);
            // lumpy cam idle: the body rocks a little
            float idle = Mathf.Clamp01(1.4f - rpm / 1100f) * (dead ? 0f : 1f);
            rollTarget += Mathf.Sin(Time.time * 7.1f) * Mathf.Sin(Time.time * 2.3f) * 0.004f * idle;
            heaveTarget += Mathf.Sin(Time.time * 41f) * 0.0018f * Mathf.Clamp01(rpm / 3000f) * (dead ? 0f : 1f);

            int steps = Mathf.Max(1, Mathf.CeilToInt(dt / 0.008f));
            float h = dt / steps;
            const float wH = 11f, zH = 0.38f, wP = 10f, zP = 0.34f, wR = 12f, zR = 0.3f;
            for (int s = 0; s < steps; s++)
            {
                heaveV += (-wH * wH * (heave - heaveTarget) - 2f * zH * wH * heaveV) * h;
                heave += heaveV * h;
                pitchV += (-wP * wP * (pitch - pitchTarget) - 2f * zP * wP * pitchV) * h;
                pitch += pitchV * h;
                rollV += (-wR * wR * (roll - rollTarget) - 2f * zR * wR * rollV) * h;
                roll += rollV * h;
            }
            heave = Mathf.Clamp(heave, -0.1f, 0.1f);
            pitch = Mathf.Clamp(pitch, -0.09f, 0.09f);
            roll = Mathf.Clamp(roll, -0.11f, 0.11f);

            squash = Mathf.MoveTowards(squash, 0, dt * 4f);
            float k = 1f + Mathf.Sin(squash * Mathf.PI) * 0.06f;
            rig.body.localPosition = new Vector3(0, heave, 0);
            rig.body.localRotation = Quaternion.Euler(-pitch * Mathf.Rad2Deg, 0, -roll * Mathf.Rad2Deg);
            rig.body.localScale = new Vector3(k, 1f / k, k);

            // wheels: stay on the ground (the body moves over them), spin, steer
            float spinF = fwdSpeed / Models.CarFrontWheelR * Mathf.Rad2Deg * dt;
            float rearSurface = fwdSpeed + Mathf.Sign(throttleOut == 0 ? 1f : throttleOut) * wheelSpin * 9f;
            if (handbrake) rearSurface = 0f;
            float spinR = rearSurface / Models.CarRearWheelR * Mathf.Rad2Deg * dt;
            for (int i = 0; i < 4 && i < rig.wheels.Count; i++)
            {
                var pivot = rig.wheels[i].parent;
                pivot.localPosition = wheelBase[i] + new Vector3(0, wheelBump[i] - droop, 0);
                rig.wheels[i].Rotate(i < 2 ? spinF : spinR, 0, 0, Space.Self);
            }
            foreach (var st in rig.steer) st.localRotation = Quaternion.Euler(0, steerDeg, 0);
        }

        void AnimateEffects(float dt)
        {
            float spd = Speed;
            bool moving = spd > 1.5f;
            bool onGround = WheelsDown && airTime <= 0f;
            for (int i = 0; i < 2; i++)
            {
                ruts[i].emitting = onGround && moving && !onAsphalt;
                skids[i].emitting = onGround && (slide > 0.25f || wheelSpin > 0.35f) && spd > 0.8f;
            }
            var em = dust.emission;
            em.rateOverTime = !onGround ? 0f : onAsphalt ? (slide > 0.2f ? 6f : 0f) : (moving ? Mathf.Lerp(4f, 18f, spd / CarTuning.TopSpeed) + slide * 20f + wheelSpin * 16f : 0f);
            var sm = tireSmoke.emission;
            sm.rateOverTime = onGround && (wheelSpin > 0.2f || slide > 0.3f) ? Mathf.Lerp(0f, 32f, Mathf.Max(wheelSpin, slide)) * (onAsphalt ? 1.2f : 0.5f) : 0f;
            for (int i = 0; i < 2; i++)
            {
                var ex = exhaust[i].emission;
                ex.rateOverTime = 3f + load * 14f + rpm / 1000f;
            }
            // visible armor evolves with its level
            for (int i = 0; i < 2; i++)
            {
                int lvl = P.d.armorLevel[i];
                int tier = lvl <= 0 ? -1 : lvl >= 20 ? 3 : lvl >= 10 ? 2 : lvl >= 5 ? 1 : 0;
                if (tier == armorShown[i]) continue;
                armorShown[i] = tier;
                armorMF[i].gameObject.SetActive(tier >= 0);
                if (tier >= 0) { armorMF[i].sharedMesh = Models.CarArmorMesh(i, tier); squash = 1f; }
            }
        }

        /// <summary>Backfire on the overrun: called by the engine sound when it synthesizes a pop.</summary>
        public void Backfire()
        {
            if (dead || Game.I == null || Game.I.fx == null) return;
            for (int i = 0; i < 2; i++)
            {
                var tip = rig.body.TransformPoint(Models.CarPipeTips[i] + new Vector3(0, 0, -0.1f));
                Game.I.fx.Backfire(tip, -rig.body.forward + rig.body.right * (i == 0 ? 0.3f : -0.3f));
            }
        }

        public void Squash() { squash = 1f; }

        /// <summary>External jolt on the suspension (hits, collisions).</summary>
        public void Jolt(Vector3 worldDir, float strength)
        {
            var local = transform.InverseTransformDirection(worldDir);
            pitchV += -local.z * strength * 0.9f;
            rollV += local.x * strength * 1.1f;
            heaveV -= strength * 0.25f;
        }

        void OnCollisionEnter(Collision c)
        {
            if (dead || Game.I == null || Game.I.sfx == null) return;
            float hit = c.relativeVelocity.magnitude;
            if (hit < 2.5f) return;
            var n = c.contactCount > 0 ? c.GetContact(0).normal : -transform.forward;
            var p = c.contactCount > 0 ? c.GetContact(0).point : Pos;
            Jolt(-n, Mathf.Clamp(hit * 0.08f, 0.1f, 0.9f));
            Game.I.sfx.Crash(p, Mathf.Clamp01(hit / 12f));
            Game.I.cameraRig.Shake(Mathf.Clamp(hit * 0.025f, 0.05f, 0.3f));
            if (hit > 5f) Game.I.fx.Sparks(p + Vector3.up * 0.4f, false);
        }

        public void TakeDamage(double dmg, Vector3 from)
        {
            if (dead) return;
            dmg *= P.DamageTakenMul;
            P.d.hp -= dmg;
            lastHurt = Time.time;
            rig.Flash(0.06f);
            var dir = Pos - from; dir.y = 0;
            Jolt(dir.sqrMagnitude > 0.01f ? dir.normalized : transform.forward, 0.35f);
            Game.I.OnPlayerHurt(dmg, from);
            if (P.d.hp <= 0) Die();
        }

        void Die()
        {
            dead = true;
            P.d.hp = 0;
            deadTimer = 2.6f;
            Game.I.OnPlayerDied();
            rig.SetBurnt(true);
            foreach (var t in ruts) t.emitting = false;
            foreach (var t in skids) t.emitting = false;
            Jolt(Vector3.up, 1.2f);
        }

        void Respawn()
        {
            dead = false;
            var st = World.I.NearestStation(Pos, P.d.unlockedZone);
            var pos = st != null ? st.pos : World.I.startPos;
            Teleport(pos, 0f);
            P.d.hp = P.d.maxHp;
            rig.SetBurnt(false);
            Game.I.OnPlayerRespawned();
        }

        public void Teleport(Vector3 pos, float yaw)
        {
            body.position = pos;
            transform.position = pos;
            body.rotation = Quaternion.Euler(0, yaw, 0);
            transform.rotation = body.rotation;
            body.linearVelocity = Vector3.zero;
            body.angularVelocity = Vector3.zero;
            planarVel = Vector3.zero; fwdSpeed = 0f;
            gear = 0; rpm = CarTuning.IdleRpm; reverseMode = false; steerDeg = 0f;
            heave = heaveV = pitch = pitchV = roll = rollV = 0f;
            SnapToGround();
            if (chassis != null) { chassis.localRotation = Quaternion.identity; chassis.localPosition = Vector3.zero; }
            ClearIgnoredLedges();
            foreach (var t in ruts) t.Clear();
            foreach (var t in skids) t.Clear();
        }

        /// <summary>Test / capture hook: places the car with a given forward speed (m/s) along its heading.</summary>
        public void SetSpeed(float forward)
        {
            var v = transform.forward * forward; v.y = 0f;
            body.linearVelocity = v;
            planarVel = v; fwdSpeed = forward;
            if (forward > 4f) gear = forward > 11f ? 3 : forward > 7.9f ? 2 : 1;
        }
    }
}
