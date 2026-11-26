using System;
using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    [Serializable]
    public class SpawnSave
    {
        public int id;
        public int kills;
        public long respawnAt;   // unix ms; 0 = alive
        public float dur;        // duration of the current respawn timer (for the ring UI)
    }

    [Serializable]
    public class SaveData
    {
        public int version = 1;
        public double maxHp = Balance.StartHP;
        public double hp = Balance.StartHP;
        public double regen = Balance.StartRegen;
        public double[] dmg = { Balance.StartDamage, 0, 0, 0 };
        public int[] weaponLevel = { 1, 0, 0, 0 };
        public int[] weaponCopies = { 0, 0, 0, 0 };
        public int[] armorLevel = { 0, 0 };
        public int[] armorCopies = { 0, 0 };
        public int unlockedZone = 0;
        public int[] bossKills = { 0, 0, 0, 0 };
        public long gems = 0;
        public float px = 0, pz = -78f, heading = 0;
        public List<SpawnSave> spawns = new List<SpawnSave>();
        public List<int> chestsOpened = new List<int>();
        public bool soundOn = true;
        public bool musicOn = true;
        public bool vibrationOn = true;
        public long nextBonusAt = 0;
        public int bonusKind = 0;
        public long freeGemsAt = 0;
        public long totalKills = 0;
        public double playTime = 0;
        public bool tutorialDone = false;
        // v6: a brand-new game starts with the intro canyon (old saves load without the field -> false, no intro)
        public bool introPending = false;
        public float py = 0;              // floor height of the saved position (tunnels, the hangar)
        // v10: the HUD opens step by step and the next goal is guided. Saves from before have uiVersion 0 and keep
        // the full HUD they knew (Sanitize turns everything on for them).
        public int uiVersion = 0;
        public bool seenGarage, seenShop, seenArmor;
        public bool landingRewardGiven;
        public int upgradesBought;        // weapon levels bought with gems
        public int tryWeapon = -1;        // a weapon just unlocked: the goal "try it on a group" until its area hit lands
    }

    public static class SaveSystem
    {
        public static string KeySuffix = "";
        static string Key => "roadgame_save_v1" + KeySuffix;

        public static SaveData Load()
        {
            try
            {
                if (PlayerPrefs.HasKey(Key))
                {
                    var json = PlayerPrefs.GetString(Key);
                    var d = JsonUtility.FromJson<SaveData>(json);
                    if (d != null) { Sanitize(d); return d; }
                }
            }
            catch (Exception e) { Debug.LogWarning("RoadGame: failed to load save: " + e.Message); }
            return NewGame(null);
        }

        /// <summary>
        /// The save of a brand-new game: starting stats, car and weapon, nothing unlocked, collected or defeated, the
        /// tutorial hint and the short intro run (with the first jump) ahead. The player's settings (sound, music,
        /// vibration) are carried over from <paramref name="keepSettingsOf"/> when given.
        /// </summary>
        public static SaveData NewGame(SaveData keepSettingsOf)
        {
            var fresh = new SaveData();
            fresh.introPending = true;
            fresh.uiVersion = 1;
            if (keepSettingsOf != null)
            {
                fresh.soundOn = keepSettingsOf.soundOn;
                fresh.musicOn = keepSettingsOf.musicOn;
                fresh.vibrationOn = keepSettingsOf.vibrationOn;
            }
            Sanitize(fresh);
            return fresh;
        }

        /// <summary>The raw saved JSON (null if there is no save) - tests compare it before / after a reset.</summary>
        public static string RawJson() => PlayerPrefs.HasKey(Key) ? PlayerPrefs.GetString(Key) : null;

        public static void Save(SaveData d)
        {
            try
            {
                PlayerPrefs.SetString(Key, JsonUtility.ToJson(d));
                PlayerPrefs.Save();
            }
            catch (Exception e) { Debug.LogWarning("RoadGame: failed to save: " + e.Message); }
        }

        public static void Wipe()
        {
            PlayerPrefs.DeleteKey(Key);
            PlayerPrefs.Save();
        }

        static void Sanitize(SaveData d)
        {
            if (d.dmg == null || d.dmg.Length != 4) d.dmg = new double[] { Balance.StartDamage, 0, 0, 0 };
            if (d.weaponLevel == null || d.weaponLevel.Length != 4) d.weaponLevel = new[] { 1, 0, 0, 0 };
            if (d.weaponCopies == null || d.weaponCopies.Length != 4) d.weaponCopies = new int[4];
            if (d.armorLevel == null || d.armorLevel.Length != 2) d.armorLevel = new int[2];
            if (d.armorCopies == null || d.armorCopies.Length != 2) d.armorCopies = new int[2];
            if (d.bossKills == null || d.bossKills.Length != 4) d.bossKills = new int[4];
            d.unlockedZone = Mathf.Clamp(d.unlockedZone, 0, Content.ZoneCount - 1);
            // A recorded boss victory must never leave its next gate locked after a reload.
            for (int z = 0; z < Content.ZoneCount - 1 && d.bossKills[z] > 0; z++)
                d.unlockedZone = Mathf.Max(d.unlockedZone, z + 1);
            if (d.spawns == null) d.spawns = new List<SpawnSave>();
            if (d.chestsOpened == null) d.chestsOpened = new List<int>();
            if (d.weaponLevel[0] <= 0) d.weaponLevel[0] = 1;
            if (d.maxHp < 1) d.maxHp = Balance.StartHP;
            if (d.hp <= 0 || d.hp > d.maxHp) d.hp = d.maxHp;
            if (d.uiVersion <= 0)
            {
                // a save from before the guided start: the full HUD stays as it was, the guidance starts at the boss
                d.uiVersion = 1;
                d.seenGarage = d.seenShop = d.seenArmor = true;
                d.landingRewardGiven = true;
                if (d.upgradesBought <= 0) d.upgradesBought = 1;
                d.tryWeapon = -1;
            }
        }
    }

    /// <summary>Runtime wrapper around the save data: all permanent progression lives here.</summary>
    public class Progress
    {
        public readonly SaveData d;
        public event Action Changed;
        public event Action<int> WeaponLevelUp;     // weapon id
        public event Action<int> WeaponUnlocked;    // weapon id
        public event Action<int> ArmorLevelUp;      // armor id
        public event Action<int> ZoneUnlocked;      // zone index

        readonly Dictionary<int, SpawnSave> spawnLookup = new Dictionary<int, SpawnSave>();

        public Progress(SaveData data)
        {
            d = data;
            foreach (var s in d.spawns) spawnLookup[s.id] = s;
        }

        public static long NowMs => DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

        public double MaxHP => d.maxHp;
        public double Regen => d.regen;
        public double Damage(DamageType t) => d.dmg[(int)t];
        public int WeaponLevel(int id) => d.weaponLevel[id];
        public bool WeaponOwned(int id) => d.weaponLevel[id] > 0;
        public int ArmorTotal => d.armorLevel[0] + d.armorLevel[1];
        public float DamageTakenMul => 1f - Balance.ArmorReduction(ArmorTotal);

        public double WeaponHitDamage(int id)
        {
            var w = Content.Weapons[id];
            return Damage(w.type) * Math.Round((double)w.dmgMul, 4) * Balance.WeaponLevelMul(d.weaponLevel[id]);
        }

        public double TotalDps()
        {
            double sum = 0;
            for (int i = 0; i < Content.Weapons.Length; i++)
            {
                if (!WeaponOwned(i)) continue;
                var w = Content.Weapons[i];
                sum += WeaponHitDamage(i) / w.interval;
            }
            return sum * (1 + Balance.CritChance * (Balance.CritMul - 1));
        }

        /// <summary>Damage shown in the HUD next to the car (best weapon per-hit damage).</summary>
        public double DisplayDamage()
        {
            double best = 0;
            for (int i = 0; i < Content.Weapons.Length; i++) if (WeaponOwned(i)) best = Math.Max(best, WeaponHitDamage(i));
            return best;
        }

        public void Apply(Reward r)
        {
            switch (r.kind)
            {
                case RewardKind.MaxHP:
                    d.maxHp += r.amount;
                    d.hp += r.amount;
                    break;
                case RewardKind.Regen:
                    d.regen += r.amount;
                    break;
                case RewardKind.Damage:
                    d.dmg[(int)r.dmgType] += r.amount;
                    break;
                case RewardKind.WeaponCopy:
                    AddWeaponCopies(r.itemId, Mathf.Max(1, (int)r.amount));
                    break;
                case RewardKind.ArmorCopy:
                    AddArmorCopies(r.itemId, Mathf.Max(1, (int)r.amount));
                    break;
                case RewardKind.Gems:
                    d.gems += (long)r.amount;
                    break;
            }
            Changed?.Invoke();
        }

        /// <summary>Gems for the next level of a weapon (its missing copies), -1 if it is not owned.</summary>
        public int WeaponLevelCost(int id) => WeaponOwned(id) ? Balance.LevelUpCost(d.weaponLevel[id], d.weaponCopies[id]) : -1;

        /// <summary>Per-hit damage a weapon would have one level up.</summary>
        public double WeaponHitDamageAt(int id, int level)
        {
            var w = Content.Weapons[id];
            return Damage(w.type) * Math.Round((double)w.dmgMul, 4) * Balance.WeaponLevelMul(level);
        }

        /// <summary>The cheapest weapon level the gems pay for now (-1 if none): the garage's red dot.</summary>
        public int AffordableUpgrade()
        {
            int best = -1, bestCost = int.MaxValue;
            for (int i = 0; i < Content.Weapons.Length; i++)
            {
                int c = WeaponLevelCost(i);
                if (c >= 0 && c <= d.gems && c < bestCost) { best = i; bestCost = c; }
            }
            return best;
        }

        /// <summary>Buys the next level of a weapon with gems (its missing copies). Returns false if it cannot be paid.</summary>
        public bool BuyWeaponLevel(int id)
        {
            int cost = WeaponLevelCost(id);
            if (cost < 0 || d.gems < cost) return false;
            d.gems -= cost;
            d.weaponCopies[id] = 0;
            d.weaponLevel[id]++;
            d.upgradesBought++;
            WeaponLevelUp?.Invoke(id);
            Changed?.Invoke();
            return true;
        }

        public void AddWeaponCopies(int id, int n)
        {
            if (d.weaponLevel[id] <= 0) { UnlockWeapon(id); n--; }
            d.weaponCopies[id] += Mathf.Max(0, n);
            while (d.weaponCopies[id] >= Balance.CopiesForLevel(d.weaponLevel[id]))
            {
                d.weaponCopies[id] -= Balance.CopiesForLevel(d.weaponLevel[id]);
                d.weaponLevel[id]++;
                WeaponLevelUp?.Invoke(id);
            }
            Changed?.Invoke();
        }

        public void AddArmorCopies(int id, int n)
        {
            if (d.armorLevel[id] <= 0) { d.armorLevel[id] = 1; n--; ArmorLevelUp?.Invoke(id); }
            d.armorCopies[id] += Mathf.Max(0, n);
            while (d.armorCopies[id] >= Balance.CopiesForLevel(d.armorLevel[id]))
            {
                d.armorCopies[id] -= Balance.CopiesForLevel(d.armorLevel[id]);
                d.armorLevel[id]++;
                ArmorLevelUp?.Invoke(id);
            }
            Changed?.Invoke();
        }

        public void UnlockWeapon(int id)
        {
            if (d.weaponLevel[id] > 0) return;
            d.weaponLevel[id] = 1;
            // a freshly unlocked damage type starts close to the player's best type so it is useful immediately
            var t = (int)Content.Weapons[id].type;
            double best = 0;
            for (int i = 0; i < 4; i++) best = Math.Max(best, d.dmg[i]);
            d.dmg[t] = Math.Max(d.dmg[t], Math.Max(Balance.StartDamage, best * 0.7));
            WeaponUnlocked?.Invoke(id);
            Changed?.Invoke();
        }

        public void UnlockZone(int zone)
        {
            if (zone <= d.unlockedZone) return;
            d.unlockedZone = zone;
            ZoneUnlocked?.Invoke(zone);
            Changed?.Invoke();
        }

        public void NotifyChanged() => Changed?.Invoke();

        // --------------------------------------------------------------- spawn persistence
        public SpawnSave GetSpawn(int id)
        {
            spawnLookup.TryGetValue(id, out var s);
            return s;
        }

        public SpawnSave GetOrCreateSpawn(int id)
        {
            if (!spawnLookup.TryGetValue(id, out var s))
            {
                s = new SpawnSave { id = id };
                spawnLookup[id] = s;
                d.spawns.Add(s);
            }
            return s;
        }
    }
}
