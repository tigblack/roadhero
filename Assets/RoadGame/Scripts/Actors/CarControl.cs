using UnityEngine;

namespace RoadGame
{
    // The car is driven in three explicit layers:
    //   1. input   - a stick vector in world XZ (touch joystick turned by the camera yaw, keyboard, a test script or
    //                the autopilot all hand the same thing to Game.MoveInput), filtered by StickFilter;
    //   2. intent  - CarDriver reads it as "travel that way, this much", ahead or behind the car (with hysteresis);
    //   3. commands - throttle, brake, steering angle and gear direction for the vehicle simulation in Player.
    // The stick always means a direction on the screen; there is no hidden "vertical = pedal, horizontal = wheel" mode.

    /// <summary>Which way the drivetrain pushes. The driver chooses it; it changes only when the car is almost stopped.</summary>
    public enum DriveGear { Forward = 1, Reverse = -1 }

    /// <summary>A stick after the radial dead zone: unit direction (stick XY = world XZ) and an amount 0..1.</summary>
    public struct StickInput
    {
        public Vector2 dir;
        public float amount;
        public bool Active => amount > 0f;
    }

    /// <summary>What the driver wants from the stick.</summary>
    public struct DriverIntent
    {
        /// <summary>World travel direction asked for (deg, 0 = +Z, clockwise from above).</summary>
        public float wantDeg;
        /// <summary>0..1 after the dead zone and the response curve.</summary>
        public float amount;
        /// <summary>The stick asks to travel behind the car (held with hysteresis).</summary>
        public bool backward;
        /// <summary>Signed angle from the travelling axis (the nose, or the tail in reverse) to the stick, + = clockwise.</summary>
        public float errDeg;
    }

    /// <summary>The commands that reach the car.</summary>
    public struct DriveCommands
    {
        /// <summary>0..1 pedal positions.</summary>
        public float throttle, brake;
        /// <summary>Front wheel angle the driver asks for (deg, + = right); the steering rack moves there at its own rate.</summary>
        public float steerDeg;
        public DriveGear gear;
        public bool handbrake;
        /// <summary>Throttle with the drivetrain's sign: negative pushes the car backwards.</summary>
        public float SignedThrottle => gear == DriveGear.Reverse ? -throttle : throttle;
    }

    /// <summary>The car state the driver reads every physics step.</summary>
    public struct CarSense
    {
        public float headingDeg;
        /// <summary>Speed along the nose (m/s), negative when rolling backwards.</summary>
        public float forwardSpeed;
        /// <summary>Yaw rate (deg/s), + = clockwise from above.</summary>
        public float yawRateDeg;
        /// <summary>Gravity along the nose on a slope (m/s^2): + = the slope pulls the car forward.</summary>
        public float slopeAccel;
        /// <summary>Acceleration the current gear gives at full throttle (m/s^2).</summary>
        public float gearAccel;
        public float wheelSpin;
        public bool dead;
    }

    /// <summary>Radial dead zone and response curve for every stick source (the same numbers for touch, keys and scripts).</summary>
    public static class StickFilter
    {
        /// <summary>Stick length below which nothing happens (a resting thumb, jitter).</summary>
        public const float DeadZone = 0.1f;
        /// <summary>Response curve on the rescaled length (1 = proportional: the deflection maps evenly onto speed, with
        /// a creep right outside the dead zone). Kept separate from the dead zone so it can be tuned on its own.</summary>
        public const float Curve = 1f;

        public static StickInput Apply(Vector2 raw, float dead = DeadZone, float curve = Curve)
        {
            if (!(dead >= 0f && dead < 1f && curve > 0f)) { Debug.LogError("StickFilter: needs 0 <= dead < 1 and curve > 0"); return default; }
            float mag = raw.magnitude;
            if (!(mag > dead) || float.IsInfinity(mag)) return default;     // also rejects NaN
            // rescale so the amount ramps from 0 at the edge of the dead zone, cap the length (keys, noisy sticks)
            float scaled = Mathf.Min((mag - dead) / (1f - dead), 1f);
            return new StickInput { dir = raw / mag, amount = Mathf.Pow(scaled, curve) };
        }

        /// <summary>The stick length that makes the driver cruise at a given forward speed (scripts and tests).</summary>
        public static float LengthForSpeed(float speed)
        {
            float amount = Mathf.Clamp01(speed / CarTuning.TopSpeed) * CarDriver.FullSpeedAmount;
            float scaled = Mathf.Pow(Mathf.Clamp01(amount), 1f / Curve);
            return Mathf.Clamp01(DeadZone + scaled * (1f - DeadZone));
        }
    }

    /// <summary>
    /// Driver model: stick -> intent -> commands. Ahead of the car the stick steers the nose there (PD on the heading).
    /// Clearly behind the car it means "back up that way": a car rolling forward brakes first, the reverse gear goes in
    /// near a standstill, and the reverse holds for as long as the stick stays there, steering the tail towards it
    /// (straight back = wheel straight). Driving on again also brakes first.
    /// </summary>
    public sealed class CarDriver
    {
        /// <summary>The stick has to point further than this behind the nose to back up, and closer than
        /// BackExitDeg to drive forward again; in between the current choice holds (no flicker on the boundary).</summary>
        public const float BackEnterDeg = 125f, BackExitDeg = 65f;
        /// <summary>The gear direction changes only below this speed (m/s): the car always brakes through zero.</summary>
        public const float ShiftSpeed = 0.6f;
        /// <summary>Stick amount at which the driver asks for full speed (the last bit of travel is a full-speed band).</summary>
        public const float FullSpeedAmount = 0.88f;
        // forward steering: deg of wheel per deg of heading error / per deg/s of yaw. Quicker up to 7 m/s (the nose
        // answers sooner among enemies and settles on the new line sooner), blending into the calm high-speed pair at
        // 14 m/s. The low-speed Kd is a little stronger than Kp's share: the car carries less yaw into a quick change of
        // direction, so with the quicker rack (CarTuning.SteerRateLow) a zig-zag reverses as soon as before or sooner
        // (feel_slalom_* in `handling`), and nothing overshoots
        const float KpFwdLow = 0.98f, KdFwdLow = 0.18f, KpFwdHigh = 0.8f, KdFwdHigh = 0.13f;
        const float GainBlendFrom = 7f, GainBlendTo = 14f;
        const float KpRev = 0.75f, KdRev = 0.12f;      // reverse: the same on the tail (the plant's sign flips, so do the terms)
        const float ThrottleUp = 3.7f, ThrottleDown = 7f, BrakeUp = 5.6f, BrakeDown = 9f;   // pedal travel per second

        public DriveGear Gear { get; private set; } = DriveGear.Forward;
        public DriverIntent Intent { get; private set; }
        public StickInput Stick { get; private set; }
        public DriveCommands Commands { get; private set; }
        /// <summary>Times the gear direction changed (tests: no flicker).</summary>
        public int GearChanges { get; private set; }
        bool backward;
        float throttle, brake;

        public void Reset(DriveGear gear = DriveGear.Forward)
        {
            Gear = gear;
            backward = gear == DriveGear.Reverse;
            throttle = brake = 0f;
            Intent = default;
            Stick = default;
            Commands = new DriveCommands { gear = gear };
        }

        public DriveCommands Step(Vector2 rawStick, CarSense car, float dt)
        {
            float u = car.forwardSpeed;
            float wantThrottle = 0f, wantBrake = 0f, steer = 0f;
            var stick = StickFilter.Apply(rawStick);
            Stick = stick;
            var intent = new DriverIntent { amount = stick.amount, backward = backward };

            if (car.dead)
            {
                wantBrake = 0.6f;
            }
            else if (!stick.Active)
            {
                // hands off: roll out gently, then hold the car (the gear stays where it was)
                wantBrake = Mathf.Abs(u) > 0.3f ? 0.3f : 1f;
            }
            else
            {
                float want = Mathf.Atan2(stick.dir.x, stick.dir.y) * Mathf.Rad2Deg;   // stick up = world +Z
                float errNose = Mathf.DeltaAngle(car.headingDeg, want);               // + = the stick is to the right
                float absNose = Mathf.Abs(errNose);
                if (!backward && absNose > BackEnterDeg) backward = true;
                else if (backward && absNose < BackExitDeg) backward = false;
                intent.wantDeg = want;
                intent.backward = backward;

                var wantGear = backward ? DriveGear.Reverse : DriveGear.Forward;
                if (wantGear != Gear && Mathf.Abs(u) <= ShiftSpeed) { Gear = wantGear; GearChanges++; }
                float speedAmount = Mathf.Clamp01(stick.amount / FullSpeedAmount);

                if (wantGear != Gear)
                {
                    // the car still rolls the other way: brake it to a stop on a straight wheel first
                    wantBrake = 0.5f + 0.5f * stick.amount;
                    intent.errDeg = backward ? Mathf.DeltaAngle(car.headingDeg + 180f, want) : errNose;
                }
                else if (Gear == DriveGear.Forward)
                {
                    intent.errDeg = errNose;
                    float speed01 = Mathf.Clamp01((Mathf.Abs(u) - 3f) / 11f);
                    float maxSteer = Mathf.Lerp(CarTuning.MaxSteerLow, CarTuning.MaxSteerHigh, speed01);
                    float gain01 = Mathf.Clamp01((Mathf.Abs(u) - GainBlendFrom) / (GainBlendTo - GainBlendFrom));
                    float kp = Mathf.Lerp(KpFwdLow, KpFwdHigh, gain01), kd = Mathf.Lerp(KdFwdLow, KdFwdHigh, gain01);
                    steer = Mathf.Clamp(errNose * kp - car.yawRateDeg * kd, -maxSteer, maxSteer);
                    // a big change of direction is taken slower (a tight turn, not a slide)
                    float turnLimit = absNose > 50f ? Mathf.Lerp(1f, 0.35f, (absNose - 50f) / 75f) : 1f;
                    float target = CarTuning.TopSpeed * speedAmount * turnLimit;
                    if (u < target) wantThrottle = Mathf.Clamp01((target - u) * 0.45f + 0.3f) * Mathf.Clamp01(stick.amount * 1.5f);
                    else if (u > target + 1.5f) wantBrake = Mathf.Clamp01((u - target - 1.5f) * 0.18f);
                    // on a climb the driver adds the throttle the slope takes away (a light stick still gets up a ramp)
                    if (car.slopeAccel < 0f && u < target + 0.5f && car.gearAccel > 0.1f)
                        wantThrottle = Mathf.Clamp01(wantThrottle + -car.slopeAccel / (car.gearAccel * 0.8f));
                    // the driver feathers the throttle when the rear tires break loose
                    wantThrottle *= 1f - Mathf.Clamp01(car.wheelSpin - 0.2f) * 0.75f;
                }
                else
                {
                    // reverse: the tail is the travelling axis. Straight back = wheel straight; a rear diagonal swings
                    // the tail that way. Moving backwards the steering acts the other way round, so both terms flip.
                    float errTail = Mathf.DeltaAngle(car.headingDeg + 180f, want);
                    float absTail = Mathf.Abs(errTail);
                    intent.errDeg = errTail;
                    steer = Mathf.Clamp(-errTail * KpRev + car.yawRateDeg * KdRev, -CarTuning.MaxSteerReverse, CarTuning.MaxSteerReverse);
                    float turnLimit = absTail > 25f ? Mathf.Lerp(1f, 0.55f, (absTail - 25f) / 65f) : 1f;
                    float target = CarTuning.ReverseTopSpeed * speedAmount * turnLimit;
                    float back = -u;
                    if (back < target) wantThrottle = Mathf.Clamp01((target - back) * 0.6f + 0.3f) * Mathf.Clamp01(stick.amount * 1.6f);
                    else if (back > target + 0.8f) wantBrake = Mathf.Clamp01((back - target - 0.8f) * 0.3f);
                    // backing up a slope: the same help as going forward up one
                    if (car.slopeAccel > 0f && back < target + 0.5f)
                        wantThrottle = Mathf.Clamp01(wantThrottle + car.slopeAccel / (CarTuning.ReverseAccel * 0.8f));
                }
            }

            // pedals travel at a limited rate: no instant jolts, still quick enough to feel direct
            throttle = Mathf.MoveTowards(throttle, wantThrottle, (wantThrottle > throttle ? ThrottleUp : ThrottleDown) * dt);
            brake = Mathf.MoveTowards(brake, wantBrake, (wantBrake > brake ? BrakeUp : BrakeDown) * dt);
            if (wantBrake > 0.95f && Mathf.Abs(u) < 0.3f) brake = wantBrake;   // a parked car is held at once
            Intent = intent;
            Commands = new DriveCommands { throttle = throttle, brake = brake, steerDeg = steer, gear = Gear, handbrake = false };
            return Commands;
        }

        /// <summary>
        /// For automated drivers (autopilot, test bots) that want to get somewhere, choosing the manoeuvre a player would:
        /// a target ahead - straight there; behind while the car is (nearly) stopped - back up on the rear diagonal that
        /// swings the nose round towards it until the nose is within 60 deg (a three-point turn: the stick behind means
        /// "back up", so the turn has to be asked for); behind while rolling on - a forward U-turn (TowardForward). With
        /// the distance to the target it also eases off before a turn the car could not make at its speed.
        /// </summary>
        public static Vector2 TowardTarget(Vector2 stick, float headingDeg, float forwardSpeed, DriveGear gear, float distance = -1f)
        {
            float m = stick.magnitude;
            if (m < 1e-4f) return Vector2.zero;
            float err = Mathf.DeltaAngle(headingDeg, Mathf.Atan2(stick.x, stick.y) * Mathf.Rad2Deg);
            float abs = Mathf.Abs(err);
            bool backing = gear == DriveGear.Reverse;
            if ((backing && abs > 60f) || (!backing && abs > 110f && forwardSpeed < 2f))
            {
                // backing up with the stick 45 deg off the tail swings the tail that way and the nose the other way
                float a = (headingDeg + 180f + 45f * Mathf.Sign(err)) * Mathf.Deg2Rad;
                return new Vector2(Mathf.Sin(a), Mathf.Cos(a)) * Mathf.Max(0.55f, m);
            }
            var s = TowardForward(stick, headingDeg);
            if (distance > 0f && abs > 15f)
            {
                // like a player easing off before a tight turn: the circle that reaches the target from the current
                // heading must fit the turning circle the tires can hold at that speed (radius ~ v^2 / 7 m/s^2)
                float r = abs >= 90f ? distance * 0.5f : distance / (2f * Mathf.Sin(abs * Mathf.Deg2Rad));
                float vMax = Mathf.Max(3f, Mathf.Sqrt(7f * Mathf.Max(r, 0.5f)));
                float len = StickFilter.LengthForSpeed(vMax);
                if (s.magnitude > len) s = s.normalized * len;
            }
            return s;
        }

        /// <summary>
        /// For automated drivers that want to get somewhere going forward: aims straight at the target while it is
        /// ahead; when it is behind, points the stick to the side the car should turn to (a U-turn, as a player swings
        /// the stick round), so the driver never reads it as "back up".
        /// </summary>
        public static Vector2 TowardForward(Vector2 stick, float headingDeg)
        {
            float m = stick.magnitude;
            if (m < 1e-4f) return Vector2.zero;
            float want = Mathf.Atan2(stick.x, stick.y) * Mathf.Rad2Deg;
            float err = Mathf.DeltaAngle(headingDeg, want);
            const float Side = 60f;   // inside the forward band (BackExitDeg) and already full lock
            if (Mathf.Abs(err) <= Side) return stick;
            float a = (headingDeg + Mathf.Sign(err) * Side) * Mathf.Deg2Rad;
            float slow = Mathf.Lerp(1f, 0.6f, Mathf.InverseLerp(Side, 180f, Mathf.Abs(err)));
            return new Vector2(Mathf.Sin(a), Mathf.Cos(a)) * (m * slow);
        }
    }
}
