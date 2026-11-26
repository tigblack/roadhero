using UnityEngine;

namespace RoadGame
{
    /// <summary>A spawn location with a persistent kill counter and an absolute (real-time) respawn timer.</summary>
    public class SpawnPoint
    {
        public int id;
        public SpawnSpec spec;
        public ZoneDef zone;
        public Vector3 pos;
        public float yaw;
        public int variant;
        public float scale = 1f;
        public Target target;
        public SpawnSave save;
        public bool pendingRespawnFx;
        /// <summary>Boss rooms: the floor rectangle the boss keeps to (walls of the underground hangar).</summary>
        public ORect? arena;

        public bool IsDead(long now) => save != null && save.respawnAt > now;
        public float Remaining(long now) => save == null ? 0f : Mathf.Max(0f, (save.respawnAt - now) / 1000f);
        public float Progress01(long now) => (save == null || save.dur <= 0f) ? 1f : Mathf.Clamp01(1f - Remaining(now) / save.dur);
        public int Kills => save != null ? save.kills : 0;
        public Reward RewardNow => spec.reward;

        public void OnKilled(Progress progress)
        {
            save = progress.GetOrCreateSpawn(id);
            save.kills++;
            float dur = spec.oneTime ? 1e9f : Balance.RespawnTime(spec.respawn, save.kills);
            save.dur = dur;
            save.respawnAt = Progress.NowMs + (long)(dur * 1000.0);
            pendingRespawnFx = true;
        }
    }

    /// <summary>Base class for anything with HP that the car can destroy and harpoon.</summary>
    public abstract class Target : MonoBehaviour
    {
        public SpawnPoint spawn;
        public SpawnSpec spec;
        public ZoneDef zone;
        public Rig rig;
        public double hp, maxHp;
        public bool dead;
        public bool beingEaten;
        public float lastHitTime = -99f;
        public float hitPunch;
        protected Collider col;
        protected Vector3 baseScale = Vector3.one;
        float spawnAnim = 1f;

        public float Radius => spec.radius * spawn.scale;
        public float BarHeight => spec.height * spawn.scale;
        public Vector3 Pos => transform.position;
        public bool Targetable => !dead && !beingEaten && gameObject.activeInHierarchy;
        public virtual bool IsEnemy => false;
        public bool IsBoss => spec.kind == TargetKind.Boss;

        public virtual void Setup(SpawnPoint sp, Rig r)
        {
            spawn = sp; spec = sp.spec; zone = sp.zone; rig = r;
            baseScale = Vector3.one * sp.scale;
            col = GetComponent<Collider>();
        }

        public virtual void ResetForSpawn(bool animate)
        {
            hp = maxHp = spec.hp;
            dead = false;
            beingEaten = false;
            transform.position = spawn.pos;
            transform.rotation = Quaternion.Euler(0, spawn.yaw, 0);
            transform.localScale = baseScale;
            if (rig != null) rig.SetBurnt(false);
            if (col != null) col.enabled = true;
            spawnAnim = animate ? 0f : 1f;
            if (animate) transform.localScale = baseScale * 0.05f;
            gameObject.SetActive(true);
        }

        public void Hit(double dmg, bool crit, Vector3 source)
        {
            if (dead || beingEaten) return;
            hp -= dmg;
            lastHitTime = Time.time;
            hitPunch = 1f;
            if (rig != null) rig.Flash(0.07f);
            Game.I.OnTargetHit(this, dmg, crit);
            OnHit(source);
            if (hp <= 0) Kill();
        }

        protected virtual void OnHit(Vector3 source) { }

        public virtual void Kill()
        {
            if (dead) return;
            dead = true;
            hp = 0;
            if (col != null) col.enabled = false;
            if (rig != null) rig.SetBurnt(true);
            spawn.OnKilled(Game.I.progress);
            OnKilledVisual();
            Game.I.OnTargetKilled(this);
        }

        protected virtual void OnKilledVisual()
        {
            transform.rotation = transform.rotation * Quaternion.Euler(Random.Range(-12f, 12f), 0, Random.Range(-12f, 12f));
            transform.localScale = baseScale * 0.85f;
        }

        /// <summary>Called by the harpooner once the wreck has been reeled in.</summary>
        public void OnEaten()
        {
            beingEaten = false;
            gameObject.SetActive(false);
            if (World.I != null) World.I.OnTargetGone(this);
        }

        protected virtual void Update()
        {
            if (spawnAnim < 1f)
            {
                spawnAnim = Mathf.Min(1f, spawnAnim + Time.deltaTime * 3.2f);
                float s = BackOut(spawnAnim);
                transform.localScale = baseScale * Mathf.Max(0.05f, s);
            }
            else if (hitPunch > 0f && !dead && !beingEaten)
            {
                hitPunch = Mathf.Max(0f, hitPunch - Time.deltaTime * 7f);
                float k = 1f + Mathf.Sin(hitPunch * Mathf.PI) * 0.09f;
                transform.localScale = new Vector3(baseScale.x * k, baseScale.y / k, baseScale.z * k);
            }
        }

        static float BackOut(float t)
        {
            const float c1 = 1.70158f, c3 = c1 + 1f;
            return 1f + c3 * Mathf.Pow(t - 1f, 3) + c1 * Mathf.Pow(t - 1f, 2);
        }
    }

    /// <summary>Static destructible prop (cactus, crates, shacks, wrecks ...).</summary>
    public class Prop : Target
    {
        protected override void Update()
        {
            base.Update();
        }
    }
}
