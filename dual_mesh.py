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


import bpy
from bpy.types import Operator
from bpy.props import (
        BoolProperty,
        EnumProperty,
        )
import bmesh
from .utils import *


class dual_mesh_tessellated(Operator):
    bl_idname = "object.dual_mesh_tessellated"
    bl_label = "Dual Mesh"
    bl_description = ("Generate a polygonal mesh using Tessellate. (Non-destructive)")
    bl_options = {'REGISTER', 'UNDO'}

    apply_modifiers : BoolProperty(
        name="Apply Modifiers",
        default=True,
        description="Apply object's modifiers"
        )

    source_faces : EnumProperty(
            items=[
                ('QUAD', 'Quad Faces', ''),
                ('TRI', 'Triangles', '')],
            name="Source Faces",
            description="Triangles works with any geometry." \
                        "Quad option is faster when the object has only Quads",
            default="TRI",
            options={'LIBRARY_EDITABLE'}
            )

    link_component : BoolProperty(
        name="Editable Component",
        default=False,
        description="Add Component Object to the Scene"
        )

    def execute(self, context):
        auto_layer_collection()
        ob0 = context.object
        name1 = "DualMesh_{}_Component".format(self.source_faces)
        # Generate component
        if self.source_faces == 'QUAD':
            verts = [(1.0, 0.0, 0.0), (0.5, 0.0, 0.0),
                    (0.0, 0.0, 0.0), (0.0, 0.5, 0.0),
                    (0.0, 1.0, 0.0), (0.5, 1.0, 0.0),
                    (1.0, 1.0, 0.0), (1.0, 0.5, 0.0),
                    (2/3, 1/3, 0.0), (1/3, 2/3, 0.0)]
            edges = [(0,1), (1,2), (2,3), (3,4), (4,5), (5,6), (6,7),
                        (7,0), (1,8), (8,7), (3,9), (9,5), (8,9)]
            faces = [(7,8,1,0), (8,9,3,2,1), (9,5,4,3), (9,8,7,6,5)]
        else:
            verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                    (0.0, 1.0, 0.0), (1.0, 1.0, 0.0),
                    (0.5, 1/3, 0.0), (0.0, 0.5, 0.0),
                    (1.0, 0.5, 0.0), (0.5, 0.0, 0.0)]
            edges = [(0,5), (1,7), (3,6), (2,3), (2,5), (1,6), (0,7),
                        (4,5), (4,7), (4,6)]
            faces = [(5,0,7,4), (7,1,6,4), (3,2,5,4,6)]

        # check pre-existing component
        try:
            _verts = [0]*len(verts)*3
            __verts = [c for co in verts for c in co]
            ob1 = bpy.data.objects[name1]
            ob1.data.vertices.foreach_get("co",_verts)
            for a, b in zip(_verts, __verts):
                if abs(a-b) > 0.0001:
                    raise ValueError
        except:
            me = bpy.data.meshes.new("Dual-Mesh")  # add a new mesh
            me.from_pydata(verts, edges, faces)
            me.update(calc_edges=True, calc_edges_loose=True)
            if self.source_faces == 'QUAD': seams = (0,1,2,3,4,5,6,9)
            else: seams = (0,1,2,3,4,5,7)
            for i in seams: me.edges[i].use_seam = True
            ob1 = bpy.data.objects.new(name1, me)
            # fix visualization issue
            if self.link_component:
                context.collection.objects.link(ob1)
                context.view_layer.objects.active = ob1
                ob1.select_set(True)
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.editmode_toggle()
                ob1.select_set(False)
                ob1.hide_render = True
        ob = convert_object_to_mesh(ob0,False,False)
        ob.name = 'DualMesh'
        ob.tissue.tissue_type = 'TESSELLATE'
        ob.tissue.bool_lock = True
        ob.tissue_tessellate.component = ob1
        ob.tissue_tessellate.generator = ob0
        ob.tissue_tessellate.gen_modifiers = self.apply_modifiers
        ob.tissue_tessellate.merge = True
        ob.tissue_tessellate.bool_dissolve_seams = True
        if self.source_faces == 'TRI': ob.tissue_tessellate.fill_mode = 'TRI'
        bpy.ops.object.tissue_update_tessellate()
        ob.tissue.bool_lock = False
        ob.location = ob0.location
        ob.matrix_world = ob0.matrix_world
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class dual_mesh(Operator):
    bl_idname = "object.dual_mesh"
    bl_label = "Convert to Dual Mesh"
    bl_description = ("Convert a generic mesh into a polygonal mesh. (Destructive)")
    bl_options = {'REGISTER', 'UNDO'}

    quad_method : EnumProperty(
            items=[('BEAUTY', 'Beauty',
                    'Split the quads in nice triangles, slower method'),
                    ('FIXED', 'Fixed',
                    'Split the quads on the 1st and 3rd vertices'),
                    ('FIXED_ALTERNATE', 'Fixed Alternate',
                    'Split the quads on the 2nd and 4th vertices'),
                    ('SHORTEST_DIAGONAL', 'Shortest Diagonal',
                    'Split the quads based on the distance between the vertices')
                    ],
            name="Quad Method",
            description="Method for splitting the quads into triangles",
            default="FIXED",
            options={'LIBRARY_EDITABLE'}
            )
    polygon_method : EnumProperty(
            items=[
                ('BEAUTY', 'Beauty', 'Arrange the new triangles evenly'),
                ('CLIP', 'Clip',
                 'Split the N-gon with an ear clipping algorithm')],
            name="N-gon Method",
            description="Method for splitting the N-gons into triangles",
            default="BEAUTY",
            options={'LIBRARY_EDITABLE'}
            )
    preserve_borders : BoolProperty(
            name="Preserve Borders",
            default=True,
            description="Preserve original borders"
            )
    apply_modifiers : BoolProperty(
            name="Apply Modifiers",
            default=True,
            description="Apply object's modifiers"
            )

    def execute(self, context):
        mode = context.mode
        if mode == 'EDIT_MESH':
            mode = 'EDIT'
        act = context.active_object
        if mode != 'OBJECT':
            sel = [act]
            bpy.ops.object.mode_set(mode='OBJECT')
        else:
            sel = context.selected_objects
        doneMeshes = []

        for ob0 in sel:
            if ob0.type != 'MESH':
                continue
            if ob0.data.name in doneMeshes:
                continue
            ob = ob0
            mesh_name = ob0.data.name

            # store linked objects
            clones = []
            n_users = ob0.data.users
            count = 0
            for o in bpy.data.objects:
                if o.type != 'MESH':
                    continue
                if o.data.name == mesh_name:
                    count += 1
                    clones.append(o)
                if count == n_users:
                    break

            if self.apply_modifiers:
                bpy.ops.object.convert(target='MESH')
            ob.data = ob.data.copy()
            bpy.ops.object.select_all(action='DESELECT')
            ob.select_set(True)
            context.view_layer.objects.active = ob0
            bpy.ops.object.mode_set(mode='EDIT')

            # prevent borders erosion
            bpy.ops.mesh.select_mode(
                    use_extend=False, use_expand=False, type='EDGE'
                    )
            bpy.ops.mesh.select_non_manifold(
                    extend=False, use_wire=False, use_boundary=True,
                    use_multi_face=False, use_non_contiguous=False,
                    use_verts=False
                    )
            bpy.ops.mesh.extrude_region_move(
                    MESH_OT_extrude_region={"mirror": False},
                    TRANSFORM_OT_translate={"value": (0, 0, 0)}
                    )

            bpy.ops.mesh.select_mode(
                    use_extend=False, use_expand=False, type='VERT',
                    action='TOGGLE'
                    )
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.quads_convert_to_tris(
                    quad_method=self.quad_method, ngon_method=self.polygon_method
                    )
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.modifier_add(type='SUBSURF')
            ob.modifiers[-1].name = "dual_mesh_subsurf"
            while True:
                bpy.ops.object.modifier_move_up(modifier="dual_mesh_subsurf")
                if ob.modifiers[0].name == "dual_mesh_subsurf":
                    break

            bpy.ops.object.modifier_apply(modifier='dual_mesh_subsurf')

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')

            verts = ob.data.vertices

            bpy.ops.object.mode_set(mode='OBJECT')
            verts[-1].select = True
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_more(use_face_step=False)

            bpy.ops.mesh.select_similar(
                type='VERT_EDGES', compare='EQUAL', threshold=0.01)
            bpy.ops.mesh.select_all(action='INVERT')

            bpy.ops.mesh.dissolve_verts()
            bpy.ops.mesh.select_all(action='DESELECT')

            bpy.ops.mesh.select_non_manifold(
                extend=False, use_wire=False, use_boundary=True,
                use_multi_face=False, use_non_contiguous=False, use_verts=False)
            bpy.ops.mesh.select_more()

            # find boundaries
            bpy.ops.object.mode_set(mode='OBJECT')
            bound_v = [v.index for v in ob.data.vertices if v.select]
            bound_e = [e.index for e in ob.data.edges if e.select]
            bound_p = [p.index for p in ob.data.polygons if p.select]
            bpy.ops.object.mode_set(mode='EDIT')

            # select quad faces
            context.tool_settings.mesh_select_mode = (False, False, True)
            bpy.ops.mesh.select_face_by_sides(number=4, extend=False)

            # deselect boundaries
            bpy.ops.object.mode_set(mode='OBJECT')
            for i in bound_v:
                context.active_object.data.vertices[i].select = False
            for i in bound_e:
                context.active_object.data.edges[i].select = False
            for i in bound_p:
                context.active_object.data.polygons[i].select = False

            bpy.ops.object.mode_set(mode='EDIT')

            context.tool_settings.mesh_select_mode = (False, False, True)
            bpy.ops.mesh.edge_face_add()
            context.tool_settings.mesh_select_mode = (True, False, False)
            bpy.ops.mesh.select_all(action='DESELECT')

            # delete boundaries
            bpy.ops.mesh.select_non_manifold(
                    extend=False, use_wire=True, use_boundary=True,
                    use_multi_face=False, use_non_contiguous=False, use_verts=True
                    )
            bpy.ops.mesh.delete(type='VERT')

            # remove middle vertices
            bm = bmesh.from_edit_mesh(ob.data)
            for v in bm.verts:
                if len(v.link_edges) == 2 and len(v.link_faces) < 3:
                    v.select = True

            # dissolve
            bpy.ops.mesh.dissolve_verts()
            bpy.ops.mesh.select_all(action='DESELECT')

            # remove border faces
            if not self.preserve_borders:
                bpy.ops.mesh.select_non_manifold(
                    extend=False, use_wire=False, use_boundary=True,
                    use_multi_face=False, use_non_contiguous=False, use_verts=False
                    )
                bpy.ops.mesh.select_more()
                bpy.ops.mesh.delete(type='FACE')

            # clean wires
            bpy.ops.mesh.select_non_manifold(
                    extend=False, use_wire=True, use_boundary=False,
                    use_multi_face=False, use_non_contiguous=False, use_verts=False
                    )
            bpy.ops.mesh.delete(type='EDGE')

            bpy.ops.object.mode_set(mode='OBJECT')
            ob0.data.name = mesh_name
            doneMeshes.append(mesh_name)

            for o in clones:
                o.data = ob.data
            bm.free()

        for o in sel:
            o.select_set(True)

        context.view_layer.objects.active = act
        bpy.ops.object.mode_set(mode=mode)

        return {'FINISHED'}
