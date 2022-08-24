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
try: from .numba_functions import run_tex_rd, run_tex_rd_ani
except: pass
#from .numba_functions import integrate_field
#from .numba_functions import numba_reaction_diffusion
try: import numexpr as ne
except: pass

# Reaction-Diffusion cache
from pathlib import Path
import random as rnd
import string

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


def tex_reaction_diffusion_add_handler(self, context):
    # remove existing handlers
    tex_reaction_diffusion_remove_handler(self, context)
    # add new handler
    bpy.app.handlers.frame_change_post.append(tex_rd_scene)


def tex_reaction_diffusion_remove_handler(self, context):
    # remove existing handlers
    old_handlers = []
    for h in bpy.app.handlers.frame_change_post:
        if "tex_rd" in str(h):
            old_handlers.append(h)
    for h in old_handlers: bpy.app.handlers.frame_change_post.remove(h)


class tex_reaction_diffusion_prop(PropertyGroup):
    run : BoolProperty(default=False, update = tex_reaction_diffusion_add_handler,
        description='Compute a new iteration on frame changes. Currently is not working during  Render Animation')

    res_x : IntProperty(
        name="Resolution X", default=512, min=2, soft_max=1000,
        description="Resolution of the simulation")

    res_y : IntProperty(
        name="Resolution Y", default=512, min=2, soft_max=1000,
        description="Resolution of the simulation")

    time_steps : IntProperty(
        name="Steps", default=10, min=0, soft_max=50,
        description="Number of Steps")

    dt : FloatProperty(
        name="dt", default=1, min=0, soft_max=0.2,
        description="Time Step")

    diff_a : FloatProperty(
        name="Diff A", default=0.14, min=0, soft_max=2, precision=3,
        description="Diffusion A")

    diff_b : FloatProperty(
        name="Diff B", default=0.07, min=0, soft_max=2, precision=3,
        description="Diffusion B")

    f : FloatProperty(
        name="f", default=0.055, soft_min=0.01, soft_max=0.06, precision=4, step=0.05,
        description="Feed Rate")

    k : FloatProperty(
        name="k", default=0.062, soft_min=0.035, soft_max=0.065, precision=4, step=0.05,
        description="Kill Rate")

    diff_mult : FloatProperty(
        name="Scale", default=1, min=0, soft_max=1, max=10, precision=2,
        description="Multiplier for the diffusion of both substances")

    anisotropy : FloatProperty(
        name="Anisotropy", default=0.5, min=0, max=1, precision=2,
        description="Influence of the Vector Field")

    img_vector_field : StringProperty(
        name="Vector Field", default='',
        description="Image used for the Vector Field. RGB to XY")

    img_a : StringProperty(
        name="A", default='',
        description="Image used for the chemical A")

    img_b : StringProperty(
        name="B", default='',
        description="Image used for the chemical B")

    img_diff_a : StringProperty(
        name="Diff A", default='',
        description="Image used for A diffusion")

    img_diff_b : StringProperty(
        name="Diff B", default='',
        description="Image used for B diffusion")

    img_scale : StringProperty(
        name="Scale", default='',
        description="Image used for Scale value")

    img_f : StringProperty(
        name="f", default='',
        description="Image used for Feed value (f)")

    img_k : StringProperty(
        name="k", default='',
        description="Image used for Kill value (k)")

    img_brush : StringProperty(
        name="Brush", default='',
        description="Image used for adding/removing B")

    invert_img_diff_a : BoolProperty(default=False,
        description='Invert the value of the Vertex Group Diff A')

    invert_img_diff_b : BoolProperty(default=False,
        description='Invert the value of the Vertex Group Diff B')

    invert_img_scale : BoolProperty(default=False,
        description='Invert the value of the Vertex Group Scale')

    invert_img_f : BoolProperty(default=False,
        description='Invert the value of the Vertex Group f')

    invert_img_k : BoolProperty(default=False,
        description='Invert the value of the Vertex Group k')

    invert_img_vector_field : BoolProperty(default=False,
        description='Use the perpendicular direction')

    min_diff_a : FloatProperty(
        name="Min Diff A", default=0.1, min=0, soft_max=2, precision=3,
        description="Min Diff A")

    max_diff_a : FloatProperty(
        name="Max Diff A", default=0.1, min=0, soft_max=2, precision=3,
        description="Max Diff A")

    min_diff_b : FloatProperty(
        name="Min Diff B", default=0.1, min=0, soft_max=2, precision=3,
        description="Min Diff B")

    max_diff_b : FloatProperty(
        name="Max Diff B", default=0.1, min=0, soft_max=2, precision=3,
        description="Max Diff B")

    min_scale : FloatProperty(
        name="Scale", default=0.35, min=0, soft_max=1, max=10, precision=2,
        description="Min Scale Value")

    max_scale : FloatProperty(
        name="Scale", default=1, min=0, soft_max=1, max=10, precision=2,
        description="Max Scale value")

    min_f : FloatProperty(
        name="Min f", default=0.02, min=0, soft_min=0.01, soft_max=0.06, max=0.2, precision=4, step=0.05,
        description="Min Feed Rate")

    max_f : FloatProperty(
        name="Max f", default=0.055, min=0, soft_min=0.01, soft_max=0.06, max=0.2, precision=4, step=0.05,
        description="Max Feed Rate")

    min_k : FloatProperty(
        name="Min k", default=0.035, min=0, soft_min=0.035, soft_max=0.065, max=0.2, precision=4, step=0.05,
        description="Min Kill Rate")

    max_k : FloatProperty(
        name="Max k", default=0.062, min=0, soft_min=0.035, soft_max=0.065, max=0.2, precision=4, step=0.05,
        description="Max Kill Rate")

    brush_mult : FloatProperty(
        name="Mult", default=0.5, min=-1, max=1, precision=3, step=0.05,
        description="Multiplier for brush value")

    bool_cache : BoolProperty(
        name="Use Cache", default=False,
        description="Read modifiers affect the vertex groups")

    cache_frame_start : IntProperty(
        name="Start", default=1,
        description="Frame on which the simulation starts")

    cache_frame_end : IntProperty(
        name="End", default=250,
        description="Frame on which the simulation ends")

    cache_dir : StringProperty(
        name="Cache directory", default="", subtype='FILE_PATH',
        description = 'Directory that contains Reaction-Diffusion cache files'
        )

    normalize : BoolProperty(
        name="Normalize values", default=False,
        description="Normalize values from 0 to 1")

def tex_rd_scene(scene, bake=False):
    for ob in bpy.context.scene.objects:
        if ob.tex_reaction_diffusion_settings.run:
            tex_reaction_diffusion_def(ob)

def tex_reaction_diffusion_def(ob, bake=False):
    try:
        props = ob.tex_reaction_diffusion_settings
    except:
        return
    scene = bpy.context.scene
    print("Texture Reaction Diffusion: " + str(scene.frame_current))
    start_time = timeit.default_timer()
    img_a = bpy.data.images[props.img_a]
    img_b = bpy.data.images[props.img_b]
    diff_a = props.diff_a
    diff_b = props.diff_b
    diff_a_min = props.min_diff_a
    diff_a_max = props.max_diff_a
    diff_b_min = props.min_diff_b
    diff_b_max = props.max_diff_b
    f_min = props.min_f
    f_max = props.max_f
    k_min = props.min_k
    k_max = props.max_k
    ani = props.anisotropy
    dt = props.dt
    time_steps = props.time_steps
    res_x = props.res_x #int(img_b.size[0])
    res_y = props.res_y #int(img_b.size[1])

    min_scale = props.min_scale
    max_scale = props.max_scale

    images = bpy.data.images.keys()
    rd_images = [img_a, img_b]
    img_diff_a = None
    img_diff_b = None
    img_vector_field = None
    img_f = None
    img_k = None
    img_scale = None
    img_brush = None
    if props.img_vector_field in images:
        img_vector_field = bpy.data.images[props.img_vector_field]
        rd_images.append(img_vector_field)
    if props.img_diff_a in images:
        img_diff_a = bpy.data.images[props.img_diff_a]
        rd_images.append(img_diff_a)
    if props.img_diff_b in images:
        img_diff_b = bpy.data.images[props.img_diff_b]
        rd_images.append(img_diff_b)
    if props.img_f in images:
        img_f = bpy.data.images[props.img_f]
        rd_images.append(img_f)
    if props.img_k in images:
        img_k = bpy.data.images[props.img_k]
        rd_images.append(img_k)
    if props.img_scale in images:
        img_scale = bpy.data.images[props.img_scale]
        rd_images.append(img_scale)
    if props.img_brush in images:
        img_brush = bpy.data.images[props.img_brush]
        rd_images.append(img_brush)
    for im in rd_images:
        im.scale(res_x ,res_y)
        im.pixels.update()
    nx = res_y
    ny = res_x

    a_px = np.float32(np.zeros(nx*ny*4))
    img_a.pixels.foreach_get(a_px)
    b_px = np.float32(np.zeros(nx*ny*4))
    img_b.pixels.foreach_get(b_px)
    if img_vector_field:
        vf_px = np.float32(np.zeros(nx*ny*4))
        img_vector_field.pixels.foreach_get(vf_px)
        vf_px = np.array(vf_px).reshape((-1,4))
        vf_x = vf_px[:,1]*2-1
        vf_x = vf_x.reshape((nx,ny))
        vf_y = vf_px[:,0]*2-1
        vf_y = vf_y.reshape((nx,ny))

        # original field
        vf_x_ = sqrt(2)/2*vf_x
        vf_y_ = sqrt(2)/2*vf_y
        vf_xy1_ = abs(vf_x_ + vf_y_)
        vf_xy2_ = abs(vf_x_ - vf_y_)
        vf_xy1 = (vf_xy1_*ani + (1-ani))*sqrt(2)/2
        vf_xy2 = (vf_xy2_*ani + (1-ani))*sqrt(2)/2
        vf_x_ = abs(vf_x)*ani + (1-ani)
        vf_y_ = abs(vf_y)*ani + (1-ani)
        vf1 = np.concatenate((vf_x_[np.newaxis,:,:], vf_y_[np.newaxis,:,:], vf_xy1[np.newaxis,:,:], vf_xy2[np.newaxis,:,:]), axis=0)

        # perpendicular field
        vf_x, vf_y = -vf_y, vf_x
        vf_x_ = sqrt(2)/2*vf_x
        vf_y_ = sqrt(2)/2*vf_y
        vf_xy1_ = abs(vf_x_ + vf_y_)
        vf_xy2_ = abs(vf_x_ - vf_y_)
        vf_xy1 = (vf_xy1_*ani + (1-ani))*sqrt(2)/2
        vf_xy2 = (vf_xy2_*ani + (1-ani))*sqrt(2)/2
        vf_x = abs(vf_x)*ani + (1-ani)
        vf_y = abs(vf_y)*ani + (1-ani)
        vf2 = np.concatenate((vf_x[np.newaxis,:,:], vf_y[np.newaxis,:,:], vf_xy1[np.newaxis,:,:], vf_xy2[np.newaxis,:,:]), axis=0)
        if props.invert_img_vector_field:
            vf1, vf2 = vf2, vf1
    else:
        vf = np.ones((1,nx,ny))
        vf_diag = np.ones((1,nx,ny))*sqrt(2)/2
        vf1 = np.concatenate((vf, vf, vf_diag, vf_diag), axis=0)
        vf2 = vf1


    if img_diff_a:
        diff_a = np_remap_image_values(img_diff_a, channel=0, min=diff_a_min, max=diff_a_max, invert=props.invert_img_diff_a)
    else:
        diff_a = np.ones((nx,ny))*props.diff_a

    if img_diff_b:
        diff_b = np_remap_image_values(img_diff_b, channel=0, min=diff_b_min, max=diff_b_max, invert=props.invert_img_diff_b)
    else:
        diff_b = np.ones((nx,ny))*props.diff_b

    if img_scale:
        scale = np_remap_image_values(img_scale, channel=0, min=min_scale, max=max_scale, invert=props.invert_img_scale)
        diff_a *= scale
        diff_b *= scale
    else:
        diff_a *= props.diff_mult
        diff_b *= props.diff_mult

    if img_f:
        f = np_remap_image_values(img_f, channel=0, min=f_min, max=f_max, invert=props.invert_img_f)
    else:
        f = np.ones((nx,ny))*props.f

    if img_k:
        k = np_remap_image_values(img_k, channel=0, min=k_min, max=k_max, invert=props.invert_img_k)
    else:
        k = np.ones((nx,ny))*props.k

    if img_brush:
        brush = np_remap_image_values(img_brush)*props.brush_mult
    else:
        brush = np.zeros((nx,ny))

    print("Load images: " + str(timeit.default_timer() - start_time) + " sec")

    start_time = timeit.default_timer()

    a_px = np.array(a_px).reshape((-1,4))
    a = a_px[:,0]
    a = a.reshape((nx,ny))
    lap_a = np.zeros((nx,ny))

    b_px = np.array(b_px).reshape((-1,4))
    b = b_px[:,0]
    b = b.reshape((nx,ny))
    lap_b = np.zeros((nx,ny))

    print("Reshape data time: " + str(timeit.default_timer() - start_time) + " sec")

    start_time = timeit.default_timer()
    run_tex_rd_ani(a, b, lap_a, lap_b, diff_a, diff_b, f, k, dt, time_steps, vf1, vf2, brush)
    print("Simulation time: " + str(timeit.default_timer() - start_time) + " sec")

    start_time = timeit.default_timer()
    np.clip(a,0,1,out=a)
    np.clip(b,0,1,out=b)
    a = a.flatten()
    b = b.flatten()
    a_px[:,0] = a
    a_px[:,1] = a
    a_px[:,2] = a
    b_px[:,0] = b
    b_px[:,1] = b
    b_px[:,2] = b
    img_a.pixels.foreach_set(np.float32(a_px.flatten()))
    img_b.pixels.foreach_set(np.float32(b_px.flatten()))
    img_a.pixels.update()
    img_b.pixels.update()
    img_a.update()
    img_b.update()
    print("Stored Images: " + str(timeit.default_timer() - start_time) + " sec")

class reset_tex_reaction_diffusion(Operator):
    bl_idname = "object.reset_tex_reaction_diffusion"
    bl_label = "Reset Texture Reaction Diffusion"
    bl_description = ("Run a Reaction-Diffusion based on images: A and B")
    bl_options = {'REGISTER', 'UNDO'}

    run : BoolProperty(
        name="Run Reaction-Diffusion", default=True, description="Compute a new iteration on frame changes")

    time_steps : IntProperty(
        name="Steps", default=10, min=0, soft_max=50,
        description="Number of Steps")

    dt : FloatProperty(
        name="dt", default=1, min=0, soft_max=0.2,
        description="Time Step")

    diff_a : FloatProperty(
        name="Diff A", default=0.14, min=0, soft_max=2,
        description="Diffusion A")

    diff_b : FloatProperty(
        name="Diff B", default=0.07, min=0, soft_max=2,
        description="Diffusion B")

    f : FloatProperty(
        name="f", default=0.055, min=0, soft_min=0.01, soft_max=0.06, max=0.1, precision=4,
        description="Feed Rate")

    k : FloatProperty(
        name="k", default=0.062, min=0, soft_min=0.035, soft_max=0.065, max=0.1, precision=4,
        description="Kill Rate")

    def execute(self, context):
        props = context.object.tex_reaction_diffusion_settings
        props.dt = self.dt
        props.time_steps = self.time_steps
        props.f = self.f
        props.k = self.k
        props.diff_a = self.diff_a
        props.diff_b = self.diff_b
        res_x = props.res_x
        res_y = props.res_y
        img_a = bpy.data.images[props.img_a]
        img_b = bpy.data.images[props.img_b]
        img_a.scale(width=res_x, height=res_y)
        img_b.scale(width=res_x, height=res_y)
        img_a.pixels.foreach_set([1]*res_x*res_y*4)
        img_b.pixels.foreach_set([0,0,0,1]*res_x*res_y)
        img_a.pixels.update()
        img_b.pixels.update()
        img_a.update()
        img_b.update()

        return {'FINISHED'}

class start_tex_reaction_diffusion(Operator):
    bl_idname = "object.start_tex_reaction_diffusion"
    bl_label = "Start Texture Reaction Diffusion"
    bl_description = ("Run a Reaction-Diffusion based on images: A and B")
    bl_options = {'REGISTER', 'UNDO'}

    #res_x : IntProperty(
    #    name="Resolution X", default=512, min=2, soft_max=1000,
    #    description="Resolution of the simulation")
    #res_y : IntProperty(
    #    name="Resolution Y", default=512, min=2, soft_max=1000,
    #    description="Resolution of the simulation")

    @classmethod
    def poll(cls, context):
        return True

    #def invoke(self, context, event):
    #    return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        tex_reaction_diffusion_add_handler(self, context)
        set_animatable_fix_handler(self, context)

        ob = context.object
        props = ob.tex_reaction_diffusion_settings
        if props.img_a in bpy.data.images.keys():
            img_a = bpy.data.images[props.img_a]
            img_a.scale(props.res_x, props.res_y)
        else:
            img_a = bpy.data.images.new(name="A", width=props.res_x, height=props.res_y)
        if props.img_b in bpy.data.images.keys():
            img_b = bpy.data.images[props.img_b]
            img_b.scale(props.res_x, props.res_y)
        else:
            img_b = bpy.data.images.new(name="B", width=props.res_x, height=props.res_y)
        props.run = True
        #props.res_x = self.res_x
        #props.res_y = self.res_y
        props.img_a = img_a.name
        props.img_b = img_b.name

        #props.run = self.run
        #props.dt = self.dt
        #props.time_steps = self.time_steps
        #props.f = self.f
        #props.k = self.k
        #props.diff_a = self.diff_a
        #props.diff_b = self.diff_b

        return {'FINISHED'}


class TISSUE_PT_tex_reaction_diffusion(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_label = "Tissue Texture Reaction-Diffusion"
    bl_options = {'DEFAULT_CLOSED'}

    #@classmethod
    #def poll(cls, context):
    #    return True

    def draw(self, context):
        tex_reaction_diffusion_add_handler(self, context)
        ob = bpy.context.object
        props = ob.tex_reaction_diffusion_settings
        img_a = props.img_a
        img_b = props.img_b
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        if not (img_a and img_b in bpy.data.images):
            row.operator("object.start_tex_reaction_diffusion",
                        icon="EXPERIMENTAL")
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(props, 'res_x')
            row.prop(props, 'res_y')
            col.separator()
            col.prop_search(props, 'img_a', bpy.data, "images")
            col.prop_search(props, 'img_b', bpy.data, "images")
        else:
            row.operator("object.reset_tex_reaction_diffusion",
                        icon="EXPERIMENTAL")
            row = col.row(align=True)
            row.prop(props, "run", text="Run Reaction-Diffusion")
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(props, 'res_x')
            row.prop(props, 'res_y')
            col.separator()
            col.prop_search(props, 'img_a', bpy.data, "images")
            col.prop_search(props, 'img_b', bpy.data, "images")
            col.separator()
            row = col.row(align=True)
            row.prop(props, "time_steps")
            row.prop(props, "dt")
            row.enabled = not props.bool_cache
            col.separator()
            row = col.row(align=True)
            col1 = row.column(align=True)
            col1.prop(props, "diff_a")
            col1.enabled = props.img_diff_a == '' and not props.bool_cache
            col1 = row.column(align=True)
            col1.prop(props, "diff_b")
            col1.enabled = props.img_diff_b == '' and not props.bool_cache
            row = col.row(align=True)
            row.prop(props, "diff_mult")
            row.enabled = props.img_scale == '' and not props.bool_cache
            #col.separator()
            row = col.row(align=True)
            col1 = row.column(align=True)
            col1.prop(props, "f")
            col1.enabled = props.img_f == '' and not props.bool_cache
            col1 = row.column(align=True)
            col1.prop(props, "k")
            col1.enabled = props.img_k == '' and not props.bool_cache
            '''
            col.separator()
            col.label(text='Cache:')
            #col.prop(props, "bool_cache")
            col.prop(props, "cache_dir", text='')
            col.separator()
            row = col.row(align=True)
            row.prop(props, "cache_frame_start")
            row.prop(props, "cache_frame_end")
            col.separator()
            if props.bool_cache:
                col.operator("object.reaction_diffusion_free_data")
            else:
                row = col.row(align=True)
                row.operator("object.bake_reaction_diffusion")
                file = bpy.context.blend_data.filepath
                temp = bpy.context.preferences.filepaths.temporary_directory
                if file == temp == props.cache_dir == '':
                    row.enabled = False
                    col.label(text="Cannot use cache", icon='ERROR')
                    col.label(text='please save the Blender or set a Cache directory')
            '''

class TISSUE_PT_tex_reaction_diffusion_images(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_parent_id = "TISSUE_PT_tex_reaction_diffusion"
    bl_label = "Image Maps"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        props = context.object.tex_reaction_diffusion_settings
        if props.img_a and props.img_b in bpy.data.images.keys():
            return True
        else:
            return False

    def draw(self, context):
        ob = context.object
        props = ob.tex_reaction_diffusion_settings
        layout = self.layout
        #layout.use_property_split = True
        col = layout.column(align=True)
        insert_image_parameter(col, ob, 'brush', text='Brush:')
        insert_image_parameter(col, ob, 'diff_a', text='Diff A:')
        insert_image_parameter(col, ob, 'diff_b', text='Diff B:')
        insert_image_parameter(col, ob, 'scale', text='Scale:')
        insert_image_parameter(col, ob, 'f', text='f:')
        insert_image_parameter(col, ob, 'k', text='k:')
        insert_image_parameter(col, ob, 'vector_field', text='Vector Field:')
        col.enabled = not props.bool_cache

def insert_image_parameter(col, ob, name, text=''):
    props = ob.tex_reaction_diffusion_settings
    split = col.split(factor=0.25, align=True)
    col2 = split.column(align=True)
    col2.label(text=text)
    col2 = split.column(align=True)
    row2 = col2.row(align=True)
    row2.prop_search(props, 'img_' + name, bpy.data, "images", text='')
    if name not in ('brush'):
        if name == 'vector_field': icon = 'DRIVER_ROTATIONAL_DIFFERENCE'#'ORIENTATION_VIEW'
        else: icon = 'ARROW_LEFTRIGHT'
        row2.prop(props, "invert_img_" + name, text="", toggle=True, icon=icon)
    if 'img_' + name in props:
        if props['img_' + name] != '':
            if name == 'brush':
                col2.prop(props, "brush_mult")
            elif name == 'vector_field':
                col2.prop(props, "anisotropy")
            else:
                row2 = col2.row(align=True)
                row2.prop(props, "min_" + name, text="Min")
                row2 = col2.row(align=True)
                row2.prop(props, "max_" + name, text="Max")
    col.separator()
