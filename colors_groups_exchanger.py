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
import math, timeit
from math import *#pi, sin
from statistics import mean
from numpy import *

bl_info = {
    "name": "Colors/Groups Exchanger",
    "author": "Alessandro Zomparelli (Co-de-iT)",
    "version": (0, 3),
    "blender": (2, 7, 9),
    "location": "",
    "description": ("Convert vertex colors channels to vertex groups and vertex"
                    " groups to colors"),
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Mesh"}


class weight_formula(bpy.types.Operator):
    bl_idname = "object.weight_formula"
    bl_label = "Weight Formula"
    bl_options = {'REGISTER', 'UNDO'}

    ex = [
        #'cos(arctan(nx/ny)*6 + sin(rz*30)*0.5)/2 + cos(arctan(nx/ny)*6 - sin(rz*30)*0.5 + pi/2)/2 + 0.5',
        'cos(arctan(nx/ny)*6 + sin(rz*30))/4 + cos(arctan(nx/ny)*6 - sin(rz*30))/4 + 0.5',
        'cos(arctan(nx/ny)*6 + sin(rz*30))/2 + cos(arctan(nx/ny)*6 - sin(rz*30))/2',
        '(sin(arctan(nx/ny)*8)*sin(nz*8)+1)/2',
        'cos(arctan(nx/ny)*6)',
        'cos(arctan(lx/ly)*6 + sin(rz*30)*2)',
        'sin(nx*15)<sin(ny*15)',
        'cos(ny*rz**2*30)',
        'sin(rx*30) > 0',
        'sin(nz*15)',
        'w[0]**2',
        'sqrt((rx-0.5)**2 + (ry-0.5)**2)*2',
        'abs(0.5-rz)*2'
        'rx'
        ]
    ex_items = list((s,s,"") for s in ex)
    ex_items.append(('CUSTOM', "User Formula", ""))
    examples = bpy.props.EnumProperty(
        items = ex_items, default='CUSTOM', name="Examples")

    _formula = ""

    formula = bpy.props.StringProperty(
        name="Formula", default="", description="Formula to Evaluate")
    bl_description = ("Generate a Vertex Group based on the given formula")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "examples")
        if self.examples == 'CUSTOM':
            layout.prop(self, "formula", text="Formula")
        layout.separator()
        layout.label(text="Variables (for each vertex):")#, icon='INFO')
        layout.label(text="lx, ly, lz: Local Coordinates", icon='OBJECT_DATA')#'MANIPUL')
        layout.label(text="gx, gy, gz: Global Coordinates", icon='WORLD')
        layout.label(text="rx, ry, rz: Local Coordinates (0 to 1)", icon='BBOX')
        layout.label(text="nx, ny, nz: Normal Coordinates", icon='SNAP_NORMAL')
        layout.label(text="w[0], w[1], w[2], ... : Vertex Groups", icon="GROUP_VERTEX")
        layout.separator()
        layout.label(text="All mathematical functions are based on Numpy", icon='INFO')
        #layout.label(text="https://docs.scipy.org/doc/numpy-1.13.0/reference/routines.math.html", icon='INFO')
        #layout.label(text="w[i]: Existing Vertex Groups", icon="GROUP_VERTEX")
        #layout.label(text="(where 'i' is the index of the Vertex Group)")

    def execute(self, context):
        ob = bpy.context.active_object
        if self.examples == 'CUSTOM':
            formula = self.formula
        else:
            self.formula = self.examples
            formula = self.examples

        if formula == "": return {'FINISHED'}
        vertex_group_name = "Formula " + formula
        ob.vertex_groups.new(name=vertex_group_name)

        verts = ob.data.vertices
        n_verts = len(verts)
        do_groups = "w[" in formula
        do_local = "lx" in formula or "ly" in formula or "lz" in formula
        do_global = "gx" in formula or "gy" in formula or "gz" in formula
        do_relative = "rx" in formula or "ry" in formula or "rz" in formula
        do_normal = "nx" in formula or "ny" in formula or "nz" in formula
        mat = ob.matrix_world

        for i in range(1000):
            if "w["+str(i)+"]" in formula and i > len(ob.vertex_groups)-1:
                self.report({'ERROR'}, "w["+str(i)+"] not found" )
                return {'FINISHED'}

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
        #print("time: " + str(timeit.default_timer() - start_time))

        #start_time = timeit.default_timer()
        try:
            weight = eval(formula)
        except:
            self.report({'ERROR'}, "There is something wrong" )
            return {'FINISHED'}

        #print("time: " + str(timeit.default_timer() - start_time))

        #start_time = timeit.default_timer()
        for i in range(n_verts):
            ob.vertex_groups[-1].add([i], weight[i], 'REPLACE')
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        print("Weight Formula: " + str(timeit.default_timer() - start_time))

        return {'FINISHED'}

class weight_laplacian(bpy.types.Operator):
    bl_idname = "object.weight_laplacian"
    bl_label = "Weight Laplacian"
    bl_description = ("Compute the Vertex Group Laplacian")
    bl_options = {'REGISTER', 'UNDO'}

    bounds = bpy.props.EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('COMPRESSION', "Compressed Only", ""),
            ('TENSION', "Extended Only", ""),
            ('AUTOMATIC', "Automatic Bounds", "")),
        default='AUTOMATIC', name="Bounds")

    mode = bpy.props.EnumProperty(
        items=(('LENGTH', "Length Weight", ""),
            ('SIMPLE', "Simple", "")),
        default='SIMPLE', name="Evaluation Mode")

    min_def = bpy.props.FloatProperty(
        name="Min", default=0, soft_min=-1, soft_max=0,
        description="Deformations with 0 weight")

    max_def = bpy.props.FloatProperty(
        name="Max", default=0.5, soft_min=0, soft_max=5,
        description="Deformations with 1 weight")

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
        print(input_group)

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
        print(len(lap))
        print(len(weight))
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

        if self.bounds == 'MANUAL':
            min_def = self.min_def
            max_def = self.max_def
        elif self.bounds == 'AUTOMATIC':
            min_def = min(lap)
            max_def = max(lap)
            self.min_def = min_def
            self.max_def = max_def
        elif self.bounds == 'COMPRESSION':
            min_def = 0
            max_def = min(lap)
            self.min_def = min_def
            self.max_def = max_def
        elif self.bounds == 'TENSION':
            min_def = 0
            max_def = max(lap)
            self.min_def = min_def
            self.max_def = max_def
        delta_def = max_def - min_def

        # check undeformed errors
        if delta_def == 0: delta_def = 0.0001

        for i in range(len(lap)):
            val = (lap[i]-min_def)/delta_def
            ob.vertex_groups[-1].add([i], val, 'REPLACE')
        self.bounds_string = str(round(min_def,2)) + " to " + str(round(max_def,2))
        ob.vertex_groups[-1].name = group_name + " " + self.bounds_string
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}

class edges_deformation(bpy.types.Operator):
    bl_idname = "object.edges_deformation"
    bl_label = "Edges Deformation"
    bl_description = ("Compute Weight based on the deformation of edges"+
        "according to visible modifiers.")
    bl_options = {'REGISTER', 'UNDO'}

    bounds = bpy.props.EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('COMPRESSION', "Compressed Only", ""),
            ('TENSION', "Extended Only", ""),
            ('AUTOMATIC', "Automatic Bounds", "")),
        default='AUTOMATIC', name="Bounds")

    mode = bpy.props.EnumProperty(
        items=(('MAX', "Max Deformation", ""),
            ('MEAN', "Average Deformation", "")),
        default='MEAN', name="Evaluation Mode")

    min_def = bpy.props.FloatProperty(
        name="Min", default=0, soft_min=-1, soft_max=0,
        description="Deformations with 0 weight")

    max_def = bpy.props.FloatProperty(
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
        me = ob.to_mesh(bpy.context.scene, apply_modifiers=True,
                settings='PREVIEW')
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
        return {'FINISHED'}

class edges_bending(bpy.types.Operator):
    bl_idname = "object.edges_bending"
    bl_label = "Edges Bending"
    bl_description = ("Compute Weight based on the bending of edges"+
        "according to visible modifiers.")
    bl_options = {'REGISTER', 'UNDO'}

    bounds = bpy.props.EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('POSITIVE', "Positive Only", ""),
            ('NEGATIVE', "Negative Only", ""),
            ('UNSIGNED', "Absolute Bending", ""),
            ('AUTOMATIC', "Signed Bending", "")),
        default='AUTOMATIC', name="Bounds")

    min_def = bpy.props.FloatProperty(
        name="Min", default=-10, soft_min=-45, soft_max=45,
        description="Deformations with 0 weight")

    max_def = bpy.props.FloatProperty(
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
        me = ob.to_mesh(bpy.context.scene, apply_modifiers=True,
                settings='PREVIEW')
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
        print(v_deformations)
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
        return {'FINISHED'}

class weight_contour_mask(bpy.types.Operator):
    bl_idname = "object.weight_contour_mask"
    bl_label = "Contour Mask"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers = bpy.props.BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")
    iso = bpy.props.FloatProperty(
        name="Iso Value", default=0.5, soft_min=0, soft_max=1,
        description="Threshold value")
    bool_mask = bpy.props.BoolProperty(
        name="Mask", default=True, description="Trim along isovalue")

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
            me0 = ob0.to_mesh(bpy.context.scene, apply_modifiers=True,
                settings='PREVIEW')
        else:
            me0 = ob0.data

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
        print("selected faces:" + str(len(faces_mask)))

        #link_faces = [[f for f in e.link_faces] for e in bm.edges]

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
            #id0 = e.vertices[0]
            #id1 = e.vertices[1]
            id0 = e.verts[0].index
            id1 = e.verts[1].index
            w0 = weight[id0]
            w1 = weight[id1]

            #edges_id.append(str(id0)+"_"+str(id1))
            #edges_id[str(id0)+"_"+str(id1)] = e.index
            #edges_id[str(id1)+"_"+str(id0)] = e.index

            if w0 == w1: continue
            elif w0 > iso_val and w1 > iso_val:
                #_filtered_edges.append(e)
                continue
            elif w0 < iso_val and w1 < iso_val: continue
            elif w0 == iso_val or w1 == iso_val: continue
            else:
                #v0 = me0.vertices[id0].select = True
                #v1 = me0.vertices[id1].select = True
                v0 = me0.vertices[id0].co
                v1 = me0.vertices[id1].co
                v = v0.lerp(v1, (iso_val-w0)/(w1-w0))
                delete_edges.append(e)
                verts.append(v)
                edges_id[str(id0)+"_"+str(id1)] = count
                edges_id[str(id1)+"_"+str(id0)] = count
                count += 1
            #_filtered_edges.append(e)
        #filtered_edges = _filtered_edges
        print("creating faces")
        del_faces = []
        splitted_faces = []
        #count = 0
        print("new vertices: " + str(len(verts)))
        todo = 0
        for i in faces_todo: todo += i
        print("faces to split: " + str(todo))

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
            del_faces.append(f.index)

        print("generate new bmesh")
        # adding new vertices
        for v in verts: bm.verts.new(v)
        bm.verts.ensure_lookup_table()

        # deleting old edges/faces
        bm.edges.ensure_lookup_table()
        remove_edges = []
        #for i in delete_edges: remove_edges.append(bm.edges[i])
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
        print("missed " + str(len(missed_faces)) + " faces")


        if(self.bool_mask or True):
            all_weight = weight + [iso_val+0.0001]*len(verts)
            weight = []
            for w, v in zip(all_weight, bm.verts):
                if w < iso_val: bm.verts.remove(v)
                else: weight.append(w)
            #count = 0
            #remove_verts = []
            #for w in weight:
            #    if w < iso_val: remove_verts.append(bm.verts[count])
            #    count += 1
            #for v in remove_verts: bm.verts.remove(v)
        # Create mesh and object
        print("creating curve")
        name = ob0.name + '_Isocurves_{:.3f}'.format(iso_val)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        ob = bpy.data.objects.new(name, me)

        # Link object to scene and make active
        scn = bpy.context.scene
        scn.objects.link(ob)
        scn.objects.active = ob
        ob.select = True
        ob0.select = False

        '''
        # Create mesh from given verts, faces.
        #me.from_pydata(verts, edges, [])
        me.from_pydata(new_verts,[],new_faces)
        me.validate(verbose=False)
        # Update mesh with new data
        me.update()
        '''

        # generate new vertex group
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)
        #ob.vertex_groups.new(name=vertex_group_name)

        print("doing weight")
        all_weight = weight + [iso_val]*len(verts)
        mult = 1/(1-iso_val)
        for id in range(len(all_weight)):
            w = (all_weight[id]-iso_val)*mult
            ob.vertex_groups[vertex_group_name].add([id], w, 'REPLACE')
        print("weight done")
        #for id in range(len(weight), len(ob.data.vertices)):
        #    ob.vertex_groups[vertex_group_name].add([id], iso_val*0, 'ADD')


        ob.vertex_groups.active_index = group_id

        # align new object
        ob.matrix_world = ob0.matrix_world

        # mask
        if self.bool_mask and True:
            #ob.modifiers.new(type='VERTEX_WEIGHT_EDIT', name='Threshold')
            #ob.modifiers['Threshold'].vertex_group = vertex_group_name
            #ob.modifiers['Threshold'].use_remove = True
            #ob.modifiers['Threshold'].remove_threshold = iso_val
            #ob.modifiers.new(type='MASK', name='Mask')
            #ob.modifiers['Mask'].vertex_group = vertex_group_name
            ob.modifiers.new(type='SOLIDIFY', name='Solidify')
            ob.modifiers['Solidify'].thickness = 0.05
            ob.modifiers['Solidify'].offset = 0
            ob.modifiers['Solidify'].vertex_group = vertex_group_name

        #bpy.ops.paint.weight_paint_toggle()
        #bpy.context.space_data.viewport_shade = 'WIREFRAME'
        ob.data.update()
        print("time: " + str(timeit.default_timer() - start_time))

        return {'FINISHED'}

class weight_contour_curves(bpy.types.Operator):
    bl_idname = "object.weight_contour_curves"
    bl_label = "Contour Curves"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers = bpy.props.BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")

    min_iso = bpy.props.FloatProperty(
        name="Min Value", default=0., soft_min=0, soft_max=1,
        description="Minimum weight value")
    max_iso = bpy.props.FloatProperty(
        name="Max Value", default=1, soft_min=0, soft_max=1,
        description="Maximum weight value")
    n_curves = bpy.props.IntProperty(
        name="Curves", default=3, soft_min=1, soft_max=10,
        description="Number of Contorur Curves")

    min_rad = bpy.props.FloatProperty(
        name="Min Radius", default=0.25, soft_min=0, soft_max=1,
        description="Minimum Curve Radius")
    max_rad = bpy.props.FloatProperty(
        name="Max Radius", default=0.75, soft_min=0, soft_max=1,
        description="Maximum Curve Radius")

    @classmethod
    def poll(cls, context):
        ob = context.object
        return len(ob.vertex_groups) > 0 or ob.type == 'CURVE'

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
            me0 = ob0.to_mesh(bpy.context.scene, apply_modifiers=True,
                settings='PREVIEW')
        else:
            me0 = ob0.data

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
            try:
                iso_val = c*(self.max_iso-self.min_iso)/(self.n_curves-1)+self.min_iso
                if iso_val < 0: iso_val = (self.min_iso + self.max_iso)/2
            except:
                iso_val = (self.min_iso + self.max_iso)/2
            print(iso_val)
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

        print("generate new bmesh")
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
            print("creating curve")
            name = ob0.name + '_Isocurves_{:.3f}'.format(iso_val)
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me)
            ob = bpy.data.objects.new(name, me)

            # Link object to scene and make active
            scn = bpy.context.scene
            scn.objects.link(ob)
            scn.objects.active = ob
            ob.select = True
            ob0.select = False

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



        '''
        # Create mesh from given verts, faces.
        #me.from_pydata(verts, edges, [])
        me.from_pydata(new_verts,[],new_faces)
        me.validate(verbose=False)
        # Update mesh with new data
        me.update()
        '''

        # align new object
        ob.matrix_world = ob0.matrix_world
        print("time: " + str(timeit.default_timer() - start_time))

        return {'FINISHED'}

class vertex_colors_to_vertex_groups(bpy.types.Operator):
    bl_idname = "object.vertex_colors_to_vertex_groups"
    bl_label = "Vertex Color"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Convert the active Vertex Color into a Vertex Group.")

    red = bpy.props.BoolProperty(
        name="red channel", default=False, description="convert red channel")
    green = bpy.props.BoolProperty(
        name="green channel", default=False,
        description="convert green channel")
    blue = bpy.props.BoolProperty(
        name="blue channel", default=False, description="convert blue channel")
    value = bpy.props.BoolProperty(
        name="value channel", default=True, description="convert value channel")
    invert = bpy.props.BoolProperty(
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
                        self.invert + mult * v_colors[i].color.r
                    if(self.green): gr[min(len(gr)-sub_green, id_green)].weight\
                        = self.invert + mult * v_colors[i].color.g
                    if(self.blue): gr[min(len(gr)-sub_blue, id_blue)].weight = \
                        self.invert + mult * v_colors[i].color.b
                    if(self.value): gr[min(len(gr)-sub_value, id_value)].weight\
                        = self.invert + mult * v_colors[i].color.v
                    i+=1
            bpy.ops.paint.weight_paint_toggle()
        return {'FINISHED'}


class vertex_group_to_vertex_colors(bpy.types.Operator):
    bl_idname = "object.vertex_group_to_vertex_colors"
    bl_label = "Vertex Group"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Convert the active Vertex Group into a Vertex Color.")

    channel = bpy.props.EnumProperty(
        items=[('Blue', 'Blue Channel', 'Convert to Blue Channel'),
               ('Green', 'Green Channel', 'Convert to Green Channel'),
               ('Red', 'Red Channel', 'Convert to Red Channel'),
               ('Value', 'Value Channel', 'Convert to Grayscale'),
               ('False Colors', 'False Colors', 'Convert to False Colors')],
        name="Convert to", description="Choose how to convert vertex group",
        default="Value", options={'LIBRARY_EDITABLE'})

    invert = bpy.props.BoolProperty(
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

                if(self.channel == 'False Colors'): v_colors[i].color = (0,0,1)
                else: v_colors[i].color = (0,0,0)

                for g in gr:
                    if g.group == group_id:
                        if(self.channel == 'False Colors'):
                            if g.weight < 0.25:
                                v_colors[i].color = (0, g.weight*4, 1)
                            elif g.weight < 0.5:
                                v_colors[i].color = (0, 1, 1-(g.weight-0.25)*4)
                            elif g.weight < 0.75:
                                v_colors[i].color = ((g.weight-0.5)*4,1,0)
                            else:
                                v_colors[i].color = (1,1-(g.weight-0.75)*4,0)
                        elif(self.channel == 'Value'):
                            v_colors[i].color = (
                                self.invert + mult * g.weight,
                                self.invert + mult * g.weight,
                                self.invert + mult * g.weight)
                        elif(self.channel == 'Red'):
                            v_colors[i].color = (
                                self.invert + mult * g.weight,0,0)
                        elif(self.channel == 'Green'):
                            v_colors[i].color = (
                                0, self.invert + mult * g.weight,0)
                        elif(self.channel == 'Blue'):
                            v_colors[i].color = (
                                0,0, self.invert + mult * g.weight)
                i+=1
        bpy.ops.paint.vertex_paint_toggle()
        bpy.context.object.data.vertex_colors[colors_id].active_render = True
        return {'FINISHED'}

class curvature_to_vertex_groups(bpy.types.Operator):
    bl_idname = "object.curvature_to_vertex_groups"
    bl_label = "Curvature"
    bl_options = {'REGISTER', 'UNDO'}
    invert = bpy.props.BoolProperty(
        name="invert", default=False, description="invert values")
    bl_description = ("Generate a Vertex Group based on the curvature of the"
                      "mesh. Is based on Dirty Vertex Color.")

    blur_strength = bpy.props.FloatProperty(
      name="Blur Strength", default=1, min=0.001,
      max=1, description="Blur strength per iteration")

    blur_iterations = bpy.props.IntProperty(
      name="Blur Iterations", default=1, min=0,
      max=40, description="Number of times to blur the values")

    min_angle = bpy.props.FloatProperty(
      name="Min Angle", default=0, min=0,
      max=pi/2, subtype='ANGLE', description="Minimum angle")

    max_angle = bpy.props.FloatProperty(
      name="Max Angle", default=pi, min=pi/2,
      max=pi, subtype='ANGLE', description="Maximum angle")

    invert = bpy.props.BoolProperty(
        name="Invert", default=False,
        description="Invert the curvature map")

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.mesh.vertex_color_add()
        vertex_colors = bpy.context.active_object.data.vertex_colors
        vertex_colors[-1].active = True
        vertex_colors[-1].active_render = True
        vertex_colors[-1].name = "Curvature"
        for c in vertex_colors[-1].data: c.color.r, c.color.g, c.color.b = 1,1,1
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
    invert = bpy.props.BoolProperty(
        name="invert", default=False, description="invert values")
    bl_description = ("Generate a Vertex Group based on the area of individual"
                      "faces.")

    bounds = bpy.props.EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('AUTOMATIC', "Automatic Bounds", "")),
        default='AUTOMATIC', name="Bounds")

    min_area = bpy.props.FloatProperty(
        name="Min", default=0.01, soft_min=0, soft_max=1,
        description="Faces with 0 weight")

    max_area = bpy.props.FloatProperty(
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
        print(areas)
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
        print(min_area)
        print(max_area)
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

    freq = bpy.props.FloatProperty(
        name="Frequency", default=20, soft_min=0,
        soft_max=100, description="Wave frequency")

    amp = bpy.props.FloatProperty(
        name="Amplitude", default=1, soft_min=0,
        soft_max=10, description="Wave amplitude")

    midlevel = bpy.props.FloatProperty(
        name="Midlevel", default=0, min=-1,
        max=1, description="Midlevel")

    add = bpy.props.FloatProperty(
        name="Add", default=0, min=-1,
        max=1, description="Add to the Weight")

    mult = bpy.props.FloatProperty(
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



class color_panel(bpy.types.Panel):
    bl_label = "Tissue Tools"
    bl_category = "Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_options = {'DEFAULT_CLOSED'}
    bl_context = "vertexpaint"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("object.vertex_colors_to_vertex_groups",
            icon="GROUP_VERTEX", text="Convert to Weight")

class weight_panel(bpy.types.Panel):
    bl_label = "Tissue Tools"
    bl_category = "Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_options = {'DEFAULT_CLOSED'}
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
        col.operator("object.face_area_to_vertex_groups", icon="SNAP_FACE")
        col.operator("object.curvature_to_vertex_groups", icon="SMOOTHCURVE")
        col.operator("object.weight_formula", icon="OUTLINER_DATA_FONT")
        #col.label(text="Weight Processing:")
        col.separator()
        col.operator("object.weight_laplacian", icon="SMOOTHCURVE")
        col.operator("object.harmonic_weight", icon="IPO_ELASTIC")
        col.operator("object.vertex_group_to_vertex_colors", icon="GROUP_VCOL",
            text="Convert to Colors")
        col.separator()
        col.label(text="Deformation Analysis:")
        col.operator("object.edges_deformation", icon="FULLSCREEN_ENTER")
        col.operator("object.edges_bending", icon="MOD_SIMPLEDEFORM")
        col.separator()
        col.label(text="Weight Contour:")
        col.operator("object.weight_contour_curves", icon="MOD_CURVE")
        col.operator("object.weight_contour_mask", icon="MOD_MASK")
        #col.separator()
        #col.label(text="Vertex Color from:")
        #col.operator("object.vertex_group_to_vertex_colors", icon="GROUP_VERTEX")


def register():
    bpy.utils.register_class(vertex_colors_to_vertex_groups)
    bpy.utils.register_class(vertex_group_to_vertex_colors)
    bpy.utils.register_class(face_area_to_vertex_groups)
    bpy.utils.register_class(weight_panel)
    bpy.utils.register_class(color_panel)
    bpy.utils.register_class(weight_contour_curves)
    bpy.utils.register_class(weight_contour_mask)
    bpy.utils.register_class(harmonic_weight)
    bpy.utils.register_class(edges_deformation)
    bpy.utils.register_class(edges_bending)
    bpy.utils.register_class(weight_laplacian)


def unregister():
    bpy.utils.unregister_class(vertex_colors_to_vertex_groups)
    bpy.utils.unregister_class(vertex_group_to_vertex_colors)
    bpy.utils.unregister_class(face_area_to_vertex_groups)
    bpy.utils.unregister_class(weight_panel)
    bpy.utils.unregister_class(color_panel)
    bpy.utils.unregister_class(harmonic_weight)
    bpy.utils.unregister_class(weight_contour_curves)
    bpy.utils.unregister_class(weight_contour_mask)
    bpy.utils.unregister_class(edges_deformation)
    bpy.utils.unregister_class(edges_bending)
    bpy.utils.unregister_class(weight_laplacian)


if __name__ == "__main__":
    register()
