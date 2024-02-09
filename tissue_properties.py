# SPDX-License-Identifier: GPL-2.0-or-later

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
from .utils import tissue_time
from . import config
import time


def update_dependencies(ob, objects):
    type = ob.tissue.tissue_type
    if type == 'NONE': return objects
    if ob.tissue.bool_dependencies:
        deps = get_deps(ob)
        for o in deps:
            if o.tissue.tissue_type == 'NONE' or o.tissue.bool_lock or o in objects:
                continue
            objects.append(o)
            objects = update_dependencies(o, objects)
    return objects

def get_deps(ob):
    type = ob.tissue.tissue_type
    if type == 'TESSELLATE':
        return [ob.tissue_tessellate.generator, ob.tissue_tessellate.component]
    elif type == 'TO_CURVE':
        return [ob.tissue_to_curve.object]
    elif type == 'POLYHEDRA':
        return [ob.tissue_polyhedra.object]
    else: return []

def anim_tessellate_active(self, context):
    ob = context.object
    props = ob.tissue_tessellate
    if not (ob.tissue.bool_lock or props.bool_hold):
        try:
            props.generator.name
            if props.component_mode == 'OBJECT':
                props.component.name
            elif props.component_mode == 'COLLECTION':
                props.component_coll.name
            bpy.ops.object.tissue_update_tessellate()
        except: pass

def anim_tessellate_object(ob):
    try:
        #bpy.context.view_layer.objects.active = ob
        bpy.ops.object.tissue_update_tessellate()
    except:
        return None

#from bpy.app.handlers import persistent


def anim_tissue(scene, depsgraph=None):
    tissue_time(None,'Tissue: Animating Tissue objects at frame {}...'.format(scene.frame_current), levels=0)
    start_time = time.time()

    try:
        active_object = bpy.context.object
        old_mode = bpy.context.object.mode
        selected_objects = bpy.context.selected_objects
    except: active_object = old_mode = selected_objects = None

    if old_mode in ('OBJECT', 'PAINT_WEIGHT'):
        update_objects = []
        for ob in scene.objects:
            if ob.tissue.bool_run and not ob.tissue.bool_lock:
                if ob not in update_objects: update_objects.append(ob)
                update_objects = list(reversed(update_dependencies(ob, update_objects)))
        for ob in update_objects:
            #override = {'object': ob}
            for window in bpy.context.window_manager.windows:
                screen = window.screen
                for area in screen.areas:
                    if area.type == 'VIEW_3D':
                        override = bpy.context.copy()
                        override['window'] = window
                        override['screen'] = screen
                        override['area'] = area
                        override['selected_objects'] = [ob]
                        override['object'] = ob
                        override['active_object'] = ob
                        override['selected_editable_objects'] = [ob]
                        override['mode'] = 'OBJECT'
                        override['view_layer'] = scene.view_layers[0]
                        break
            with bpy.context.temp_override(**override):
                if ob.tissue.tissue_type == 'TESSELLATE':
                    bpy.ops.object.tissue_update_tessellate()
                elif ob.tissue.tissue_type == 'TO_CURVE':
                    bpy.ops.object.tissue_update_convert_to_curve()
                elif ob.tissue.tissue_type == 'POLYHEDRA':
                    bpy.ops.object.tissue_update_polyhedra()
                elif ob.tissue.tissue_type == 'CONTOUR_CURVES':
                    bpy.ops.object.tissue_update_contour_curves()

        if old_mode != None:
            objects = bpy.context.view_layer.objects
            objects.active = active_object
            for o in objects: o.select_set(o in selected_objects)
            bpy.ops.object.mode_set(mode=old_mode)

    config.evaluatedDepsgraph = None
    tissue_time(start_time,'Animated Tissue objects at frame {}'.format(scene.frame_current), levels=0)
    return

def remove_tissue_handler():
    tissue_handlers = []
    blender_handlers = bpy.app.handlers.frame_change_post
    for h in blender_handlers:
        if "anim_tissue" in str(h):
            tissue_handlers.append(h)
    for h in tissue_handlers: blender_handlers.remove(h)

def set_tissue_handler(self, context):
    remove_tissue_handler()
    for o in context.scene.objects:
        if o.tissue.bool_run:
            blender_handlers = bpy.app.handlers.frame_change_post
            blender_handlers.append(anim_tissue)
            break
    return

def remove_polyhedra_handler():
    tissue_handlers = []
    blender_handlers = bpy.app.handlers.frame_change_post
    for h in blender_handlers:
        if "anim_polyhedra" in str(h):
            tissue_handlers.append(h)
    for h in tissue_handlers: blender_handlers.remove(h)

def set_polyhedra_handler(self, context):
    remove_polyhedra_handler()
    for o in context.scene.objects:
        if o.tissue.bool_run:
            blender_handlers = bpy.app.handlers.frame_change_post
            blender_handlers.append(anim_polyhedra)
            break
    return


class tissue_prop(PropertyGroup):
    bool_lock : BoolProperty(
        name="Lock",
        description="Prevent automatic update on settings changes or if other objects have it in the hierarchy.",
        default=False
        )
    bool_dependencies : BoolProperty(
        name="Update Dependencies",
        description="Automatically updates source objects, when possible",
        default=False
        )
    bool_run : BoolProperty(
        name="Animatable",
        description="Automatically recompute the geometry when the frame is changed. Tessellations may not work using the default Render Animation",
        default = False,
        update = set_tissue_handler
        )
    tissue_type : EnumProperty(
        items=(
                ('NONE', "None", ""),
                ('TESSELLATE', "Tessellate", ""),
                ('TO_CURVE', "To Curve", ""),
                ('POLYHEDRA', "Polyhedra", ""),
                ('CONTOUR_CURVES', "Contour Curves", "")
                ),
        default='NONE',
        name=""
        )
    bool_hold : BoolProperty(
            name="Hold",
            description="Wait...",
            default=False
        )

class tissue_tessellate_prop(PropertyGroup):
    bool_hold : BoolProperty(
        name="Hold",
        description="Wait...",
        default=False
        )
    zscale : FloatProperty(
        name="Scale", default=1, soft_min=0, soft_max=10,
        description="Scale factor for the component thickness",
        update = anim_tessellate_active
        )
    component_mode : EnumProperty(
        items=(
                ('OBJECT', "Object", "Use the same component object for all the faces"),
                ('COLLECTION', "Collection", "Use multiple components from Collection"),
                ('MATERIALS', "Materials", "Use multiple components by materials name")
                ),
        default='OBJECT',
        name="Component Mode",
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
               ('WEIGHT', "Weight Gradient", "Rotate according to Vertex Group gradient"),
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
            ('TRI', 'Tri', 'Triangulate the base mesh'),
            ('QUAD', 'Quad', 'Regular quad tessellation. Uses only 3 or 4 vertices'),
            ('FAN', 'Fan', 'Radial tessellation for polygonal faces'),
            ('PATCH', 'Patch', 'Curved tessellation according to the last ' +
            'Subsurf\n(or Multires) modifiers. Works only with 4 sides ' +
            'patches.\nAfter the last Subsurf (or Multires) only ' +
            'deformation\nmodifiers can be used'),
            ('FRAME', 'Frame', 'Tessellation along the edges of each face')),
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
        default=True,
        description="Apply Modifiers and Shape Keys to the base object",
        update = anim_tessellate_active
        )
    com_modifiers : BoolProperty(
        name="Component Modifiers",
        default=True,
        description="Apply Modifiers and Shape Keys to the component object",
        update = anim_tessellate_active
        )
    merge : BoolProperty(
        name="Merge",
        default=False,
        description="Merge vertices in adjacent duplicates",
        update = anim_tessellate_active
        )
    merge_open_edges_only : BoolProperty(
        name="Open edges only",
        default=False,
        description="Merge only open edges",
        update = anim_tessellate_active
        )
    merge_thres : FloatProperty(
        name="Distance",
        default=0.0001,
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
    component_coll : PointerProperty(
        type=bpy.types.Collection,
        name="",
        description="Use objects inside the collection",
        #default="",
        update = anim_tessellate_active
        )
    target : PointerProperty(
        type=bpy.types.Object,
        name="",
        description="Target object for custom direction",
        #default="",
        update = anim_tessellate_active
        )
    even_thickness : BoolProperty(
        name="Even Thickness",
        default=False,
        description="Iterative sampling method for determine the correct length of the vectors (Experimental)",
        update = anim_tessellate_active
        )
    even_thickness_iter : IntProperty(
        name="Even Thickness Iterations",
        default=3,
        min = 1,
        soft_max = 20,
        description="More iterations produces more accurate results but make the tessellation slower",
        update = anim_tessellate_active
        )
    bool_random : BoolProperty(
        name="Randomize",
        default=False,
        description="Randomize component rotation",
        update = anim_tessellate_active
        )
    rand_seed : IntProperty(
        name="Seed",
        default=0,
        soft_min=0,
        soft_max=50,
        description="Random seed",
        update = anim_tessellate_active
        )
    coll_rand_seed : IntProperty(
        name="Seed",
        default=0,
        soft_min=0,
        soft_max=50,
        description="Random seed",
        update = anim_tessellate_active
        )
    rand_step : IntProperty(
        name="Steps",
        default=1,
        min=1,
        soft_max=2,
        description="Random step",
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
        name="Index",
        default=0,
        min=0,
        description="Only the faces with the chosen Material Index will be used",
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
            ('FACES', 'Faces', 'Based on individual faces normal'),
            ('CUSTOM', 'Custom', 'Custom split normals'),
            ('SHAPEKEYS', 'Keys', "According to base object's shape keys"),
            ('OBJECT', 'Object', "According to a target object")),
        default='VERTS',
        name="Direction",
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
    warning_message_thickness : StringProperty(
        name="Warning Message Thickness",
        default=""
        )
    warning_message_merge : StringProperty(
        name="Warning Message Merge",
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
                ('BRIDGE', 'Bridge Open Loops', 'Automatically bridge loop pairs'),
                ('BRIDGE_CAP', 'Custom', 'Bridge loop pairs and cap holes according to vertex groups')),
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
    boundary_mat_offset : IntProperty(
            name="Material Offset",
            default=0,
            description="Material Offset for boundaries (with components based on Materials)",
            update = anim_tessellate_active
            )
    fill_frame_mat : IntProperty(
            name="Material Offset",
            default=0,
            description="Material Offset for inner faces (with components based on Materials)",
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
    bridge_edges_crease : FloatProperty(
            name="Bridge Edges Crease",
            default=0,
            min=0,
            max=1,
            description="Automatically set crease for bridge edges",
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
            soft_max=1,
            description="Frame Thickness",
            update = anim_tessellate_active
            )
    frame_boundary_thickness : FloatProperty(
            name="Frame Boundary Thickness",
            default=0,
            min=0,
            soft_max=1,
            description="Frame Boundary Thickness (when zero it uses the Frame Thickness instead)",
            update = anim_tessellate_active
            )
    frame_mode : EnumProperty(
            items=(
                ('CONSTANT', 'Constant', 'Even thickness'),
                ('RELATIVE', 'Relative', 'Frame offset depends on face areas'),
                ('CENTER', 'Center', 'Toward the center of the face (uses Incenter for Triangles)')),
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
    cap_material_offset : IntProperty(
            name="Material Offset",
            default=0,
            min=0,
            description="Material index offset for the cap faces",
            update = anim_tessellate_active
            )
    bridge_material_offset : IntProperty(
            name="Material Offset",
            default=0,
            min=0,
            description="Material index offset for the bridge faces",
            update = anim_tessellate_active
            )
    patch_subs : IntProperty(
            name="Patch Subdivisions",
            default=0,
            min=0,
            description="Subdivisions levels for Patch tessellation after the first iteration",
            update = anim_tessellate_active
            )
    use_origin_offset : BoolProperty(
            name="Align to Origins",
            default=True,
            description="Define offset according to components origin and local Z coordinate",
            update = anim_tessellate_active
            )

    vertex_group_thickness : StringProperty(
            name="Thickness weight", default='',
            description="Vertex Group used for thickness",
            update = anim_tessellate_active
            )
    invert_vertex_group_thickness : BoolProperty(
            name="Invert", default=False,
            description="Invert the vertex group influence",
            update = anim_tessellate_active
            )
    vertex_group_thickness_factor : FloatProperty(
            name="Factor",
            default=0,
            min=0,
            max=1,
            description="Thickness factor to use for zero vertex group influence",
            update = anim_tessellate_active
            )

    vertex_group_frame_thickness : StringProperty(
            name="Frame Thickness weight", default='',
            description="Vertex Group used for frame thickness",
            update = anim_tessellate_active
            )
    invert_vertex_group_frame_thickness : BoolProperty(
            name="Invert", default=False,
            description="Invert the vertex group influence",
            update = anim_tessellate_active
            )
    vertex_group_frame_thickness_factor : FloatProperty(
            name="Factor",
            default=0,
            min=0,
            max=1,
            description="Frame thickness factor to use for zero vertex group influence",
            update = anim_tessellate_active
            )
    face_weight_frame : BoolProperty(
            name="Face Weight",
            default=True,
            description="Uniform weight for individual faces",
            update = anim_tessellate_active
            )

    vertex_group_cap_owner : EnumProperty(
            items=(
                ('BASE', 'Base', 'Use base vertex group'),
                ('COMP', 'Component', 'Use component vertex group')),
            default='COMP',
            name="Source",
            update = anim_tessellate_active
            )
    vertex_group_cap : StringProperty(
            name="Cap Vertex Group", default='',
            description="Vertex Group used for cap open edges",
            update = anim_tessellate_active
            )
    invert_vertex_group_cap : BoolProperty(
            name="Invert", default=False,
            description="Invert the vertex group influence",
            update = anim_tessellate_active
            )

    vertex_group_bridge_owner : EnumProperty(
            items=(
                ('BASE', 'Base', 'Use base vertex group'),
                ('COMP', 'Component', 'Use component vertex group')),
            default='COMP',
            name="Source",
            update = anim_tessellate_active
            )
    vertex_group_bridge : StringProperty(
            name="Bridge Vertex Group", default='',
            description="Vertex Group used for bridge open edges",
            update = anim_tessellate_active
            )
    invert_vertex_group_bridge : BoolProperty(
            name="Invert", default=False,
            description="Invert the vertex group influence",
            update = anim_tessellate_active
            )

    vertex_group_rotation : StringProperty(
            name="Rotation weight", default='',
            description="Vertex Group used for rotation",
            update = anim_tessellate_active
            )
    invert_vertex_group_rotation : BoolProperty(
            name="Invert", default=False,
            description="Invert the vertex group influence",
            update = anim_tessellate_active
            )
    smooth_normals : BoolProperty(
            name="Smooth Normals", default=False,
            description="Smooth normals of the surface in order to reduce intersections",
            update = anim_tessellate_active
            )
    smooth_normals_iter : IntProperty(
            name="Iterations",
            default=5,
            min=0,
            description="Smooth iterations",
            update = anim_tessellate_active
            )
    smooth_normals_uv : FloatProperty(
            name="UV Anisotropy",
            default=0,
            min=-1,
            max=1,
            description="0 means no anisotropy, -1 represent the U direction, while 1 represent the V direction",
            update = anim_tessellate_active
            )
    vertex_group_smooth_normals : StringProperty(
            name="Smooth normals weight", default='',
            description="Vertex Group used for smooth normals",
            update = anim_tessellate_active
            )
    invert_vertex_group_smooth_normals : BoolProperty(
            name="Invert", default=False,
            description="Invert the vertex group influence",
            update = anim_tessellate_active
            )

    vertex_group_distribution : StringProperty(
            name="Distribution weight", default='',
            description="Vertex Group used for gradient distribution",
            update = anim_tessellate_active
            )
    invert_vertex_group_distribution : BoolProperty(
            name="Invert", default=False,
            description="Invert the vertex group influence",
            update = anim_tessellate_active
            )
    vertex_group_distribution_factor : FloatProperty(
            name="Factor",
            default=0,
            min=0,
            max=1,
            description="Randomness factor to use for zero vertex group influence",
            update = anim_tessellate_active
            )
    consistent_wedges : BoolProperty(
            name="Consistent Wedges", default=True,
            description="Use same component for the wedges generated by the Fan tessellation",
            update = anim_tessellate_active
            )
    normals_x : FloatProperty(
            name="X", default=1, min=0, max=1,
            description="Scale X component of the normals",
            update = anim_tessellate_active
            )
    normals_y : FloatProperty(
            name="Y", default=1, min=0, max=1,
            description="Scale Y component of the normals",
            update = anim_tessellate_active
            )
    normals_z : FloatProperty(
            name="Z", default=1, min=0, max=1,
            description="Scale Z component of the normals",
            update = anim_tessellate_active
            )
    vertex_group_scale_normals : StringProperty(
            name="Scale normals weight", default='',
            description="Vertex Group used for editing the normals directions",
            update = anim_tessellate_active
            )
    invert_vertex_group_scale_normals : BoolProperty(
            name="Invert", default=False,
            description="Invert the vertex group influence",
            update = anim_tessellate_active
            )
    boundary_variable_offset : BoolProperty(
            name="Boundary Variable Offset", default=False,
            description="Additional material offset based on the number of boundary vertices",
            update = anim_tessellate_active
            )
    auto_rotate_boundary : BoolProperty(
            name="Automatic Rotation", default=False,
            description="Automatically rotate the boundary faces",
            update = anim_tessellate_active
            )
    preserve_quads : BoolProperty(
            name="Preserve Quads",
            default=False,
            description="Quad faces are tessellated using QUAD mode",
            update = anim_tessellate_active
            )

def store_parameters(operator, ob):
    ob.tissue_tessellate.bool_hold = True
    if operator.generator in bpy.data.objects.keys():
        ob.tissue_tessellate.generator = bpy.data.objects[operator.generator]
    if operator.component in bpy.data.objects.keys():
        ob.tissue_tessellate.component = bpy.data.objects[operator.component]
    if operator.component_coll in bpy.data.collections.keys():
        ob.tissue_tessellate.component_coll = bpy.data.collections[operator.component_coll]
    if operator.target in bpy.data.objects.keys():
        ob.tissue_tessellate.target = bpy.data.objects[operator.target]
    ob.tissue_tessellate.even_thickness = operator.even_thickness
    ob.tissue_tessellate.even_thickness_iter = operator.even_thickness_iter
    ob.tissue_tessellate.zscale = operator.zscale
    ob.tissue_tessellate.offset = operator.offset
    ob.tissue_tessellate.gen_modifiers = operator.gen_modifiers
    ob.tissue_tessellate.com_modifiers = operator.com_modifiers
    ob.tissue_tessellate.mode = operator.mode
    ob.tissue_tessellate.rotation_mode = operator.rotation_mode
    ob.tissue_tessellate.rotation_shift = operator.rotation_shift
    ob.tissue_tessellate.rotation_direction = operator.rotation_direction
    ob.tissue_tessellate.merge = operator.merge
    ob.tissue_tessellate.merge_open_edges_only = operator.merge_open_edges_only
    ob.tissue_tessellate.merge_thres = operator.merge_thres
    ob.tissue_tessellate.scale_mode = operator.scale_mode
    ob.tissue_tessellate.bool_random = operator.bool_random
    ob.tissue_tessellate.rand_seed = operator.rand_seed
    ob.tissue_tessellate.coll_rand_seed = operator.coll_rand_seed
    ob.tissue_tessellate.rand_step = operator.rand_step
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
    ob.tissue_tessellate.combine_mode = operator.combine_mode
    ob.tissue_tessellate.bounds_x = operator.bounds_x
    ob.tissue_tessellate.bounds_y = operator.bounds_y
    ob.tissue_tessellate.cap_faces = operator.cap_faces
    ob.tissue_tessellate.close_mesh = operator.close_mesh
    ob.tissue_tessellate.bridge_cuts = operator.bridge_cuts
    ob.tissue_tessellate.bridge_smoothness = operator.bridge_smoothness
    ob.tissue_tessellate.frame_thickness = operator.frame_thickness
    ob.tissue_tessellate.frame_boundary_thickness = operator.frame_boundary_thickness
    ob.tissue_tessellate.frame_mode = operator.frame_mode
    ob.tissue_tessellate.frame_boundary = operator.frame_boundary
    ob.tissue_tessellate.fill_frame = operator.fill_frame
    ob.tissue_tessellate.boundary_mat_offset = operator.boundary_mat_offset
    ob.tissue_tessellate.fill_frame_mat = operator.fill_frame_mat
    ob.tissue_tessellate.cap_material_offset = operator.cap_material_offset
    ob.tissue_tessellate.patch_subs = operator.patch_subs
    ob.tissue_tessellate.use_origin_offset = operator.use_origin_offset
    ob.tissue_tessellate.vertex_group_thickness = operator.vertex_group_thickness
    ob.tissue_tessellate.invert_vertex_group_thickness = operator.invert_vertex_group_thickness
    ob.tissue_tessellate.vertex_group_thickness_factor = operator.vertex_group_thickness_factor
    ob.tissue_tessellate.vertex_group_frame_thickness = operator.vertex_group_frame_thickness
    ob.tissue_tessellate.invert_vertex_group_frame_thickness = operator.invert_vertex_group_frame_thickness
    ob.tissue_tessellate.vertex_group_frame_thickness_factor = operator.vertex_group_frame_thickness_factor
    ob.tissue_tessellate.face_weight_frame = operator.face_weight_frame
    ob.tissue_tessellate.vertex_group_distribution = operator.vertex_group_distribution
    ob.tissue_tessellate.invert_vertex_group_distribution = operator.invert_vertex_group_distribution
    ob.tissue_tessellate.vertex_group_distribution_factor = operator.vertex_group_distribution_factor
    ob.tissue_tessellate.vertex_group_cap_owner = operator.vertex_group_cap_owner
    ob.tissue_tessellate.vertex_group_cap = operator.vertex_group_cap
    ob.tissue_tessellate.invert_vertex_group_cap = operator.invert_vertex_group_cap
    ob.tissue_tessellate.vertex_group_bridge_owner = operator.vertex_group_bridge_owner
    ob.tissue_tessellate.vertex_group_bridge = operator.vertex_group_bridge
    ob.tissue_tessellate.invert_vertex_group_bridge = operator.invert_vertex_group_bridge
    ob.tissue_tessellate.vertex_group_rotation = operator.vertex_group_rotation
    ob.tissue_tessellate.invert_vertex_group_rotation = operator.invert_vertex_group_rotation
    ob.tissue_tessellate.smooth_normals = operator.smooth_normals
    ob.tissue_tessellate.smooth_normals_iter = operator.smooth_normals_iter
    ob.tissue_tessellate.smooth_normals_uv = operator.smooth_normals_uv
    ob.tissue_tessellate.vertex_group_smooth_normals = operator.vertex_group_smooth_normals
    ob.tissue_tessellate.invert_vertex_group_smooth_normals = operator.invert_vertex_group_smooth_normals
    ob.tissue_tessellate.component_mode = operator.component_mode
    ob.tissue_tessellate.consistent_wedges = operator.consistent_wedges
    ob.tissue_tessellate.normals_x = operator.normals_x
    ob.tissue_tessellate.normals_y = operator.normals_y
    ob.tissue_tessellate.normals_z = operator.normals_z
    ob.tissue_tessellate.vertex_group_scale_normals = operator.vertex_group_scale_normals
    ob.tissue_tessellate.invert_vertex_group_scale_normals = operator.invert_vertex_group_scale_normals
    ob.tissue_tessellate.boundary_variable_offset = operator.boundary_variable_offset
    ob.tissue_tessellate.auto_rotate_boundary = operator.auto_rotate_boundary
    ob.tissue_tessellate.preserve_quads = operator.preserve_quads
    ob.tissue_tessellate.bool_hold = False
    return ob

def load_parameters(operator, ob):
    operator.generator = ob.tissue_tessellate.generator.name
    operator.component = ob.tissue_tessellate.component.name
    operator.component_coll = ob.tissue_tessellate.component_coll.name
    operator.zscale = ob.tissue_tessellate.zscale
    operator.offset = ob.tissue_tessellate.offset
    operator.gen_modifiers = ob.tissue_tessellate.gen_modifiers
    operator.com_modifiers = ob.tissue_tessellate.com_modifiers
    operator.mode = ob.tissue_tessellate.mode
    operator.rotation_mode = ob.tissue_tessellate.rotation_mode
    operator.rotation_shift = ob.tissue_tessellate.rotation_shift
    operator.rotation_direction = ob.tissue_tessellate.rotation_direction
    operator.merge = ob.tissue_tessellate.merge
    operator.merge_open_edges_only = ob.tissue_tessellate.merge_open_edges_only
    operator.merge_thres = ob.tissue_tessellate.merge_thres
    operator.scale_mode = ob.tissue_tessellate.scale_mode
    operator.bool_random = ob.tissue_tessellate.bool_random
    operator.rand_seed = ob.tissue_tessellate.rand_seed
    operator.coll_rand_seed = ob.tissue_tessellate.coll_rand_seed
    operator.rand_step = ob.tissue_tessellate.rand_step
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
    operator.combine_mode = ob.tissue_tessellate.combine_mode
    operator.bounds_x = ob.tissue_tessellate.bounds_x
    operator.bounds_y = ob.tissue_tessellate.bounds_y
    operator.cap_faces = ob.tissue_tessellate.cap_faces
    operator.close_mesh = ob.tissue_tessellate.close_mesh
    operator.bridge_cuts = ob.tissue_tessellate.bridge_cuts
    operator.bridge_smoothness = ob.tissue_tessellate.bridge_smoothness
    operator.cap_material_offset = ob.tissue_tessellate.cap_material_offset
    operator.patch_subs = ob.tissue_tessellate.patch_subs
    operator.frame_boundary = ob.tissue_tessellate.frame_boundary
    operator.fill_frame = ob.tissue_tessellate.fill_frame
    operator.boundary_mat_offset = ob.tissue_tessellate.boundary_mat_offset
    operator.fill_frame_mat = ob.tissue_tessellate.fill_frame_mat
    operator.frame_thickness = ob.tissue_tessellate.frame_thickness
    operator.frame_boundary_thickness = ob.tissue_tessellate.frame_boundary_thickness
    operator.frame_mode = ob.tissue_tessellate.frame_mode
    operator.use_origin_offset = ob.tissue_tessellate.use_origin_offset
    operator.vertex_group_thickness = ob.tissue_tessellate.vertex_group_thickness
    operator.invert_vertex_group_thickness = ob.tissue_tessellate.invert_vertex_group_thickness
    operator.vertex_group_thickness_factor = ob.tissue_tessellate.vertex_group_thickness_factor
    operator.vertex_group_frame_thickness = ob.tissue_tessellate.vertex_group_frame_thickness
    operator.invert_vertex_group_frame_thickness = ob.tissue_tessellate.invert_vertex_group_frame_thickness
    operator.vertex_group_frame_thickness_factor = ob.tissue_tessellate.vertex_group_frame_thickness_factor
    operator.face_weight_frame = ob.tissue_tessellate.face_weight_frame
    operator.vertex_group_distribution = ob.tissue_tessellate.vertex_group_distribution
    operator.invert_vertex_group_distribution = ob.tissue_tessellate.invert_vertex_group_distribution
    operator.vertex_group_distribution_factor = ob.tissue_tessellate.vertex_group_distribution_factor
    operator.vertex_group_cap_owner = ob.tissue_tessellate.vertex_group_cap_owner
    operator.vertex_group_cap = ob.tissue_tessellate.vertex_group_cap
    operator.invert_vertex_group_cap = ob.tissue_tessellate.invert_vertex_group_cap
    operator.vertex_group_bridge_owner = ob.tissue_tessellate.vertex_group_bridge_owner
    operator.vertex_group_bridge = ob.tissue_tessellate.vertex_group_bridge
    operator.invert_vertex_group_bridge = ob.tissue_tessellate.invert_vertex_group_bridge
    operator.vertex_group_rotation = ob.tissue_tessellate.vertex_group_rotation
    operator.invert_vertex_group_rotation = ob.tissue_tessellate.invert_vertex_group_rotation
    operator.smooth_normals = ob.tissue_tessellate.smooth_normals
    operator.smooth_normals_iter = ob.tissue_tessellate.smooth_normals_iter
    operator.smooth_normals_uv = ob.tissue_tessellate.smooth_normals_uv
    operator.vertex_group_smooth_normals = ob.tissue_tessellate.vertex_group_smooth_normals
    operator.invert_vertex_group_smooth_normals = ob.tissue_tessellate.invert_vertex_group_smooth_normals
    operator.component_mode = ob.tissue_tessellate.component_mode
    operator.consistent_wedges = ob.tissue_tessellate.consistent_wedges
    operator.normals_x = ob.tissue_tessellate.normals_x
    operator.normals_y = ob.tissue_tessellate.normals_y
    operator.normals_z = ob.tissue_tessellate.normals_z
    operator.vertex_group_scale_normals = ob.tissue_tessellate.vertex_group_scale_normals
    operator.invert_vertex_group_scale_normals = ob.tissue_tessellate.invert_vertex_group_scale_normals
    operator.boundary_variable_offset = ob.tissue_tessellate.boundary_variable_offset
    operator.auto_rotate_boundary = ob.tissue_tessellate.auto_rotate_boundary
    operator.preserve_quads = ob.tissue_tessellate.preserve_quads
    return ob

def props_to_dict(ob):
    props = ob.tissue_tessellate
    tessellate_dict = {}
    tessellate_dict['self'] = ob
    tessellate_dict['generator'] = props.generator
    tessellate_dict['component'] = props.component
    tessellate_dict['component_coll'] = props.component_coll
    tessellate_dict['offset'] = props.offset
    tessellate_dict['zscale'] = props.zscale
    tessellate_dict['gen_modifiers'] = props.gen_modifiers
    tessellate_dict['com_modifiers'] = props.com_modifiers
    tessellate_dict['mode'] = props.mode
    tessellate_dict['scale_mode'] = props.scale_mode
    tessellate_dict['rotation_mode'] = props.rotation_mode
    tessellate_dict['rotation_shift'] = props.rotation_shift
    tessellate_dict['rotation_direction'] = props.rotation_direction
    tessellate_dict['rand_seed'] = props.rand_seed
    tessellate_dict['coll_rand_seed'] = props.coll_rand_seed
    tessellate_dict['rand_step'] = props.rand_step
    tessellate_dict['fill_mode'] = props.fill_mode
    tessellate_dict['bool_vertex_group'] = props.bool_vertex_group
    tessellate_dict['bool_selection'] = props.bool_selection
    tessellate_dict['bool_shapekeys'] = props.bool_shapekeys
    tessellate_dict['bool_material_id'] = props.bool_material_id
    tessellate_dict['material_id'] = props.material_id
    tessellate_dict['normals_mode'] = props.normals_mode
    tessellate_dict['bounds_x'] = props.bounds_x
    tessellate_dict['bounds_y'] = props.bounds_y
    tessellate_dict['use_origin_offset'] = props.use_origin_offset
    tessellate_dict['target'] = props.target
    tessellate_dict['even_thickness'] = props.even_thickness
    tessellate_dict['even_thickness_iter'] = props.even_thickness_iter
    tessellate_dict['frame_thickness'] = props.frame_thickness
    tessellate_dict['frame_boundary_thickness'] = props.frame_boundary_thickness
    tessellate_dict['frame_mode'] = props.frame_mode
    tessellate_dict['frame_boundary'] = props.frame_boundary
    tessellate_dict['fill_frame'] = props.fill_frame
    tessellate_dict['boundary_mat_offset'] = props.boundary_mat_offset
    tessellate_dict['fill_frame_mat'] = props.fill_frame_mat
    tessellate_dict['vertex_group_thickness'] = props.vertex_group_thickness
    tessellate_dict['invert_vertex_group_thickness'] = props.invert_vertex_group_thickness
    tessellate_dict['vertex_group_thickness_factor'] = props.vertex_group_thickness_factor
    tessellate_dict['vertex_group_frame_thickness'] = props.vertex_group_frame_thickness
    tessellate_dict['invert_vertex_group_frame_thickness'] = props.invert_vertex_group_frame_thickness
    tessellate_dict['vertex_group_frame_thickness_factor'] = props.vertex_group_frame_thickness_factor
    tessellate_dict['face_weight_frame'] = props.face_weight_frame
    tessellate_dict['vertex_group_distribution'] = props.vertex_group_distribution
    tessellate_dict['invert_vertex_group_distribution'] = props.invert_vertex_group_distribution
    tessellate_dict['vertex_group_distribution_factor'] = props.vertex_group_distribution_factor
    tessellate_dict['vertex_group_cap_owner'] = props.vertex_group_cap_owner
    tessellate_dict['vertex_group_cap'] = props.vertex_group_cap
    tessellate_dict['invert_vertex_group_cap'] = props.invert_vertex_group_cap
    tessellate_dict['vertex_group_bridge_owner'] = props.vertex_group_bridge_owner
    tessellate_dict['vertex_group_bridge'] = props.vertex_group_bridge
    tessellate_dict['invert_vertex_group_bridge'] = props.invert_vertex_group_bridge
    tessellate_dict['vertex_group_rotation'] = props.vertex_group_rotation
    tessellate_dict['invert_vertex_group_rotation'] = props.invert_vertex_group_rotation
    tessellate_dict['smooth_normals'] = props.smooth_normals
    tessellate_dict['smooth_normals_iter'] = props.smooth_normals_iter
    tessellate_dict['smooth_normals_uv'] = props.smooth_normals_uv
    tessellate_dict['vertex_group_smooth_normals'] = props.vertex_group_smooth_normals
    tessellate_dict['invert_vertex_group_smooth_normals'] = props.invert_vertex_group_smooth_normals
    tessellate_dict['component_mode'] = props.component_mode
    tessellate_dict['consistent_wedges'] = props.consistent_wedges
    tessellate_dict["normals_x"] = props.normals_x
    tessellate_dict["normals_y"] = props.normals_y
    tessellate_dict["normals_z"] = props.normals_z
    tessellate_dict["vertex_group_scale_normals"] = props.vertex_group_scale_normals
    tessellate_dict["invert_vertex_group_scale_normals"] = props.invert_vertex_group_scale_normals
    tessellate_dict["boundary_variable_offset"] = props.boundary_variable_offset
    tessellate_dict["auto_rotate_boundary"] = props.auto_rotate_boundary
    tessellate_dict["merge"] = props.merge
    tessellate_dict["merge_thres"] = props.merge_thres
    tessellate_dict["merge_open_edges_only"] = props.merge_open_edges_only
    tessellate_dict["preserve_quads"] = props.preserve_quads
    return tessellate_dict

def copy_tessellate_props(source_ob, target_ob):
    source_props = source_ob.tissue_tessellate
    target_props = target_ob.tissue_tessellate
    for key in source_props.keys():
        target_props[key] = source_props[key]
    return
