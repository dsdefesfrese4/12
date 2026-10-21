"""Toon-set kit for Blender (bpy): build simple Japanese interiors/exteriors from primitives,
flat 'one colour per block' toon materials, manga ink lines (Freestyle), key/fill lights, camera moves.

Use inside a scene script run with:  blender -b --factory-startup -P scene.py -- <args>
Coordinates: metres, Z up, Y forward.
"""
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector, Euler

C = bpy.context
D = bpy.data


# ------------------------------------------------------------------ setup
def reset(res=(1280, 720), fps=24, engine="BLENDER_EEVEE"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = engine
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.render.fps = fps
    s.render.image_settings.file_format = "PNG"
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    if engine == "BLENDER_EEVEE":
        e = s.eevee
        e.taa_render_samples = 16
        e.use_soft_shadows = True
        e.shadow_cube_size = "1024"
        e.shadow_cascade_size = "2048"
        e.use_gtao = True
        e.gtao_distance = 0.6
        e.use_bloom = False
    w = D.worlds.new("world")
    s.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.02, 0.025, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    return s


def hexc(h, a=1.0):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    # sRGB -> linear
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (f(r), f(g), f(b), a)


# ------------------------------------------------------------------ materials
_MATS = {}


def toon(name, color, shadow=None, steps=2, rim=0.0, emission=0.0):
    """Cel material: diffuse -> Shader to RGB -> constant colour ramp (lit colour / shadow colour)."""
    key = (name, color, shadow, steps)
    if key in _MATS:
        return _MATS[key]
    m = D.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    dif.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    lit = hexc(color)
    sh = hexc(shadow) if shadow else tuple(c * 0.42 for c in lit[:3]) + (1,)
    els = ramp.color_ramp.elements
    els[0].position = 0.0
    els[0].color = sh
    els[1].position = 0.18
    els[1].color = lit
    if steps >= 3:
        e = els.new(0.08)
        e.color = tuple((a + b) / 2 for a, b in zip(sh, lit))
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(dif.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs[0], bw.inputs[0])
    nt.links.new(bw.outputs[0], ramp.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(ramp.outputs[0], em.inputs[0])
    em.inputs[1].default_value = 1.0 + emission
    nt.links.new(em.outputs[0], out.inputs[0])
    _MATS[key] = m
    return m


def glow_mat(name, color, strength=3.0):
    m = D.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = hexc(color)
    em.inputs[1].default_value = strength
    nt.links.new(em.outputs[0], out.inputs[0])
    m.shadow_method = "NONE"
    return m


def image_mat(name, path, alpha=True, emission=1.0):
    """Unlit image card (manga panels, character cutouts, posters)."""
    m = D.materials.new(name)
    m.use_nodes = True
    m.blend_method = "HASHED" if alpha else "OPAQUE"
    m.shadow_method = "HASHED" if alpha else "OPAQUE"
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = D.images.load(path)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[1].default_value = emission
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tex.outputs["Color"], em.inputs[0])
    nt.links.new(tex.outputs["Alpha"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m, tex.image


# ------------------------------------------------------------------ geometry
def _obj(name, mesh, mat=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    o = D.objects.new(name, mesh)
    C.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = Euler([math.radians(a) for a in rot])
    if mat:
        o.data.materials.append(mat)
    return o


def box(name, size, loc, mat, rot=(0, 0, 0), bevel=0.0):
    """size = (x, y, z) full extents; loc = centre of the bottom face."""
    me = D.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z = (v.co.z + 0.5) * size[2]
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect="EDGES")
    bm.to_mesh(me)
    bm.free()
    return _obj(name, me, mat, loc, rot)


def plane(name, w, h, loc, rot, mat):
    me = D.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    for v in bm.verts:
        v.co.x *= w
        v.co.y *= h
    bm.to_mesh(me)
    bm.free()
    return _obj(name, me, mat, loc, rot)


def cylinder(name, r, h, loc, mat, rot=(0, 0, 0), seg=16):
    me = D.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
    for v in bm.verts:
        v.co.z += h / 2
    bm.to_mesh(me)
    bm.free()
    return _obj(name, me, mat, loc, rot)


def card(name, img_path, height, loc, rot=(90, 0, 0), emission=1.0):
    """Image card standing upright (default faces -Y) with real aspect; loc = bottom centre."""
    m, im = image_mat(name, img_path, True, emission)
    w = height * im.size[0] / max(1, im.size[1])
    o = plane(name, w, height, (0, 0, 0), (0, 0, 0), m)
    for v in o.data.vertices:
        v.co.y += height / 2
    o.location = loc
    o.rotation_euler = Euler([math.radians(a) for a in rot])
    return o


def room(name, w, d, h, wall, floor, ceiling=None, open_side="-y", skirting=None):
    """Box room centred on x, floor at z=0, from y=0 to y=d. One side left open for the camera."""
    objs = [box(f"{name}_floor", (w, d, 0.02), (0, d / 2, -0.02), floor)]
    if ceiling:
        objs.append(box(f"{name}_ceil", (w, d, 0.02), (0, d / 2, h), ceiling))
    t = 0.08
    objs.append(box(f"{name}_back", (w, t, h), (0, d + t / 2, 0), wall))
    objs.append(box(f"{name}_left", (t, d, h), (-w / 2 - t / 2, d / 2, 0), wall))
    objs.append(box(f"{name}_right", (t, d, h), (w / 2 + t / 2, d / 2, 0), wall))
    if open_side != "-y":
        objs.append(box(f"{name}_front", (w, t, h), (0, -t / 2, 0), wall))
    if skirting:
        objs.append(box(f"{name}_sk_b", (w, 0.03, 0.08), (0, d - 0.015, 0), skirting))
        objs.append(box(f"{name}_sk_l", (0.03, d, 0.08), (-w / 2 + 0.015, d / 2, 0), skirting))
        objs.append(box(f"{name}_sk_r", (0.03, d, 0.08), (w / 2 - 0.015, d / 2, 0), skirting))
    return objs


def window_hole(wall_obj, x, z, w, h):
    """Boolean a window opening into a wall box (difference)."""
    cut = box("cut", (w, 1.0, h), (x, wall_obj.location.y, z), None)
    mod = wall_obj.modifiers.new("win", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cut
    cut.hide_render = True
    cut.hide_viewport = True
    return cut


def table(name, w, d, h, loc, top_mat, leg_mat, rot=0):
    o = [box(f"{name}_top", (w, d, 0.04), (0, 0, h - 0.04), top_mat)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            o.append(box(f"{name}_leg{sx}{sy}", (0.04, 0.04, h - 0.04), (sx * (w / 2 - 0.05), sy * (d / 2 - 0.05), 0), leg_mat))
    return group(name, o, loc, rot)


def chair(name, loc, rot, seat_mat, leg_mat, seat_h=0.44, back_h=0.42):
    o = [box(f"{name}_seat", (0.42, 0.42, 0.04), (0, 0, seat_h - 0.04), seat_mat),
         box(f"{name}_back", (0.42, 0.04, back_h), (0, 0.19, seat_h), seat_mat)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            o.append(box(f"{name}_leg{sx}{sy}", (0.03, 0.03, seat_h - 0.04), (sx * 0.18, sy * 0.18, 0), leg_mat))
    return group(name, o, loc, rot)


def group(name, objs, loc, rot=0):
    e = D.objects.new(name, None)
    C.scene.collection.objects.link(e)
    for o in objs:
        o.parent = e
    e.location = loc
    e.rotation_euler = Euler((0, 0, math.radians(rot)))
    return e


# ------------------------------------------------------------------ lights / camera / lines
def sun(energy=3.0, rot=(50, 0, 30), color="#fff4e0", angle=2.0):
    L = D.lights.new("sun", "SUN")
    L.energy = energy
    L.color = hexc(color)[:3]
    L.angle = math.radians(angle)
    o = D.objects.new("sun", L)
    C.scene.collection.objects.link(o)
    o.rotation_euler = Euler([math.radians(a) for a in rot])
    return o


def point(loc, energy=200, color="#ffd8a0", radius=0.1):
    L = D.lights.new("pt", "POINT")
    L.energy = energy
    L.color = hexc(color)[:3]
    L.shadow_soft_size = radius
    o = D.objects.new("pt", L)
    C.scene.collection.objects.link(o)
    o.location = loc
    return o


def area(loc, rot, size=2.0, energy=300, color="#cfe0ff"):
    L = D.lights.new("area", "AREA")
    L.energy = energy
    L.size = size
    L.color = hexc(color)[:3]
    o = D.objects.new("area", L)
    C.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = Euler([math.radians(a) for a in rot])
    return o


def world_color(hexcol, strength=1.0):
    bg = C.scene.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = hexc(hexcol)
    bg.inputs[1].default_value = strength


def ink_lines(thickness=1.6, color="#141012", crease=135):
    s = C.scene
    s.render.use_freestyle = True
    s.render.line_thickness_mode = "ABSOLUTE"
    s.render.line_thickness = thickness
    vl = s.view_layers[0]
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    fs.crease_angle = math.radians(crease)
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new("ink")
    ls.select_by_visibility = True
    ls.select_by_edge_types = True
    ls.select_silhouette = True
    ls.select_border = True
    ls.select_crease = True
    if ls.linestyle is None:
        ls.linestyle = D.linestyles.new("ink")
    ls.linestyle.color = hexc(color)[:3]
    ls.linestyle.thickness = thickness
    return ls


def camera(keys, fov=40, name="cam", dof=None):
    """keys: [(frame, (x,y,z), (look_x,look_y,look_z), roll_deg), ...] — Bezier-eased path."""
    cd = D.cameras.new(name)
    cd.angle = math.radians(fov)
    cd.clip_start = 0.02
    cd.clip_end = 200
    o = D.objects.new(name, cd)
    C.scene.collection.objects.link(o)
    C.scene.camera = o
    tgt = D.objects.new(name + "_tgt", None)
    C.scene.collection.objects.link(tgt)
    con = o.constraints.new("TRACK_TO")
    con.target = tgt
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    for f, pos, look, roll in keys:
        o.location = pos
        o.keyframe_insert("location", frame=f)
        tgt.location = look
        tgt.keyframe_insert("location", frame=f)
        o.rotation_euler = Euler((0, 0, 0))
        o.delta_rotation_euler = Euler((0, 0, math.radians(roll)))
        o.keyframe_insert("delta_rotation_euler", frame=f)
    for ob in (o, tgt):
        if ob.animation_data and ob.animation_data.action:
            for fc in ob.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "EASE_IN_OUT"
    if dof:
        cd.dof.use_dof = True
        cd.dof.focus_distance = dof.get("dist", 3.0)
        cd.dof.aperture_fstop = dof.get("fstop", 2.8)
    return o


def render(out_dir, f0, f1, step=1):
    s = C.scene
    s.frame_start, s.frame_end, s.frame_step = f0, f1, step
    os.makedirs(out_dir, exist_ok=True)
    s.render.filepath = os.path.join(out_dir, "f_")
    bpy.ops.render.render(animation=True)


def still(path, frame=1):
    s = C.scene
    s.frame_set(frame)
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)


def args():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


# ------------------------------------------------------------------ export (for AE / other renderers)
def export_scene(path, f0=None, f1=None):
    """Write a renderer-agnostic description: every mesh as world-space box/plane primitives with colours,
    every light, and the camera sampled per frame (position, rotation XYZ deg, fov, focal length in px).
    AE 3D: x right, y DOWN, z forward — the converter is included as `ae` fields (px, 1 m = 100 px)."""
    import json
    s = C.scene
    f0 = f0 or s.frame_start
    f1 = f1 or s.frame_end
    dg = C.evaluated_depsgraph_get()
    out = {"fps": s.render.fps, "resolution": [s.render.resolution_x, s.render.resolution_y], "frames": [f0, f1],
           "units": "metres, Z up (Blender)", "objects": [], "lights": [], "camera": []}
    for o in s.objects:
        if o.type == "MESH" and not o.hide_render:
            ev = o.evaluated_get(dg)
            col = None
            if o.data.materials and o.data.materials[0] and o.data.materials[0].node_tree:
                for n in o.data.materials[0].node_tree.nodes:
                    if n.type == "VALTORGB":
                        col = [list(n.color_ramp.elements[-1].color)[:3], list(n.color_ramp.elements[0].color)[:3]]
                    if n.type == "TEX_IMAGE" and n.image:
                        col = {"image": bpy.path.abspath(n.image.filepath)}
            bb = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
            out["objects"].append({"name": o.name, "matrix_world": [list(r) for r in ev.matrix_world],
                                   "dimensions": list(o.dimensions), "bbox_world": [list(v) for v in bb], "color": col})
        elif o.type == "LIGHT":
            out["lights"].append({"name": o.name, "type": o.data.type, "energy": o.data.energy, "color": list(o.data.color),
                                  "matrix_world": [list(r) for r in o.matrix_world]})
    cam = s.camera
    for f in range(f0, f1 + 1):
        s.frame_set(f)
        m = cam.matrix_world
        loc = m.to_translation()
        rot = m.to_euler("XYZ")
        fov = cam.data.angle
        fpx = (s.render.resolution_x / 2) / math.tan(cam.data.angle_x / 2) if hasattr(cam.data, "angle_x") else None
        out["camera"].append({"frame": f, "location": list(loc), "rotation_deg": [math.degrees(a) for a in rot],
                              "fov_deg": math.degrees(fov), "focal_px": fpx,
                              "ae": {"position_px": [loc.x * 100, -loc.z * 100, loc.y * 100]}})
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1)
    return path
