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
from statistics import mean, stdev
from mathutils import Vector
from mathutils.kdtree import KDTree
from numpy import *
try: import numexpr as ne
except: pass

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

class formula_prop(PropertyGroup):
    name : StringProperty()
    formula : StringProperty()
    float_var : FloatVectorProperty(name="", description="", default=(0, 0, 0, 0, 0), size=5)
    int_var : IntVectorProperty(name="", description="", default=(0, 0, 0, 0, 0), size=5)

from numpy import *
def compute_formula(ob=None, formula="rx", float_var=(0,0,0,0,0), int_var=(0,0,0,0,0)):
    verts = ob.data.vertices
    n_verts = len(verts)

    f1,f2,f3,f4,f5 = float_var
    i1,i2,i3,i4,i5 = int_var

    do_groups = "w[" in formula
    do_local = "lx" in formula or "ly" in formula or "lz" in formula
    do_global = "gx" in formula or "gy" in formula or "gz" in formula
    do_relative = "rx" in formula or "ry" in formula or "rz" in formula
    do_normal = "nx" in formula or "ny" in formula or "nz" in formula
    mat = ob.matrix_world

    for i in range(1000):
        if "w["+str(i)+"]" in formula and i > len(ob.vertex_groups)-1:
            return "w["+str(i)+"] not found"

    w = []
    for i in range(len(ob.vertex_groups)):
        w.append([])
        if "w["+str(i)+"]" in formula:
            vg = ob.vertex_groups[i]
            for v in verts:
                try:
                    w[i].append(vg.weight(v.index))
                except:
                    w[i].append(0)
            w[i] = array(w[i])

    start_time = timeit.default_timer()
    # compute vertex coordinates
    if do_local or do_relative or do_global:
        co = [0]*n_verts*3
        verts.foreach_get('co', co)
        np_co = array(co).reshape((n_verts, 3))
        lx, ly, lz = array(np_co).transpose()
        if do_relative:
            rx = np.interp(lx, (lx.min(), lx.max()), (0, +1))
            ry = np.interp(ly, (ly.min(), ly.max()), (0, +1))
            rz = np.interp(lz, (lz.min(), lz.max()), (0, +1))
        if do_global:
            co = [v.co for v in verts]
            global_co = []
            for v in co:
                global_co.append(mat @ v)
            global_co = array(global_co).reshape((n_verts, 3))
            gx, gy, gz = array(global_co).transpose()
    # compute vertex normals
    if do_normal:
        normal = [0]*n_verts*3
        verts.foreach_get('normal', normal)
        normal = array(normal).reshape((n_verts, 3))
        nx, ny, nz = array(normal).transpose()

    try:
        weight = eval(formula)
        return weight
    except:
        return "There is something wrong"
    print("Weight Formula: " + str(timeit.default_timer() - start_time))

class weight_formula_wiki(Operator):
    bl_idname = "scene.weight_formula_wiki"
    bl_label = "Online Documentation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.wm.url_open(url="https://github.com/alessandro-zomparelli/tissue/wiki/Weight-Tools#weight-formula")
        return {'FINISHED'}

class weight_formula(Operator):
    bl_idname = "object.weight_formula"
    bl_label = "Weight Formula"
    bl_description = "Generate a Vertex Group according to a mathematical formula"
    bl_options = {'REGISTER', 'UNDO'}

    ex_items = [
        ('cos(arctan(nx/ny)*i1*2 + sin(rz*i3))/i2 + cos(arctan(nx/ny)*i1*2 - sin(rz*i3))/i2 + 0.5','Vertical Spots'),
        ('cos(arctan(nx/ny)*i1*2 + sin(rz*i2))/2 + cos(arctan(nx/ny)*i1*2 - sin(rz*i2))/2','Vertical Spots'),
        ('(sin(arctan(nx/ny)*i1*2)*sin(nz*i1*2)+1)/2','Grid Spots'),
        ('cos(arctan(nx/ny)*f1)','Vertical Stripes'),
        ('cos(arctan(lx/ly)*f1 + sin(rz*f2)*f3)','Curly Stripes'),
        ('sin(rz*pi*i1+arctan2(nx,ny))/2+0.5', 'Vertical Spiral'),
        ('sin(nx*15)<sin(ny*15)','Chess'),
        ('cos(ny*rz**2*i1)','Hyperbolic'),
        ('sin(rx*30) > 0','Step Stripes'),
        ('sin(nz*i1)','Normal Stripes'),
        ('w[0]**2','Vertex Group square'),
        ('abs(0.5-rz)*2','Double vertical gradient'),
        ('rz', 'Vertical Gradient')
    ]
    _ex_items = list((str(i),'{}   ( {} )'.format(s[0],s[1]),s[1]) for i,s in enumerate(ex_items))
    _ex_items.append(('CUSTOM', "User Formula", ""))

    examples : EnumProperty(
        items = _ex_items, default='CUSTOM', name="Examples")

    old_ex = ""

    formula : StringProperty(
        name="Formula", default="", description="Formula to Evaluate")

    slider_f01 : FloatProperty(
        name="f1", default=1, description="Slider Float 1")
    slider_f02 : FloatProperty(
        name="f2", default=1, description="Slider Float 2")
    slider_f03 : FloatProperty(
        name="f3", default=1, description="Slider Float 3")
    slider_f04 : FloatProperty(
        name="f4", default=1, description="Slider Float 4")
    slider_f05 : FloatProperty(
        name="f5", default=1, description="Slider Float 5")
    slider_i01 : IntProperty(
        name="i1", default=1, description="Slider Integer 1")
    slider_i02 : IntProperty(
        name="i2", default=1, description="Slider Integer 2")
    slider_i03 : IntProperty(
        name="i3", default=1, description="Slider Integer 3")
    slider_i04 : IntProperty(
        name="i4", default=1, description="Slider Integer 4")
    slider_i05 : IntProperty(
        name="i5", default=1, description="Slider Integer 5")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        #layout.label(text="Examples")
        layout.prop(self, "examples", text="Examples")
        #if self.examples == 'CUSTOM':
        layout.label(text="Formula")
        layout.prop(self, "formula", text="")
        #try: self.examples = self.formula
        #except: pass

        if self.examples != 'CUSTOM':
            example = self.ex_items[int(self.examples)][0]
            if example != self.old_ex:
                self.formula = example
                self.old_ex = example
            elif self.formula != example:
                self.examples = 'CUSTOM'
        formula = self.formula

        layout.separator()
        if "f1" in formula: layout.prop(self, "slider_f01")
        if "f2" in formula: layout.prop(self, "slider_f02")
        if "f3" in formula: layout.prop(self, "slider_f03")
        if "f4" in formula: layout.prop(self, "slider_f04")
        if "f5" in formula: layout.prop(self, "slider_f05")
        if "i1" in formula: layout.prop(self, "slider_i01")
        if "i2" in formula: layout.prop(self, "slider_i02")
        if "i3" in formula: layout.prop(self, "slider_i03")
        if "i4" in formula: layout.prop(self, "slider_i04")
        if "i5" in formula: layout.prop(self, "slider_i05")

        layout.label(text="Variables (for each vertex):")
        layout.label(text="lx, ly, lz: Local Coordinates", icon='ORIENTATION_LOCAL')
        layout.label(text="gx, gy, gz: Global Coordinates", icon='WORLD')
        layout.label(text="rx, ry, rz: Local Coordinates (0 to 1)", icon='NORMALIZE_FCURVES')
        layout.label(text="nx, ny, nz: Normal Coordinates", icon='SNAP_NORMAL')
        layout.label(text="w[0], w[1], w[2], ... : Vertex Groups", icon="GROUP_VERTEX")
        layout.separator()
        layout.label(text="f1, f2, f3, f4, f5: Float Sliders", icon='MOD_HUE_SATURATION')#PROPERTIES
        layout.label(text="i1, i2, i3, i4, i5: Integer Sliders", icon='MOD_HUE_SATURATION')
        layout.separator()
        #layout.label(text="All mathematical functions are based on Numpy", icon='INFO')
        #layout.label(text="https://docs.scipy.org/doc/numpy-1.13.0/reference/routines.math.html", icon='INFO')
        layout.operator("scene.weight_formula_wiki", icon="HELP")
        #layout.label(text="(where 'i' is the index of the Vertex Group)")

    def execute(self, context):
        ob = context.active_object
        n_verts = len(ob.data.vertices)
        #if self.examples == 'CUSTOM':
        #    formula = self.formula
        #else:
        #self.formula = self.examples
        #    formula = self.examples

        #f1, f2, f3, f4, f5 = self.slider_f01, self.slider_f02, self.slider_f03, self.slider_f04, self.slider_f05
        #i1, i2, i3, i4, i5 = self.slider_i01, self.slider_i02, self.slider_i03, self.slider_i04, self.slider_i05
        f_sliders = self.slider_f01, self.slider_f02, self.slider_f03, self.slider_f04, self.slider_f05
        i_sliders = self.slider_i01, self.slider_i02, self.slider_i03, self.slider_i04, self.slider_i05

        if self.examples != 'CUSTOM':
            example = self.ex_items[int(self.examples)][0]
            if example != self.old_ex:
                self.formula = example
                self.old_ex = example
            elif self.formula != example:
                self.examples = 'CUSTOM'
        formula = self.formula

        if formula == "": return {'FINISHED'}
        # replace numeric sliders value
        for i, slider in enumerate(f_sliders):
            formula = formula.replace('f'+str(i+1),"{0:.2f}".format(slider))
        for i, slider in enumerate(i_sliders):
            formula =formula.replace('i'+str(i+1),str(slider))
        vertex_group_name = "" + formula
        ob.vertex_groups.new(name=vertex_group_name)

        weight = compute_formula(ob, formula=formula, float_var=f_sliders, int_var=i_sliders)
        if type(weight) == str:
            self.report({'ERROR'}, weight)
            return {'CANCELLED'}

        #start_time = timeit.default_timer()
        weight = nan_to_num(weight)
        vg = ob.vertex_groups[-1]
        if type(weight) == int or type(weight) == float:
            for i in range(n_verts):
                vg.add([i], weight, 'REPLACE')
        elif type(weight) == ndarray:
            for i in range(n_verts):
                vg.add([i], weight[i], 'REPLACE')
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

        # Store formula settings
        new_formula = ob.formula_settings.add()
        new_formula.name = ob.vertex_groups[-1].name
        new_formula.formula = formula
        new_formula.int_var = i_sliders
        new_formula.float_var = f_sliders

        #for f in ob.formula_settings:
        #    print(f.name, f.formula, f.int_var, f.float_var)
        return {'FINISHED'}


class update_weight_formula(Operator):
    bl_idname = "object.update_weight_formula"
    bl_label = "Update Weight Formula"
    bl_description = "Update an existing Vertex Group. Make sure that the name\nof the active Vertex Group is a valid formula"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        ob = context.active_object
        n_verts = len(ob.data.vertices)

        vg = ob.vertex_groups.active
        formula = vg.name
        weight = compute_formula(ob, formula=formula)
        if type(weight) == str:
            self.report({'ERROR'}, "The name of the active Vertex Group\nis not a valid Formula")
            return {'CANCELLED'}

        #start_time = timeit.default_timer()
        weight = nan_to_num(weight)
        if type(weight) == int or type(weight) == float:
            for i in range(n_verts):
                vg.add([i], weight, 'REPLACE')
        elif type(weight) == ndarray:
            for i in range(n_verts):
                vg.add([i], weight[i], 'REPLACE')
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}


class _weight_laplacian(Operator):
    bl_idname = "object._weight_laplacian"
    bl_label = "Weight Laplacian"
    bl_description = ("Compute the Vertex Group Laplacian")
    bl_options = {'REGISTER', 'UNDO'}

    bounds : EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('POSITIVE', "Positive Only", ""),
            ('NEGATIVE', "Negative Only", ""),
            ('AUTOMATIC', "Automatic Bounds", "")),
        default='AUTOMATIC', name="Bounds")

    mode : EnumProperty(
        items=(('LENGTH', "Length Weight", ""),
            ('SIMPLE', "Simple", "")),
        default='SIMPLE', name="Evaluation Mode")

    min_def : FloatProperty(
        name="Min", default=0, soft_min=-1, soft_max=0,
        description="Laplacian value with 0 weight")

    max_def : FloatProperty(
        name="Max", default=0.5, soft_min=0, soft_max=5,
        description="Laplacian value with 1 weight")

    bounds_string = ""

    frame = None

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Evaluation Mode")
        col.prop(self, "mode", text="")
        col.label(text="Bounds")
        col.prop(self, "bounds", text="")
        if self.bounds == 'MANUAL':
            col.label(text="Strain Rate \u03B5:")
            col.prop(self, "min_def")
            col.prop(self, "max_def")
        col.label(text="\u03B5" + ": from " + self.bounds_string)


    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}

        group_id = ob.vertex_groups.active_index
        input_group = ob.vertex_groups[group_id].name

        group_name = "Laplacian"
        ob.vertex_groups.new(name=group_name)
        me = ob.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.edges.ensure_lookup_table()

        # store weight values
        weight = []
        for v in me.vertices:
            try:
                weight.append(ob.vertex_groups[input_group].weight(v.index))
            except:
                weight.append(0)

        n_verts = len(bm.verts)
        lap = [0]*n_verts
        for e in bm.edges:
            if self.mode == 'LENGTH':
                length = e.calc_length()
                if length == 0: continue
                id0 = e.verts[0].index
                id1 = e.verts[1].index
                lap[id0] += weight[id1]/length - weight[id0]/length
                lap[id1] += weight[id0]/length - weight[id1]/length
            else:
                id0 = e.verts[0].index
                id1 = e.verts[1].index
                lap[id0] += weight[id1] - weight[id0]
                lap[id1] += weight[id0] - weight[id1]

        mean_lap = mean(lap)
        stdev_lap = stdev(lap)
        filter_lap = [i for i in lap if mean_lap-2*stdev_lap < i < mean_lap+2*stdev_lap]
        if self.bounds == 'MANUAL':
            min_def = self.min_def
            max_def = self.max_def
        elif self.bounds == 'AUTOMATIC':
            min_def = min(filter_lap)
            max_def = max(filter_lap)
            self.min_def = min_def
            self.max_def = max_def
        elif self.bounds == 'NEGATIVE':
            min_def = 0
            max_def = min(filter_lap)
            self.min_def = min_def
            self.max_def = max_def
        elif self.bounds == 'POSITIVE':
            min_def = 0
            max_def = max(filter_lap)
            self.min_def = min_def
            self.max_def = max_def
        delta_def = max_def - min_def

        # check undeformed errors
        if delta_def == 0: delta_def = 0.0001

        for i in range(len(lap)):
            val = (lap[i]-min_def)/delta_def
            #if val > 0.7: print(str(val) + " " + str(lap[i]))
            #val = weight[i] + 0.2*lap[i]
            ob.vertex_groups[-1].add([i], val, 'REPLACE')
        self.bounds_string = str(round(min_def,2)) + " to " + str(round(max_def,2))
        ob.vertex_groups[-1].name = group_name + " " + self.bounds_string
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        bm.free()
        return {'FINISHED'}

class ok_weight_laplacian(Operator):
    bl_idname = "object.weight_laplacian"
    bl_label = "Weight Laplacian"
    bl_description = ("Compute the Vertex Group Laplacian")
    bl_options = {'REGISTER', 'UNDO'}

    bounds_string = ""

    frame = None

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0


    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}

        me = ob.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.edges.ensure_lookup_table()

        group_id = ob.vertex_groups.active_index
        input_group = ob.vertex_groups[group_id].name

        group_name = "Laplacian"
        ob.vertex_groups.new(name=group_name)

        # store weight values
        a = []
        for v in me.vertices:
            try:
                a.append(ob.vertex_groups[input_group].weight(v.index))
            except:
                a.append(0)

        a = array(a)


        # initialize
        n_verts = len(bm.verts)
        # find max number of edges for vertex
        max_edges = 0
        n_neighbors = []
        id_neighbors = []
        for v in bm.verts:
            n_edges = len(v.link_edges)
            max_edges = max(max_edges, n_edges)
            n_neighbors.append(n_edges)
            neighbors = []
            for e in v.link_edges:
                for v1 in e.verts:
                    if v != v1: neighbors.append(v1.index)
            id_neighbors.append(neighbors)
        n_neighbors = array(n_neighbors)


        lap_map = [[] for i in range(n_verts)]
        #lap_map = []
        '''
        for e in bm.edges:
            id0 = e.verts[0].index
            id1 = e.verts[1].index
            lap_map[id0].append(id1)
            lap_map[id1].append(id0)
        '''
        lap = zeros((n_verts))#[0]*n_verts
        n_records = zeros((n_verts))
        for e in bm.edges:
            id0 = e.verts[0].index
            id1 = e.verts[1].index
            length = e.calc_length()
            if length == 0: continue
            #lap[id0] += abs(a[id1] - a[id0])/length
            #lap[id1] += abs(a[id0] - a[id1])/length
            lap[id0] += (a[id1] - a[id0])/length
            lap[id1] += (a[id0] - a[id1])/length
            n_records[id0]+=1
            n_records[id1]+=1
        lap /= n_records
        lap /= max(lap)

        for i in range(n_verts):
            ob.vertex_groups['Laplacian'].add([i], lap[i], 'REPLACE')
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        bm.free()
        return {'FINISHED'}

class weight_laplacian(Operator):
    bl_idname = "object.weight_laplacian"
    bl_label = "Weight Laplacian"
    bl_description = ("Compute the Vertex Group Laplacian")
    bl_options = {'REGISTER', 'UNDO'}

    bounds_string = ""

    frame = None

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0


    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}

        me = ob.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.edges.ensure_lookup_table()
        n_verts = len(me.vertices)

        group_id = ob.vertex_groups.active_index
        input_group = ob.vertex_groups[group_id].name

        group_name = "Laplacian"
        vg = ob.vertex_groups.new(name=group_name)

        # store weight values
        dvert_lay = bm.verts.layers.deform.active
        weight = bmesh_get_weight_numpy(group_id, dvert_lay, bm.verts)

        #verts, normals = get_vertices_and_normals_numpy(me)

        #lap = zeros((n_verts))#[0]*n_verts
        lap = [Vector((0,0,0)) for i in range(n_verts)]
        n_records = zeros((n_verts))
        for e in bm.edges:
            vert0 = e.verts[0]
            vert1 = e.verts[1]
            id0 = vert0.index
            id1 = vert1.index
            v0 = vert0.co
            v1 = vert1.co
            v01 = v1-v0
            v10 = -v01
            v01 -= v01.project(vert0.normal)
            v10 -= v10.project(vert1.normal)
            length = e.calc_length()
            if length == 0: continue
            dw = (weight[id1] - weight[id0])/length
            lap[id0] += v01.normalized() * dw
            lap[id1] -= v10.normalized() * dw
            n_records[id0]+=1
            n_records[id1]+=1
        #lap /= n_records[:,np.newaxis]
        lap = [l.length/r for r,l in zip(n_records,lap)]

        lap = np.array(lap)
        lap /= np.max(lap)
        lap = list(lap)

        for i in range(n_verts):
            vg.add([i], lap[i], 'REPLACE')
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        bm.free()
        return {'FINISHED'}

class edges_deformation(Operator):
    bl_idname = "object.edges_deformation"
    bl_label = "Edges Deformation"
    bl_description = ("Compute Weight based on the deformation of edges"+
        "according to visible modifiers.")
    bl_options = {'REGISTER', 'UNDO'}

    bounds : EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('COMPRESSION', "Compressed Only", ""),
            ('TENSION', "Extended Only", ""),
            ('AUTOMATIC', "Automatic Bounds", "")),
        default='AUTOMATIC', name="Bounds")

    mode : EnumProperty(
        items=(('MAX', "Max Deformation", ""),
            ('MEAN', "Average Deformation", "")),
        default='MEAN', name="Evaluation Mode")

    min_def : FloatProperty(
        name="Min", default=0, soft_min=-1, soft_max=0,
        description="Deformations with 0 weight")

    max_def : FloatProperty(
        name="Max", default=0.5, soft_min=0, soft_max=5,
        description="Deformations with 1 weight")

    bounds_string = ""

    frame = None

    @classmethod
    def poll(cls, context):
        return len(context.object.modifiers) > 0

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Evaluation Mode")
        col.prop(self, "mode", text="")
        col.label(text="Bounds")
        col.prop(self, "bounds", text="")
        if self.bounds == 'MANUAL':
            col.label(text="Strain Rate \u03B5:")
            col.prop(self, "min_def")
            col.prop(self, "max_def")
        col.label(text="\u03B5" + ": from " + self.bounds_string)

    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}

        # check if the object is Cloth or Softbody
        physics = False
        for m in ob.modifiers:
            if m.type == 'CLOTH' or m.type == 'SOFT_BODY':
                physics = True
                if context.scene.frame_current == 1 and self.frame != None:
                    context.scene.frame_current = self.frame
                break
        if not physics: self.frame = None

        if self.mode == 'MEAN': group_name = "Average Deformation"
        elif self.mode == 'MAX': group_name = "Max Deformation"
        ob.vertex_groups.new(name=group_name)
        me0 = ob.data

        me = simple_to_mesh(ob) #ob.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get()).copy()
        if len(me.vertices) != len(me0.vertices) or len(me.edges) != len(me0.edges):
            self.report({'ERROR'}, "The topology of the object should be" +
                "unaltered")
            return {'CANCELLED'}

        bm0 = bmesh.new()
        bm0.from_mesh(me0)
        bm = bmesh.new()
        bm.from_mesh(me)
        deformations = []
        for e0, e in zip(bm0.edges, bm.edges):
            try:
                l0 = e0.calc_length()
                l1 = e.calc_length()
                epsilon = (l1 - l0)/l0
                deformations.append(epsilon)
            except: deformations.append(1)
        v_deformations = []
        for v in bm.verts:
            vdef = []
            for e in v.link_edges:
                vdef.append(deformations[e.index])
            if self.mode == 'MEAN': v_deformations.append(mean(vdef))
            elif self.mode == 'MAX': v_deformations.append(max(vdef, key=abs))
            #elif self.mode == 'MIN': v_deformations.append(min(vdef, key=abs))

        if self.bounds == 'MANUAL':
            min_def = self.min_def
            max_def = self.max_def
        elif self.bounds == 'AUTOMATIC':
            min_def = min(v_deformations)
            max_def = max(v_deformations)
            self.min_def = min_def
            self.max_def = max_def
        elif self.bounds == 'COMPRESSION':
            min_def = 0
            max_def = min(v_deformations)
            self.min_def = min_def
            self.max_def = max_def
        elif self.bounds == 'TENSION':
            min_def = 0
            max_def = max(v_deformations)
            self.min_def = min_def
            self.max_def = max_def
        delta_def = max_def - min_def

        # check undeformed errors
        if delta_def == 0:
            if self.bounds == 'MANUAL':
                delta_def = 0.0001
            else:
                message = "The object doesn't have deformations."
                if physics:
                    message = message + ("\nIf you are using Physics try to " +
                        "save it in the cache before.")
                self.report({'ERROR'}, message)
                return {'CANCELLED'}
        else:
            if physics:
                self.frame = context.scene.frame_current

        for i in range(len(v_deformations)):
            weight = (v_deformations[i] - min_def)/delta_def
            ob.vertex_groups[-1].add([i], weight, 'REPLACE')
        self.bounds_string = str(round(min_def,2)) + " to " + str(round(max_def,2))
        ob.vertex_groups[-1].name = group_name + " " + self.bounds_string
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        bpy.data.meshes.remove(me)
        bm.free()
        bm0.free()
        return {'FINISHED'}

class edges_bending(Operator):
    bl_idname = "object.edges_bending"
    bl_label = "Edges Bending"
    bl_description = ("Compute Weight based on the bending of edges"+
        "according to visible modifiers.")
    bl_options = {'REGISTER', 'UNDO'}

    bounds : EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('POSITIVE', "Positive Only", ""),
            ('NEGATIVE', "Negative Only", ""),
            ('UNSIGNED', "Absolute Bending", ""),
            ('AUTOMATIC', "Signed Bending", "")),
        default='AUTOMATIC', name="Bounds")

    min_def : FloatProperty(
        name="Min", default=-10, soft_min=-45, soft_max=45,
        description="Deformations with 0 weight")

    max_def : FloatProperty(
        name="Max", default=10, soft_min=-45, soft_max=45,
        description="Deformations with 1 weight")

    bounds_string = ""
    frame = None

    @classmethod
    def poll(cls, context):
        return len(context.object.modifiers) > 0

    def draw(self, context):
        layout = self.layout
        layout.label(text="Bounds")
        layout.prop(self, "bounds", text="")
        if self.bounds == 'MANUAL':
            layout.prop(self, "min_def")
            layout.prop(self, "max_def")

    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}

        group_name = "Edges Bending"
        ob.vertex_groups.new(name=group_name)

        # check if the object is Cloth or Softbody
        physics = False
        for m in ob.modifiers:
            if m.type == 'CLOTH' or m.type == 'SOFT_BODY':
                physics = True
                if context.scene.frame_current == 1 and self.frame != None:
                    context.scene.frame_current = self.frame
                break
        if not physics: self.frame = None

        #ob.data.update()
        #context.scene.update()
        me0 = ob.data
        me = simple_to_mesh(ob) #ob.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get()).copy()
        if len(me.vertices) != len(me0.vertices) or len(me.edges) != len(me0.edges):
            self.report({'ERROR'}, "The topology of the object should be" +
                "unaltered")
        bm0 = bmesh.new()
        bm0.from_mesh(me0)
        bm = bmesh.new()
        bm.from_mesh(me)
        deformations = []
        for e0, e in zip(bm0.edges, bm.edges):
            try:
                ang = e.calc_face_angle_signed()
                ang0 = e0.calc_face_angle_signed()
                if self.bounds == 'UNSIGNED':
                    deformations.append(abs(ang-ang0))
                else:
                    deformations.append(ang-ang0)
            except: deformations.append(0)
        v_deformations = []
        for v in bm.verts:
            vdef = []
            for e in v.link_edges:
                vdef.append(deformations[e.index])
            v_deformations.append(mean(vdef))
        if self.bounds == 'MANUAL':
            min_def = radians(self.min_def)
            max_def = radians(self.max_def)
        elif self.bounds == 'AUTOMATIC':
            min_def = min(v_deformations)
            max_def = max(v_deformations)
        elif self.bounds == 'POSITIVE':
            min_def = 0
            max_def = min(v_deformations)
        elif self.bounds == 'NEGATIVE':
            min_def = 0
            max_def = max(v_deformations)
        elif self.bounds == 'UNSIGNED':
            min_def = 0
            max_def = max(v_deformations)
        delta_def = max_def - min_def

        # check undeformed errors
        if delta_def == 0:
            if self.bounds == 'MANUAL':
                delta_def = 0.0001
            else:
                message = "The object doesn't have deformations."
                if physics:
                    message = message + ("\nIf you are using Physics try to " +
                        "save it in the cache before.")
                self.report({'ERROR'}, message)
                return {'CANCELLED'}
        else:
            if physics:
                self.frame = context.scene.frame_current

        for i in range(len(v_deformations)):
            weight = (v_deformations[i] - min_def)/delta_def
            ob.vertex_groups[-1].add([i], weight, 'REPLACE')
        self.bounds_string = str(round(min_def,2)) + " to " + str(round(max_def,2))
        ob.vertex_groups[-1].name = group_name + " " + self.bounds_string
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        bpy.data.meshes.remove(me)
        bm0.free()
        bm.free()
        return {'FINISHED'}

class weight_contour_displace(Operator):
    bl_idname = "object.weight_contour_displace"
    bl_label = "Contour Displace"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")
    min_iso : FloatProperty(
        name="Min Iso Value", default=0.49, min=0, max=1,
        description="Threshold value")
    max_iso : FloatProperty(
        name="Max Iso Value", default=0.51, min=0, max=1,
        description="Threshold value")
    n_cuts : IntProperty(
        name="Cuts", default=2, min=1, soft_max=10,
        description="Number of cuts in the selected range of values")
    bool_displace : BoolProperty(
        name="Add Displace", default=True, description="Add Displace Modifier")
    bool_flip : BoolProperty(
        name="Flip", default=False, description="Flip Output Weight")

    weight_mode : EnumProperty(
        items=[('Remapped', 'Remapped', 'Remap values'),
               ('Alternate', 'Alternate', 'Alternate 0 and 1'),
               ('Original', 'Original', 'Keep original Vertex Group')],
        name="Weight", description="Choose how to convert vertex group",
        default="Remapped", options={'LIBRARY_EDITABLE'})

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}

        ob0 = context.object

        group_id = ob0.vertex_groups.active_index
        vertex_group_name = ob0.vertex_groups[group_id].name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        if self.use_modifiers:
            #me0 = ob0.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get()).copy()
            me0 = simple_to_mesh(ob0)
        else:
            me0 = ob0.data.copy()

        # generate new bmesh
        bm = bmesh.new()
        bm.from_mesh(me0)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # store weight values
        weight = []
        ob = bpy.data.objects.new("temp", me0)
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)
        for v in me0.vertices:
            try:
                weight.append(ob.vertex_groups[vertex_group_name].weight(v.index))
            except:
                weight.append(0)

        # define iso values
        iso_values = []
        for i_cut in range(self.n_cuts):
            delta_iso = abs(self.max_iso - self.min_iso)
            min_iso = min(self.min_iso, self.max_iso)
            max_iso = max(self.min_iso, self.max_iso)
            if delta_iso == 0: iso_val = min_iso
            elif self.n_cuts > 1: iso_val = i_cut/(self.n_cuts-1)*delta_iso + min_iso
            else: iso_val = (self.max_iso + self.min_iso)/2
            iso_values.append(iso_val)

        # Start Cuts Iterations
        filtered_edges = bm.edges
        for iso_val in iso_values:
            delete_edges = []

            faces_mask = []
            for f in bm.faces:
                w_min = 2
                w_max = 2
                for v in f.verts:
                    w = weight[v.index]
                    if w_min == 2:
                        w_max = w_min = w
                    if w > w_max: w_max = w
                    if w < w_min: w_min = w
                    if w_min < iso_val and w_max > iso_val:
                        faces_mask.append(f)
                        break

            #link_faces = [[f for f in e.link_faces] for e in bm.edges]

            #faces_todo = [f.select for f in bm.faces]
            #faces_todo = [True for f in bm.faces]
            verts = []
            edges = []
            edges_id = {}
            _filtered_edges = []
            n_verts = len(bm.verts)
            count = n_verts
            for e in filtered_edges:
                #id0 = e.vertices[0]
                #id1 = e.vertices[1]
                id0 = e.verts[0].index
                id1 = e.verts[1].index
                w0 = weight[id0]
                w1 = weight[id1]

                if w0 == w1: continue
                elif w0 > iso_val and w1 > iso_val:
                    _filtered_edges.append(e)
                    continue
                elif w0 < iso_val and w1 < iso_val: continue
                elif w0 == iso_val or w1 == iso_val:
                    _filtered_edges.append(e)
                    continue
                else:
                    v0 = bm.verts[id0].co
                    v1 = bm.verts[id1].co
                    v = v0.lerp(v1, (iso_val-w0)/(w1-w0))
                    if e not in delete_edges:
                        delete_edges.append(e)
                    verts.append(v)
                    edges_id[str(id0)+"_"+str(id1)] = count
                    edges_id[str(id1)+"_"+str(id0)] = count
                    count += 1
                    _filtered_edges.append(e)
            filtered_edges = _filtered_edges
            splitted_faces = []

            switch = False
            # splitting faces
            for f in faces_mask:
                # create sub-faces slots. Once a new vertex is reached it will
                # change slot, storing the next vertices for a new face.
                build_faces = [[],[]]
                #switch = False
                verts0 = [v.index for v in f.verts]
                verts1 = list(verts0)
                verts1.append(verts1.pop(0)) # shift list
                for id0, id1 in zip(verts0, verts1):

                    # add first vertex to active slot
                    build_faces[switch].append(id0)

                    # try to split edge
                    try:
                        # check if the edge must be splitted
                        new_vert = edges_id[str(id0)+"_"+str(id1)]
                        # add new vertex
                        build_faces[switch].append(new_vert)
                        # if there is an open face on the other slot
                        if len(build_faces[not switch]) > 0:
                            # store actual face
                            splitted_faces.append(build_faces[switch])
                            # reset actual faces and switch
                            build_faces[switch] = []
                            # change face slot
                        switch = not switch
                        # continue previous face
                        build_faces[switch].append(new_vert)
                    except: pass
                if len(build_faces[not switch]) == 2:
                    build_faces[not switch].append(id0)
                if len(build_faces[not switch]) > 2:
                    splitted_faces.append(build_faces[not switch])
                # add last face
                splitted_faces.append(build_faces[switch])
                #del_faces.append(f.index)

            # adding new vertices
            _new_vert = bm.verts.new
            for v in verts: new_vert = _new_vert(v)
            bm.verts.index_update()
            bm.verts.ensure_lookup_table()
            # adding new faces
            _new_face = bm.faces.new
            missed_faces = []
            added_faces = []
            for f in splitted_faces:
                try:
                    face_verts = [bm.verts[i] for i in f]
                    new_face = _new_face(face_verts)
                    for e in new_face.edges:
                        filtered_edges.append(e)
                except:
                    missed_faces.append(f)

            bm.faces.ensure_lookup_table()
            # updating weight values
            weight = weight + [iso_val]*len(verts)

            # deleting old edges/faces
            _remove_edge = bm.edges.remove
            bm.edges.ensure_lookup_table()
            for e in delete_edges:
                _remove_edge(e)
            _filtered_edges = []
            for e in filtered_edges:
                if e not in delete_edges: _filtered_edges.append(e)
            filtered_edges = _filtered_edges

        name = ob0.name + '_ContourDisp'
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)

        # Link object to scene and make active
        scn = context.scene
        context.collection.objects.link(ob)
        context.view_layer.objects.active = ob
        ob.select_set(True)
        ob0.select_set(False)

        # generate new vertex group
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)
        #ob.vertex_groups.new(name=vertex_group_name)

        all_weight = weight + [iso_val]*len(verts)
        #mult = 1/(1-iso_val)
        for id in range(len(all_weight)):
            #if False: w = (all_weight[id]-iso_val)*mult
            w = all_weight[id]
            if self.weight_mode == 'Alternate':
                direction = self.bool_flip
                for i in range(len(iso_values)-1):
                    val0, val1 = iso_values[i], iso_values[i+1]
                    if val0 < w <= val1:
                        if direction: w1 = (w-val0)/(val1-val0)
                        else: w1 = (val1-w)/(val1-val0)
                    direction = not direction
                if w < iso_values[0]: w1 = not self.bool_flip
                if w > iso_values[-1]: w1 = not direction
            elif self.weight_mode == 'Remapped':
                if w < min_iso: w1 = 0
                elif w > max_iso: w1 = 1
                else: w1 = (w - min_iso)/delta_iso
            else:
                if self.bool_flip: w1 = 1-w
                else: w1 = w
            ob.vertex_groups[vertex_group_name].add([id], w1, 'REPLACE')

        ob.vertex_groups.active_index = group_id

        # align new object
        ob.matrix_world = ob0.matrix_world

        # Displace Modifier
        if self.bool_displace:
            ob.modifiers.new(type='DISPLACE', name='Displace')
            ob.modifiers["Displace"].mid_level = 0
            ob.modifiers["Displace"].strength = 0.1
            ob.modifiers['Displace'].vertex_group = vertex_group_name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        print("Contour Displace time: " + str(timeit.default_timer() - start_time) + " sec")

        bpy.data.meshes.remove(me0)

        return {'FINISHED'}

class weight_contour_mask(Operator):
    bl_idname = "object.weight_contour_mask"
    bl_label = "Contour Mask"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")
    iso : FloatProperty(
        name="Iso Value", default=0.5, soft_min=0, soft_max=1,
        description="Threshold value")
    bool_solidify : BoolProperty(
        name="Solidify", default=True, description="Add Solidify Modifier")
    offset : FloatProperty(
        name="Offset", default=1, min=0, max=1,
        description="Offset")
    thickness : FloatProperty(
        name="Thickness", default=0.5, soft_min=0, soft_max=1,
        description="Thickness")
    normalize_weight : BoolProperty(
        name="Normalize Weight", default=True,
        description="Normalize weight of remaining vertices")

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}

        ob0 = bpy.context.object

        iso_val = self.iso
        group_id = ob0.vertex_groups.active_index
        vertex_group_name = ob0.vertex_groups[group_id].name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        if self.use_modifiers:
            me0 = simple_to_mesh(ob0)#ob0.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get()).copy()
        else:
            me0 = ob0.data.copy()

        # generate new bmesh
        bm = bmesh.new()
        bm.from_mesh(me0)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # store weight values
        weight = []
        ob = bpy.data.objects.new("temp", me0)
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)
        for v in me0.vertices:
            try:
                #weight.append(v.groups[vertex_group_name].weight)
                weight.append(ob.vertex_groups[vertex_group_name].weight(v.index))
            except:
                weight.append(0)

        faces_mask = []
        for f in bm.faces:
            w_min = 2
            w_max = 2
            for v in f.verts:
                w = weight[v.index]
                if w_min == 2:
                    w_max = w_min = w
                if w > w_max: w_max = w
                if w < w_min: w_min = w
                if w_min < iso_val and w_max > iso_val:
                    faces_mask.append(f)
                    break

        filtered_edges = bm.edges# me0.edges
        faces_todo = [f.select for f in bm.faces]
        verts = []
        edges = []
        delete_edges = []
        edges_id = {}
        _filtered_edges = []
        n_verts = len(bm.verts)
        count = n_verts
        for e in filtered_edges:
            id0 = e.verts[0].index
            id1 = e.verts[1].index
            w0 = weight[id0]
            w1 = weight[id1]

            if w0 == w1: continue
            elif w0 > iso_val and w1 > iso_val:
                continue
            elif w0 < iso_val and w1 < iso_val: continue
            elif w0 == iso_val or w1 == iso_val: continue
            else:
                v0 = me0.vertices[id0].co
                v1 = me0.vertices[id1].co
                v = v0.lerp(v1, (iso_val-w0)/(w1-w0))
                delete_edges.append(e)
                verts.append(v)
                edges_id[str(id0)+"_"+str(id1)] = count
                edges_id[str(id1)+"_"+str(id0)] = count
                count += 1

        splitted_faces = []

        switch = False
        # splitting faces
        for f in faces_mask:
            # create sub-faces slots. Once a new vertex is reached it will
            # change slot, storing the next vertices for a new face.
            build_faces = [[],[]]
            #switch = False
            verts0 = list(me0.polygons[f.index].vertices)
            verts1 = list(verts0)
            verts1.append(verts1.pop(0)) # shift list
            for id0, id1 in zip(verts0, verts1):

                # add first vertex to active slot
                build_faces[switch].append(id0)

                # try to split edge
                try:
                    # check if the edge must be splitted
                    new_vert = edges_id[str(id0)+"_"+str(id1)]
                    # add new vertex
                    build_faces[switch].append(new_vert)
                    # if there is an open face on the other slot
                    if len(build_faces[not switch]) > 0:
                        # store actual face
                        splitted_faces.append(build_faces[switch])
                        # reset actual faces and switch
                        build_faces[switch] = []
                        # change face slot
                    switch = not switch
                    # continue previous face
                    build_faces[switch].append(new_vert)
                except: pass
            if len(build_faces[not switch]) == 2:
                build_faces[not switch].append(id0)
            if len(build_faces[not switch]) > 2:
                splitted_faces.append(build_faces[not switch])
            # add last face
            splitted_faces.append(build_faces[switch])

        # adding new vertices
        _new_vert = bm.verts.new
        for v in verts: _new_vert(v)
        bm.verts.ensure_lookup_table()

        # deleting old edges/faces
        _remove_edge = bm.edges.remove
        bm.edges.ensure_lookup_table()
        remove_edges = []
        for e in delete_edges: _remove_edge(e)

        bm.verts.ensure_lookup_table()
        # adding new faces
        _new_face = bm.faces.new
        missed_faces = []
        for f in splitted_faces:
            try:
                face_verts = [bm.verts[i] for i in f]
                _new_face(face_verts)
            except:
                missed_faces.append(f)

        # Mask geometry
        if(True):
            _remove_vert = bm.verts.remove
            all_weight = weight + [iso_val+0.0001]*len(verts)
            weight = []
            for w, v in zip(all_weight, bm.verts):
                if w < iso_val: _remove_vert(v)
                else: weight.append(w)

        # Create mesh and object
        name = ob0.name + '_ContourMask_{:.3f}'.format(iso_val)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)

        # Link object to scene and make active
        scn = context.scene
        context.collection.objects.link(ob)
        context.view_layer.objects.active = ob
        ob.select_set(True)
        ob0.select_set(False)

        # generate new vertex group
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)

        if iso_val != 1: mult = 1/(1-iso_val)
        else: mult = 1
        for id in range(len(weight)):
            if self.normalize_weight: w = (weight[id]-iso_val)*mult
            else: w = weight[id]
            ob.vertex_groups[vertex_group_name].add([id], w, 'REPLACE')
        ob.vertex_groups.active_index = group_id

        # align new object
        ob.matrix_world = ob0.matrix_world

        # Add Solidify
        if self.bool_solidify and True:
            ob.modifiers.new(type='SOLIDIFY', name='Solidify')
            ob.modifiers['Solidify'].thickness = self.thickness
            ob.modifiers['Solidify'].offset = self.offset
            ob.modifiers['Solidify'].vertex_group = vertex_group_name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        print("Contour Mask time: " + str(timeit.default_timer() - start_time) + " sec")

        bpy.data.meshes.remove(me0)

        return {'FINISHED'}


class weight_contour_mask_wip(Operator):
    bl_idname = "object.weight_contour_mask"
    bl_label = "Contour Mask"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")
    iso : FloatProperty(
        name="Iso Value", default=0.5, soft_min=0, soft_max=1,
        description="Threshold value")
    bool_solidify : BoolProperty(
        name="Solidify", default=True, description="Add Solidify Modifier")
    normalize_weight : BoolProperty(
        name="Normalize Weight", default=True,
        description="Normalize weight of remaining vertices")

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}

        ob0 = bpy.context.object

        iso_val = self.iso
        group_id = ob0.vertex_groups.active_index
        vertex_group_name = ob0.vertex_groups[group_id].name

        if self.use_modifiers:
            me0 = simple_to_mesh(ob0)
        else:
            me0 = ob0.data.copy()

        # generate new bmesh
        bm = bmesh.new()
        bm.from_mesh(me0)

        # store weight values
        weight = []
        ob = bpy.data.objects.new("temp", me0)
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)
        weight = get_weight_numpy(ob.vertex_groups[vertex_group_name], len(me0.vertices))

        me0, bm, weight = contour_bmesh(me0, bm, weight, iso_val)

        # Mask geometry
        mask = weight >= iso_val
        weight = weight[mask]
        mask = np.logical_not(mask)
        delete_verts = np.array(bm.verts)[mask]

        # Create mesh and object
        name = ob0.name + '_ContourMask_{:.3f}'.format(iso_val)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)

        # Link object to scene and make active
        scn = context.scene
        context.collection.objects.link(ob)
        context.view_layer.objects.active = ob
        ob.select_set(True)
        ob0.select_set(False)

        # generate new vertex group
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)

        if iso_val != 1: mult = 1/(1-iso_val)
        else: mult = 1
        for id in range(len(weight)):
            if self.normalize_weight: w = (weight[id]-iso_val)*mult
            else: w = weight[id]
            ob.vertex_groups[vertex_group_name].add([id], w, 'REPLACE')
        ob.vertex_groups.active_index = group_id

        # align new object
        ob.matrix_world = ob0.matrix_world

        # Add Solidify
        if self.bool_solidify and True:
            ob.modifiers.new(type='SOLIDIFY', name='Solidify')
            ob.modifiers['Solidify'].thickness = 0.05
            ob.modifiers['Solidify'].offset = 0
            ob.modifiers['Solidify'].vertex_group = vertex_group_name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        print("Contour Mask time: " + str(timeit.default_timer() - start_time) + " sec")

        bpy.data.meshes.remove(me0)

        return {'FINISHED'}

class vertex_colors_to_vertex_groups(Operator):
    bl_idname = "object.vertex_colors_to_vertex_groups"
    bl_label = "Vertex Color"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Convert the active Vertex Color into a Vertex Group.")

    red : BoolProperty(
        name="red channel", default=False, description="convert red channel")
    green : BoolProperty(
        name="green channel", default=False,
        description="convert green channel")
    blue : BoolProperty(
        name="blue channel", default=False, description="convert blue channel")
    value : BoolProperty(
        name="value channel", default=True, description="convert value channel")
    invert : BoolProperty(
         name="invert", default=False, description="invert all color channels")

    @classmethod
    def poll(cls, context):
        try:
            return len(context.object.data.color_attributes) > 0
        except: return False

    def execute(self, context):
        ob = context.active_object
        id = len(ob.vertex_groups)
        id_red = id
        id_green = id
        id_blue = id
        id_value = id

        boolCol = len(ob.data.color_attributes)
        if(boolCol):
            col = ob.data.color_attributes.active_color
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        if(self.red and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_red = id
            ob.vertex_groups[id_red].name = col.name + '_red'
            id+=1
        if(self.green and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_green = id
            ob.vertex_groups[id_green].name = col.name + '_green'
            id+=1
        if(self.blue and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_blue = id
            ob.vertex_groups[id_blue].name = col.name + '_blue'
            id+=1
        if(self.value and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_value = id
            ob.vertex_groups[id_value].name = col.name + '_value'
            id+=1

        mult = 1
        if(self.invert): mult = -1
        bpy.ops.object.mode_set(mode='OBJECT')
        sub_red = 1 + self.value + self.blue + self.green
        sub_green = 1 + self.value + self.blue
        sub_blue = 1 + self.value
        sub_value = 1

        id = len(ob.vertex_groups)
        if(id_red <= id and id_green <= id and id_blue <= id and id_value <= \
                id and boolCol):
            v_colors = ob.data.color_attributes.active_color.data

            i = 0
            if ob.data.color_attributes.active_color.domain == 'POINT':
                for v in ob.data.vertices:
                    gr = v.groups
                    if(self.red): gr[min(len(gr)-sub_red, id_red)].weight = \
                        self.invert + mult * v_colors[i].color[0]
                    if(self.green): gr[min(len(gr)-sub_green, id_green)].weight\
                        = self.invert + mult * v_colors[i].color[1]
                    if(self.blue): gr[min(len(gr)-sub_blue, id_blue)].weight = \
                        self.invert + mult * v_colors[i].color[2]
                    if(self.value):
                        r = v_colors[i].color[0]
                        g = v_colors[i].color[1]
                        b = v_colors[i].color[2]
                        gr[min(len(gr)-sub_value, id_value)].weight\
                        = self.invert + mult * (0.2126*r + 0.7152*g + 0.0722*b)
                    i+=1
            elif ob.data.color_attributes.active_color.domain == 'CORNER':
                for f in ob.data.polygons:
                    for v in f.vertices:
                        gr = ob.data.vertices[v].groups
                        if(self.red): gr[min(len(gr)-sub_red, id_red)].weight = \
                            self.invert + mult * v_colors[i].color[0]
                        if(self.green): gr[min(len(gr)-sub_green, id_green)].weight\
                            = self.invert + mult * v_colors[i].color[1]
                        if(self.blue): gr[min(len(gr)-sub_blue, id_blue)].weight = \
                            self.invert + mult * v_colors[i].color[2]
                        if(self.value):
                            r = v_colors[i].color[0]
                            g = v_colors[i].color[1]
                            b = v_colors[i].color[2]
                            gr[min(len(gr)-sub_value, id_value)].weight\
                            = self.invert + mult * (0.2126*r + 0.7152*g + 0.0722*b)
                        i+=1

            bpy.ops.paint.weight_paint_toggle()
        return {'FINISHED'}

class vertex_group_to_vertex_colors(Operator):
    bl_idname = "object.vertex_group_to_vertex_colors"
    bl_label = "Vertex Group"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Convert the active Vertex Group into a Vertex Color.")

    channel : EnumProperty(
        items=[('BLUE', 'Blue Channel', 'Convert to Blue Channel'),
               ('GREEN', 'Green Channel', 'Convert to Green Channel'),
               ('RED', 'Red Channel', 'Convert to Red Channel'),
               ('VALUE', 'Value Channel', 'Convert to Grayscale'),
               ('FALSE_COLORS', 'False Colors', 'Convert to False Colors')],
        name="Convert to", description="Choose how to convert vertex group",
        default="VALUE", options={'LIBRARY_EDITABLE'})

    invert : BoolProperty(
        name="invert", default=False, description="invert color channel")

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        obj = context.active_object
        me = obj.data
        group_id = obj.vertex_groups.active_index
        if (group_id == -1):
            return {'FINISHED'}

        bpy.ops.object.mode_set(mode='OBJECT')
        group_name = obj.vertex_groups[group_id].name
        bpy.ops.geometry.color_attribute_add()
        active_color = obj.data.color_attributes.active_color

        colors_name = group_name
        if(self.channel == 'FALSE_COLORS'): colors_name += "_false_colors"
        elif(self.channel == 'VALUE'):  colors_name += "_value"
        elif(self.channel == 'RED'):  colors_name += "_red"
        elif(self.channel == 'GREEN'):  colors_name += "_green"
        elif(self.channel == 'BLUE'):  colors_name += "_blue"
        active_color.name = colors_name

        v_colors = obj.data.color_attributes.active_color.data

        bm = bmesh.new()
        bm.from_mesh(me)
        dvert_lay = bm.verts.layers.deform.active
        weight = bmesh_get_weight_numpy(group_id,dvert_lay,bm.verts)
        if self.invert: weight = 1-weight
        loops_size = get_attribute_numpy(me.polygons, attribute='loop_total', mult=1)
        n_colors = np.sum(loops_size)
        splitted_weight = weight[:,None]
        r = np.zeros(splitted_weight.shape)
        g = np.zeros(splitted_weight.shape)
        b = np.zeros(splitted_weight.shape)
        a = np.ones(splitted_weight.shape)
        if(self.channel == 'FALSE_COLORS'):
            mult = 0.6+0.4*splitted_weight
            mask = splitted_weight < 0.25
            g[mask] = splitted_weight[mask]*4
            b[mask] = np.ones(splitted_weight.shape)[mask]

            mask = np.where(np.logical_and(splitted_weight>=0.25, splitted_weight<0.5))
            g[mask] = np.ones(splitted_weight.shape)[mask]
            b[mask] = (1-(splitted_weight[mask]-0.25)*4)

            mask = np.where(np.logical_and(splitted_weight>=0.5, splitted_weight<0.75))
            r[mask] = (splitted_weight[mask]-0.5)*4
            g[mask] = np.ones(splitted_weight.shape)[mask]

            mask = 0.75 <= splitted_weight
            r[mask] = np.ones(splitted_weight.shape)[mask]
            g[mask] = (1-(splitted_weight[mask]-0.75)*4)
        elif(self.channel == 'VALUE'):
            r = splitted_weight
            g = splitted_weight
            b = splitted_weight
        elif(self.channel == 'RED'):
            r = splitted_weight
        elif(self.channel == 'GREEN'):
            g = splitted_weight
        elif(self.channel == 'BLUE'):
            b = splitted_weight

        colors = np.concatenate((r,g,b,a),axis=1).flatten()
        v_colors.foreach_set('color',colors)

        bpy.ops.paint.vertex_paint_toggle()
        bpy.ops.geometry.color_attribute_render_set(name=active_color.name)
        return {'FINISHED'}

class vertex_group_to_uv(Operator):
    bl_idname = "object.vertex_group_to_uv"
    bl_label = "Vertex Group"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Combine two Vertex Groups as UV Map Layer.")

    vertex_group_u : StringProperty(
        name="U", default='',
        description="Vertex Group used for the U coordinate")
    vertex_group_v : StringProperty(
        name="V", default='',
        description="Vertex Group used for the V coordinate")
    normalize_weight : BoolProperty(
        name="Normalize Weight", default=True,
        description="Normalize weight values")
    invert_u : BoolProperty(
        name="Invert U", default=False, description="Invert U")
    invert_v : BoolProperty(
        name="Invert V", default=False, description="Invert V")

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        ob = context.object
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop_search(self, 'vertex_group_u', ob, "vertex_groups", text='')
        row.separator()
        row.prop_search(self, 'vertex_group_v', ob, "vertex_groups", text='')
        row = col.row(align=True)
        row.prop(self, "invert_u")
        row.separator()
        row.prop(self, "invert_v")
        row = col.row(align=True)
        row.prop(self, "normalize_weight")

    def execute(self, context):
        ob = context.active_object
        me = ob.data
        n_verts = len(me.vertices)
        vg_keys = ob.vertex_groups.keys()
        bool_u = self.vertex_group_u in vg_keys
        bool_v = self.vertex_group_v in vg_keys
        if bool_u or bool_v:
            bm = bmesh.new()
            bm.from_mesh(me)
            dvert_lay = bm.verts.layers.deform.active
            if bool_u:
                u_index = ob.vertex_groups[self.vertex_group_u].index
                u = bmesh_get_weight_numpy(u_index, dvert_lay, bm.verts)
                if self.invert_u:
                    u = 1-u
                if self.normalize_weight:
                    u = np.interp(u, (u.min(), u.max()), (0, 1))
            else:
                u = np.zeros(n_verts)
            if bool_v:
                v_index = ob.vertex_groups[self.vertex_group_v].index
                v = bmesh_get_weight_numpy(v_index, dvert_lay, bm.verts)
                if self.invert_v:
                    v = 1-v
                if self.normalize_weight:
                    v = np.interp(v, (v.min(), v.max()), (0, 1))
            else:
                v = np.zeros(n_verts)
        else:
            u = v = np.zeros(n_verts)

        uv_layer = me.uv_layers.new(name='Weight_to_UV')
        loops_size = get_attribute_numpy(me.polygons, attribute='loop_total', mult=1)
        n_data = np.sum(loops_size)
        v_id = np.ones(n_data)
        me.polygons.foreach_get('vertices',v_id)
        v_id = v_id.astype(int)
        split_u = u[v_id,None]
        split_v = v[v_id,None]
        uv = np.concatenate((split_u,split_v),axis=1).flatten()
        uv_layer.data.foreach_set('uv',uv)
        me.uv_layers.update()
        return {'FINISHED'}

class curvature_to_vertex_groups(Operator):
    bl_idname = "object.curvature_to_vertex_groups"
    bl_label = "Curvature"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Generate a Vertex Group based on the curvature of the"
                      "mesh. Is based on Dirty Vertex Color.")

    blur_strength : FloatProperty(
      name="Blur Strength", default=1, min=0.001,
      max=1, description="Blur strength per iteration")

    blur_iterations : IntProperty(
      name="Blur Iterations", default=1, min=0,
      max=40, description="Number of times to blur the values")

    angle : FloatProperty(
      name="Angle", default=5*pi/90, min=0,
      max=pi/2, subtype='ANGLE', description="Angle")

    invert : BoolProperty(
        name="Invert", default=False,
        description="Invert the curvature map")

    absolute : BoolProperty(
        name="Absolute", default=False, description="Absolute values")

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.geometry.color_attribute_add(domain='CORNER', color = (1,1,1,1))
        color_attributes = context.active_object.data.color_attributes
        color_attributes.active = color_attributes[-1]
        color_attributes.active_color = color_attributes[-1]
        color_attributes[-1].name = "Curvature"
        bpy.ops.geometry.color_attribute_render_set(name=color_attributes[-1].name)
        bpy.ops.object.mode_set(mode='VERTEX_PAINT')
        bpy.ops.paint.vertex_color_dirt(
            blur_strength=self.blur_strength,
            blur_iterations=self.blur_iterations,
            clean_angle=pi/2 + self.angle,
            dirt_angle=pi/2 - self.angle,
            normalize=False)
        bpy.ops.object.vertex_colors_to_vertex_groups(invert=self.invert)
        if self.absolute:
            ob = context.object
            weight = get_weight_numpy(ob.vertex_groups[-1], len(ob.data.vertices))
            weight = np.abs(0.5-weight)*2
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            bmesh_set_weight_numpy(bm,len(ob.vertex_groups)-1,weight)
            bm.to_mesh(ob.data)
            ob.vertex_groups.update()
            ob.data.update()
        #bpy.ops.geometry.color_attribute_remove()
        return {'FINISHED'}

class face_area_to_vertex_groups(Operator):
    bl_idname = "object.face_area_to_vertex_groups"
    bl_label = "Area"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Generate a Vertex Group based on the area of individual"
                      "faces.")

    invert : BoolProperty(
        name="invert", default=False, description="invert values")
    bounds : EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('AUTOMATIC', "Automatic Bounds", "")),
        default='AUTOMATIC', name="Bounds")

    min_area : FloatProperty(
        name="Min", default=0.01, soft_min=0, soft_max=1,
        description="Faces with 0 weight")

    max_area : FloatProperty(
        name="Max", default=0.1, soft_min=0, soft_max=1,
        description="Faces with 1 weight")

    def draw(self, context):
        layout = self.layout
        layout.label(text="Bounds")
        layout.prop(self, "bounds", text="")
        if self.bounds == 'MANUAL':
            layout.prop(self, "min_area")
            layout.prop(self, "max_area")

    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}
        ob.vertex_groups.new(name="Faces Area")

        areas = [[] for v in ob.data.vertices]

        for p in ob.data.polygons:
            for v in p.vertices:
                areas[v].append(p.area)

        for i in range(len(areas)):
            areas[i] = mean(areas[i])
        if self.bounds == 'MANUAL':
            min_area = self.min_area
            max_area = self.max_area
        elif self.bounds == 'AUTOMATIC':
            min_area = min(areas)
            max_area = max(areas)
        elif self.bounds == 'COMPRESSION':
            min_area = 1
            max_area = min(areas)
        elif self.bounds == 'TENSION':
            min_area = 1
            max_area = max(areas)
        delta_area = max_area - min_area
        if delta_area == 0:
            delta_area = 0.0001
            if self.bounds == 'MANUAL':
                delta_area = 0.0001
            else:
                self.report({'ERROR'}, "The faces have the same areas")
                #return {'CANCELLED'}
        for i in range(len(areas)):
            weight = (areas[i] - min_area)/delta_area
            ob.vertex_groups[-1].add([i], weight, 'REPLACE')
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}

class random_weight(Operator):
    bl_idname = "object.random_weight"
    bl_label = "Random"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Generate a random Vertex Group")

    min_val : FloatProperty(
        name="Min", default=0, soft_min=0, soft_max=1,
        description="Minimum Value")

    max_val : FloatProperty(
        name="Max", default=1, soft_min=0, soft_max=1,
        description="Maximum Value")

    #def draw(self, context):
    #    layout = self.layout
    #    layout.prop(self, "min_area")
    #    layout.prop(self, "max_area")
    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}
        #ob.vertex_groups.new(name="Random")
        n_verts = len(ob.data.vertices)
        weight = np.random.uniform(low=self.min_val, high=self.max_val, size=(n_verts,))
        np.clip(weight, 0, 1, out=weight)

        group_id = ob.vertex_groups.active_index
        for i in range(n_verts):
            ob.vertex_groups[group_id].add([i], weight[i], 'REPLACE')
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}


class harmonic_weight(Operator):
    bl_idname = "object.harmonic_weight"
    bl_label = "Harmonic"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Create an harmonic variation of the active Vertex Group")

    freq : FloatProperty(
        name="Frequency", default=20, soft_min=0,
        soft_max=100, description="Wave frequency")

    amp : FloatProperty(
        name="Amplitude", default=1, soft_min=0,
        soft_max=10, description="Wave amplitude")

    midlevel : FloatProperty(
        name="Midlevel", default=0, min=-1,
        max=1, description="Midlevel")

    add : FloatProperty(
        name="Add", default=0, min=-1,
        max=1, description="Add to the Weight")

    mult : FloatProperty(
        name="Multiply", default=0, min=0,
        max=1, description="Multiply for he Weight")

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        ob = context.active_object
        if len(ob.vertex_groups) > 0:
            group_id = ob.vertex_groups.active_index
            ob.vertex_groups.new(name="Harmonic")
            for i in range(len(ob.data.vertices)):
                try: val = ob.vertex_groups[group_id].weight(i)
                except: val = 0
                weight = self.amp*(math.sin(val*self.freq) - self.midlevel)/2 + 0.5 + self.add*val*(1-(1-val)*self.mult)
                ob.vertex_groups[-1].add([i], weight, 'REPLACE')
            ob.data.update()
        else:
            self.report({'ERROR'}, "Active object doesn't have vertex groups")
            return {'CANCELLED'}
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}


class tissue_weight_distance(Operator):
    bl_idname = "object.tissue_weight_distance"
    bl_label = "Weight Distance"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Create a weight map according to the distance from the "
                    "selected vertices along the mesh surface")

    mode : EnumProperty(
        items=(('GEOD', "Geodesic Distance", ""),
            ('EUCL', "Euclidean Distance", ""),
            ('TOPO', "Topology Distance", "")),
        default='GEOD', name="Distance Method")

    normalize : BoolProperty(
        name="Normalize", default=True,
        description="Automatically remap the distance values from 0 to 1")

    min_value : FloatProperty(
        name="Min", default=0, min=0,
        soft_max=100, description="Minimum Distance")

    max_value : FloatProperty(
        name="Max", default=10, min=0,
        soft_max=100, description="Max Distance")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)

    def fill_neighbors(self,verts,weight):
        neigh = {}
        for v0 in verts:
            for f in v0.link_faces:
                for v1 in f.verts:
                    if self.mode == 'GEOD':
                        dist = weight[v0.index] + (v0.co-v1.co).length
                    elif self.mode == 'TOPO':
                        dist = weight[v0.index] + 1.0
                    w1 = weight[v1.index]
                    if w1 == None or w1 > dist:
                        weight[v1.index] = dist
                        neigh[v1] = 0
        if len(neigh) == 0: return weight
        else: return self.fill_neighbors(neigh.keys(), weight)

    def execute(self, context):
        ob = context.object
        old_mode = ob.mode
        if old_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        me = ob.data

        # store weight values
        weight = [None]*len(me.vertices)

        if self.mode != 'EUCL':
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            selected = [v for v in bm.verts if v.select]
            if len(selected) == 0:
                bpy.ops.object.mode_set(mode=old_mode)
                message = "Please, select one or more vertices"
                self.report({'ERROR'}, message)
                return {'CANCELLED'}
            for v in selected: weight[v.index] = 0
            weight = self.fill_neighbors(selected, weight)
            bm.free()
        else:
            selected = [v for v in me.vertices if v.select]
            kd = KDTree(len(selected))
            for i, v in enumerate(selected):
                kd.insert(v.co, i)
            kd.balance()
            for i,v in enumerate(me.vertices):
                co, index, dist = kd.find(v.co)
                weight[i] = dist


        for i in range(len(weight)):
            if weight[i] == None: weight[i] = 0
        weight = np.array(weight)
        max_dist = np.max(weight)
        if self.normalize:
            if max_dist > 0:
                weight /= max_dist
        else:
            delta_value = self.max_value - self.min_value
            if delta_value == 0: delta_value = 0.0000001
            weight = (weight-self.min_value)/delta_value

        if self.mode == 'TOPO':
            vg = ob.vertex_groups.new(name='Distance: {:d}'.format(int(max_dist)))
        else:
            vg = ob.vertex_groups.new(name='Distance: {:.4f}'.format(max_dist))
        for i, w in enumerate(weight):
            vg.add([i], w, 'REPLACE')
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}

class TISSUE_PT_color(Panel):
    bl_label = "Tissue Tools"
    bl_category = "Tissue"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    #bl_options = {'DEFAULT_CLOSED'}
    bl_context = "vertexpaint"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("object.vertex_colors_to_vertex_groups",
            icon="GROUP_VERTEX", text="Convert to Weight")

class TISSUE_PT_weight(Panel):
    bl_label = "Tissue Tools"
    bl_category = "Tissue"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    #bl_options = {'DEFAULT_CLOSED'}
    bl_context = "weightpaint"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        #if context.object.type == 'MESH' and context.mode == 'OBJECT':
            #col.label(text="Transform:")
            #col.separator()
        #elif bpy.context.mode == 'PAINT_WEIGHT':
        col.label(text="Weight Generate:")
        #col.operator(
        #    "object.vertex_colors_to_vertex_groups", icon="GROUP_VCOL")
        col.operator("object.face_area_to_vertex_groups", icon="FACESEL")
        col.operator("object.curvature_to_vertex_groups", icon="SMOOTHCURVE")
        col.operator("object.tissue_weight_distance", icon="TRACKING")
        row = col.row(align=True)
        try: row.operator("object.weight_formula", icon="CON_TRANSFORM")
        except: row.operator("object.weight_formula")#, icon="CON_TRANSFORM")
        row.operator("object.update_weight_formula", icon="FILE_REFRESH", text='')#, icon="CON_TRANSFORM")
        #col.label(text="Weight Processing:")
        col.separator()

        # TO BE FIXED
        col.operator("object.weight_laplacian", icon="SMOOTHCURVE")

        col.label(text="Weight Edit:")
        col.operator("object.harmonic_weight", icon="IPO_ELASTIC")
        col.operator("object.random_weight", icon="RNDCURVE")
        col.separator()
        col.label(text="Deformation Analysis:")
        col.operator("object.edges_deformation", icon="DRIVER_DISTANCE")#FULLSCREEN_ENTER")
        col.operator("object.edges_bending", icon="DRIVER_ROTATIONAL_DIFFERENCE")#"MOD_SIMPLEDEFORM")
        col.separator()
        col.label(text="Weight Curves:")
        #col.operator("object.weight_contour_curves", icon="MOD_CURVE")
        col.operator("object.tissue_weight_streamlines", icon="ANIM")
        op = col.operator("object.tissue_weight_contour_curves_pattern", icon="FORCE_TURBULENCE")
        op.contour_mode = 'WEIGHT'
        col.separator()
        col.operator("object.weight_contour_displace", icon="MOD_DISPLACE")
        col.operator("object.weight_contour_mask", icon="MOD_MASK")
        col.separator()
        col.label(text="Simulations:")
        col.operator("object.start_reaction_diffusion",
                    icon="EXPERIMENTAL",
                    text="Reaction-Diffusion")
        col.separator()
        col.label(text="Materials:")
        col.operator("object.random_materials", icon='COLOR')
        col.operator("object.weight_to_materials", icon='GROUP_VERTEX')
        col.separator()
        col.label(text="Weight Convert:")
        col.operator("object.vertex_group_to_vertex_colors", icon="GROUP_VCOL",
            text="Convert to Colors")
        col.operator("object.vertex_group_to_uv", icon="UV",
            text="Convert to UV")

def contour_bmesh(me, bm, weight, iso_val):
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    vertices = get_vertices_numpy(me)
    faces_mask = np.array(bm.faces)
    filtered_edges = get_edges_id_numpy(me)
    n_verts = len(bm.verts)

    #############################

    # vertices indexes
    id0 = filtered_edges[:,0]
    id1 = filtered_edges[:,1]
    # vertices weight
    w0 = weight[id0]
    w1 = weight[id1]
    # weight condition
    bool_w0 = w0 < iso_val
    bool_w1 = w1 < iso_val

    # mask all edges that have one weight value below the iso value
    mask_new_verts = np.logical_xor(bool_w0, bool_w1)
    if not mask_new_verts.any(): return np.array([[None]]), {}, np.array([[None]])

    id0 = id0[mask_new_verts]
    id1 = id1[mask_new_verts]
    # filter arrays
    v0 = vertices[id0]
    v1 = vertices[id1]
    w0 = w0[mask_new_verts]
    w1 = w1[mask_new_verts]
    param = (iso_val-w0)/(w1-w0)
    param = np.expand_dims(param,axis=1)
    verts = v0 + (v1-v0)*param

    edges_id = {}
    for i, e in enumerate(filtered_edges):
        #edges_id[id] = i + n_verts
        edges_id['{}_{}'.format(e[0],e[1])] = i + n_verts
        edges_id['{}_{}'.format(e[1],e[0])] = i + n_verts

    splitted_faces = []

    switch = False
    # splitting faces
    for f in faces_mask:
        # create sub-faces slots. Once a new vertex is reached it will
        # change slot, storing the next vertices for a new face.
        build_faces = [[],[]]
        #switch = False
        verts0 = list(me.polygons[f.index].vertices)
        verts1 = list(verts0)
        verts1.append(verts1.pop(0)) # shift list
        for id0, id1 in zip(verts0, verts1):

            # add first vertex to active slot
            build_faces[switch].append(id0)

            # try to split edge
            try:
                # check if the edge must be splitted
                new_vert = edges_id['{}_{}'.format(id0,id1)]
                # add new vertex
                build_faces[switch].append(new_vert)
                # if there is an open face on the other slot
                if len(build_faces[not switch]) > 0:
                    # store actual face
                    splitted_faces.append(build_faces[switch])
                    # reset actual faces and switch
                    build_faces[switch] = []
                    # change face slot
                switch = not switch
                # continue previous face
                build_faces[switch].append(new_vert)
            except: pass
        if len(build_faces[not switch]) == 2:
            build_faces[not switch].append(id0)
        if len(build_faces[not switch]) > 2:
            splitted_faces.append(build_faces[not switch])
        # add last face
        splitted_faces.append(build_faces[switch])

    # adding new vertices use fast local method access
    _new_vert = bm.verts.new
    for v in verts: _new_vert(v)
    bm.verts.ensure_lookup_table()

    # deleting old edges/faces
    bm.edges.ensure_lookup_table()
    remove_edges = [bm.edges[i] for i in filtered_edges[:,2]]
    #for e in remove_edges: bm.edges.remove(e)
    #for e in delete_edges: bm.edges.remove(e)

    bm.verts.ensure_lookup_table()
    # adding new faces use fast local method access
    _new_face = bm.faces.new
    missed_faces = []
    for f in splitted_faces:
        try:
            face_verts = [bm.verts[i] for i in f]
            _new_face(face_verts)
        except:
            missed_faces.append(f)

    #me = bpy.data.meshes.new('_tissue_tmp_')
    bm.to_mesh(me)
    weight = np.concatenate((weight, np.ones(len(verts))*iso_val))

    return me, bm, weight




class tissue_weight_streamlines(Operator):
    bl_idname = "object.tissue_weight_streamlines"
    bl_label = "Streamlines Curves"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    mode : EnumProperty(
        items=(
            ('VERTS', "Verts", "Follow vertices"),
            ('EDGES', "Edges", "Follow Edges")
            ),
        default='VERTS',
        name="Streamlines path mode"
        )

    interpolation : EnumProperty(
        items=(
            ('POLY', "Poly", "Generate Polylines"),
            ('NURBS', "NURBS", "Generate Nurbs curves")
            ),
        default='POLY',
        name="Interpolation mode"
        )

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")

    use_selected : BoolProperty(
        name="Use Selected Vertices", default=False,
        description="Use selected vertices as Seed")

    same_weight : BoolProperty(
        name="Same Weight", default=True,
        description="Continue the streamlines when the weight is the same")

    min_iso : FloatProperty(
        name="Min Value", default=0., soft_min=0, soft_max=1,
        description="Minimum weight value")
    max_iso : FloatProperty(
        name="Max Value", default=1, soft_min=0, soft_max=1,
        description="Maximum weight value")

    rand_seed : IntProperty(
        name="Seed", default=0, min=0, soft_max=10,
        description="Random Seed")
    n_curves : IntProperty(
        name="Curves", default=50, soft_min=1, soft_max=100000,
        description="Number of Curves")
    min_rad = 1
    max_rad = 1

    pos_steps : IntProperty(
        name="High Steps", default=50, min=0, soft_max=100,
        description="Number of steps in the direction of high weight")
    neg_steps : IntProperty(
        name="Low Steps", default=50, min=0, soft_max=100,
        description="Number of steps in the direction of low weight")

    bevel_depth : FloatProperty(
        name="Bevel Depth", default=0, min=0, soft_max=1,
        description="")
    min_bevel_depth : FloatProperty(
        name="Min Bevel Depth", default=0.1, min=0, soft_max=1,
        description="")
    max_bevel_depth : FloatProperty(
        name="Max Bevel Depth", default=1, min=0, soft_max=1,
        description="")

    rand_dir : FloatProperty(
        name="Randomize", default=0, min=0, max=1,
        description="Randomize streamlines directions (Slower)")

    vertex_group_seeds : StringProperty(
        name="Displace", default='',
        description="Vertex Group used for pattern displace")

    vertex_group_bevel : StringProperty(
        name="Bevel", default='',
        description="Variable Bevel depth")

    object_name : StringProperty(
        name="Active Object", default='',
        description="")

    try: vg_name = bpy.context.object.vertex_groups.active.name
    except: vg_name = ''

    vertex_group_streamlines : StringProperty(
        name="Flow", default=vg_name,
        description="Vertex Group used for streamlines")

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob and len(ob.vertex_groups) > 0 or ob.type == 'CURVE'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        if not context.object.type == 'CURVE':
            self.object_name = context.object.name
        ob = bpy.data.objects[self.object_name]
        if self.vertex_group_streamlines not in [vg.name for vg in ob.vertex_groups]:
            self.vertex_group_streamlines = ob.vertex_groups.active.name
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(self, 'mode', expand=True,
            slider=True, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        col.prop(self, "use_modifiers")
        col.label(text="Streamlines Curves:")
        row = col.row(align=True)
        row.prop(self, 'interpolation', expand=True,
            slider=True, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        col.separator()
        col.prop_search(self, 'vertex_group_streamlines', ob, "vertex_groups", text='')
        if not (self.use_selected or context.mode == 'EDIT_MESH'):
            row = col.row(align=True)
            row.prop(self,'n_curves')
            #row.enabled = context.mode != 'EDIT_MESH'
            row = col.row(align=True)
            row.prop(self,'rand_seed')
            #row.enabled = context.mode != 'EDIT_MESH'
        row = col.row(align=True)
        row.prop(self,'neg_steps')
        row.prop(self,'pos_steps')
        #row = col.row(align=True)
        #row.prop(self,'min_iso')
        #row.prop(self,'max_iso')
        col.prop(self, "same_weight")
        col.separator()
        col.label(text='Curves Bevel:')
        col.prop_search(self, 'vertex_group_bevel', ob, "vertex_groups", text='')
        if self.vertex_group_bevel != '':
            row = col.row(align=True)
            row.prop(self,'min_bevel_depth')
            row.prop(self,'max_bevel_depth')
        else:
            col.prop(self,'bevel_depth')
        col.separator()
        col.prop(self, "rand_dir")

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}
        ob = bpy.data.objects[self.object_name]
        ob.select_set(False)


        seeds = []

        if bpy.context.mode == 'EDIT_MESH':
            self.use_selected = True
            bpy.ops.object.mode_set(mode='OBJECT')
            #ob = bpy.context.object
            #me = simple_to_mesh(ob)
        ob = convert_object_to_mesh(ob, apply_modifiers=self.use_modifiers)
        #dg = context.evaluated_depsgraph_get()
        #ob = ob.evaluated_get(dg)
        me = ob.data

        if self.use_selected:
            # generate new bmesh
            bm = bmesh.new()
            bm.from_mesh(me)
            #for v in me.vertices:
            #    if v.select: seeds.append(v.index)
            for v in bm.verts:
                if v.select: seeds.append(v.index)
            bm.free()
        n_verts = len(me.vertices)
        n_edges = len(me.edges)
        n_faces = len(me.polygons)

        # store weight values
        try:
            weight = get_weight_numpy(ob.vertex_groups[self.vertex_group_streamlines], n_verts)
        except:
            bpy.data.objects.remove(ob)
            self.report({'ERROR'}, "Please select a Vertex Group for streamlines")
            return {'CANCELLED'}

        variable_bevel = False
        bevel_weight = None
        bevel_depth = self.bevel_depth
        try:
            if self.min_bevel_depth == self.max_bevel_depth:
                #bevel_weight = np.ones((n_verts))
                bevel_depth = self.min_bevel_depth
            else:
                b0 = min(self.min_bevel_depth, self.max_bevel_depth)
                b1 = max(self.min_bevel_depth, self.max_bevel_depth)
                bevel_weight = get_weight_numpy(ob.vertex_groups[self.vertex_group_bevel], n_verts)
                if self.min_bevel_depth > self.max_bevel_depth:
                    bevel_weight = 1-bevel_weight
                bevel_weight = b0/b1 + bevel_weight*((b1-b0)/b1)
                bevel_depth = b1
            variable_bevel = True
        except:
            pass#bevel_weight = np.ones((n_verts))


        if not seeds:
            np.random.seed(self.rand_seed)
            seeds = np.random.randint(n_verts, size=self.n_curves)

        #weight = np.array(get_weight(ob.vertex_groups.active, n_verts))

        curves_pts = []
        curves_weight = []

        neigh = [[] for i in range(n_verts)]
        if self.mode == 'EDGES':
            # store neighbors
            for e in me.edges:
                ev = e.vertices
                neigh[ev[0]].append(ev[1])
                neigh[ev[1]].append(ev[0])

        elif self.mode == 'VERTS':
            # store neighbors
            for p in me.polygons:
                face_verts = [v for v in p.vertices]
                n_face_verts = len(face_verts)
                for i in range(n_face_verts):
                    fv = face_verts.copy()
                    neigh[fv.pop(i)] += fv

        neigh_weight = [weight[n].tolist() for n in neigh]

        # evaluate direction
        next_vert = [-1]*n_verts

        if self.rand_dir > 0:
            for i in range(n_verts):
                n = neigh[i]
                nw = neigh_weight[i]
                sorted_nw = neigh_weight[i].copy()
                sorted_nw.sort()
                for w in sorted_nw:
                    neigh[i] = [n[nw.index(w)] for w in sorted_nw]
        else:
            if self.pos_steps > 0:
                for i in range(n_verts):
                    n = neigh[i]
                    if len(n) == 0: continue
                    nw = neigh_weight[i]
                    max_w = max(nw)
                    if self.same_weight:
                        if max_w >= weight[i]:
                            next_vert[i] = n[nw.index(max(nw))]
                    else:
                        if max_w > weight[i]:
                            next_vert[i] = n[nw.index(max(nw))]

            if self.neg_steps > 0:
                prev_vert = [-1]*n_verts
                for i in range(n_verts):
                    n = neigh[i]
                    if len(n) == 0: continue
                    nw = neigh_weight[i]
                    min_w = min(nw)
                    if self.same_weight:
                        if min_w <= weight[i]:
                            prev_vert[i] = n[nw.index(min(nw))]
                    else:
                        if min_w < weight[i]:
                            prev_vert[i] = n[nw.index(min(nw))]

        co = [0]*3*n_verts
        me.vertices.foreach_get('co', co)
        co = np.array(co).reshape((-1,3))

        # create streamlines
        curves = []
        for i in seeds:
            next_pts = [i]
            for j in range(self.pos_steps):
                if self.rand_dir > 0:
                    n = neigh[next_pts[-1]]
                    if len(n) == 0: break
                    next = n[int((len(n)-1) * (1-random.random() * self.rand_dir))]
                else:
                    next = next_vert[next_pts[-1]]
                if next > 0:
                    if next not in next_pts: next_pts.append(next)
                else: break

            prev_pts = [i]
            for j in range(self.neg_steps):
                if self.rand_dir > 0:
                    n = neigh[prev_pts[-1]]
                    if len(n) == 0: break
                    prev = n[int(len(n) * random.random() * self.rand_dir)]
                else:
                    prev = prev_vert[prev_pts[-1]]
                if prev > 0:
                    if prev not in prev_pts:
                        prev_pts.append(prev)
                else: break

            next_pts = np.array(next_pts).astype('int')
            prev_pts = np.flip(prev_pts[1:]).astype('int')
            all_pts = np.concatenate((prev_pts, next_pts))
            if len(all_pts) > 1:
                curves.append(all_pts)
        crv = nurbs_from_vertices(curves, co, bevel_weight, ob.name + '_Streamlines', True, self.interpolation)
        crv.data.bevel_depth = bevel_depth
        crv.matrix_world = ob.matrix_world
        bpy.data.objects.remove(ob)

        print("Streamlines Curves, total time: " + str(timeit.default_timer() - start_time) + " sec")
        return {'FINISHED'}
