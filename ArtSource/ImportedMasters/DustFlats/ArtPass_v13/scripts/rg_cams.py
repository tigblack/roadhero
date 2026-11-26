"""Shared camera/render helpers for the DustFlats v11 art pass.
Game camera (Unity CameraRig): pitch 54 deg, vertical FOV 46 deg, 540x1170 portrait,
half visible ground width 13.5 m -> distance 68.9 m, focus = car + 2.5 m north (Unity +Z = Blender +Y).
Unity (x,y,z) -> Blender (x,z,y)."""
import bpy, math
from mathutils import Vector, Euler

PITCH = 54.0
FOV_V = 46.0
W, H = 540, 1170
HALF_W = 13.5

def game_distance(aspect=W / H, half_w=HALF_W, zoom=1.0):
    t = math.tan(math.radians(FOV_V * 0.5))
    return max(half_w / (t * aspect), 15.0 / t) * zoom

def game_camera(name, car_xy, floor_z=0.0, zoom=1.0, collection=None):
    """car_xy in Blender (x, y). Returns a camera object placed like the Unity CameraRig."""
    cam_data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cam_data.type = 'PERSP'
    cam_data.sensor_fit = 'VERTICAL'
    cam_data.angle_y = math.radians(FOV_V)
    cam_data.clip_start = 1.0
    cam_data.clip_end = 190.0
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, cam_data)
        (collection or bpy.context.scene.collection).objects.link(cam)
    d = game_distance(zoom=zoom)
    focus = Vector((car_xy[0], car_xy[1] + 2.5, floor_z))
    p = math.radians(PITCH)
    cam.location = focus + Vector((0, -math.cos(p) * d, math.sin(p) * d))
    cam.rotation_euler = Euler((math.radians(90 - PITCH), 0, 0), 'XYZ')
    cam["roadgame_camera"] = f"Unity CameraRig: pitch {PITCH}, vFOV {FOV_V}, {W}x{H}, distance {d:.1f} m"
    return cam

def free_camera(name, loc, look_at, lens=35.0, collection=None, ortho_scale=None):
    cam_data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    if ortho_scale:
        cam_data.type = 'ORTHO'; cam_data.ortho_scale = ortho_scale
    else:
        cam_data.type = 'PERSP'; cam_data.lens = lens
    cam_data.sensor_fit = 'AUTO'
    cam_data.clip_start = 0.5; cam_data.clip_end = 2000
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, cam_data)
        (collection or bpy.context.scene.collection).objects.link(cam)
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(look_at) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return cam

# Shot list shared by before/after renders. (name, kind, params)
SHOTS = [
    ("01_overview",        "free", dict(loc=(150, -330, 260), look=(0, -40, 0), lens=34, res=(1600, 1200))),
    ("02_intro_canyon",    "game", dict(car=(0, -205))),
    ("02b_intro_canyon_low","free", dict(loc=(-9, -232, 9), look=(2, -170, 1.5), lens=28, res=(1400, 900))),
    ("03_road_section",    "game", dict(car=(-24, -50))),
    ("04_camp",            "game", dict(car=(-70, -44))),
    ("05_ramp_intro",      "game", dict(car=(0, -122))),
    ("05b_ramp_side",      "free", dict(loc=(-9, -127, 4.2), look=(1.5, -112, 1.2), lens=28, res=(1400, 900))),
    ("06_works_entrance",  "game", dict(car=(24, 38))),
    ("06b_works_side",     "free", dict(loc=(0, 10, 22), look=(40, 55, -1), lens=30, res=(1400, 900))),
    ("07_hangar_interior", "game", dict(car=(52, 66), floor=-4.5, hide_roofs=True)),
    ("07b_hangar_low",     "free", dict(loc=(30, 56, 3.5), look=(60, 76, -4), lens=24, res=(1400, 900), hide_roofs=True)),
]

# v12 review shots
SHOTS_V12 = [
    ("01_overview",          "free", dict(loc=(150, -330, 260), look=(0, -40, 0), lens=34, res=(1600, 1200))),
    ("01b_top_outline",      "ortho", dict(center=(0, -70), scale=390, res=(1100, 1560))),
    ("02_intro_canyon",      "game", dict(car=(0, -205))),
    ("02b_intro_canyon_low", "free", dict(loc=(-9, -232, 9), look=(2, -170, 1.5), lens=28, res=(1400, 900))),
    ("03_road_section",      "game", dict(car=(-24, -50))),
    ("04_camp",              "game", dict(car=(-70, -44))),
    ("05_ramp_intro",        "game", dict(car=(0, -122))),
    ("05b_ramp_side",        "free", dict(loc=(-9, -127, 4.2), look=(1.5, -112, 1.2), lens=28, res=(1400, 900))),
    ("06_works_entrance",    "game", dict(car=(24, 38))),
    ("06b_works_side",       "free", dict(loc=(0, 10, 22), look=(40, 55, -1), lens=30, res=(1400, 900))),
    ("07_hangar_interior",   "game", dict(car=(52, 66), floor=-4.5, hide_roofs=True)),
    ("07b_hangar_low",       "free", dict(loc=(30, 56, 3.5), look=(60, 76, -4), lens=24, res=(1400, 900), hide_roofs=True)),
    ("08_river_bridge1",     "game", dict(car=(-14, 14))),
    ("08b_river_bridge1_low","free", dict(loc=(-32, 4, 7), look=(-12, 22, 0), lens=30, res=(1400, 900))),
    ("09_river_ford_centre", "game", dict(car=(-5, -12))),
    ("09b_car_in_ford",      "free", dict(loc=(9, -14, 3.2), look=(-5, -5, 0), lens=40, res=(1400, 900))),
    ("10_river_bridge2",     "game", dict(car=(26, -38))),
    ("10b_river_bridge2_low","free", dict(loc=(42, -46, 5), look=(26, -31, 0), lens=30, res=(1400, 900))),
    ("11_river_east",        "game", dict(car=(70, -52))),
    ("12_ford_north",        "game", dict(car=(-36, 58))),
]
