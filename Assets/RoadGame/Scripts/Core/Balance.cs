using System;
using System.Globalization;
using UnityEngine;

namespace RoadGame
{
    /// <summary>Tunable balance formulas. Starting numbers mirror the reference (100 HP, 5.5 dmg/hit, crit x1.5).</summary>
    public static class Balance
    {
        public const double StartHP = 100;
        public const double StartRegen = 1.0;      // HP per second
        public const double StartDamage = 5.5;     // per hit, first weapon type
        public const float CritChance = 0.10f;
        public const float CritMul = 1.5f;

        public const float RespawnGrowth = 1.32f;  // each kill of the same spawn makes the next respawn longer
        public const float RespawnCap = 6f * 3600f;

        public const float RepairHealFraction = 0.14f; // of max HP per second on the repair pad
        public const float RegenDelayAfterHit = 0f;

        public const float CarMaxSpeed = 11.5f;
        public const float CarAccel = 30f;
        public const float CarBrake = 38f;
        public const float CarTurnRateLow = 340f;
        public const float CarTurnRateHigh = 230f;

        public const float HarpoonSpeed = 55f;
        public const float HarpoonReelTime = 0.32f;

        public static float RespawnTime(float baseSeconds, int kills)
        {
            int k = Mathf.Clamp(kills - 1, 0, 60);
            return Mathf.Min(RespawnCap, baseSeconds * Mathf.Pow(RespawnGrowth, k));
        }

        /// <summary>Copies needed to go from level to level+1.</summary>
        public static int CopiesForLevel(int level) => 2 * Mathf.Max(1, level);

        /// <summary>Per-hit multiplier of a weapon level (double: 6.5 x 1.3 must show as 8.45, not 8.44).</summary>
        public static double WeaponLevelMul(int level) => level <= 0 ? 0.0 : 1.0 + 0.3 * (level - 1);

        public static float ArmorReduction(int totalLevels) => 1f - 1f / (1f + 0.08f * Mathf.Max(0, totalLevels));

        // ------------------------------------------------------------------ economy: one scale for every boost
        // A "farm minute" is what one minute of ordinary play gives. Measured on the reproducible route (the stock
        // autopilot from a clean save in the Dust Flats, 10 minutes, x1 speed): base damage 5.5 -> 38 (3.25 a minute),
        // max HP 100 -> 241 (14 a minute), about 12 wrecks a minute. Every later zone multiplies HP and rewards by 8,
        // so a farm minute there is 8x bigger, and at the zone's own entry strength it takes the same real time.
        public const double FarmDmgPerMin = 3.0, FarmHpPerMin = 14.0;
        public static double ZoneMul(int zone) => Content.Zones[Mathf.Clamp(zone, 0, Content.ZoneCount - 1)].mul;
        public static double FarmMinuteDmg(int zone) => FarmDmgPerMin * ZoneMul(zone);
        public static double FarmMinuteHp(int zone) => FarmHpPerMin * ZoneMul(zone);

        /// <summary>
        /// Free bonus (the reference's rewarded bubble), damage and max HP in turn: one farm minute of the furthest
        /// unlocked zone. A flat amount instead of a share of the stat it adds to, so claiming it does not compound.
        /// </summary>
        public const float BonusCooldown = 120f;       // seconds between offers (the first one 45 s into a new game)
        public static double BonusDamage(int zone) => Math.Round(FarmMinuteDmg(zone), 1);
        public static double BonusHP(int zone) => Math.Round(FarmMinuteHp(zone));

        /// <summary>One weapon / armor copy bought straight away (a level is its copies: 2 x level of them).</summary>
        public const int GemsPerCopy = 25;
        /// <summary>Direct level up: the copies still missing for the next level, at the copy price (owned copies count).</summary>
        public static int LevelUpCost(int level, int copies) => GemsPerCopy * Math.Max(1, CopiesForLevel(level) - Math.Max(0, copies));
        /// <summary>Crates: random copies of the owned weapons (armor parts), cheaper per copy than choosing one.</summary>
        public const int CrateCopies = 3, CratePrice = 60;              // 20 gems a copy
        public const int BigCrateCopies = 15, BigCratePrice = 250;      // 16.7 gems a copy
        public const int ArmorCrateParts = 2, ArmorCratePrice = 60;     // 30 gems a part
        /// <summary>
        /// Stat packs: five farm minutes of damage / max HP of the furthest unlocked zone for 150 gems (30 a farm minute):
        /// about what the next weapon level is worth over ten minutes of play (a pack pays at once, a level keeps paying).
        /// </summary>
        public const int PackPrice = 150;
        public const double PackFarmMinutes = 5;
        public static double PackDamage(int zone) => Math.Round(FarmMinuteDmg(zone) * PackFarmMinutes, 1);
        public static double PackHP(int zone) => Math.Round(FarmMinuteHp(zone) * PackFarmMinutes);
        public const int FreeGems = 20;
        public const float FreeGemsHours = 4f;
        /// <summary>Reward for the intro's jump into the Dust Flats: exactly the first weapon level (2 copies).</summary>
        public const int LandingGems = 50;

        /// <summary>
        /// Per-hit damage that beats a zone boss in about 90 s with the hood gun (0.62 s, crits on average x1.05):
        /// the "ready" mark of the boss goal. The Mammoth (4000 HP): 26.
        /// </summary>
        public static double BossReadyHit(int zone)
        {
            var b = Content.Zones[Mathf.Clamp(zone, 0, Content.ZoneCount - 1)].boss;
            return Math.Round(b.hp / (90.0 / 0.62 * (1 + CritChance * (CritMul - 1))));
        }

        /// <summary>
        /// Damage a boss deals per second to a car that does not dodge: its regular blows, 16 / 1.7 s = 9.4 on the
        /// Mammoth. Measured with the guided bot (it never dodges): 7.65 a second in two fights, 9.3 in one where its
        /// charges and slams pinned the car to a wall, so the nominal rate is the honest estimate.
        /// </summary>
        public static double BossDps(int zone)
        {
            var b = Content.Zones[Mathf.Clamp(zone, 0, Content.ZoneCount - 1)].boss;
            return b.damage / Math.Max(0.1, b.attackInterval);
        }

        /// <summary>
        /// The other half of "ready": max HP to come out of the whole fight with at least 30 % left, (the boss's damage per
        /// second - regen) x the fight's length / 0.7. The fight lasts boss HP / (the car's damage per second x 0.85): the
        /// guns are on the boss about 85 % of the time (its charges, retargeting). The Mammoth (9.4 a second): with regen
        /// 2.5 about 1050 HP at hit 26, 690 at hit 40, 490 at hit 56. Measured with the guided bot: at hit 26 / 236 HP,
        /// 43 / 392 HP and 51 / 424 HP it had to pull out after 30-45 s; at hit 56-60 / 413 HP it won in 46 s with 191 left.
        /// </summary>
        public static double BossHpNeed(int zone, double dps, double regen, double takenMul)
        {
            var b = Content.Zones[Mathf.Clamp(zone, 0, Content.ZoneCount - 1)].boss;
            double fight = b.hp / Math.Max(1e-6, dps * 0.85);
            return Math.Max(0.0, BossDps(zone) * takenMul - regen) * fight / 0.7;
        }
    }

    public static class Fmt
    {
        static readonly string[] Suffix = { "", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc" };
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        public static string Num(double v)
        {
            if (double.IsNaN(v) || double.IsInfinity(v)) return "0";
            bool neg = v < 0;
            v = Math.Abs(v);
            string s;
            if (v < 10) s = Trunc(v, 2).ToString("0.##", Inv);
            else if (v < 100) s = Trunc(v, 1).ToString("0.#", Inv);
            else if (v < 1000) s = Math.Floor(v).ToString("0", Inv);
            else
            {
                int i = 0;
                while (v >= 1000 && i < Suffix.Length - 1) { v /= 1000; i++; }
                if (v < 10) s = Trunc(v, 2).ToString("0.##", Inv);
                else if (v < 100) s = Trunc(v, 1).ToString("0.#", Inv);
                else s = Math.Floor(v).ToString("0", Inv);
                s += Suffix[i];
            }
            return neg ? "-" + s : s;
        }

        static double Trunc(double v, int digits)
        {
            double p = Math.Pow(10, digits);
            return Math.Floor(v * p + 1e-6) / p;
        }

        public static string Time(double seconds)
        {
            if (seconds < 0) seconds = 0;
            long s = (long)Math.Ceiling(seconds);
            if (s < 60) return s + "s";
            if (s < 3600) return (s / 60) + "m " + (s % 60) + "s";
            return (s / 3600) + "h " + ((s % 3600) / 60) + "m";
        }

        public static string Pct(double fraction) => (fraction * 100).ToString("0.#", Inv) + "%";
    }
}
