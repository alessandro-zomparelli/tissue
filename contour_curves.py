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

#-------------------------- COLORS / GROUPS EXCHANGER -------------------------#
#                                                                              #
# Vertex Color to Vertex Group allow you to convert colors channles to weight  #
# maps.                                                                        #
# The main purpose is to use vertex colors to store information when importing #
# files from other softwares. The script works with the active vertex color    #
# slot.                                                                        #
# For use the command "Vertex Clors to Vertex Groups" use the search bar       #
# (space bar).                                                                 #
#                                                                              #
#                          (c)  Alessandro Zomparelli                          #
#                                     (2017)                                   #
#                                                                              #
# http://www.co-de-it.com/                                                     #
#                                                                              #
################################################################################

import bpy, bmesh, os
import numpy as np
import math, timeit, time
from math import pi
from mathutils import Vector
from numpy import *

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
    FloatVectorProperty,
    IntVectorProperty,
    PointerProperty
)

from .utils import *

def anim_contour_curves(self, context):
    ob = context.object
    props = ob.tissue_contour_curves
    if not (ob.tissue.bool_lock or ob.tissue.bool_hold):
        #try:
        props.object.name
        bpy.ops.object.tissue_update_contour_curves()
        #except: pass

class tissue_contour_curves_prop(PropertyGroup):
    object : PointerProperty(
        type=bpy.types.Object,
        name="Object",
        description="Source object",
        update = anim_contour_curves
        )

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers",
        update = anim_contour_curves
        )

    variable_bevel : BoolProperty(
        name="Variable Bevel", default=False,
        description="Variable Bevel",
        update = anim_contour_curves
        )

    min_value : FloatProperty(
        name="Offset Value", default=0., #soft_min=0, soft_max=1,
        description="Offset contouring values",
        update = anim_contour_curves
        )

    range_value : FloatProperty(
        name="Range Values", default=100, #soft_min=0, soft_max=1,
        description="Maximum range of contouring values",
        update = anim_contour_curves
        )

    n_curves : IntProperty(
        name="Curves", default=1000, soft_min=1, soft_max=200,
        description="Number of Contour Curves",
        update = anim_contour_curves
        )

    in_displace : FloatProperty(
        name="Displace A", default=0, soft_min=-10, soft_max=10,
        description="Pattern displace strength",
        update = anim_contour_curves
        )

    out_displace : FloatProperty(
        name="Displace B", default=2, soft_min=-10, soft_max=10,
        description="Pattern displace strength",
        update = anim_contour_curves
        )

    in_steps : IntProperty(
        name="Steps A", default=1, min=0, soft_max=10,
        description="Number of layers to move inwards",
        update = anim_contour_curves
        )

    out_steps : IntProperty(
        name="Steps B", default=1, min=0, soft_max=10,
        description="Number of layers to move outwards",
        update = anim_contour_curves
        )

    displace_x : BoolProperty(
        name="Use X", default=True,
        description="Displace along X axis",
        update = anim_contour_curves
        )

    displace_y : BoolProperty(
        name="Use Y", default=True,
        description="Displace along Y axis",
        update = anim_contour_curves
        )

    displace_z : BoolProperty(
        name="Use Z", default=True,
        description="Displace along Z axis",
        update = anim_contour_curves
        )

    merge : BoolProperty(
        name="Merge Vertices", default=True,
        description="Merge points",
        update = anim_contour_curves
        )

    merge_thres : FloatProperty(
        name="Merge Threshold", default=0.01, min=0, soft_max=1,
        description="Minimum Curve Radius",
        update = anim_contour_curves
        )

    bevel_depth : FloatProperty(
        name="Bevel Depth", default=0, min=0, soft_max=1,
        description="",
        update = anim_contour_curves
        )

    min_bevel_depth : FloatProperty(
        name="Min Bevel Depth", default=0.05, min=0, soft_max=1,
        description="",
        update = anim_contour_curves
        )

    max_bevel_depth : FloatProperty(
        name="Max Bevel Depth", default=0.20, min=0, soft_max=1,
        description="",
        update = anim_contour_curves
        )

    remove_open_curves : BoolProperty(
        name="Remove Open Curves", default=False,
        description="Remove Open Curves",
        update = anim_contour_curves
        )

    vertex_group_pattern : StringProperty(
        name="Displace", default='',
        description="Vertex Group used for pattern displace",
        update = anim_contour_curves
        )

    vertex_group_bevel : StringProperty(
        name="Bevel", default='',
        description="Variable Bevel depth",
        update = anim_contour_curves
        )

    object_name : StringProperty(
        name="Active Object", default='',
        description="",
        update = anim_contour_curves
        )

    vertex_group_contour : StringProperty(
        name="Contour", default="",
        description="Vertex Group used for contouring",
        update = anim_contour_curves
        )

    clean_distance : FloatProperty(
        name="Clean Distance", default=0.005, min=0, soft_max=10,
        description="Remove short segments",
        update = anim_contour_curves
        )

    spiralized: BoolProperty(
        name='Spiralized', default=False,
        description='Create a Spiral Contour. Works better with dense meshes.',
        update = anim_contour_curves
        )

    spiral_axis: FloatVectorProperty(
        name="Spiral Axis", default=(0,0,1),
        description="Axis of the Spiral (in local coordinates)",
        update = anim_contour_curves
        )

    spiral_rotation : FloatProperty(
        name="Spiral Rotation", default=0, min=0, max=2*pi,
        description="",
        update = anim_contour_curves
        )

    contour_mode : EnumProperty(
        items=(
            ('VECTOR', "Vector", "Orient the Contour to a given vector starting from the origin of the object"),
            ('OBJECT', "Object", "Orient the Contour to a target object's Z"),
            ('WEIGHT', "Weight", "Contour based on a Vertex Group"),
            ('ATTRIBUTE', "Attribute", "Contour based on an Attribute (Vertex > Float)"),
            ('GEODESIC', "Geodesic Distance", "Contour based on the geodesic distance from the chosen vertices"),
            ('TOPOLOGY', "Topology Distance", "Contour based on the topology distance from the chosen vertices")
            ),
        default='VECTOR',
        name="Mode used for the Contour Curves",
        update = anim_contour_curves
        )

    contour_vector : FloatVectorProperty(
        name='Vector', description='Constant Vector', default=(0.0, 0.0, 1.0),
        update = anim_contour_curves
        )

    contour_vector_object : PointerProperty(
        type=bpy.types.Object,
        name="",
        description="Target Object",
        update = anim_contour_curves
        )

    contour_offset : FloatProperty(
        name="Offset", default=0.05, min=0.000001, soft_min=0.01, soft_max=10,
        description="Contour offset along the Vector",
        update = anim_contour_curves
        )

    seeds_mode : EnumProperty(
        items=(
            ('BOUND', "Boundary Edges", "Compute the distance starting from the boundary edges"),
            ('SHARP', "Sharp Edges", "Compute the distance starting from the sharp edges"),
            ('WEIGHT', "Weight", "Compute the distance starting from the selected vertex group")
            ),
        default='BOUND',
        name="Seeds used for computing the distance",
        update = anim_contour_curves
        )

    vertex_group_seed : StringProperty(
        name="Seeds", default="",
        description="Vertex Group used for computing the distance",
        update = anim_contour_curves
        )

    spline_type : EnumProperty(
        items=(
            ('POLY', "Poly", "Generate Poly curves"),
            ('NURBS', "NURBS", "Generate NURBS curves")
            ),
        default='POLY',
        name="Spline type",
        update = anim_contour_curves
        )

    contour_attribute : StringProperty(
        name="Contour Attribute", default='',
        description="Vertex > Float attribute used for contouring",
        update = anim_contour_curves
        )


class tissue_weight_contour_curves_pattern(Operator):
    bl_idname = "object.tissue_weight_contour_curves_pattern"
    bl_label = "Contour Curves"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    object : StringProperty(
        name="Object",
        description="Source object",
        default = ""
        )

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers"
        )

    variable_bevel : BoolProperty(
        name="Variable Bevel", default=False,
        description="Variable Bevel"
        )

    min_value : FloatProperty(
        name="Offset Value", default=0.,
        description="Offset contouring values"
        )

    range_value : FloatProperty(
        name="Range Values", default=100,
        description="Maximum range of contouring values"
        )

    n_curves : IntProperty(
        name="Curves", default=1000, soft_min=1, soft_max=200,
        description="Number of Contour Curves"
        )

    min_rad = 1
    max_rad = 1

    in_displace : FloatProperty(
        name="Displace A", default=0, soft_min=-10, soft_max=10,
        description="Pattern displace strength"
        )

    out_displace : FloatProperty(
        name="Displace B", default=2, soft_min=-10, soft_max=10,
        description="Pattern displace strength"
        )

    in_steps : IntProperty(
        name="Steps A", default=1, min=0, soft_max=10,
        description="Number of layers to move inwards"
        )

    out_steps : IntProperty(
        name="Steps B", default=1, min=0, soft_max=10,
        description="Number of layers to move outwards"
        )

    displace_x : BoolProperty(
        name="Use X", default=True,
        description="Displace along X axis"
        )

    displace_y : BoolProperty(
        name="Use Y", default=True,
        description="Displace along Y axis"
        )

    displace_z : BoolProperty(
        name="Use Z", default=True,
        description="Displace along Z axis"
        )

    merge : BoolProperty(
        name="Merge Vertices", default=True,
        description="Merge points"
        )

    merge_thres : FloatProperty(
        name="Merge Threshold", default=0.01, min=0, soft_max=1,
        description="Minimum Curve Radius"
        )

    bevel_depth : FloatProperty(
        name="Bevel Depth", default=0, min=0, soft_max=1,
        description=""
        )

    min_bevel_depth : FloatProperty(
        name="Min Bevel Depth", default=0.05, min=0, soft_max=1,
        description=""
        )

    max_bevel_depth : FloatProperty(
        name="Max Bevel Depth", default=0.20, min=0, soft_max=1,
        description=""
        )

    remove_open_curves : BoolProperty(
        name="Remove Open Curves", default=False,
        description="Remove Open Curves"
        )

    vertex_group_pattern : StringProperty(
        name="Displace", default='',
        description="Vertex Group used for pattern displace"
        )

    vertex_group_bevel : StringProperty(
        name="Bevel", default='',
        description="Variable Bevel depth"
        )

    object_name : StringProperty(
        name="Active Object", default='',
        description=""
        )

    contour_attribute : StringProperty(
        name="Contour Attribute", default='',
        description="Vertex > Float attribute used for contouring"
        )

    try: vg_name = bpy.context.object.vertex_groups.active.name
    except: vg_name = ''

    vertex_group_contour : StringProperty(
        name="Contour", default=vg_name,
        description="Vertex Group used for contouring"
        )

    clean_distance : FloatProperty(
        name="Clean Distance", default=0.005, min=0, soft_max=10,
        description="Remove short segments"
        )

    spiralized: BoolProperty(
        name='Spiralized', default=False,
        description='Create a Spiral Contour. Works better with dense meshes.'
        )

    spiral_axis: FloatVectorProperty(
        name="Spiral Axis", default=(0,0,1),
        description="Axis of the Spiral (in local coordinates)"
        )

    spiral_rotation : FloatProperty(
        name="Spiral Rotation", default=0, min=0, max=2*pi,
        description=""
        )

    bool_hold : BoolProperty(
        name="Hold",
        description="Wait...",
        default=False
        )

    contour_mode : EnumProperty(
        items=(
            ('VECTOR', "Vector", "Orient the Contour to a given vector starting from the origin of the object"),
            ('OBJECT', "Object", "Orient the Contour to a target object's Z"),
            ('WEIGHT', "Weight", "Contour based on a Vertex Group"),
            ('ATTRIBUTE', "Attribute", "Contour based on an Attribute (Vertex > Float)"),
            ('GEODESIC', "Geodesic Distance", "Contour based on the geodesic distance from the chosen vertices"),
            ('TOPOLOGY', "Topology Distance", "Contour based on the topology distance from the chosen vertices")
            ),
        default='VECTOR',
        name="Mode used for the Contour Curves"
        )

    contour_vector : FloatVectorProperty(
        name='Vector', description='Constant Vector', default=(0.0, 0.0, 1.0)
        )

    contour_vector_object : StringProperty(
        name="Object",
        description="Target object",
        default = ""
        )

    contour_offset : FloatProperty(
        name="Offset", default=0.05, min=0.000001, soft_min=0.01, soft_max=10,
        description="Contour offset along the Vector"
        )

    seeds_mode : EnumProperty(
        items=(
            ('BOUND', "Boundary Edges", "Compute the distance starting from the boundary edges"),
            ('SHARP', "Sharp Edges", "Compute the distance starting from the sharp edges"),
            ('WEIGHT', "Weight", "Compute the distance starting from the selected vertex group")
            ),
        default='BOUND',
        name="Seeds used for computing the distance"
        )

    vertex_group_seed : StringProperty(
        name="Seeds", default=vg_name,
        description="Vertex Group used for computing the distance"
        )

    spline_type : EnumProperty(
        items=(
            ('POLY', "Poly", "Generate Poly curves"),
            ('NURBS', "NURBS", "Generate NURBS curves")
            ),
        default='POLY',
        name="Spline type"
        )

    def invoke(self, context, event):
        self.object = context.object.name
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        ob = context.object
        ob0 = bpy.data.objects[self.object]

        if self.contour_mode == 'WEIGHT':
            try:
                if self.vertex_group_contour not in [vg.name for vg in ob.vertex_groups]:
                    self.vertex_group_contour = ob.vertex_groups.active.name
            except:
                self.contour_mode == 'VECTOR'

        if not self.bool_hold:
            self.object = ob.name
        self.bool_hold = True

        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "use_modifiers")
        col.label(text="Contour Curves:")

        row = col.row()
        row.prop(self, "spline_type", icon='NONE', expand=True,
                 slider=True, toggle=False, icon_only=False, event=False,
                 full_event=False, emboss=True, index=-1)
        col.separator()
        col.prop(self, "contour_mode", text="Mode")

        if self.contour_mode == 'VECTOR':
            row = col.row()
            row.prop(self,'contour_vector')
        elif self.contour_mode == 'WEIGHT':
            col.prop_search(self, 'vertex_group_contour', ob, "vertex_groups", text='Group')
        elif self.contour_mode == 'ATTRIBUTE':
            col.prop_search(self, 'contour_attribute', ob0.data, "attributes", text='Attribute')
            is_attribute = True
            if self.contour_attribute in ob0.data.attributes:
                attr = ob0.data.attributes[self.contour_attribute]
                is_attribute = attr.data_type == 'FLOAT' and attr.domain == 'POINT'
            else:
                is_attribute = False
            if not is_attribute:
                 col.label(text="Please select a (Vertex > Float) Attribute for contouring.", icon='ERROR')
        elif self.contour_mode in ('TOPOLOGY','GEODESIC'):
            col.prop(self, "seeds_mode", text="Seeds")
            if self.seeds_mode == 'WEIGHT':
                col.prop_search(self, 'vertex_group_seed', ob, "vertex_groups", text='Group')
        elif self.contour_mode == 'OBJECT':
            col.prop_search(self, "contour_vector_object", context.scene, "objects", text='Object')
        col.separator()

        if self.contour_mode == 'OBJECT':
            col.prop(self,'contour_offset')
            col.prop(self,'n_curves', text='Max Curves')
        elif self.contour_mode in ('VECTOR', 'GEODESIC', 'ATTRIBUTE'):
            col.prop(self,'contour_offset')
            row = col.row(align=True)
            row.prop(self,'min_value')
            row.prop(self,'range_value')
            col.prop(self,'n_curves', text='Max Curves')
        elif self.contour_mode in ('TOPOLOGY', 'WEIGHT'):
            row = col.row(align=True)
            row.prop(self,'min_value')
            row.prop(self,'range_value')
            col.prop(self,'n_curves')

        col.separator()
        col.label(text='Curves Bevel:')
        col.prop(self,'variable_bevel')
        row = col.row(align=True)
        row.prop(self,'min_bevel_depth')
        row.prop(self,'max_bevel_depth')
        row2 = col.row(align=True)
        row2.prop_search(self, 'vertex_group_bevel', ob, "vertex_groups", text='')
        if not self.variable_bevel:
            row.enabled = row2.enabled = False
        col.separator()

        col.label(text="Displace Pattern:")
        col.prop_search(self, 'vertex_group_pattern', ob, "vertex_groups", text='')
        if self.vertex_group_pattern != '':
            col.separator()
            row = col.row(align=True)
            row.prop(self,'in_steps')
            row.prop(self,'out_steps')
            row = col.row(align=True)
            row.prop(self,'in_displace')
            row.prop(self,'out_displace')
            col.separator()
            row = col.row(align=True)
            row.label(text="Axis")
            row.prop(self,'displace_x', text="X", toggle=1)
            row.prop(self,'displace_y', text="Y", toggle=1)
            row.prop(self,'displace_z', text="Z", toggle=1)
        col.separator()

        col.label(text='Clean Curves:')
        col.prop(self,'clean_distance')
        col.prop(self,'remove_open_curves')

    def execute(self, context):
        ob0 = bpy.context.object

        self.object_name = "Contour Curves"
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

        if bpy.ops.object.select_all.poll():
            bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')

        bool_update = False
        if context.object == ob0:
            auto_layer_collection()
            curve = bpy.data.curves.new(self.object_name,'CURVE')
            new_ob = bpy.data.objects.new(self.object_name,curve)
            bpy.context.collection.objects.link(new_ob)
            bpy.context.view_layer.objects.active = new_ob
            if bpy.ops.object.select_all.poll():
                bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            new_ob.select_set(True)
        else:
            new_ob = context.object
            bool_update = True

        # Store parameters
        props = new_ob.tissue_contour_curves
        new_ob.tissue.bool_hold = True
        if self.object in bpy.data.objects.keys():
            props.object = bpy.data.objects[self.object]
        props.use_modifiers = self.use_modifiers
        props.variable_bevel = self.variable_bevel
        props.min_value = self.min_value
        props.range_value = self.range_value
        props.n_curves = self.n_curves
        props.in_displace = self.in_displace
        props.out_displace = self.out_displace
        props.in_steps = self.in_steps
        props.out_steps = self.out_steps
        props.displace_x = self.displace_x
        props.displace_y = self.displace_y
        props.displace_z = self.displace_z
        props.merge = self.merge
        props.merge_thres = self.merge_thres
        props.bevel_depth = self.bevel_depth
        props.min_bevel_depth = self.min_bevel_depth
        props.max_bevel_depth = self.max_bevel_depth
        props.remove_open_curves = self.remove_open_curves
        props.vertex_group_pattern = self.vertex_group_pattern
        props.vertex_group_bevel = self.vertex_group_bevel
        props.object_name = self.object_name
        props.vertex_group_contour = self.vertex_group_contour
        props.clean_distance = self.clean_distance
        props.spiralized = self.spiralized
        props.spiral_axis = self.spiral_axis
        props.spiral_rotation = self.spiral_rotation
        props.contour_mode = self.contour_mode
        if self.contour_vector_object in bpy.data.objects.keys():
            props.contour_vector_object = bpy.data.objects[self.contour_vector_object]
        props.contour_vector = self.contour_vector
        props.contour_offset = self.contour_offset
        props.seeds_mode = self.seeds_mode
        props.vertex_group_seed = self.vertex_group_seed
        props.spline_type = self.spline_type
        props.contour_attribute = self.contour_attribute
        new_ob.tissue.bool_hold = False

        new_ob.tissue.tissue_type = 'CONTOUR_CURVES'
        try: bpy.ops.object.tissue_update_contour_curves()
        except RuntimeError as e:
            print("no update")
            bpy.data.objects.remove(new_ob)
            remove_temp_objects()
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        if not bool_update:
            self.object_name = new_ob.name
            #self.working_on = self.object_name
            new_ob.location = ob0.location
            new_ob.matrix_world = ob0.matrix_world

        # Assign collection of the base object
        old_coll = new_ob.users_collection
        if old_coll != ob0.users_collection:
            for c in old_coll:
                c.objects.unlink(new_ob)
            for c in ob0.users_collection:
                c.objects.link(new_ob)
        context.view_layer.objects.active = new_ob

        return {'FINISHED'}

class tissue_update_contour_curves(Operator):
    bl_idname = "object.tissue_update_contour_curves"
    bl_label = "Update Contour Curves"
    bl_description = ("Update a previously generated Contour Curves object")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.object
        props = ob.tissue_contour_curves
        _ob0 = props.object
        n_curves = props.n_curves
        tt0 = time.time()
        tt1 = time.time()
        tissue_time(None,'Tissue: Contour Curves of "{}"...'.format(ob.name), levels=0)

        ob0 = convert_object_to_mesh(_ob0, apply_modifiers=props.use_modifiers)
        ob0.name = "_tissue_tmp_ob0"
        me0 = ob0.data

        # generate new bmesh
        bm = bmesh.new()
        bm.from_mesh(me0)
        n_verts = len(bm.verts)
        vertices, normals = get_vertices_and_normals_numpy(me0)

        if props.contour_mode == 'OBJECT':
            try:
                vec_ob = props.contour_vector_object
                vec_ob_name = vec_ob.name
            except:
                bm.free()
                bpy.data.objects.remove(ob0)
                self.report({'ERROR'}, "Please select an target Object")
                return {'CANCELLED'}

        tt1 = tissue_time(tt1, "Load objects", levels=1)

        # store weight values
        if props.contour_mode in ('VECTOR','OBJECT'):
            ob0_matrix = np.matrix(ob0.matrix_world.to_3x3().transposed())
            global_verts = np.matmul(vertices,ob0_matrix)
            global_verts += np.array(ob0.matrix_world.translation)
            if props.contour_mode == 'OBJECT' and props.contour_vector_object:
                vec_ob = props.contour_vector_object
                global_verts -= np.array(vec_ob.matrix_world.translation)
                vec_ob_matrix = np.matrix(vec_ob.matrix_world.to_3x3().inverted().transposed())
                global_verts = np.matmul(global_verts,vec_ob_matrix)
                weight = global_verts[:,2].A1
            elif props.contour_mode == 'VECTOR':
                vec = np.array(props.contour_vector)
                vec_len = np.linalg.norm(vec)
                if vec_len == 0:
                    vec = np.array((0,0,1))
                    vec_len = 1
                else:
                    vec /= vec_len
                    vec_len = 1
                global_verts = global_verts.A
                projected_verts = global_verts * vec
                projected_verts = np.sum(projected_verts,axis=1)[:,np.newaxis]
                weight = projected_verts.reshape((-1))
        elif props.contour_mode == 'WEIGHT':
            try:
                weight = get_weight_numpy(ob0.vertex_groups[props.vertex_group_contour], len(me0.vertices))
            except:
                bm.free()
                bpy.data.objects.remove(ob0)
                self.report({'ERROR'}, "Please select a Vertex Group for contouring")
                return {'CANCELLED'}
        elif props.contour_mode == 'ATTRIBUTE':
            if props.contour_attribute in me0.attributes:
                weight = [0]*n_verts
                me0.attributes[props.contour_attribute].data.foreach_get('value',weight)
                weight = np.array(weight)
            else:
                bm.free()
                bpy.data.objects.remove(ob0)
                self.report({'ERROR'}, "Please select a (Vertex > Float) Attribute for contouring")
                return {'CANCELLED'}
        elif props.contour_mode in ('GEODESIC','TOPOLOGY'):
            cancel = False
            weight = [None]*n_verts
            seed_verts = []
            bm.verts.ensure_lookup_table()
            if props.seeds_mode == 'BOUND':
                for v in bm.verts:
                    if v.is_boundary:
                        seed_verts.append(v)
                        weight[v.index] = 0
            if props.seeds_mode == 'SHARP':
                for e, bme in zip(me0.edges, bm.edges):
                    if e.use_edge_sharp:
                        seed_verts.append(bme.verts[0])
                        seed_verts.append(bme.verts[1])
                seed_verts = list(set(seed_verts))
                if len(seed_verts) == 0: cancel = True
                for i in [v.index for v in seed_verts]:
                    weight[i] = 0
            if props.seeds_mode == 'WEIGHT':
                try:
                    seeds = get_weight_numpy(ob0.vertex_groups[props.vertex_group_seed], len(me0.vertices))
                except:
                    bm.free()
                    bpy.data.objects.remove(ob0)
                    self.report({'ERROR'}, "Please select a Vertex Group as seed")
                    return {'CANCELLED'}
                for i,v in enumerate(bm.verts):
                    if seeds[i]>0.999999:
                        seed_verts.append(v)
                        weight[i] = 0
            if cancel or len(seed_verts)==0:
                bm.free()
                bpy.data.objects.remove(ob0)
                self.report({'ERROR'}, "No seed vertices found")
                return {'CANCELLED'}

            weight = fill_neighbors_attribute(seed_verts, weight, props.contour_mode)
            weight = np.array(weight)
            print(weight[weight==None])
            weight[weight==None] = 0
            print(weight[weight==None])

        try:
            pattern_weight = get_weight_numpy(ob0.vertex_groups[props.vertex_group_pattern], len(me0.vertices))
        except:
            #self.report({'WARNING'}, "There is no Vertex Group assigned to the pattern displace")
            pattern_weight = np.zeros(len(me0.vertices))

        weight_bevel = False
        if props.variable_bevel:
            try:
                bevel_weight = get_weight_numpy(ob0.vertex_groups[props.vertex_group_bevel], len(me0.vertices))
                weight_bevel = True
            except:
                bevel_weight = np.ones(len(me0.vertices))
        else:
            bevel_weight = np.ones(len(me0.vertices))

        total_verts = np.zeros((0,3))
        total_radii = np.zeros((0,1))
        total_edges_index = np.zeros((0)).astype('int')
        total_segments = []# np.array([])
        radius = []

        tt1 = tissue_time(tt1, "Compute values", levels=1)

        # start iterate contours levels
        filtered_edges = get_edges_id_numpy(me0)

        min_value = props.min_value
        max_value = props.min_value + props.range_value

        if props.contour_mode in ('VECTOR','OBJECT','GEODESIC','ATTRIBUTE'):
            delta_iso = props.contour_offset
            n_curves = min(int((np.max(weight)-props.min_value)/delta_iso)+1, props.n_curves)
        else:
            if n_curves == 1:
                delta_iso = props.range_value/2
            else:
                delta_iso = props.range_value/(n_curves-1)
        if props.contour_mode == 'TOPOLOGY':
            weight = weight/np.max(weight)

        if False:
            edges_verts = get_attribute_numpy(me0.edges,"vertices",mult=2).astype('int')
            edges_vec = vertices[edges_verts[:,0]]-vertices[edges_verts[:,1]]
            #edges_vec = global_verts[edges_verts[:,0]]-global_verts[edges_verts[:,1]]
            edges_length = np.linalg.norm(edges_vec,axis=1)
            edges_vec /= edges_length[:,np.newaxis]
            edges_dw = np.abs(weight[edges_verts[:,0]]-weight[edges_verts[:,1]])
            edges_bevel = delta_iso*edges_length/edges_dw/2*0 + 1

        '''
        # numpy method
        faces_n_verts = get_attribute_numpy(me0.polygons, attribute='loop_total').astype('int')
        faces_verts = get_attribute_numpy(me0.polygons, attribute='vertices', size=np.sum(faces_n_verts)).astype('int')
        faces_weight = weight[faces_verts]
        faces_weight = np.split(faces_weight, np.cumsum(faces_n_verts)[:-1])
        '''
        faces_weight = [np.array([weight[v] for v in p.vertices]) for p in me0.polygons]
        try:
            fw_min = np.min(faces_weight, axis=1)
            fw_max = np.max(faces_weight, axis=1)
        except:
            # necessary for irregular meshes
            fw_min = np.array([min(fw) for fw in faces_weight])
            fw_max = np.array([max(fw) for fw in faces_weight])
        bm_faces = np.array(bm.faces)

        tt1 = tissue_time(tt1, "Compute face values", levels=1)
        for c in range(n_curves):
            if delta_iso:
                iso_val = c*delta_iso + min_value
            else:
                iso_val = min_value + range_value/2
            if iso_val > max_value: break

            # remove passed faces
            bool_mask = iso_val <= fw_max
            bm_faces = bm_faces[bool_mask]
            fw_min = fw_min[bool_mask]
            fw_max = fw_max[bool_mask]

            # mask faces
            bool_mask = fw_min <= iso_val
            faces_mask = bm_faces[bool_mask]

            count = len(total_verts)

            if not weight_bevel and props.variable_bevel:
                bevel_weight = np.full(n_verts, c/n_curves)
            new_filtered_edges, edges_index, verts, bevel = contour_edges_pattern(props, c, len(total_verts), iso_val, vertices, normals, filtered_edges, weight, pattern_weight, bevel_weight)
            #bevel = edges_bevel[edges_index][:,np.newaxis]

            if len(edges_index) > 0:
                if props.variable_bevel and props.max_bevel_depth != props.min_bevel_depth and False:
                    #min_radius = min(props.min_bevel_depth, props.max_bevel_depth)
                    #max_radius = max(props.min_bevel_depth, props.max_bevel_depth)
                    min_radius = props.min_bevel_depth
                    max_radius = props.max_bevel_depth
                    min_radius = min_radius / max(0.0001,max_radius)
                    radii = min_radius + bevel*(1 - min_radius)
                else:
                    radii = bevel
            else:
                continue

            if verts[0,0] == None: continue
            else: filtered_edges = new_filtered_edges
            edges_id = {}
            for i, id in enumerate(edges_index): edges_id[id] = i + count

            if len(verts) == 0: continue

            # finding segments
            segments = []
            for f in faces_mask:
                seg = []
                for e in f.edges:
                    try:
                        #seg.append(new_ids[np.where(edges_index == e.index)[0][0]])
                        seg.append(edges_id[e.index])
                        if len(seg) == 2:
                            segments.append(seg)
                            seg = []
                    except: pass

            total_segments = total_segments + segments
            total_verts = np.concatenate((total_verts, verts))
            total_radii = np.concatenate((total_radii, radii))
            total_edges_index = np.concatenate((total_edges_index, edges_index))
        tt1 = tissue_time(tt1, "Compute curves", levels=1)

        if len(total_segments) > 0:
            ordered_points, ordered_points_edge_id = find_curves_attribute(total_segments, len(total_verts), total_edges_index)

            total_tangents = np.zeros((len(total_verts),3))
            for curve in ordered_points:
                np_curve = np.array(curve).astype('int')
                curve_pts = np.array(total_verts[np_curve], dtype=np.float64)
                tangents = np.roll(curve_pts,1) - np.roll(curve_pts,-1)
                tangents /= np.linalg.norm(tangents,axis=1)[:,np.newaxis]
                total_tangents[curve] = tangents

            step_time = timeit.default_timer()
            ob.data.splines.clear()
            if props.variable_bevel:# and not weight_bevel:
                total_radii = np.interp(total_radii, (total_radii.min(), total_radii.max()), (props.min_bevel_depth, props.max_bevel_depth))
            ob.data = curve_from_pydata(total_verts, total_radii, ordered_points, ob0.name + '_ContourCurves', props.remove_open_curves, merge_distance=props.clean_distance, only_data=True, curve=ob.data, spline_type=props.spline_type)
            #context.view_layer.objects.active = crv
            if props.variable_bevel:
                if not weight_bevel:
                    ob.data.bevel_depth = 1
                else:
                    ob.data.bevel_depth = max(props.max_bevel_depth, props.min_bevel_depth)
            tt1 = tissue_time(tt1, "Store curves data", levels=1)
        else:
            ob.data.splines.clear()
            pass
        bm.free()
        for o in bpy.data.objects:
            if '_tissue_tmp_' in o.name:
                bpy.data.objects.remove(o)

        tt0 = tissue_time(tt0, "Contour Curves", levels=0)
        return {'FINISHED'}


class TISSUE_PT_contour_curves(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_label = "Tissue Contour Curves"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try:
            #bool_curve = context.object.tissue_to_curve.object != None
            ob = context.object
            return ob.type == 'CURVE' and ob.tissue.tissue_type == 'CONTOUR_CURVES'
        except:
            return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_contour_curves
        ob0 = bpy.data.objects[props.object.name]

        layout = self.layout
        #layout.use_property_split = True
        #layout.use_property_decorate = False
        col = layout.column(align=True)
        row = col.row(align=True)
        #col.operator("object.tissue_update_convert_to_curve", icon='FILE_REFRESH', text='Refresh')
        row.operator("object.tissue_update_tessellate_deps", icon='FILE_REFRESH', text='Refresh') ####
        lock_icon = 'LOCKED' if ob.tissue.bool_lock else 'UNLOCKED'
        #lock_icon = 'PINNED' if props.bool_lock else 'UNPINNED'
        deps_icon = 'LINKED' if ob.tissue.bool_dependencies else 'UNLINKED'
        row.prop(ob.tissue, "bool_dependencies", text="", icon=deps_icon)
        row.prop(ob.tissue, "bool_lock", text="", icon=lock_icon)
        col2 = row.column(align=True)
        col2.prop(ob.tissue, "bool_run", text="",icon='TIME')
        col2.enabled = not ob.tissue.bool_lock
        col2 = row.column(align=True)
        col2.operator("mesh.tissue_remove", text="", icon='X')

        col.separator()
        row = col.row(align=True)
        row.prop_search(props, "object", context.scene, "objects", text="")
        row.prop(props, "use_modifiers", icon='MODIFIER', text='')
        col.separator()
        col.label(text="Contour Curves:")
        row = col.row()
        row.prop(props, "spline_type", icon='NONE', expand=True,
                 slider=True, toggle=False, icon_only=False, event=False,
                 full_event=False, emboss=True, index=-1)
        col.separator()
        col.prop(props, "contour_mode", text="Mode")

        if props.contour_mode == 'VECTOR':
            row = col.row()
            row.prop(props,'contour_vector')
        elif props.contour_mode == 'WEIGHT':
            col.prop_search(props, 'vertex_group_contour', ob0, "vertex_groups", text='Group')
        elif props.contour_mode == 'ATTRIBUTE':
            col.prop_search(props, 'contour_attribute', ob0.data, "attributes", text='Attribute')
            is_attribute = True
            if props.contour_attribute in ob0.data.attributes:
                attr = ob0.data.attributes[props.contour_attribute]
                is_attribute = attr.data_type == 'FLOAT' and attr.domain == 'POINT'
            else:
                is_attribute = False
            if not is_attribute:
                 col.label(text="Please select a (Vertex > Float) Attribute for contouring.", icon='ERROR')
        elif props.contour_mode in ('TOPOLOGY','GEODESIC'):
            col.prop(props, "seeds_mode", text="Seeds")
            if props.seeds_mode == 'WEIGHT':
                col.prop_search(props, 'vertex_group_seed', ob0, "vertex_groups", text='Group')
        elif props.contour_mode == 'OBJECT':
            col.prop_search(props, "contour_vector_object", context.scene, "objects", text='Object')
        col.separator()

        if props.contour_mode == 'OBJECT':
            col.prop(props,'contour_offset')
            col.prop(props,'n_curves', text='Max Curves')
        elif props.contour_mode in ('VECTOR','GEODESIC','ATTRIBUTE'):
            col.prop(props,'contour_offset')
            row = col.row(align=True)
            row.prop(props,'min_value')
            row.prop(props,'range_value')
            col.prop(props,'n_curves', text='Max Curves')
        elif props.contour_mode in ('TOPOLOGY', 'WEIGHT'):
            row = col.row(align=True)
            row.prop(props,'min_value')
            row.prop(props,'range_value')
            col.prop(props,'n_curves')

        col.separator()
        col.label(text='Curves Bevel:')
        col.prop(props,'variable_bevel')
        row = col.row(align=True)
        row.prop(props,'min_bevel_depth')
        row.prop(props,'max_bevel_depth')
        row2 = col.row(align=True)
        row2.prop_search(props, 'vertex_group_bevel', ob0, "vertex_groups", text='')
        if not props.variable_bevel:
            row.enabled = row2.enabled = False
        col.separator()

        col.label(text="Displace Pattern:")
        col.prop_search(props, 'vertex_group_pattern', ob0, "vertex_groups", text='')
        if props.vertex_group_pattern != '':
            col.separator()
            row = col.row(align=True)
            row.prop(props,'in_steps')
            row.prop(props,'out_steps')
            row = col.row(align=True)
            row.prop(props,'in_displace')
            row.prop(props,'out_displace')
            col.separator()
            row = col.row(align=True)
            row.label(text="Axis")
            row.prop(props,'displace_x', text="X", toggle=1)
            row.prop(props,'displace_y', text="Y", toggle=1)
            row.prop(props,'displace_z', text="Z", toggle=1)
        col.separator()
        row=col.row(align=True)

        col.label(text='Clean Curves:')
        col.prop(props,'clean_distance')
        col.prop(props,'remove_open_curves')

def contour_edges_pattern(operator, c, verts_count, iso_val, vertices, normals, filtered_edges, weight, pattern_weight, bevel_weight):
    # vertices indexes
    id0 = filtered_edges[:,0]
    id1 = filtered_edges[:,1]
    # vertices weight
    w0 = weight[id0]
    w1 = weight[id1]
    # weight condition
    bool_w0 = w0 <= iso_val
    bool_w1 = w1 <= iso_val

    # mask all edges that have one weight value below the iso value
    mask_new_verts = np.logical_xor(bool_w0, bool_w1)
    if not mask_new_verts.any():
        return np.array([[None]]), {}, np.array([[None]]), np.array([[None]])

    id0 = id0[mask_new_verts]
    id1 = id1[mask_new_verts]
    # filter arrays
    v0 = vertices[id0]
    v1 = vertices[id1]
    n0 = normals[id0]
    n1 = normals[id1]
    w0 = w0[mask_new_verts]
    w1 = w1[mask_new_verts]
    pattern0 = pattern_weight[id0]
    pattern1 = pattern_weight[id1]
    try:
        bevel0 = bevel_weight[id0]
        bevel1 = bevel_weight[id1]
    except: pass

    param = (iso_val - w0)/(w1-w0)
    if c%(operator.in_steps + operator.out_steps) < operator.in_steps:
        mult = operator.in_displace
    else:
        mult = operator.out_displace
    pattern_value = pattern0 + (pattern1-pattern0)*param
    try:
        bevel_value = bevel0 + (bevel1-bevel0)*param
        bevel_value = np.expand_dims(bevel_value,axis=1)
    except: bevel_value = None
    disp = pattern_value * mult

    param = np.expand_dims(param,axis=1)
    disp = np.expand_dims(disp,axis=1)
    verts = v0 + (v1-v0)*param
    norm = n0 + (n1-n0)*param
    axis = np.array((operator.displace_x, operator.displace_y, operator.displace_z))
    norm[:] *= axis
    verts = verts + norm*disp

    # indexes of edges with new vertices
    edges_index = filtered_edges[mask_new_verts][:,2]

    # remove all edges completely below the iso value
    #mask_edges = np.logical_not(np.logical_and(bool_w0, bool_w1))
    #filtered_edges = filtered_edges[mask_edges]
    return filtered_edges.astype("int"), edges_index, verts, bevel_value
