using UnityEngine;

namespace RoadGame
{
    /// <summary>
    /// The opening run of a new game (about 10-15 s): the car starts on a straight canyon road pointing north, two weak
    /// scout buggies come at it and the starting cannon wrecks them on the move, chevrons and a floating arrow lead to a
    /// launch ramp, the car jumps the barricade into the Dust Flats and the normal game takes over on touch-down.
    /// Driving is free the whole time; hints are one line each. Old saves never see it (SaveData.introPending).
    /// </summary>
    public class Intro : MonoBehaviour
    {
        public static Intro Active { get; private set; }

        public enum Phase { Fight, ToRamp, Air, Done }
        public Phase phase { get; private set; } = Phase.Fight;
        public float Elapsed { get; private set; }
        public float JumpAt { get; private set; } = -1f;       // session time of the take-off (tests)
        public float LandAt { get; private set; } = -1f;
        public int ScoutsKilled { get; private set; }

        SpawnPoint scoutA, scoutB;
        bool rampHintShown;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { Active = null; }

        public static Intro Begin(Game g)
        {
            var go = new GameObject("Intro");
            var intro = go.AddComponent<Intro>();
            Active = intro;
            // the scouts' HP follows the machine gun's real hit damage: exactly two hits each
            var spec = Content.IntroScout(g.progress.WeaponHitDamage(0));
            intro.scoutA = g.world.AddIntroSpawn(9600, spec, Structures.IntroScoutA, 180f);
            intro.scoutB = g.world.AddIntroSpawn(9601, spec, Structures.IntroScoutB, 168f);
            // a replay after a wipe: the one-time scouts are back for a new game
            if (intro.scoutA.save != null) intro.scoutA.save.respawnAt = 0;
            if (intro.scoutB.save != null) intro.scoutB.save.respawnAt = 0;
            if (Structures.IntroGuide != null) Structures.IntroGuide.SetActive(true);
            g.player.Landed += intro.OnLanded;
            g.world.Tick();
            intro.FenceScouts();
            Debug.Log("RoadGame Intro: started, scout hp=" + spec.hp.ToString("0.0") + " hit=" + g.progress.WeaponHitDamage(0).ToString("0.0"));
            return intro;
        }

        void Update()
        {
            var g = Game.I;
            if (g == null || g.player == null || !g.Ready) return;
            Elapsed += Time.deltaTime;
            var p = g.player;
            FenceScouts();
            int dead = (scoutA != null && scoutA.Kills > 0 ? 1 : 0) + (scoutB != null && scoutB.Kills > 0 ? 1 : 0);
            if (dead != ScoutsKilled)
            {
                ScoutsKilled = dead;
                Debug.Log($"RoadGame Intro: scout down ({dead}/2) t={Elapsed:0.0} car z={p.Pos.z:0.0}");
            }
            if (phase == Phase.Fight && (dead >= 2 || p.Pos.z > Structures.IntroScoutLimitZ))
            {
                phase = Phase.ToRamp;
            }
            if (phase == Phase.ToRamp && !rampHintShown && (dead >= 2 || p.Pos.z > Structures.IntroScoutLimitZ - 8f))
            {
                rampHintShown = true;
                g.hud.ShowHint("HIT THE RAMP!", "Full speed - jump into the Dust Flats");
            }
            if (phase != Phase.Air && phase != Phase.Done && p.Airborne && p.Pos.z > Structures.IntroRampStart.z)
            {
                phase = Phase.Air;
                JumpAt = g.SessionTime;
                g.hud.HideHint();
                Debug.Log($"RoadGame Intro: take-off t={Elapsed:0.0} speed={p.Speed:0.0} z={p.Pos.z:0.0}");
            }
            // safety net: the car got into the zone any other way (respawn, test teleport)
            if (phase != Phase.Done && !p.Airborne && p.Pos.z > Structures.IntroZoneZ) Finish();
        }

        /// <summary>The scouts fight in the wide straight only: they never follow the car into the run-up to the ramp.</summary>
        void FenceScouts()
        {
            foreach (var sp in new[] { scoutA, scoutB })
                if (sp != null && sp.target is Enemy e) e.maxZ = Structures.IntroScoutLimitZ;
        }

        void OnLanded(float impact)
        {
            var p = Game.I.player;
            if (phase == Phase.Air && p.Pos.z > Structures.IntroZoneZ)
            {
                LandAt = Game.I.SessionTime;
                Debug.Log($"RoadGame Intro: landed t={Elapsed:0.0} impact={impact:0.0} z={p.Pos.z:0.0} air={p.MaxAirHeight:0.0}m");
                Finish();
            }
        }

        void Finish()
        {
            if (phase == Phase.Done) return;
            phase = Phase.Done;
            var g = Game.I;
            g.progress.d.introPending = false;
            g.progress.d.tutorialDone = true;
            g.hud.HideHint();
            g.hud.ShowBanner(Content.Zones[0].name, Content.Zones[0].subtitle);
            g.GiveLandingReward();
            if (Structures.IntroGuide != null) Structures.IntroGuide.SetActive(false);
            // a scout left behind in the canyon simply drives off: it never comes back
            foreach (var sp in new[] { scoutA, scoutB })
            {
                if (sp == null || sp.Kills > 0) continue;
                sp.save = g.progress.GetOrCreateSpawn(sp.id);
                sp.save.respawnAt = Progress.NowMs + 1000L * 3600 * 24 * 365 * 50;
                if (sp.target != null && sp.target.gameObject.activeSelf)
                {
                    sp.target.gameObject.SetActive(false);
                    g.world.OnTargetGone(sp.target);
                }
            }
            g.SaveNow();
            Debug.Log("RoadGame Intro: done in " + Elapsed.ToString("0.0") + " s");
            Active = null;
            g.player.Landed -= OnLanded;
            Destroy(gameObject, 0.1f);
        }

        /// <summary>
        /// DEV «Локации» during the intro: the intro steps aside without finishing - no landing reward, no tutorial
        /// completion, the save keeps the intro ahead (it plays again on the next start). The scouts stay fenced in
        /// the canyon.
        /// </summary>
        public void Suspend()
        {
            if (phase == Phase.Done) return;
            phase = Phase.Done;
            var g = Game.I;
            if (g != null)
            {
                if (g.hud != null) g.hud.HideHint();
                if (g.player != null) g.player.Landed -= OnLanded;
            }
            if (Structures.IntroGuide != null) Structures.IntroGuide.SetActive(false);
            Debug.Log("RoadGame Intro: set aside by a DEV move after " + Elapsed.ToString("0.0") + " s (intro still ahead in the save)");
            Active = null;
            Destroy(gameObject);
        }

        void OnDestroy()
        {
            if (Active == this) Active = null;
        }
    }
}
