using System;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;

namespace RoadGame
{
    /// <summary>
    /// Bootstrap + orchestration. Everything (world, car, UI, materials, sounds) is generated at runtime,
    /// so the Game scene only needs one GameObject with this component.
    /// </summary>
    [DefaultExecutionOrder(-100)]
    public class Game : MonoBehaviour
    {
        public static Game I;

        public Progress progress;
        public World world;
        public Player player;
        public Camera cam;
        public CameraRig cameraRig;
        public Fx fx;
        public Sfx sfx;
        public Hud hud;
        public Overlay overlay;
        public Light sun;
        [NonSerialized] public Target focusTarget;
        public float RespawnIn { get; private set; }

        /// <summary>Automation hooks (used by the editor capture tool / tests).</summary>
        public static bool Autopilot;
        public static bool AutopilotBoss;
        public static bool AutopilotEnemiesOnly;
        /// <summary>Test bot: the autopilot leaves the bosses alone (farming until the goal says "ready").</summary>
        public static bool AutopilotAvoidBoss;
        /// <summary>Test bot: in a boss fight the autopilot keeps fighting at low HP (a player told "ready" would).</summary>
        public static bool AutopilotStayInFight;
        public static Action<Progress> TestSetup;
        /// <summary>Scripted joystick input (test harness): session time -> stick vector.</summary>
        public static Func<float, Vector2> ScriptedInput;

        bool _paused;
        float demoSlowMoUntil = -1f;
        // hit-stop: a few real-time hundredths of a second of slow time on the big moments (boss down, a car-creature or
        // a buggy blowing up, a heavy blow on the car). Real time, so pause and the Dev speed come back exactly.
        float hitStopUntil = -1f, hitStopScale = 1f;
        public bool paused
        {
            get => _paused;
            set
            {
                _paused = value;
                RefreshTimeScale();
                // a menu takes the screen: a thumb that was steering lets go (no stale stick when it closes)
                if (value && hud != null && hud.joystick != null) hud.joystick.Release();
            }
        }

        public void RefreshTimeScale()
        {
            float cinematic = Time.unscaledTime < demoSlowMoUntil ? 0.3f : 1f;
            float stop = Time.unscaledTime < hitStopUntil ? hitStopScale : 1f;
            Time.timeScale = _paused ? 0f : DevOptions.Speed * cinematic * stop;
        }

        /// <summary>Hit-stop: game time runs at `scale` for `realSeconds` of real time. Overlapping stops keep the deepest
        /// slow and the latest end; nothing while paused. The normal speed (Dev 1x/2x/4x, a demo slow-mo) comes back by
        /// itself.</summary>
        public void HitStop(float realSeconds, float scale)
        {
            if (_paused || realSeconds <= 0f) return;
            float now = Time.unscaledTime, until = now + Mathf.Min(realSeconds, 0.2f);
            if (now < hitStopUntil) { hitStopScale = Mathf.Min(hitStopScale, scale); hitStopUntil = Mathf.Max(hitStopUntil, until); }
            else { hitStopScale = Mathf.Clamp(scale, 0.02f, 1f); hitStopUntil = until; }
            HitStops++;
            RefreshTimeScale();
        }

        /// <summary>Hit-stops started this session (tests).</summary>
        public static int HitStops;
        public bool InHitStop => Time.unscaledTime < hitStopUntil;

        public long freeGemsAt { get => progress.d.freeGemsAt; set => progress.d.freeGemsAt = value; }

        float saveTimer;
        static float lastRecover = -100f;
        int currentZone = -1;
        int zoneFrom, zoneTo;
        float moodT = 1f;
        float playTimer;
        public float SessionTime { get; private set; }
        // after a weapon level: its hits come up as green "boosted" numbers for a while
        public int BoostWeapon { get; private set; } = -1;
        public float BoostUntil { get; private set; } = -1f;
        int boostHits;
        /// <summary>Test hooks: the demo of a new weapon's first area hit (session time, targets hit).</summary>
        public static float LastDemoAt = -1f;
        public static int LastDemoHits;
        Vector2 autoInput;
        float autoRetarget;
        Vector3 autoGoal;

        /// <summary>Domain reload may be disabled on Play: reset all static caches at the start of every session.</summary>
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics()
        {
            I = null;
            World.I = null;
            ScriptedInput = null;
            AutopilotEnemiesOnly = false;
            AutopilotAvoidBoss = false;
            AutopilotStayInFight = false;
            LastDemoAt = -1f; LastDemoHits = 0;
            Player.AllowOutOfBounds = false;
            Mats.Reset();
            Tex.Reset();
            Models.Reset();
            Projectile.ResetPool();
            Turret.ResetStatics();
            Harpooner.ResetStatics();
            DevOptions.ResetForPlay();
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void AutoBoot()
        {
            // Safety net: if the Game scene is opened without the bootstrap object, create it.
            if (I == null && SceneManager.GetActiveScene().name == "Game" && FindAnyObjectByType<Game>() == null)
                new GameObject("Game").AddComponent<Game>();
        }

        bool ready;
        public bool Ready => ready;
        LoadingScreen loading;

        void Awake()
        {
            if (I != null && I != this) { Destroy(gameObject); return; }
            I = this;
            Application.targetFrameRate = 60;
            QualitySettings.vSyncCount = 0;
            Screen.sleepTimeout = SleepTimeout.NeverSleep;
            RefreshTimeScale();
            cam = Camera.main;
            loading = LoadingScreen.Create();
        }

        /// <summary>Builds the session over several frames behind the loading screen (keeps phones responsive).</summary>
        System.Collections.IEnumerator Start()
        {
            if (I != this) yield break;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            yield return null;
            Mats.Init();
            long tMats = sw.ElapsedMilliseconds;
            progress = new Progress(SaveSystem.Load());
            TestSetup?.Invoke(progress);
            if (progress.d.nextBonusAt == 0) progress.d.nextBonusAt = Progress.NowMs + 45000;
            SetupRendering();
            loading.SetProgress(0.1f);
            yield return null;

            long tRender = sw.ElapsedMilliseconds;
            fx = Fx.Create();
            sfx = Sfx.Create();
            long tAudio = sw.ElapsedMilliseconds;
            sfx.on = progress.d.soundOn;
            sfx.musicOn = progress.d.musicOn;
            loading.SetProgress(0.25f);
            yield return null;

            world = new GameObject("World").AddComponent<World>();
            yield return world.GenerateRoutine(k => loading.SetProgress(0.25f + 0.55f * k));
            world.ApplyGateStates(false);
            long tWorld = sw.ElapsedMilliseconds;

            Vector3 spawn = world.startPos;
            float yaw = 0f;
            var sp = new Vector3(progress.d.px, progress.d.py, progress.d.pz);
            if (progress.d.introPending)
            {
                // a new game opens with the intro run: straight canyon road, car pointing north
                spawn = Structures.IntroStart; yaw = 0f;
            }
            else if (progress.d.tutorialDone && Content.ZoneIndexAt(sp.z) <= progress.d.unlockedZone
                     && (DustFlatsSurfaces.Active && sp.z <= Content.ZoneMaxZ(0)
                         ? DustFlatsSurfaces.ContainsBoundary(sp.x, sp.z)
                         : Mathf.Abs(sp.x) < Content.ZoneHalfWidth - 4f)
                     && sp.z > Content.ZoneMinZ(0) && SpawnSpotFree(sp))
            {
                spawn = sp; yaw = progress.d.heading;
            }
            long tCar0 = sw.ElapsedMilliseconds;
            player = Player.Create(spawn, yaw);
            long tCar = sw.ElapsedMilliseconds - tCar0;
            sfx.engine = EngineAudio.Create(player);
            cameraRig = CameraRig.Create(cam, player.transform);
            loading.SetProgress(0.85f);
            yield return null;

            UI.EnsureEventSystem();
            overlay = Overlay.Create();
            hud = Hud.Create();
            if (progress.d.tutorialDone) hud.HideHint();
            if (progress.d.introPending) Intro.Begin(this);

            progress.WeaponLevelUp += id => OnWeaponLevelUp(id);
            progress.WeaponUnlocked += id =>
            {
                hud.ShowPopup(Tex.DamageIcon(Content.Weapons[id].type), "NEW WEAPON!", Content.Weapons[id].name + ": " + Goals.WeaponWhat[id]);
                if (id > 0) progress.d.tryWeapon = id;   // the goal widget: "try it on a group"
                sfx.Play(Sfx.Kind.Unlock, Vector3.zero, 0.9f);
                sfx.Duck(3f);
                hud.PulseWeapon(id);
            };
            progress.ArmorLevelUp += id =>
            {
                var lvl = progress.d.armorLevel[id];
                hud.ShowPopup(Tex.ArmorIcon(id), lvl <= 1 ? "NEW ARMOR!" : "ARMOR UP!", Content.Armors[id].name + " Lv " + lvl);
                sfx.Play(Sfx.Kind.LevelUp, Vector3.zero, 0.8f);
                sfx.Duck(2f, 0.6f);
                hud.PulseArmor(id);
            };
            progress.ZoneUnlocked += z =>
            {
                world.ApplyGateStates(true);
                hud.ShowBanner("NEW ZONE UNLOCKED", Content.Zones[z].name);
                sfx.Play(Sfx.Kind.Unlock, Vector3.zero, 1f);
                sfx.Play(Sfx.Kind.Gate, Vector3.zero, 0.8f);
                sfx.Duck(3f);
            };

            world.Tick();
            UpdateZone(true);
            ready = true;
            loading.SetProgress(1f);
            loading.Hide();
            Debug.Log("RoadGame: session built in " + sw.ElapsedMilliseconds + " ms (materials " + tMats + ", rendering " + (tRender - tMats) + ", fx+audio " + (tAudio - tRender) + ", world " + (tWorld - tAudio) + ", car " + tCar + ")");
            // Release the Web overlay only once the ready world and HUD have rendered a frame.
            // Art animations and display timers never delay the actual ready flag or native play.
            yield return new WaitForEndOfFrame();
            LoadingScreen.SignalReady();
        }

        // ------------------------------------------------------------------ rendering setup
        void SetupRendering()
        {
            if (cam == null) cam = Camera.main;
            if (cam == null)
            {
                var cg = new GameObject("Main Camera");
                cg.tag = "MainCamera";
                cam = cg.AddComponent<Camera>();
                cg.AddComponent<AudioListener>();
            }
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = Content.Zones[0].sky;
            var camData = cam.GetUniversalAdditionalCameraData();
            if (camData != null)
            {
                camData.renderPostProcessing = true;
                camData.antialiasing = AntialiasingMode.None;
                camData.renderShadows = true;
            }

            foreach (var l in FindObjectsByType<Light>())
                if (l.type == LightType.Directional) { sun = l; break; }
            if (sun == null) sun = new GameObject("Sun").AddComponent<Light>();
            sun.type = LightType.Directional;
            // high sun from the upper left of the screen: soft shadows fall to the lower right (visible, grounding),
            // the camera-facing sides get grazing light instead of being fully in shadow
            sun.transform.rotation = Quaternion.Euler(56f, 118f, 0f);
            var z0 = Content.Zones[0];
            sun.color = z0.sun;
            sun.intensity = z0.sunIntensity;
            sun.shadows = LightShadows.Soft;
            sun.shadowStrength = 1f;      // shadow darkness is art-directed per material (_ShadowStrength)
            sun.shadowBias = 0.05f;
            sun.shadowNormalBias = 0.4f;
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.62f, 0.6f, 0.66f);
            // light distant haze (the camera sits ~70 m from the car; the top of the screen is ~110 m away)
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogStartDistance = 88f;
            RenderSettings.fogEndDistance = 260f;
            RenderSettings.fogColor = z0.sky;
            RenderSettings.skybox = null;

            if (GraphicsSettings.currentRenderPipeline is UniversalRenderPipelineAsset urp)
            {
                urp.shadowDistance = 115f;
                urp.shadowCascadeCount = 1;
                urp.mainLightShadowmapResolution = 2048;
                urp.renderScale = 1f;
                urp.msaaSampleCount = 4;
            }

            Mats.ApplyZone(z0, z0, 1f);
            zoneFrom = zoneTo = 0;

            // clean grade: neutral tonemapping (soft highlight roll-off), restrained bloom for flashes only,
            // no film grain, no split toning, no heavy vignette
            try
            {
                var vgo = new GameObject("PostFx");
                var vol = vgo.AddComponent<Volume>();
                vol.isGlobal = true;
                vol.priority = 10;
                var profile = ScriptableObject.CreateInstance<VolumeProfile>();
                var tm = profile.Add<Tonemapping>(true);
                tm.mode.Override(TonemappingMode.Neutral);
                var ca = profile.Add<ColorAdjustments>(true);
                ca.saturation.Override(8f);
                ca.contrast.Override(6f);
                ca.postExposure.Override(0.18f);
                var bloom = profile.Add<Bloom>(true);
                bloom.threshold.Override(1.15f);
                bloom.intensity.Override(0.2f);
                bloom.scatter.Override(0.5f);
                vol.sharedProfile = profile;
            }
            catch (Exception e) { Debug.LogWarning("RoadGame: post fx setup failed: " + e.Message); }
        }

        /// <summary>Zone palette blend (shadow tint, fill, reflections, haze, sun) while crossing a border.</summary>
        void ApplyZoneLook(float t)
        {
            var a = Content.Zones[zoneFrom]; var b = Content.Zones[zoneTo];
            Mats.ApplyZone(a, b, t);
            var sky = Color.Lerp(a.sky, b.sky, t);
            RenderSettings.fogColor = sky;
            cam.backgroundColor = sky;
            if (sun != null)
            {
                sun.color = Color.Lerp(a.sun, b.sun, t);
                sun.intensity = Mathf.Lerp(a.sunIntensity, b.sunIntensity, t);
            }
        }

        // ------------------------------------------------------------------ input
        /// <summary>
        /// The raw stick for the driver: the direction to travel in world XZ (stick X = world X, stick Y = world Z) and
        /// a length 0..1. One source at a time, by priority: paused (nothing), a test script, the autopilot, then the
        /// player (touch joystick, else keys). The player's stick is a screen direction, turned by the camera's yaw so
        /// "up on the screen" is always "away from the camera". The driver applies the dead zone and the curve.
        /// </summary>
        public Vector2 MoveInput
        {
            get
            {
                if (paused) return Vector2.zero;
                if (ScriptedInput != null) return ScriptedInput(playTimer);
                if (DevTravel.InputHeld) return Vector2.zero;      // a DEV move: no stick carried over from the menu
                if (Autopilot) return autoInput;
                var v = hud != null && hud.joystick != null ? hud.joystick.Value : Vector2.zero;
                var kb = Keyboard.current;
                if (kb != null)
                {
                    var k = Vector2.zero;
                    if (kb.wKey.isPressed || kb.upArrowKey.isPressed) k.y += 1;
                    if (kb.sKey.isPressed || kb.downArrowKey.isPressed) k.y -= 1;
                    if (kb.dKey.isPressed || kb.rightArrowKey.isPressed) k.x += 1;
                    if (kb.aKey.isPressed || kb.leftArrowKey.isPressed) k.x -= 1;
                    if (k.sqrMagnitude > 0) { v = k.normalized; OnFirstInput(); }
                }
                return ScreenToWorld(v);
            }
        }

        /// <summary>Screen stick -> world XZ stick: rotated by the camera's yaw (the follow camera keeps yaw 0 today).</summary>
        Vector2 ScreenToWorld(Vector2 s)
        {
            if (s.sqrMagnitude < 1e-8f || cam == null) return s;
            float yaw = cam.transform.eulerAngles.y;
            if (Mathf.Abs(Mathf.DeltaAngle(0f, yaw)) < 0.01f) return s;
            var w = Quaternion.Euler(0f, yaw, 0f) * new Vector3(s.x, 0f, s.y);
            return new Vector2(w.x, w.z);
        }

        public void OnFirstInput()
        {
            if (progress.d.tutorialDone) return;
            progress.d.tutorialDone = true;
            hud.HideHint();
        }

        // ------------------------------------------------------------------ main loop
        void Update()
        {
            if (hitStopUntil > 0f && Time.unscaledTime >= hitStopUntil) { hitStopUntil = -1f; RefreshTimeScale(); }
            if (!ready) return;
            if (progress == null)
            {
                // scripts were recompiled while playing: runtime state is gone, rebuild the session once
                if (Time.realtimeSinceStartup - lastRecover > 5f)
                {
                    lastRecover = Time.realtimeSinceStartup;
                    I = null;
                    SceneManager.LoadScene(SceneManager.GetActiveScene().name);
                }
                return;
            }
            float dt = Time.deltaTime;
            playTimer += dt;
            SessionTime = playTimer;
            progress.d.playTime += dt;
            if (Autopilot) UpdateAutopilot(dt);
            if (!player.Alive) RespawnIn -= dt;
            if (focusTarget != null && (!focusTarget.Targetable || (focusTarget.Pos - player.Pos).magnitude > 12f)) focusTarget = null;
            UpdateZone(false);
            if (moodT < 1f)
            {
                moodT = Mathf.Min(1f, moodT + dt / 1.5f);
                ApplyZoneLook(Mathf.SmoothStep(0f, 1f, moodT));
            }
            saveTimer -= Time.unscaledDeltaTime;
            if (saveTimer <= 0f) SaveNow();

            var kbBack = Keyboard.current;
            if (kbBack != null && kbBack.escapeKey.wasPressedThisFrame)
            {
                if (hud.devPanel != null && hud.devPanel.IsOpen) hud.devPanel.Close();
                else if (hud.panels.IsOpen) hud.panels.Close();
            }
#if UNITY_EDITOR || DEBUG
            var kb = Keyboard.current;
            if (kb != null && kb.leftShiftKey.isPressed && kb.digit1Key.wasPressedThisFrame) { progress.Apply(Reward.Dmg(DamageType.Gun, progress.Damage(DamageType.Gun))); }
            if (kb != null && kb.leftShiftKey.isPressed && kb.digit2Key.wasPressedThisFrame) { progress.Apply(Reward.HP(progress.MaxHP)); }
            if (kb != null && kb.leftShiftKey.isPressed && kb.digit3Key.wasPressedThisFrame) { progress.d.gems += 1000; }
#endif
        }

        void UpdateZone(bool force)
        {
            int z = Content.ZoneIndexAt(player.Pos.z);
            if (z == currentZone && !force) return;
            currentZone = z;
            var zd = Content.Zones[z];
            // a new game opens in the canyon outside the map: the zone's banner waits for the landing (Intro)
            if (!DevTravel.IntroRunning(progress.d)) hud.ShowBanner(zd.name, zd.subtitle);
            zoneFrom = force ? z : zoneTo;
            zoneTo = z;
            moodT = force ? 1f : 0f;
            if (force) ApplyZoneLook(1f);
        }

        /// <summary>DEV «Локации»: the zone look, banner and mood follow the car's new zone at once.</summary>
        public void SnapZoneLook()
        {
            currentZone = -1;
            UpdateZone(true);
        }

        public void SaveNow()
        {
            saveTimer = 5f;
            // never a position in a zone the save has not unlocked (a DEV test visit): the last allowed checkpoint stays
            if (player != null && !player.Airborne && progress.d.introPending == false && !DevTravel.InTestZone(this))
            {
                progress.d.px = player.Pos.x;
                progress.d.pz = player.Pos.z;
                progress.d.py = player.GroundY;
                progress.d.heading = player.Heading;
            }
            SaveSystem.Save(progress.d);
        }

        /// <summary>
        /// A saved spot is used only if it is still a free place on a floor at the saved level (structures added in an
        /// update may stand there now; an old save has no height and means the surface).
        /// </summary>
        bool SpawnSpotFree(Vector3 p)
        {
            var g = Ground.Sample(p.x, p.z, p.y + 0.6f);
            if (!g.valid || Mathf.Abs(g.h - p.y) > 1.2f || (g.piece != null && g.piece.launch)) return false;
            // a save from before the hills and the mesa were there: not inside one of them
            if (Ground.CoveredAbove(p.x, p.z, g.h, 1.2f)) return false;
            var center = new Vector3(p.x, g.h + 0.75f, p.z);
            return !Physics.CheckBox(center, new Vector3(1.3f, 0.45f, 2.6f), Quaternion.Euler(0, progress.d.heading, 0), ~0, QueryTriggerInteraction.Ignore);
        }

        void OnApplicationPause(bool pause) { if (pause && ready && progress != null) SaveNow(); }
        void OnApplicationQuit() { if (ready && progress != null) SaveNow(); }

        // ------------------------------------------------------------------ gameplay events
        public void OnTargetHit(Target t, double dmg, bool crit)
        {
            bool boosted = false;
            if (BoostWeapon >= 0 && SessionTime < BoostUntil)
            {
                // a hit of the weapon that just went up a level (its per-hit damage, or its crit)
                double hit = progress.WeaponHitDamage(BoostWeapon);
                if (Math.Abs(dmg - hit) <= hit * 0.04 || Math.Abs(dmg - hit * Balance.CritMul) <= hit * 0.06)
                {
                    boosted = true;
                    // seen a few times: the widget moves on to the boss a little later
                    if (++boostHits >= 6 && Goals.SeeUpgradeUntil > SessionTime + 3f) Goals.SeeUpgradeUntil = SessionTime + 3f;
                }
            }
            overlay.DamageNumber(t.Pos + Vector3.up * Mathf.Min(2.2f, t.BarHeight), dmg, crit, boosted);
            if (crit) cameraRig.Shake(0.12f);
        }

        public void OnTargetKilled(Target t)
        {
            progress.d.totalKills++;
            var c = t.zone.cliff;
            if (t.spec.kind == TargetKind.Foot) c = new Color(0.85f, 0.8f, 0.75f);
            float size = Mathf.Clamp(t.Radius, 0.6f, 3f);
            fx.Debris(t.Pos, c, size, Mathf.RoundToInt(6 + size * 4));
            fx.Puff(t.Pos, size);
            if (t.spec.kind == TargetKind.Vehicle || t.IsBoss || t.spec.model == ModelId.CarWreck || t.spec.model == ModelId.Barrels || t.spec.model == ModelId.ToxicBarrels || t.spec.model == ModelId.OilTank)
            {
                fx.Explosion(t.Pos, t.IsBoss ? 2.5f : 1.1f);
                sfx.Play(t.IsBoss || t.spec.model == ModelId.OilTank ? Sfx.Kind.ExplodeBig : Sfx.Kind.Explode, t.Pos, t.IsBoss ? 1f : 0.85f);
                if (t.IsBoss) sfx.Duck(3f, 0.5f);
                cameraRig.Shake(t.IsBoss ? 0.9f : 0.35f);
                // the big ones land with a beat of stillness: the boss, a buggy / car-creature (barrels stay light: they are everywhere)
                if (t.IsBoss) HitStop(0.14f, 0.05f);
                else if (t.spec.kind == TargetKind.Vehicle) HitStop(0.06f, 0.2f);
            }
            else sfx.Break(t);
            player.harpooner.Enqueue(t);
            if (focusTarget == t) focusTarget = null;
            if (t.IsBoss) OnBossKilled(t);
            Vibrate(t.IsBoss);
        }

        void OnBossKilled(Target t)
        {
            int zi = t.zone.index;
            progress.d.bossKills[zi]++;
            bool first = progress.d.bossKills[zi] == 1;
            hud.ShowBanner("BOSS DEFEATED!", t.spec.name);
            if (first)
            {
                var z = Content.Zones[zi];
                if (z.unlockWeapon >= 0) progress.UnlockWeapon(z.unlockWeapon);
                if (z.unlockArmor >= 0 && progress.d.armorLevel[z.unlockArmor] <= 0) progress.AddArmorCopies(z.unlockArmor, 1);
                if (zi + 1 == Content.ZoneCount) hud.ShowPopup(Icon.Star, "WASTELAND CONQUERED!", "Keep growing. There is no cap.");
            }
            if (zi + 1 < Content.ZoneCount) progress.UnlockZone(zi + 1);
            SaveNow();
        }

        public void OnTargetEaten(Target t)
        {
            var pos = player.Pos;
            if (t.IsBoss)
            {
                var z = Content.Zones[t.zone.index];
                foreach (var r in z.bossRewards) { progress.Apply(r); overlay.RewardPop(pos, r); }
                var gem = Reward.Gem(z.bossGems);
                progress.Apply(gem);
                overlay.RewardPop(pos + Vector3.up, gem);
            }
            else
            {
                // small gains add up into one line over the car instead of a label per wreck
                var r = t.spawn.RewardNow;
                progress.Apply(r);
                overlay.QueueGain(r);
            }
            fx.AbsorbPop(pos, Tex.RewardColor(t.spawn.RewardNow));
            player.AbsorbJolt();
            sfx.Absorb(pos, 0.9f);
        }

        public void OnWeaponLevelUp(int id)
        {
            var w = Content.Weapons[id];
            int lvl = progress.d.weaponLevel[id];
            hud.ShowPopup(Tex.DamageIcon(w.type), "LEVEL UP!", w.name + " Lv " + lvl + " · урон " +
                          Fmt.Num(progress.WeaponHitDamageAt(id, lvl - 1)) + " → " + Fmt.Num(progress.WeaponHitDamage(id)));
            BoostWeapon = id; BoostUntil = SessionTime + 15f; boostHits = 0;
            sfx.Play(Sfx.Kind.LevelUp, Vector3.zero, 0.9f);
            sfx.Duck(2f, 0.6f);
            hud.PulseWeapon(id);
        }

        /// <summary>A weapon level bought in the garage: the goal widget says where to see it, the numbers turn green.</summary>
        public void OnUpgradeBought(int id, double from, double to)
        {
            Goals.SeeUpgradeWeapon = id; Goals.SeeUpgradeFrom = from; Goals.SeeUpgradeTo = to;
            Goals.SeeUpgradeUntil = SessionTime + 25f;
            BoostWeapon = id; BoostUntil = SessionTime + 25f; boostHits = 0;
            Debug.Log($"RoadGame UPGRADE bought weapon={id} lvl={progress.d.weaponLevel[id]} hit {from:0.##} -> {to:0.##} gems left={progress.d.gems} t={SessionTime:0.0}");
        }

        /// <summary>
        /// Landing in the Dust Flats after the intro jump: 50 gems, exactly the first weapon level, so the first
        /// upgrade is a conscious choice made right away (once per game).
        /// </summary>
        public void GiveLandingReward()
        {
            var d = progress.d;
            if (d.landingRewardGiven) return;
            d.landingRewardGiven = true;
            var gem = Reward.Gem(Balance.LandingGems);
            progress.Apply(gem);
            overlay.RewardPop(player.Pos + Vector3.up, gem);
            fx.AbsorbPop(player.Pos, Tex.RewardColor(gem));
            hud.ShowPopup(Icon.GemPile, "НАГРАДА ЗА ПРЫЖОК", "+" + Balance.LandingGems + " кристаллов: хватит на первое улучшение");
            sfx.Play(Sfx.Kind.Chest, Vector3.zero, 0.8f);
            SaveNow();
        }

        /// <summary>
        /// A melee weapon landed (WeaponArm.Impact): `hits` things took damage. The first one of a new weapon that shows
        /// what it does (the hammer: two or more at once) gets a short demo: a beat of slow motion, a ring the size of
        /// the area and "УДАР ПО ПЛОЩАДИ ×N" over the spot; the "try it" goal is done.
        /// </summary>
        public void OnWeaponImpact(int id, int hits, Vector3 center)
        {
            var d = progress.d;
            if (d.tryWeapon != id) return;
            var w = Content.Weapons[id];
            bool area = w.aoe > 0f;
            if (hits < (area ? 2 : 1)) return;
            d.tryWeapon = -1;
            LastDemoAt = SessionTime; LastDemoHits = hits;
            // the ring shows the area, the line says what happened (no popup over it: one message, where it happened)
            fx.Ring(center + Vector3.up * 0.15f, w.aoe, new Color(1f, 0.8f, 0.3f), 0.9f);
            overlay.WorldText(center + Vector3.up * 4.2f, area ? "УДАР ПО ПЛОЩАДИ ×" + hits : w.name + "!", new Color(1f, 0.85f, 0.3f), 54);
            hud.PulseWeapon(id);
            StartCoroutine(DemoSlowMo());
            Debug.Log($"RoadGame DEMO weapon={id} hits={hits} t={SessionTime:0.0}");
            SaveNow();
        }

        System.Collections.IEnumerator DemoSlowMo()
        {
            if (paused) yield break;
            demoSlowMoUntil = Mathf.Max(demoSlowMoUntil, Time.unscaledTime + 0.7f);
            RefreshTimeScale();
            while (Time.unscaledTime < demoSlowMoUntil)
            {
                yield return null;
            }
            RefreshTimeScale();
        }

        public void OnPlayerHurt(double dmg, Vector3 from)
        {
            overlay.PlayerDamage(player.Pos + Vector3.up * 1.5f, dmg);
            // the share of the car's HP the blow took decides how hard it reads: a bullet ticks, a club or a boss slam lands
            float share = (float)(dmg / Math.Max(1.0, progress.MaxHP));
            float heavy = Mathf.Clamp01((share - 0.02f) / 0.1f);
            sfx.Play(Sfx.Kind.Hurt, player.Pos, 0.5f + 0.35f * heavy);
            cameraRig.Shake(0.15f + 0.35f * heavy);
            if (heavy > 0.5f) HitStop(0.05f, 0.25f);
        }

        public void OnPlayerDied()
        {
            fx.Explosion(player.Pos, 1.6f);
            sfx.Play(Sfx.Kind.ExplodeBig, player.Pos, 1f);
            sfx.Play(Sfx.Kind.Glass, player.Pos, 0.6f);
            sfx.Duck(2.5f, 0.5f);
            cameraRig.Shake(0.8f);
            player.harpooner.ClearAll();
            player.turret.ClearAll();
            RespawnIn = 2.6f;
            focusTarget = null;
            Vibrate(true);
        }

        public void OnPlayerRespawned()
        {
            cameraRig.Snap();
            fx.Puff(player.Pos, 2f);
            sfx.Play(Sfx.Kind.Ignition, Vector3.zero, 0.8f);
            world.Tick();
            SaveNow();
        }

        void Vibrate(bool strong)
        {
#if UNITY_IOS || UNITY_ANDROID
            if (strong && progress.d.vibrationOn) Handheld.Vibrate();
#endif
        }

        // ------------------------------------------------------------------ boss bar helper
        public Enemy EngagedBoss
        {
            get
            {
                var list = world.activeTargets;
                for (int i = 0; i < list.Count; i++)
                {
                    var t = list[i];
                    if (t == null || !t.IsBoss || !t.Targetable) continue;
                    if (!Ground.SameLevel(t.Pos, player.Pos)) continue;   // the Mammoth under the ground stays hidden from the surface
                    var off = t.Pos - player.Pos; off.y = 0;
                    if (off.magnitude < 34f || ((Enemy)t).Engaged) return (Enemy)t;
                }
                return null;
            }
        }

        // ------------------------------------------------------------------ bonus offer (reference: rewarded bubble)
        public bool BonusReady => player != null && Progress.NowMs >= progress.d.nextBonusAt;
        public bool BonusIsHp => progress.d.bonusKind == 0;
        public DamageType BonusDamageType
        {
            get
            {
                int best = 0;
                for (int i = 1; i < 4; i++) if (progress.d.dmg[i] > progress.d.dmg[best]) best = i;
                return (DamageType)best;
            }
        }
        /// <summary>One farm minute of the furthest unlocked zone (flat: claiming it never compounds).</summary>
        public double BonusValue => BonusIsHp ? Balance.BonusHP(progress.d.unlockedZone) : Balance.BonusDamage(progress.d.unlockedZone);

        public void ClaimBonus()
        {
            if (!BonusReady) return;
            // Hook point for a rewarded video ad SDK: grant the reward in the ad's completion callback.
            var r = BonusIsHp ? Reward.HP(BonusValue) : Reward.Dmg(BonusDamageType, BonusValue);
            progress.Apply(r);
            overlay.RewardPop(player.Pos, r);
            fx.AbsorbPop(player.Pos, Tex.RewardColor(r));
            sfx.Play(Sfx.Kind.LevelUp, Vector3.zero, 0.8f);
            progress.d.bonusKind = 1 - progress.d.bonusKind;
            progress.d.nextBonusAt = Progress.NowMs + (long)(Balance.BonusCooldown * 1000);
            SaveNow();
        }

        /// <summary>
        /// Settings > "Reset progress": the game starts over. A new save (starting car and weapon, no currency, upgrades,
        /// unlocks, bosses, stashes or rewards, tutorial and intro run ahead) that keeps the player's settings is
        /// written at once, so the old progress cannot come back after a restart; then this session stops saving and
        /// is rebuilt from scratch (scene reload: world, car, enemies, timers, HUD), opening with the intro run.
        /// </summary>
        public void ResetProgress()
        {
            DevTravel.ResetForPlay();
            var fresh = SaveSystem.NewGame(progress.d);
            SaveSystem.Save(fresh);
            progress = new Progress(fresh);   // whatever still runs this frame can only see / save the new game
            ready = false;                    // no more autosaves, quit / pause saves or updates from this session
            focusTarget = null;
            _paused = false;
            demoSlowMoUntil = -1f;
            hitStopUntil = -1f;
            RefreshTimeScale();
            Debug.Log("RoadGame: progress reset (settings kept: sound=" + fresh.soundOn + " music=" + fresh.musicOn + " vibration=" + fresh.vibrationOn + ")");
            Projectile.ResetPool();
            Turret.ResetStatics();
            Harpooner.ResetStatics();
            Goals.ResetStatics();
            NavGrid.ResetStatics();
            LastDemoAt = -1f; LastDemoHits = 0;
            I = null;
            SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex >= 0 ? SceneManager.GetActiveScene().buildIndex : 0);
        }

        void OnDestroy()
        {
            if (I == this) I = null;
        }

        // ------------------------------------------------------------------ autopilot (automated play for capture/testing)
        Target autoTarget;
        readonly System.Collections.Generic.Dictionary<Target, float> autoBlacklist = new System.Collections.Generic.Dictionary<Target, float>();
        Vector3 autoLastPos;
        float autoStuckTimer, autoDetour, autoDetourSign = 1f;

        void UpdateAutopilot(float dt)
        {
            autoRetarget -= dt;
            var d = progress.d;
            // stuck detection: no progress while trying to move -> detour + blacklist the target for a while
            autoStuckTimer += dt;
            if (autoStuckTimer > 1.2f)
            {
                bool wantsMove = autoInput.sqrMagnitude > 0.01f;
                if (wantsMove && (player.Pos - autoLastPos).magnitude < 1.2f)
                {
                    autoDetour = 1.4f;
                    autoDetourSign = UnityEngine.Random.value > 0.5f ? 1f : -1f;
                    if (autoTarget != null) autoBlacklist[autoTarget] = Time.time + 12f;
                    autoRetarget = 0f;
                }
                autoLastPos = player.Pos;
                autoStuckTimer = 0f;
            }
            if (autoRetarget <= 0f)
            {
                autoRetarget = 0.5f;
                autoTarget = null;
                if (d.hp < d.maxHp * 0.35f && !(AutopilotStayInFight && AutopilotBoss && EngagedBoss != null))
                {
                    var st = world.NearestStation(player.Pos, DevTravel.AccessZone(d));
                    autoGoal = st != null ? st.pos : world.startPos;
                }
                else if (d.hp < d.maxHp * 0.9f && player.OnRepairPad) autoGoal = player.Pos;
                else
                {
                    Target best = null; float bd = float.MaxValue;
                    int pzone = Content.ZoneIndexAt(player.Pos.z);
                    foreach (var t in world.activeTargets)
                    {
                        if (t == null || !t.Targetable || Content.ZoneIndexAt(t.Pos.z) != pzone) continue;
                        if (autoBlacklist.TryGetValue(t, out var until) && until > Time.time) continue;
                        if (AutopilotBoss && t.IsBoss) { best = t; break; }
                        if (AutopilotEnemiesOnly && !t.IsEnemy) continue;
                        if (AutopilotAvoidBoss && t.IsBoss) continue;
                        if (t.IsBoss && d.hp < d.maxHp * 0.8f) continue;
                        float dist = (t.Pos - player.Pos).magnitude;
                        if (t.IsBoss) dist += 25f;
                        if (dist < bd) { bd = dist; best = t; }
                    }
                    autoTarget = best;
                    autoGoal = best != null ? best.Pos : player.Pos + new Vector3(UnityEngine.Random.Range(-20f, 20f), 0, 25f);
                }
            }
            // a target under the ground (the Mammoth's hangar): follow the route down the entrance ramp first
            if (autoTarget != null && autoTarget.Pos.y < -1.5f && !player.Underground)
            {
                var route = Structures.WorksRoute;
                int best = 0; float bd2 = float.MaxValue;
                for (int i = 0; i < route.Length; i++)
                {
                    var dd = route[i] - player.Pos; dd.y = 0;
                    if (dd.sqrMagnitude < bd2) { bd2 = dd.sqrMagnitude; best = i; }
                }
                autoGoal = route[Mathf.Min(route.Length - 1, best + 1)];
            }
            var off = autoGoal - player.Pos; off.y = 0;
            float m = off.magnitude;
            var dir = m > 0.01f ? new Vector2(off.x, off.z) / m : Vector2.zero;
            if (autoDetour > 0f)
            {
                autoDetour -= dt;
                dir = new Vector2(-dir.y, dir.x) * autoDetourSign * 0.8f - dir * 0.6f;
                autoInput = dir.normalized;
                return;
            }
            float stopAt = autoTarget != null ? autoTarget.Radius + 2.4f : 3.2f;
            // a goal behind the car: a three-point turn when stopped, a forward U-turn when rolling - like a player
            // (the stuck detour above backs off on purpose)
            autoInput = m > stopAt ? CarDriver.TowardTarget(dir * Mathf.Clamp01(m / 6f + 0.3f), player.Heading, player.ForwardSpeed, player.GearDirection, m) : Vector2.zero;
        }
    }
}
