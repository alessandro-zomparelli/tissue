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
        IntProperty,
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
        convert_object_to_mesh,
        get_weight_numpy
        )


def anim_curve_active(self, context):
    ob = context.object
    props = ob.tissue_to_curve
    try:
        props.object.name
        if not ob.tissue.bool_lock:
            bpy.ops.object.tissue_convert_to_curve_update()
    except: pass


class tissue_to_curve_prop(PropertyGroup):
    object : PointerProperty(
        type=bpy.types.Object,
        name="",
        description="Source object",
        update = anim_curve_active
    )
    bool_smooth : BoolProperty(
        name="Smooth Shading",
        default=True,
        description="Output faces with smooth shading rather than flat shaded",
        update = anim_curve_active
        )
    bool_lock : BoolProperty(
        name="Lock",
        description="Prevent automatic update on settings changes or if other objects have it in the hierarchy.",
        default=False,
        update = anim_curve_active
        )
    bool_dependencies : BoolProperty(
        name="Update Dependencies",
        description="Automatically updates source object as well, when possible",
        default=False,
        update = anim_curve_active
        )
    bool_run : BoolProperty(
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
    use_endpoint_u : BoolProperty(
        name="Endpoint U",
        default=False,
        description="Make all open nurbs curve meet the endpoints",
        update = anim_curve_active
        )
    clean_distance : FloatProperty(
        name="Merge Distance", default=0, min=0, soft_max=10,
        description="Merge Distance",
        update = anim_curve_active
        )
    nurbs_order : IntProperty(
        name="Order", default=4, min=2, max=6,
        description="Nurbs order",
        update = anim_curve_active
        )
    spline_type : EnumProperty(
        items=(
                ('POLY', "Poly", ""),
                ('BEZIER', "Bezier", ""),
                ('NURBS', "NURBS", "")
                ),
        default='POLY',
        name="Spline Type",
        update = anim_curve_active
        )
    mode : EnumProperty(
        items=(
                ('BOUNDS', "Boundaries", ""),
                ('EDGES', "Edges", ""),
                ('CONTINUOUS', "Continuous", "")
                ),
        default='BOUNDS',
        name="Conversion Mode",
        update = anim_curve_active
        )
    vertex_group : StringProperty(
        name="Radius", default='',
        description="Vertex Group used for variable radius",
        update = anim_curve_active
        )
    invert_vertex_group : BoolProperty(default=False,
        description='Inverte the value of the Vertex Group',
        update = anim_curve_active
        )
    vertex_group_factor : FloatProperty(
        name="Factor",
        default=0,
        min=0,
        max=1,
        description="Depth bevel factor to use for zero vertex group influence",
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
    bool_smooth : BoolProperty(
        name="Smooth Shading",
        default=True,
        description="Output faces with smooth shading rather than flat shaded"
        )
    '''
    bool_lock : BoolProperty(
        name="Lock",
        description="Prevent automatic update on settings changes or if other objects have it in the hierarchy.",
        default=False
        )
    bool_dependencies : BoolProperty(
        name="Update Dependencies",
        description="Automatically updates source object as well, when possible",
        default=False
        )
    bool_run : BoolProperty(
        name="Animatable Curve",
        description="Automatically recompute the conversion when the frame is changed.",
        default = False
        )
    '''
    use_modifiers : BoolProperty(
        name="Use Modifiers",
        default=False,
        description="Automatically apply Modifiers and Shape Keys"
        )
    use_endpoint_u : BoolProperty(
        name="Endpoint U",
        default=False,
        description="Make all open nurbs curve meet the endpoints"
        )
    nurbs_order : IntProperty(
        name="Order", default=4, min=2, max=6,
        description="Nurbs order"
        )
    clean_distance : FloatProperty(
        name="Merge Distance", default=0, min=0, soft_max=10,
        description="Merge Distance"
        )
    spline_type : EnumProperty(
        items=(
                ('POLY', "Poly", ""),
                ('BEZIER', "Bezier", ""),
                ('NURBS', "NURBS", "")
                ),
        default='POLY',
        name="Spline Type"
        )
    mode : EnumProperty(
        items=(
                ('BOUNDS', "Boundaries", ""),
                ('EDGES', "Edges", ""),
                ('CONTINUOUS', "Continuous", "")
                ),
        default='BOUNDS',
        name="Conversion Mode"
        )
    vertex_group : StringProperty(
        name="Radius", default='',
        description="Vertex Group used for variable radius"
        )
    invert_vertex_group : BoolProperty(default=False,
        description='Inverte the value of the Vertex Group'
        )
    vertex_group_factor : FloatProperty(
        name="Factor",
        default=0,
        min=0,
        max=1,
        description="Depth bevel factor to use for zero vertex group influence"
        )

    @classmethod
    def poll(cls, context):
        try:
            #bool_tessellated = context.object.tissue_tessellate.generator != None
            ob = context.object
            return ob.type in ('MESH','CURVE','SURFACE','FONT') and ob.mode == 'OBJECT'# and bool_tessellated
        except:
            return False

    def invoke(self, context, event):
        self.object = context.object.name
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        ob = context.object
        ob0 = bpy.data.objects[self.object]
        #props = ob.tissue_to_curve
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        row.label(text='Object: ' + self.object)
        #row.prop_search(self, "object", context.scene, "objects")
        row.prop(self, "use_modifiers")#, icon='MODIFIER', text='')
        col.separator()
        col.label(text='Conversion Mode:')
        row = col.row(align=True)
        row.prop(
            self, "mode", text="Conversion Mode", icon='NONE', expand=True,
            slider=False, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        col.separator()
        col.label(text='Spline Type:')
        row = col.row(align=True)
        row.prop(
            self, "spline_type", text="Spline Type", icon='NONE', expand=True,
            slider=False, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        if self.spline_type == 'NURBS':
            col.separator()
            col.label(text='Nurbs splines:')
            row = col.row(align=True)
            row.prop(self, "use_endpoint_u")
            row.prop(self, "nurbs_order")
        col.separator()
        col.prop(self, "bool_smooth")
        if ob0.type == 'MESH':
            col.separator()
            col.label(text='Variable Radius:')
            row = col.row(align=True)
            row.prop_search(self, 'vertex_group', ob0, "vertex_groups", text='')
            row.prop(self, "invert_vertex_group", text="", toggle=True, icon='ARROW_LEFTRIGHT')
            row.prop(self, "vertex_group_factor")
        col.separator()
        col.label(text='Clean curves:')
        col.prop(self, "clean_distance")

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

        new_ob.tissue.tissue_type = 'TO_CURVE'
        props = new_ob.tissue_to_curve
        props.object = ob
        #props.bool_run = self.bool_run
        props.use_modifiers = self.use_modifiers
        props.clean_distance = self.clean_distance
        props.spline_type = self.spline_type
        props.mode = self.mode
        props.use_endpoint_u = self.use_endpoint_u
        props.nurbs_order = self.nurbs_order
        props.vertex_group = self.vertex_group
        props.vertex_group_factor = self.vertex_group_factor
        props.invert_vertex_group = self.invert_vertex_group
        props.bool_smooth = self.bool_smooth
        #props.bool_lock = self.bool_lock
        #props.bool_dependencies = self.bool_dependencies

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
        ob = context.object
        props = ob.tissue_to_curve
        ob0 = props.object
        ob0 = convert_object_to_mesh(ob0, apply_modifiers=props.use_modifiers)
        me = ob0.data
        if props.mode == 'BOUNDS':
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.edges.ensure_lookup_table()
            edges = [me.edges[e.index] for e in bm.edges if e.is_boundary]
        #elif props.mode == 'CONTINUOUS':
        #    bm = bmesh.new()
        #    bm.from_mesh(me)
        #    bm.edges.ensure_lookup_table()
        #    edges = loops_from_bmesh(bm)
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

        try:
            weight = get_weight_numpy(ob0.vertex_groups[props.vertex_group], n_verts)
            if props.invert_vertex_group: weight = 1-weight
            fact = props.vertex_group_factor
            if fact > 0:
                weight = weight*(1-fact) + fact
        except:
            weight = None

        update_curve_from_pydata(ob.data, verts, weight, ordered_points, merge_distance=props.clean_distance)
        for s in ob.data.splines:
            s.type = props.spline_type
            if s.type == 'NURBS':
                s.use_endpoint_u = props.use_endpoint_u
                s.order_u = props.nurbs_order
        ob.data.splines.update()
        bpy.data.objects.remove(ob0)
        if not props.bool_smooth: bpy.ops.object.shade_flat()

        return {'FINISHED'}


class TISSUE_PT_convert_to_curve(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_label = "Tissue Convert to Curve"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try:
            #bool_curve = context.object.tissue_to_curve.object != None
            ob = context.object
            return ob.type == 'CURVE' and ob.tissue.tissue_type == 'TO_CURVE'
        except:
            return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_to_curve

        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        #col.operator("object.tissue_convert_to_curve_update", icon='FILE_REFRESH', text='Refresh')
        row.operator("object.tissue_update_tessellate_deps", icon='FILE_REFRESH', text='Refresh') ####
        lock_icon = 'LOCKED' if ob.tissue.bool_lock else 'UNLOCKED'
        #lock_icon = 'PINNED' if props.bool_lock else 'UNPINNED'
        deps_icon = 'LINKED' if ob.tissue.bool_dependencies else 'UNLINKED'
        row.prop(ob.tissue, "bool_dependencies", text="", icon=deps_icon)
        row.prop(ob.tissue, "bool_lock", text="", icon=lock_icon)
        col2 = row.column(align=True)
        col2.prop(ob.tissue, "bool_run", text="",icon='TIME')
        col2.enabled = not ob.tissue.bool_lock

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
        if props.spline_type == 'NURBS':
            col.separator()
            col.label(text='Nurbs Splines:')
            row = col.row(align=True)
            row.prop(props, "use_endpoint_u")
            row.prop(props, "nurbs_order")
        col.separator()
        col.prop(props, "bool_smooth")
        if props.object.type == 'MESH':
            col.separator()
            col.label(text='Variable Radius:')
            row = col.row(align=True)
            row.prop_search(props, 'vertex_group', props.object, "vertex_groups", text='')
            row.prop(props, "invert_vertex_group", text="", toggle=True, icon='ARROW_LEFTRIGHT')
            row.prop(props, "vertex_group_factor")
        col.separator()
        col.label(text='Clean Curves:')
        col.prop(props, "clean_distance")
