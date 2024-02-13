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
#                          (c)  Alessandro Zomparelli                          #
#                                     (2020)                                   #
#                                                                              #
# http://www.co-de-it.com/                                                     #
#                                                                              #
################################################################################

import bpy
import numpy as np

import colorsys
from numpy import *

from bpy.types import (
        Operator,
        Panel
        )

from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
    FloatVectorProperty,
    IntVectorProperty
)

from .utils import *

class random_materials(Operator):
    bl_idname = "object.random_materials"
    bl_label = "Random Materials"
    bl_description = "Assign random materials to the faces of the mesh"
    bl_options = {'REGISTER', 'UNDO'}

    prefix : StringProperty(
        name="Prefix", default="Random.", description="Name prefix")

    color_A : FloatVectorProperty(name="Color A",
                                    subtype='COLOR_GAMMA',
                                    min=0,
                                    max=1,
                                    default=[0,0,0])

    color_B : FloatVectorProperty(name="Color B",
                                    subtype='COLOR_GAMMA',
                                    min=0,
                                    max=1,
                                    default=[1,1,1])

    hue : FloatProperty(name="Hue", min=0, max=1, default=0.5)
    hue_variation : FloatProperty(name="Hue Variation", min=0, max=1, default=0.6)

    seed : IntProperty(
        name="Seed", default=0, description="Random seed")

    count : IntProperty(
        name="Count", default=3, min=2, description="Count of random materials")

    generate_materials : BoolProperty(
        name="Generate Materials", default=False, description="Automatically generates new materials")

    random_colors : BoolProperty(
        name="Random Colors", default=True, description="Colors are automatically generated")

    executed = False

    @classmethod
    def poll(cls, context):
        try: return context.object.type == 'MESH'
        except: return False

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "seed")
        col.prop(self, "generate_materials")
        if self.generate_materials:
            col.prop(self, "prefix")
            col.separator()
            col.prop(self, "count")
            #row = col.row(align=True)
            col.separator()
            col.label(text='Colors:')
            col.prop(self, "hue")
            col.prop(self, "hue_variation")
            #col.prop(self, "random_colors")
            if not self.random_colors:
                col.prop(self, "color_A")
                col.prop(self, "color_B")

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        ob = context.active_object
        if len(ob.material_slots) == 0 and not self.executed:
            self.generate_materials = True
        if self.generate_materials:
            colA = self.color_A
            colB = self.color_B
            h1 = (self.hue - self.hue_variation/2)
            h2 = (self.hue + self.hue_variation/2)
            count = self.count
            ob.data.materials.clear()
            materials = []
            for i in range(count):
                mat_name = '{}{:03d}'.format(self.prefix,i)
                mat = bpy.data.materials.new(mat_name)
                if self.random_colors:
                    mat.diffuse_color = colorsys.hsv_to_rgb((h1 + (h2-h1)/(count)*i)%1, 1, 1)[:] + (1,)
                else:
                    mat.diffuse_color = list(colA + (colB - colA)/(count-1)*i) + [1]
                ob.data.materials.append(mat)
        else:
            count = len(ob.material_slots)
        np.random.seed(seed=self.seed)
        n_faces = len(ob.data.polygons)
        if count > 0:
            rand = list(np.random.randint(count, size=n_faces))
            ob.data.polygons.foreach_set('material_index',rand)
            ob.data.update()
        self.executed = True
        return {'FINISHED'}

class weight_to_materials(Operator):
    bl_idname = "object.weight_to_materials"
    bl_label = "Weight to Materials"
    bl_description = "Assign materials to the faces of the mesh according to the active Vertex Group"
    bl_options = {'REGISTER', 'UNDO'}

    prefix : StringProperty(
        name="Prefix", default="Weight.", description="Name prefix")

    hue : FloatProperty(name="Hue", min=0, max=1, default=0.5)
    hue_variation : FloatProperty(name="Hue Variation", min=0, max=1, default=0.3)

    count : IntProperty(
        name="Count", default=3, min=2, description="Count of random materials")

    generate_materials : BoolProperty(
        name="Generate Materials", default=False, description="Automatically generates new materials")

    mode : EnumProperty(
        items=(
                ('MIN', "Min", "Use the min weight value"),
                ('MAX', "Max", "Use the max weight value"),
                ('MEAN', "Mean", "Use the mean weight value")
                ),
        default='MEAN',
        name="Mode"
        )

    vg = None

    @classmethod
    def poll(cls, context):
        try: return context.object.type == 'MESH'
        except: return False

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "mode")
        col.prop(self, "generate_materials")
        if self.generate_materials:
            col.prop(self, "prefix")
            col.separator()
            col.prop(self, "count")
            #row = col.row(align=True)
            col.separator()
            col.label(text='Colors:')
            col.prop(self, "hue")
            col.prop(self, "hue_variation")

    def execute(self, context):
        ob = context.active_object
        if self.vg == None:
            self.vg = ob.vertex_groups.active_index
        vg = ob.vertex_groups[self.vg]
        if vg == None:
            self.report({'ERROR'}, "The selected object doesn't have any Vertex Group")
            return {'CANCELLED'}
        weight = get_weight_numpy(vg, len(ob.data.vertices))
        if self.generate_materials:
            h1 = (self.hue - self.hue_variation/2)
            h2 = (self.hue + self.hue_variation/2)
            count = self.count
            ob.data.materials.clear()
            materials = []
            for i in range(count):
                mat_name = '{}{:03d}'.format(self.prefix,i)
                mat = bpy.data.materials.new(mat_name)
                mat.diffuse_color = colorsys.hsv_to_rgb((h1 + (h2-h1)/(count)*i)%1, 1, 1)[:] + (1,)
                ob.data.materials.append(mat)
        else:
            count = len(ob.material_slots)

        faces_weight = []
        for p in ob.data.polygons:
            verts_id = np.array([v for v in p.vertices])
            face_weight = weight[verts_id]
            if self.mode == 'MIN': w = face_weight.min()
            if self.mode == 'MAX': w = face_weight.max()
            if self.mode == 'MEAN': w = face_weight.mean()
            faces_weight.append(w)
        faces_weight = np.array(faces_weight)
        faces_weight = faces_weight * count
        faces_weight = list(faces_weight.astype('int'))
        ob.data.polygons.foreach_set('material_index', faces_weight)
        ob.data.update()
        bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}
