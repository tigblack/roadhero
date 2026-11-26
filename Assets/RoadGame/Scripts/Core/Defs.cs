using System;
using System.Collections.Generic;
using UnityEngine;

namespace RoadGame
{
    public enum DamageType { Gun = 0, Smash = 1, Pierce = 2, Blast = 3 }
    public enum RewardKind { MaxHP = 0, Regen = 1, Damage = 2, WeaponCopy = 3, ArmorCopy = 4, Gems = 5 }
    public enum TargetKind { Prop, Foot, Vehicle, Boss }
    /// <summary>What a ranged enemy shoots.</summary>
    public enum ProjKind { Bolt, Bullet, Spear, Slug, Acid, Spit }

    /// <summary>Permanent stat reward granted when a destroyed target is harpooned in.</summary>
    [Serializable]
    public struct Reward
    {
        public RewardKind kind;
        public DamageType dmgType;
        public int itemId;      // weapon / armor id for copies
        public double amount;

        public static Reward HP(double a) => new Reward { kind = RewardKind.MaxHP, amount = a };
        public static Reward Regen(double a) => new Reward { kind = RewardKind.Regen, amount = a };
        public static Reward Dmg(DamageType t, double a) => new Reward { kind = RewardKind.Damage, dmgType = t, amount = a };
        public static Reward Weapon(int id, double a = 1) => new Reward { kind = RewardKind.WeaponCopy, itemId = id, amount = a };
        public static Reward Armor(int id, double a = 1) => new Reward { kind = RewardKind.ArmorCopy, itemId = id, amount = a };
        public static Reward Gem(double a) => new Reward { kind = RewardKind.Gems, amount = a };

        public Reward Scaled(double mul)
        {
            var r = this;
            if (kind == RewardKind.MaxHP || kind == RewardKind.Regen || kind == RewardKind.Damage) r.amount = amount * mul;
            return r;
        }
    }

    public class WeaponDef
    {
        public int id;
        public string name;
        public DamageType type;
        public float interval;   // seconds between swings
        public float range;      // reach in meters (from car edge)
        public float dmgMul;     // multiplier on the type damage stat
        public float aoe;        // splash radius (0 = single target)
        public string desc;
    }

    public class ArmorDef
    {
        public int id;
        public string name;
        public string desc;
    }

    public enum ModelId
    {
        // props (zone themed)
        Cactus, DeadTree, Crates, Tires, JunkPile, Shack, Tent, Tower, Boulder, CarWreck, Barrels,
        OilPump, OilTank, Pipes, RedRock, DryBush,
        SaltCrystal, RibCage, Turbine, SaltRock, Skull,
        ToxicBarrels, SwampTree, Hut, ToxicRock, Mushroom,
        // enemies
        Scav, Raider, Spearman, Crossbow, Brute, Buggy,
        // bosses
        BossMammoth, BossBaron, BossColossus, BossWarlord,
        // special
        Chest
    }

    public enum Placement { Scatter, Camp, Road, Arena }

    /// <summary>One kind of spawnable thing within a zone (balance values are zone-local, final numbers).</summary>
    public class SpawnSpec
    {
        public ModelId model;
        public TargetKind kind;
        public string name;
        public int count;
        public Placement placement = Placement.Scatter;
        public double hp;
        public Reward reward;
        public float respawn;       // base respawn seconds
        public float radius = 1f;   // collision / spacing radius
        public float height = 2f;   // HP bar height
        // combat (enemies)
        public double damage;
        public float attackInterval = 1.2f;
        public float attackRange = 1.6f;
        public float speed = 3f;
        public float aggro = 8f;
        public bool ranged;
        public ProjKind proj = ProjKind.Bolt;
        public int burst = 1;               // shots per attack (damage is split between them)
        public float windupTime = 0.35f;
        public float scale = 1f;
        public bool oneTime;        // hidden stash chests: never respawn
        public bool pace;           // intro scouts: keep pace with the car so the first fight happens on the move
    }

    public class ZoneDef
    {
        public int index;
        public string name;
        public string subtitle;
        public Color ground, groundAlt, road, roadEdge, cliff, cliffDark, minimap;
        public Color roadLine;           // painted lane markings
        public Color shade;              // color of soft shadows in this zone
        public Color sky;                // camera background / haze / reflected sky tint
        public Color sun = Color.white;  // sun tint
        public float sunIntensity = 1.2f;
        public double mul;               // HP / reward multiplier
        public List<SpawnSpec> specs = new List<SpawnSpec>();
        public SpawnSpec boss;
        public Reward[] bossRewards;
        public int unlockWeapon = -1;    // weapon unlocked on first boss kill
        public int unlockArmor = -1;
        public int bossGems;
    }

    public static class Content
    {
        public const float ZoneLength = 200f;
        public const float ZoneHalfWidth = 100f;
        public const int ZoneCount = 4;

        public static readonly WeaponDef[] Weapons =
        {
            new WeaponDef { id = 0, name = "Hood Machine Gun", type = DamageType.Gun, interval = 0.62f, range = 8.5f, dmgMul = 1.0f, aoe = 0f,   desc = "Light machine gun on a swivel base, right side of the hood. Auto-aims at the nearest target." },
            new WeaponDef { id = 1, name = "Pipe Hammer",   type = DamageType.Smash,  interval = 1.00f, range = 3.2f, dmgMul = 1.9f, aoe = 2.2f, desc = "Heavy smash, hits an area." },
            new WeaponDef { id = 2, name = "Scrap Spear",   type = DamageType.Pierce, interval = 0.75f, range = 4.6f, dmgMul = 1.3f, aoe = 0f,   desc = "Long reach piercing stabs." },
            new WeaponDef { id = 3, name = "Thunder Lance", type = DamageType.Blast,  interval = 1.40f, range = 4.0f, dmgMul = 2.8f, aoe = 3.2f, desc = "Explosive tip. Big area damage." },
        };

        public static readonly ArmorDef[] Armors =
        {
            new ArmorDef { id = 0, name = "Bull Bar",    desc = "Front ram plating. Reduces damage taken." },
            new ArmorDef { id = 1, name = "Roof Plates", desc = "Riveted roof armor. Reduces damage taken." },
        };

        public static readonly string[] DamageTypeNames = { "Gun", "Smash", "Pierce", "Blast" };

        static ZoneDef[] _zones;
        public static ZoneDef[] Zones { get { if (_zones == null) Build(); return _zones; } }

        static Color C(string hex) { ColorUtility.TryParseHtmlString(hex, out var c); return c; }

        static SpawnSpec Prop(ModelId m, string name, int count, double hp, Reward r, float respawn, float radius, float height, Placement pl = Placement.Scatter, float scale = 1f)
            => new SpawnSpec { model = m, kind = TargetKind.Prop, name = name, count = count, hp = hp, reward = r, respawn = respawn, radius = radius, height = height, placement = pl, scale = scale };

        static SpawnSpec Foot(ModelId m, string name, int count, double hp, Reward r, float respawn, double dmg, float interval, float range, float speed, float aggro, bool ranged = false, float scale = 1f, Placement pl = Placement.Camp)
            => new SpawnSpec { model = m, kind = TargetKind.Foot, name = name, count = count, hp = hp, reward = r, respawn = respawn, damage = dmg, attackInterval = interval, attackRange = range, speed = speed, aggro = aggro, ranged = ranged, radius = 0.55f * scale, height = 2.55f * scale, placement = pl, scale = scale };

        static SpawnSpec Vehicle(ModelId m, string name, int count, double hp, Reward r, float respawn, double dmg, float speed, float aggro)
            => new SpawnSpec { model = m, kind = TargetKind.Vehicle, name = name, count = count, hp = hp, reward = r, respawn = respawn, damage = dmg, attackInterval = 1.6f, attackRange = 2.6f, speed = speed, aggro = aggro, radius = 1.5f, height = 2.4f, placement = Placement.Road };

        static void Build()
        {
            var z = new ZoneDef[ZoneCount];
            var S = DamageType.Gun; var M = DamageType.Smash; var P = DamageType.Pierce; var B = DamageType.Blast;

            // ---------------------------------------------------------------- Zone 1: Dust Flats (balance mirrors the reference's first island)
            z[0] = new ZoneDef
            {
                index = 0, name = "DUST FLATS", subtitle = "Scavenger country",
                // warm sand + ochre, terracotta rock, muted mauve-gray road, lavender shadows
                ground = C("#E0B888"), groundAlt = C("#D3A574"), road = C("#8D8288"), roadEdge = C("#CFA67C"), roadLine = C("#F2D27E"),
                cliff = C("#C67A5C"), cliffDark = C("#A2614A"), minimap = C("#E2B06E"), shade = C("#A99CC6"), sky = C("#EFD6B2"),
                sun = C("#FFF0DA"), sunIntensity = 1.22f,
                mul = 1, unlockWeapon = 1, bossGems = 50,
            };
            z[0].specs.AddRange(new[]
            {
                Prop(ModelId.Cactus,   "Cactus",      38, 21,  Reward.HP(2.5),       45, 0.7f, 2.6f),
                Prop(ModelId.DeadTree, "Dead Tree",   14, 25,  Reward.HP(5),         60, 0.9f, 3.4f),
                Prop(ModelId.Crates,   "Scrap Crates",22, 35,  Reward.Dmg(S, 0.5),   50, 1.0f, 1.9f),
                Prop(ModelId.Tires,    "Tire Stack",  14, 44,  Reward.HP(1.5),       50, 0.9f, 1.7f),
                Prop(ModelId.JunkPile, "Junk Pile",   10, 56,  Reward.HP(10),        90, 1.4f, 2.0f),
                Prop(ModelId.Barrels,  "Fuel Drums",  10, 40,  Reward.Regen(0.1),    60, 0.9f, 1.8f),
                Prop(ModelId.Boulder,  "Boulder",      8, 283, Reward.HP(10),       180, 2.2f, 3.6f),
                Prop(ModelId.CarWreck, "Car Wreck",    6, 600, Reward.Dmg(S, 2),    240, 2.3f, 2.4f),
                Prop(ModelId.Shack,    "Scrap Shack",  8, 105, Reward.Dmg(S, 0.5),  120, 2.3f, 3.6f, Placement.Camp),
                Prop(ModelId.Tent,     "Tent",         8, 44,  Reward.HP(1.5),       60, 1.5f, 2.6f, Placement.Camp),
                Prop(ModelId.Tower,    "Watchtower",   4, 150, Reward.Dmg(S, 1),    150, 1.5f, 6.0f, Placement.Camp),
                Foot(ModelId.Scav,     "Scavenger",   16, 18,  Reward.HP(2),         40, 1.5, 1.2f, 1.5f, 2.8f, 7f, false, 0.95f, Placement.Scatter),
                Foot(ModelId.Raider,   "Raider",      14, 47,  Reward.Regen(0.1),    50, 3.0, 1.1f, 1.6f, 3.2f, 8f),
                Foot(ModelId.Spearman, "Lancer",       8, 71,  Reward.Dmg(S, 0.5),   60, 4.5, 1.3f, 2.3f, 3.0f, 8f),
                Foot(ModelId.Crossbow, "Bolter",       5, 276, Reward.Dmg(S, 2),    120, 6.0, 1.9f, 10f, 2.6f, 12f, true),
                Foot(ModelId.Brute,    "Brute",        3, 640, Reward.Weapon(0),    240, 11, 1.6f, 2.1f, 2.6f, 9f, false, 1.45f),
                Vehicle(ModelId.Buggy, "Buggy",        3, 380, Reward.Dmg(S, 1.5),  150, 9, 8f, 15f),
            });
            z[0].boss = new SpawnSpec { model = ModelId.BossMammoth, kind = TargetKind.Boss, name = "THE MAMMOTH", count = 1, hp = 4000, respawn = 600, damage = 16, attackInterval = 1.7f, attackRange = 4.8f, speed = 4.5f, aggro = 17f, radius = 3.4f, height = 6.5f, placement = Placement.Arena };
            z[0].bossRewards = new[] { Reward.HP(40), Reward.Dmg(S, 3) };

            // ---------------------------------------------------------------- Zone 2: Toxic Wetlands (was Rust Canyon)
            // Blender art: ArtSource/Levels/ToxicWetlands (bundle Levels/ToxicWetlandsZ1); balance, IDs and rewards unchanged.
            // Enemies and boss are the swamp mutants (ArtSource/Characters/ToxicWetlandsMutants, see MutantStyle)
            z[1] = new ZoneDef
            {
                index = 1, name = "TOXIC WETLANDS", subtitle = "The Mire Mother's pumpworks",
                // wet olive mud, mossy berms, faded industrial grey; cool slate shadows, a pale green-grey haze
                ground = C("#6E6B4A"), groundAlt = C("#636042"), road = C("#5F5B57"), roadEdge = C("#6A6547"), roadLine = C("#D8C07A"),
                cliff = C("#6B6957"), cliffDark = C("#4D4B3F"), minimap = C("#6E7546"), shade = C("#8E92AC"), sky = C("#C7CCB4"),
                sun = C("#FFF6DC"), sunIntensity = 1.15f,
                mul = 8, unlockWeapon = 2, unlockArmor = 0, bossGems = 100,
            };
            double m = 8;
            z[1].specs.AddRange(new[]
            {
                Prop(ModelId.DryBush,  "Reed Clump",  34, 21 * m,  Reward.HP(2.5 * m),     45, 0.8f, 2.0f),
                Prop(ModelId.RedRock,  "Bog Rock",    16, 25 * m,  Reward.HP(5 * m),       60, 1.1f, 2.8f),
                Prop(ModelId.Pipes,    "Pipe Stack",  20, 35 * m,  Reward.Dmg(M, 0.5 * m), 50, 1.2f, 1.6f),
                Prop(ModelId.Barrels,  "Chem Drums",  16, 44 * m,  Reward.HP(1.5 * m),     50, 0.9f, 1.8f),
                Prop(ModelId.JunkPile, "Junk Heap",   10, 56 * m,  Reward.Regen(0.1 * m),  90, 1.4f, 2.0f),
                Prop(ModelId.OilTank,  "Toxic Tank",   6, 300 * m, Reward.Dmg(S, 1 * m),  180, 2.0f, 3.6f),
                Prop(ModelId.OilPump,  "Sludge Pump",  6, 600 * m, Reward.Dmg(M, 2 * m),  240, 2.4f, 4.5f),
                Prop(ModelId.CarWreck, "Sunk Wreck",   6, 600 * m, Reward.Dmg(S, 2 * m),  240, 2.3f, 2.4f),
                Prop(ModelId.Shack,    "Stilt Shack",  8, 105 * m, Reward.Dmg(M, 0.5 * m), 120, 2.3f, 3.6f, Placement.Camp),
                Prop(ModelId.Tent,     "Tarp Tent",    8, 44 * m,  Reward.HP(1.5 * m),     60, 1.5f, 2.6f, Placement.Camp),
                Prop(ModelId.Tower,    "Bog Tower",    4, 150 * m, Reward.Dmg(S, 1 * m),  150, 1.5f, 6.0f, Placement.Camp),
                Foot(ModelId.Scav,     "Leechling",   14, 18 * m,  Reward.HP(2 * m),       40, 1.5 * m, 1.2f, 1.5f, 2.8f, 7f, false, 0.95f, Placement.Scatter),
                Foot(ModelId.Raider,   "Mire Crab",   14, 47 * m,  Reward.Regen(0.1 * m),  50, 3.0 * m, 1.1f, 1.6f, 3.2f, 8f),
                Foot(ModelId.Spearman, "Reed Stalker", 9, 71 * m,  Reward.Dmg(M, 0.5 * m), 60, 4.5 * m, 1.3f, 2.3f, 3.0f, 8f),
                Foot(ModelId.Crossbow, "Bile Toad",    6, 276 * m, Reward.Dmg(S, 2 * m),  120, 6.0 * m, 1.9f, 10f, 2.6f, 12f, true),
                Foot(ModelId.Brute,    "Spore Brute",  4, 640 * m, Reward.Weapon(1),      240, 11 * m, 1.6f, 2.1f, 2.6f, 9f, false, 1.45f),
                Vehicle(ModelId.Buggy, "Flesh Engine", 4, 380 * m, Reward.Armor(0),       150, 9 * m, 8.5f, 15f),
            });
            z[1].boss = new SpawnSpec { model = ModelId.BossBaron, kind = TargetKind.Boss, name = "MIRE MOTHER", count = 1, hp = 4000 * m, respawn = 600, damage = 16 * m, attackInterval = 1.6f, attackRange = 4.8f, speed = 3.8f, aggro = 17f, radius = 3.4f, height = 7f, placement = Placement.Arena };
            z[1].bossRewards = new[] { Reward.HP(40 * m), Reward.Dmg(M, 3 * m) };

            // ---------------------------------------------------------------- Zone 3: Ashen Winter (was Salt Flats)
            // Blender art: ArtSource/Levels/AshenWinter (bundle Levels/AshenWinterZ2); enemies and boss are the Ashen
            // Winter creatures (ArtSource/Characters/AshenWinterEnemies, see AshenStyle). Balance, counts, IDs, rewards
            // and unlocks are the Salt Flats' numbers, unchanged.
            z[2] = new ZoneDef
            {
                index = 2, name = "ASHEN WINTER", subtitle = "The Black Reactor's burnt valley",
                // dirty milky snow over graphite ash, dark asphalt with a worn yellow line, light grey concrete,
                // cold grey-blue shadows, an overcast sky; orange-amber only in lamps, furnaces and the reactor
                ground = C("#B9BCC0"), groundAlt = C("#A6A9AE"), road = C("#45464A"), roadEdge = C("#8D8F92"), roadLine = C("#D6A63A"),
                cliff = C("#8E8F91"), cliffDark = C("#5B5D62"), minimap = C("#C3C6CB"), shade = C("#8E9AB8"), sky = C("#C6CBD2"),
                sun = C("#F3F5FA"), sunIntensity = 1.06f,
                mul = 64, unlockWeapon = 3, unlockArmor = 1, bossGems = 200,
            };
            m = 64;
            z[2].specs.AddRange(new[]
            {
                Prop(ModelId.SaltCrystal, "Burnt Tree",       34, 21 * m,  Reward.HP(2.5 * m),     45, 0.8f, 2.4f),
                Prop(ModelId.Skull,    "Concrete Block",      14, 25 * m,  Reward.HP(5 * m),       60, 1.0f, 2.0f),
                Prop(ModelId.Crates,   "Supply Crates",       18, 35 * m,  Reward.Dmg(P, 0.5 * m), 50, 1.0f, 1.9f),
                Prop(ModelId.Tires,    "Frozen Tires",        14, 44 * m,  Reward.HP(1.5 * m),     50, 0.9f, 1.7f),
                Prop(ModelId.SaltRock, "Frost Rock",          10, 283 * m, Reward.HP(10 * m),     180, 2.2f, 3.4f),
                Prop(ModelId.RibCage,  "Fallen Pylon",         8, 150 * m, Reward.Dmg(P, 1 * m),  150, 2.4f, 3.2f),
                Prop(ModelId.Turbine,  "Power Pylon",          5, 600 * m, Reward.Dmg(M, 2 * m),  240, 1.6f, 9.0f),
                Prop(ModelId.CarWreck, "Snowed Wreck",         6, 600 * m, Reward.Dmg(S, 2 * m),  240, 2.3f, 2.4f),
                Prop(ModelId.Barrels,  "Fuel Drums",          10, 40 * m,  Reward.Regen(0.1 * m),  60, 0.9f, 1.8f),
                Prop(ModelId.Shack,    "Scrap Hut",            8, 105 * m, Reward.Dmg(P, 0.5 * m), 120, 2.3f, 3.6f, Placement.Camp),
                Prop(ModelId.Tent,     "Frost Tent",           8, 44 * m,  Reward.HP(1.5 * m),     60, 1.5f, 2.6f, Placement.Camp),
                Prop(ModelId.Tower,    "Watch Post",           4, 150 * m, Reward.Dmg(S, 1 * m),  150, 1.5f, 6.0f, Placement.Camp),
                Foot(ModelId.Scav,     "Ash Pecker",          14, 18 * m,  Reward.HP(2 * m),       40, 1.5 * m, 1.2f, 1.5f, 2.8f, 7f, false, 0.95f, Placement.Scatter),
                Foot(ModelId.Raider,   "Snow Reaper",         14, 47 * m,  Reward.Regen(0.1 * m),  50, 3.0 * m, 1.1f, 1.6f, 3.2f, 8f),
                Foot(ModelId.Spearman, "Needle Walker",       10, 71 * m,  Reward.Dmg(P, 0.5 * m), 60, 4.5 * m, 1.3f, 2.3f, 3.0f, 8f),
                Foot(ModelId.Crossbow, "Boiler Spitter",       7, 276 * m, Reward.Dmg(M, 2 * m),  120, 6.0 * m, 1.9f, 10f, 2.6f, 12f, true),
                Foot(ModelId.Brute,    "Concrete Executioner", 4, 640 * m, Reward.Weapon(2),      240, 11 * m, 1.6f, 2.1f, 2.6f, 9f, false, 1.45f),
                Vehicle(ModelId.Buggy, "Whiteout Raider",      4, 380 * m, Reward.Armor(1),       150, 9 * m, 9f, 15f),
            });
            z[2].boss = new SpawnSpec { model = ModelId.BossColossus, kind = TargetKind.Boss, name = "BLACK REACTOR", count = 1, hp = 4000 * m, respawn = 600, damage = 16 * m, attackInterval = 1.8f, attackRange = 5.2f, speed = 3.4f, aggro = 17f, radius = 3.2f, height = 9.6f, placement = Placement.Arena };
            z[2].bossRewards = new[] { Reward.HP(40 * m), Reward.Dmg(P, 3 * m) };

            // ---------------------------------------------------------------- Zone 4: Toxic Marsh
            z[3] = new ZoneDef
            {
                index = 3, name = "TOXIC MARSH", subtitle = "The Warlord's citadel",
                // muted olive mud, slate rock, dark road, plum shadows; only the goo is saturated green
                ground = C("#A3A475"), groundAlt = C("#95976A"), road = C("#6F6C6E"), roadEdge = C("#8E8E63"), roadLine = C("#E8CF7A"),
                cliff = C("#7C7566"), cliffDark = C("#5E584C"), minimap = C("#86954F"), shade = C("#918BB8"), sky = C("#CACDA6"),
                sun = C("#F8F6DE"), sunIntensity = 1.16f,
                mul = 512, unlockWeapon = -1, bossGems = 400,
            };
            m = 512;
            z[3].specs.AddRange(new[]
            {
                Prop(ModelId.Mushroom,    "Glow Shroom",  34, 21 * m,  Reward.HP(2.5 * m),     45, 0.8f, 2.2f),
                Prop(ModelId.SwampTree,   "Swamp Tree",   16, 25 * m,  Reward.HP(5 * m),       60, 1.0f, 4.0f),
                Prop(ModelId.ToxicBarrels,"Toxic Drums",  20, 35 * m,  Reward.Dmg(B, 0.5 * m), 50, 0.9f, 1.8f),
                Prop(ModelId.Pipes,       "Pipe Stack",   12, 44 * m,  Reward.HP(1.5 * m),     50, 1.2f, 1.6f),
                Prop(ModelId.ToxicRock,   "Slag Rock",    10, 283 * m, Reward.HP(10 * m),     180, 2.2f, 3.4f),
                Prop(ModelId.JunkPile,    "Junk Pile",    10, 56 * m,  Reward.Regen(0.1 * m),  90, 1.4f, 2.0f),
                Prop(ModelId.CarWreck,    "Car Wreck",     6, 600 * m, Reward.Dmg(P, 2 * m),  240, 2.3f, 2.4f),
                Prop(ModelId.OilTank,     "Toxic Tank",    6, 300 * m, Reward.Dmg(B, 1 * m),  180, 2.0f, 3.6f),
                Prop(ModelId.Hut,         "Stilt Hut",     8, 105 * m, Reward.Dmg(B, 0.5 * m), 120, 2.3f, 4.2f, Placement.Camp),
                Prop(ModelId.Tent,        "Tent",          8, 44 * m,  Reward.HP(1.5 * m),     60, 1.5f, 2.6f, Placement.Camp),
                Prop(ModelId.Tower,       "Watchtower",    4, 150 * m, Reward.Dmg(M, 1 * m),  150, 1.5f, 6.0f, Placement.Camp),
                Foot(ModelId.Scav,     "Scavenger",       14, 18 * m,  Reward.HP(2 * m),       40, 1.5 * m, 1.2f, 1.5f, 2.8f, 7f, false, 0.95f, Placement.Scatter),
                Foot(ModelId.Raider,   "Raider",          14, 47 * m,  Reward.Regen(0.1 * m),  50, 3.0 * m, 1.1f, 1.6f, 3.2f, 8f),
                Foot(ModelId.Spearman, "Lancer",          10, 71 * m,  Reward.Dmg(B, 0.5 * m), 60, 4.5 * m, 1.3f, 2.3f, 3.0f, 8f),
                Foot(ModelId.Crossbow, "Bolter",           8, 276 * m, Reward.Dmg(S, 2 * m),  120, 6.0 * m, 1.9f, 10f, 2.6f, 12f, true),
                Foot(ModelId.Brute,    "Brute",            5, 640 * m, Reward.Weapon(3),      240, 11 * m, 1.6f, 2.1f, 2.6f, 9f, false, 1.45f),
                Vehicle(ModelId.Buggy, "Buggy",            5, 380 * m, Reward.Armor(0),       150, 9 * m, 9.5f, 15f),
            });
            z[3].boss = new SpawnSpec { model = ModelId.BossWarlord, kind = TargetKind.Boss, name = "THE WARLORD", count = 1, hp = 4000 * m, respawn = 600, damage = 16 * m, attackInterval = 1.5f, attackRange = 5.0f, speed = 5.0f, aggro = 17f, radius = 3.6f, height = 7.5f, placement = Placement.Arena };
            z[3].bossRewards = new[] { Reward.HP(40 * m), Reward.Dmg(B, 3 * m) };

            foreach (var zone in z) ApplyWeapons(zone);
            _zones = z;
        }

        /// <summary>
        /// Enemy weapons: everybody shoots except the raiders, who are the only melee fighters - they sprint at the
        /// car as soon as it enters their radius and strike fast. Damage per attack stays as in the tables.
        /// </summary>
        static void ApplyWeapons(ZoneDef zone)
        {
            foreach (var s in zone.specs)
            {
                switch (s.model)
                {
                    case ModelId.Scav:      // scrap pipe-gun
                        s.ranged = true; s.proj = ProjKind.Bullet; s.attackRange = 7f; s.windupTime = 0.4f; break;
                    case ModelId.Spearman:  // throws spears
                        s.ranged = true; s.proj = ProjKind.Spear; s.attackRange = 8f; s.windupTime = 0.45f; break;
                    case ModelId.Crossbow:  // crossbow bolts (lobbed)
                        s.ranged = true; s.proj = ProjKind.Bolt; s.attackRange = 10f; s.windupTime = 0.4f; break;
                    case ModelId.Brute:     // blunderbuss: heavy exploding slug
                        s.ranged = true; s.proj = ProjKind.Slug; s.attackRange = 7.5f; s.windupTime = 0.55f; break;
                    case ModelId.Buggy:     // roll-cage machine gun, bursts of 3, circles the car
                        s.ranged = true; s.proj = ProjKind.Bullet; s.burst = 3; s.attackRange = 10f; s.windupTime = 0.3f; break;
                    case ModelId.Raider:    // melee rusher
                        s.ranged = false; s.speed = 7.2f; s.aggro = 9.5f; s.windupTime = 0.18f; s.attackInterval = 0.95f; break;
                }
                if (zone.index == 1) MutantStyle(s);
                else if (zone.index == 2) AshenStyle(s);
            }
        }

        /// <summary>
        /// Second zone (Toxic Wetlands, swamp mutants from ArtSource/Characters/ToxicWetlandsMutants): each creature fights
        /// the way its body is built. HP, damage per attack, attack interval, aggro, rewards and respawn stay the zone's
        /// numbers; only the delivery follows the anatomy. The Leechling bites (a fast melee rusher like the raiders),
        /// the Reed Stalker lunges with its bone spike, the Spore Brute smashes with its club arm (slow), the Bile Toad
        /// spits an acid gob (the bolt's lobbed flight), the Flesh Engine spits acid bursts from its jaw (the machine
        /// gun's flight). Heights put the HP bars and the aim points on the new bodies. The radius stays: it also lays out
        /// the world's spawns (positions and persistent IDs).
        /// </summary>
        static void MutantStyle(SpawnSpec s)
        {
            switch (s.model)
            {
                case ModelId.Scav:     s.ranged = false; s.attackRange = 1.6f; s.speed = 6.8f; s.windupTime = 0.4f; s.height = 1.35f; break;
                case ModelId.Raider:   s.height = 1.9f; break;
                case ModelId.Spearman: s.ranged = false; s.attackRange = 2.8f; s.speed = 4.6f; s.windupTime = 0.45f; s.height = 3.45f; break;
                case ModelId.Crossbow: s.proj = ProjKind.Acid; s.height = 1.7f; break;
                case ModelId.Brute:    s.ranged = false; s.attackRange = 2.6f; s.windupTime = 0.55f; s.height = 3.55f; break;
                case ModelId.Buggy:    s.proj = ProjKind.Spit; break;
            }
        }

        /// <summary>
        /// Third zone (Ashen Winter, creatures from ArtSource/Characters/AshenWinterEnemies): every creature keeps the Salt
        /// Flats role, weapon, range, timing and numbers (the pecker's beak gun, the reaper's blades as the melee rusher,
        /// the needle launcher's spears, the boiler's lobbed shell, the executioner's heavy slug, the sled's turret
        /// bursts). Only the heights change, so the HP bars and the aim points sit on the new bodies. The radius stays:
        /// it also lays out the world's spawns (positions and persistent IDs).
        /// </summary>
        static void AshenStyle(SpawnSpec s)
        {
            switch (s.model)
            {
                case ModelId.Scav:     s.height = 1.85f; break;
                case ModelId.Raider:   s.height = 2.25f; break;
                case ModelId.Spearman: s.height = 3.1f; break;
                case ModelId.Crossbow: s.height = 2.55f; break;
                case ModelId.Brute:    s.height = 3.7f; break;
                case ModelId.Buggy:    s.height = 2.8f; break;
            }
        }

        /// <summary>
        /// The two scouts of the intro canyon: own numbers, separate from the zones' buggies. HP is set from the car's
        /// actual hit damage so the starting machine gun needs exactly two hits: the first takes away more than half the HP
        /// bar, the second wrecks the buggy. Targets have no armor (a hit takes its full damage), and 1.75 hits of HP
        /// means no single round - even a crit (x1.5) - destroys one, while any two always do.
        /// </summary>
        public const double IntroScoutHits = 1.75;
        public static SpawnSpec IntroScout(double hitDamage) => new SpawnSpec
        {
            model = ModelId.Buggy, kind = TargetKind.Vehicle, name = "Scout Buggy", count = 1,
            hp = System.Math.Round(hitDamage * IntroScoutHits, 2), reward = Reward.Dmg(DamageType.Gun, 0.5), respawn = 1e9f, oneTime = true,
            damage = 1.2, attackInterval = 2.2f, attackRange = 8.5f, speed = 7.5f, aggro = 34f,
            ranged = true, proj = ProjKind.Bullet, burst = 2, windupTime = 0.45f,
            radius = 1.5f, height = 2.4f, placement = Placement.Road, pace = true,
        };

        public static ZoneDef ZoneAtZ(float worldZ)
        {
            int i = Mathf.Clamp(Mathf.FloorToInt((worldZ + ZoneLength * 0.5f) / ZoneLength), 0, ZoneCount - 1);
            return Zones[i];
        }

        public static int ZoneIndexAt(float worldZ)
        {
            return Mathf.Clamp(Mathf.FloorToInt((worldZ + ZoneLength * 0.5f) / ZoneLength), 0, ZoneCount - 1);
        }

        public static float ZoneMinZ(int i) => i * ZoneLength - ZoneLength * 0.5f;
        public static float ZoneMaxZ(int i) => i * ZoneLength + ZoneLength * 0.5f;
        public static float ZoneCenterZ(int i) => i * ZoneLength;
    }
}
