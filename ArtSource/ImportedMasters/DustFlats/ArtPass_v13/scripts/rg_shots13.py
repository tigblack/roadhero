"""v13 SmoothPass comparison shots (same cameras for before/after, clay and colour).
kind: 'game' = Unity CameraRig (pitch 54, vFOV 46, 540x1170 portrait), 'free' = perspective."""
SHOTS_V13 = [
    ("01_overview",          "free", dict(loc=(150, -330, 260), look=(0, -40, 0), lens=34, res=(1600, 1200))),
    ("02_elev_roadhill",     "free", dict(loc=(2, -64, 6.5), look=(-21, -52, 0.8), lens=30)),
    ("02g_elev_roadhill",    "game", dict(car=(-20, -56))),
    ("03_road_bend",         "free", dict(loc=(10, -101, 7.5), look=(-5, -74, 0.0), lens=30)),
    ("03g_road_bend",        "game", dict(car=(-3, -79))),
    ("04_ramp_intro_side",   "free", dict(loc=(-9, -127, 4.2), look=(1.5, -112, 1.2), lens=28)),
    ("04b_bigjump",          "free", dict(loc=(27, -83, 4.5), look=(38.5, -66, 1.0), lens=30)),
    ("04c_plateau_ramp",     "free", dict(loc=(52, -47, 7.5), look=(72, -33, 1.2), lens=28)),
    ("04g_ramp_intro",       "game", dict(car=(0, -122))),
    ("05_camp_buildings",    "free", dict(loc=(-48, 6, 9), look=(-66, 24, 2.0), lens=30)),
    ("05b_garage",           "free", dict(loc=(-29, -58, 8), look=(-47, -39, 2.0), lens=30)),
    ("05c_camp_south",       "free", dict(loc=(-55, -66, 9), look=(-72, -44, 2.0), lens=30)),
    ("05g_camp",             "game", dict(car=(-70, -44))),
    ("06_works_side",        "free", dict(loc=(0, 10, 22), look=(40, 55, -1), lens=30)),
    ("06b_hangar_ext",       "free", dict(loc=(8, 28, 13), look=(46, 70, 2), lens=28)),
    ("06g_works_entrance",   "game", dict(car=(24, 38))),
    ("07_hangar_interior",   "game", dict(car=(52, 66), floor=-4.5, hide_roofs=True)),
    ("08_bridge1_bank",      "free", dict(loc=(-32, 4, 7), look=(-12, 22, 0), lens=30)),
    ("08g_bridge1",          "game", dict(car=(-14, 14))),
    ("09_bridge2_bank",      "free", dict(loc=(42, -46, 5), look=(26, -31, 0), lens=30)),
    ("10_mesa",              "free", dict(loc=(-26, 38, 16), look=(-62, 70, 4), lens=28)),
    ("10g_mesa_road",        "game", dict(car=(-50, 70), floor=1.5)),
    ("11_hill_open",         "free", dict(loc=(58, -101, 6), look=(77, -77, 1.5), lens=30)),
    ("12_ridge_plateau",     "free", dict(loc=(52, -36, 11), look=(48, -56, 1.5), lens=28)),
]
# props / small structures close-ups (object names; framed by bounds)
CLOSEUPS_V13 = ['Body.098', 'Body.100', 'Body.103', 'Body.074', 'Body.075', 'Body.080', 'Body.052', 'Body.054', 'Body.055',
                'Body.088', 'Body.091', 'Body.116', 'Body.122', 'Body.123', 'Body.128', 'Body.130', 'Body.138',
                'Barricade', 'Funnel', 'Billboard', 'Pad', 'GateTowers', 'Vents', 'WorksSign', 'HangarDoor',
                'Wreck', 'AP_Bridge_Road0', 'AP_Bridge_Track', 'Kicker0a.001', 'Ramp.002', 'Ramp.007']
