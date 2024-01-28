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
from mathutils import Vector
from math import pi
from .utils import (
        find_curves,
        update_curve_from_pydata,
        simple_to_mesh,
        convert_object_to_mesh,
        get_weight_numpy,
        loops_from_bmesh,
        get_mesh_before_subs,
        tissue_time
        )
import time


def anim_curve_active(self, context):
    ob = context.object
    props = ob.tissue_to_curve
    try:
        props.object.name
        if not ob.tissue.bool_lock:
            bpy.ops.object.tissue_update_convert_to_curve()
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
        default=True,
        description="Automatically apply Modifiers and Shape Keys",
        update = anim_curve_active
        )
    subdivision_mode : EnumProperty(
        items=(
                ('ALL', "All", ""),
                ('CAGE', "Cage", ""),
                ('INNER', "Inner", "")
                ),
        default='CAGE',
        name="Subdivided Edges",
        update = anim_curve_active
        )
    use_endpoint_u : BoolProperty(
        name="Endpoint U",
        default=True,
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
    system : IntProperty(
        name="System", default=0, min=0,
        description="Particle system index",
        update = anim_curve_active
        )
    bounds_selection : EnumProperty(
        items=(
                ('ALL', "All", ""),
                ('BOUNDS', "Boundaries", ""),
                ('INNER', "Inner", "")
                ),
        default='ALL',
        name="Boundary Selection",
        update = anim_curve_active
        )
    periodic_selection : EnumProperty(
        items=(
                ('ALL', "All", ""),
                ('OPEN', "Open", ""),
                ('CLOSED', "Closed", "")
                ),
        default='ALL',
        name="Periodic Selection",
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
                ('LOOPS', "Loops", ""),
                ('EDGES', "Edges", ""),
                ('PARTICLES', "Particles", "")
                ),
        default='LOOPS',
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
    only_sharp : BoolProperty(
        default=False,
        name="Only Sharp Edges",
        description='Convert only Sharp edges',
        update = anim_curve_active
        )
    pattern_depth : FloatProperty(
        name="Depth",
        default=0.02,
        min=0,
        soft_max=10,
        description="Displacement pattern depth",
        update = anim_curve_active
        )
    pattern_offset : FloatProperty(
        name="Offset",
        default=0,
        soft_min=-1,
        soft_max=1,
        description="Displacement pattern offset",
        update = anim_curve_active
        )
    pattern0 : IntProperty(
        name="Step 0",
        default=0,
        min=0,
        soft_max=10,
        description="Pattern step 0",
        update = anim_curve_active
        )
    pattern1 : IntProperty(
        name="Step 1",
        default=0,
        min=0,
        soft_max=10,
        description="Pattern step 1",
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
    use_modifiers : BoolProperty(
        name="Use Modifiers",
        default=True,
        description="Automatically apply Modifiers and Shape Keys"
        )
    subdivision_mode : EnumProperty(
        items=(
                ('ALL', "All", ""),
                ('CAGE', "Cage", ""),
                ('INNER', "Inner", "")
                ),
        default='CAGE',
        name="Subdivided Edges"
        )
    use_endpoint_u : BoolProperty(
        name="Endpoint U",
        default=True,
        description="Make all open nurbs curve meet the endpoints"
        )
    nurbs_order : IntProperty(
        name="Order", default=4, min=2, max=6,
        description="Nurbs order"
        )
    system : IntProperty(
        name="System", default=0, min=0,
        description="Particle system index"
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
    bounds_selection : EnumProperty(
        items=(
                ('ALL', "All", ""),
                ('BOUNDS', "Boundaries", ""),
                ('INNER', "Inner", "")
                ),
        default='ALL',
        name="Boundary Selection"
        )
    periodic_selection : EnumProperty(
        items=(
                ('ALL', "All", ""),
                ('OPEN', "Open", ""),
                ('CLOSED', "Closed", "")
                ),
        default='ALL',
        name="Periodic Selection"
        )
    mode : EnumProperty(
        items=(
                ('LOOPS', "Loops", ""),
                ('EDGES', "Edges", ""),
                ('PARTICLES', "Particles", "")
                ),
        default='LOOPS',
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
    only_sharp : BoolProperty(
        default=False,
        name="Only Sharp Edges",
        description='Convert only Sharp edges'
        )
    pattern_depth : FloatProperty(
        name="Depth",
        default=0.02,
        min=0,
        soft_max=10,
        description="Displacement pattern depth"
        )
    pattern_offset : FloatProperty(
        name="Offset",
        default=0,
        soft_min=-1,
        soft_max=1,
        description="Displacement pattern offset"
        )
    pattern0 : IntProperty(
        name="Step 0",
        default=0,
        min=0,
        soft_max=10,
        description="Pattern step 0"
        )
    pattern1 : IntProperty(
        name="Step 1",
        default=0,
        min=0,
        soft_max=10,
        description="Pattern step 1"
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
        #row.label(text='Object: ' + self.object)
        #row.prop_search(self, "object", context.scene, "objects")
        #row.prop(self, "use_modifiers")#, icon='MODIFIER', text='')
        col.separator()
        col.label(text='Conversion Mode:')
        row = col.row(align=True)
        row.prop(
            self, "mode", text="Conversion Mode", icon='NONE', expand=True,
            slider=False, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        if self.mode == 'PARTICLES':
            col.separator()
            col.prop(self, "system")
        col.separator()
        if self.mode in ('LOOPS', 'EDGES'):
            row = col.row(align=True)
            row.prop(self, "use_modifiers")
            col2 = row.column(align=True)
            if self.use_modifiers:
                col2.prop(self, "subdivision_mode", text='', icon='NONE', expand=False,
                         slider=True, toggle=False, icon_only=False, event=False,
                         full_event=False, emboss=True, index=-1)
                col2.enabled = False
            for m in bpy.data.objects[self.object].modifiers:
                if m.type in ('SUBSURF','MULTIRES'): col2.enabled = True
            col.separator()
            row = col.row(align=True)
            row.label(text='Filter Edges:')
            col2 = row.column(align=True)
            col2.prop(self, "bounds_selection", text='', icon='NONE', expand=False,
                     slider=True, toggle=False, icon_only=False, event=False,
                     full_event=False, emboss=True, index=-1)
            col2.prop(self, 'only_sharp')
            col.separator()
            if self.mode == 'LOOPS':
                row = col.row(align=True)
                row.label(text='Filter Loops:')
                row.prop(self, "periodic_selection", text='', icon='NONE', expand=False,
                         slider=True, toggle=False, icon_only=False, event=False,
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
        if ob0.type == 'MESH' and self.mode != 'PARTICLES':
            col.separator()
            col.label(text='Variable Radius:')
            row = col.row(align=True)
            row.prop_search(self, 'vertex_group', ob0, "vertex_groups", text='')
            row.prop(self, "invert_vertex_group", text="", toggle=True, icon='ARROW_LEFTRIGHT')
            row.prop(self, "vertex_group_factor")
        col.separator()
        col.label(text='Clean curves:')
        col.prop(self, "clean_distance")
        col.separator()
        col.label(text='Displacement Pattern:')
        row = col.row(align=True)
        row.prop(self, "pattern0")
        row.prop(self, "pattern1")
        row = col.row(align=True)
        row.prop(self, "pattern_depth")
        row.prop(self, "pattern_offset")

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
        new_ob.tissue.bool_lock = True

        props = new_ob.tissue_to_curve
        props.object = ob
        props.use_modifiers = self.use_modifiers
        props.subdivision_mode = self.subdivision_mode
        props.clean_distance = self.clean_distance
        props.spline_type = self.spline_type
        props.mode = self.mode
        props.use_endpoint_u = self.use_endpoint_u
        props.nurbs_order = self.nurbs_order
        props.vertex_group = self.vertex_group
        props.vertex_group_factor = self.vertex_group_factor
        props.invert_vertex_group = self.invert_vertex_group
        props.bool_smooth = self.bool_smooth
        props.system = self.system
        props.periodic_selection = self.periodic_selection
        props.bounds_selection = self.bounds_selection
        props.only_sharp = self.only_sharp
        props.pattern0 = self.pattern0
        props.pattern1 = self.pattern1
        props.pattern_depth = self.pattern_depth
        props.pattern_offset = self.pattern_offset

        new_ob.tissue.bool_lock = False

        bpy.ops.object.tissue_update_convert_to_curve()

        return {'FINISHED'}

class tissue_update_convert_to_curve(Operator):
    bl_idname = "object.tissue_update_convert_to_curve"
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
        tissue_time(None,'Tissue: Convert to Curve of "{}"...'.format(ob.name), levels=0)
        start_time = time.time()

        props = ob.tissue_to_curve
        ob0 = props.object
        if props.mode == 'PARTICLES':
            eval_ob = ob0.evaluated_get(context.evaluated_depsgraph_get())
            system_id = min(props.system, len(eval_ob.particle_systems))
            psystem = eval_ob.particle_systems[system_id]
            ob.data.splines.clear()
            particles = psystem.particles
            for id,p in enumerate(particles):
                s = ob.data.splines.new('POLY')
                if psystem.settings.type == 'HAIR':
                    n_pts = len(p.hair_keys)
                    pts = [0]*3*n_pts
                    p.hair_keys.foreach_get('co',pts)
                    co = np.array(pts).reshape((-1,3))
                else:
                    n_pts = 2**psystem.settings.display_step + 1
                    pts = []
                    for i in range(n_pts):
                        vec = psystem.co_hair(eval_ob, particle_no=id,step=i)
                        vec = ob0.matrix_world.inverted() @ vec
                        pts.append(vec)
                    co = np.array(pts)
                w = np.ones(n_pts).reshape((n_pts,1))
                co = np.concatenate((co,w),axis=1).reshape((n_pts*4))
                s.points.add(n_pts-1)
                s.points.foreach_set('co',co)

        else:
            _ob0 = ob0
            ob0 = convert_object_to_mesh(ob0, apply_modifiers=props.use_modifiers)
            me = ob0.data
            n_verts = len(me.vertices)
            verts = [0]*n_verts*3
            me.vertices.foreach_get('co',verts)
            verts = np.array(verts).reshape((-1,3))

            normals = [0]*n_verts*3
            me.vertices.foreach_get('normal',normals)
            normals = np.array(normals).reshape((-1,3))
            #tilt = np.degrees(np.arcsin(normals[:,2]))
            #tilt = np.arccos(normals[:,2])/2

            verts = np.array(verts).reshape((-1,3))
            if props.mode in ('LOOPS','EDGES'):
                bm = bmesh.new()
                bm.from_mesh(me)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
                todo_edges = list(bm.edges)
                if props.use_modifiers and props.subdivision_mode != 'ALL':
                    me0, subs = get_mesh_before_subs(_ob0)
                    n_edges0 = len(me0.edges)
                    bpy.data.meshes.remove(me0)
                    if props.subdivision_mode == 'CAGE':
                        todo_edges = todo_edges[:n_edges0*(2**subs)]
                    elif props.subdivision_mode == 'INNER':
                        todo_edges = todo_edges[n_edges0*(2**subs):]

                if props.only_sharp:
                    _todo_edges = []
                    sharp_verts = []
                    for e in todo_edges:
                        edge = me.edges[e.index]
                        if edge.use_edge_sharp:
                            _todo_edges.append(e)
                            sharp_verts.append(edge.vertices[0])
                            sharp_verts.append(edge.vertices[1])
                    todo_edges = _todo_edges

                if props.bounds_selection == 'BOUNDS': todo_edges = [e for e in todo_edges if len(e.link_faces)<2]
                elif props.bounds_selection == 'INNER': todo_edges = [e for e in todo_edges if len(e.link_faces)>1]

                if props.mode == 'EDGES':
                    ordered_points = [[e.verts[0].index, e.verts[1].index] for e in todo_edges]
                elif props.mode == 'LOOPS':
                    vert_loops, edge_loops = loops_from_bmesh(todo_edges)
                    if props.only_sharp:
                        ordered_points = []
                        for loop in vert_loops:
                            loop_points = []
                            for v in loop:
                                if v.index in sharp_verts:
                                    loop_points.append(v.index)
                                else:
                                    if len(loop_points)>1:
                                        ordered_points.append(loop_points)
                                    loop_points = []
                            if len(loop_points)>1:
                                ordered_points.append(loop_points)
                        #ordered_points = [[v.index for v in loop if v.index in sharp_verts] for loop in vert_loops]
                    else:
                        ordered_points = [[v.index for v in loop] for loop in vert_loops]
                    if props.periodic_selection == 'CLOSED':
                        ordered_points = [points for points in ordered_points if points[0] == points[-1]]
                    elif props.periodic_selection == 'OPEN':
                        ordered_points = [points for points in ordered_points if points[0] != points[-1]]
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

            # Set curves Tilt
            '''
            tilt = []
            for points in ordered_points:
                if points[0] == points[-1]:             # Closed curve
                     pts0 = [points[-1]] + points[:-1]  # i-1
                     pts1 = points[:]                   # i
                     pts2 = points[1:] + [points[0]]    # 1+1
                else:                                   # Open curve
                    pts0 = [points[0]] + points[:-1]    # i-1
                    pts1 = points[:]                    # i
                    pts2 = points[1:] + [points[-1]]    # i+1
                curve_tilt = []
                for i0, i1, i2 in zip(pts0, pts1, pts2):
                    pt0 = Vector(verts[i0])
                    pt1 = Vector(verts[i1])
                    pt2 = Vector(verts[i2])
                    tan1 = (pt1-pt0).normalized()
                    tan2 = (pt2-pt1).normalized()
                    vec_tan = -(tan1 + tan2).normalized()
                    vec2 = vec_tan.cross(Vector((0,0,1)))
                    vec_z = vec_tan.cross(vec2)
                    nor = normals[i1]
                    if vec_z.length == 0:
                        vec_z = Vector(nor)
                    ang = vec_z.angle(nor)
                    if nor[2] < 0: ang = 2*pi-ang
                    #if vec_tan[0] > vec_tan[1] and nor[0]>0: ang = -ang
                    #if vec_tan[0] > vec_tan[2] and nor[0]>0: ang = -ang
                    #if vec_tan[0] < vec_tan[1] and nor[1]>0: ang = -ang
                    #if nor[0]*nor[1]*nor[2] < 0: ang = -ang
                    if nor[2] == 0: ang = -5*pi/4
                    #ang = max(ang, np.arccos(nor[2]))
                    curve_tilt.append(ang)
                    #curve_tilt.append(np.arccos(nor[2]))
                tilt.append(curve_tilt)
            '''
            depth = props.pattern_depth
            offset = props.pattern_offset
            pattern = [props.pattern0,props.pattern1]
            update_curve_from_pydata(ob.data, verts, normals, weight, ordered_points, merge_distance=props.clean_distance, pattern=pattern, depth=depth, offset=offset)


            bpy.data.objects.remove(ob0)
        for s in ob.data.splines:
            s.type = props.spline_type
            if s.type == 'NURBS':
                s.use_endpoint_u = props.use_endpoint_u
                s.order_u = props.nurbs_order
        ob.data.splines.update()
        if not props.bool_smooth: bpy.ops.object.shade_flat()

        tissue_time(start_time,'Convert to Curve',levels=0)

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
        row.prop_search(props, "object", context.scene, "objects")
        row.prop(props, "use_modifiers", icon='MODIFIER', text='')
        col.separator()
        col.label(text='Conversion Mode:')
        row = col.row(align=True)
        row.prop(
            props, "mode", icon='NONE', expand=True,
            slider=False, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        if props.mode == 'PARTICLES':
            col.separator()
            col.prop(props, "system")
        col.separator()

        if props.mode in ('LOOPS', 'EDGES'):
            row = col.row(align=True)
            row.prop(props, "use_modifiers")
            col2 = row.column(align=True)
            if props.use_modifiers:
                col2.prop(props, "subdivision_mode", text='', icon='NONE', expand=False,
                         slider=True, toggle=False, icon_only=False, event=False,
                         full_event=False, emboss=True, index=-1)
                col2.enabled = False
            for m in props.object.modifiers:
                if m.type in ('SUBSURF','MULTIRES'): col2.enabled = True
            col.separator()
            row = col.row(align=True)
            row.label(text='Filter Edges:')
            col2 = row.column(align=True)
            col2.prop(props, "bounds_selection", text='', icon='NONE', expand=False,
                     slider=True, toggle=False, icon_only=False, event=False,
                     full_event=False, emboss=True, index=-1)
            col2.prop(props, 'only_sharp')
            col.separator()
            if props.mode == 'LOOPS':
                row = col.row(align=True)
                row.label(text='Filter Loops:')
                row.prop(props, "periodic_selection", text='', icon='NONE', expand=False,
                         slider=True, toggle=False, icon_only=False, event=False,
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
        col.separator()
        col.label(text='Displacement Pattern:')
        row = col.row(align=True)
        row.prop(props, "pattern0")
        row.prop(props, "pattern1")
        row = col.row(align=True)
        row.prop(props, "pattern_depth")
        row.prop(props, "pattern_offset")
