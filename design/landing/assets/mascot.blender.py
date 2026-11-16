# Blender script: cute clay hero for KOC Discovery landing (option B).
# Run: blender -b -P clay_hero.py -- <out.png>
import math
import sys

import bpy
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def hex_rgba(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1.0,)


def clay(name, color, rough=0.62, sss=0.08, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hex_rgba(color)
    b.inputs["Roughness"].default_value = rough
    for key in ("Subsurface Weight", "Subsurface"):
        if key in b.inputs:
            b.inputs[key].default_value = sss
            break
    if emit:
        b.inputs["Emission Color"].default_value = hex_rgba(color)
        b.inputs["Emission Strength"].default_value = emit
    return m


M = {
    "cream": clay("cream", "#FFF8EC"),
    "green": clay("green", "#2F5D50"),
    "green2": clay("green2", "#3F7464"),
    "sage": clay("sage", "#A9C7B8"),
    "mint": clay("mint", "#DCE8E2"),
    "clay": clay("clay", "#B5643C"),
    "claysoft": clay("claysoft", "#F3D2C0"),
    "skin": clay("skin", "#F6D3B8", sss=0.25),
    "hair": clay("hair", "#2A211D", rough=0.5),
    "ink": clay("ink", "#1F2A24", rough=0.3),
    "blush": clay("blush", "#F2A99A", rough=0.8),
    "light": clay("light", "#FFF4DD", emit=2.5),
    "screen": clay("screen", "#DCE8E2", emit=0.6),
}


def soft(obj, bevel=0.0, subd=2):
    if bevel:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 4
    if subd:
        mod = obj.modifiers.new("subd", "SUBSURF")
        mod.levels = subd
        mod.render_levels = subd
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def put(obj, mat):
    obj.data.materials.append(M[mat])
    return obj


def sphere(loc, r, mat, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=48, ring_count=24)
    o = bpy.context.object
    o.scale = scale
    for p in o.data.polygons:
        p.use_smooth = True
    return put(o, mat)


def cyl(loc, r, depth, mat, scale=(1, 1, 1), rot=(0, 0, 0), bevel=0.08):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=48)
    o = bpy.context.object
    o.scale = scale
    return put(soft(o, bevel, 2), mat)


def box(loc, size, mat, rot=(0, 0, 0), bevel=0.06):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    return put(soft(o, bevel, 2), mat)


def tube(points, radius, mat):
    cu = bpy.data.curves.new("c", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 6
    cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for bp, co in zip(sp.bezier_points, points):
        bp.co = co
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    o = bpy.data.objects.new("curve", cu)
    scene.collection.objects.link(o)
    o.data.materials.append(M[mat])
    return o


def face(x, z, front_y, s=1.0, closed=False):
    """Eyes, smile and blush on a surface facing -Y at front_y."""
    if closed:
        for dx in (-0.22, 0.22):
            tube([(x + dx * s - 0.08 * s, front_y, z + 0.0), (x + dx * s, front_y - 0.02, z + 0.06 * s), (x + dx * s + 0.08 * s, front_y, z)], 0.025 * s, "ink")
    else:
        for dx in (-0.22, 0.22):
            sphere((x + dx * s, front_y, z), 0.075 * s, "ink", (1, 0.6, 1.25))
            sphere((x + dx * s + 0.025 * s, front_y - 0.05 * s, z + 0.035 * s), 0.022 * s, "light")
    tube([(x - 0.13 * s, front_y, z - 0.2 * s), (x, front_y - 0.02, z - 0.3 * s), (x + 0.13 * s, front_y, z - 0.2 * s)], 0.028 * s, "ink")
    for dx in (-0.36, 0.36):
        sphere((x + dx * s, front_y + 0.01, z - 0.16 * s), 0.09 * s, "blush", (1, 0.3, 0.6))


# --- mascot: sunscreen tube --------------------------------------------------
MX = -2.35
cyl((MX - 0.32, 0, 0.32), 0.2, 0.5, "green")          # legs
cyl((MX + 0.32, 0, 0.32), 0.2, 0.5, "green")
sphere((MX - 0.36, -0.12, 0.1), 0.24, "green", (1, 1.4, 0.6))
sphere((MX + 0.36, -0.12, 0.1), 0.24, "green", (1, 1.4, 0.6))
cyl((MX, 0, 0.95), 0.78, 0.7, "green", scale=(1.15, 0.72, 1), bevel=0.15)  # cap
body = cyl((MX, 0, 2.55), 0.92, 2.6, "cream", scale=(1.12, 0.66, 1), bevel=0.2)
taper = body.modifiers.new("taper", "SIMPLE_DEFORM")
taper.deform_method = "TAPER"
taper.factor = 0.28
taper.deform_axis = "Z"
body.modifiers.move(len(body.modifiers) - 1, 0)
box((MX, 0, 3.98), (2.3, 0.32, 0.34), "cream", bevel=0.12)  # crimped end
for i in range(7):
    box((MX - 0.84 + i * 0.28, -0.17, 3.98), (0.05, 0.02, 0.26), "mint", bevel=0.01)
cyl((MX, 0, 1.55), 0.93, 0.5, "sage", scale=(1.13, 0.67, 1), bevel=0.05)  # lower band
sphere((MX, -0.63, 1.58), 0.2, "claysoft", (1, 0.25, 1))  # little sun on the band
for a in range(-75, 76, 25):
    r = math.radians(a)
    box((MX + math.sin(r) * 0.36, -0.63, 1.58 + math.cos(r) * 0.36), (0.045, 0.03, 0.1), "claysoft", rot=(0, r, 0), bevel=0.015)
face(MX, 2.55, -0.64, s=1.25)
tube([(MX - 1.0, -0.1, 2.3), (MX - 1.45, -0.2, 2.0), (MX - 1.55, -0.3, 1.55)], 0.11, "cream")   # left arm
tube([(MX + 1.0, -0.1, 2.3), (MX + 1.5, -0.4, 2.55), (MX + 1.85, -0.6, 2.9)], 0.11, "cream")   # right arm
sphere((MX - 1.55, -0.32, 1.48), 0.15, "cream")
phone = box((MX + 2.0, -0.7, 3.15), (0.42, 0.1, 0.78), "green", rot=(0, math.radians(-18), 0), bevel=0.08)
box((MX + 2.0, -0.77, 3.15), (0.34, 0.02, 0.62), "screen", rot=(0, math.radians(-18), 0), bevel=0.02)
sphere((MX + 1.9, -0.66, 2.95), 0.15, "cream")


# sparkles
for loc, r, mat in [((-3.9, -0.2, 4.4), 0.15, "clay"), ((-0.6, 0.0, 4.5), 0.11, "green2")]:
    bpy.ops.mesh.primitive_ico_sphere_add(radius=r, location=loc, subdivisions=1)
    st = bpy.context.object
    st.scale = (1, 1, 1.8)
    put(st, mat)

# shadow catcher: a round disc, so the shadow fades inside the frame instead of ending at its edge
bpy.ops.mesh.primitive_circle_add(vertices=128, radius=3.4, fill_type="NGON", location=(-2.1, 0, 0))
ground = bpy.context.object
ground.is_shadow_catcher = True

# --- camera, light, render ---------------------------------------------------
cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 62
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
cam.location = (-1.95, -12.5, 3.6)
direction = Vector((-1.95, 0, 2.25)) - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
scene.camera = cam


def area(name, loc, energy, size, color=(1, 1, 1), shadow=True):
    ld = bpy.data.lights.new(name, "AREA")
    ld.use_shadow = shadow
    ld.energy = energy
    ld.size = size
    ld.color = color
    lo = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (Vector((0, 0, 1.8)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


area("key", (-1.5, -4, 13), 2200, 8, (1.0, 0.96, 0.9))
area("fill", (8, -10, 3), 1300, 10, (0.9, 0.97, 1.0), shadow=False)
area("rim", (2, 8, 7), 1100, 5, shadow=False)

world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = hex_rgba("#F6F3EE")
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
scene.world = world

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 128
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.resolution_x = 900
scene.render.resolution_y = 1000
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("SAVED", OUT)
