# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# ---------------------------- ADAPTIVE DUPLIFACES --------------------------- #
# ------------------------------- version 0.84 ------------------------------- #
#                                                                              #
# Creates duplicates of selected mesh to active morphing the shape according   #
# to target faces.                                                             #
#                                                                              #
#                    (c)  Alessandro Zomparelli                                #
#                             (2017)                                           #
#                                                                              #
# http://www.co-de-it.com/                                                     #
#                                                                              #
# ############################################################################ #


import bpy
from bpy.types import (
        Operator,
        Panel,
        PropertyGroup,
        )
from bpy.props import (
        BoolProperty,
        EnumProperty,
        FloatProperty,
        IntProperty,
        StringProperty,
        PointerProperty
        )
from mathutils import Vector
import numpy as np
from math import *
import random, time, copy
import bmesh
from .utils import *

def anim_tessellate_active(self, context):
    ob = context.object
    props = ob.tissue_tessellate
    if not (props.bool_lock or props.bool_hold):
        try:
            props.generator.name
            props.component.name
            bpy.ops.object.tissue_update_tessellate()
        except: pass

def anim_tessellate_object(ob):
    try:
        #bpy.context.view_layer.objects.active = ob
        bpy.ops.object.tissue_update_tessellate()
    except:
        return None

#from bpy.app.handlers import persistent

def anim_tessellate(scene):
    try:
        active_object = bpy.context.object
        old_mode = bpy.context.object.mode
        selected_objects = bpy.context.selected_objects
    except: active_object = old_mode = selected_objects = None
    if old_mode in ('OBJECT', 'PAINT_WEIGHT'):
        update_objects = []
        for ob in scene.objects:
            if ob.tissue_tessellate.bool_run and not ob.tissue_tessellate.bool_lock:
                if ob not in update_objects: update_objects.append(ob)
                update_objects = list(reversed(update_dependencies(ob, update_objects)))
        for ob in update_objects:
            override = {'object': ob}
            '''
            win      = bpy.data.window_managers[0].windows[0]#bpy.context.window
            scr      = win.screen
            areas3d  = [area for area in scr.areas if area.type == 'VIEW_3D']
            region   = [region for region in areas3d[0].regions if region.type == 'WINDOW']
            override = {
                'window':win,
                'screen':scr,
                'area'  :areas3d[0],
                'region':region[0],
                'scene' :scene,
                'object': ob
            }
            '''
            print(override)
            bpy.ops.object.tissue_update_tessellate(override)
    # restore selected objects
    if old_mode != None:
        for o in scene.objects:
            if not o.hide_viewport: o.select_set(o in selected_objects)
        bpy.context.view_layer.objects.active = active_object
        bpy.ops.object.mode_set(mode=old_mode)
    return


def set_tessellate_handler(self, context):
    old_handlers = []
    blender_handlers = bpy.app.handlers.frame_change_post
    for h in blender_handlers:
        if "anim_tessellate" in str(h):
            old_handlers.append(h)
    for h in old_handlers: blender_handlers.remove(h)
    for o in context.scene.objects:
        if o.tissue_tessellate.bool_run:
            blender_handlers.append(anim_tessellate)
            break
    return

class tissue_tessellate_prop(PropertyGroup):
    bool_lock : BoolProperty(
        name="Lock",
        description="Prevent automatic update on settings changes or if other objects have it in the hierarchy.",
        default=False
        )
    bool_hold : BoolProperty(
        name="Hold",
        description="Wait...",
        default=False
        )
    bool_dependencies : BoolProperty(
        name="Update Dependencies",
        description="Automatically updates base and components as well, if results of other tessellations",
        default=False
        )
    bool_run : BoolProperty(
        name="Animatable Tessellation",
        description="Automatically recompute the tessellation when the frame is changed. Currently is not working during  Render Animation",
        default = False,
        update = set_tessellate_handler
        )
    zscale : FloatProperty(
        name="Scale", default=1, soft_min=0, soft_max=10,
        description="Scale factor for the component thickness",
        update = anim_tessellate_active
        )
    scale_mode : EnumProperty(
        items=(
                ('CONSTANT', "Constant", "Uniform thinkness"),
                ('ADAPTIVE', "Relative", "Preserve component's proportions")
                ),
        default='ADAPTIVE',
        name="Z-Scale according to faces size",
        update = anim_tessellate_active
        )
    offset : FloatProperty(
        name="Surface Offset",
        default=1,
        min=-1,
        max=1,
        soft_min=-1,
        soft_max=1,
        description="Surface offset",
        update = anim_tessellate_active
        )
    mode : EnumProperty(
        items=(
            ('BOUNDS', "Bounds", "The component fits automatically the size of the target face"),
            ('LOCAL', "Local", "Based on Local coordinates, from 0 to 1"),
            ('GLOBAL', 'Global', "Based on Global coordinates, from 0 to 1")),
        default='BOUNDS',
        name="Component Mode",
        update = anim_tessellate_active
        )
    rotation_mode : EnumProperty(
        items=(('RANDOM', "Random", "Random faces rotation"),
               ('UV', "Active UV", "Rotate according to UV coordinates"),
               ('WEIGHT', "Active Weight", "Rotate according to Vertex Group gradient"),
               ('DEFAULT', "Default", "Default rotation")),
        default='DEFAULT',
        name="Component Rotation",
        update = anim_tessellate_active
        )
    rotation_direction : EnumProperty(
        items=(('ORTHO', "Orthogonal", "Component main directions in XY"),
               ('DIAG', "Diagonal", "Component main direction aligned with diagonal")),
        default='ORTHO',
        name="Direction",
        update = anim_tessellate_active
        )
    rotation_shift : IntProperty(
        name="Shift",
        default=0,
        soft_min=0,
        soft_max=3,
        description="Shift components rotation",
        update = anim_tessellate_active
        )
    fill_mode : EnumProperty(
        items=(
            ('QUAD', 'Quad', 'Regular quad tessellation. Uses only 3 or 4 vertices'),
            ('FAN', 'Fan', 'Radial tessellation for polygonal faces'),
            ('PATCH', 'Patch', 'Curved tessellation according to the last ' +
            'Subsurf\n(or Multires) modifiers. Works only with 4 sides ' +
            'patches.\nAfter the last Subsurf (or Multires) only ' +
            'deformation\nmodifiers can be used'),
            ('FRAME', 'Frame', 'Essellation along the edges of each face')),
        default='QUAD',
        name="Fill Mode",
        update = anim_tessellate_active
        )
    combine_mode : EnumProperty(
        items=(
            ('LAST', 'Last', 'Show only the last iteration'),
            ('UNUSED', 'Unused', 'Combine each iteration with the unused faces of the previous iteration. Used for branching systems'),
            ('ALL', 'All', 'Combine the result of all iterations')),
        default='LAST',
        name="Combine Mode",
        update = anim_tessellate_active
        )
    gen_modifiers : BoolProperty(
        name="Generator Modifiers",
        default=False,
        description="Apply Modifiers and Shape Keys to the base object",
        update = anim_tessellate_active
        )
    com_modifiers : BoolProperty(
        name="Component Modifiers",
        default=False,
        description="Apply Modifiers and Shape Keys to the component object",
        update = anim_tessellate_active
        )
    merge : BoolProperty(
        name="Merge",
        default=False,
        description="Merge vertices in adjacent duplicates",
        update = anim_tessellate_active
        )
    merge_thres : FloatProperty(
        name="Distance",
        default=0.001,
        soft_min=0,
        soft_max=10,
        description="Limit below which to merge vertices",
        update = anim_tessellate_active
        )
    generator : PointerProperty(
        type=bpy.types.Object,
        name="",
        description="Base object for the tessellation",
        update = anim_tessellate_active
        )
    component : PointerProperty(
        type=bpy.types.Object,
        name="",
        description="Component object for the tessellation",
        #default="",
        update = anim_tessellate_active
        )
    bool_random : BoolProperty(
        name="Randomize",
        default=False,
        description="Randomize component rotation",
        update = anim_tessellate_active
        )
    random_seed : IntProperty(
        name="Seed",
        default=0,
        soft_min=0,
        soft_max=10,
        description="Random seed",
        update = anim_tessellate_active
        )
    bool_vertex_group : BoolProperty(
        name="Map Vertex Group",
        default=False,
        description="Transfer all Vertex Groups from Base object",
        update = anim_tessellate_active
        )
    bool_selection : BoolProperty(
        name="On selected Faces",
        default=False,
        description="Create Tessellation only on selected faces",
        update = anim_tessellate_active
        )
    bool_shapekeys : BoolProperty(
        name="Use Shape Keys",
        default=False,
        description="Transfer Component's Shape Keys. If the name of Vertex "
                    "Groups and Shape Keys are the same, they will be "
                    "automatically combined",
        update = anim_tessellate_active
        )
    bool_smooth : BoolProperty(
        name="Smooth Shading",
        default=False,
        description="Output faces with smooth shading rather than flat shaded",
        update = anim_tessellate_active
        )
    bool_materials : BoolProperty(
        name="Transfer Materials",
        default=False,
        description="Preserve component's materials",
        update = anim_tessellate_active
        )
    bool_material_id : BoolProperty(
        name="Tessellation on Material ID",
        default=False,
        description="Apply the component only on the selected Material",
        update = anim_tessellate_active
        )
    material_id : IntProperty(
        name="Material ID",
        default=0,
        min=0,
        description="Material ID",
        update = anim_tessellate_active
        )
    bool_dissolve_seams : BoolProperty(
        name="Dissolve Seams",
        default=False,
        description="Dissolve all seam edges",
        update = anim_tessellate_active
        )
    iterations : IntProperty(
        name="Iterations",
        default=1,
        min=1,
        soft_max=5,
        description="Automatically repeat the Tessellation using the "
                    + "generated geometry as new base object.\nUsefull for "
                    + "for branching systems. Dangerous!",
        update = anim_tessellate_active
        )
    bool_combine : BoolProperty(
        name="Combine unused",
        default=False,
        description="Combine the generated geometry with unused faces",
        update = anim_tessellate_active
        )
    bool_advanced : BoolProperty(
        name="Advanced Settings",
        default=False,
        description="Show more settings"
        )
    normals_mode : EnumProperty(
        items=(
            ('VERTS', 'Normals', 'Consistent direction based on vertices normal'),
            ('FACES', 'Individual Faces', 'Based on individual faces normal'),
            ('CUSTOM', 'Custom', "According to Base object's shape keys")),
        default='VERTS',
        name="Direction",
        update = anim_tessellate_active
        )
    bool_multi_components : BoolProperty(
        name="Multi Components",
        default=False,
        description="Combine different components according to materials name",
        update = anim_tessellate_active
        )
    error_message : StringProperty(
        name="Error Message",
        default=""
        )
    warning_message : StringProperty(
        name="Warning Message",
        default=""
        )
    bounds_x : EnumProperty(
            items=(
                ('EXTEND', 'Extend', 'Default X coordinates'),
                ('CLIP', 'Clip', 'Trim out of bounds in X direction'),
                ('CYCLIC', 'Cyclic', 'Cyclic components in X direction')),
            default='EXTEND',
            name="Bounds X",
            update = anim_tessellate_active
            )
    bounds_y : EnumProperty(
            items=(
                ('EXTEND', 'Extend', 'Default Y coordinates'),
                ('CLIP', 'Clip', 'Trim out of bounds in Y direction'),
                ('CYCLIC', 'Cyclic', 'Cyclic components in Y direction')),
            default='EXTEND',
            name="Bounds Y",
            update = anim_tessellate_active
            )
    close_mesh : EnumProperty(
            items=(
                ('NONE', 'None', 'Keep the mesh open'),
                ('CAP', 'Cap Holes', 'Automatically cap open loops'),
                ('BRIDGE', 'Bridge Loops', 'Automatically bridge loop pairs')),
            default='NONE',
            name="Close Mesh",
            update = anim_tessellate_active
            )
    cap_faces : BoolProperty(
            name="Cap Holes",
            default=False,
            description="Cap open edges loops",
            update = anim_tessellate_active
            )
    frame_boundary : BoolProperty(
            name="Frame Boundary",
            default=False,
            description="Support face boundaries",
            update = anim_tessellate_active
            )
    fill_frame : BoolProperty(
            name="Fill Frame",
            default=False,
            description="Fill inner faces with Fan tessellation",
            update = anim_tessellate_active
            )
    frame_boundary_mat : IntProperty(
            name="Material Offset",
            default=0,
            description="Material Offset for boundaries",
            update = anim_tessellate_active
            )
    fill_frame_mat : IntProperty(
            name="Material Offset",
            default=0,
            description="Material Offset for inner faces",
            update = anim_tessellate_active
            )
    open_edges_crease : FloatProperty(
            name="Open Edges Crease",
            default=0,
            min=0,
            max=1,
            description="Automatically set crease for open edges",
            update = anim_tessellate_active
            )
    bridge_smoothness : FloatProperty(
            name="Smoothness",
            default=1,
            min=0,
            max=1,
            description="Bridge Smoothness",
            update = anim_tessellate_active
            )
    frame_thickness : FloatProperty(
            name="Frame Thickness",
            default=0.2,
            min=0,
            soft_max=2,
            description="Frame Thickness",
            update = anim_tessellate_active
            )
    frame_mode : EnumProperty(
            items=(
                ('CONSTANT', 'Constant', 'Even thickness'),
                ('RELATIVE', 'Relative', 'Frame offset depends on face areas')),
            default='CONSTANT',
            name="Offset",
            update = anim_tessellate_active
            )
    bridge_cuts : IntProperty(
            name="Cuts",
            default=0,
            min=0,
            max=20,
            description="Bridge Cuts",
            update = anim_tessellate_active
            )
    cap_material_index : IntProperty(
            name="Material",
            default=0,
            min=0,
            description="Material index for the cap/bridge faces",
            update = anim_tessellate_active
            )
    patch_subs : IntProperty(
            name="Patch Subdivisions",
            default=1,
            min=0,
            description="Subdivisions levels for Patch tessellation after the first iteration",
            update = anim_tessellate_active
            )

def store_parameters(operator, ob):
    ob.tissue_tessellate.bool_hold = True
    ob.tissue_tessellate.bool_lock = operator.bool_lock
    ob.tissue_tessellate.bool_dependencies = operator.bool_dependencies
    ob.tissue_tessellate.generator = bpy.data.objects[operator.generator]
    ob.tissue_tessellate.component = bpy.data.objects[operator.component]
    ob.tissue_tessellate.zscale = operator.zscale
    ob.tissue_tessellate.offset = operator.offset
    ob.tissue_tessellate.gen_modifiers = operator.gen_modifiers
    ob.tissue_tessellate.com_modifiers = operator.com_modifiers
    ob.tissue_tessellate.mode = operator.mode
    ob.tissue_tessellate.rotation_mode = operator.rotation_mode
    ob.tissue_tessellate.rotation_shift = operator.rotation_shift
    ob.tissue_tessellate.rotation_direction = operator.rotation_direction
    ob.tissue_tessellate.merge = operator.merge
    ob.tissue_tessellate.merge_thres = operator.merge_thres
    ob.tissue_tessellate.scale_mode = operator.scale_mode
    ob.tissue_tessellate.bool_random = operator.bool_random
    ob.tissue_tessellate.random_seed = operator.random_seed
    ob.tissue_tessellate.fill_mode = operator.fill_mode
    ob.tissue_tessellate.bool_vertex_group = operator.bool_vertex_group
    ob.tissue_tessellate.bool_selection = operator.bool_selection
    ob.tissue_tessellate.bool_shapekeys = operator.bool_shapekeys
    ob.tissue_tessellate.bool_smooth = operator.bool_smooth
    ob.tissue_tessellate.bool_materials = operator.bool_materials
    ob.tissue_tessellate.bool_material_id = operator.bool_material_id
    ob.tissue_tessellate.material_id = operator.material_id
    ob.tissue_tessellate.bool_dissolve_seams = operator.bool_dissolve_seams
    ob.tissue_tessellate.iterations = operator.iterations
    ob.tissue_tessellate.bool_advanced = operator.bool_advanced
    ob.tissue_tessellate.normals_mode = operator.normals_mode
    ob.tissue_tessellate.bool_combine = operator.bool_combine
    ob.tissue_tessellate.bool_multi_components = operator.bool_multi_components
    ob.tissue_tessellate.combine_mode = operator.combine_mode
    ob.tissue_tessellate.bounds_x = operator.bounds_x
    ob.tissue_tessellate.bounds_y = operator.bounds_y
    ob.tissue_tessellate.cap_faces = operator.cap_faces
    ob.tissue_tessellate.close_mesh = operator.close_mesh
    ob.tissue_tessellate.bridge_cuts = operator.bridge_cuts
    ob.tissue_tessellate.bridge_smoothness = operator.bridge_smoothness
    ob.tissue_tessellate.frame_thickness = operator.frame_thickness
    ob.tissue_tessellate.frame_mode = operator.frame_mode
    ob.tissue_tessellate.frame_boundary = operator.frame_boundary
    ob.tissue_tessellate.fill_frame = operator.fill_frame
    ob.tissue_tessellate.frame_boundary_mat = operator.frame_boundary_mat
    ob.tissue_tessellate.fill_frame_mat = operator.fill_frame_mat
    ob.tissue_tessellate.cap_material_index = operator.cap_material_index
    ob.tissue_tessellate.patch_subs = operator.patch_subs
    ob.tissue_tessellate.bool_hold = False
    return ob

def load_parameters(operator, ob):
    operator.bool_lock = ob.tissue_tessellate.bool_lock
    operator.bool_dependencies = ob.tissue_tessellate.bool_dependencies
    operator.generator = ob.tissue_tessellate.generator.name
    operator.component = ob.tissue_tessellate.component.name
    operator.zscale = ob.tissue_tessellate.zscale
    operator.offset = ob.tissue_tessellate.offset
    operator.gen_modifiers = ob.tissue_tessellate.gen_modifiers
    operator.com_modifiers = ob.tissue_tessellate.com_modifiers
    operator.mode = ob.tissue_tessellate.mode
    operator.rotation_mode = ob.tissue_tessellate.rotation_mode
    operator.rotation_shift = ob.tissue_tessellate.rotation_shift
    operator.rotation_direction = ob.tissue_tessellate.rotation_direction
    operator.merge = ob.tissue_tessellate.merge
    operator.merge_thres = ob.tissue_tessellate.merge_thres
    operator.scale_mode = ob.tissue_tessellate.scale_mode
    operator.bool_random = ob.tissue_tessellate.bool_random
    operator.random_seed = ob.tissue_tessellate.random_seed
    operator.fill_mode = ob.tissue_tessellate.fill_mode
    operator.bool_vertex_group = ob.tissue_tessellate.bool_vertex_group
    operator.bool_selection = ob.tissue_tessellate.bool_selection
    operator.bool_shapekeys = ob.tissue_tessellate.bool_shapekeys
    operator.bool_smooth = ob.tissue_tessellate.bool_smooth
    operator.bool_materials = ob.tissue_tessellate.bool_materials
    operator.bool_material_id = ob.tissue_tessellate.bool_material_id
    operator.material_id = ob.tissue_tessellate.material_id
    operator.bool_dissolve_seams = ob.tissue_tessellate.bool_dissolve_seams
    operator.iterations = ob.tissue_tessellate.iterations
    operator.bool_advanced = ob.tissue_tessellate.bool_advanced
    operator.normals_mode = ob.tissue_tessellate.normals_mode
    operator.bool_combine = ob.tissue_tessellate.bool_combine
    operator.bool_multi_components = ob.tissue_tessellate.bool_multi_components
    operator.combine_mode = ob.tissue_tessellate.combine_mode
    operator.bounds_x = ob.tissue_tessellate.bounds_x
    operator.bounds_y = ob.tissue_tessellate.bounds_y
    operator.cap_faces = ob.tissue_tessellate.cap_faces
    operator.close_mesh = ob.tissue_tessellate.close_mesh
    operator.bridge_cuts = ob.tissue_tessellate.bridge_cuts
    operator.bridge_smoothness = ob.tissue_tessellate.bridge_smoothness
    operator.cap_material_index = ob.tissue_tessellate.cap_material_index
    operator.patch_subs = ob.tissue_tessellate.patch_subs
    operator.frame_boundary = ob.tissue_tessellate.frame_boundary
    operator.fill_frame = ob.tissue_tessellate.fill_frame
    operator.frame_boundary_mat = ob.tissue_tessellate.frame_boundary_mat
    operator.fill_frame_mat = ob.tissue_tessellate.fill_frame_mat
    operator.frame_thickness = ob.tissue_tessellate.frame_thickness
    operator.frame_mode = ob.tissue_tessellate.frame_mode
    return ob

def tessellate_patch(_ob0, _ob1, offset, zscale, com_modifiers, mode,
               scale_mode, rotation_mode, rotation_shift, rand_seed, bool_vertex_group,
               bool_selection, bool_shapekeys, bool_material_id, material_id,
               normals_mode, bounds_x, bounds_y):
    random.seed(rand_seed)

    if normals_mode == 'CUSTOM':
        if _ob0.data.shape_keys != None:
            ob0_sk = convert_object_to_mesh(_ob0)
            me0_sk = ob0_sk.data
            key_values0 = [sk.value for sk in _ob0.data.shape_keys.key_blocks]
            for sk in _ob0.data.shape_keys.key_blocks: sk.value = 0
        else: normals_mode = 'VERTS'

    ob0 = convert_object_to_mesh(_ob0)
    me0 = ob0.data

    # base normals
    normals0 = []
    if normals_mode == 'CUSTOM':
        for sk, val in zip(_ob0.data.shape_keys.key_blocks, key_values0): sk.value = val
        for v0, v1 in zip(ob0.data.vertices, me0_sk.vertices):
            normals0.append(v1.co - v0.co)
        bpy.data.objects.remove(ob0_sk)
    else:
        ob0.data.update()
        normals0 = [v.normal for v in ob0.data.vertices]

#    ob0 = convert_object_to_mesh(_ob0)
    ob0.name = _ob0.name + "_apply_mod"
    me0 = _ob0.data

    # Check if zero faces are selected
    if _ob0.type == 'MESH':
        bool_cancel = True
        for p in me0.polygons:
            check_sel = check_mat = False
            if not bool_selection or p.select: check_sel = True
            if not bool_material_id or p.material_index == material_id: check_mat = True
            if check_sel and check_mat:
                    bool_cancel = False
                    break
        if bool_cancel:
            bpy.data.meshes.remove(ob0.data)
            #bpy.data.objects.remove(ob0)
            return 0

    levels = 0
    sculpt_levels = 0
    render_levels = 0
    bool_multires = False
    multires_name = ""
    not_allowed  = ['FLUID_SIMULATION', 'ARRAY', 'BEVEL', 'BOOLEAN', 'BUILD',
                    'DECIMATE', 'EDGE_SPLIT', 'MASK', 'MIRROR', 'REMESH',
                    'SCREW', 'SOLIDIFY', 'TRIANGULATE', 'WIREFRAME', 'SKIN',
                    'EXPLODE', 'PARTICLE_INSTANCE', 'PARTICLE_SYSTEM', 'SMOKE']
    modifiers0 = list(_ob0.modifiers)#[m for m in ob0.modifiers]
    show_modifiers = [m.show_viewport for m in _ob0.modifiers]
    show_modifiers.reverse()
    modifiers0.reverse()
    for m in modifiers0:
        visible = m.show_viewport
        if not visible: continue
        #m.show_viewport = False
        if m.type in ('SUBSURF', 'MULTIRES') and visible:
            levels = m.levels
            multires_name = m.name
            if m.type == 'MULTIRES':
                bool_multires = True
                multires_name = m.name
                sculpt_levels = m.sculpt_levels
                render_levels = m.render_levels
            else: bool_multires = False
            break
        elif m.type in not_allowed:
            bpy.data.meshes.remove(ob0.data)
            #bpy.data.meshes.remove(me0)
            return "modifiers_error"

    before = _ob0.copy()
    before.name = _ob0.name + "_before_subs"
    bpy.context.collection.objects.link(before)
    #if ob0.type == 'MESH': before.data = me0
    before_mod = list(before.modifiers)
    before_mod.reverse()
    for m in before_mod:
        if m.type in ('SUBSURF', 'MULTIRES') and m.show_viewport:
            before.modifiers.remove(m)
            break
        else: before.modifiers.remove(m)

    before_subsurf = simple_to_mesh(before)

    before_bm = bmesh.new()
    before_bm.from_mesh(before_subsurf)
    before_bm.faces.ensure_lookup_table()
    before_bm.edges.ensure_lookup_table()
    before_bm.verts.ensure_lookup_table()

    error = ""
    for f in before_bm.faces:
        if len(f.loops) != 4:
            error = "topology_error"
            break
    for e in before_bm.edges:
        if len(e.link_faces) == 0:
            error = "wires_error"
            break
    for v in before_bm.verts:
        if len(v.link_faces) == 0:
            error = "verts_error"
            break
    if error != "":
        bpy.data.meshes.remove(ob0.data)
        #bpy.data.meshes.remove(me0)
        bpy.data.meshes.remove(before_subsurf)
        bpy.data.objects.remove(before)
        return error

    me0 = ob0.data
    verts0 = me0.vertices   # Collect generator vertices

    if com_modifiers or _ob1.type != 'MESH': bool_shapekeys = False

    # set Shape Keys to zero
    if bool_shapekeys or not com_modifiers:
        try:
            original_key_values = []
            for sk in _ob1.data.shape_keys.key_blocks:
                original_key_values.append(sk.value)
                sk.value = 0
        except:
            bool_shapekeys = False

    if not com_modifiers and not bool_shapekeys:
        mod_visibility = []
        for m in _ob1.modifiers:
            mod_visibility.append(m.show_viewport)
            m.show_viewport = False
        com_modifiers = True

    ob1 = convert_object_to_mesh(_ob1, com_modifiers, False)
    me1 = ob1.data

    if mode != 'BOUNDS':
        ob1.active_shape_key_index = 0
        # Bound X
        if bounds_x != 'EXTEND':
            if mode == 'GLOBAL':
                planes_co = ((0,0,0),(1,1,1))
                plane_no = (1,0,0)
            if mode == 'LOCAL':
                planes_co = (ob1.matrix_world @ Vector((0,0,0)), ob1.matrix_world @ Vector((1,0,0)))
                plane_no = planes_co[0]-planes_co[1]
            bpy.ops.object.mode_set(mode='EDIT')
            for co in planes_co:
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.bisect(plane_co=co, plane_no=plane_no)
                bpy.ops.mesh.mark_seam()
            bpy.ops.object.mode_set(mode='OBJECT')
            _faces = ob1.data.polygons
            if mode == 'GLOBAL':
                for f in [f for f in _faces if (ob1.matrix_world @ f.center).x > 1]:
                    f.select = True
                for f in [f for f in _faces if (ob1.matrix_world @ f.center).x < 0]:
                    f.select = True
            else:
                for f in [f for f in _faces if f.center.x > 1]:
                    f.select = True
                for f in [f for f in _faces if f.center.x < 0]:
                    f.select = True
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='FACE')
            if bounds_x == 'CLIP':
                bpy.ops.mesh.delete(type='FACE')
                bpy.ops.object.mode_set(mode='OBJECT')
            if bounds_x == 'CYCLIC':
                bpy.ops.mesh.split()
                bpy.ops.object.mode_set(mode='OBJECT')
        # Bound Y
        if bounds_y != 'EXTEND':
            if mode == 'GLOBAL':
                planes_co = ((0,0,0),(1,1,1))
                plane_no = (0,1,0)
            if mode == 'LOCAL':
                planes_co = (ob1.matrix_world @ Vector((0,0,0)), ob1.matrix_world @ Vector((0,1,0)))
                plane_no = planes_co[0]-planes_co[1]
            bpy.ops.object.mode_set(mode='EDIT')
            for co in planes_co:
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.bisect(plane_co=co, plane_no=plane_no)
                bpy.ops.mesh.mark_seam()
            bpy.ops.object.mode_set(mode='OBJECT')
            _faces = ob1.data.polygons
            if mode == 'GLOBAL':
                for f in [f for f in _faces if (ob1.matrix_world @ f.center).y > 1]:
                    f.select = True
                for f in [f for f in _faces if (ob1.matrix_world @ f.center).y < 0]:
                    f.select = True
            else:
                for f in [f for f in _faces if f.center.y > 1]:
                    f.select = True
                for f in [f for f in _faces if f.center.y < 0]:
                    f.select = True

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='FACE')
            if bounds_y == 'CLIP':
                bpy.ops.mesh.delete(type='FACE')
                bpy.ops.object.mode_set(mode='OBJECT')
            if bounds_y == 'CYCLIC':
                bpy.ops.mesh.split()
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='OBJECT')

    # Component statistics
    n_verts = len(me1.vertices)

    # Create empty lists
    new_verts = []
    new_edges = []
    new_faces = []
    new_verts_np = np.array(())

    # Component bounding box
    min_c = Vector((0, 0, 0))
    max_c = Vector((0, 0, 0))
    first = True
    for v in me1.vertices:
        vert = v.co
        if vert[0] < min_c[0] or first:
            min_c[0] = vert[0]
        if vert[1] < min_c[1] or first:
            min_c[1] = vert[1]
        if vert[2] < min_c[2] or first:
            min_c[2] = vert[2]
        if vert[0] > max_c[0] or first:
            max_c[0] = vert[0]
        if vert[1] > max_c[1] or first:
            max_c[1] = vert[1]
        if vert[2] > max_c[2] or first:
            max_c[2] = vert[2]
        first = False
    bb = max_c - min_c

    # adaptive XY
    verts1 = []
    for v in me1.vertices:
        if mode == 'BOUNDS':
            vert = v.co - min_c  # (ob1.matrix_world * v.co) - min_c
            vert[0] = vert[0] / bb[0] if bb[0] != 0 else 0.5
            vert[1] = vert[1] / bb[1] if bb[1] != 0 else 0.5
            vert[2] = vert[2] / bb[2] if bb[2] != 0 else 0
            vert[2] = (vert[2] - 0.5 + offset * 0.5) * zscale
        elif mode == 'LOCAL':
            vert = v.co.xyz
            vert[2] *= zscale
            #vert[2] = (vert[2] - min_c[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
        elif mode == 'GLOBAL':
            vert = ob1.matrix_world @ v.co
            vert[2] *= zscale
            try:
                for sk in me1.shape_keys.key_blocks:
                    sk.data[v.index].co = ob1.matrix_world @ sk.data[v.index].co
            except: pass
        #verts1.append(vert)
        v.co = vert

    # Bounds X, Y
    if mode != 'BOUNDS':
        if bounds_x == 'CYCLIC':
            move_verts = []
            for f in [f for f in me1.polygons if (f.center).x > 1]:
                for v in f.vertices:
                    if v not in move_verts: move_verts.append(v)
            for v in move_verts:
                me1.vertices[v].co.x -= 1
                try:
                    _ob1.active_shape_key_index = 0
                    for sk in me1.shape_keys.key_blocks:
                        sk.data[v].co.x -= 1
                except: pass
            move_verts = []
            for f in [f for f in me1.polygons if (f.center).x < 0]:
                for v in f.vertices:
                    if v not in move_verts: move_verts.append(v)
            for v in move_verts:
                me1.vertices[v].co.x += 1
                try:
                    _ob1.active_shape_key_index = 0
                    for sk in me1.shape_keys.key_blocks:
                        sk.data[v].co.x += 1
                except: pass
        if bounds_y == 'CYCLIC':
            move_verts = []
            for f in [f for f in me1.polygons if (f.center).y > 1]:
                for v in f.vertices:
                    if v not in move_verts: move_verts.append(v)
            for v in move_verts:
                me1.vertices[v].co.y -= 1
                try:
                    _ob1.active_shape_key_index = 0
                    for sk in me1.shape_keys.key_blocks:
                        sk.data[v].co.y -= 1
                except: pass
            move_verts = []
            for f in [f for f in me1.polygons if (f.center).y < 0]:
                for v in f.vertices:
                    if v not in move_verts: move_verts.append(v)
            for v in move_verts:
                me1.vertices[v].co.y += 1
                try:
                    _ob1.active_shape_key_index = 0
                    for sk in me1.shape_keys.key_blocks:
                        sk.data[v].co.y += 1
                except: pass
    verts1 = [v.co for v in me1.vertices]
    n_verts1 = len(verts1)

    patch_faces = 4**levels
    sides = int(sqrt(patch_faces))
    step = 1/sides
    sides0 = sides-2
    patch_faces0 = int((sides-2)**2)
    n_patches = int(len(me0.polygons)/patch_faces)
    if len(me0.polygons)%patch_faces != 0:
        #ob0.data = old_me0
        return "topology_error"

    new_verts = []
    new_edges = []
    new_faces = []

    for o in bpy.context.view_layer.objects: o.select_set(False)
    new_patch = None

    # All vertex group
    if bool_vertex_group:
        try:
            weight = []
            for vg in ob0.vertex_groups:
                _weight = []
                for v in me0.vertices:
                    try:
                        _weight.append(vg.weight(v.index))
                    except:
                        _weight.append(0)
                weight.append(_weight)
        except:
            bool_vertex_group = False

    # Adaptive Z
    if scale_mode == 'ADAPTIVE':
        com_area = bb[0]*bb[1]
        if mode != 'BOUNDS' or com_area == 0: com_area = 1
        #mult = 1/com_area
        verts_area = []
        bm = bmesh.new()
        bm.from_mesh(me0)
        bm.verts.ensure_lookup_table()
        for v in bm.verts:
            area = 0
            faces = v.link_faces
            for f in faces:
                area += f.calc_area()
            area = area/len(faces)*patch_faces/com_area
            #area*=mult*
            verts_area.append(sqrt(area)*bb[2])

    random.seed(rand_seed)
    bool_correct = False

    _faces = [[[0] for ii in range(sides)] for jj in range(sides)]
    _verts = [[[0] for ii in range(sides+1)] for jj in range(sides+1)]

    # find relative UV component's vertices
    verts1_uv_quads = [0]*len(verts1)
    verts1_uv = [0]*len(verts1)
    for i, vert in enumerate(verts1):
        # grid coordinates
        u = int(vert[0]//step)
        v = int(vert[1]//step)
        u1 = min(u+1, sides)
        v1 = min(v+1, sides)
        if mode != 'BOUNDS':
            if u > sides-1:
                u = sides-1
                u1 = sides
            if u < 0:
                u = 0
                u1 = 1
            if v > sides-1:
                v = sides-1
                v1 = sides
            if v < 0:
                v = 0
                v1 = 1
        verts1_uv_quads[i] = (u,v,u1,v1)
        # factor coordinates
        fu = (vert[0]-u*step)/step
        fv = (vert[1]-v*step)/step
        fw = vert.z
        # interpolate Z scaling factor
        verts1_uv[i] = Vector((fu,fv,fw))

    sk_uv_quads = []
    sk_uv = []
    if bool_shapekeys:
        for sk in ob1.data.shape_keys.key_blocks:
            source = sk.data
            _sk_uv_quads = [0]*len(verts1)
            _sk_uv = [0]*len(verts1)
            for i, sk_v in enumerate(source):
                if mode == 'BOUNDS':
                    sk_vert = sk_v.co - min_c
                    sk_vert[0] = (sk_vert[0] / bb[0] if bb[0] != 0 else 0.5)
                    sk_vert[1] = (sk_vert[1] / bb[1] if bb[1] != 0 else 0.5)
                    sk_vert[2] = (sk_vert[2] / bb[2] if bb[2] != 0 else sk_vert[2])
                    sk_vert[2] = (sk_vert[2] - 0.5 + offset * 0.5) * zscale
                elif mode == 'LOCAL':
                    sk_vert = sk_v.co
                    sk_vert[2] *= zscale
                elif mode == 'GLOBAL':
                    sk_vert = sk_v.co
                    sk_vert[2] *= zscale

                # grid coordinates
                u = int(sk_vert[0]//step)
                v = int(sk_vert[1]//step)
                u1 = min(u+1, sides)
                v1 = min(v+1, sides)
                if mode != 'BOUNDS':
                    if u > sides-1:
                        u = sides-1
                        u1 = sides
                    if u < 0:
                        u = 0
                        u1 = 1
                    if v > sides-1:
                        v = sides-1
                        v1 = sides
                    if v < 0:
                        v = 0
                        v1 = 1
                _sk_uv_quads[i] = (u,v,u1,v1)
                # factor coordinates
                fu = (sk_vert[0]-u*step)/step
                fv = (sk_vert[1]-v*step)/step
                fw = sk_vert.z
                _sk_uv[i] = Vector((fu,fv,fw))
            sk_uv_quads.append(_sk_uv_quads)
            sk_uv.append(_sk_uv)

    for i in range(n_patches):
        poly = me0.polygons[i*patch_faces]
        if bool_selection and not poly.select: continue
        if bool_material_id and not poly.material_index == material_id: continue

        bool_correct = True
        new_patch = bpy.data.objects.new("patch", me1.copy())
        bpy.context.collection.objects.link(new_patch)

        new_patch.select_set(True)
        bpy.context.view_layer.objects.active = new_patch

        for area in bpy.context.screen.areas:
            for space in area.spaces:
                try: new_patch.local_view_set(space, True)
                except: pass

        # Vertex Group
        if bool_vertex_group:
            for vg in ob0.vertex_groups:
                new_patch.vertex_groups.new(name=vg.name)

        # find patch faces
        faces = _faces.copy()
        verts = _verts.copy()
        shift1 = sides
        shift2 = sides*2-1
        shift3 = sides*3-2
        for j in range(patch_faces):
            if j < patch_faces0:
                if levels == 0:
                    u = j%sides0
                    v = j//sides0
                else:
                    u = j%sides0+1
                    v = j//sides0+1
            elif j < patch_faces0 + shift1:
                u = j-patch_faces0
                v = 0
            elif j < patch_faces0 + shift2:
                u = sides-1
                v = j-(patch_faces0 + sides)+1
            elif j < patch_faces0 + shift3:
                jj = j-(patch_faces0 + shift2)
                u = sides-jj-2
                v = sides-1
            else:
                jj = j-(patch_faces0 + shift3)
                u = 0
                v = sides-jj-2
            face = me0.polygons[j+i*patch_faces]
            faces[u][v] = face
            verts[u][v] = verts0[face.vertices[0]]
            if u == sides-1:
                verts[sides][v] = verts0[face.vertices[1]]
            if v == sides-1:
                verts[u][sides] = verts0[face.vertices[3]]
            if u == v == sides-1:
                verts[sides][sides] = verts0[face.vertices[2]]

        # Random rotation
        if rotation_mode == 'RANDOM' or rotation_shift != 0:
            if rotation_mode == 'RANDOM': rot = random.randint(0, 3)
            else: rot = rotation_shift%4
            if rot == 1:
                verts = [[verts[w][k] for w in range(sides+1)] for k in range(sides,-1,-1)]
            elif rot == 2:
                verts = [[verts[k][w] for w in range(sides,-1,-1)] for k in range(sides,-1,-1)]
            elif rot == 3:
                verts = [[verts[w][k] for w in range(sides,-1,-1)] for k in range(sides+1)]

        # UV rotation
        if rotation_mode == 'UV' and ob0.type == 'MESH':
            if len(ob0.data.uv_layers) > 0:
                uv0 = me0.uv_layers.active.data[faces[0][0].index*4].uv
                uv1 = me0.uv_layers.active.data[faces[0][-1].index*4 + 3].uv
                uv2 = me0.uv_layers.active.data[faces[-1][-1].index*4 + 2].uv
                uv3 = me0.uv_layers.active.data[faces[-1][0].index*4 + 1].uv
                v01 = (uv0 + uv1)
                v32 = (uv3 + uv2)
                v0132 = v32 - v01
                v0132.normalize()
                v12 = (uv1 + uv2)
                v03 = (uv0 + uv3)
                v1203 = v03 - v12
                v1203.normalize()

                vertUV = []
                dot1203 = v1203.x
                dot0132 = v0132.x
                if(abs(dot1203) < abs(dot0132)):
                    if (dot0132 > 0):
                        pass
                    else:
                        verts = [[verts[k][w] for w in range(sides,-1,-1)] for k in range(sides,-1,-1)]
                else:
                    if(dot1203 < 0):
                        verts = [[verts[w][k] for w in range(sides,-1,-1)] for k in range(sides+1)]
                    else:
                        verts = [[verts[w][k] for w in range(sides+1)] for k in range(sides,-1,-1)]

        if True:
            verts_xyz = np.array([[v.co for v in _verts] for _verts in verts])
            #verts_norm = np.array([[v.normal for v in _verts] for _verts in verts])
            verts_norm = np.array([[normals0[v.index] for v in _verts] for _verts in verts])
            if normals_mode == 'FACES':
                verts_norm = np.mean(verts_norm, axis=(0,1))
                verts_norm = np.expand_dims(verts_norm, axis=0)
                verts_norm = np.repeat(verts_norm,len(verts),axis=0)
                verts_norm = np.expand_dims(verts_norm, axis=0)
                verts_norm = np.repeat(verts_norm,len(verts),axis=0)
            np_verts1_uv = np.array(verts1_uv)
            verts1_uv_quads = np.array(verts1_uv_quads)
            u = verts1_uv_quads[:,0]
            v = verts1_uv_quads[:,1]
            u1 = verts1_uv_quads[:,2]
            v1 = verts1_uv_quads[:,3]
            v00 = verts_xyz[u,v]
            v10 = verts_xyz[u1,v]
            v01 = verts_xyz[u,v1]
            v11 = verts_xyz[u1,v1]
            n00 = verts_norm[u,v]
            n10 = verts_norm[u1,v]
            n01 = verts_norm[u,v1]
            n11 = verts_norm[u1,v1]
            vx = np_verts1_uv[:,0].reshape((n_verts1,1))
            vy = np_verts1_uv[:,1].reshape((n_verts1,1))
            vz = np_verts1_uv[:,2].reshape((n_verts1,1))
            co2 = np_lerp2(v00,v10,v01,v11,vx,vy)
            n2 = np_lerp2(n00,n10,n01,n11,vx,vy)
            if scale_mode == 'ADAPTIVE':
                areas = np.array([[verts_area[v.index] for v in verts_v] for verts_v in verts])
                a00 = areas[u,v].reshape((n_verts1,1))
                a10 = areas[u1,v].reshape((n_verts1,1))
                a01 = areas[u,v1].reshape((n_verts1,1))
                a11 = areas[u1,v1].reshape((n_verts1,1))
                # remapped z scale
                a2 = np_lerp2(a00,a10,a01,a11,vx,vy)
                co3 = co2 + n2 * vz * a2
            else:
                co3 = co2 + n2 * vz
            coordinates = co3.flatten().tolist()
            new_patch.data.vertices.foreach_set('co',coordinates)

            # vertex groups
            if bool_vertex_group:
                for _weight, vg in zip(weight, new_patch.vertex_groups):
                    np_weight = np.array([[_weight[v.index] for v in verts_v] for verts_v in verts])
                    w00 = np_weight[u,v].reshape((n_verts1,1))
                    w10 = np_weight[u1,v].reshape((n_verts1,1))
                    w01 = np_weight[u,v1].reshape((n_verts1,1))
                    w11 = np_weight[u1,v1].reshape((n_verts1,1))
                    # remapped z scale
                    w2 = np_lerp2(w00,w10,w01,w11,vx,vy)
                    for vert_id in range(n_verts1):
                        vg.add([vert_id], w2[vert_id], "ADD")

            if bool_shapekeys:
                for i_sk, sk in enumerate(ob1.data.shape_keys.key_blocks):
                    np_verts1_uv = np.array(sk_uv[i_sk])
                    np_sk_uv_quads = np.array(sk_uv_quads[i_sk])
                    u = np_sk_uv_quads[:,0]
                    v = np_sk_uv_quads[:,1]
                    u1 = np_sk_uv_quads[:,2]
                    v1 = np_sk_uv_quads[:,3]
                    v00 = verts_xyz[u,v]
                    v10 = verts_xyz[u1,v]
                    v01 = verts_xyz[u,v1]
                    v11 = verts_xyz[u1,v1]
                    vx = np_verts1_uv[:,0].reshape((n_verts1,1))
                    vy = np_verts1_uv[:,1].reshape((n_verts1,1))
                    vz = np_verts1_uv[:,2].reshape((n_verts1,1))
                    co2 = np_lerp2(v00,v10,v01,v11,vx,vy)
                    n2 = np_lerp2(n00,n10,n01,n11,vx,vy)
                    if scale_mode == 'ADAPTIVE':
                        areas = np.array([[verts_area[v.index] for v in verts_v] for verts_v in verts])
                        a00 = areas[u,v].reshape((n_verts1,1))
                        a10 = areas[u1,v].reshape((n_verts1,1))
                        a01 = areas[u,v1].reshape((n_verts1,1))
                        a11 = areas[u1,v1].reshape((n_verts1,1))
                        # remapped z scale
                        a2 = np_lerp2(a00,a10,a01,a11,vx,vy)
                        co3 = co2 + n2 * vz * a2
                    else:
                        co3 = co2 + n2 * vz
                    coordinates = co3.flatten().tolist()
                    new_patch.data.shape_keys.key_blocks[sk.name].data.foreach_set('co', coordinates)
                    #new_patch.data.shape_keys.key_blocks[sk.name].data[i_vert].co = sk_co
        else:
            for _fvec, uv_quad, patch_vert in zip(verts1_uv, verts1_uv_quads, new_patch.data.vertices):
                u = uv_quad[0]
                v = uv_quad[1]
                u1 = uv_quad[2]
                v1 = uv_quad[3]
                v00 = verts[u][v]
                v10 = verts[u1][v]
                v01 = verts[u][v1]
                v11 = verts[u1][v1]
                # interpolate Z scaling factor
                fvec = _fvec.copy()
                if scale_mode == 'ADAPTIVE':
                    a00 = verts_area[v00.index]
                    a10 = verts_area[v10.index]
                    a01 = verts_area[v01.index]
                    a11 = verts_area[v11.index]
                    fvec[2]*=lerp2(a00,a10,a01,a11,fvec)
                # interpolate vertex on patch
                patch_vert.co = lerp3(v00, v10, v01, v11, fvec)

                # Vertex Group
                if bool_vertex_group:
                    for _weight, vg in zip(weight, new_patch.vertex_groups):
                        w00 = _weight[v00.index]
                        w10 = _weight[v10.index]
                        w01 = _weight[v01.index]
                        w11 = _weight[v11.index]
                        wuv = lerp2(w00,w10,w01,w11, fvec)
                        vg.add([patch_vert.index], wuv, "ADD")

            if bool_shapekeys:
                for i_sk, sk in enumerate(ob1.data.shape_keys.key_blocks):
                    for i_vert, _fvec, _sk_uv_quad in zip(range(len(new_patch.data.vertices)), sk_uv[i_sk], sk_uv_quads[i_sk]):
                        u = _sk_uv_quad[0]
                        v = _sk_uv_quad[1]
                        u1 = _sk_uv_quad[2]
                        v1 = _sk_uv_quad[3]
                        v00 = verts[u][v]
                        v10 = verts[u1][v]
                        v01 = verts[u][v1]
                        v11 = verts[u1][v1]

                        fvec = _fvec.copy()
                        if scale_mode == 'ADAPTIVE':
                            a00 = verts_area[v00.index]
                            a10 = verts_area[v10.index]
                            a01 = verts_area[v01.index]
                            a11 = verts_area[v11.index]
                            fvec[2]*=lerp2(a00, a10, a01, a11, fvec)
                        sk_co = lerp3(v00, v10, v01, v11, fvec)

                        new_patch.data.shape_keys.key_blocks[sk.name].data[i_vert].co = sk_co

    #if ob0.type == 'MESH': ob0.data = old_me0
    if not bool_correct: return 0

    bpy.ops.object.join()


    if bool_shapekeys:
        # set original values and combine Shape Keys and Vertex Groups
        for sk, val in zip(_ob1.data.shape_keys.key_blocks, original_key_values):
            sk.value = val
            new_patch.data.shape_keys.key_blocks[sk.name].value = val
        if bool_vertex_group:
            for sk in new_patch.data.shape_keys.key_blocks:
                for vg in new_patch.vertex_groups:
                    if sk.name == vg.name:
                        sk.vertex_group = vg.name
    else:
        try:
            for sk, val in zip(_ob1.data.shape_keys.key_blocks, original_key_values):
                sk.value = val
        except: pass

    new_name = ob0.name + "_" + ob1.name
    new_patch.name = "tessellate_temp"

    if bool_multires:
        for m in ob0.modifiers:
            if m.type == 'MULTIRES' and m.name == multires_name:
                m.levels = levels
                m.sculpt_levels = sculpt_levels
                m.render_levels = render_levels
    # restore original modifiers visibility for component object
    try:
        for m, vis in zip(_ob1.modifiers, mod_visibility):
            m.show_viewport = vis
    except: pass

    bpy.data.objects.remove(before)
    bpy.data.objects.remove(ob0)
    bpy.data.objects.remove(ob1)
    return new_patch

def tessellate_original(_ob0, _ob1, offset, zscale, gen_modifiers, com_modifiers, mode,
               scale_mode, rotation_mode, rotation_shift, rotation_direction, rand_seed, fill_mode,
               bool_vertex_group, bool_selection, bool_shapekeys,
               bool_material_id, material_id, normals_mode, bounds_x, bounds_y):

    if com_modifiers or _ob1.type != 'MESH': bool_shapekeys = False
    random.seed(rand_seed)

    if bool_shapekeys:
        try:
            original_key_values = []
            for sk in _ob1.data.shape_keys.key_blocks:
                original_key_values.append(sk.value)
                sk.value = 0
        except:
            bool_shapekeys = False

    if normals_mode == 'CUSTOM':
        if _ob0.data.shape_keys != None:
            ob0_sk = convert_object_to_mesh(_ob0, True, True)
            me0_sk = ob0_sk.data
            key_values0 = [sk.value for sk in _ob0.data.shape_keys.key_blocks]
            for sk in _ob0.data.shape_keys.key_blocks: sk.value = 0
        else: normals_mode == 'VERTS'

    ob0 = convert_object_to_mesh(_ob0, gen_modifiers, True)
    me0 = ob0.data
    ob1 = convert_object_to_mesh(_ob1, com_modifiers, True)
    me1 = ob1.data

    # base normals
    normals0 = []
    if normals_mode == 'CUSTOM' and _ob0.data.shape_keys != None:
        for sk, val in zip(_ob0.data.shape_keys.key_blocks, key_values0): sk.value = val
        for v0, v1 in zip(me0.vertices, me0_sk.vertices):
            normals0.append(v1.co - v0.co)
        bpy.data.objects.remove(ob0_sk)
    else:
        me0.update()
        normals0 = [v.normal for v in me0.vertices]

    base_polygons = []
    base_face_normals = []

    n_faces0 = len(me0.polygons)

    # Check if zero faces are selected
    if (bool_selection and ob0.type == 'MESH') or bool_material_id:
        for p in me0.polygons:
            if (bool_selection and ob0.type == 'MESH'):
                is_sel = p.select
            else: is_sel = True
            if bool_material_id:
                is_mat = p.material_index == material_id
            else: is_mat = True
            if is_sel and is_mat:
                base_polygons.append(p)
                base_face_normals.append(p.normal)
    else:
        base_polygons = me0.polygons
        base_face_normals = [p.normal for p in me0.polygons]

        # numpy test: slower
        #base_face_normals = np.zeros(n_faces0*3)
        #me0.polygons.foreach_get("normal", base_face_normals)
        #base_face_normals = base_face_normals.reshape((n_faces0,3))

    if len(base_polygons) == 0:
        bpy.data.objects.remove(ob0)
        bpy.data.objects.remove(ob1)
        bpy.data.meshes.remove(me1)
        bpy.data.meshes.remove(me0)
        return 0

    if mode != 'BOUNDS':

        bpy.ops.object.select_all(action='DESELECT')
        for o in bpy.context.view_layer.objects: o.select_set(False)
        bpy.context.view_layer.objects.active = ob1
        ob1.select_set(True)
        ob1.active_shape_key_index = 0
        # Bound X
        if bounds_x != 'EXTEND':
            if mode == 'GLOBAL':
                planes_co = ((0,0,0),(1,1,1))
                plane_no = (1,0,0)
            if mode == 'LOCAL':
                planes_co = (ob1.matrix_world @ Vector((0,0,0)), ob1.matrix_world @ Vector((1,0,0)))
                plane_no = planes_co[0]-planes_co[1]
            bpy.ops.object.mode_set(mode='EDIT')
            for co in planes_co:
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.bisect(plane_co=co, plane_no=plane_no)
                bpy.ops.mesh.mark_seam()
            bpy.ops.object.mode_set(mode='OBJECT')
            _faces = ob1.data.polygons
            if mode == 'GLOBAL':
                for f in [f for f in _faces if (ob1.matrix_world @ f.center).x > 1]:
                    f.select = True
                for f in [f for f in _faces if (ob1.matrix_world @ f.center).x < 0]:
                    f.select = True
            else:
                for f in [f for f in _faces if f.center.x > 1]:
                    f.select = True
                for f in [f for f in _faces if f.center.x < 0]:
                    f.select = True
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='FACE')
            if bounds_x == 'CLIP':
                bpy.ops.mesh.delete(type='FACE')
                bpy.ops.object.mode_set(mode='OBJECT')
            if bounds_x == 'CYCLIC':
                bpy.ops.mesh.split()
                bpy.ops.object.mode_set(mode='OBJECT')
        # Bound Y
        if bounds_y != 'EXTEND':
            if mode == 'GLOBAL':
                planes_co = ((0,0,0),(1,1,1))
                plane_no = (0,1,0)
            if mode == 'LOCAL':
                planes_co = (ob1.matrix_world @ Vector((0,0,0)), ob1.matrix_world @ Vector((0,1,0)))
                plane_no = planes_co[0]-planes_co[1]
            bpy.ops.object.mode_set(mode='EDIT')
            for co in planes_co:
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.bisect(plane_co=co, plane_no=plane_no)
                bpy.ops.mesh.mark_seam()
            bpy.ops.object.mode_set(mode='OBJECT')
            _faces = ob1.data.polygons
            if mode == 'GLOBAL':
                for f in [f for f in _faces if (ob1.matrix_world @ f.center).y > 1]:
                    f.select = True
                for f in [f for f in _faces if (ob1.matrix_world @ f.center).y < 0]:
                    f.select = True
            else:
                for f in [f for f in _faces if f.center.y > 1]:
                    f.select = True
                for f in [f for f in _faces if f.center.y < 0]:
                    f.select = True

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='FACE')
            if bounds_y == 'CLIP':
                bpy.ops.mesh.delete(type='FACE')
                bpy.ops.object.mode_set(mode='OBJECT')
            if bounds_y == 'CYCLIC':
                bpy.ops.mesh.split()
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set(mode='OBJECT')
        #ob1 = new_ob1

        me1 = ob1.data

    verts0 = me0.vertices   # Collect generator vertices

    # Component statistics
    n_verts1 = len(me1.vertices)
    n_edges1 = len(me1.edges)
    n_faces1 = len(me1.polygons)

    # Create empty lists
    new_verts = []
    new_edges = []
    new_faces = []
    new_verts_np = np.array(())

    # Component Coordinates
    co1 = [0]*n_verts1*3

    if mode == 'GLOBAL':
        for v in me1.vertices:
            v.co = ob1.matrix_world @ v.co
            try:
                for sk in me1.shape_keys.key_blocks:
                    sk.data[v.index].co = ob1.matrix_world @ sk.data[v.index].co
            except: pass
    if mode != 'BOUNDS':
        if bounds_x == 'CYCLIC':
            move_verts = []
            for f in [f for f in me1.polygons if (f.center).x > 1]:
                for v in f.vertices:
                    if v not in move_verts: move_verts.append(v)
            for v in move_verts:
                me1.vertices[v].co.x -= 1
                try:
                    _ob1.active_shape_key_index = 0
                    for sk in me1.shape_keys.key_blocks:
                        sk.data[v].co.x -= 1
                except: pass
            move_verts = []
            for f in [f for f in me1.polygons if (f.center).x < 0]:
                for v in f.vertices:
                    if v not in move_verts: move_verts.append(v)
            for v in move_verts:
                me1.vertices[v].co.x += 1
                try:
                    _ob1.active_shape_key_index = 0
                    for sk in me1.shape_keys.key_blocks:
                        sk.data[v].co.x += 1
                except: pass
        if bounds_y == 'CYCLIC':
            move_verts = []
            for f in [f for f in me1.polygons if (f.center).y > 1]:
                for v in f.vertices:
                    if v not in move_verts: move_verts.append(v)
            for v in move_verts:
                me1.vertices[v].co.y -= 1
                try:
                    #new_ob1.active_shape_key_index = 0
                    for sk in me1.shape_keys.key_blocks:
                        sk.data[v].co.y -= 1
                except: pass
            move_verts = []
            for f in [f for f in me1.polygons if (f.center).y < 0]:
                for v in f.vertices:
                    if v not in move_verts: move_verts.append(v)
            for v in move_verts:
                me1.vertices[v].co.y += 1
                try:
                    #new_ob1.active_shape_key_index = 0
                    for sk in me1.shape_keys.key_blocks:
                        sk.data[v].co.y += 1
                except: pass
    if len(me1.vertices) == 0:
        bpy.data.objects.remove(ob0)
        bpy.data.objects.remove(ob1)
        return 0

    me1.vertices.foreach_get("co", co1)
    co1 = np.array(co1)
    vx = co1[0::3].reshape((n_verts1,1))
    vy = co1[1::3].reshape((n_verts1,1))
    vz = co1[2::3].reshape((n_verts1,1))
    min_c = Vector((vx.min(), vy.min(), vz.min()))          # Min BB Corner
    max_c = Vector((vx.max(), vy.max(), vz.max()))          # Max BB Corner
    bb = max_c - min_c                                      # Bounding Box

    # Component Coordinates
    if mode == 'BOUNDS':
        vx = (vx - min_c[0]) / bb[0] if bb[0] != 0 else 0.5
        vy = (vy - min_c[1]) / bb[1] if bb[1] != 0 else 0.5
        vz = (vz - min_c[2]) / bb[2] if bb[2] != 0 else 0
        vz = (vz - 0.5 + offset * 0.5) * zscale
        #vz = ((vz - min_c[2]) + (-0.5 + offset * 0.5) * bb[2]) * zscale
    else:
        vz *= zscale

    # Component polygons
    fs1 = [[i for i in p.vertices] for p in me1.polygons]
    new_faces = fs1[:]

    # Component edges
    es1 = np.array([[i for i in e.vertices] for e in me1.edges])
    #es1 = [[i for i in e.vertices] for e in me1.edges if e.is_loose]
    new_edges = es1[:]

    # SHAPE KEYS
    if bool_shapekeys:
        basis = True #com_modifiers
        vx_key = []
        vy_key = []
        vz_key = []
        sk_np = []
        for sk in ob1.data.shape_keys.key_blocks:
            do_shapekeys = True
            # set all keys to 0
            for _sk in ob1.data.shape_keys.key_blocks: _sk.value = 0
            sk.value = 1

            if basis:
                basis = False
                continue

            # Apply component modifiers
            if com_modifiers:
                sk_ob = convert_object_to_mesh(_ob1)
                sk_data = sk_ob.data
                source = sk_data.vertices
            else:
                source = sk.data

            shapekeys = []
            for v in source:
                if mode == 'BOUNDS':
                    vert = v.co - min_c
                    vert[0] = (vert[0] / bb[0] if bb[0] != 0 else 0.5)
                    vert[1] = (vert[1] / bb[1] if bb[1] != 0 else 0.5)
                    vert[2] = (vert[2] / bb[2] if bb[2] != 0 else vert[2])
                    vert[2] = (vert[2] - 0.5 + offset * 0.5) * zscale
                elif mode == 'LOCAL':
                    vert = v.co.xyz
                    vert[2] *= zscale
                    #vert[2] = (vert[2] - min_c[2] + (-0.5 + offset * 0.5) * bb[2]) * \
                    #          zscale
                elif mode == 'GLOBAL':
                    vert = v.co.xyz
                    #vert = ob1.matrix_world @ v.co
                    vert[2] *= zscale
                shapekeys.append(vert)

            # Component vertices
            key1 = np.array([v for v in shapekeys]).reshape(len(shapekeys), 3, 1)
            vx_key.append(key1[:, 0])
            vy_key.append(key1[:, 1])
            vz_key.append(key1[:, 2])
            #sk_np.append([])

    # All vertex group
    if bool_vertex_group or rotation_mode == 'WEIGHT':
        try:
            weight = []
            for vg in ob0.vertex_groups:
                _weight = []
                for i,v in enumerate(me0.vertices):
                    try:
                        _weight.append(vg.weight(i))
                    except:
                        _weight.append(0)
                weight.append(_weight)
        except:
            bool_vertex_group = False

    # Adaptive Z
    if scale_mode == 'ADAPTIVE':
        com_area = bb[0]*bb[1]
        if mode != 'BOUNDS' or com_area == 0: com_area = 1
        verts_area = []
        bm = bmesh.new()
        bm.from_mesh(me0)
        bm.verts.ensure_lookup_table()
        for v in bm.verts:
            area = 0
            faces = v.link_faces
            for f in faces:
                area += f.calc_area()
            try:
                area/=len(faces) # average area
                area/=com_area
                verts_area.append(sqrt(area)*bb[2])
                #verts_area.append(area)
            except:
                verts_area.append(1)

    count = 0   # necessary for UV calculation

    # TESSELLATION
    j = 0
    jj = -1
    bool_correct = False

    # optimization test
    n_faces = len(base_polygons)
    _vs0 = [0]*n_faces
    _nvs0 = [0]*n_faces
    _sz = [0]*n_faces
    n_vg = len(ob0.vertex_groups)
    _w0 = [[0]*n_faces for i in range(n_vg)]
    np_faces = [np.array(p) for p in fs1]
    new_faces = [0]*n_faces*n_faces1
    face1_count = 0

    for j, p in enumerate(base_polygons):

        bool_correct = True
        if rotation_mode in ['UV', 'WEIGHT'] and ob0.type != 'MESH':
            rotation_mode = 'DEFAULT'

        ordered = p.vertices

        # Random rotation
        if rotation_mode == 'RANDOM':
            shifted_vertices = []
            n_poly_verts = len(p.vertices)
            rand = random.randint(0, n_poly_verts)
            for i in range(n_poly_verts):
                shifted_vertices.append(p.vertices[(i + rand) % n_poly_verts])
            if scale_mode == 'ADAPTIVE':
                verts_area0 = np.array([verts_area[i] for i in shifted_vertices])
            ordered = shifted_vertices

        # UV rotation
        elif rotation_mode == 'UV':
            if len(ob0.data.uv_layers) > 0:
                i = p.index
                if bool_material_id:
                    count = sum([len(p.vertices) for p in me0.polygons[:i]])
                    #if i == 0: count = 0
                v01 = (me0.uv_layers.active.data[count].uv +
                       me0.uv_layers.active.data[count + 1].uv)
                if len(p.vertices) > 3:
                    v32 = (me0.uv_layers.active.data[count + 3].uv +
                           me0.uv_layers.active.data[count + 2].uv)
                else:
                    v32 = (me0.uv_layers.active.data[count].uv +
                           me0.uv_layers.active.data[count + 2].uv)
                v0132 = v32 - v01
                v0132.normalize()

                v12 = (me0.uv_layers.active.data[count + 1].uv +
                       me0.uv_layers.active.data[count + 2].uv)
                if len(p.vertices) > 3:
                    v03 = (me0.uv_layers.active.data[count].uv +
                           me0.uv_layers.active.data[count + 3].uv)
                else:
                    v03 = (me0.uv_layers.active.data[count].uv +
                           me0.uv_layers.active.data[count].uv)
                v1203 = v03 - v12
                v1203.normalize()

                vertUV = []
                dot1203 = v1203.x
                dot0132 = v0132.x
                if(abs(dot1203) < abs(dot0132)):
                    if (dot0132 > 0):
                        vertUV = p.vertices[1:] + p.vertices[:1]
                    else:
                        vertUV = p.vertices[3:] + p.vertices[:3]
                else:
                    if(dot1203 < 0):
                        vertUV = p.vertices[:]
                    else:
                        vertUV = p.vertices[2:] + p.vertices[:2]
                ordered = vertUV
                count += len(p.vertices)

        # Weight Rotation
        elif rotation_mode == 'WEIGHT':
            if len(weight) > 0:
                active_weight = weight[ob0.vertex_groups.active_index]
                i = p.index
                face_weights = [active_weight[v] for v in p.vertices]
                face_weights*=2
                if rotation_direction == 'DIAG':
                    differential = [face_weights[ii]-face_weights[ii+2] for ii in range(4)]
                else:
                    differential = [face_weights[ii]+face_weights[ii+1]-face_weights[ii+2]- face_weights[ii+3] for ii in range(4)]
                starting = differential.index(max(differential))

                ordered = p.vertices[starting:] + p.vertices[:starting]

        if rotation_mode != 'RANDOM':
            ordered = np.roll(np.array(ordered),rotation_shift)
        ordered = np.array((ordered[0], ordered[1], ordered[2], ordered[-1]))

        # assign vertices and values
        vs0 = np.array([verts0[i].co for i in ordered])
        #nvs0 = np.array([verts0[i].normal for i in ordered])
        nvs0 = np.array([normals0[i] for i in ordered])
        if scale_mode == 'ADAPTIVE':
            np_verts_area = np.array([verts_area[i] for i in ordered])
            _sz[j] = np_verts_area
        # Vertex weight
        if bool_vertex_group:
            ws0 = []
            for w in weight:
                _ws0 = []
                for i in ordered:
                    try:
                        _ws0.append(w[i])
                    except:
                        _ws0.append(0)
                ws0.append(np.array(_ws0))

        # optimization test
        _vs0[j] = (vs0[0], vs0[1], vs0[2], vs0[-1])
        if normals_mode != 'FACES':
            _nvs0[j] = (nvs0[0], nvs0[1], nvs0[2], nvs0[-1])

        if bool_vertex_group:
            for i_vg, ws0_face in enumerate(ws0):
                _w0[i_vg][j] = (ws0_face[0], ws0_face[1], ws0_face[2], ws0_face[-1])

        for p in fs1:
            new_faces[face1_count] = [i + n_verts1 * j for i in p]
            face1_count += 1

    # build edges list
    n_edges1 = new_edges.shape[0]
    new_edges = new_edges.reshape((1, n_edges1, 2))
    new_edges = new_edges.repeat(n_faces,axis=0)
    new_edges = new_edges.reshape((n_edges1*n_faces, 2))
    increment = np.arange(n_faces)*n_verts1
    increment = increment.repeat(n_edges1, axis=0)
    increment = increment.reshape((n_faces*n_edges1,1))
    new_edges = new_edges + increment

    # optimization test
    _vs0 = np.array(_vs0)
    _sz = np.array(_sz)

    _vs0_0 = _vs0[:,0].reshape((n_faces,1,3))
    _vs0_1 = _vs0[:,1].reshape((n_faces,1,3))
    _vs0_2 = _vs0[:,2].reshape((n_faces,1,3))
    _vs0_3 = _vs0[:,3].reshape((n_faces,1,3))

    # remapped vertex coordinates
    v2 = np_lerp2(_vs0_0, _vs0_1, _vs0_3, _vs0_2, vx, vy)

    # remapped vertex normal
    if normals_mode != 'FACES':
        _nvs0 = np.array(_nvs0)
        _nvs0_0 = _nvs0[:,0].reshape((n_faces,1,3))
        _nvs0_1 = _nvs0[:,1].reshape((n_faces,1,3))
        _nvs0_2 = _nvs0[:,2].reshape((n_faces,1,3))
        _nvs0_3 = _nvs0[:,3].reshape((n_faces,1,3))
        nv2 = np_lerp2(_nvs0_0, _nvs0_1, _nvs0_3, _nvs0_2, vx, vy)
    else:
        nv2 = np.array(base_face_normals).reshape((n_faces,1,3))

    # interpolate vertex groups
    if bool_vertex_group:
        w = np.array(_w0)
        w_0 = w[:,:,0].reshape((n_vg, n_faces,1,1))
        w_1 = w[:,:,1].reshape((n_vg, n_faces,1,1))
        w_2 = w[:,:,2].reshape((n_vg, n_faces,1,1))
        w_3 = w[:,:,3].reshape((n_vg, n_faces,1,1))
        # remapped weight
        w = np_lerp2(w_0, w_1, w_3, w_2, vx, vy)
        w = w.reshape((n_vg, n_faces*n_verts1))

    if scale_mode == 'ADAPTIVE':
        _sz_0 = _sz[:,0].reshape((n_faces,1,1))
        _sz_1 = _sz[:,1].reshape((n_faces,1,1))
        _sz_2 = _sz[:,2].reshape((n_faces,1,1))
        _sz_3 = _sz[:,3].reshape((n_faces,1,1))
        # remapped z scale
        sz2 = np_lerp2(_sz_0, _sz_1, _sz_3, _sz_2, vx, vy)
        v3 = v2 + nv2 * vz * sz2
    else:
        v3 = v2 + nv2 * vz

    new_verts_np = v3.reshape((n_faces*n_verts1,3))

    if bool_shapekeys:
        n_sk = len(vx_key)
        sk_np = [0]*n_sk
        for i in range(n_sk):
            vx = np.array(vx_key[i])
            vy = np.array(vy_key[i])
            vz = np.array(vz_key[i])

            # remapped vertex coordinates
            v2 = np_lerp2(_vs0_0, _vs0_1, _vs0_3, _vs0_2, vx, vy)

            # remapped vertex normal
            if normals_mode != 'FACES':
                nv2 = np_lerp2(_nvs0_0, _nvs0_1, _nvs0_3, _nvs0_2, vx, vy)
            else:
                nv2 = np.array(base_face_normals).reshape((n_faces,1,3))

            if scale_mode == 'ADAPTIVE':
                # remapped z scale
                sz2 = np_lerp2(_sz_0, _sz_1, _sz_3, _sz_2, vx, vy)
                v3 = v2 + nv2 * vz * sz2
            else:
                v3 = v2 + nv2 * vz

            sk_np[i] = v3.reshape((n_faces*n_verts1,3))

    #if ob0.type == 'MESH': ob0.data = old_me0

    if not bool_correct:
        #bpy.data.objects.remove(ob1)
        return 0

    new_verts = new_verts_np.tolist()
    new_name = ob0.name + "_" + ob1.name
    new_me = bpy.data.meshes.new(new_name)
    new_me.from_pydata(new_verts, new_edges.tolist(), new_faces)
    new_me.update(calc_edges=True)
    new_ob = bpy.data.objects.new("tessellate_temp", new_me)

    # vertex group
    if bool_vertex_group and False:
        for vg in ob0.vertex_groups:
            new_ob.vertex_groups.new(name=vg.name)
            for i in range(len(vg_np[vg.index])):
                new_ob.vertex_groups[vg.name].add([i], vg_np[vg.index][i],"ADD")
    # vertex group
    if bool_vertex_group:
        for vg in ob0.vertex_groups:
            new_ob.vertex_groups.new(name=vg.name)
            for i, vertex_weight in enumerate(w[vg.index]):
                new_ob.vertex_groups[vg.name].add([i], vertex_weight,"ADD")

    if bool_shapekeys:
        basis = com_modifiers
        sk_count = 0
        for sk, val in zip(_ob1.data.shape_keys.key_blocks, original_key_values):
            sk.value = val
            new_ob.shape_key_add(name=sk.name, from_mix=False)
            new_ob.data.shape_keys.key_blocks[sk.name].value = val
            # set shape keys vertices
            sk_data = new_ob.data.shape_keys.key_blocks[sk.name].data
            if sk_count == 0:
                sk_count += 1
                continue
            for id in range(len(sk_data)):
                sk_data[id].co = sk_np[sk_count-1][id]
            sk_count += 1
        if bool_vertex_group:
            for sk in new_ob.data.shape_keys.key_blocks:
                for vg in new_ob.vertex_groups:
                    if sk.name == vg.name:
                        sk.vertex_group = vg.name

    # EDGES SEAMS
    edge_data = [0]*n_edges1
    me1.edges.foreach_get("use_seam",edge_data)
    if any(edge_data):
        edge_data = edge_data*n_faces
        new_ob.data.edges.foreach_set("use_seam",edge_data)

    # EDGES SHARP
    edge_data = [0]*n_edges1
    me1.edges.foreach_get("use_edge_sharp",edge_data)
    if any(edge_data):
        edge_data = edge_data*n_faces
        new_ob.data.edges.foreach_set("use_edge_sharp",edge_data)

    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.collection.objects.link(new_ob)
    new_ob.select_set(True)
    bpy.context.view_layer.objects.active = new_ob

    # EDGES BEVEL
    edge_data = [0]*n_edges1
    me1.edges.foreach_get("bevel_weight",edge_data)
    if any(edge_data):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.transform.edge_bevelweight(value=1)
        bpy.ops.object.mode_set(mode='OBJECT')
        edge_data = edge_data*n_faces
        new_ob.data.edges.foreach_set("bevel_weight",edge_data)

    # EDGE CREASES
    edge_data = [0]*n_edges1
    me1.edges.foreach_get("crease",edge_data)
    if any(edge_data):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.transform.edge_crease(value=1)
        bpy.ops.object.mode_set(mode='OBJECT')
        edge_data = edge_data*n_faces
        new_ob.data.edges.foreach_set('crease', edge_data)

    # MATERIALS
    for slot in ob1.material_slots: new_ob.data.materials.append(slot.material)

    polygon_materials = [0]*n_faces1
    me1.polygons.foreach_get("material_index", polygon_materials)
    polygon_materials *= n_faces
    new_ob.data.polygons.foreach_set("material_index", polygon_materials)
    new_ob.data.update() ###

    try:
        bpy.data.objects.remove(new_ob1)
    except: pass

    bpy.data.objects.remove(ob0)
    bpy.data.meshes.remove(me0)
    bpy.data.objects.remove(ob1)
    bpy.data.meshes.remove(me1)

    return new_ob


class tissue_tessellate(Operator):
    bl_idname = "object.tissue_tessellate"
    bl_label = "Tessellate"
    bl_description = ("Create a copy of selected object on the active object's "
                      "faces, adapting the shape to the different faces")
    bl_options = {'REGISTER', 'UNDO'}


    bool_hold : BoolProperty(
            name="Hold",
            description="Wait...",
            default=False
    )
    bool_lock : BoolProperty(
            name="Lock",
            description="Prevent automatic update on settings changes or if other objects have it in the hierarchy.",
            default=False
    )
    bool_dependencies : BoolProperty(
            name="Update Dependencies",
            description="Automatically updates base and components as well, if results of other tessellations",
            default=False
    )
    object_name : StringProperty(
            name="",
            description="Name of the generated object"
            )
    zscale : FloatProperty(
            name="Scale",
            default=1,
            soft_min=0,
            soft_max=10,
            description="Scale factor for the component thickness"
            )
    scale_mode : EnumProperty(
            items=(
                ('CONSTANT', "Constant", "Uniform thickness"),
                ('ADAPTIVE', "Relative", "Preserve component's proportions")
                ),
            default='ADAPTIVE',
            name="Z-Scale according to faces size"
            )
    offset : FloatProperty(
            name="Surface Offset",
            default=1,
            min=-1, max=1,
            soft_min=-1,
            soft_max=1,
            description="Surface offset"
            )
    mode : EnumProperty(
            items=(
                ('BOUNDS', "Bounds", "The component fits automatically the size of the target face"),
                ('LOCAL', "Local", "Based on Local coordinates, from 0 to 1"),
                ('GLOBAL', 'Global', "Based on Global coordinates, from 0 to 1")),
            default='BOUNDS',
            name="Component Mode"
            )
    rotation_mode : EnumProperty(
            items=(('RANDOM', "Random", "Random faces rotation"),
                   ('UV', "Active UV", "Face rotation is based on UV coordinates"),
                   ('WEIGHT', "Active Weight", "Rotate according to Vertex Group gradient"),
                   ('DEFAULT', "Default", "Default rotation")),
            default='DEFAULT',
            name="Component Rotation"
            )
    rotation_direction : EnumProperty(
            items=(('ORTHO', "Orthogonal", "Component main directions in XY"),
                   ('DIAG', "Diagonal", "Component main direction aligned with diagonal")),
            default='ORTHO',
            name="Direction"
            )
    rotation_shift : IntProperty(
            name="Shift",
            default=0,
            soft_min=0,
            soft_max=3,
            description="Shift components rotation"
            )
    fill_mode : EnumProperty(
            items=(
                ('QUAD', 'Quad', 'Regular quad tessellation. Uses only 3 or 4 vertices'),
                ('FAN', 'Fan', 'Radial tessellation for polygonal faces'),
                ('PATCH', 'Patch', 'Curved tessellation according to the last ' +
                'Subsurf\n(or Multires) modifiers. Works only with 4 sides ' +
                'patches.\nAfter the last Subsurf (or Multires) only ' +
                'deformation\nmodifiers can be used'),
                ('FRAME', 'Frame', 'Essellation along the edges of each face')),
            default='QUAD',
            name="Fill Mode"
            )
    combine_mode : EnumProperty(
            items=(
                ('LAST', 'Last', 'Show only the last iteration'),
                ('UNUSED', 'Unused', 'Combine each iteration with the unused faces of the previous iteration. Used for branching systems'),
                ('ALL', 'All', 'Combine the result of all iterations')),
            default='LAST',
            name="Combine Mode",
            )
    gen_modifiers : BoolProperty(
            name="Generator Modifiers",
            default=False,
            description="Apply Modifiers and Shape Keys to the base object"
            )
    com_modifiers : BoolProperty(
            name="Component Modifiers",
            default=False,
            description="Apply Modifiers and Shape Keys to the component object"
            )
    merge : BoolProperty(
            name="Merge",
            default=False,
            description="Merge vertices in adjacent duplicates"
            )
    merge_thres : FloatProperty(
            name="Distance",
            default=0.001,
            soft_min=0,
            soft_max=10,
            description="Limit below which to merge vertices"
            )
    bool_random : BoolProperty(
            name="Randomize",
            default=False,
            description="Randomize component rotation"
            )
    random_seed : IntProperty(
            name="Seed",
            default=0,
            soft_min=0,
            soft_max=10,
            description="Random seed"
            )
    bool_vertex_group : BoolProperty(
            name="Map Vertex Groups",
            default=False,
            description="Transfer all Vertex Groups from Base object"
            )
    bool_selection : BoolProperty(
            name="On selected Faces",
            default=False,
            description="Create Tessellation only on selected faces"
            )
    bool_shapekeys : BoolProperty(
            name="Use Shape Keys",
            default=False,
            description="Transfer Component's Shape Keys. If the name of Vertex "
                        "Groups and Shape Keys are the same, they will be "
                        "automatically combined"
            )
    bool_smooth : BoolProperty(
            name="Smooth Shading",
            default=False,
            description="Output faces with smooth shading rather than flat shaded"
            )
    bool_materials : BoolProperty(
            name="Transfer Materials",
            default=True,
            description="Preserve component's materials"
            )
    generator : StringProperty(
            name="",
            description="Base object for the tessellation",
            default = ""
            )
    component : StringProperty(
            name="",
            description="Component object for the tessellation",
            default = ""
            )
    bool_material_id : BoolProperty(
            name="Tessellation on Material ID",
            default=False,
            description="Apply the component only on the selected Material"
            )
    bool_dissolve_seams : BoolProperty(
            name="Dissolve Seams",
            default=False,
            description="Dissolve all seam edges"
            )
    material_id : IntProperty(
            name="Material ID",
            default=0,
            min=0,
            description="Material ID"
            )
    iterations : IntProperty(
            name="Iterations",
            default=1,
            min=1,
            soft_max=5,
            description="Automatically repeat the Tessellation using the "
                        + "generated geometry as new base object.\nUsefull for "
                        + "for branching systems. Dangerous!"
            )
    bool_combine : BoolProperty(
            name="Combine unused",
            default=False,
            description="Combine the generated geometry with unused faces"
            )
    bool_advanced : BoolProperty(
            name="Advanced Settings",
            default=False,
            description="Show more settings"
            )
    normals_mode : EnumProperty(
            items=(
                ('VERTS', 'Normals', 'Consistent direction based on vertices normal'),
                ('FACES', 'Individual Faces', 'Based on individual faces normal'),
                ('CUSTOM', 'Custom', "According to Base object's shape keys")),
            default='VERTS',
            name="Direction"
            )
    bool_multi_components : BoolProperty(
            name="Multi Components",
            default=False,
            description="Combine different components according to materials name"
            )
    bounds_x : EnumProperty(
            items=(
                ('EXTEND', 'Extend', 'Default X coordinates'),
                ('CLIP', 'Clip', 'Trim out of bounds in X direction'),
                ('CYCLIC', 'Cyclic', 'Cyclic components in X direction')),
            default='EXTEND',
            name="Bounds X",
            )
    bounds_y : EnumProperty(
            items=(
                ('EXTEND', 'Extend', 'Default Y coordinates'),
                ('CLIP', 'Clip', 'Trim out of bounds in Y direction'),
                ('CYCLIC', 'Cyclic', 'Cyclic components in Y direction')),
            default='EXTEND',
            name="Bounds Y",
            )
    close_mesh : EnumProperty(
            items=(
                ('NONE', 'None', 'Keep the mesh open'),
                ('CAP', 'Cap Holes', 'Automatically cap open loops'),
                ('BRIDGE', 'Bridge Loops', 'Automatically bridge loop pairs')),
            default='NONE',
            name="Close Mesh"
            )
    cap_faces : BoolProperty(
            name="Cap Holes",
            default=False,
            description="Cap open edges loops"
            )
    frame_boundary : BoolProperty(
            name="Frame Boundary",
            default=False,
            description="Support face boundaries"
            )
    fill_frame : BoolProperty(
            name="Fill Frame",
            default=False,
            description="Fill inner faces with Fan tessellation"
            )
    frame_boundary_mat : IntProperty(
            name="Material Offset",
            default=0,
            description="Material Offset for boundaries"
            )
    fill_frame_mat : IntProperty(
            name="Material Offset",
            default=0,
            description="Material Offset for inner faces"
            )
    open_edges_crease : FloatProperty(
            name="Open Edges Crease",
            default=0,
            min=0,
            max=1,
            description="Automatically set crease for open edges"
            )
    bridge_smoothness : FloatProperty(
            name="Smoothness",
            default=1,
            min=0,
            max=1,
            description="Bridge Smoothness"
            )
    frame_thickness : FloatProperty(
            name="Frame Thickness",
            default=0.2,
            min=0,
            soft_max=2,
            description="Frame Thickness"
            )
    frame_mode : EnumProperty(
            items=(
                ('CONSTANT', 'Constant', 'Even thickness'),
                ('RELATIVE', 'Relative', 'Frame offset depends on face areas')),
            default='CONSTANT',
            name="Offset"
            )
    bridge_cuts : IntProperty(
            name="Cuts",
            default=0,
            min=0,
            max=20,
            description="Bridge Cuts"
            )
    cap_material_index : IntProperty(
            name="Material",
            default=0,
            min=0,
            description="Material index for the cap/bridge faces"
            )
    patch_subs : IntProperty(
            name="Patch Subdivisions",
            default=1,
            min=0,
            description="Subdivisions levels for Patch tessellation after the first iteration"
            )
    working_on = ""

    def draw(self, context):
        allowed_obj = ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META')
        '''
        try:
            bool_working = self.working_on == self.object_name and \
            self.working_on != ""
        except:
            bool_working = False
        '''

        bool_working = False
        bool_allowed = False
        ob0 = None
        ob1 = None

        sel = bpy.context.selected_objects
        if len(sel) == 1:
            try:
                ob0 = sel[0].tissue_tessellate.generator
                ob1 = sel[0].tissue_tessellate.component
                self.generator = ob0.name
                self.component = ob1.name
                if self.working_on == '':
                    load_parameters(self,sel[0])
                    self.working_on = sel[0].name
                bool_working = True
                bool_allowed = True
            except:
                pass

        if len(sel) == 2:
            bool_allowed = True
            for o in sel:
                if o.type not in allowed_obj:
                    bool_allowed = False

        if len(sel) != 2 and not bool_working:
            layout = self.layout
            layout.label(icon='INFO')
            layout.label(text="Please, select two different objects")
            layout.label(text="Select first the Component object, then select")
            layout.label(text="the Base object.")
        elif not bool_allowed and not bool_working:
            layout = self.layout
            layout.label(icon='INFO')
            layout.label(text="Only Mesh, Curve, Surface or Text objects are allowed")
        else:
            if ob0 == ob1 == None:
                ob0 = bpy.context.active_object
                self.generator = ob0.name
                for o in sel:
                    if o != ob0:
                        ob1 = o
                        self.component = o.name
                        self.no_component = False
                        break

            # new object name
            if self.object_name == "":
                if self.generator == "":
                    self.object_name = "Tessellation"
                else:
                    #self.object_name = self.generator + "_Tessellation"
                    self.object_name = "Tessellation"

            layout = self.layout
            # Base and Component
            col = layout.column(align=True)
            row = col.row(align=True)
            row.label(text="BASE : " + self.generator)
            row.label(text="COMPONENT : " + self.component)

            # Base Modifiers
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(self, "gen_modifiers", text="Use Modifiers", icon='MODIFIER')
            base = bpy.data.objects[self.generator]
            try:
                if not (base.modifiers or base.data.shape_keys):
                    col2.enabled = False
                    self.gen_modifiers = False
            except:
                col2.enabled = False
                self.gen_modifiers = False

            # Component Modifiers
            row.separator()
            col3 = row.column(align=True)
            col3.prop(self, "com_modifiers", text="Use Modifiers", icon='MODIFIER')
            component = bpy.data.objects[self.component]
            try:
                if not (component.modifiers or component.data.shape_keys):
                    col3.enabled = False
                    self.com_modifiers = False
            except:
                col3.enabled = False
                self.com_modifiers = False
            col.separator()
            # Fill and Rotation
            row = col.row(align=True)
            row.label(text="Fill Mode:")
            row = col.row(align=True)
            row.prop(
                self, "fill_mode", icon='NONE', expand=True,
                slider=True, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)
            row = col.row(align=True)
            row.prop(self, "bool_smooth")

            # frame settings
            if self.fill_mode == 'FRAME':
                col.separator()
                col.label(text="Frame Settings:")
                row = col.row(align=True)
                row.prop(self, "frame_mode", expand=True)
                col.prop(self, "frame_thickness", text='Thickness', icon='NONE')
                col.separator()
                row = col.row(align=True)
                row.prop(self, "fill_frame", icon='NONE')
                show_frame_mat = self.bool_multi_components or self.bool_material_id
                if self.fill_frame and show_frame_mat:
                    row.prop(self, "fill_frame_mat", icon='NONE')
                row = col.row(align=True)
                row.prop(self, "frame_boundary", text='Boundary', icon='NONE')
                if self.frame_boundary and show_frame_mat:
                    row.prop(self, "frame_boundary_mat", icon='NONE')

            if self.rotation_mode == 'UV':
                uv_error = False

                if ob0.type != 'MESH':
                    row = col.row(align=True)
                    row.label(
                        text="UV rotation supported only for Mesh objects",
                        icon='ERROR')
                    uv_error = True
                else:
                    if len(ob0.data.uv_layers) == 0:
                        row = col.row(align=True)
                        check_name = self.generator
                        row.label(text="'" + check_name +
                                  "' doesn't have UV Maps", icon='ERROR')
                        uv_error = True
                if uv_error:
                    row = col.row(align=True)
                    row.label(text="Default rotation will be used instead",
                              icon='INFO')

            # Component Z
            col.separator()
            col.label(text="Thickness:")
            row = col.row(align=True)
            row.prop(
                self, "scale_mode", text="Scale Mode", icon='NONE', expand=True,
                slider=False, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)
            col.prop(
                self, "zscale", text="Scale", icon='NONE', expand=False,
                slider=True, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)
            if self.mode == 'BOUNDS':
                col.prop(
                    self, "offset", text="Offset", icon='NONE', expand=False,
                    slider=True, toggle=False, icon_only=False, event=False,
                    full_event=False, emboss=True, index=-1)

            # Component XY
            col.separator()
            row = col.row(align=True)
            row.label(text="Component Coordinates:")
            row = col.row(align=True)
            row.prop(
                self, "mode", text="Component XY", icon='NONE', expand=True,
                slider=False, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)

            if self.mode != 'BOUNDS':
                col.separator()
                row = col.row(align=True)
                row.label(text="X:")
                row.prop(
                    self, "bounds_x", text="Bounds X", icon='NONE', expand=True,
                    slider=False, toggle=False, icon_only=False, event=False,
                    full_event=False, emboss=True, index=-1)

                row = col.row(align=True)
                row.label(text="Y:")
                row.prop(
                    self, "bounds_y", text="Bounds X", icon='NONE', expand=True,
                    slider=False, toggle=False, icon_only=False, event=False,
                    full_event=False, emboss=True, index=-1)


            # merge settings
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(self, "merge")
            if self.merge:
                row.prop(self, "merge_thres")
                col.separator()
                row = col.row(align=True)
                col2 = row.column(align=True)
                col2.label(text='Close Mesh:')
                col2 = row.column(align=True)
                col2.prop(self, "close_mesh",text='')
                if self.close_mesh != 'NONE':
                    row = col.row(align=True)
                    row.prop(self, "open_edges_crease", text="Crease")
                    row.prop(self, "cap_material_index")
                    if self.close_mesh == 'BRIDGE':
                        row = col.row(align=True)
                        row.prop(self, "bridge_cuts")
                        row.prop(self, "bridge_smoothness")
                row = col.row(align=True)
                row.prop(self, "bool_dissolve_seams")

            # Advanced Settings
            col = layout.column(align=True)
            col.separator()
            col.separator()
            row = col.row(align=True)
            row.prop(self, "bool_advanced", icon='SETTINGS')
            if self.bool_advanced:
                # rotation
                layout.use_property_split = True
                layout.use_property_decorate = False  # No animation.
                col = layout.column(align=True)
                col.prop(self, "rotation_mode", text='Rotation', icon='NONE', expand=False,
                         slider=True, toggle=False, icon_only=False, event=False,
                         full_event=False, emboss=True, index=-1)
                if self.rotation_mode == 'WEIGHT':
                    col.prop(self, "rotation_direction", expand=False,
                              slider=True, toggle=False, icon_only=False, event=False,
                              full_event=False, emboss=True, index=-1)
                if self.rotation_mode == 'RANDOM':
                    col.prop(self, "random_seed")
                else:
                    col.prop(self, "rotation_shift")

                if self.rotation_mode == 'UV':
                    uv_error = False
                    if self.generator.type != 'MESH':
                        row = col.row(align=True)
                        row.label(
                            text="UV rotation supported only for Mesh objects",
                            icon='ERROR')
                        uv_error = True
                    else:
                        if len(self.generator.data.uv_layers) == 0:
                            row = col.row(align=True)
                            row.label(text="'" + props.generator.name +
                                      " doesn't have UV Maps", icon='ERROR')
                            uv_error = True
                    if uv_error:
                        row = col.row(align=True)
                        row.label(text="Default rotation will be used instead",
                                  icon='INFO')
                layout.use_property_split = False

                # Direction
                col = layout.column(align=True)
                row = col.row(align=True)
                row.label(text="Direction:")
                row = col.row(align=True)
                row.prop(
                    self, "normals_mode", text="Direction", icon='NONE', expand=True,
                    slider=False, toggle=False, icon_only=False, event=False,
                    full_event=False, emboss=True, index=-1)
                #row.enabled = self.fill_mode != 'PATCH'

                allow_multi = False
                allow_shapekeys = not self.com_modifiers
                if self.com_modifiers: self.bool_shapekeys = False
                for m in ob0.data.materials:
                    try:
                        o = bpy.data.objects[m.name]
                        allow_multi = True
                        try:
                            if o.data.shape_keys is None: continue
                            elif len(o.data.shape_keys.key_blocks) < 2: continue
                            else: allow_shapekeys = not self.com_modifiers
                        except: pass
                    except: pass
                # DATA #
                col = layout.column(align=True)
                col.label(text="Weight and Morphing:")
                # vertex group + shape keys
                row = col.row(align=True)
                col2 = row.column(align=True)
                col2.prop(self, "bool_vertex_group", icon='GROUP_VERTEX')
                try:
                    if len(ob0.vertex_groups) == 0:
                        col2.enabled = False
                except:
                    col2.enabled = False
                row.separator()
                col2 = row.column(align=True)
                row2 = col2.row(align=True)
                row2.prop(self, "bool_shapekeys", text="Use Shape Keys",  icon='SHAPEKEY_DATA')
                row2.enabled = allow_shapekeys

                # LIMITED TESSELLATION
                col = layout.column(align=True)
                col.label(text="Limited Tessellation:")
                row = col.row(align=True)
                col2 = row.column(align=True)
                col2.prop(self, "bool_multi_components", icon='MOD_TINT')
                if not allow_multi:
                    col2.enabled = False
                    self.bool_multi_components = False
                col.separator()
                row = col.row(align=True)
                col2 = row.column(align=True)
                col2.prop(self, "bool_selection", text="On selected Faces", icon='RESTRICT_SELECT_OFF')
                row.separator()
                if ob0.type != 'MESH':
                    col2.enabled = False
                col2 = row.column(align=True)
                col2.prop(self, "bool_material_id", icon='MATERIAL_DATA', text="Material ID")
                if self.bool_material_id and not self.bool_multi_components:
                    #col2 = row.column(align=True)
                    col2.prop(self, "material_id")
                col2.enabled = not self.bool_multi_components

                col.separator()
                row = col.row(align=True)
                row.label(text='Reiterate Tessellation:', icon='FILE_REFRESH')
                row.prop(self, 'iterations', text='Repeat', icon='SETTINGS')
                if self.iterations > 1 and self.fill_mode == 'PATCH':
                    col.separator()
                    row = col.row(align=True)
                    row.prop(self, 'patch_subs')
                col.separator()
                row = col.row(align=True)
                row.label(text='Combine Iterations:')
                row = col.row(align=True)
                row.prop(
                    self, "combine_mode", icon='NONE', expand=True,
                    slider=False, toggle=False, icon_only=False, event=False,
                    full_event=False, emboss=True, index=-1)

    def execute(self, context):
        allowed_obj = ('MESH', 'CURVE', 'META', 'SURFACE', 'FONT')
        try:
            ob0 = bpy.data.objects[self.generator]
            ob1 = bpy.data.objects[self.component]
        except:
            return {'CANCELLED'}

        self.object_name = "Tessellation"
        # Check if existing object with same name
        names = [o.name for o in bpy.data.objects]
        if self.object_name in names:
            count_name = 1
            while True:
                test_name = self.object_name + '.{:03d}'.format(count_name)
                if not (test_name in names):
                    self.object_name = test_name
                    break
                count_name += 1

        if ob1.type not in allowed_obj:
            message = "Component must be Mesh, Curve, Surface, Text or Meta object!"
            self.report({'ERROR'}, message)
            self.component = None

        if ob0.type not in allowed_obj:
            message = "Generator must be Mesh, Curve, Surface, Text or Meta object!"
            self.report({'ERROR'}, message)
            self.generator = ""

        if True:#self.component not in ("",None) and self.generator not in ("",None):
            if bpy.ops.object.select_all.poll():
                bpy.ops.object.select_all(action='TOGGLE')
            bpy.ops.object.mode_set(mode='OBJECT')

            #data0 = ob0.to_mesh(False)
            #data0 = ob0.data.copy()
            bool_update = False
            if bpy.context.object == ob0:
                auto_layer_collection()
                #new_ob = bpy.data.objects.new(self.object_name, data0)
                new_ob = convert_object_to_mesh(ob0,False,False)
                new_ob.data.name = self.object_name
                #bpy.context.collection.objects.link(new_ob)
                #bpy.context.view_layer.objects.active = new_ob
                new_ob.name = self.object_name
                #new_ob.select_set(True)
            else:
                new_ob = bpy.context.object
                bool_update = True
            new_ob = store_parameters(self, new_ob)
            try: bpy.ops.object.tissue_update_tessellate()
            except RuntimeError as e:
                bpy.data.objects.remove(new_ob)
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}
            if not bool_update:
                self.object_name = new_ob.name
                #self.working_on = self.object_name
                new_ob.location = ob0.location
                new_ob.matrix_world = ob0.matrix_world

            return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


def update_dependencies(ob, objects):
    ob0 = ob.tissue_tessellate.generator
    ob1 = ob.tissue_tessellate.component
    deps = [ob0, ob1]
    for o in deps:
        if o.tissue_tessellate.bool_lock: continue
        o0 = o.tissue_tessellate.generator
        o1 = o.tissue_tessellate.component
        deps_deps = [o0, o1]
        try:
            o0.name
            o1.name
            if o0 not in objects and o1 not in objects:
                objects.append(o)
                objects = update_dependencies(o, objects)
        except:
            continue
    return objects


class tissue_refresh_tessellate(Operator):
    bl_idname = "object.tissue_refresh_tessellate"
    bl_label = "Refresh"
    bl_description = ("Fast update the tessellated mesh according to base and "
                      "component changes")
    bl_options = {'REGISTER', 'UNDO'}

    go = False

    @classmethod
    def poll(cls, context):
        try:
            return context.object.tissue_tessellate.generator != None and \
                context.object.tissue_tessellate.component != None
        except:
            return False

    @staticmethod
    def check_gen_comp(checking):
        # note pass the stored name key in here to check it out
        return checking in bpy.data.objects.keys()

    def execute(self, context):
        ob = bpy.context.object
        ob0 = ob.tissue_tessellate.generator
        ob1 = ob.tissue_tessellate.component
        try:
            ob0.name
            ob1.name
        except:
            self.report({'ERROR'},
                        "Active object must be Tessellate before Update")
            return {'CANCELLED'}

        if ob.tissue_tessellate.bool_dependencies:
            update_objects = list(reversed(update_dependencies(ob, [ob])))
        else:
            update_objects = [ob]
        for o in update_objects:
            override = {'object': o}
            bpy.ops.object.tissue_update_tessellate(override)

        return {'FINISHED'}


class tissue_update_tessellate(Operator):
    bl_idname = "object.tissue_update_tessellate"
    bl_label = "Refresh"
    bl_description = ("Fast update the tessellated mesh according to base and "
                      "component changes")
    bl_options = {'REGISTER', 'UNDO'}

    go = False

    @classmethod
    def poll(cls, context):
        #try:
        try: #context.object == None: return False
            return context.object.tissue_tessellate.generator != None and \
                context.object.tissue_tessellate.component != None
        except:
            return False

    @staticmethod
    def check_gen_comp(checking):
        # note pass the stored name key in here to check it out
        return checking in bpy.data.objects.keys()

    def execute(self, context):
        start_time = time.time()

        ob = context.object
        if not self.go:
            generator = ob.tissue_tessellate.generator
            component = ob.tissue_tessellate.component
            zscale = ob.tissue_tessellate.zscale
            scale_mode = ob.tissue_tessellate.scale_mode
            rotation_mode = ob.tissue_tessellate.rotation_mode
            rotation_shift = ob.tissue_tessellate.rotation_shift
            rotation_direction = ob.tissue_tessellate.rotation_direction
            offset = ob.tissue_tessellate.offset
            merge = ob.tissue_tessellate.merge
            merge_thres = ob.tissue_tessellate.merge_thres
            gen_modifiers = ob.tissue_tessellate.gen_modifiers
            com_modifiers = ob.tissue_tessellate.com_modifiers
            bool_random = ob.tissue_tessellate.bool_random
            random_seed = ob.tissue_tessellate.random_seed
            fill_mode = ob.tissue_tessellate.fill_mode
            bool_vertex_group = ob.tissue_tessellate.bool_vertex_group
            bool_selection = ob.tissue_tessellate.bool_selection
            bool_shapekeys = ob.tissue_tessellate.bool_shapekeys
            mode = ob.tissue_tessellate.mode
            bool_smooth = ob.tissue_tessellate.bool_smooth
            bool_materials = ob.tissue_tessellate.bool_materials
            bool_dissolve_seams = ob.tissue_tessellate.bool_dissolve_seams
            bool_material_id = ob.tissue_tessellate.bool_material_id
            material_id = ob.tissue_tessellate.material_id
            iterations = ob.tissue_tessellate.iterations
            bool_combine = ob.tissue_tessellate.bool_combine
            normals_mode = ob.tissue_tessellate.normals_mode
            bool_advanced = ob.tissue_tessellate.bool_advanced
            bool_multi_components = ob.tissue_tessellate.bool_multi_components
            combine_mode = ob.tissue_tessellate.combine_mode
            bounds_x = ob.tissue_tessellate.bounds_x
            bounds_y = ob.tissue_tessellate.bounds_y
            cap_faces = ob.tissue_tessellate.cap_faces
            close_mesh = ob.tissue_tessellate.close_mesh
            open_edges_crease = ob.tissue_tessellate.open_edges_crease
            bridge_smoothness = ob.tissue_tessellate.bridge_smoothness
            frame_thickness = ob.tissue_tessellate.frame_thickness
            frame_mode = ob.tissue_tessellate.frame_mode
            frame_boundary = ob.tissue_tessellate.frame_boundary
            fill_frame = ob.tissue_tessellate.fill_frame
            frame_boundary_mat = ob.tissue_tessellate.frame_boundary_mat
            fill_frame_mat = ob.tissue_tessellate.fill_frame_mat
            bridge_cuts = ob.tissue_tessellate.bridge_cuts
            cap_material_index = ob.tissue_tessellate.cap_material_index
            patch_subs = ob.tissue_tessellate.patch_subs
        try:
            generator.name
            component.name
        except:
            self.report({'ERROR'},
                        "Active object must be Tessellate before Update")
            return {'CANCELLED'}

        # Solve Local View issues
        local_spaces = []
        local_ob0 = []
        local_ob1 = []
        for area in context.screen.areas:
            for space in area.spaces:
                try:
                    if ob.local_view_get(space):
                        local_spaces.append(space)
                        local_ob0 = ob0.local_view_get(space)
                        ob0.local_view_set(space, True)
                        local_ob1 = ob1.local_view_get(space)
                        ob1.local_view_set(space, True)
                except:
                    pass

        starting_mode = context.object.mode

        #if starting_mode == 'PAINT_WEIGHT': starting_mode = 'WEIGHT_PAINT'
        bpy.ops.object.mode_set(mode='OBJECT')

        ob0 = generator
        ob1 = component
        ##### auto_layer_collection()

        ob0_hide = ob0.hide_get()
        ob0_hidev = ob0.hide_viewport
        ob0_hider = ob0.hide_render
        ob1_hide = ob1.hide_get()
        ob1_hidev = ob1.hide_viewport
        ob1_hider = ob1.hide_render
        ob0.hide_set(False)
        ob0.hide_viewport = False
        ob0.hide_render = False
        ob1.hide_set(False)
        ob1.hide_viewport = False
        ob1.hide_render = False

        if ob0.type == 'META':
            base_ob = convert_object_to_mesh(ob0, False, True)
        else:
            base_ob = ob0.copy()
            base_ob.data = ob0.data#
            context.collection.objects.link(base_ob)
        base_ob.name = '_tissue_tmp_base'

        # In Blender 2.80 cache of copied objects is lost, must be re-baked
        bool_update_cloth = False
        for m in base_ob.modifiers:
            if m.type == 'CLOTH':
                m.point_cache.frame_end = context.scene.frame_current
                bool_update_cloth = True
        if bool_update_cloth:
            bpy.ops.ptcache.free_bake_all()
            bpy.ops.ptcache.bake_all()
        base_ob.modifiers.update()


        #new_ob.location = ob.location
        #new_ob.matrix_world = ob.matrix_world
        #bpy.ops.object.select_all(action='DESELECT')
        if bool_selection:
            faces = base_ob.data.polygons
            selections = [False]*len(faces)
            faces.foreach_get('select',selections)
            selections = np.array(selections)
            if not selections.any():
                message = "There are no faces selected."
                context.view_layer.objects.active = ob
                ob.select_set(True)
                bpy.ops.object.mode_set(mode=starting_mode)
                bpy.data.objects.remove(base_ob)
                self.report({'ERROR'}, message)
                return {'CANCELLED'}



        iter_objects = [base_ob]
        ob_location = ob.location
        ob_matrix_world = ob.matrix_world
        #base_ob = new_ob#.copy()

        for iter in range(iterations):

            if iter > 0 and len(iter_objects) == 0: break
            if iter > 0 and normals_mode == 'CUSTOM': normals_mode = 'VERTS'
            same_iteration = []
            matched_materials = []
            # iterate base object materials (needed for multi-components)
            if bool_multi_components: mat_iter = len(base_ob.material_slots)
            else: mat_iter = 1
            for m_id in range(mat_iter):
                if bool_multi_components:
                    # check if material and components match
                    try:
                        mat = base_ob.material_slots[m_id].material
                        ob1 = bpy.data.objects[mat.name]
                        if ob1.type not in ('MESH', 'CURVE','SURFACE','FONT', 'META'):
                            continue
                        material_id = m_id
                        matched_materials.append(m_id)
                        bool_material_id = True
                    except:
                        continue
                if com_modifiers or ob1.type != 'MESH':
                    data1 = simple_to_mesh(ob1)
                else:
                    data1 = ob1.data.copy()
                n_edges1 = len(data1.edges)
                bpy.data.meshes.remove(data1)

                if iter != 0: gen_modifiers = True

                if fill_mode == 'PATCH':
                    # patch subdivisions for additional iterations
                    if iter > 0:
                        base_ob.modifiers.new('Tissue_Subsurf', type='SUBSURF')
                        base_ob.modifiers['Tissue_Subsurf'].levels = patch_subs
                        temp_mod = base_ob.modifiers['Tissue_Subsurf']
                    # patch tessellation
                    new_ob = tessellate_patch(
                            base_ob, ob1, offset, zscale, com_modifiers, mode, scale_mode,
                            rotation_mode, rotation_shift, random_seed, bool_vertex_group,
                            bool_selection, bool_shapekeys, bool_material_id, material_id,
                            normals_mode, bounds_x, bounds_y
                            )
                    if iter > 0:
                        base_ob.modifiers.remove(temp_mod)
                else:
                    ### FRAME and FAN ###
                    if fill_mode in ('FRAME','FAN'):

                        if fill_mode == 'FRAME': convert_function = convert_to_frame
                        else: convert_function = convert_to_fan

                        if normals_mode == 'CUSTOM' and base_ob.data.shape_keys != None:
                            ## base key
                            sk_values = [sk.value for sk in base_ob.data.shape_keys.key_blocks]
                            for sk in ob0.data.shape_keys.key_blocks: sk.value = 0
                            _base_ob = convert_function(base_ob, ob.tissue_tessellate, gen_modifiers)
                            for i, sk in enumerate(ob0.data.shape_keys.key_blocks):
                                sk.value = sk_values[i]
                            ## key 1
                            # hide modifiers
                            if not gen_modifiers and len(base_ob.modifiers) > 0:
                                mod_visibility = [m.show_viewport for m in base_ob.modifiers]
                                for m in base_ob.modifiers: m.show_viewport = False
                                base_ob.modifiers.update()
                            base_ob_sk = convert_function(ob0, ob.tissue_tessellate, True)
                            ## combine shapekeys
                            _base_ob.shape_key_add(name='Basis', from_mix=False)
                            _base_ob.shape_key_add(name='Key1', from_mix=False)
                            sk_block = _base_ob.data.shape_keys.key_blocks[1]
                            sk_block.value = 1
                            for vert, sk in zip(base_ob_sk.data.vertices, sk_block.data):
                                sk.co = vert.co
                            bpy.data.objects.remove(base_ob_sk)
                            # set original modifiers
                            if not gen_modifiers and len(base_ob.modifiers) > 0:
                                for i,m in enumerate(base_ob.modifiers):
                                    m.show_viewport = mod_visibility[i]
                                base_ob.modifiers.update()
                        else:
                            _base_ob = convert_function(base_ob, ob.tissue_tessellate, gen_modifiers)
                        bpy.data.objects.remove(base_ob)
                        base_ob = _base_ob
                    # quad tessellation
                    new_ob = tessellate_original(
                            base_ob, ob1, offset, zscale, gen_modifiers,
                            com_modifiers, mode, scale_mode, rotation_mode,
                            rotation_shift, rotation_direction,
                            random_seed, fill_mode, bool_vertex_group,
                            bool_selection, bool_shapekeys, bool_material_id,
                            material_id, normals_mode, bounds_x, bounds_y
                            )

                # if empty or error, continue
                if type(new_ob) is not bpy.types.Object:
                    continue

                # prepare base object
                if iter == 0 and gen_modifiers:
                    temp_base_ob = convert_object_to_mesh(base_ob, True, True)
                    bpy.data.objects.remove(base_ob)
                    base_ob = temp_base_ob
                    iter_objects = [base_ob]

                # rename, make active and change transformations
                new_ob.name = '_tissue_tmp_{}_{}'.format(iter,m_id)
                new_ob.select_set(True)
                context.view_layer.objects.active = new_ob
                new_ob.location = ob_location
                new_ob.matrix_world = ob_matrix_world

                n_components = int(len(new_ob.data.edges) / n_edges1)
                # SELECTION
                if bool_selection:
                    try:
                        # create selection list
                        polygon_selection = [p.select for p in ob1.data.polygons] * int(
                                len(new_ob.data.polygons) / len(ob1.data.polygons))
                        new_ob.data.polygons.foreach_set("select", polygon_selection)
                    except:
                        pass
                if bool_multi_components: same_iteration.append(new_ob)

            base_ob.location = ob_location
            base_ob.matrix_world = ob_matrix_world

            # join together multiple components iterations
            if bool_multi_components:
                if len(same_iteration) > 0:
                    context.view_layer.update()
                    for o in context.view_layer.objects:
                        o.select_set(o in same_iteration)
                    bpy.ops.object.join()
                    new_ob = context.view_layer.objects.active
                    new_ob.select_set(True)
                    #new_ob.data.update()

            if type(new_ob) in (int,str):
                if iter == 0:
                    try:
                        bpy.data.objects.remove(iter_objects[0])
                        iter_objects = []
                    except: continue
                continue

            # Clean last iteration, needed for combine object
            if (bool_selection or bool_material_id) and combine_mode == 'UNUSED':
                # remove faces from last mesh
                bm = bmesh.new()
                last_mesh = iter_objects[-1].data.copy()
                bm.from_mesh(last_mesh)
                bm.faces.ensure_lookup_table()
                if bool_multi_components:
                    remove_materials = matched_materials
                elif bool_material_id:
                    remove_materials = [material_id]
                else: remove_materials = []
                if bool_selection:
                    if bool_multi_components or bool_material_id:
                        remove_faces = [f for f in bm.faces if f.material_index in remove_materials and f.select]
                    else:
                        remove_faces = [f for f in bm.faces if f.select]
                else:
                    remove_faces = [f for f in bm.faces if f.material_index in remove_materials]
                bmesh.ops.delete(bm, geom=remove_faces, context='FACES')
                bm.to_mesh(last_mesh)
                last_mesh.update()
                last_mesh.name = '_tissue_tmp_previous_unused'

                # delete previous iteration if empty or update it
                if len(last_mesh.vertices) > 0:
                    iter_objects[-1].data = last_mesh.copy()
                    iter_objects[-1].data.update()
                else:
                    bpy.data.objects.remove(iter_objects[-1])
                    iter_objects = iter_objects[:-1]
                # set new base object for next iteration
                base_ob = convert_object_to_mesh(new_ob,True,True)
                if iter < iterations-1: new_ob.data = base_ob.data
                # store new iteration and set transformations
                iter_objects.append(new_ob)
                #try:
                #    bpy.data.objects.remove(bpy.data.objects['_tissue_tmp_base'])
                #except:
                #    pass
                base_ob.name = '_tissue_tmp_base'
            elif combine_mode == 'ALL':
                base_ob = new_ob.copy()
                iter_objects.append(new_ob)
            else:
                if base_ob != new_ob:
                    bpy.data.objects.remove(base_ob)
                base_ob = new_ob
                iter_objects = [new_ob]

            # Combine
            if combine_mode != 'LAST' and len(iter_objects)>0:
                if base_ob not in iter_objects and type(base_ob) == bpy.types.Object:
                    bpy.data.objects.remove(base_ob)
                for o in context.view_layer.objects:
                    o.select_set(o in iter_objects)
                bpy.ops.object.join()
                new_ob.data.update()
                iter_objects = [new_ob]

            if merge:
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_mode(
                    use_extend=False, use_expand=False, type='VERT')
                bpy.ops.mesh.select_non_manifold(
                    extend=False, use_wire=True, use_boundary=True,
                    use_multi_face=False, use_non_contiguous=False, use_verts=False)

                bpy.ops.mesh.remove_doubles(
                    threshold=merge_thres, use_unselected=False)

                if bool_dissolve_seams:
                    bpy.ops.mesh.select_mode(type='EDGE')
                    bpy.ops.mesh.select_all(action='DESELECT')
                    bpy.ops.object.mode_set(mode='OBJECT')
                    for e in new_ob.data.edges:
                        e.select = e.use_seam
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.dissolve_edges()
                bpy.ops.object.mode_set(mode='OBJECT')

                if close_mesh != 'NONE':
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_mode(
                        use_extend=False, use_expand=False, type='EDGE')
                    bpy.ops.mesh.select_non_manifold(
                        extend=False, use_wire=False, use_boundary=True,
                        use_multi_face=False, use_non_contiguous=False, use_verts=False)
                    if open_edges_crease != 0:
                        bpy.ops.transform.edge_crease(value=open_edges_crease)
                    if close_mesh == 'CAP':
                        bpy.ops.mesh.edge_face_add()
                    if close_mesh == 'BRIDGE':
                        try:
                            bpy.ops.mesh.bridge_edge_loops(
                                type='PAIRS',
                                number_cuts=bridge_cuts,
                                interpolation='SURFACE',
                                smoothness=bridge_smoothness)
                        except: pass
                    bpy.ops.object.mode_set(mode='OBJECT')
                    for f in new_ob.data.polygons:
                        if f.select: f.material_index = cap_material_index
            base_ob = context.view_layer.objects.active

        # Combine iterations
        if combine_mode != 'LAST' and len(iter_objects)>0:
            #if base_ob not in iter_objects and type(base_ob) == bpy.types.Object:
            #    bpy.data.objects.remove(base_ob)
            for o in context.view_layer.objects:
                o.select_set(o in iter_objects)
            bpy.ops.object.join()
            new_ob = context.view_layer.objects.active
        elif combine_mode == 'LAST' and type(new_ob) != bpy.types.Object:
            # if last iteration gives error, then use the last correct iteration
            try:
                if type(iter_objects[-1]) == bpy.types.Object:
                    new_ob = iter_objects[-1]
            except: pass

        if new_ob == 0:
            #bpy.data.objects.remove(base_ob.data)
            try: bpy.data.objects.remove(base_ob)
            except: pass
            message = "The generated object is an empty geometry!"
            context.view_layer.objects.active = ob
            ob.select_set(True)
            bpy.ops.object.mode_set(mode=starting_mode)
            self.report({'ERROR'}, message)
            return {'CANCELLED'}
        errors = {}
        errors["modifiers_error"] = "Modifiers that change the topology of the mesh \n" \
                                    "after the last Subsurf (or Multires) are not allowed."
        errors["topology_error"] = "Make sure that the topology of the mesh before \n" \
                                    "the last Subsurf (or Multires) is quads only."
        errors["wires_error"] = "Please remove all wire edges in the base object."
        errors["verts_error"] = "Please remove all floating vertices in the base object"
        if new_ob in errors:
            for o in iter_objects:
                try: bpy.data.objects.remove(o)
                except: pass
            try: bpy.data.meshes.remove(data1)
            except: pass
            context.view_layer.objects.active = ob
            ob.select_set(True)
            message = errors[new_ob]
            ob.tissue_tessellate.error_message = message
            bpy.ops.object.mode_set(mode=starting_mode)
            self.report({'ERROR'}, message)
            return {'CANCELLED'}

        #new_ob.location = ob_location
        #new_ob.matrix_world = ob_matrix_world

        # update data and preserve name
        if ob.type != 'MESH':
            loc, matr = ob.location, ob.matrix_world
            ob = convert_object_to_mesh(ob,False,True)
            ob.location, ob.matrix_world = loc, matr
        data_name = ob.data.name
        old_data = ob.data
        #ob.data = bpy.data.meshes.new_from_object(new_ob)#
        ob.data = new_ob.data.copy()
        ob.data.name = data_name
        bpy.data.meshes.remove(old_data)

        # copy vertex group
        if bool_vertex_group:
            for vg in new_ob.vertex_groups:
                if not vg.name in ob.vertex_groups.keys():
                    ob.vertex_groups.new(name=vg.name)
                new_vg = ob.vertex_groups[vg.name]
                for i in range(len(ob.data.vertices)):
                    try:
                        weight = vg.weight(i)
                    except:
                        weight = 0
                    new_vg.add([i], weight, 'REPLACE')

        selected_objects = [o for o in context.selected_objects]
        for o in selected_objects: o.select_set(False)

        ob.select_set(True)
        context.view_layer.objects.active = ob

        if merge:
            try:
                bpy.ops.object.mode_set(mode='EDIT')
                #bpy.ops.mesh.select_mode(
                #    use_extend=False, use_expand=False, type='VERT')
                bpy.ops.mesh.select_mode(type='VERT')
                bpy.ops.mesh.select_non_manifold(
                    extend=False, use_wire=True, use_boundary=True,
                    use_multi_face=False, use_non_contiguous=False, use_verts=False)

                bpy.ops.mesh.remove_doubles(
                    threshold=merge_thres, use_unselected=False)

                bpy.ops.object.mode_set(mode='OBJECT')
                if bool_dissolve_seams:
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_mode(type='EDGE')
                    bpy.ops.mesh.select_all(action='DESELECT')
                    bpy.ops.object.mode_set(mode='OBJECT')
                    for e in ob.data.edges:
                        e.select = e.use_seam
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.dissolve_edges()
            except: pass
            if close_mesh != 'NONE':
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_mode(
                    use_extend=False, use_expand=False, type='EDGE')
                bpy.ops.mesh.select_non_manifold(
                    extend=False, use_wire=False, use_boundary=True,
                    use_multi_face=False, use_non_contiguous=False, use_verts=False)
                if open_edges_crease != 0:
                    bpy.ops.transform.edge_crease(value=open_edges_crease)
                if close_mesh == 'CAP':
                    bpy.ops.mesh.edge_face_add()
                if close_mesh == 'BRIDGE':
                    try:
                        bpy.ops.mesh.bridge_edge_loops(
                            type='PAIRS',
                            number_cuts=bridge_cuts,
                            interpolation='SURFACE',
                            smoothness=bridge_smoothness)
                    except:
                        pass
                bpy.ops.object.mode_set(mode='OBJECT')
                for f in ob.data.polygons:
                    if f.select: f.material_index = cap_material_index
        #else:

        try:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.object.mode_set(mode='OBJECT')
        except: pass

        if bool_smooth: bpy.ops.object.shade_smooth()

        for mesh in bpy.data.meshes:
            if not mesh.users: bpy.data.meshes.remove(mesh)

        for o in selected_objects:
            try: o.select_set(True)
            except: pass

        bpy.ops.object.mode_set(mode=starting_mode)

        ob.tissue_tessellate.error_message = ""

        # Restore Base visibility
        ob0.hide_set(ob0_hide)
        ob0.hide_viewport = ob0_hidev
        ob0.hide_render = ob0_hider
        # Restore Component visibility
        ob1.hide_set(ob1_hide)
        ob1.hide_viewport = ob1_hidev
        ob1.hide_render = ob1_hider
        # Restore Local visibility
        for space, local0, local1 in zip(local_spaces, local_ob0, local_ob1):
            ob0.local_view_set(space, local0)
            ob1.local_view_set(space, local1)

        bpy.data.objects.remove(new_ob)

        # clean objects
        for o in bpy.data.objects:
            #if o.name not in context.view_layer.objects and "_tissue_tmp" in o.name:
            if "_tissue_tmp" in o.name:
                bpy.data.objects.remove(o)

        end_time = time.time()
        print('Tissue: object "{}" tessellated in {:.4f} sec'.format(ob.name, end_time-start_time))
        return {'FINISHED'}

    def check(self, context):
        return True

class TISSUE_PT_tessellate(Panel):
    bl_label = "Tissue Tools"
    bl_category = "Tissue"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    #bl_options = {'DEFAULT_OPEN'}

    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.label(text="Tessellate:")
        col.operator("object.tissue_tessellate")
        col.operator("object.dual_mesh_tessellated")
        col.separator()
        col.operator("object.tissue_refresh_tessellate", icon='FILE_REFRESH')

        col.separator()
        col.label(text="Rotate Faces:")
        row = col.row(align=True)
        row.operator("mesh.tissue_rotate_face_left", text='Left', icon='LOOP_BACK')
        row.operator("mesh.tissue_rotate_face_right", text='Right', icon='LOOP_FORWARDS')

        col.separator()
        col.label(text="Other:")
        col.operator("object.dual_mesh")
        col.operator("object.lattice_along_surface", icon="OUTLINER_OB_LATTICE")

        act = context.object
        if act and act.type == 'MESH':
            col.operator("object.uv_to_mesh", icon="UV")

            if act.mode == 'EDIT':
                col.separator()
                col.label(text="Weight:")
                col.operator("object.tissue_weight_distance", icon="TRACKING")

class TISSUE_PT_tessellate_object(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_label = "Tessellate Settings"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try: return context.object.type == 'MESH'
        except: return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_tessellate
        allowed_obj = ('MESH','CURVE','SURFACE','FONT', 'META')

        try:
            bool_tessellated = props.generator or props.component != None
            ob0 = props.generator
            ob1 = props.component
        except: bool_tessellated = False
        layout = self.layout
        if not bool_tessellated:
            layout.label(text="The selected object is not a Tessellated object",
                        icon='INFO')
        else:
            if props.error_message != "":
                layout.label(text=props.error_message,
                            icon='ERROR')
            col = layout.column(align=True)
            row = col.row(align=True)

            set_tessellate_handler(self,context)
            set_animatable_fix_handler(self,context)
            row.operator("object.tissue_refresh_tessellate", icon='FILE_REFRESH')
            lock_icon = 'LOCKED' if props.bool_lock else 'UNLOCKED'
            #lock_icon = 'PINNED' if props.bool_lock else 'UNPINNED'
            deps_icon = 'LINKED' if props.bool_dependencies else 'UNLINKED'
            row.prop(props, "bool_dependencies", text="", icon=deps_icon)
            row.prop(props, "bool_lock", text="", icon=lock_icon)
            col2 = row.column(align=True)
            col2.prop(props, "bool_run", text="",icon='TIME')
            col2.enabled = not props.bool_lock
            '''
            col = layout.column(align=True)
            row = col.row(align=True)
            row.label(text="Base :")
            row.label(text="Component :")
            row = col.row(align=True)

            col2 = row.column(align=True)
            col2.prop_search(props, "generator", context.scene, "objects")
            row.separator()
            col2 = row.column(align=True)
            col2.prop_search(props, "component", context.scene, "objects")
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(props, "gen_modifiers", text="Use Modifiers", icon='MODIFIER')
            row.separator()
            try:
                if not (ob0.modifiers or ob0.data.shape_keys) or props.fill_mode == 'PATCH':
                    col2.enabled = False
            except:
                col2.enabled = False
            col2 = row.column(align=True)
            col2.prop(props, "com_modifiers", text="Use Modifiers", icon='MODIFIER')
            try:
                if not (props.component.modifiers or props.component.data.shape_keys):
                    col2.enabled = False
            except:
                    col2.enabled = False
            '''
            layout.use_property_split = True
            layout.use_property_decorate = False  # No animation.
            col = layout.column(align=True)
            row = col.row(align=True)
            row.label(text='Base:')
            row.prop_search(props, "generator", context.scene, "objects")
            col2 = row.column(align=True)
            col2.prop(props, "gen_modifiers", text='',icon='MODIFIER')
            try:
                if not (props.generator.modifiers or props.generator.data.shape_keys):
                    col2.enabled = False
            except:
                    col2.enabled = False
            col.separator()
            row = col.row(align=True)
            row.label(text='Component:')
            row.prop_search(props, "component", context.scene, "objects")
            col2 = row.column(align=True)
            col2.prop(props, "com_modifiers", text='',icon='MODIFIER')
            try:
                if not (props.component.modifiers or props.component.data.shape_keys):
                    col2.enabled = False
            except:
                    col2.enabled = False
            layout.use_property_split = False

            # Fill
            col = layout.column(align=True)
            col.label(text="Fill Mode:")

            # fill
            row = col.row(align=True)
            row.prop(props, "fill_mode", icon='NONE', expand=True,
                     slider=True, toggle=False, icon_only=False, event=False,
                     full_event=False, emboss=True, index=-1)

            #layout.use_property_split = True
            col = layout.column(align=True)
            col.prop(props, "bool_smooth")


class TISSUE_PT_tessellate_frame(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_tessellate_object"
    bl_label = "Frame Settings"
    #bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try:
            bool_frame = context.object.tissue_tessellate.fill_mode == 'FRAME'
            bool_tessellated = context.object.tissue_tessellate.generator != None
            return context.object.type == 'MESH' and bool_frame and bool_tessellated
        except:
            return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_tessellate
        allowed_obj = ('MESH','CURVE','SURFACE','FONT', 'META')

        try:
            bool_tessellated = props.generator or props.component != None
            ob0 = props.generator
            ob1 = props.component
        except: bool_tessellated = False
        layout = self.layout
        if bool_tessellated:
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(props, "frame_mode", expand=True)
            row = col.row(align=True)
            row.prop(props, "frame_thickness", icon='NONE', expand=True)
            row = col.row(align=True)
            row.prop(props, "fill_frame", icon='NONE')
            show_frame_mat = props.bool_multi_components or props.bool_material_id
            if props.fill_frame and show_frame_mat:
                row.prop(props, "fill_frame_mat", icon='NONE')
            row = col.row(align=True)
            row.prop(props, "frame_boundary", text='Boundary', icon='NONE')
            if props.frame_boundary and show_frame_mat:
                row.prop(props, "frame_boundary_mat", icon='NONE')


class TISSUE_PT_tessellate_coordinates(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_tessellate_object"
    bl_label = "Component Coordinates"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try:
            bool_tessellated = context.object.tissue_tessellate.generator != None
            return context.object.type == 'MESH' and bool_tessellated
        except:
            return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_tessellate
        allowed_obj = ('MESH','CURVE','SURFACE','FONT', 'META')

        try:
            bool_tessellated = props.generator or props.component != None
            ob0 = props.generator
            ob1 = props.component
        except: bool_tessellated = False
        layout = self.layout
        if bool_tessellated:
            col = layout.column(align=True)
            # component XY
            row = col.row(align=True)
            row.prop(props, "mode", expand=True)

            if props.mode != 'BOUNDS':
                col.separator()
                row = col.row(align=True)
                row.label(text="X:")
                row.prop(
                    props, "bounds_x", text="Bounds X", icon='NONE', expand=True,
                    slider=False, toggle=False, icon_only=False, event=False,
                    full_event=False, emboss=True, index=-1)

                row = col.row(align=True)
                row.label(text="Y:")
                row.prop(
                    props, "bounds_y", text="Bounds X", icon='NONE', expand=True,
                    slider=False, toggle=False, icon_only=False, event=False,
                    full_event=False, emboss=True, index=-1)


class TISSUE_PT_tessellate_rotation(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_tessellate_object"
    bl_label = "Rotation"
    bl_options = {'DEFAULT_CLOSED'}


    @classmethod
    def poll(cls, context):
        try:
            bool_tessellated = context.object.tissue_tessellate.generator != None
            return context.object.type == 'MESH' and bool_tessellated
        except:
            return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_tessellate
        allowed_obj = ('MESH','CURVE','SURFACE','FONT', 'META')

        try:
            bool_tessellated = props.generator or props.component != None
            ob0 = props.generator
            ob1 = props.component
        except: bool_tessellated = False
        layout = self.layout
        if bool_tessellated:
            # rotation
            layout.use_property_split = True
            layout.use_property_decorate = False  # No animation.
            col = layout.column(align=True)
            col.prop(props, "rotation_mode", text='Rotation', icon='NONE', expand=False,
                     slider=True, toggle=False, icon_only=False, event=False,
                     full_event=False, emboss=True, index=-1)
            if props.rotation_mode == 'WEIGHT':
                col.prop(props, "rotation_direction", expand=False,
                          slider=True, toggle=False, icon_only=False, event=False,
                          full_event=False, emboss=True, index=-1)
            if props.rotation_mode == 'RANDOM':
                col.prop(props, "random_seed")
            else:
                col.prop(props, "rotation_shift")

            if props.rotation_mode == 'UV':
                uv_error = False
                if props.generator.type != 'MESH':
                    row = col.row(align=True)
                    row.label(
                        text="UV rotation supported only for Mesh objects",
                        icon='ERROR')
                    uv_error = True
                else:
                    if len(props.generator.data.uv_layers) == 0:
                        row = col.row(align=True)
                        row.label(text="'" + props.generator.name +
                                  " doesn't have UV Maps", icon='ERROR')
                        uv_error = True
                if uv_error:
                    row = col.row(align=True)
                    row.label(text="Default rotation will be used instead",
                              icon='INFO')

class TISSUE_PT_tessellate_thickness(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_tessellate_object"
    bl_label = "Thickness"
    #bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try:
            bool_tessellated = context.object.tissue_tessellate.generator != None
            return context.object.type == 'MESH' and bool_tessellated
        except:
            return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_tessellate
        allowed_obj = ('MESH','CURVE','SURFACE','FONT', 'META')

        try:
            bool_tessellated = props.generator or props.component != None
            ob0 = props.generator
            ob1 = props.component
        except: bool_tessellated = False
        layout = self.layout
        #layout.use_property_split = True
        if bool_tessellated:
            col = layout.column(align=True)
            # component Z
            row = col.row(align=True)
            row.prop(props, "scale_mode", expand=True)
            col.prop(props, "zscale", text="Scale", icon='NONE', expand=False,
                     slider=True, toggle=False, icon_only=False, event=False,
                     full_event=False, emboss=True, index=-1)
            if props.mode == 'BOUNDS':
                col.prop(props, "offset", text="Offset", icon='NONE', expand=False,
                         slider=True, toggle=False, icon_only=False, event=False,
                         full_event=False, emboss=True, index=-1)

            # Direction
            col = layout.column(align=True)
            row = col.row(align=True)
            row.label(text="Direction:")
            row = col.row(align=True)
            row.prop(
            props, "normals_mode", text="Direction", icon='NONE', expand=True,
                slider=False, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)


class TISSUE_PT_tessellate_options(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_tessellate_object"
    bl_label = " "
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try:
            bool_tessellated = context.object.tissue_tessellate.generator != None
            return context.object.type == 'MESH' and bool_tessellated
        except:
            return False

    def draw_header(self, context):
        ob = context.object
        props = ob.tissue_tessellate
        self.layout.prop(props, "merge")

    def draw(self, context):
        ob = context.object
        props = ob.tissue_tessellate
        allowed_obj = ('MESH','CURVE','SURFACE','FONT', 'META')

        try:
            bool_tessellated = props.generator or props.component != None
            ob0 = props.generator
            ob1 = props.component
        except: bool_tessellated = False
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.
        if bool_tessellated:
            col = layout.column(align=True)
            if props.merge:
                col.prop(props, "merge_thres")
                col.prop(props, "bool_dissolve_seams")
                col.prop(props, "close_mesh")
                if props.close_mesh != 'NONE':
                    #row = col.row(align=True)
                    col.separator()
                    col.prop(props, "open_edges_crease", text="Crease")
                    col.prop(props, "cap_material_index", text='Material Index')
                    if props.close_mesh == 'BRIDGE':
                        col.separator()
                        col.prop(props, "bridge_cuts")
                        col.prop(props, "bridge_smoothness")


class TISSUE_PT_tessellate_morphing(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_tessellate_object"
    bl_label = "Weight and Morphing"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try:
            bool_tessellated = context.object.tissue_tessellate.generator != None
            return context.object.type == 'MESH' and bool_tessellated
        except:
            return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_tessellate
        allowed_obj = ('MESH','CURVE','SURFACE','FONT', 'META')

        try:
            bool_tessellated = props.generator or props.component != None
            ob0 = props.generator
            ob1 = props.component
        except: bool_tessellated = False
        layout = self.layout
        if bool_tessellated:
            allow_shapekeys = not props.com_modifiers
            for m in ob0.data.materials:
                try:
                    o = bpy.data.objects[m.name]
                    allow_multi = True
                    try:
                        if o.data.shape_keys is None: continue
                        elif len(o.data.shape_keys.key_blocks) < 2: continue
                        else: allow_shapekeys = not props.com_modifiers
                    except: pass
                except: pass
            col = layout.column(align=True)
            #col.label(text="Morphing:")
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(props, "bool_vertex_group", icon='GROUP_VERTEX')
            #col2.prop_search(props, "vertex_group", props.generator, "vertex_groups")
            try:
                if len(props.generator.vertex_groups) == 0:
                    col2.enabled = False
            except:
                col2.enabled = False
            row.separator()
            col2 = row.column(align=True)
            row2 = col2.row(align=True)
            row2.prop(props, "bool_shapekeys", text="Use Shape Keys",  icon='SHAPEKEY_DATA')
            row2.enabled = allow_shapekeys
            if not allow_shapekeys:
                col2 = layout.column(align=True)
                row2 = col2.row(align=True)
                row2.label(text="Use Shape Keys is not compatible with Use Modifiers", icon='INFO')


class TISSUE_PT_tessellate_selective(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_tessellate_object"
    bl_label = "Selective"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try:
            bool_tessellated = context.object.tissue_tessellate.generator != None
            return context.object.type == 'MESH' and bool_tessellated
        except:
            return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_tessellate
        allowed_obj = ('MESH','CURVE','SURFACE','FONT', 'META')

        try:
            bool_tessellated = props.generator or props.component != None
            ob0 = props.generator
            ob1 = props.component
        except: bool_tessellated = False
        layout = self.layout
        if bool_tessellated:
            allow_multi = False
            allow_shapekeys = not props.com_modifiers
            for m in ob0.data.materials:
                try:
                    o = bpy.data.objects[m.name]
                    allow_multi = True
                    try:
                        if o.data.shape_keys is None: continue
                        elif len(o.data.shape_keys.key_blocks) < 2: continue
                        else: allow_shapekeys = not props.com_modifiers
                    except: pass
                except: pass
            # LIMITED TESSELLATION
            col = layout.column(align=True)
            #col.label(text="Limited Tessellation:")
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(props, "bool_selection", text="On selected Faces", icon='RESTRICT_SELECT_OFF')
            row.separator()
            if props.generator.type != 'MESH':
                col2.enabled = False
            col2 = row.column(align=True)
            col2.prop(props, "bool_material_id", icon='MATERIAL_DATA', text="Material ID")
            if props.bool_material_id and not props.bool_multi_components:
                #col2 = row.column(align=True)
                col2.prop(props, "material_id")
            if props.bool_multi_components:
                col2.enabled = False

            col.separator()
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(props, "bool_multi_components", icon='MOD_TINT')
            if not allow_multi:
                col2.enabled = False


class TISSUE_PT_tessellate_iterations(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_tessellate_object"
    bl_label = "Iterations"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try:
            bool_tessellated = context.object.tissue_tessellate.generator != None
            return context.object.type == 'MESH' and bool_tessellated
        except:
            return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_tessellate
        allowed_obj = ('MESH','CURVE','SURFACE','FONT', 'META')

        try:
            bool_tessellated = props.generator or props.component != None
            ob0 = props.generator
            ob1 = props.component
        except: bool_tessellated = False
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.
        if bool_tessellated:
            col = layout.column(align=True)
            row = col.row(align=True)
            #row.label(text='', icon='FILE_REFRESH')
            col.prop(props, 'iterations', text='Repeat')#, icon='FILE_REFRESH')
            if props.iterations > 1 and props.fill_mode == 'PATCH':
                col.separator()
                #row = col.row(align=True)
                col.prop(props, 'patch_subs')
            layout.use_property_split = False
            col = layout.column(align=True)
            #row = col.row(align=True)
            col.label(text='Combine Iterations:')
            row = col.row(align=True)
            row.prop(
                props, "combine_mode", text="Combine:",icon='NONE', expand=True,
                slider=False, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)

class tissue_rotate_face_right(Operator):
    bl_idname = "mesh.tissue_rotate_face_right"
    bl_label = "Rotate Faces Right"
    bl_description = "Rotate clockwise selected faces and update tessellated meshes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            #bool_tessellated = context.object.tissue_tessellate.generator != None
            ob = context.object
            return ob.type == 'MESH' and ob.mode == 'EDIT'# and bool_tessellated
        except:
            return False

    def execute(self, context):
        ob = context.active_object
        me = ob.data

        bm = bmesh.from_edit_mesh(me)
        mesh_select_mode = [sm for sm in context.tool_settings.mesh_select_mode]

        for face in bm.faces:
            if (face.select):
                vs = face.verts[:]
                vs2 = vs[-1:]+vs[:-1]
                material_index = face.material_index
                bm.faces.remove(face)
                f2 = bm.faces.new(vs2)
                f2.select = True
                f2.material_index = material_index
                bm.normal_update()

        # trigger UI update
        bmesh.update_edit_mesh(me)
        ob.select_set(False)

        # update tessellated meshes
        bpy.ops.object.mode_set(mode='OBJECT')
        for o in [obj for obj in bpy.data.objects if
                  obj.tissue_tessellate.generator == ob and obj.visible_get()]:
            context.view_layer.objects.active = o
            bpy.ops.object.tissue_update_tessellate()
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='EDIT')
        context.tool_settings.mesh_select_mode = mesh_select_mode

        return {'FINISHED'}

class tissue_rotate_face_left(Operator):
    bl_idname = "mesh.tissue_rotate_face_left"
    bl_label = "Rotate Faces Left"
    bl_description = "Rotate counterclockwise selected faces and update tessellated meshes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            #bool_tessellated = context.object.tissue_tessellate.generator != None
            ob = context.object
            return ob.type == 'MESH' and ob.mode == 'EDIT'# and bool_tessellated
        except:
            return False

    def execute(self, context):
        ob = context.active_object
        me = ob.data

        bm = bmesh.from_edit_mesh(me)
        mesh_select_mode = [sm for sm in context.tool_settings.mesh_select_mode]

        for face in bm.faces:
            if (face.select):
                vs = face.verts[:]
                vs2 = vs[1:]+vs[:1]
                material_index = face.material_index
                bm.faces.remove(face)
                f2 = bm.faces.new(vs2)
                f2.select = True
                f2.material_index = material_index
                bm.normal_update()

        # trigger UI update
        bmesh.update_edit_mesh(me)
        ob.select_set(False)

        # update tessellated meshes
        bpy.ops.object.mode_set(mode='OBJECT')
        for o in [obj for obj in bpy.data.objects if
                  obj.tissue_tessellate.generator == ob and obj.visible_get()]:
            context.view_layer.objects.active = o
            bpy.ops.object.tissue_update_tessellate()
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='EDIT')
        context.tool_settings.mesh_select_mode = mesh_select_mode

        return {'FINISHED'}


def convert_to_frame(ob, props, use_modifiers):
    new_ob = convert_object_to_mesh(ob, use_modifiers, True)

    # create bmesh
    bm = bmesh.new()
    bm.from_mesh(new_ob.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    if props.bool_selection:
        original_faces = [f for f in bm.faces if f.select]
    else:
        original_faces = list(bm.faces)
    # detect edge loops

    loops = []
    boundaries_mat = []
    neigh_face_center = []
    face_normals = []
    # append boundary loops
    if props.frame_boundary:
        #selected_edges = [e for e in bm.edges if e.select]
        selected_edges = [e for e in bm.edges if e.is_boundary]
        if len(selected_edges) > 0:
            loop = []
            count = 0
            e0 = selected_edges[0]
            face = e0.link_faces[0]
            boundary_mat = [face.material_index]
            face_center = [face.calc_center_median()]
            loop_normals = [face.normal]
            selected_edges = selected_edges[1:]
            if props.bool_vertex_group:
                n_verts = len(new_ob.data.vertices)
                base_vg = [get_weight(vg,n_verts) for vg in new_ob.vertex_groups]
                '''
                base_vg = []
                for vg in new_ob.vertex_groups:
                    vertex_group = []
                    for v in bm.verts:
                        try:
                            vertex_group.append(vg.weight(v.index))
                        except:
                            vertex_group.append(0)
                    base_vg.append(vertex_group)
                '''
            while True:
                new_vert = None
                face = None
                for e1 in selected_edges:
                    if e1.verts[0] in e0.verts: new_vert = e1.verts[1]
                    elif e1.verts[1] in e0.verts: new_vert = e1.verts[0]
                    if new_vert != None:
                        if len(loop)==0:
                            loop = [v for v in e1.verts if v != new_vert]
                        loop.append(new_vert)
                        e0 = e1
                        face = e0.link_faces[0]
                        boundary_mat.append(face.material_index)
                        face_center.append(face.calc_center_median())
                        loop_normals.append(face.normal)
                        selected_edges.remove(e0)
                        break
                if new_vert == None:
                    try:
                        loops.append(loop)
                        loop = []
                        e0 = selected_edges[0]
                        selected_edges = selected_edges[1:]
                        boundaries_mat.append(boundary_mat)
                        neigh_face_center.append(face_center)
                        face_normals.append(loop_normals)
                        face = e0.link_faces[0]
                        boundary_mat = [face.material_index]
                        face_center = [face.calc_center_median()]
                        loop_normals = [face.normal]
                    except: break
            boundaries_mat.append(boundary_mat)
            neigh_face_center.append(face_center)
            face_normals.append(loop_normals)
    # compute boundary frames
    new_faces = []
    vert_ids = []

    # append regular faces
    for f in original_faces:#bm.faces:
        loop = list(f.verts)
        loops.append(loop)
        boundaries_mat.append([f.material_index for v in loop])
        face_normals.append([f.normal for v in loop])

    # calc areas for relative frame mode
    if props.frame_mode == 'RELATIVE':
        verts_area = []
        for v in bm.verts:
            linked_faces = v.link_faces
            if len(linked_faces) > 0:
                area = sum([sqrt(f.calc_area())/len(f.verts) for f in v.link_faces])*2
                area /= len(linked_faces)
            else: area = 0
            verts_area.append(area)

    for loop_index, loop in enumerate(loops):
        is_boundary = loop_index < len(neigh_face_center)
        materials = boundaries_mat[loop_index]
        new_loop = []
        loop_ext = [loop[-1]] + loop + [loop[0]]

        # calc tangents
        tangents = []
        for i in range(len(loop)):
            # vertices
            vert0 = loop_ext[i]
            vert = loop_ext[i+1]
            vert1 = loop_ext[i+2]
            # edge vectors
            vec0 = (vert0.co - vert.co).normalized()
            vec1 = (vert.co - vert1.co).normalized()
            # tangent
            _vec1 = -vec1
            _vec0 = -vec0
            ang = (pi - vec0.angle(vec1))/2
            normal = face_normals[loop_index][i]
            tan0 = normal.cross(vec0)
            tan1 = normal.cross(vec1)
            tangent = (tan0 + tan1).normalized()/sin(ang)*props.frame_thickness
            tangents.append(tangent)

        # calc correct direction for boundaries
        mult = -1
        if is_boundary:
            dir_val = 0
            for i in range(len(loop)):
                surf_point = neigh_face_center[loop_index][i]
                tangent = tangents[i]
                vert = loop_ext[i+1]
                dir_val += tangent.dot(vert.co - surf_point)
            if dir_val > 0: mult = 1

        # add vertices
        for i in range(len(loop)):
            vert = loop_ext[i+1]
            if props.frame_mode == 'RELATIVE': area = verts_area[vert.index]
            else: area = 1
            new_co = vert.co + tangents[i] * mult * area
            # add vertex
            new_vert = bm.verts.new(new_co)
            new_loop.append(new_vert)
            vert_ids.append(vert.index)
        new_loop.append(new_loop[0])

        # add faces
        materials += [materials[0]]
        for i in range(len(loop)):
             v0 = loop_ext[i+1]
             v1 = loop_ext[i+2]
             v2 = new_loop[i+1]
             v3 = new_loop[i]
             face_verts = [v1,v0,v3,v2]
             if mult == -1: face_verts = [v0,v1,v2,v3]
             new_face = bm.faces.new(face_verts)
             new_face.material_index = materials[i+1] + props.frame_boundary_mat
             new_face.select = True
             new_faces.append(new_face)
        # fill frame
        if props.fill_frame and not is_boundary:
            n_verts = len(new_loop)-1
            loop_center = Vector((0,0,0))
            for v in new_loop[1:]: loop_center += v.co
            loop_center /= n_verts
            center = bm.verts.new(loop_center)
            for i in range(n_verts):
                v0 = new_loop[i+1]
                v1 = new_loop[i]
                face_verts = [v1,v0,center]
                new_face = bm.faces.new(face_verts)
                new_face.material_index = materials[i] + props.frame_boundary_mat
                new_face.select = True
                new_faces.append(new_face)
    bpy.ops.object.mode_set(mode='OBJECT')
    #for f in bm.faces: f.select_set(f not in new_faces)
    for f in original_faces: bm.faces.remove(f)
    bm.to_mesh(new_ob.data)
    # propagate vertex groups
    if props.bool_vertex_group:
        base_vg = []
        for vg in new_ob.vertex_groups:
            vertex_group = []
            for v in bm.verts:
                try:
                    vertex_group.append(vg.weight(v.index))
                except:
                    vertex_group.append(0)
            base_vg.append(vertex_group)
        new_vert_ids = range(len(bm.verts)-len(vert_ids),len(bm.verts))
        for vg_id, vg in enumerate(new_ob.vertex_groups):
            for ii, jj in zip(vert_ids, new_vert_ids):
                vg.add([jj], base_vg[vg_id][ii], 'REPLACE')
    new_ob.data.update()
    return new_ob

def convert_to_fan(ob, props, use_modifiers):
    new_ob = convert_object_to_mesh(ob, use_modifiers, True)
    # make base object selected and active
    for o in bpy.context.view_layer.objects: o.select_set(False)
    new_ob.select_set(True)
    bpy.context.view_layer.objects.active = new_ob
    sk_index0 = new_ob.active_shape_key_index
    new_ob.active_shape_key_index = 0

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='FACE')
    if not props.bool_selection:
        bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.poke()
    bpy.ops.object.mode_set(mode='OBJECT')
    return new_ob
