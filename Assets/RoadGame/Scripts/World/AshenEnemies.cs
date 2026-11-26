using UnityEngine;

namespace RoadGame
{
    // The seven enemies of the third zone (Ashen Winter): procedural animators for the rigid-part creatures of
    // ArtSource/Characters/AshenWinterEnemies (bundle Resources/Creatures/AshenWinterEnemies, built by Mutants.Apply).
    // Each one follows its anatomy from the concept sheet. The game's logic is untouched: the wind-up curve
    // (Enemy.AnimWindup) ends on the frame the damage is dealt or the shot leaves the muzzle part, so the strike and
    // the projectile line up with the existing combat timing. Unity axes: x = the creature's right, y up, z forward.

    // ========================================================================================== 01 Ash Pecker (Scav)
    /// <summary>Bird gait with a head bob; before a shot the neck pulls back and the beak aims at the car, then a short
    /// thrust as the round leaves the beak's open muzzle.</summary>
    public sealed class AshPeckerAnimator : MutantAnimator
    {
        P body, neck, head, wingL, wingR, legL, legR, footL, footR;
        float shotT = -9f, aimYaw;

        protected override void OnBind()
        {
            body = Get("Body"); neck = Get("Neck"); head = Get("Head"); wingL = Get("WingL"); wingR = Get("WingR");
            legL = Get("LegL"); legR = Get("LegR"); footL = Get("FootL"); footR = Get("FootR");
        }

        public override void OnShot() { base.OnShot(); shotT = 0f; }

        protected override void Animate(float dt)
        {
            phase += dt * (3.4f + speed * 2.0f);
            shotT += dt;
            float m = moving;
            Split(wind, 0.72f, out float antic, out float strike);
            float pull = antic * (1f - strike);
            float thrust = shotT < 0.32f ? Mathf.Sin(Mathf.Clamp01(shotT / 0.32f) * Mathf.PI) : 0f;
            // legs: alternate steps; the tarsus folds up while the foot travels forward
            for (int s = 0; s < 2; s++)
            {
                float ph = phase + s * Mathf.PI;
                var leg = s == 0 ? legL : legR;
                var foot = s == 0 ? footL : footR;
                leg.R(Pitch(-Mathf.Sin(ph) * 26f * m - 6f * pull));
                foot.R(Pitch(Mathf.Max(0f, Mathf.Cos(ph)) * 38f * m + 8f * pull));
            }
            float bob = Mathf.Abs(Mathf.Sin(phase)) * 0.04f * m;
            body.T(new Vector3(0f, bob - 0.03f * pull, -0.04f * pull + 0.03f * thrust - 0.05f * hitK));
            body.R(Pitch(4f * m - 6f * pull + 5f * thrust + hitK * -10f) * Roll(Mathf.Sin(phase) * 3f * m));
            // the head bob of a walking bird: the neck thrusts forward and holds, twice per stride
            float headBob = Mathf.Sin(phase * 2f) * 9f * m;
            var pl = PlayerLocal();
            float wantYaw = enemy.AnimAttackState || wind >= 0f ? Mathf.Clamp(Mathf.Atan2(pl.x, pl.z) * Mathf.Rad2Deg, -40f, 40f) : Mathf.Sin(tm * 0.8f) * 18f * (1f - m);
            aimYaw = Mathf.MoveTowards(aimYaw, wantYaw, 220f * dt);
            neck.R(Yaw(aimYaw * 0.5f) * Pitch(headBob - 26f * pull + 22f * thrust + hitK * -14f));
            head.R(Yaw(aimYaw * 0.5f) * Pitch(-headBob * 0.8f + 14f * pull - 12f * thrust + hitK * 10f));
            // ragged wings: a shiver at rest, flared on hits and with each shot
            float flare = Mathf.Max(hitK, thrust * 0.6f) + 0.15f * pull;
            wingL.R(Roll(-(4f + 26f * flare + Mathf.Sin(tm * 7f) * 2f)) * Yaw(6f * flare));
            wingR.R(Roll(4f + 26f * flare + Mathf.Sin(tm * 7f + 1f) * 2f) * Yaw(-6f * flare));
        }

        protected override void Die(float k)
        {
            body.T(new Vector3(0f, -0.52f * k, 0f));
            body.R(Roll(84f * k) * Pitch(10f * k));
            neck.R(Pitch(35f * k) * Yaw(-20f * k));
            head.R(Pitch(25f * k));
            legL.R(Pitch(-40f * k)); legR.R(Pitch(-20f * k));
            footL.R(Pitch(70f * k)); footR.R(Pitch(55f * k));
            wingL.R(Roll(-40f * k)); wingR.R(Roll(30f * k));
        }
    }

    // ========================================================================================== 02 Snow Reaper (Raider)
    /// <summary>Low gait with its weight on the two front blades; the strike: the body settles, one blade rises over
    /// the shoulder and chops down on the damage frame.</summary>
    public sealed class SnowReaperAnimator : MutantAnimator
    {
        P body, head, tail, armL, armR, foreL, foreR, bladeL, bladeR, thighL, thighR, shinL, shinR;
        int side;       // 0: the left blade strikes next, 1: the right

        protected override void OnBind()
        {
            body = Get("Body"); head = Get("Head"); tail = Get("Tail");
            armL = Get("ArmL"); armR = Get("ArmR"); foreL = Get("ForeL"); foreR = Get("ForeR");
            bladeL = Get("BladeL"); bladeR = Get("BladeR");
            thighL = Get("ThighL"); thighR = Get("ThighR"); shinL = Get("ShinL"); shinR = Get("ShinR");
            recoverDur = 0.32f;
        }

        public override void OnStrike(bool landed)
        {
            base.OnStrike(landed);
            var blade = side == 0 ? bladeL : bladeR;
            if (blade.t != null) Dust(blade.t.TransformPoint(new Vector3(0f, -0.85f, 0.32f)), 1.1f);
            side = 1 - side;
        }

        protected override void Animate(float dt)
        {
            phase += dt * (2.8f + speed * 1.3f);
            float m = moving;
            Split(wind, 0.5f, out float antic, out float strike);
            float raise = antic * (1f - strike);
            float chop = strike;
            if (rec >= 0f) { chop = 1f - Ease(rec); raise = 0f; }
            float settle = Mathf.Max(raise, chop * 0.7f) + (enemy.AnimAttackState ? 0.25f : 0f);
            // body: low, weight shifting onto the front blades with every stride; settles for the strike
            float bob = Mathf.Abs(Mathf.Sin(phase)) * 0.05f * m;
            body.T(new Vector3(0f, bob - 0.12f * settle - 0.04f * hitK, 0.04f * Mathf.Sin(phase) * m + 0.10f * chop));
            body.R(Pitch(5f * Mathf.Sin(phase) * m + 6f * settle + hitK * -8f) * Roll(Mathf.Sin(phase * 0.5f) * 4f * m + hitDir.x * hitK * 6f));
            head.R(Pitch(-8f * raise + 10f * chop + Mathf.Sin(tm * 1.3f) * 2f) * Yaw(Mathf.Sin(tm * 0.7f) * 8f * (1f - m)));
            tail.R(Yaw(Mathf.Sin(phase * 0.5f) * 12f * m + Mathf.Sin(tm * 0.9f) * 5f) * Pitch(-6f * settle + Mathf.Sin(tm * 1.7f) * 2f));
            // the blades: alternate supports while running; the striking side rises over the shoulder and chops
            for (int s = 0; s < 2; s++)
            {
                bool striking = s == side && (raise > 0f || chop > 0f);
                float ph = phase + s * Mathf.PI;
                float swing = Mathf.Sin(ph) * 20f * m;
                float lift = Mathf.Max(0f, Mathf.Cos(ph)) * 16f * m;
                float sgn = s == 0 ? -1f : 1f;     // left arm is at -x
                var arm = s == 0 ? armL : armR;
                var fore = s == 0 ? foreL : foreR;
                var blade = s == 0 ? bladeL : bladeR;
                float r = striking ? raise : 0f, c = striking ? chop : 0f;
                arm.R(Pitch(-swing - 55f * r + 25f * c) * Roll(sgn * (-lift - 18f * r)));
                fore.R(Pitch(-lift * 0.8f - 45f * r + 35f * c));
                blade.R(Pitch(-35f * r + 28f * c + Mathf.Sin(tm * 1.1f + s) * 2f));
            }
            for (int s = 0; s < 2; s++)
            {
                float ph = phase + s * Mathf.PI + 1.2f;
                var thigh = s == 0 ? thighL : thighR;
                var shin = s == 0 ? shinL : shinR;
                thigh.R(Pitch(-Mathf.Sin(ph) * 24f * m - 10f * settle));
                shin.R(Pitch(Mathf.Max(0f, Mathf.Cos(ph)) * 30f * m + 12f * settle));
            }
        }

        protected override void Die(float k)
        {
            body.T(new Vector3(0f, -0.55f * k + 0.25f * Mathf.Sin(k * Mathf.PI), 0f));
            body.R(Roll(-150f * k) * Pitch(10f * k));
            armL.R(Pitch(-40f * k)); armR.R(Pitch(-30f * k));
            foreL.R(Pitch(50f * k)); foreR.R(Pitch(40f * k));
            thighL.R(Pitch(-50f * k)); thighR.R(Pitch(-40f * k));
            shinL.R(Pitch(60f * k)); shinR.R(Pitch(50f * k));
            tail.R(Yaw(30f * k));
        }
    }

    // ========================================================================================== 03 Needle Walker (Spearman)
    /// <summary>Three legs step one at a time and keep a stable triangle; the body steadies before a shot, the needle
    /// launcher aims on its own, the needle leaves the tip of the guide and the launcher recoils.</summary>
    public sealed class NeedleWalkerAnimator : MutantAnimator
    {
        P body, launcher;
        readonly P[] legs = new P[3], shins = new P[3];
        readonly Vector3[] hinge = new Vector3[3];
        static readonly string[] Names = { "A", "B", "C" };
        float shotT = -9f, aimYaw, aimPitch;
        protected override float DeathDuration => 0.9f;

        protected override void OnBind()
        {
            body = Get("Body"); launcher = Get("Launcher");
            for (int i = 0; i < 3; i++)
            {
                legs[i] = Get("Leg" + Names[i]); shins[i] = Get("Shin" + Names[i]);
                // the leg's outward direction (from the body) and its knee hinge axis (horizontal, across the leg)
                var d = legs[i].t != null ? new Vector3(legs[i].pos.x, 0f, legs[i].pos.z) : Vector3.forward;
                if (d.sqrMagnitude < 1e-4f) d = Vector3.back;
                d.Normalize();
                hinge[i] = new Vector3(-d.z, 0f, d.x);
            }
            recoverDur = 0.4f;
        }

        public override void OnShot() { base.OnShot(); shotT = 0f; }

        protected override void Animate(float dt)
        {
            phase += dt * (1.6f + speed * 1.2f);
            shotT += dt;
            float m = moving;
            float steady = wind >= 0f ? 1f : (enemy.AnimAttackState ? 0.6f : 0f);
            for (int i = 0; i < 3; i++)
            {
                // one leg in the air at a time: its third of the cycle
                float c = Mathf.Repeat(phase / (Mathf.PI * 2f) - i / 3f, 1f);
                float lift = c < 0.33f ? Mathf.Sin(c / 0.33f * Mathf.PI) : 0f;
                float travel = c < 0.33f ? Mathf.Lerp(-1f, 1f, c / 0.33f) : Mathf.Lerp(1f, -1f, (c - 0.33f) / 0.67f);
                lift *= m * (1f - 0.7f * steady);
                travel *= m;
                legs[i].R(Yaw(travel * 9f) * Quaternion.AngleAxis(-lift * 16f - 4f * steady, hinge[i]));
                shins[i].R(Quaternion.AngleAxis(lift * 22f + 5f * steady, hinge[i]));
            }
            float sway = (1f - steady) * (1f - 0.5f * m);
            body.T(new Vector3(0f, Mathf.Sin(phase * 3f) * 0.03f * m - 0.08f * steady, 0f));
            body.R(Pitch(Mathf.Sin(tm * 0.9f) * 3f * sway + hitK * -6f + (shotT < 0.4f ? -5f * (1f - shotT / 0.4f) : 0f))
                   * Roll(Mathf.Sin(tm * 1.3f) * 4f * sway + Mathf.Sin(phase) * 3f * m));
            // the launcher aims at the car while it fights (yaw and pitch of its own), recoils on the shot
            var pl = PlayerLocal();
            bool fight = enemy.AnimAttackState || wind >= 0f;
            float wantYaw = fight ? Mathf.Clamp(Mathf.Atan2(pl.x, pl.z) * Mathf.Rad2Deg, -55f, 55f) : Mathf.Sin(tm * 0.5f) * 25f;
            float dist = new Vector2(pl.x, pl.z).magnitude;
            float wantPitch = fight ? Mathf.Clamp(Mathf.Atan2(2.6f, Mathf.Max(1f, dist)) * Mathf.Rad2Deg, 0f, 35f) : 0f;
            aimYaw = Mathf.MoveTowards(aimYaw, wantYaw, 160f * dt);
            aimPitch = Mathf.MoveTowards(aimPitch, wantPitch, 90f * dt);
            float kick = shotT < 0.35f ? (1f - shotT / 0.35f) : 0f;
            launcher.R(Yaw(aimYaw) * Pitch(aimPitch + 6f * kick));
            launcher.T(new Vector3(0f, 0f, -0.16f * kick));
        }

        protected override void Die(float k)
        {
            body.T(new Vector3(0f, -1.9f * k, 0f));
            body.R(Pitch(12f * k) * Roll(-18f * k));
            for (int i = 0; i < 3; i++)
            {
                legs[i].R(Quaternion.AngleAxis(-25f * k, hinge[i]));
                shins[i].R(Quaternion.AngleAxis(-55f * k, hinge[i]));
            }
            launcher.R(Pitch(20f * k));
        }
    }

    // ========================================================================================== 04 Boiler Spitter (Crossbow)
    /// <summary>Four short legs, the boiler sways; before the shot the firebox flares, the pipe aims and recoils as the
    /// lobbed shell leaves its mouth.</summary>
    public sealed class BoilerSpitterAnimator : MutantAnimator
    {
        P body, fire, pipe;
        readonly P[] legs = new P[4], feet = new P[4];
        static readonly string[] Names = { "FL", "FR", "BL", "BR" };
        static readonly float[] SideX = { -1f, 1f, -1f, 1f };
        float shotT = -9f, aimYaw;
        protected override float DeathDuration => 0.85f;
        protected override float VisualTurnRate => 150f;

        protected override void OnBind()
        {
            body = Get("Body"); fire = Get("Fire"); pipe = Get("Pipe");
            for (int i = 0; i < 4; i++) { legs[i] = Get("Leg" + Names[i]); feet[i] = Get("Foot" + Names[i]); }
        }

        public override void OnShot() { base.OnShot(); shotT = 0f; }

        protected override void Animate(float dt)
        {
            phase += dt * (2.2f + speed * 1.8f);
            shotT += dt;
            float m = moving;
            float heat = wind >= 0f ? Ease(wind) : 0f;
            float kick = shotT < 0.4f ? 1f - Ease(shotT / 0.4f) : 0f;
            for (int i = 0; i < 4; i++)
            {
                // diagonal pairs: FL + BR, then FR + BL
                float ph = phase + ((i == 0 || i == 3) ? 0f : Mathf.PI);
                float swing = Mathf.Sin(ph) * 16f * m;
                float lift = Mathf.Max(0f, Mathf.Cos(ph)) * 14f * m;
                legs[i].R(SideLeg(swing, lift, SideX[i]));
                feet[i].R(Roll(-lift * 0.6f * SideX[i]));
            }
            body.T(new Vector3(0f, Mathf.Abs(Mathf.Sin(phase)) * 0.035f * m - 0.06f * heat + 0.03f * kick, -0.05f * kick));
            body.R(Roll(Mathf.Sin(phase) * 4f * m + hitDir.x * hitK * 5f) * Pitch(Mathf.Sin(phase * 2f) * 1.5f * m - 3f * heat + 4f * kick + hitK * -5f));
            // the firebox flares while it winds up and puffs with the shot; a slow glow otherwise
            float glow = 1f + 0.08f * Mathf.Sin(tm * 5.3f) + 0.9f * heat + 0.5f * kick;
            fire.S(new Vector3(glow, glow, 1f));
            var pl = PlayerLocal();
            bool fight = enemy.AnimAttackState || wind >= 0f;
            aimYaw = Mathf.MoveTowards(aimYaw, fight ? Mathf.Clamp(Mathf.Atan2(pl.x, pl.z) * Mathf.Rad2Deg, -25f, 25f) : 0f, 90f * dt);
            pipe.R(Yaw(aimYaw) * Pitch(-8f * heat + 10f * kick));
            pipe.T(new Vector3(0f, -0.10f * kick, -0.06f * kick));
        }

        protected override void Die(float k)
        {
            body.T(new Vector3(0f, -0.48f * k, 0f));
            body.R(Roll(9f * k) * Pitch(6f * k));
            for (int i = 0; i < 4; i++) { legs[i].R(SideLeg(0f, -30f * k, SideX[i])); feet[i].R(Roll(35f * k * SideX[i])); }
            fire.S(Mathf.Lerp(1f, 0.25f, k));
            pipe.R(Pitch(18f * k));
        }
    }

    // ========================================================================================== 05 Concrete Executioner (Brute)
    /// <summary>Heavy gait; before the shot the body turns to the car and the cannon steadies; the recoil goes into the
    /// shoulder and the whole body.</summary>
    public sealed class ExecutionerAnimator : MutantAnimator
    {
        P pelvis, torso, head, armGun, armL, handL, thighL, thighR, shinL, shinR;
        float shotT = -9f, aimYaw, aimPitch;
        protected override float DeathDuration => 1.0f;
        protected override float VisualTurnRate => 110f;

        protected override void OnBind()
        {
            pelvis = Get("Pelvis"); torso = Get("Torso"); head = Get("Head"); armGun = Get("ArmGun");
            armL = Get("ArmL"); handL = Get("HandL");
            thighL = Get("ThighL"); thighR = Get("ThighR"); shinL = Get("ShinL"); shinR = Get("ShinR");
            recoverDur = 0.5f;
        }

        public override void OnShot()
        {
            base.OnShot();
            shotT = 0f;
            if (Game.I != null && Game.I.cameraRig != null && Game.I.player != null && (Game.I.player.Pos - transform.position).sqrMagnitude < 400f)
                Game.I.cameraRig.Shake(0.12f);
        }

        protected override void Animate(float dt)
        {
            phase += dt * (1.4f + speed * 1.4f);
            shotT += dt;
            float m = moving;
            float aim = wind >= 0f ? Ease(Mathf.Clamp01(wind / 0.6f)) : (enemy.AnimAttackState ? 0.5f : 0f);
            float kick = shotT < 0.5f ? 1f - Ease(shotT / 0.5f) : 0f;
            for (int s = 0; s < 2; s++)
            {
                float ph = phase + s * Mathf.PI;
                var thigh = s == 0 ? thighL : thighR;
                var shin = s == 0 ? shinL : shinR;
                thigh.R(Pitch(-Mathf.Sin(ph) * 20f * m + 6f * kick) * Roll((s == 0 ? 1f : -1f) * 2f * m));
                shin.R(Pitch(Mathf.Max(0f, Mathf.Cos(ph)) * 26f * m + 4f * kick));
            }
            float sway = Mathf.Sin(phase) * 6f * m * (1f - aim) + Mathf.Sin(tm * 0.6f) * 1.2f * (1f - aim);
            pelvis.T(new Vector3(0f, Mathf.Abs(Mathf.Cos(phase)) * 0.08f * m - 0.03f * kick, -0.10f * kick));
            pelvis.R(Roll(-sway * 0.5f));
            // the upper body turns to the car (yaw of its own on top of the slow visual turn) and holds still to aim
            var pl = PlayerLocal();
            aimYaw = Mathf.MoveTowards(aimYaw, Mathf.Clamp(Mathf.Atan2(pl.x - 1.0f, pl.z) * Mathf.Rad2Deg, -35f, 35f) * aim, 120f * dt);
            float dist = new Vector2(pl.x, pl.z).magnitude;
            aimPitch = Mathf.MoveTowards(aimPitch, Mathf.Clamp(Mathf.Atan2(0.6f, Mathf.Max(1f, dist)) * Mathf.Rad2Deg, 0f, 20f) * aim, 60f * dt);
            torso.R(Yaw(aimYaw) * Pitch(-7f * kick + hitK * -8f + Mathf.Sin(tm * 1.1f) * 1f) * Roll(sway));
            head.R(Yaw(aimYaw * 0.3f) * Pitch(Mathf.Sin(tm * 0.8f) * 3f));
            // the cannon: swings with the gait, steadies on the car, kicks up into the shoulder on the shot
            float pend = Mathf.Sin(phase - 0.6f) * 8f * m * (1f - aim);
            armGun.R(Pitch(pend + aimPitch - 16f * kick) * Yaw(-4f * kick));
            armL.R(Pitch(-pend * 1.2f + hitK * 12f) * Roll(6f + 4f * kick));
            handL.R(Pitch(-14f + 10f * Mathf.Sin(tm * 1.6f)));
        }

        protected override void Die(float k)
        {
            pelvis.T(new Vector3(0f, -0.75f * k, -0.25f * k));
            thighL.R(Pitch(-55f * k)); thighR.R(Pitch(-40f * k));
            shinL.R(Pitch(80f * k)); shinR.R(Pitch(65f * k));
            torso.R(Pitch(-48f * k) * Roll(10f * k));
            armGun.R(Pitch(25f * k));
            armL.R(Pitch(-30f * k) * Roll(-20f * k));
        }
    }

    // ========================================================================================== 06 Whiteout Raider (Buggy)
    /// <summary>The snow-plough sled: track belts scroll and road wheels spin with the real speed, the skis steer
    /// with the turn, the open turret aims at the car on its own and the barrels spin through the burst.</summary>
    public sealed class WhiteoutRaiderAnimator : MutantAnimator
    {
        P body, skiL, skiR, turret, gun, barrels, driver, driverHead;
        readonly System.Collections.Generic.List<P> wheels = new System.Collections.Generic.List<P>();
        readonly System.Collections.Generic.List<float> wheelR = new System.Collections.Generic.List<float>();
        Renderer[] tracks;
        MaterialPropertyBlock mpb;
        float spin, belt, barrelSpin, barrelRate, turretYaw, gunPitch, shotT = -9f, lastBelt = float.NaN;
        // metres of belt per texture width (aw_lib.STRIP_SCALE['tread'])
        const float TreadMetres = 2.4f;

        protected override void OnBind()
        {
            body = Get("Body"); skiL = Get("SkiL"); skiR = Get("SkiR"); turret = Get("Turret"); gun = Get("Gun");
            barrels = Get("Barrels"); driver = Get("Driver"); driverHead = Get("DriverHead");
            wheels.Clear(); wheelR.Clear();
            foreach (var side in new[] { "L", "R" })
            {
                for (int k = 0; k < 5; k++) { wheels.Add(Get("Wheel" + side + k)); wheelR.Add(0.19f); }
                wheels.Add(Get("Idler" + side)); wheelR.Add(0.25f);
                wheels.Add(Get("Sprocket" + side)); wheelR.Add(0.27f);
            }
            var list = new System.Collections.Generic.List<Renderer>();
            foreach (var n in new[] { "TrackL", "TrackR" })
            {
                var t = v != null ? v.Part(n) : null;
                if (t != null) list.AddRange(t.GetComponentsInChildren<Renderer>(true));
            }
            tracks = list.ToArray();
            mpb = new MaterialPropertyBlock();
        }

        public override void OnShot() { base.OnShot(); shotT = 0f; barrelRate = 1800f; }

        protected override void Animate(float dt)
        {
            float sp = speed;
            spin += sp * dt * Mathf.Rad2Deg;
            for (int i = 0; i < wheels.Count; i++) wheels[i].R(Pitch(spin / wheelR[i]));
            // the belt's tread (strip u runs along the belt) moves backward on the ground as the sled drives forward
            belt = Mathf.Repeat(belt + sp * dt / TreadMetres, 1f);
            if (tracks != null && !Mathf.Approximately(belt, lastBelt))
            {
                lastBelt = belt;
                foreach (var r in tracks)
                {
                    if (r == null) continue;
                    r.GetPropertyBlock(mpb);
                    mpb.SetVector("_BaseMap_ST", new Vector4(1f, 1f, -belt, 0f));
                    r.SetPropertyBlock(mpb);
                }
            }
            float steer = Mathf.Clamp(turnRate * 0.22f, -26f, 26f);
            skiL.R(Yaw(steer)); skiR.R(Yaw(steer));
            float acc = Mathf.Clamp(sp * 0.35f, 0f, 4f);
            float bounce = Mathf.Sin(tm * 12f) * 0.012f * Mathf.Clamp01(sp / 4f);
            body.R(Pitch(-acc * 0.5f + hitK * -4f) * Roll(-steer * 0.15f + Mathf.Sin(tm * 9f) * 0.5f * Mathf.Clamp01(sp / 4f)));
            body.T(new Vector3(0f, bounce, -0.05f * hitK));
            // the open turret tracks the car on its own (the hull keeps its course); scans slowly when idle
            bool engaged = enemy.Engaged;
            var pl = PlayerLocal();
            float want = engaged ? Mathf.Atan2(pl.x, pl.z) * Mathf.Rad2Deg : Mathf.Sin(tm * 0.4f) * 40f;
            turretYaw = Mathf.MoveTowardsAngle(turretYaw, want, (engaged ? 220f : 50f) * dt);
            turret.R(Yaw(turretYaw));
            float dist = new Vector2(pl.x, pl.z).magnitude;
            float wantPitch = engaged ? Mathf.Clamp(Mathf.Atan2(1.2f, Mathf.Max(1.5f, dist)) * Mathf.Rad2Deg, 0f, 25f) : -4f;
            gunPitch = Mathf.MoveTowards(gunPitch, wantPitch, 80f * dt);
            shotT += dt;
            float kick = shotT < 0.12f ? 1f - shotT / 0.12f : 0f;
            gun.R(Pitch(gunPitch + 3f * kick));
            gun.T(new Vector3(0f, 0f, -0.05f * kick));
            if (wind >= 0f || enemy.AnimBurst) barrelRate = Mathf.Max(barrelRate, 900f + 900f * Mathf.Max(0f, wind));
            barrelRate = Mathf.MoveTowards(barrelRate, 0f, 1400f * dt);
            barrelSpin += barrelRate * dt;
            barrels.R(Roll(barrelSpin));
            // the hooded driver ducks with the bumps and watches the car
            driver.R(Roll(steer * 0.25f) * Pitch(acc * 0.8f + hitK * -6f));
            driverHead.R(Yaw(engaged ? Mathf.Clamp(Mathf.Atan2(pl.x, pl.z) * Mathf.Rad2Deg, -60f, 60f) : Mathf.Sin(tm * 0.6f) * 25f));
        }

        protected override void Die(float k)
        {
            body.T(new Vector3(0f, -0.14f * k, 0f));
            body.R(Roll(9f * k) * Pitch(-4f * k));
            skiL.R(Yaw(22f * k)); skiR.R(Yaw(-14f * k));
            gun.R(Pitch(gunPitch + 22f * k));
            driver.R(Pitch(28f * k) * Roll(12f * k));
            driverHead.R(Pitch(30f * k));
        }
    }

    // ========================================================================================== 07 Black Reactor (BossColossus)
    /// <summary>Huge biped: walking shifts its weight from foot to foot (dust and a camera shake at each step); before a
    /// blow it twists back and raises the block fist, the fist lands on the game's damage frame; the slam special
    /// raises the fist overhead for its telegraph and brings it down on the circle.</summary>
    public sealed class BlackReactorAnimator : MutantAnimator
    {
        P pelvis, torso, port, armHeavy, foreHeavy, armClaw, foreClaw, handClaw, thighL, thighR, shinL, shinR;
        float lastStep;
        protected override float DeathDuration => 1.3f;
        protected override float VisualTurnRate => 60f;

        protected override void OnBind()
        {
            pelvis = Get("Pelvis"); torso = Get("Torso"); port = Get("Port");
            armHeavy = Get("ArmHeavy"); foreHeavy = Get("ForeHeavy");
            armClaw = Get("ArmClaw"); foreClaw = Get("ForeClaw"); handClaw = Get("HandClaw");
            thighL = Get("ThighL"); thighR = Get("ThighR"); shinL = Get("ShinL"); shinR = Get("ShinR");
            recoverDur = 0.6f;
        }

        public override void OnStrike(bool landed)
        {
            base.OnStrike(landed);
            Vector3 p = foreHeavy.t != null ? foreHeavy.t.TransformPoint(new Vector3(0.2f, -2.3f, 0.9f)) : transform.position + transform.forward * 3f;
            p.y = transform.position.y;
            Dust(p, 2.8f);
            if (Game.I != null && Game.I.cameraRig != null) Game.I.cameraRig.Shake(0.3f);
        }

        protected override void Animate(float dt)
        {
            phase += dt * (0.85f + speed * 0.55f);
            float m = moving;
            bool special = enemy.AnimSpecial && enemy.AnimSpecialKind == 1;
            float st = enemy.AnimSpecialT;
            // slam special (telegraph 1.1 s): the fist rises overhead by 0.9 s, comes down on the circle at 1.1 s
            float up = special ? Ease(Mathf.Clamp01(st / 0.9f)) : 0f;
            float slam = special && st > 0.9f ? Ease(Mathf.Clamp01((st - 0.9f) / 0.2f)) : 0f;
            Split(wind, 0.7f, out float antic, out float strike);
            float raise = antic * (1f - strike);
            float blow = strike;
            if (rec >= 0f) { blow = 1f - Ease(rec); raise = 0f; }
            // gait: each step shifts the weight onto the planted foot
            for (int s = 0; s < 2; s++)
            {
                float ph = phase + s * Mathf.PI;
                var thigh = s == 0 ? thighL : thighR;
                var shin = s == 0 ? shinL : shinR;
                thigh.R(Pitch(-Mathf.Sin(ph) * 13f * m - 8f * slam - 6f * blow) * Roll((s == 0 ? 1f : -1f) * 3f * m));
                shin.R(Pitch(Mathf.Max(0f, Mathf.Cos(ph)) * 18f * m + 10f * slam + 6f * blow));
            }
            float stepPhase = Mathf.Repeat(phase / Mathf.PI, 1f);
            if (m > 0.3f && stepPhase < lastStep)
            {
                // a foot comes down: dust under it, a small shake close by
                var foot = (Mathf.FloorToInt(phase / Mathf.PI) % 2 == 0 ? shinL : shinR);
                if (foot.t != null) Dust(foot.t.TransformPoint(new Vector3(0f, -1.6f, 0.3f)), 1.6f);
                if (Game.I != null && Game.I.cameraRig != null && Game.I.player != null && (Game.I.player.Pos - transform.position).sqrMagnitude < 900f)
                    Game.I.cameraRig.Shake(0.12f);
            }
            lastStep = stepPhase;
            float shift = Mathf.Sin(phase) * m;
            pelvis.T(new Vector3(shift * 0.12f, Mathf.Abs(Mathf.Cos(phase)) * 0.10f * m - 0.25f * slam - 0.12f * blow, 0f));
            pelvis.R(Roll(-shift * 4f));
            float breathe = Mathf.Sin(tm * 1.6f);
            torso.R(Yaw(-18f * raise + 12f * blow - 10f * up * (1f - slam) + 6f * slam)
                    * Pitch(-6f * up * (1f - slam) + 12f * slam + 8f * blow - 3f * raise + hitK * -3f + breathe * 0.8f)
                    * Roll(shift * 3f + hitK * Mathf.Sin(tm * 37f) * 1.2f));
            torso.T(new Vector3(0f, 0.05f * breathe, 0f));
            // the block fist: hangs and swings, rises for the blow / overhead for the slam, lands on the damage frame
            float pend = Mathf.Sin(phase - 0.7f) * 9f * m;
            float heavyPitch = pend - 75f * raise + 18f * blow - 150f * up * (1f - slam) + 20f * slam;
            armHeavy.R(Pitch(heavyPitch) * Roll(-10f * raise - 14f * up * (1f - slam)));
            foreHeavy.R(Pitch(-40f * raise + 10f * blow - 30f * up * (1f - slam)));
            // the claw arm balances: forward and up while the fist goes back, claws flex
            armClaw.R(Pitch(-pend * 0.8f - 20f * raise - 25f * up * (1f - slam) + hitK * 6f) * Roll(8f * up));
            foreClaw.R(Pitch(-18f * raise - 20f * up + Mathf.Sin(tm * 1.2f) * 3f));
            handClaw.R(Pitch(-10f + 14f * Mathf.Sin(tm * 1.9f) * (enemy.Engaged ? 1f : 0.4f)));
            // the reactor core beats faster in a fight and blazes for the slam
            float rate = special ? 3.2f : (enemy.Engaged ? 1.7f : 0.8f);
            float beat = Mathf.Pow(Mathf.Max(0f, Mathf.Sin(tm * rate * Mathf.PI * 2f)), 4f);
            port.S(1f + 0.10f * beat + 0.25f * up * (1f - slam) + 0.1f * raise);
        }

        protected override void Die(float k)
        {
            pelvis.T(new Vector3(0f, -1.55f * k, 0.25f * k));
            thighL.R(Pitch(-62f * k)); thighR.R(Pitch(-55f * k));
            shinL.R(Pitch(88f * k)); shinR.R(Pitch(80f * k));
            torso.R(Pitch(22f * k) * Roll(-5f * k));
            armHeavy.R(Pitch(12f * k) * Roll(8f * k));
            armClaw.R(Pitch(-6f * k) * Roll(-10f * k));
            foreClaw.R(Pitch(20f * k));
            port.S(Mathf.Lerp(1f, 0.5f, k));
        }
    }
}
