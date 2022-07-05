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

# --------------------------------- UV to MESH ------------------------------- #
# -------------------------------- version 0.1.1 ----------------------------- #
#                                                                              #
# Create a new Mesh based on active UV                                         #
#                                                                              #
#                        (c)   Alessandro Zomparelli                           #
#                                    (2017)                                    #
#                                                                              #
# http://www.co-de-it.com/                                                     #
#                                                                              #
# ############################################################################ #

import bpy, bmesh
import math
from bpy.types import Operator
from bpy.props import BoolProperty
from mathutils import Vector
from .utils import *


class uv_to_mesh(Operator):
    bl_idname = "object.uv_to_mesh"
    bl_label = "UV to Mesh"
    bl_description = ("Create a new Mesh based on active UV")
    bl_options = {'REGISTER', 'UNDO'}

    apply_modifiers : BoolProperty(
            name="Apply Modifiers",
            default=True,
            description="Apply object's modifiers"
            )
    vertex_groups : BoolProperty(
            name="Keep Vertex Groups",
            default=True,
            description="Transfer all the Vertex Groups"
            )
    materials : BoolProperty(
            name="Keep Materials",
            default=True,
            description="Transfer all the Materials"
            )
    auto_scale : BoolProperty(
            name="Resize",
            default=True,
            description="Scale the new object in order to preserve the average surface area"
            )

    def execute(self, context):
        if context.mode == 'EDIT_MESH': on_selection = True
        else: on_selection = False

        bpy.ops.object.mode_set(mode='OBJECT')
        ob0 = context.object
        for o in bpy.context.view_layer.objects: o.select_set(False)
        ob0.select_set(True)

        name0 = ob0.name
        ob0 = convert_object_to_mesh(ob0, apply_modifiers=self.apply_modifiers, preserve_status=False)
        me0 = ob0.data
        area = 0
        verts = []
        faces = []
        face_materials = []
        if on_selection: polygons = [f for f in me0.polygons if f.select]
        else: polygons = me0.polygons
        bm = bmesh.new()

        for face in polygons:
            area += face.area
            uv_face = []
            store = False
            if len(me0.uv_layers) > 0:
                verts = []
                for loop in face.loop_indices:
                    uv = me0.uv_layers.active.data[loop].uv
                    if uv.x != 0 and uv.y != 0:
                        store = True
                    new_vert = bm.verts.new((uv.x, uv.y, 0))
                    verts.append(new_vert)
                if store:
                    new_face = bm.faces.new(verts)
                    new_face.material_index = face.material_index
            else:
                self.report({'ERROR'}, "Missing UV Map")
                return {'CANCELLED'}

        name = name0 + '_UV'
        # Create mesh and object
        me = bpy.data.meshes.new(name + 'Mesh')
        ob = bpy.data.objects.new(name, me)

        # Link object to scene and make active
        scn = bpy.context.scene
        bpy.context.collection.objects.link(ob)
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)

        # Create mesh from given verts, faces.
        bm.to_mesh(me)
        # Update mesh with new data
        me.update()

        if self.auto_scale:
            new_area = 0
            for p in me.polygons:
                new_area += p.area
            if new_area == 0:
                self.report({'ERROR'}, "Impossible to generate mesh from UV")
                bpy.data.objects.remove(ob0)
                return {'CANCELLED'}

        # VERTEX GROUPS
        if self.vertex_groups:
            for group in ob0.vertex_groups:
                index = group.index
                ob.vertex_groups.new(name=group.name)
                for p in polygons:
                    for vert, loop in zip(p.vertices, p.loop_indices):
                        try:
                            ob.vertex_groups[index].add([loop], group.weight(vert), 'REPLACE')
                        except:
                            pass

        ob0.select_set(False)
        if self.auto_scale:
            scaleFactor = math.pow(area / new_area, 1 / 2)
            ob.scale = Vector((scaleFactor, scaleFactor, scaleFactor))

        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        bpy.ops.mesh.remove_doubles(threshold=1e-06)
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        # MATERIALS
        if self.materials:
            if len(ob0.material_slots) > 0:
                # assign old material
                uv_materials = [slot.material for slot in ob0.material_slots]
                for i in range(len(uv_materials)):
                    bpy.ops.object.material_slot_add()
                    bpy.context.object.material_slots[i].material = uv_materials[i]

        bpy.data.objects.remove(ob0)
        bpy.data.meshes.remove(me0)
        return {'FINISHED'}
