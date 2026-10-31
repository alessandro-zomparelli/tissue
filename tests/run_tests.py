# SPDX-FileCopyrightText: 2026 Alessandro Zomparelli
#
# SPDX-License-Identifier: GPL-3.0-or-later

# Smoke tests for Tissue, run inside Blender without a window:
#
#   blender --background --factory-startup --python tests/run_tests.py
#
# Every test builds a small scene, runs one Tissue tool and checks its result.
# The script exits with code 1 if any test fails, so CI marks the run as failed.

import os
import shutil
import sys
import tempfile
import traceback

import addon_utils
import bmesh
import bpy

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TESTS = []


def test(func):
    TESTS.append(func)
    return func


def enable_tissue():
    # Copy the add-on into a folder called "tissue" so it imports under its own
    # name wherever the repository is checked out.
    root = tempfile.mkdtemp(prefix="tissue_tests_")
    shutil.copytree(REPO, os.path.join(root, "tissue"),
                    ignore=shutil.ignore_patterns(".git", "docs", "tests", "__pycache__"))
    sys.path.insert(0, root)
    addon_utils.enable("tissue", default_set=True, handle_error=None)
    if "tissue" not in bpy.context.preferences.addons:
        raise RuntimeError("Tissue could not be enabled")


def reset_scene():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for collection in (bpy.data.objects, bpy.data.meshes, bpy.data.curves,
                       bpy.data.materials, bpy.data.lattices, bpy.data.textures):
        bpy.data.batch_remove(list(collection))


def select_only(*objects, active=None):
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    for ob in objects:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = active or objects[-1]


def add_grid(size=4):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=size + 1, y_subdivisions=size + 1, size=2)
    return bpy.context.object


def add_cube(size=0.5, location=(0, 0, 3)):
    bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    return bpy.context.object


def add_icosphere(subdivisions=2):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions)
    return bpy.context.object


def add_weight(ob, name="Weight"):
    # A vertex group going from 0 to 1 along X.
    group = ob.vertex_groups.new(name=name)
    xs = [v.co.x for v in ob.data.vertices]
    lo, hi = min(xs), max(xs)
    for v in ob.data.vertices:
        group.add([v.index], (v.co.x - lo) / (hi - lo), 'REPLACE')
    ob.vertex_groups.active_index = group.index
    return group


def weights(ob, group):
    values = []
    for v in ob.data.vertices:
        for g in v.groups:
            if g.group == group.index:
                values.append(g.weight)
    return values


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def check_finished(result, name):
    check(result == {'FINISHED'}, f"{name} returned {result}")


def check_weights(ob, group):
    values = weights(ob, group)
    check(values, f"vertex group '{group.name}' is empty")
    check(all(0 <= w <= 1 for w in values), f"vertex group '{group.name}' has weights outside 0-1")


def new_group(ob, before):
    added = [g for g in ob.vertex_groups if g.name not in before]
    check(added, "no vertex group was created")
    return added[-1]


# --- Tissue Tools -------------------------------------------------------------


def tessellate(fill_mode, prepare=None):
    base = add_grid()
    if prepare:
        prepare(base)
    component = add_cube()
    select_only(component, base, active=base)
    result = bpy.ops.object.tissue_tessellate(
        generator=base.name, component=component.name, fill_mode=fill_mode)
    check_finished(result, f"Tessellate ({fill_mode})")
    out = bpy.context.object
    check(out not in (base, component), "no tessellated object was created")
    check(out.tissue.tissue_type == 'TESSELLATE', "result is not marked as a tessellation")
    check(len(out.data.polygons) > 0, "tessellation is empty")
    return base, component, out


@test
def tessellate_quad():
    base, component, out = tessellate('QUAD')
    expected = len(base.data.polygons) * len(component.data.polygons)
    check(len(out.data.polygons) == expected,
          f"expected {expected} faces, got {len(out.data.polygons)}")


@test
def tessellate_tri():
    tessellate('TRI')


@test
def tessellate_fan():
    tessellate('FAN')


@test
def tessellate_frame():
    tessellate('FRAME')


@test
def tessellate_patch():
    tessellate('PATCH', prepare=lambda base: base.modifiers.new("Subdivision", 'SUBSURF'))


@test
def tessellate_refresh():
    base, component, out = tessellate('QUAD')
    faces = len(out.data.polygons)
    component.scale = (1, 1, 2)
    select_only(out)
    check_finished(bpy.ops.object.tissue_update_tessellate(), "Refresh")
    check(len(out.data.polygons) == faces, "refresh changed the number of faces")


@test
def dual_mesh():
    ob = add_icosphere()
    vertices = len(ob.data.vertices)
    select_only(ob)
    check_finished(bpy.ops.object.dual_mesh(), "Dual Mesh")
    # The dual of a closed triangle mesh has one face per original vertex.
    check(len(ob.data.polygons) == vertices,
          f"expected {vertices} faces, got {len(ob.data.polygons)}")


@test
def polyhedra_wireframe():
    ob = add_cube(size=2, location=(0, 0, 0))
    select_only(ob)
    check_finished(bpy.ops.object.polyhedral_wireframe(), "Polyhedra Wireframe")
    check(len(bpy.context.object.data.polygons) > 0, "result is empty")


@test
def convert_to_curve():
    ob = add_grid()
    select_only(ob)
    check_finished(bpy.ops.object.tissue_convert_to_curve(), "Convert to Curve")
    check(bpy.context.object.type == 'CURVE', "result is not a curve")


@test
def lattice_along_surface():
    surface = add_grid()
    ob = add_cube(size=0.5, location=(0, 0, 1))
    select_only(ob, surface, active=surface)
    # Hiding the lattice needs a 3D Viewport, which background mode does not have.
    check_finished(bpy.ops.object.lattice_along_surface(hide_lattice=False), "Lattice along Surface")
    check(any(o.type == 'LATTICE' for o in bpy.data.objects), "no lattice was created")


@test
def uv_to_mesh():
    ob = add_cube(size=2, location=(0, 0, 0))
    select_only(ob)
    check_finished(bpy.ops.object.uv_to_mesh(), "UV to Mesh")
    check(bpy.context.object != ob, "no mesh was created")


@test
def random_materials():
    ob = add_grid()
    for i in range(3):
        ob.data.materials.append(bpy.data.materials.new(f"Material{i}"))
    select_only(ob)
    check_finished(bpy.ops.object.random_materials(), "Random Materials")
    used = {p.material_index for p in ob.data.polygons}
    check(len(used) > 1, "all faces kept the same material")


@test
def weight_to_materials():
    ob = add_grid()
    add_weight(ob)
    for i in range(3):
        ob.data.materials.append(bpy.data.materials.new(f"Material{i}"))
    select_only(ob)
    check_finished(bpy.ops.object.weight_to_materials(), "Weight to Materials")


@test
def rotate_faces():
    base, component, out = tessellate('QUAD')
    select_only(base)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    check_finished(bpy.ops.mesh.tissue_rotate_face_right(), "Rotate Faces")
    bpy.ops.object.mode_set(mode='OBJECT')


# --- Tissue Weight Tools ------------------------------------------------------


def weight_tool(operator, name, prepare=None, **kwargs):
    ob = add_icosphere(subdivisions=3)
    if prepare:
        prepare(ob)
    select_only(ob)
    before = {g.name for g in ob.vertex_groups}
    check_finished(operator(**kwargs), name)
    check_weights(ob, new_group(ob, before))
    return ob


@test
def weight_area():
    weight_tool(bpy.ops.object.face_area_to_vertex_groups, "Area")


@test
def weight_curvature():
    weight_tool(bpy.ops.object.curvature_to_vertex_groups, "Curvature")


@test
def weight_formula():
    weight_tool(bpy.ops.object.weight_formula, "Weight Formula", formula="rz")


@test
def weight_random():
    # Random fills the active vertex group instead of creating a new one.
    ob = add_icosphere(subdivisions=3)
    group = add_weight(ob)
    select_only(ob)
    check_finished(bpy.ops.object.random_weight(), "Random")
    check_weights(ob, group)


@test
def weight_harmonic():
    weight_tool(bpy.ops.object.harmonic_weight, "Harmonic", prepare=add_weight)


@test
def weight_laplacian():
    weight_tool(bpy.ops.object.weight_laplacian, "Weight Laplacian", prepare=add_weight)


@test
def weight_distance():
    def select_one_vertex(ob):
        for v in ob.data.vertices:
            v.select = v.index == 0
    weight_tool(bpy.ops.object.tissue_weight_distance, "Weight Distance", prepare=select_one_vertex)


@test
def edges_deformation():
    def deform(ob):
        ob.modifiers.new("Cast", 'CAST').factor = 1.0
    weight_tool(bpy.ops.object.edges_deformation, "Edges Deformation", prepare=deform)


@test
def edges_bending():
    def deform(ob):
        ob.modifiers.new("Cast", 'CAST').factor = 1.0
    weight_tool(bpy.ops.object.edges_bending, "Edges Bending", prepare=deform)


@test
def contour_curves():
    ob = add_icosphere(subdivisions=3)
    add_weight(ob)
    select_only(ob)
    check_finished(bpy.ops.object.tissue_weight_contour_curves_pattern(object=ob.name), "Contour Curves")
    check(bpy.context.object != ob, "no contour object was created")


@test
def contour_displace():
    ob = add_icosphere(subdivisions=3)
    add_weight(ob)
    select_only(ob)
    check_finished(bpy.ops.object.weight_contour_displace(), "Contour Displace")


@test
def contour_mask():
    ob = add_icosphere(subdivisions=3)
    add_weight(ob)
    select_only(ob)
    check_finished(bpy.ops.object.weight_contour_mask(), "Contour Mask")


@test
def reaction_diffusion():
    ob = add_icosphere(subdivisions=3)
    select_only(ob)
    check_finished(bpy.ops.object.reaction_diffusion_free_data(), "Reaction Diffusion reset")
    check_finished(bpy.ops.object.start_reaction_diffusion(), "Reaction Diffusion")
    check({"A", "B"} <= {g.name for g in ob.vertex_groups}, "groups A and B were not created")


# --- Conversions --------------------------------------------------------------


@test
def weight_to_colors_and_back():
    ob = add_icosphere(subdivisions=3)
    add_weight(ob)
    select_only(ob)
    check_finished(bpy.ops.object.vertex_group_to_vertex_colors(), "Convert to Colors")
    check(len(ob.data.color_attributes) > 0, "no color attribute was created")
    before = {g.name for g in ob.vertex_groups}
    check_finished(bpy.ops.object.vertex_colors_to_vertex_groups(), "Convert to Weight")
    check_weights(ob, new_group(ob, before))


@test
def weight_to_uv():
    ob = add_icosphere(subdivisions=3)
    add_weight(ob)
    select_only(ob)
    uv_maps = len(ob.data.uv_layers)
    check_finished(bpy.ops.object.vertex_group_to_uv(), "Convert to UV")
    check(len(ob.data.uv_layers) > uv_maps, "no UV map was created")


# --- Runner -------------------------------------------------------------------


def main():
    print(f"\nBlender {bpy.app.version_string}, Python {sys.version.split()[0]}")
    enable_tissue()
    failures = []
    for func in TESTS:
        reset_scene()
        try:
            func()
        except Exception:
            failures.append((func.__name__, traceback.format_exc()))
            print(f"FAIL  {func.__name__}")
        else:
            print(f"ok    {func.__name__}")

    for name, trace in failures:
        print(f"\n--- {name} ---\n{trace}")
    print(f"\n{len(TESTS) - len(failures)} passed, {len(failures)} failed")
    sys.exit(1 if failures else 0)


main()
