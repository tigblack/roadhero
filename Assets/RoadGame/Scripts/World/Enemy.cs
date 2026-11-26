using UnityEngine;

namespace RoadGame
{
    /// <summary>Raiders (foot), buggies (vehicle) and bosses. Simple readable AI: idle/wander → chase → attack → return home.</summary>
    public class Enemy : Target
    {
        enum State { Idle, Chase, Attack, Return, Special }

        State state;
        Vector3 home;
        Vector3 wanderTarget;
        float wanderTimer;
        float attackTimer;
        float windup = -1f;
        float attackAnim;
        float walkPhase;
        float speedNow;
        float heading;
        float leash;
        float knockback;
        Vector3 knockDir;
        float outOfArenaTimer;
        float aggroFlash;
        int burstLeft;
        float burstTimer;
        float orbitSign = 1f;

        // boss specials
        float specialTimer;
        float specialPhase;
        int specialKind;
        Vector3 specialDir;
        Vector3 specialPoint;
        float specialT;
        bool specialHit;
        float chargeLen;
        bool chargeHitsWall;
        Telegraph tele;
        // level / sight: an enemy only fights a car on its own level that it can see (no shooting through ground)
        float sightTimer;
        bool canSee = true;
        // obstacles: rocks, walls, buildings and props stop it; it steers round them (sticking to the side it chose)
        float avoidSide = 1f, avoidTimer;
        // going round an obstacle: it follows the surface on one side until the way to the goal is open again
        float detourSide, detourHold;
        // progress towards the goal: no gain for a while -> it goes round the other way (concave traps, long walls)
        float progressBest = float.MaxValue, progressTimer;
        Vector3 progressPos;
        // melee needs a clear line to the car: no club through a hut, a wall or a rock
        float meleeCheckTimer;
        bool meleeClear = true;
        /// <summary>Movement steps that ran into an obstacle and slid along it / stopped (tests).</summary>
        public static int ObstacleContacts;
        /// <summary>Times an enemy made no progress and switched the side it goes round an obstacle (tests).</summary>
        public static int StuckFlips;
        /// <summary>Melee wind-ups held back / strikes that missed because something solid stood between (tests).</summary>
        public static int MeleeBlocked;
        /// <summary>Time spent in obstacle-aware movement (sweeps, steering, push-out) since start, in stopwatch ticks (tests).</summary>
        public static long MoveTicks;
        /// <summary>Intro scouts: they never drive past this line (the run-up to the first ramp stays clear).</summary>
        public float maxZ = float.MaxValue;

        public override bool IsEnemy => true;

        // ---- animation state read by the second-zone mutants' animators (Scripts/World/Mutants.cs)
        public MutantAnimator mutant;
        public float AnimSpeed => speedNow;
        public float AnimHeading => heading;
        public bool AnimAttackState => state == State.Attack;
        /// <summary>Wind-up progress 0..1 (1 = the damage / shot frame), -1 when not winding up.</summary>
        public float AnimWindup => windup >= 0f ? Mathf.Clamp01(1f - windup / Mathf.Max(0.01f, WindupTotal)) : -1f;
        public bool AnimBurst => burstLeft > 0;
        public bool AnimSpecial => state == State.Special;
        public int AnimSpecialKind => specialKind;
        public float AnimSpecialT => specialT;
        /// <summary>Time of the last melee strike or volley (the frame the game dealt / launched the damage).</summary>
        public float AnimStrikeTime { get; private set; } = -99f;
        public bool AnimStrikeLanded { get; private set; }
        float WindupTotal => spec.kind == TargetKind.Boss ? 0.5f : spec.windupTime;
        public bool Engaged => !dead && (state == State.Chase || state == State.Attack || state == State.Special);
        public bool JustAggroed => aggroFlash > 0f;

        bool IsVehicleLike => spec.kind == TargetKind.Vehicle || spec.model == ModelId.BossMammoth || spec.model == ModelId.BossWarlord;
        /// <summary>A foot soldier that fights hand to hand (club, spike, claws, bite).</summary>
        bool IsMeleeFoot => spec.kind == TargetKind.Foot && !spec.ranged;
        /// <summary>Boss room (the Mammoth's hangar): the boss keeps to this floor, the fight is on while the car is in it.</summary>
        ORect? Arena => spawn != null ? spawn.arena : null;

        static readonly RaycastHit[] lineHits = new RaycastHit[8];

        /// <summary>
        /// Nothing solid between the fighter's chest and the car's body (re-checked every 0.2 s unless forced): huts,
        /// walls, rocks and towers block a blow; low clutter it can swing over (crates, barrels, tyres) does not, nor do
        /// the car itself and the fighter's own parts.
        /// </summary>
        bool MeleeLineClear(Player player, float dt, bool force)
        {
            meleeCheckTimer -= dt;
            if (!force && meleeCheckTimer > 0f) return meleeClear;
            meleeCheckTimer = 0.2f;
            var from = transform.position + Vector3.up * Mathf.Min(1.3f, spec.height * spawn.scale * 0.45f);
            var to = player.Pos + Vector3.up * 0.8f;
            var d = to - from;
            float len = d.magnitude;
            meleeClear = true;
            if (len < 0.05f) return true;
            int n = Physics.RaycastNonAlloc(from, d / len, lineHits, len, Player.ObstacleMask, QueryTriggerInteraction.Ignore);
            float low = transform.position.y + 1.15f;
            for (int i = 0; i < n; i++)
            {
                var c = lineHits[i].collider;
                if (!IsObstacle(c, transform)) continue;
                if (c.bounds.max.y < low) continue;
                meleeClear = false;
                break;
            }
            return meleeClear;
        }

        public override void Setup(SpawnPoint sp, Rig r)
        {
            base.Setup(sp, r);
            home = sp.pos;
            leash = spec.kind == TargetKind.Boss ? 21f : (spec.kind == TargetKind.Vehicle ? 34f : 22f);
            if (spec.pace) leash = 150f;
            mutant = GetComponent<MutantAnimator>();
            if (mutant != null) mutant.Attach(this);
        }

        public override void ResetForSpawn(bool animate)
        {
            base.ResetForSpawn(animate);
            state = State.Idle;
            speedNow = 0;
            heading = spawn.yaw;
            attackTimer = Random.Range(0.2f, 0.8f);
            windup = -1f;
            wanderTimer = Random.Range(0.5f, 3f);
            specialTimer = 5f;
            knockback = 0;
            detourSide = 0f; detourHold = 0f;
            progressBest = float.MaxValue; progressTimer = 0f;
            meleeClear = true; meleeCheckTimer = 0f;
            if (tele != null) tele.Hide();
            PoseNeutral();
        }

        void PoseNeutral()
        {
            if (mutant != null) { mutant.ResetPose(); return; }
            if (rig == null) return;
            if (rig.legL) rig.legL.localRotation = Quaternion.identity;
            if (rig.legR) rig.legR.localRotation = Quaternion.identity;
            if (rig.armL) rig.armL.localRotation = Quaternion.identity;
            if (rig.armR) rig.armR.localRotation = Quaternion.identity;
            if (rig.body) rig.body.localPosition = Vector3.zero;
        }

        protected override void OnHit(Vector3 source)
        {
            if (mutant != null) mutant.OnHit(source);
            if (state == State.Idle || state == State.Return)
            {
                if ((transform.position - home).magnitude < leash * 0.8f) SetState(State.Chase);
            }
            if (spec.kind == TargetKind.Foot && spec.scale < 1.2f) { knockback = 0.12f; knockDir = (transform.position - source).normalized; knockDir.y = 0; }
        }

        void SetState(State s)
        {
            if (s == State.Chase && state == State.Idle)
            {
                aggroFlash = 0.6f;
                if (Game.I != null && Game.I.overlay != null) Game.I.overlay.Alert(transform.position + Vector3.up * (spec.height * spawn.scale * 0.9f));
            }
            if (s != state) { progressBest = float.MaxValue; progressTimer = 0f; }
            state = s;
        }

        protected override void OnKilledVisual()
        {
            if (tele != null) tele.Hide();
            if (mutant != null) { mutant.OnDeath(); return; }   // the creature plays its own death; the root stays upright for the harpoon
            if (spec.kind == TargetKind.Foot || spec.model == ModelId.BossBaron || spec.model == ModelId.BossColossus)
            {
                PoseNeutral();
                if (rig.armL) rig.armL.localRotation = Quaternion.Euler(-150, 0, 20);
                if (rig.armR) rig.armR.localRotation = Quaternion.Euler(-150, 0, -20);
                transform.rotation = Quaternion.Euler(0, heading, 0) * Quaternion.Euler(-82, 0, 0);
                transform.position += Vector3.up * 0.25f * spawn.scale;
            }
            else
            {
                transform.rotation = Quaternion.Euler(0, heading + Random.Range(-20f, 20f), Random.Range(-14f, 14f));
                transform.localScale = baseScale * 0.92f;
            }
        }

        protected override void Update()
        {
            base.Update();
            if (dead || beingEaten || Game.I == null || Game.I.player == null) return;
            float dt = Time.deltaTime;
            if (aggroFlash > 0) aggroFlash -= dt;
            var player = Game.I.player;
            Vector3 pos = transform.position;
            Vector3 toP = player.Pos - pos; toP.y = 0;
            float dist = toP.magnitude;
            float homeDist = Flat(pos - home).magnitude;
            UpdateSight(player, dt, dist);
            bool playerOk = player.Alive && !player.OnRepairPad && canSee;
            float reach = spec.attackRange + player.Radius;
            if (Arena.HasValue)
            {
                // a boss room: the leash is the room itself
                bool inRoom = Arena.Value.Distance(player.Pos.x, player.Pos.z) < 3f && Ground.SameLevel(player.Pos, pos);
                playerOk &= inRoom;
                homeDist = 0f;
            }

            switch (state)
            {
                case State.Idle:
                    {
                        wanderTimer -= dt;
                        if (wanderTimer <= 0)
                        {
                            wanderTimer = Random.Range(2f, 5f);
                            var r = Random.insideUnitCircle * (spec.kind == TargetKind.Boss ? 5f : 3f);
                            wanderTarget = home + new Vector3(r.x, 0, r.y);
                        }
                        MoveTowards(wanderTarget, Mathf.Min(spec.speed, 4f) * 0.3f, dt, 0.4f);
                        if (playerOk && (Arena.HasValue || (dist < spec.aggro && Flat(player.Pos - home).magnitude < leash + 4f))) SetState(State.Chase);
                        break;
                    }
                case State.Chase:
                    {
                        if (!playerOk || homeDist > leash || (!Arena.HasValue && Flat(player.Pos - home).magnitude > leash + 8f)) { SetState(State.Return); break; }
                        // a melee fighter attacks once it is in reach AND nothing solid stands between (else it goes round)
                        if (dist <= reach && (!IsMeleeFoot || MeleeLineClear(player, dt, false))) { SetState(State.Attack); break; }
                        // surround the player instead of stacking on one point
                        Vector3 dirFromP = dist > 0.01f ? -toP / dist : Vector3.forward;
                        Vector3 goal = player.Pos + dirFromP * reach * 0.8f;
                        if (spec.ranged) goal = IsVehicleLike ? OrbitGoal(player, dirFromP) : player.Pos + dirFromP * Mathf.Min(spec.attackRange * 0.85f, dist);
                        MoveTowards(goal, spec.speed, dt, 0.1f);
                        break;
                    }
                case State.Attack:
                    {
                        if (!playerOk) { SetState(State.Return); break; }
                        if (dist > reach + 0.9f && windup < 0) { SetState(State.Chase); break; }
                        if (homeDist > leash + 3f) { SetState(State.Return); break; }
                        if (IsVehicleLike && spec.ranged)
                        {
                            var dirFromP2 = dist > 0.01f ? -toP / dist : Vector3.forward;
                            MoveTowards(OrbitGoal(player, dirFromP2), spec.speed * 0.6f, dt, 0.5f);
                        }
                        else
                        {
                            FaceTowards(player.Pos, dt, 540f);
                            if (IsVehicleLike && windup < 0) MoveTowards(player.Pos, spec.speed * 0.4f, dt, reach * 0.7f);
                            else if (IsMeleeFoot && windup < 0 && dist > reach * 0.8f)
                            {
                                // steps in before the swing: the blow comes from a comfortable distance, not the edge of its reach
                                var dirFromP3 = dist > 0.01f ? -toP / dist : Vector3.forward;
                                MoveTowards(player.Pos + dirFromP3 * reach * 0.7f, spec.speed * 0.7f, dt, 0.1f);
                            }
                            else speedNow = Mathf.MoveTowards(speedNow, 0, 20f * dt);
                        }
                        attackTimer -= dt;
                        if (windup < 0 && attackTimer <= 0)
                        {
                            // no swing at a car behind a hut or a wall: go round first
                            if (IsMeleeFoot && !MeleeLineClear(player, dt, true)) { MeleeBlocked++; attackTimer = 0.25f; SetState(State.Chase); break; }
                            windup = spec.kind == TargetKind.Boss ? 0.5f : spec.windupTime;
                            attackAnim = 0;
                        }
                        break;
                    }
                case State.Return:
                    {
                        MoveTowards(home, Mathf.Min(spec.speed, 4.5f) * 1.15f, dt, 0.6f);
                        hp = System.Math.Min(maxHp, hp + maxHp * (spec.kind == TargetKind.Boss ? 0.04 : 0.25) * dt);
                        if (Flat(transform.position - home).magnitude < 1.2f) SetState(State.Idle);
                        else if (playerOk && (Arena.HasValue || (dist < spec.aggro && Flat(player.Pos - home).magnitude < leash * 0.75f))) SetState(State.Chase);
                        break;
                    }
                case State.Special:
                    UpdateSpecial(dt, player);
                    break;
            }

            // attack windup → strike
            if (windup >= 0)
            {
                windup -= dt;
                attackAnim += dt;
                if (windup < 0)
                {
                    attackTimer = spec.attackInterval * Random.Range(0.9f, 1.1f);
                    AnimStrikeTime = Time.time;
                    AnimStrikeLanded = false;
                    if (spec.ranged)
                    {
                        burstLeft = Mathf.Max(1, spec.burst);
                        burstTimer = 0f;
                    }
                    else if (dist <= reach + 0.8f && playerOk && (!IsMeleeFoot || MeleeLineClear(player, dt, true)))
                    {
                        player.TakeDamage(spec.damage, transform.position);
                        AnimStrikeLanded = true;
                        if (IsVehicleLike) { knockback = 0.35f; knockDir = -toP.normalized; }
                    }
                    if (mutant != null && !spec.ranged) mutant.OnStrike(AnimStrikeLanded);
                    attackAnim = -0.25f; // recovery
                }
            }

            // ranged volley (single shot or machine-gun burst)
            if (burstLeft > 0)
            {
                burstTimer -= dt;
                if (burstTimer <= 0f)
                {
                    burstLeft--;
                    burstTimer = 0.1f;
                    FireShot(player);
                }
            }

            // boss special attacks
            if (spec.kind == TargetKind.Boss && (state == State.Chase || state == State.Attack) && windup < 0)
            {
                specialTimer -= dt;
                if (specialTimer <= 0) StartSpecial(player);
            }

            // boss leash: heal if the player leaves the arena for a while
            if (spec.kind == TargetKind.Boss)
            {
                bool away = Arena.HasValue ? !playerOk : Flat(player.Pos - home).magnitude > leash + 6f;
                if (away) outOfArenaTimer += dt; else outOfArenaTimer = 0;
                if (outOfArenaTimer > 4f) hp = System.Math.Min(maxHp, hp + maxHp * 0.03 * dt);
            }

            if (knockback > 0)
            {
                knockback -= dt;
                Step(knockDir * (IsVehicleLike ? 6f : 4f) * dt);
            }

            // zone-2 mutants are bulky (crabs, toads, a car-creature): two of them closing in on the car are eased apart
            // round it instead of standing inside each other. Positions only, through Step (rocks and walls still stop
            // them), never towards or away from the car and never during a wind-up, so reach and damage stay as they were.
            if (mutant != null && spec.kind != TargetKind.Boss && windup < 0 && (state == State.Chase || state == State.Attack))
                Separate(dt, player);

            // foot soldiers / buggies have no colliders: the car shoves them out of its way (same level only: a car
            // flying over them or driving on the floor above leaves them alone)
            if (spec.kind != TargetKind.Boss && player.Alive && Mathf.Abs(player.Pos.y - transform.position.y) < 1.3f)
            {
                var away = transform.position - player.Pos; away.y = 0;
                float minD = player.Radius * 1.05f + Radius * 0.6f;
                float dd = away.magnitude;
                if (dd < minD)
                {
                    var n = dd > 0.01f ? away / dd : -player.transform.forward;
                    Step(n * (minD - dd));
                    if (player.Speed > 4f && knockback <= 0f)
                    {
                        knockback = 0.25f; knockDir = (n + player.Velocity.normalized * 0.5f).normalized;
                        player.Jolt(-n, 0.25f);
                        Game.I.sfx.Play(spec.kind == TargetKind.Vehicle ? Sfx.Kind.Crash : Sfx.Kind.Hurt, transform.position, 0.45f);
                    }
                }
            }

            Animate(dt);
        }

        /// <summary>A point at weapon range, a bit around the car: ranged vehicles circle while they shoot.</summary>
        Vector3 OrbitGoal(Player player, Vector3 dirFromP)
        {
            var side = Quaternion.Euler(0, 35f * orbitSign, 0) * dirFromP;
            if (Random.value < 0.002f) orbitSign = -orbitSign;
            return player.Pos + side * spec.attackRange * 0.8f;
        }

        void FireShot(Player player)
        {
            if (!player.Alive) { burstLeft = 0; return; }
            Vector3 from = rig != null && rig.muzzle != null ? rig.muzzle.position
                         : transform.position + Vector3.up * 1.4f * spawn.scale + transform.forward * 0.5f;
            float lead = spec.proj == ProjKind.Bullet ? 0.12f : 0.3f;
            var aim = player.Pos + player.Velocity * lead;
            if (spec.burst > 1) aim += Random.insideUnitSphere * 0.9f;
            double dmg = spec.damage / Mathf.Max(1, spec.burst);
            Projectile.Fire(from, aim, dmg, zone, spec.proj);
            if (mutant != null) mutant.OnShot();
            switch (spec.proj)
            {
                case ProjKind.Bullet:
                    Game.I.sfx.Play(Sfx.Kind.EnemyGun, transform.position, spec.burst > 1 ? 0.5f : 0.6f);
                    Game.I.fx.MuzzleSmoke(from, (aim - from).normalized);
                    break;
                case ProjKind.Slug:
                    Game.I.sfx.Play(Sfx.Kind.Cannon, transform.position, 0.55f, 0.72f);
                    Game.I.fx.MuzzleSmoke(from, (aim - from).normalized);
                    break;
                case ProjKind.Spear:
                    Game.I.sfx.Play(Sfx.Kind.Throw, transform.position, 0.7f);
                    break;
                default:
                    Game.I.sfx.Play(Sfx.Kind.Shoot, transform.position, 0.6f);
                    break;
            }
        }

        void StartSpecial(Player player)
        {
            state = State.Special;
            specialPhase = 0;
            specialT = 0;
            specialHit = false;
            if (tele == null) tele = Telegraph.Create();
            if (IsVehicleLike)
            {
                specialKind = 0; // charge
                specialDir = Flat(player.Pos - transform.position).normalized;
                if (specialDir.sqrMagnitude < 0.01f) specialDir = transform.forward;
                chargeLen = 18f;
                chargeHitsWall = false;
                if (Arena.HasValue)
                {
                    // in the hangar the charge ends at the wall: the warning shows exactly how far it goes
                    float toWall = DistanceToArenaEdge(transform.position, specialDir) - spec.radius * 0.6f;
                    if (toWall < chargeLen) { chargeLen = Mathf.Max(4f, toWall); chargeHitsWall = true; }
                }
                tele.ShowLine(transform.position, specialDir, chargeLen + spec.radius, 4.2f);
#if UNITY_EDITOR
                if (Arena.HasValue) Debug.Log($"RoadGame BOSS charge t={Time.time:0.0} len={chargeLen:0.0} wall={chargeHitsWall} from={transform.position}");
#endif
            }
            else
            {
                specialKind = 1; // slam
                specialPoint = player.Pos;
                tele.ShowCircle(specialPoint, 5.5f);
            }
            Game.I.sfx.Play(specialKind == 0 ? Sfx.Kind.Warn : Sfx.Kind.Rumble, transform.position, 0.9f);
        }

        void UpdateSpecial(float dt, Player player)
        {
            specialT += dt;
            if (specialKind == 0)
            {
                if (specialPhase == 0)
                {
                    FaceTowards(transform.position + specialDir, dt, 720f);
                    tele.Progress(specialT / 0.9f);
                    speedNow = Mathf.MoveTowards(speedNow, 0, 30 * dt);
                    if (specialT >= 0.9f) { specialPhase = 1; specialT = 0; tele.Hide(); }
                }
                else
                {
                    float sp = spec.speed * 4.2f;
                    Step(specialDir * sp * dt);
                    speedNow = sp;
                    if (!specialHit && player.Alive && Flat(player.Pos - transform.position).magnitude < spec.radius + player.Radius + 0.5f)
                    {
                        specialHit = true;
                        player.TakeDamage(spec.damage * 2.0, transform.position);
                        Game.I.cameraRig.Shake(0.5f);
                    }
                    if (specialT > chargeLen / sp || (!Arena.HasValue && Flat(transform.position - home).magnitude > leash + 2f))
                    {
                        if (chargeHitsWall)
                        {
                            // slams into the hangar wall: dust, a jolt, then it backs off and turns around
                            var p = transform.position + specialDir * spec.radius;
                            Game.I.fx.Slam(p, 3.2f);
                            Game.I.sfx.Play(Sfx.Kind.Crash, p, 0.9f);
                            Game.I.cameraRig.Shake(0.35f);
                            knockback = 0.3f; knockDir = -specialDir;
#if UNITY_EDITOR
                            Debug.Log($"RoadGame BOSS wall slam t={Time.time:0.0} at={transform.position}");
#endif
                        }
                        state = State.Chase; specialTimer = Random.Range(5f, 7.5f);
                    }
                }
            }
            else
            {
                FaceTowards(specialPoint, dt, 360f);
                speedNow = Mathf.MoveTowards(speedNow, 0, 30 * dt);
                tele.Progress(specialT / 1.1f);
                if (specialPhase == 0 && rig.armR) rig.armR.localRotation = Quaternion.Euler(-170f * Mathf.Clamp01(specialT / 0.9f), 0, 0);
                if (specialT >= 1.1f)
                {
                    tele.Hide();
                    Game.I.fx.Slam(specialPoint, 5.5f);
                    Game.I.cameraRig.Shake(0.6f);
                    Game.I.sfx.Play(Sfx.Kind.Explode, specialPoint, 1f);
                    if (player.Alive && Flat(player.Pos - specialPoint).magnitude < 5.5f + player.Radius * 0.5f)
                        player.TakeDamage(spec.damage * 2.2, specialPoint);
                    state = State.Chase; specialTimer = Random.Range(5.5f, 8f);
                }
            }
        }

        void MoveTowards(Vector3 goal, float speed, float dt, float stopDist)
        {
            // intro scouts keep up with the car (the first fight happens while driving, inside the cannon's reach)
            if (spec.pace && state != State.Idle && state != State.Return && Game.I.player != null)
                speed = Mathf.Max(speed, Game.I.player.Speed * 1.08f + 1.5f);
            Vector3 d = Flat(goal - transform.position);
            float m = d.magnitude;
            float target = m > stopDist ? speed : 0f;
            speedNow = Mathf.MoveTowards(speedNow, target, (IsVehicleLike ? 10f : 18f) * dt);
            if ((state == State.Chase || state == State.Return) && m > stopDist + 0.3f) TrackProgress(m, dt);
            if (m > 0.05f)
            {
                // the way to the goal is checked a little ahead: blocked -> the nearest open bearing, or a stop
                var dir = Steer(d / m, Mathf.Min(m, IsVehicleLike ? 5f : 1.8f), dt);
                if (dir == Vector3.zero) { speedNow = Mathf.MoveTowards(speedNow, 0f, 30f * dt); FaceTowards(goal, dt, 120f); Step(Vector3.zero); return; }
                var steerGoal = transform.position + dir * Mathf.Max(2f, m);
                if (IsVehicleLike)
                {
                    FaceTowards(steerGoal, dt, spec.kind == TargetKind.Boss ? 90f : 160f);
                    Step(transform.forward * speedNow * dt);
                }
                else
                {
                    FaceTowards(steerGoal, dt, 600f);
                    Step(dir * Mathf.Min(speedNow * dt, m));
                }
            }
            else Step(Vector3.zero);
        }

        /// <summary>
        /// Eases a zone-2 mutant out of the other live mutants it overlaps (ground radii of the models), at most 3 m/s.
        /// The push only runs along the circle round the car, never towards or away from it, so a crowd spreads round the
        /// car and nobody is kept out of reach (a slow brute still walks up through the crabs).
        /// </summary>
        void Separate(float dt, Player player)
        {
            if (World.I == null) return;
            var list = World.I.activeTargets;
            Vector3 pos = transform.position, push = Vector3.zero;
            Vector3 radial = pos - player.Pos; radial.y = 0f;
            radial = radial.sqrMagnitude > 1e-4f ? radial.normalized : transform.forward;
            var tangent = new Vector3(-radial.z, 0f, radial.x);
            float mine = mutant.Footprint;
            int myId = spawn != null ? spawn.id : 0;
            for (int i = 0; i < list.Count; i++)
            {
                if (!(list[i] is Enemy o) || o == this || o.dead || o.mutant == null || o.spec.kind == TargetKind.Boss) continue;
                Vector3 d = pos - o.transform.position;
                if (Mathf.Abs(d.y) > 1.5f) continue;
                d.y = 0f;
                float min = (mine + o.mutant.Footprint) * 0.85f;
                float m2 = d.sqrMagnitude;
                if (m2 >= min * min) continue;
                float m = Mathf.Sqrt(m2);
                float side = m > 0.01f ? Vector3.Dot(d / m, tangent) : 0f;
                // one straight behind the other: the pair splits to opposite sides (by spawn id)
                if (Mathf.Abs(side) < 0.3f) side = myId < (o.spawn != null ? o.spawn.id : 0) ? 1f : -1f;
                push += tangent * (Mathf.Sign(side) * (min - m));
            }
            if (push.sqrMagnitude > 1e-6f) Step(Vector3.ClampMagnitude(push, 3f * dt));
        }

        // ------------------------------------------------------------------ obstacles
        static readonly RaycastHit[] castHits = new RaycastHit[12];
        static readonly Collider[] nearCols = new Collider[12];
        const float Skin = 0.04f;

        /// <summary>Footprint radius against rocks / walls / props, and the radius of the probe sphere (its height is limited
        /// so a big boss still fits under a tunnel lid: the rest of the footprint is a margin ahead).</summary>
        float BodyR => IsVehicleLike ? Mathf.Max(0.9f, Radius * 0.72f) : Mathf.Max(0.32f, Radius * 0.75f);
        float ProbeR => Mathf.Min(BodyR, 1.1f);
        Vector3 ProbeCenter(Vector3 at) => new Vector3(at.x, at.y + 0.3f + ProbeR, at.z);

        static bool IsObstacle(Collider c, Transform self)
        {
            if (c == null || !c.enabled || c.isTrigger) return false;
            if (c.attachedRigidbody != null) return false;                 // the car (it shoves enemies itself)
            return !c.transform.IsChildOf(self);
        }

        /// <summary>Distance an enemy can move along dir before its footprint meets an obstacle (dist if free).</summary>
        float FreeDistance(Vector3 from, Vector3 dir, float dist, out Vector3 normal)
        {
            normal = Vector3.zero;
            float margin = BodyR - ProbeR;
            int n = Physics.SphereCastNonAlloc(ProbeCenter(from), ProbeR, dir, castHits, dist + margin + Skin, Player.ObstacleMask, QueryTriggerInteraction.Ignore);
            float best = dist;
            for (int i = 0; i < n; i++)
            {
                var h = castHits[i];
                if (!IsObstacle(h.collider, transform)) continue;
                if (h.distance <= 0f)
                {
                    // already touching: blocked only when the move goes into it (sliding along or backing off is free).
                    // Treating every touch as open let an enemy step into a hut, get pushed out and step in again forever.
                    if (h.collider is MeshCollider mc && !mc.convex) continue;  // no closest point on a concave mesh: the push-out handles it
                    var center = ProbeCenter(from);
                    var away = center - h.collider.ClosestPoint(center); away.y = 0f;
                    if (away.sqrMagnitude < 1e-6f) { away = center - h.collider.bounds.center; away.y = 0f; }
                    if (away.sqrMagnitude < 1e-6f) continue;
                    away.Normalize();
                    if (Vector3.Dot(dir, away) < -0.1f) { best = 0f; normal = away; }
                    continue;
                }
                float free = Mathf.Max(0f, h.distance - margin - Skin);
                if (free < best) { best = free; normal = h.normal; }
            }
            return best;
        }

        /// <summary>No real progress (it barely moved and got no closer) for 1.2 s while it wants to go somewhere: it goes
        /// round the other way. Escapes the inside of a palisade corner or a long wall picked from the wrong end.</summary>
        void TrackProgress(float distToGoal, float dt)
        {
            progressTimer += dt;
            if (progressTimer < 1.2f) return;
            float moved = Flat(transform.position - progressPos).magnitude;
            bool closer = distToGoal < progressBest - 0.3f;
            if (moved < 0.5f && !closer && speedNow > 0.5f && progressBest < float.MaxValue)
            {
                detourSide = detourSide == 0f ? -avoidSide : -detourSide;
                avoidSide = detourSide;
                detourHold = 2f;
                StuckFlips++;
            }
            progressTimer = 0f;
            progressPos = transform.position;
            progressBest = distToGoal;
        }

        /// <summary>Straight on if the way is open, else the nearest open bearing on the side it is going round; zero if boxed in.</summary>
        Vector3 Steer(Vector3 dir, float look, float dt)
        {
            long t0 = System.Diagnostics.Stopwatch.GetTimestamp();
            var r = SteerInner(dir, look, dt);
            MoveTicks += System.Diagnostics.Stopwatch.GetTimestamp() - t0;
            return r;
        }

        Vector3 SteerInner(Vector3 dir, float look, float dt)
        {
            avoidTimer -= dt;
            if (detourHold > 0f) detourHold -= dt;
            var pos = transform.position;
            if (FreeDistance(pos, dir, look, out var n) >= look - 0.01f)
            {
                if (detourHold <= 0f) detourSide = 0f;
                return dir;
            }
            // blocked: walk round the obstacle along its surface, keeping one side for the whole detour (a big hut or a
            // rock is followed round instead of being nudged from both sides in turn)
            n.y = 0f;
            if (n.sqrMagnitude > 1e-4f)
            {
                n.Normalize();
                var left = new Vector3(-n.z, 0f, n.x);
                if (detourSide == 0f)
                {
                    float dl = Vector3.Dot(left, dir);
                    if (Mathf.Abs(dl) > 0.15f) detourSide = Mathf.Sign(dl);
                    else detourSide = FreeDistance(pos, left, look, out _) >= FreeDistance(pos, -left, look, out _) ? 1f : -1f;
                }
                detourHold = Mathf.Max(detourHold, 0.5f);
                var along = left * detourSide;
                if (FreeDistance(pos, along, look * 0.6f, out _) >= look * 0.6f - 0.01f) return along;
                avoidSide = Vector3.Dot(Quaternion.Euler(0, 50f, 0) * dir, along) > 0f ? 1f : -1f;
                avoidTimer = 0.8f;
            }
            if (avoidTimer <= 0f)
            {
                // pick the side with more room
                float l = FreeDistance(pos, Quaternion.Euler(0, -50f, 0) * dir, look, out _);
                float r = FreeDistance(pos, Quaternion.Euler(0, 50f, 0) * dir, look, out _);
                avoidSide = r >= l ? 1f : -1f;
            }
            for (int k = 1; k <= 6; k++)
            {
                float ang = k * 25f;
                for (int sIdx = 0; sIdx < 2; sIdx++)
                {
                    float side = sIdx == 0 ? avoidSide : -avoidSide;
                    var d2 = Quaternion.Euler(0, ang * side, 0) * dir;
                    if (FreeDistance(pos, d2, look * 0.7f, out _) >= look * 0.7f - 0.01f)
                    {
                        avoidSide = side;
                        avoidTimer = 0.8f;
                        return d2;
                    }
                }
            }
            return Vector3.zero;
        }

        /// <summary>
        /// Moves on the ground: rocks, walls, buildings and props stop it (it slides along them), it never walks off a
        /// ledge into another level, stays inside its boss room, and stands on the floor it is on (surface, tunnel, ramp).
        /// </summary>
        void Step(Vector3 delta)
        {
            long t0 = System.Diagnostics.Stopwatch.GetTimestamp();
            StepInner(delta);
            MoveTicks += System.Diagnostics.Stopwatch.GetTimestamp() - t0;
        }

        void StepInner(Vector3 delta)
        {
            var pos = transform.position;
            delta.y = 0f;
            // slide: move up to the first obstacle, then along it with what is left (twice for corners)
            for (int iter = 0; iter < 2; iter++)
            {
                float len = delta.magnitude;
                if (len < 1e-5f) break;
                var dir = delta / len;
                float free = FreeDistance(pos, dir, len, out var n);
                if (free >= len - 1e-4f) { pos += delta; delta = Vector3.zero; break; }
                ObstacleContacts++;
                pos += dir * free;
                n.y = 0f;
                if (n.sqrMagnitude < 1e-4f) { delta = Vector3.zero; break; }
                n.Normalize();
                var rest = delta - dir * free;
                delta = rest - n * Vector3.Dot(rest, n);
            }
            var next = PushOut(pos);
            if (next.z > maxZ) next.z = Mathf.Min(maxZ, transform.position.z);
            if (Arena.HasValue)
            {
                var a = Arena.Value;
                var l = a.Local(next.x, next.z);
                float m = spec.radius * 0.7f;
                l.x = Mathf.Clamp(l.x, -a.half.x + m, a.half.x - m);
                l.y = Mathf.Clamp(l.y, -a.half.y + m, a.half.y - m);
                next = a.World(l.x, l.y, next.y);
            }
            var cur = transform.position;
            var g = Ground.Sample(next.x, next.z, cur.y);
            if (!g.valid || g.h < cur.y - 1.2f || (g.piece != null && !g.piece.enemyWalkable))
            {
                // a drop or a ramp deck ahead: stay on this level
                g = Ground.Sample(cur.x, cur.z, cur.y);
                next = cur;
            }
            next.y = g.valid ? g.h : cur.y;
            transform.position = next;
        }

        /// <summary>Pushes the footprint out of any obstacle it overlaps (spawned into one, shoved into one by the car).</summary>
        Vector3 PushOut(Vector3 p)
        {
            float r = ProbeR;
            var c = ProbeCenter(p);
            int n = Physics.OverlapSphereNonAlloc(c, r + (BodyR - r) * 0.5f, nearCols, Player.ObstacleMask, QueryTriggerInteraction.Ignore);
            for (int i = 0; i < n; i++)
            {
                var col = nearCols[i];
                if (!IsObstacle(col, transform)) continue;
                if (col is MeshCollider mc && !mc.convex) continue;
                var cp = col.ClosestPoint(c);
                var away = c - cp; away.y = 0f;
                float d = away.magnitude;
                float want = BodyR * 0.85f;
                if (d < 1e-3f)
                {
                    // the centre is inside: back out toward where it came from
                    var back = transform.position - p; back.y = 0f;
                    if (back.sqrMagnitude < 1e-4f) back = -transform.forward;
                    p += back.normalized * 0.25f;
                }
                else if (d < want) p += away / d * (want - d);
                c = ProbeCenter(p);
            }
            return p;
        }

        /// <summary>Distance from a point to the arena edge along a direction (for charges inside the hangar).</summary>
        float DistanceToArenaEdge(Vector3 from, Vector3 dir)
        {
            var a = Arena.Value;
            var l = a.Local(from.x, from.z);
            var ld = new Vector2(dir.x * a.cos - dir.z * a.sin, dir.x * a.sin + dir.z * a.cos);
            float t = 999f;
            if (Mathf.Abs(ld.x) > 1e-4f) t = Mathf.Min(t, ((ld.x > 0 ? a.half.x : -a.half.x) - l.x) / ld.x);
            if (Mathf.Abs(ld.y) > 1e-4f) t = Mathf.Min(t, ((ld.y > 0 ? a.half.y : -a.half.y) - l.y) / ld.y);
            return Mathf.Max(0f, t);
        }

        /// <summary>The car is a valid opponent only on the same level and in plain sight (walls, lids, the ground between block it).</summary>
        void UpdateSight(Player player, float dt, float flatDist)
        {
            sightTimer -= dt;
            if (sightTimer > 0f) return;
            sightTimer = 0.25f + Random.value * 0.1f;
            if (!Ground.SameLevel(player.Pos, transform.position)) { canSee = false; return; }
            if (flatDist > 40f) { canSee = true; return; }
            var eye = transform.position + Vector3.up * Mathf.Min(1.4f, spec.height * spawn.scale * 0.5f);
            canSee = !Ground.Blocked(eye, player.Pos + Vector3.up * 0.9f);
        }

        void FaceTowards(Vector3 p, float dt, float degPerSec)
        {
            var d = Flat(p - transform.position);
            if (d.sqrMagnitude < 0.0001f) return;
            float want = Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg;
            heading = Mathf.MoveTowardsAngle(heading, want, degPerSec * dt);
            transform.rotation = Quaternion.Euler(0, heading, 0);
        }

        void Animate(float dt)
        {
            if (mutant != null) { mutant.Tick(dt); return; }
            if (rig == null) return;
            if (IsVehicleLike)
            {
                float spin = speedNow * dt / Mathf.Max(0.2f, rig.wheelRadius) * Mathf.Rad2Deg;
                foreach (var w in rig.wheels) w.Rotate(spin, 0, 0, Space.Self);
                if (rig.body) rig.body.localRotation = Quaternion.Euler(-speedNow * 0.25f, 0, Mathf.Sin(Time.time * 18f) * speedNow * 0.06f);
                if (rig.turret != null && Game.I != null && Game.I.player != null)
                {
                    var target = Engaged ? Game.I.player.Pos : transform.position + transform.forward;
                    var local = rig.turret.parent.InverseTransformPoint(target);
                    float want = Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;
                    var e = rig.turret.localEulerAngles;
                    rig.turret.localRotation = Quaternion.Euler(0, Mathf.MoveTowardsAngle(e.y, want, 400f * dt), 0);
                }
                return;
            }
            float moving = Mathf.Clamp01(speedNow / Mathf.Max(0.1f, spec.speed));
            walkPhase += dt * (4f + speedNow * 2.4f) / Mathf.Max(0.8f, spawn.scale * 0.8f);
            float sw = Mathf.Sin(walkPhase) * 38f * moving;
            if (rig.legL) rig.legL.localRotation = Quaternion.Euler(sw, 0, 0);
            if (rig.legR) rig.legR.localRotation = Quaternion.Euler(-sw, 0, 0);
            if (rig.armL) rig.armL.localRotation = Quaternion.Euler(-sw * 0.8f, 0, 0);
            if (rig.body) rig.body.localPosition = new Vector3(0, Mathf.Abs(Mathf.Sin(walkPhase)) * 0.06f * moving, 0);
            if (rig.armR)
            {
                float a;
                if (windup >= 0)
                {
                    float wTot = spec.kind == TargetKind.Boss ? 0.5f : spec.windupTime;
                    float k = Mathf.Clamp01(1f - windup / wTot);
                    a = Mathf.Lerp(-30f, -165f, k);
                    if (spec.ranged) a = -90f;
                }
                else if (attackAnim < 0)
                {
                    attackAnim += dt;
                    a = Mathf.Lerp(-35f, -10f, Mathf.Clamp01(1f + attackAnim / 0.25f));
                    if (spec.ranged) a = -90f;
                }
                else a = spec.ranged ? (state == State.Attack ? -90f : sw * 0.6f) : (state == State.Attack || state == State.Chase ? -40f + sw * 0.3f : sw * 0.8f);
                rig.armR.localRotation = Quaternion.Euler(a, 0, 0);
                if (spec.ranged && rig.armL && state == State.Attack) rig.armL.localRotation = Quaternion.Euler(-80, 0, 20);
            }
        }

        static Vector3 Flat(Vector3 v) { v.y = 0; return v; }

        void OnDisable()
        {
            if (tele != null) tele.Hide();
        }
    }

    /// <summary>Red ground telegraph for boss specials (circle slam / charge line).</summary>
    public class Telegraph : MonoBehaviour
    {
        MeshRenderer fill, ring, backing, lane;
        Transform fillT;
        bool line;
        float size;

        public static Telegraph Create()
        {
            var go = new GameObject("Telegraph");
            var t = go.AddComponent<Telegraph>();
            // dark backing ring under the red edge: the warning stays readable on sand, terracotta and salt
            var k = Models.MeshGO("Backing", Models.FlatQuad(), Mats.NewUnlit("TeleBacking", Tex.RingTex(0.1f), false), go.transform, false);
            k.GetComponent<MeshRenderer>().sharedMaterial.SetColor("_BaseColor", new Color(0.18f, 0.05f, 0.05f, 0.45f));
            k.GetComponent<MeshRenderer>().sharedMaterial.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent - 2;
            var f = Models.MeshGO("Fill", Models.FlatQuad(), Mats.NewUnlit("TeleFill", Tex.SoftCircle(), false), go.transform, false);
            f.GetComponent<MeshRenderer>().sharedMaterial.SetColor("_BaseColor", new Color(1f, 0.22f, 0.14f, 0.58f));
            var r = Models.MeshGO("Ring", Models.FlatQuad(), Mats.NewUnlit("TeleRing", Tex.RingTex(0.06f), false), go.transform, false);
            r.GetComponent<MeshRenderer>().sharedMaterial.SetColor("_BaseColor", new Color(1f, 0.3f, 0.2f, 1f));
            r.GetComponent<MeshRenderer>().sharedMaterial.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent + 2;
            t.fill = f.GetComponent<MeshRenderer>(); t.ring = r.GetComponent<MeshRenderer>(); t.fillT = f.transform;
            t.backing = k.GetComponent<MeshRenderer>();
            // a charge shows its whole lane from the first moment (faint), the fill then runs along it: where it will go
            // and how far is readable at once, not only at the end
            var ln = Models.MeshGO("Lane", Models.FlatQuad(), Mats.NewUnlit("TeleLane", null, false), go.transform, false);
            ln.GetComponent<MeshRenderer>().sharedMaterial.SetColor("_BaseColor", new Color(0.75f, 0.12f, 0.08f, 0.3f));
            ln.GetComponent<MeshRenderer>().sharedMaterial.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent - 2;
            t.lane = ln.GetComponent<MeshRenderer>();
            t.lane.enabled = false;
            go.SetActive(false);
            return t;
        }

        public void ShowCircle(Vector3 c, float radius)
        {
            line = false; size = radius;
            transform.position = new Vector3(c.x, Ground.FloorY(c + Vector3.up * 0.5f) + 0.06f, c.z);
            transform.rotation = Quaternion.identity;
            ring.transform.localScale = new Vector3(radius, 1, radius);
            backing.transform.localScale = new Vector3(radius * 1.04f, 1, radius * 1.04f);
            backing.enabled = true;
            if (lane != null) lane.enabled = false;
            fill.sharedMaterial.SetTexture("_BaseMap", Tex.HardCircle());
            fillT.localScale = Vector3.zero;
            fillT.localPosition = Vector3.zero;
            ring.enabled = true;
            gameObject.SetActive(true);
        }

        public void ShowLine(Vector3 from, Vector3 dir, float length, float width)
        {
            line = true; size = length;
            transform.position = new Vector3(from.x, Ground.FloorY(from + Vector3.up * 0.5f) + 0.06f, from.z);
            transform.rotation = Quaternion.LookRotation(dir, Vector3.up);
            ring.enabled = false;
            backing.enabled = false;
            if (lane != null)
            {
                lane.enabled = true;
                lane.transform.localScale = new Vector3(width * 0.5f, 1, length * 0.5f);
                lane.transform.localPosition = new Vector3(0, -0.01f, length * 0.5f);
            }
            fill.sharedMaterial.SetTexture("_BaseMap", null);
            fillT.localScale = new Vector3(width * 0.5f, 1, 0.01f);
            fillT.localPosition = Vector3.zero;
            gameObject.SetActive(true);
        }

        public void Progress(float k)
        {
            k = Mathf.Clamp01(k);
            if (line)
            {
                float w = fillT.localScale.x;
                fillT.localScale = new Vector3(w, 1, size * 0.5f * k);
                fillT.localPosition = new Vector3(0, 0, size * 0.5f * k);
            }
            else fillT.localScale = new Vector3(size * k, 1, size * k);
        }

        public void Hide()
        {
            if (this != null && gameObject != null) gameObject.SetActive(false);
        }
    }
}
