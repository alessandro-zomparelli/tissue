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

import bpy, bmesh
import numpy as np
import math, timeit, time
from math import *#pi, sin
from statistics import mean, stdev
from mathutils import Vector
from numpy import *
try: from .numba_functions import numba_reaction_diffusion
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
    IntVectorProperty
)

from .utils import *

def reaction_diffusion_add_handler(self, context):
    # remove existing handlers
    old_handlers = []
    for h in bpy.app.handlers.frame_change_post:
        if "reaction_diffusion" in str(h):
            old_handlers.append(h)
    for h in old_handlers: bpy.app.handlers.frame_change_post.remove(h)
    # add new handler
    bpy.app.handlers.frame_change_post.append(reaction_diffusion_def)

class formula_prop(PropertyGroup):
    name : StringProperty()
    formula : StringProperty()
    float_var : FloatVectorProperty(name="", description="", default=(0, 0, 0, 0, 0), size=5)
    int_var : IntVectorProperty(name="", description="", default=(0, 0, 0, 0, 0), size=5)

class reaction_diffusion_prop(PropertyGroup):
    run : BoolProperty(default=False, update = reaction_diffusion_add_handler,
        description='Compute a new iteration on frame changes. Currently is not working during  Render Animation')

    time_steps : bpy.props.IntProperty(
        name="Steps", default=10, min=0, soft_max=50,
        description="Number of Steps")

    dt : bpy.props.FloatProperty(
        name="dt", default=1, min=0, soft_max=0.2,
        description="Time Step")

    diff_a : bpy.props.FloatProperty(
        name="Diff A", default=0.1, min=0, soft_max=2, precision=3,
        description="Diffusion A")

    diff_b : bpy.props.FloatProperty(
        name="Diff B", default=0.05, min=0, soft_max=2, precision=3,
        description="Diffusion B")

    f : bpy.props.FloatProperty(
        name="f", default=0.055, min=0, soft_max=0.5, precision=3,
        description="Feed Rate")

    k : bpy.props.FloatProperty(
        name="k", default=0.062, min=0, soft_max=0.5, precision=3,
        description="Kill Rate")

    diff_mult : bpy.props.FloatProperty(
        name="Scale", default=1, min=0, soft_max=1, max=2, precision=2,
        description="Multiplier for the diffusion of both substances")

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
                global_co.append(mat * v)
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

class weight_formula_wiki(bpy.types.Operator):
    bl_idname = "scene.weight_formula_wiki"
    bl_label = "Online Documentation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.wm.url_open(url="https://github.com/alessandro-zomparelli/tissue/wiki/Weight-Tools#weight-formula")
        return {'FINISHED'}

class weight_formula(bpy.types.Operator):
    bl_idname = "object.weight_formula"
    bl_label = "Weight Formula"
    bl_options = {'REGISTER', 'UNDO'}

    ex = [
        #'cos(arctan(nx/ny)*6 + sin(rz*30)*0.5)/2 + cos(arctan(nx/ny)*6 - sin(rz*30)*0.5 + pi/2)/2 + 0.5',
        'cos(arctan(nx/ny)*i1*2 + sin(rz*i3))/i2 + cos(arctan(nx/ny)*i1*2 - sin(rz*i3))/i2 + 0.5',
        'cos(arctan(nx/ny)*i1*2 + sin(rz*i2))/2 + cos(arctan(nx/ny)*i1*2 - sin(rz*i2))/2',
        '(sin(arctan(nx/ny)*i1)*sin(nz*i1)+1)/2',
        'cos(arctan(nx/ny)*f1)',
        'cos(arctan(lx/ly)*f1 + sin(rz*f2)*f3)',
        'sin(nx*15)<sin(ny*15)',
        'cos(ny*rz**2*i1)',
        'sin(rx*30) > 0',
        'sin(nz*i1)',
        'w[0]**2',
        'sqrt((rx-0.5)**2 + (ry-0.5)**2)*2',
        'abs(0.5-rz)*2',
        'rx'
        ]
    ex_items = list((s,s,"") for s in ex)
    ex_items.append(('CUSTOM', "User Formula", ""))

    examples : bpy.props.EnumProperty(
        items = ex_items, default='CUSTOM', name="Examples")

    old_ex = ""

    formula : bpy.props.StringProperty(
        name="Formula", default="", description="Formula to Evaluate")
    bl_description = ("Generate a Vertex Group based on the given formula")

    slider_f01 : bpy.props.FloatProperty(
        name="f1", default=1, description="Slider")
    bl_description = ("Slider Float 1")
    slider_f02 : bpy.props.FloatProperty(
        name="f2", default=1, description="Slider")
    bl_description = ("Slider Float 2")
    slider_f03 : bpy.props.FloatProperty(
        name="f3", default=1, description="Slider")
    bl_description = ("Slider Float 3")
    slider_f04 : bpy.props.FloatProperty(
        name="f4", default=1, description="Slider")
    bl_description = ("Slider Float 4")
    slider_f05 : bpy.props.FloatProperty(
        name="f5", default=1, description="Slider")
    bl_description = ("Slider Float 5")
    slider_i01 : bpy.props.IntProperty(
        name="i1", default=1, description="Slider")
    bl_description = ("Slider Integer 1")
    slider_i02 : bpy.props.IntProperty(
        name="i2", default=1, description="Slider")
    bl_description = ("Slider Integer 2")
    slider_i03 : bpy.props.IntProperty(
        name="i3", default=1, description="Slider")
    bl_description = ("Slider Integer 3")
    slider_i04 : bpy.props.IntProperty(
        name="i4", default=1, description="Slider")
    bl_description = ("Slider Integer 4")
    slider_i05 : bpy.props.IntProperty(
        name="i5", default=1, description="Slider")
    bl_description = ("Slider Integer 5")

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

        if self.examples != self.old_ex and self.examples != 'CUSTOM':
            self.formula = self.examples
            self.old_ex = self.examples
        elif self.formula != self.examples:
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
        ob = bpy.context.active_object
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

        if self.examples != self.old_ex and self.examples != 'CUSTOM':
            self.formula = self.examples
            self.old_ex = self.examples
        elif self.formula != self.examples:
            self.examples = 'CUSTOM'
        formula = self.formula

        if formula == "": return {'FINISHED'}
        vertex_group_name = "Formula " + formula
        ob.vertex_groups.new(name=vertex_group_name)

        weight = compute_formula(ob, formula=formula, float_var=f_sliders, int_var=i_sliders)
        if type(weight) == str:
            self.report({'ERROR'}, weight)
            return {'CANCELLED'}

        #start_time = timeit.default_timer()
        weight = nan_to_num(weight)
        if type(weight) == int or type(weight) == float:
            for i in range(n_verts):
                ob.vertex_groups[-1].add([i], weight, 'REPLACE')
        elif type(weight) == ndarray:
            for i in range(n_verts):
                ob.vertex_groups[-1].add([i], weight[i], 'REPLACE')
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

class _weight_laplacian(bpy.types.Operator):
    bl_idname = "object._weight_laplacian"
    bl_label = "Weight Laplacian"
    bl_description = ("Compute the Vertex Group Laplacian")
    bl_options = {'REGISTER', 'UNDO'}

    bounds : bpy.props.EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('POSITIVE', "Positive Only", ""),
            ('NEGATIVE', "Negative Only", ""),
            ('AUTOMATIC', "Automatic Bounds", "")),
        default='AUTOMATIC', name="Bounds")

    mode : bpy.props.EnumProperty(
        items=(('LENGTH', "Length Weight", ""),
            ('SIMPLE', "Simple", "")),
        default='SIMPLE', name="Evaluation Mode")

    min_def : bpy.props.FloatProperty(
        name="Min", default=0, soft_min=-1, soft_max=0,
        description="Laplacian value with 0 weight")

    max_def : bpy.props.FloatProperty(
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
            if val > 0.7: print(str(val) + " " + str(lap[i]))
            #val = weight[i] + 0.2*lap[i]
            ob.vertex_groups[-1].add([i], val, 'REPLACE')
        self.bounds_string = str(round(min_def,2)) + " to " + str(round(max_def,2))
        ob.vertex_groups[-1].name = group_name + " " + self.bounds_string
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}

class weight_laplacian(bpy.types.Operator):
    bl_idname = "object.weight_laplacian"
    bl_label = "Weight Laplacian"
    bl_description = ("Compute the Vertex Group Laplacian")
    bl_options = {'REGISTER', 'UNDO'}

    steps : bpy.props.IntProperty(
        name="Steps", default=10, min=0, soft_max=50,
        description="Number of Steps")

    dt : bpy.props.FloatProperty(
        name="dt", default=0.2, min=0, soft_max=0.2,
        description="Time Step")

    diff_a : bpy.props.FloatProperty(
        name="Diff A", default=1, min=0, soft_max=2,
        description="Diffusion A")

    diff_b : bpy.props.FloatProperty(
        name="Diff B", default=0.5, min=0, soft_max=2,
        description="Diffusion B")

    f : bpy.props.FloatProperty(
        name="f", default=0.055, min=0, soft_max=0.5,
        description="Feed Rate")

    k : bpy.props.FloatProperty(
        name="k", default=0.062, min=0, soft_max=0.5,
        description="Kill Rate")

    diff_mult : bpy.props.FloatProperty(
        name="Scale", default=1, min=0, soft_max=1, max=2, precision=2,
        description="Multiplier for the diffusion of both substances")

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

        # store weight values
        a = []
        b = []
        for v in me.vertices:
            try:
                a.append(ob.vertex_groups["A"].weight(v.index))
            except:
                a.append(0)
            try:
                b.append(ob.vertex_groups["B"].weight(v.index))
            except:
                b.append(0)

        a = array(a)
        b = array(b)
        f = self.f
        k = self.k
        diff_a = self.diff_a * self.diff_mult
        diff_b = self.diff_b * self.diff_mult
        dt = self.dt

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
            for e in link_edges:
                for v1 in e.verts:
                    if v != v1: neighbors.append(v1.index)
            id_neighbors.append(neighbors)
        n_neighbors = array(n_neighbors)


        a = [[] for i in range(n_verts)]
        lap_map = []

        for e in bm.edges:
            id0 = e.verts[0].index
            id1 = e.verts[1].index
            lap_map[id0].append(id1)
            lap_map[id1].append(id0)

        e1 = array(e1)
        e2 = array(e2)
        lap_a = a[e1]

        for i in range(self.steps):

            lap_a = zeros((n_verts))#[0]*n_verts
            lap_b = zeros((n_verts))#[0]*n_verts
            for e in bm.edges:
                id0 = e.verts[0].index
                id1 = e.verts[1].index
                lap_a[id0] += a[id1] - a[id0]
                lap_a[id1] += a[id0] - a[id1]
                lap_b[id0] += b[id1] - b[id0]
                lap_b[id1] += b[id0] - b[id1]
            ab2 = a*b**2
            a += (diff_a*lap_a - ab2 + f*(1-a))*dt
            b += (diff_b*lap_b + ab2 - (k+f)*b)*dt

        for i in range(n_verts):
            ob.vertex_groups['A'].add([i], a[i], 'REPLACE')
            ob.vertex_groups['B'].add([i], b[i], 'REPLACE')
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}


class reaction_diffusion(bpy.types.Operator):
    bl_idname = "object.reaction_diffusion"
    bl_label = "Reaction Diffusion"
    bl_description = ("Run a Reaction-Diffusion based on existing Vertex Groups: A and B")
    bl_options = {'REGISTER', 'UNDO'}

    steps : bpy.props.IntProperty(
        name="Steps", default=10, min=0, soft_max=50,
        description="Number of Steps")

    dt : bpy.props.FloatProperty(
        name="dt", default=0.2, min=0, soft_max=0.2,
        description="Time Step")

    diff_a : bpy.props.FloatProperty(
        name="Diff A", default=1, min=0, soft_max=2,
        description="Diffusion A")

    diff_b : bpy.props.FloatProperty(
        name="Diff B", default=0.5, min=0, soft_max=2,
        description="Diffusion B")

    f : bpy.props.FloatProperty(
        name="f", default=0.055, min=0, soft_max=0.5,
        description="Feed Rate")

    k : bpy.props.FloatProperty(
        name="k", default=0.062, min=0, soft_max=0.5,
        description="Kill Rate")

    bounds_string = ""

    frame = None

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0


    def execute(self, context):
        #bpy.app.handlers.frame_change_post.remove(reaction_diffusion_def)
        reaction_diffusion_add_handler(self, context)
        set_animatable_fix_handler(self, context)
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}

        me = ob.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.edges.ensure_lookup_table()

        # store weight values
        a = []
        b = []
        for v in me.vertices:
            try:
                a.append(ob.vertex_groups["A"].weight(v.index))
            except:
                a.append(0)
            try:
                b.append(ob.vertex_groups["B"].weight(v.index))
            except:
                b.append(0)

        a = array(a)
        b = array(b)
        f = self.f
        k = self.k
        diff_a = self.diff_a
        diff_b = self.diff_b
        dt = self.dt
        n_verts = len(bm.verts)

        for i in range(self.steps):

            lap_a = zeros((n_verts))#[0]*n_verts
            lap_b = zeros((n_verts))#[0]*n_verts
            for e in bm.edges:
                id0 = e.verts[0].index
                id1 = e.verts[1].index
                lap_a[id0] += a[id1] - a[id0]
                lap_a[id1] += a[id0] - a[id1]
                lap_b[id0] += b[id1] - b[id0]
                lap_b[id1] += b[id0] - b[id1]
            ab2 = a*b**2
            a += (diff_a*lap_a - ab2 + f*(1-a))*dt
            b += (diff_b*lap_b + ab2 - (k+f)*b)*dt

            for i in range(n_verts):
                ob.vertex_groups['A'].add([i], a[i], 'REPLACE')
                ob.vertex_groups['B'].add([i], b[i], 'REPLACE')
            ob.vertex_groups.update()
            ob.data.update()

            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}


class edges_deformation(bpy.types.Operator):
    bl_idname = "object.edges_deformation"
    bl_label = "Edges Deformation"
    bl_description = ("Compute Weight based on the deformation of edges"+
        "according to visible modifiers.")
    bl_options = {'REGISTER', 'UNDO'}

    bounds : bpy.props.EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('COMPRESSION', "Compressed Only", ""),
            ('TENSION', "Extended Only", ""),
            ('AUTOMATIC', "Automatic Bounds", "")),
        default='AUTOMATIC', name="Bounds")

    mode : bpy.props.EnumProperty(
        items=(('MAX', "Max Deformation", ""),
            ('MEAN', "Average Deformation", "")),
        default='MEAN', name="Evaluation Mode")

    min_def : bpy.props.FloatProperty(
        name="Min", default=0, soft_min=-1, soft_max=0,
        description="Deformations with 0 weight")

    max_def : bpy.props.FloatProperty(
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
        return {'FINISHED'}

class edges_bending(bpy.types.Operator):
    bl_idname = "object.edges_bending"
    bl_label = "Edges Bending"
    bl_description = ("Compute Weight based on the bending of edges"+
        "according to visible modifiers.")
    bl_options = {'REGISTER', 'UNDO'}

    bounds : bpy.props.EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('POSITIVE', "Positive Only", ""),
            ('NEGATIVE', "Negative Only", ""),
            ('UNSIGNED', "Absolute Bending", ""),
            ('AUTOMATIC', "Signed Bending", "")),
        default='AUTOMATIC', name="Bounds")

    min_def : bpy.props.FloatProperty(
        name="Min", default=-10, soft_min=-45, soft_max=45,
        description="Deformations with 0 weight")

    max_def : bpy.props.FloatProperty(
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
        return {'FINISHED'}

class weight_contour_displace(bpy.types.Operator):
    bl_idname = "object.weight_contour_displace"
    bl_label = "Contour Displace"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers : bpy.props.BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")
    min_iso : bpy.props.FloatProperty(
        name="Min Iso Value", default=0.49, min=0, max=1,
        description="Threshold value")
    max_iso : bpy.props.FloatProperty(
        name="Max Iso Value", default=0.51, min=0, max=1,
        description="Threshold value")
    n_cuts : bpy.props.IntProperty(
        name="Cuts", default=2, min=1, soft_max=10,
        description="Number of cuts in the selected range of values")
    bool_displace : bpy.props.BoolProperty(
        name="Add Displace", default=True, description="Add Displace Modifier")
    bool_flip : bpy.props.BoolProperty(
        name="Flip", default=False, description="Flip Output Weight")

    weight_mode : bpy.props.EnumProperty(
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
            check = bpy.context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}

        ob0 = bpy.context.object

        group_id = ob0.vertex_groups.active_index
        vertex_group_name = ob0.vertex_groups[group_id].name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
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
            for v in verts: new_vert = bm.verts.new(v)
            bm.verts.index_update()
            bm.verts.ensure_lookup_table()
            # adding new faces
            missed_faces = []
            added_faces = []
            for f in splitted_faces:
                try:
                    face_verts = [bm.verts[i] for i in f]
                    new_face = bm.faces.new(face_verts)
                    for e in new_face.edges:
                        filtered_edges.append(e)
                except:
                    missed_faces.append(f)

            bm.faces.ensure_lookup_table()
            # updating weight values
            weight = weight + [iso_val]*len(verts)

            # deleting old edges/faces
            bm.edges.ensure_lookup_table()
            for e in delete_edges:
                bm.edges.remove(e)
            _filtered_edges = []
            for e in filtered_edges:
                if e not in delete_edges: _filtered_edges.append(e)
            filtered_edges = _filtered_edges

        name = ob0.name + '_ContourDisp'
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        ob = bpy.data.objects.new(name, me)

        # Link object to scene and make active
        scn = bpy.context.scene
        bpy.context.collection.objects.link(ob)
        bpy.context.view_layer.objects.active = ob
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

class weight_contour_mask(bpy.types.Operator):
    bl_idname = "object.weight_contour_mask"
    bl_label = "Contour Mask"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers : bpy.props.BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")
    iso : bpy.props.FloatProperty(
        name="Iso Value", default=0.5, soft_min=0, soft_max=1,
        description="Threshold value")
    bool_solidify : bpy.props.BoolProperty(
        name="Solidify", default=True, description="Add Solidify Modifier")
    normalize_weight : bpy.props.BoolProperty(
        name="Normalize Weight", default=True,
        description="Normalize weight of remaining vertices")

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = bpy.context.object.vertex_groups[0]
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
        for v in verts: bm.verts.new(v)
        bm.verts.ensure_lookup_table()

        # deleting old edges/faces
        bm.edges.ensure_lookup_table()
        remove_edges = []
        for e in delete_edges: bm.edges.remove(e)

        bm.verts.ensure_lookup_table()
        # adding new faces
        missed_faces = []
        for f in splitted_faces:
            try:
                face_verts = [bm.verts[i] for i in f]
                bm.faces.new(face_verts)
            except:
                missed_faces.append(f)

        # Mask geometry
        if(True):
            all_weight = weight + [iso_val+0.0001]*len(verts)
            weight = []
            for w, v in zip(all_weight, bm.verts):
                if w < iso_val: bm.verts.remove(v)
                else: weight.append(w)

        # Create mesh and object
        name = ob0.name + '_ContourMask_{:.3f}'.format(iso_val)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        ob = bpy.data.objects.new(name, me)

        # Link object to scene and make active
        scn = bpy.context.scene
        bpy.context.collection.objects.link(ob)
        bpy.context.view_layer.objects.active = ob
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

class weight_contour_curves(bpy.types.Operator):
    bl_idname = "object.weight_contour_curves"
    bl_label = "Contour Curves"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers : bpy.props.BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")

    min_iso : bpy.props.FloatProperty(
        name="Min Value", default=0., soft_min=0, soft_max=1,
        description="Minimum weight value")
    max_iso : bpy.props.FloatProperty(
        name="Max Value", default=1, soft_min=0, soft_max=1,
        description="Maximum weight value")
    n_curves : bpy.props.IntProperty(
        name="Curves", default=3, soft_min=1, soft_max=10,
        description="Number of Contour Curves")

    min_rad : bpy.props.FloatProperty(
        name="Min Radius", default=0.25, soft_min=0, soft_max=1,
        description="Minimum Curve Radius")
    max_rad : bpy.props.FloatProperty(
        name="Max Radius", default=0.75, soft_min=0, soft_max=1,
        description="Maximum Curve Radius")

    @classmethod
    def poll(cls, context):
        ob = context.object
        return len(ob.vertex_groups) > 0 or ob.type == 'CURVE'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = bpy.context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}
        ob0 = bpy.context.object

        group_id = ob0.vertex_groups.active_index
        vertex_group_name = ob0.vertex_groups[group_id].name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        if self.use_modifiers:
            me0 = simple_to_mesh(ob0) #ob0.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get()).copy()
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

        filtered_edges = bm.edges
        total_verts = []
        total_segments = []
        radius = []

        # start iterate contours levels
        for c in range(self.n_curves):
            min_iso = min(self.min_iso, self.max_iso)
            max_iso = max(self.min_iso, self.max_iso)
            try:
                iso_val = c*(max_iso-min_iso)/(self.n_curves-1)+min_iso
                if iso_val < 0: iso_val = (min_iso + max_iso)/2
            except:
                iso_val = (min_iso + max_iso)/2
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

            faces_todo = [f.select for f in bm.faces]
            verts = []

            edges_id = {}
            _filtered_edges = []
            n_verts = len(bm.verts)
            count = len(total_verts)
            for e in filtered_edges:
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
                    #v0 = me0.vertices[id0].select = True
                    #v1 = me0.vertices[id1].select = True
                    v0 = me0.vertices[id0].co
                    v1 = me0.vertices[id1].co
                    v = v0.lerp(v1, (iso_val-w0)/(w1-w0))
                    verts.append(v)
                    edges_id[e.index] = count
                    count += 1
                    _filtered_edges.append(e)
            filtered_edges = _filtered_edges

            if len(verts) == 0: continue

            # finding segments
            segments = []
            for f in faces_mask:
                seg = []
                for e in f.edges:
                    try:
                        seg.append(edges_id[e.index])
                        if len(seg) == 2:
                            segments.append(seg)
                            seg = []
                    except: pass

            total_segments = total_segments + segments
            total_verts = total_verts + verts

            # Radius

            try:
                iso_rad = c*(self.max_rad-self.min_rad)/(self.n_curves-1)+self.min_rad
                if iso_rad < 0: iso_rad = (self.min_rad + self.max_rad)/2
            except:
                iso_rad = (self.min_rad + self.max_rad)/2
            radius = radius + [iso_rad]*len(verts)

        bm = bmesh.new()
        # adding new vertices
        for v in total_verts: bm.verts.new(v)
        bm.verts.ensure_lookup_table()

        # adding new edges
        for s in total_segments:
            try:
                pts = [bm.verts[i] for i in s]
                bm.edges.new(pts)
            except: pass

        try:
            name = ob0.name + '_ContourCurves'
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me)
            ob = bpy.data.objects.new(name, me)

            # Link object to scene and make active
            scn = bpy.context.scene
            bpy.context.collection.objects.link(ob)
            bpy.context.view_layer.objects.active = ob
            ob.select_set(True)
            ob0.select_set(False)

            bpy.ops.object.convert(target='CURVE')
            ob = context.object
            count = 0
            for s in ob.data.splines:
                for p in s.points:
                    p.radius = radius[count]
                    count += 1
            ob.data.bevel_depth = 0.01
            ob.data.fill_mode = 'FULL'
            ob.data.bevel_resolution = 3
        except:
            self.report({'ERROR'}, "There are no values in the chosen range")
            return {'CANCELLED'}

        # align new object
        ob.matrix_world = ob0.matrix_world
        print("Contour Curves time: " + str(timeit.default_timer() - start_time) + " sec")

        bpy.data.meshes.remove(me0)
        bpy.data.meshes.remove(me)

        return {'FINISHED'}

class vertex_colors_to_vertex_groups(bpy.types.Operator):
    bl_idname = "object.vertex_colors_to_vertex_groups"
    bl_label = "Vertex Color"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Convert the active Vertex Color into a Vertex Group.")

    red : bpy.props.BoolProperty(
        name="red channel", default=False, description="convert red channel")
    green : bpy.props.BoolProperty(
        name="green channel", default=False,
        description="convert green channel")
    blue : bpy.props.BoolProperty(
        name="blue channel", default=False, description="convert blue channel")
    value : bpy.props.BoolProperty(
        name="value channel", default=True, description="convert value channel")
    invert : bpy.props.BoolProperty(
         name="invert", default=False, description="invert all color channels")

    @classmethod
    def poll(cls, context):
        return len(context.object.data.vertex_colors) > 0

    def execute(self, context):
        obj = bpy.context.active_object
        id = len(obj.vertex_groups)
        id_red = id
        id_green = id
        id_blue = id
        id_value = id

        boolCol = len(obj.data.vertex_colors)
        if(boolCol): col_name = obj.data.vertex_colors.active.name
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        if(self.red and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_red = id
            obj.vertex_groups[id_red].name = col_name + '_red'
            id+=1
        if(self.green and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_green = id
            obj.vertex_groups[id_green].name = col_name + '_green'
            id+=1
        if(self.blue and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_blue = id
            obj.vertex_groups[id_blue].name = col_name + '_blue'
            id+=1
        if(self.value and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_value = id
            obj.vertex_groups[id_value].name = col_name + '_value'
            id+=1

        mult = 1
        if(self.invert): mult = -1
        bpy.ops.object.mode_set(mode='OBJECT')
        sub_red = 1 + self.value + self.blue + self.green
        sub_green = 1 + self.value + self.blue
        sub_blue = 1 + self.value
        sub_value = 1

        id = len(obj.vertex_groups)
        if(id_red <= id and id_green <= id and id_blue <= id and id_value <= \
                id and boolCol):
            v_colors = obj.data.vertex_colors.active.data
            i = 0
            for f in obj.data.polygons:
                for v in f.vertices:
                    gr = obj.data.vertices[v].groups
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

class vertex_group_to_vertex_colors(bpy.types.Operator):
    bl_idname = "object.vertex_group_to_vertex_colors"
    bl_label = "Vertex Group"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Convert the active Vertex Group into a Vertex Color.")

    channel : bpy.props.EnumProperty(
        items=[('Blue', 'Blue Channel', 'Convert to Blue Channel'),
               ('Green', 'Green Channel', 'Convert to Green Channel'),
               ('Red', 'Red Channel', 'Convert to Red Channel'),
               ('Value', 'Value Channel', 'Convert to Grayscale'),
               ('False Colors', 'False Colors', 'Convert to False Colors')],
        name="Convert to", description="Choose how to convert vertex group",
        default="Value", options={'LIBRARY_EDITABLE'})

    invert : bpy.props.BoolProperty(
        name="invert", default=False, description="invert color channel")

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        obj = bpy.context.active_object
        group_id = obj.vertex_groups.active_index
        if (group_id == -1):
            return {'FINISHED'}

        bpy.ops.object.mode_set(mode='OBJECT')
        group_name = obj.vertex_groups[group_id].name
        bpy.ops.mesh.vertex_color_add()
        colors_id = obj.data.vertex_colors.active_index

        colors_name = group_name
        if(self.channel == 'False Colors'): colors_name += "_false_colors"
        elif(self.channel == 'Value'):  colors_name += "_value"
        elif(self.channel == 'Red'):  colors_name += "_red"
        elif(self.channel == 'Green'):  colors_name += "_green"
        elif(self.channel == 'Blue'):  colors_name += "_blue"
        bpy.context.object.data.vertex_colors[colors_id].name = colors_name

        v_colors = obj.data.vertex_colors.active.data

        mult = 1
        if(self.invert): mult = -1

        i = 0
        for f in obj.data.polygons:
            for v in f.vertices:
                gr = obj.data.vertices[v].groups

                if(self.channel == 'False Colors'): v_colors[i].color = (0,0,0.5,1)
                else: v_colors[i].color = (0,0,0,1)

                for g in gr:
                    if g.group == group_id:
                        w = g.weight
                        if(self.channel == 'False Colors'):
                            mult = 0.6+0.4*w
                            if w < 0.25:
                                v_colors[i].color = (0, w*4*mult, 1*mult,1)
                            elif w < 0.5:
                                v_colors[i].color = (0, 1*mult, (1-(w-0.25)*4)*mult,1)
                            elif w < 0.75:
                                v_colors[i].color = ((w-0.5)*4*mult,1*mult,0,1)
                            else:
                                v_colors[i].color = (1*mult,(1-(w-0.75)*4)*mult,0,1)
                        elif(self.channel == 'Value'):
                            v_colors[i].color = (
                                self.invert + mult * w,
                                self.invert + mult * w,
                                self.invert + mult * w,
                                1)
                        elif(self.channel == 'Red'):
                            v_colors[i].color = (
                                self.invert + mult * w,0,0,1)
                        elif(self.channel == 'Green'):
                            v_colors[i].color = (
                                0, self.invert + mult * w,0,1)
                        elif(self.channel == 'Blue'):
                            v_colors[i].color = (
                                0,0, self.invert + mult * w,1)
                i+=1
        bpy.ops.paint.vertex_paint_toggle()
        bpy.context.object.data.vertex_colors[colors_id].active_render = True
        return {'FINISHED'}

class curvature_to_vertex_groups(bpy.types.Operator):
    bl_idname = "object.curvature_to_vertex_groups"
    bl_label = "Curvature"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Generate a Vertex Group based on the curvature of the"
                      "mesh. Is based on Dirty Vertex Color.")

    invert : bpy.props.BoolProperty(
        name="invert", default=False, description="invert values")

    blur_strength : bpy.props.FloatProperty(
      name="Blur Strength", default=1, min=0.001,
      max=1, description="Blur strength per iteration")

    blur_iterations : bpy.props.IntProperty(
      name="Blur Iterations", default=1, min=0,
      max=40, description="Number of times to blur the values")

    min_angle : bpy.props.FloatProperty(
      name="Min Angle", default=0, min=0,
      max=pi/2, subtype='ANGLE', description="Minimum angle")

    max_angle : bpy.props.FloatProperty(
      name="Max Angle", default=pi, min=pi/2,
      max=pi, subtype='ANGLE', description="Maximum angle")

    invert : bpy.props.BoolProperty(
        name="Invert", default=False,
        description="Invert the curvature map")

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.mesh.vertex_color_add()
        vertex_colors = bpy.context.active_object.data.vertex_colors
        vertex_colors[-1].active = True
        vertex_colors[-1].active_render = True
        vertex_colors[-1].name = "Curvature"
        for c in vertex_colors[-1].data: c.color = (1,1,1,1)
        bpy.ops.object.mode_set(mode='VERTEX_PAINT')
        bpy.ops.paint.vertex_color_dirt(
            blur_strength=self.blur_strength,
            blur_iterations=self.blur_iterations, clean_angle=self.max_angle,
            dirt_angle=self.min_angle)
        bpy.ops.object.vertex_colors_to_vertex_groups(invert=self.invert)
        bpy.ops.mesh.vertex_color_remove()
        return {'FINISHED'}


class face_area_to_vertex_groups(bpy.types.Operator):
    bl_idname = "object.face_area_to_vertex_groups"
    bl_label = "Area"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Generate a Vertex Group based on the area of individual"
                      "faces.")

    invert : bpy.props.BoolProperty(
        name="invert", default=False, description="invert values")
    bounds : bpy.props.EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('AUTOMATIC', "Automatic Bounds", "")),
        default='AUTOMATIC', name="Bounds")

    min_area : bpy.props.FloatProperty(
        name="Min", default=0.01, soft_min=0, soft_max=1,
        description="Faces with 0 weight")

    max_area : bpy.props.FloatProperty(
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


class harmonic_weight(bpy.types.Operator):
    bl_idname = "object.harmonic_weight"
    bl_label = "Harmonic"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Create an harmonic variation of the active Vertex Group")

    freq : bpy.props.FloatProperty(
        name="Frequency", default=20, soft_min=0,
        soft_max=100, description="Wave frequency")

    amp : bpy.props.FloatProperty(
        name="Amplitude", default=1, soft_min=0,
        soft_max=10, description="Wave amplitude")

    midlevel : bpy.props.FloatProperty(
        name="Midlevel", default=0, min=-1,
        max=1, description="Midlevel")

    add : bpy.props.FloatProperty(
        name="Add", default=0, min=-1,
        max=1, description="Add to the Weight")

    mult : bpy.props.FloatProperty(
        name="Multiply", default=0, min=0,
        max=1, description="Multiply for he Weight")

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        ob = bpy.context.active_object
        if len(ob.vertex_groups) > 0:
            group_id = ob.vertex_groups.active_index
            ob.vertex_groups.new(name="Harmonic")
            for i in range(len(ob.data.vertices)):
                try: val = ob.vertex_groups[group_id].weight(i)
                except: val = 0
                weight = self.amp*(sin(val*self.freq) - self.midlevel)/2 + 0.5 + self.add*val*(1-(1-val)*self.mult)
                ob.vertex_groups[-1].add([i], weight, 'REPLACE')
            ob.data.update()
        else:
            self.report({'ERROR'}, "Active object doesn't have vertex groups")
            return {'CANCELLED'}
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}



class TISSUE_PT_color(bpy.types.Panel):
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

class TISSUE_PT_weight(bpy.types.Panel):
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
        try: col.operator("object.weight_formula", icon="CON_TRANSFORM")
        except: col.operator("object.weight_formula")#, icon="CON_TRANSFORM")
        #col.label(text="Weight Processing:")
        col.separator()

        # TO BE FIXED
        #col.operator("object.weight_laplacian", icon="SMOOTHCURVE")

        col.operator("object.harmonic_weight", icon="IPO_ELASTIC")
        col.operator("object.vertex_group_to_vertex_colors", icon="GROUP_VCOL",
            text="Convert to Colors")
        col.separator()
        col.label(text="Deformation Analysis:")
        col.operator("object.edges_deformation", icon="DRIVER_DISTANCE")#FULLSCREEN_ENTER")
        col.operator("object.edges_bending", icon="DRIVER_ROTATIONAL_DIFFERENCE")#"MOD_SIMPLEDEFORM")
        col.separator()
        col.label(text="Weight Contour:")
        col.operator("object.weight_contour_curves", icon="MOD_CURVE")
        col.operator("object.weight_contour_displace", icon="MOD_DISPLACE")
        col.operator("object.weight_contour_mask", icon="MOD_MASK")
        col.separator()
        col.label(text="Simulations:")
        #col.operator("object.reaction_diffusion", icon="MOD_OCEAN")
        col.operator("object.start_reaction_diffusion",
                    icon="EXPERIMENTAL",
                    text="Reaction-Diffusion")

        #col.prop(context.object, "reaction_diffusion_run", icon="PLAY", text="Run Simulation")
        ####col.prop(context.object, "reaction_diffusion_run")
        #col.separator()
        #col.label(text="Vertex Color from:")
        #col.operator("object.vertex_group_to_vertex_colors", icon="GROUP_VERTEX")




class start_reaction_diffusion(bpy.types.Operator):
    bl_idname = "object.start_reaction_diffusion"
    bl_label = "Start Reaction Diffusion"
    bl_description = ("Run a Reaction-Diffusion based on existing Vertex Groups: A and B")
    bl_options = {'REGISTER', 'UNDO'}

    run : bpy.props.BoolProperty(
        name="Run Reaction-Diffusion", default=True, description="Compute a new iteration on frame changes")

    time_steps : bpy.props.IntProperty(
        name="Steps", default=10, min=0, soft_max=50,
        description="Number of Steps")

    dt : bpy.props.FloatProperty(
        name="dt", default=1, min=0, soft_max=0.2,
        description="Time Step")

    diff_a : bpy.props.FloatProperty(
        name="Diff A", default=0.18, min=0, soft_max=2,
        description="Diffusion A")

    diff_b : bpy.props.FloatProperty(
        name="Diff B", default=0.09, min=0, soft_max=2,
        description="Diffusion B")

    f : bpy.props.FloatProperty(
        name="f", default=0.055, min=0, soft_max=0.5, precision=4,
        description="Feed Rate")

    k : bpy.props.FloatProperty(
        name="k", default=0.062, min=0, soft_max=0.5, precision=4,
        description="Kill Rate")

    @classmethod
    def poll(cls, context):
        return context.object.type == 'MESH'

    def execute(self, context):
        reaction_diffusion_add_handler(self, context)
        set_animatable_fix_handler(self, context)

        ob = context.object

        ob.reaction_diffusion_settings.run = self.run
        ob.reaction_diffusion_settings.dt = self.dt
        ob.reaction_diffusion_settings.time_steps = self.time_steps
        ob.reaction_diffusion_settings.f = self.f
        ob.reaction_diffusion_settings.k = self.k
        ob.reaction_diffusion_settings.diff_a = self.diff_a
        ob.reaction_diffusion_settings.diff_b = self.diff_b


        # check vertex group A
        try:
            vg = ob.vertex_groups['A']
        except:
            ob.vertex_groups.new(name='A')
        # check vertex group B
        try:
            vg = ob.vertex_groups['B']
        except:
            ob.vertex_groups.new(name='B')

        for v in ob.data.vertices:
            ob.vertex_groups['A'].add([v.index], 1, 'REPLACE')
            ob.vertex_groups['B'].add([v.index], 0, 'REPLACE')

        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

        return {'FINISHED'}

class reset_reaction_diffusion_weight(bpy.types.Operator):
    bl_idname = "object.reset_reaction_diffusion_weight"
    bl_label = "Reset Reaction Diffusion Weight"
    bl_description = ("Set A and B weight to default values")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object.type == 'MESH'

    def execute(self, context):
        reaction_diffusion_add_handler(self, context)
        set_animatable_fix_handler(self, context)

        ob = context.object

        # check vertex group A
        try:
            vg = ob.vertex_groups['A']
        except:
            ob.vertex_groups.new(name='A')
        # check vertex group B
        try:
            vg = ob.vertex_groups['B']
        except:
            ob.vertex_groups.new(name='B')

        for v in ob.data.vertices:
            ob.vertex_groups['A'].add([v.index], 1, 'REPLACE')
            ob.vertex_groups['B'].add([v.index], 0, 'REPLACE')

        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

        return {'FINISHED'}

from bpy.app.handlers import persistent

@persistent
def reaction_diffusion_def_blur(scene):
    for ob in scene.objects:
        if ob.reaction_diffusion_settings.run:
            #try:
            me = ob.data
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.edges.ensure_lookup_table()

            # store weight values
            a = []
            b = []
            for v in me.vertices:
                try:
                    a.append(ob.vertex_groups["A"].weight(v.index))
                except:
                    a.append(0)
                try:
                    b.append(ob.vertex_groups["B"].weight(v.index))
                except:
                    b.append(0)

            a = array(a)
            b = array(b)
            props = ob.reaction_diffusion_settings
            dt = props.dt
            time_steps = props.time_steps
            f = props.f
            k = props.k
            diff_a = props.diff_a * props.diff_mult
            diff_b = props.diff_b * props.diff_mult

            n_verts = len(bm.verts)
            #bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            #ob.data.use_paint_mask_vertex = True

            for i in range(time_steps):
                ab2 = a*b**2
                ob.vertex_groups.active = ob.vertex_groups['A']
                bpy.ops.object.vertex_group_smooth(group_select_mode='ACTIVE', factor=diff_a)
                ob.vertex_groups.active = ob.vertex_groups['B']
                bpy.ops.object.vertex_group_smooth(group_select_mode='ACTIVE', factor=diff_b)

                a = []
                b = []
                for v in me.vertices:
                    a.append(ob.vertex_groups["A"].weight(v.index))
                    b.append(ob.vertex_groups["B"].weight(v.index))
                a = array(a)
                b = array(b)

                a += - (ab2 + f*(1-a))*dt
                b += (ab2 - (k+f)*b)*dt

            a = nan_to_num(a)
            b = nan_to_num(b)

            for i in range(n_verts):
                ob.vertex_groups['A'].add([i], a[i], 'REPLACE')
                ob.vertex_groups['B'].add([i], b[i], 'REPLACE')
            ob.vertex_groups.update()
            ob.data.update()
            #bpy.ops.object.mode_set(mode='EDIT')
            #bpy.ops.object.mode_set(mode='WEIGHT_PAINT
            #bpy.ops.paint.weight_paint_toggle()
            #bpy.ops.paint.weight_paint_toggle()

            #bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            #except:
            #    pass

def reaction_diffusion_def_(scene):
    for ob in scene.objects:
        if ob.reaction_diffusion_settings.run:
            #try:
            me = ob.data
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.edges.ensure_lookup_table()

            # store weight values
            a = []
            b = []
            for v in me.vertices:
                try:
                    a.append(ob.vertex_groups["A"].weight(v.index))
                except:
                    a.append(0)
                try:
                    b.append(ob.vertex_groups["B"].weight(v.index))
                except:
                    b.append(0)

            a = array(a)
            b = array(b)
            props = ob.reaction_diffusion_settings
            dt = props.dt
            time_steps = props.time_steps
            f = props.f
            k = props.k
            diff_a = props.diff_a * props.diff_mult
            diff_b = props.diff_b * props.diff_mult

            n_verts = len(bm.verts)
            for i in range(time_steps):
                lap_a = zeros((n_verts))#[0]*n_verts
                lap_b = zeros((n_verts))#[0]*n_verts
                if i == 0:
                    lap_map = [[] for i in range(n_verts)]
                    lap_mult = []
                    for e in bm.edges:
                        id0 = e.verts[0].index
                        id1 = e.verts[1].index
                        lap_map[id0].append(id1)
                        lap_map[id1].append(id0)
                    for id in range(n_verts):
                         lap_mult.append(len(lap_map[id]))
                    lap_mult = array(lap_mult)
                    lap_map = array(lap_map)
                for id in range(n_verts):
                    map = lap_map[id]
                    lap_a[id] = a[lap_map[id]].sum()
                    lap_b[id] = b[lap_map[id]].sum()
                lap_a -= a*lap_mult
                lap_b -= b*lap_mult
                ab2 = a*b**2

                a += (diff_a*lap_a - ab2 + f*(1-a))*dt
                b += (diff_b*lap_b + ab2 - (k+f)*b)*dt

            a = nan_to_num(a)
            b = nan_to_num(b)

            for i in range(n_verts):
                ob.vertex_groups['A'].add([i], a[i], 'REPLACE')
                ob.vertex_groups['B'].add([i], b[i], 'REPLACE')
            ob.vertex_groups.update()
            ob.data.update()
            #bpy.ops.object.mode_set(mode='EDIT')
            #bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            bpy.ops.paint.weight_paint_toggle()
            bpy.ops.paint.weight_paint_toggle()

            #bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            #except:
            #    pass

def reaction_diffusion_def(scene):
    for ob in scene.objects:
        if ob.reaction_diffusion_settings.run:

            start = time.time()

            me = ob.data
            n_edges = len(me.edges)
            n_verts = len(me.vertices)

            # store weight values
            a = np.zeros(n_verts)
            b = np.zeros(n_verts)
            #a = thread_read_weight(a, ob.vertex_groups["A"])
            #b = thread_read_weight(b, ob.vertex_groups["B"])
            #a = read_weight(a, ob.vertex_groups["A"])
            #b = read_weight(b, ob.vertex_groups["B"])

            for i in range(n_verts):
                try: a[i] = ob.vertex_groups["A"].weight(i)
                except: pass
                try: b[i] = ob.vertex_groups["B"].weight(i)
                except: pass

            props = ob.reaction_diffusion_settings
            dt = props.dt
            time_steps = props.time_steps
            f = props.f
            k = props.k
            diff_a = props.diff_a * props.diff_mult
            diff_b = props.diff_b * props.diff_mult

            edge_verts = [0]*n_edges*2
            me.edges.foreach_get("vertices", edge_verts)

            timeElapsed = time.time() - start
            print('RD - Preparation Time:',timeElapsed)
            start = time.time()

            try:
                edge_verts = np.array(edge_verts)
                a, b = numba_reaction_diffusion(n_verts, n_edges, edge_verts, a, b, diff_a, diff_b, f, k, dt, time_steps)
                a = nan_to_num(a)
                b = nan_to_num(b)
            except:
                edge_verts = np.array(edge_verts)
                arr = np.arange(n_edges)*2
                id0 = edge_verts[arr]     # first vertex indices for each edge
                id1 = edge_verts[arr+1]   # second vertex indices for each edge
                for i in range(time_steps):
                    lap_a = np.zeros(n_verts)
                    lap_b = np.zeros(n_verts)
                    lap_a0 =  a[id1] -  a[id0]   # laplacian increment for first vertex of each edge
                    lap_b0 =  b[id1] -  b[id0]   # laplacian increment for first vertex of each edge

                    for i, j, la0, lb0 in np.nditer([id0,id1,lap_a0,lap_b0]):
                        lap_a[i] += la0
                        lap_b[i] += lb0
                        lap_a[j] -= la0
                        lap_b[j] -= lb0
                    ab2 = a*b**2
                    a += eval("(diff_a*lap_a - ab2 + f*(1-a))*dt")
                    b += eval("(diff_b*lap_b + ab2 - (k+f)*b)*dt")
                    #a += (diff_a*lap_a - ab2 + f*(1-a))*dt
                    #b += (diff_b*lap_b + ab2 - (k+f)*b)*dt

                    a = nan_to_num(a)
                    b = nan_to_num(b)

            timeElapsed = time.time() - start
            print('RD - Simulation Time:',timeElapsed)
            start = time.time()

            for i in range(n_verts):
                ob.vertex_groups['A'].add([i], a[i], 'REPLACE')
                ob.vertex_groups['B'].add([i], b[i], 'REPLACE')

            for ps in ob.particle_systems:
                if ps.vertex_group_density == 'B' or ps.vertex_group_density == 'A':
                    ps.invert_vertex_group_density = not ps.invert_vertex_group_density
                    ps.invert_vertex_group_density = not ps.invert_vertex_group_density

            timeElapsed = time.time() - start
            print('RD - Closing Time:',timeElapsed)

class TISSUE_PT_reaction_diffusion(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_label = "Tissue - Reaction-Diffusion"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return 'A' and 'B' in context.object.vertex_groups

    def draw(self, context):
        reaction_diffusion_add_handler(self, context)

        ob = context.object
        props = ob.reaction_diffusion_settings
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        if not ("A" and "B" in ob.vertex_groups):
            row.operator("object.start_reaction_diffusion",
                        icon="EXPERIMENTAL",
                        text="Reaction-Diffusion")
        else:
            row.operator("object.start_reaction_diffusion",
                        icon="EXPERIMENTAL",
                        text="Reset Reaction-Diffusion")
            row = col.row(align=True)
            row.prop(props, "run", text="Run Reaction-Diffusion")
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(props, "time_steps")
            row.prop(props, "dt")
            col.separator()
            row = col.row(align=True)
            row.prop(props, "diff_a")
            row.prop(props, "diff_b")
            row = col.row(align=True)
            row.prop(props, "diff_mult")
            #col.separator()
            row = col.row(align=True)
            row.prop(props, "f")
            row.prop(props, "k")
