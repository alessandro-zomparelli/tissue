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

# --------------------------------- DUAL MESH -------------------------------- #
# -------------------------------- version 0.3 ------------------------------- #
#                                                                              #
# Convert a generic mesh to its dual. With open meshes it can get some wired   #
# effect on the borders.                                                       #
#                                                                              #
#                        (c)   Alessandro Zomparelli                           #
#                                    (2017)                                    #
#                                                                              #
# http://www.co-de-it.com/                                                     #
#                                                                              #
# ############################################################################ #


import bpy, bmesh
from bpy.types import Operator
from bpy.props import (
        BoolProperty,
        EnumProperty,
        PointerProperty,
        StringProperty,
        FloatProperty
        )
from bpy.types import (
        Operator,
        Panel,
        PropertyGroup,
        )

import numpy as np

from .utils import (
        find_curves,
        update_curve_from_pydata,
        simple_to_mesh,
        convert_object_to_mesh
        )


def anim_curve_active(self, context):
    ob = context.object
    props = ob.tissue_to_curve
    try:
        props.object.name
        bpy.ops.object.tissue_convert_to_curve_update()
    except: pass


class tissue_to_curve_prop(PropertyGroup):
    object : PointerProperty(
        type=bpy.types.Object,
        name="",
        description="Source object",
        update = anim_curve_active
    )
    animate : BoolProperty(
        name="Animatable Curve",
        description="Automatically recompute the conversion when the frame is changed.",
        default = False
        )
    use_modifiers : BoolProperty(
        name="Use Modifiers",
        default=False,
        description="Automatically apply Modifiers and Shape Keys",
        update = anim_curve_active
        )
    clean_distance : FloatProperty(
        name="Merge Distance", default=0, min=0, soft_max=10,
        description="Merge Distance",
        update = anim_curve_active
        )
    spline_type : EnumProperty(
        items=(
                ('BEZIER', "Bezier", ""),
                ('NURBS', "NURBS", ""),
                ('POLY', "Poly", "")
                ),
        default='POLY',
        name="Spline Type",
        update = anim_curve_active
        )
    mode : EnumProperty(
        items=(
                ('EDGES', "Edges", ""),
                ('CONTINUOUS', "Continuous", ""),
                ('BOUNDS', "Boundaries", "")
                ),
        default='EDGES',
        name="Conversion Mode",
        update = anim_curve_active
        )

class tissue_convert_to_curve(Operator):
    bl_idname = "object.tissue_convert_to_curve"
    bl_label = "Tissue Convert to Curve"
    bl_description = "Convert selected mesh to Curve object"
    bl_options = {'REGISTER', 'UNDO'}

    object : StringProperty(
        name="",
        description="Source object",
        default = ""
    )
    animate : BoolProperty(
        name="Animatable Curve",
        description="Automatically recompute the conversion when the frame is changed.",
        default = False
        )
    use_modifiers : BoolProperty(
        name="Use Modifiers",
        default=False,
        description="Automatically apply Modifiers and Shape Keys"
        )
    clean_distance : FloatProperty(
        name="Merge Distance", default=0, min=0, soft_max=10,
        description="Merge Distance"
        )
    spline_type : EnumProperty(
        items=(
                ('BEZIER', "Bezier", ""),
                ('NURBS', "NURBS", ""),
                ('POLY', "Poly", "")
                ),
        default='POLY',
        name="Spline Type"
        )
    mode : EnumProperty(
        items=(
                ('EDGES', "Edges", ""),
                ('CONTINUOUS', "Continuous", ""),
                ('BOUNDS', "Boundaries", "")
                ),
        default='EDGES',
        name="Conversion Mode"
        )

    @classmethod
    def poll(cls, context):
        try:
            #bool_tessellated = context.object.tissue_tessellate.generator != None
            ob = context.object
            return ob.type in ('MESH','CURVE','SURFACE','FONT') and ob.mode == 'OBJECT'# and bool_tessellated
        except:
            return False

    def execute(self, context):
        ob = context.active_object

        crv = bpy.data.curves.new(ob.name + '_Curve', type='CURVE')
        crv.dimensions = '3D'
        new_ob = bpy.data.objects.new(ob.name + '_Curve', crv)
        bpy.context.collection.objects.link(new_ob)
        context.view_layer.objects.active = new_ob

        new_ob.select_set(True)
        ob.select_set(False)
        new_ob.matrix_world = ob.matrix_world

        props = new_ob.tissue_to_curve
        props.object = ob
        props.animate = self.animate
        props.use_modifiers = self.use_modifiers
        props.clean_distance = self.clean_distance
        props.spline_type = self.spline_type
        props.mode = self.mode

        bpy.ops.object.tissue_convert_to_curve_update()

        return {'FINISHED'}

class tissue_convert_to_curve_update(Operator):
    bl_idname = "object.tissue_convert_to_curve_update"
    bl_label = "Tissue Update Curve"
    bl_description = "Update Curve object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            ob = context.object
            bool_curve = ob.tissue_to_curve.object != None
            return ob.type == 'CURVE' and ob.mode == 'OBJECT' and bool_curve
        except:
            return False

    def execute(self, context):
        ob = context.active_object
        props = ob.tissue_to_curve
        ob0 = props.object
        ob0 = convert_object_to_mesh(ob0, apply_modifiers=props.use_modifiers)
        me = ob0.data
        if props.mode == 'BOUNDS':
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.edges.ensure_lookup_table()
            edges = [me.edges[e.index] for e in bm.edges if e.is_boundary]
        else:
            edges = me.edges
        edges = [e.vertices for e in edges]
        n_verts = len(me.vertices)
        verts = [0]*n_verts*3
        me.vertices.foreach_get('co',verts)
        verts = np.array(verts).reshape((-1,3))
        if props.mode == 'EDGES':
            ordered_points = edges
        else:
            try:
                ordered_points = find_curves(edges, n_verts)
            except:
                bpy.data.objects.remove(ob0)
                return {'CANCELLED'}
        update_curve_from_pydata(ob.data, verts, None, ordered_points, merge_distance=props.clean_distance)
        for s in ob.data.splines:
            s.type = props.spline_type
        bpy.data.objects.remove(ob0)

        return {'FINISHED'}


class TISSUE_PT_convert_to_curve(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_label = "Convert to Curve Settings"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try:
            #bool_curve = context.object.tissue_to_curve.object != None
            return context.object.type == 'CURVE'# and bool_curve
        except:
            return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_to_curve

        layout = self.layout
        col = layout.column(align=True)
        col.operator("object.tissue_convert_to_curve_update", icon='FILE_REFRESH', text='Refresh')
        col.separator()
        row = col.row(align=True)
        row.prop_search(props, "object", context.scene, "objects")
        row.prop(props, "use_modifiers", icon='MODIFIER', text='')
        col.separator()
        col.label(text='Conversion Mode:')
        row = col.row(align=True)
        row.prop(
            props, "mode", text="Conversion Mode", icon='NONE', expand=True,
            slider=False, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        col.separator()
        col.label(text='Spline Type:')
        row = col.row(align=True)
        row.prop(
            props, "spline_type", text="Spline Type", icon='NONE', expand=True,
            slider=False, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        col.separator()
        col.prop(props, "clean_distance")
