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
try: from .numba_functions import numba_reaction_diffusion, numba_reaction_diffusion_anisotropic, integrate_field
except: pass
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
    IntVectorProperty,
    PointerProperty
)

from .utils import *

def force_geometry_data_update(self, context):
    ob = context.object
    props = ob.reaction_diffusion_settings
    if props.input_mode == 'STATIC':
        props.update_geometry_data =  True

def reaction_diffusion_add_handler(self, context):
    # remove existing handlers
    reaction_diffusion_remove_handler(self, context)
    # add new handler
    bpy.app.handlers.frame_change_post.append(reaction_diffusion_scene)

def reaction_diffusion_remove_handler(self, context):
    # remove existing handlers
    old_handlers = []
    for h in bpy.app.handlers.frame_change_post:
        if "reaction_diffusion" in str(h):
            old_handlers.append(h)
    for h in old_handlers: bpy.app.handlers.frame_change_post.remove(h)

class start_reaction_diffusion(Operator):
    bl_idname = "object.start_reaction_diffusion"
    bl_label = "Start Reaction Diffusion"
    bl_description = ("Run a Reaction-Diffusion based on existing Vertex Groups: A and B")
    bl_options = {'REGISTER', 'UNDO'}

    run : BoolProperty(
        name="Run Reaction-Diffusion", default=True, description="Compute a new iteration on frame changes")

    time_steps : IntProperty(
        name="Steps", default=10, min=0, soft_max=50,
        description="Number of Steps")

    dt : FloatProperty(
        name="dt", default=0.5, min=0, soft_max=1,
        description="Time Step")

    diff_a : FloatProperty(
        name="Diff A", default=0.18, min=0, soft_max=2,
        description="Diffusion A")

    diff_b : FloatProperty(
        name="Diff B", default=0.09, min=0, soft_max=2,
        description="Diffusion B")

    f : FloatProperty(
        name="f", default=0.055, min=0, soft_min=0.01, soft_max=0.06, max=0.1, precision=4,
        description="Feed Rate")

    k : FloatProperty(
        name="k", default=0.062, min=0, soft_min=0.035, soft_max=0.065, max=0.1, precision=4,
        description="Kill Rate")

    @classmethod
    def poll(cls, context):
        return context.object.type == 'MESH' and context.mode != 'EDIT_MESH'

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

class reset_reaction_diffusion_weight(Operator):
    bl_idname = "object.reset_reaction_diffusion_weight"
    bl_label = "Reset Reaction Diffusion Weight"
    bl_description = ("Set A and B weight to default values")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object.type == 'MESH' and context.mode != 'EDIT_MESH'

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

class reaction_diffusion_prop(PropertyGroup):
    run : BoolProperty(default=False, update = reaction_diffusion_add_handler,
        description='Compute a new iteration on frame changes. Currently is not working during  Render Animation')

    time_steps : IntProperty(
        name="Steps", default=10, min=0, soft_max=50,
        description="Number of Steps"
        )

    dt : FloatProperty(
        name="dt", default=0.5, min=0, soft_max=1,
        description="Time Step"
        )

    diff_a : FloatProperty(
        name="Diff A", default=0.1, min=0, soft_max=2, precision=3,
        description="Diffusion A"
        )

    diff_b : FloatProperty(
        name="Diff B", default=0.05, min=0, soft_max=2, precision=3,
        description="Diffusion B"
        )

    f : FloatProperty(
        name="f", default=0.055, soft_min=0.01, soft_max=0.06, precision=4,
        step=0.05, description="Feed Rate"
        )

    k : FloatProperty(
        name="k", default=0.062, soft_min=0.035, soft_max=0.065, precision=4,
        step=0.05, description="Kill Rate"
        )

    diff_mult : FloatProperty(
        name="Scale", default=1, min=0, soft_max=1, max=10, precision=2,
        description="Multiplier for the diffusion of both substances"
        )

    vertex_group_diff_a : StringProperty(
        name="Diff A", default='',
        description="Vertex Group used for A diffusion"
        )

    vertex_group_diff_b : StringProperty(
        name="Diff B", default='',
        description="Vertex Group used for B diffusion"
        )

    vertex_group_scale : StringProperty(
        name="Scale", default='',
        description="Vertex Group used for Scale value"
        )

    vertex_group_f : StringProperty(
        name="f", default='',
        description="Vertex Group used for Feed value (f)"
        )

    vertex_group_k : StringProperty(
        name="k", default='',
        description="Vertex Group used for Kill value (k)"
        )

    vertex_group_brush : StringProperty(
        name="Brush", default='',
        description="Vertex Group used for adding/removing B"
        )

    invert_vertex_group_diff_a : BoolProperty(default=False,
        description='Inverte the value of the Vertex Group Diff A'
        )

    invert_vertex_group_diff_b : BoolProperty(default=False,
        description='Inverte the value of the Vertex Group Diff B'
        )

    invert_vertex_group_scale : BoolProperty(default=False,
        description='Inverte the value of the Vertex Group Scale'
        )

    invert_vertex_group_f : BoolProperty(default=False,
        description='Inverte the value of the Vertex Group f'
        )

    invert_vertex_group_k : BoolProperty(default=False,
        description='Inverte the value of the Vertex Group k'
        )

    min_diff_a : FloatProperty(
        name="Min Diff A", default=0.1, min=0, soft_max=2, precision=3,
        description="Min Diff A"
        )

    max_diff_a : FloatProperty(
        name="Max Diff A", default=0.1, min=0, soft_max=2, precision=3,
        description="Max Diff A"
        )

    min_diff_b : FloatProperty(
        name="Min Diff B", default=0.1, min=0, soft_max=2, precision=3,
        description="Min Diff B"
        )

    max_diff_b : FloatProperty(
        name="Max Diff B", default=0.1, min=0, soft_max=2, precision=3,
        description="Max Diff B"
        )

    min_scale : FloatProperty(
        name="Scale", default=0.35, min=0, soft_max=1, max=10, precision=2,
        description="Min Scale Value"
        )

    max_scale : FloatProperty(
        name="Scale", default=1, min=0, soft_max=1, max=10, precision=2,
        description="Max Scale value"
        )

    min_f : FloatProperty(
        name="Min f", default=0.02, min=0, soft_min=0.01, soft_max=0.06, max=0.1, precision=4, step=0.05,
        description="Min Feed Rate"
        )

    max_f : FloatProperty(
        name="Max f", default=0.055, min=0, soft_min=0.01, soft_max=0.06, max=0.1, precision=4, step=0.05,
        description="Max Feed Rate"
        )

    min_k : FloatProperty(
        name="Min k", default=0.035, min=0, soft_min=0.035, soft_max=0.065, max=0.1, precision=4, step=0.05,
        description="Min Kill Rate"
        )

    max_k : FloatProperty(
        name="Max k", default=0.062, min=0, soft_min=0.035, soft_max=0.065, max=0.1, precision=4, step=0.05,
        description="Max Kill Rate"
        )

    brush_mult : FloatProperty(
        name="Mult", default=0.5, min=-1, max=1, precision=3, step=0.05,
        description="Multiplier for brush value"
        )

    bool_mod : BoolProperty(
        name="Use Modifiers", default=False,
        description="Read modifiers affect the vertex groups or attributes"
        )

    bool_cache : BoolProperty(
        name="Use Cache", default=False,
        description="Read modifiers affect the vertex groups"
        )

    cache_frame_start : IntProperty(
        name="Start", default=1,
        description="Frame on which the simulation starts"
        )

    cache_frame_end : IntProperty(
        name="End", default=250,
        description="Frame on which the simulation ends"
        )

    cache_dir : StringProperty(
        name="Cache directory", default="", subtype='FILE_PATH',
        description = 'Directory that contains Reaction-Diffusion cache files'
        )

    reload_at_start : BoolProperty(
        name="Reload at Start", default=True,
        description="Values from A and B are loaded from Vertex Groups or Modifiers after the first frame"
        )

    update_geometry_data : BoolProperty(
        name="Update Geometry Data", default=True,
        description="Update geometry data and vector field data at the next frame"
        )

    update_baked_geometry : BoolProperty(
        name="Update Baked Geometry", default=False,
        description="Force to update geometry data on the next iteration"
        )

    vector_field_mode : EnumProperty(
        items=(
            ('NONE', "None", "Isotropic Reaction-Diffusion"),
            ('VECTOR', "Vector", "Uniform vector"),
            ('OBJECT', "Object", "Orient the field with a target object's Z"),
            ('GRADIENT', "Gradient", "Gradient vertex group"),
            ('XYZ', "x, y, z", "Vector field defined by vertex groups 'x', 'y' and 'z'"),
            ('VECTOR_ATTRIBUTE', "Vector Field", "'RD_vector_field' attribute (Vertex > Vector)")
            ),
        default='NONE',
        name="Vector Field controlling the direction of the Reaction-Diffusion",
        update = force_geometry_data_update
        )

    anisotropy : FloatProperty(
        name="Anisotropy", default=0.5, min=0, max=1, precision=2,
        description="Influence of the Vector Field"
        )

    vector : FloatVectorProperty(
        name='Vector', description='Constant Vector', default=(0.0, 0.0, 1.0),
        update = force_geometry_data_update
        )

    perp_vector_field : BoolProperty(default=False,
        description='Use the perpendicular direction',
        update = force_geometry_data_update
        )

    vector_field_object : PointerProperty(
        type=bpy.types.Object,
        name="",
        description="Target Object",
        update = force_geometry_data_update
        )

    vertex_group_gradient : StringProperty(
        name="Gradient", default='',
        description="Vertex Group for the gradient vector field",
        update = force_geometry_data_update
        )

    input_mode : EnumProperty(
        items=(
                ('STATIC', "Static input (faster)", "Information about geometry and input values are loaded once in the first frame and then stored as attributes. This includes also the effects of modifiers on vertex groups or attributes. Geometry data and Vector Field data are stored instead in a newly mesh."),
                ('INTERACTIVE', "Interactive (slower)", "Information about geometry and input values are updated dynamically. This includes also the effects of modifiers on vertex groups or attributes.")
            ),
        default='INTERACTIVE',
        name="Input Mode",
        update = force_geometry_data_update
        )

    input_data : EnumProperty(
        items=(
                ('WEIGHT', "Vertex Groups (default)", "The fields A and B are loaded from vertex groups. If 'Input Mode' is 'Static', then the Vertex Groups are loaded only for the first frame."),
                ('ATTRIBUTES', "Attributes (faster)", "The fields A and B are loaded from the attributes 'RD_A' and 'RD_B'. If 'Input Mode' is 'Static', then this is the automatic mode for every frame except the first one.")
            ),
        default='WEIGHT',
        name="Input Data"
        )

    output_data : EnumProperty(
        items=(
            ('WEIGHT', "Vertex Groups (default)", "The fields A and B are saved as Vertex Group at evry frame."),
            ('ATTRIBUTES', "Attributes (faster)", "The fields A and B are saved as attributes 'RD_A' and 'RD_B' at every frame. If 'Input Mode' is 'Static', then this happens automatically.")
            ),
        default='WEIGHT',
        name="Output Data"
        )

    cache_mesh : StringProperty(
        name="Cache Mesh", default='',
        description="Mesh used to store data for 'Static' mode."
    )

class bake_reaction_diffusion(Operator):
    bl_idname = "object.bake_reaction_diffusion"
    bl_label = "Bake Data"
    bl_description = ("Bake the Reaction-Diffusion to the cache directory")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object.type == 'MESH' and context.mode != 'EDIT_MESH'

    def execute(self, context):
        ob = context.object
        props = ob.reaction_diffusion_settings
        frames = range(props.cache_frame_start, props.cache_frame_end) if props.input_mode == 'INTERACTIVE' else [props.cache_frame_start]
        props.run = False if props.input_mode == 'STATIC' else True
        for frame in frames:
            context.scene.frame_current = frame
            message = reaction_diffusion_def(ob, bake=True)
            if type(message) is str:
                self.report({'ERROR'}, message)
        props.bool_cache = True
        props.run = True
        context.scene.frame_current = props.cache_frame_start
        return {'FINISHED'}

class reaction_diffusion_free_data(Operator):
    bl_idname = "object.reaction_diffusion_free_data"
    bl_label = "Free Data"
    bl_description = ("Free Reaction-Diffusion data")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object.type == 'MESH'

    def execute(self, context):
        ob = context.object
        props = ob.reaction_diffusion_settings
        props.bool_cache = False

        folder = Path(props.cache_dir)
        for i in range(props.cache_frame_start, props.cache_frame_end):
            data_a = folder / "a_{:04d}".format(i)
            if os.path.exists(data_a):
                os.remove(data_a)
            data_a = folder / "b_{:04d}".format(i)
            if os.path.exists(data_a):
                os.remove(data_a)
        return {'FINISHED'}

from bpy.app.handlers import persistent

def reaction_diffusion_scene(scene, bake=False):
    tissue_time(None,'{:7d} Tissue: Reaction-Diffusion...'.format(scene.frame_current), levels=0)
    for ob in scene.objects:
        if ob.reaction_diffusion_settings.run:
            message = reaction_diffusion_def(ob)
            if type(message) is str:
                print(message)

def load_attribute_parameter(mesh, name, default, domain, data_type):
    if name in mesh.attributes:
        att = mesh.attributes[name]
        if att.domain == domain and att.data_type == data_type:
            values = np.zeros((len(att.data)))
            att.data.foreach_get('value', values)
            return values
    return default

def store_attribute_parameter(mesh, name, values, domain, data_type):
    if name not in mesh.attributes:
        mesh.attributes.new(name, data_type, domain)
    att = mesh.attributes[name]
    if att.domain == domain and att.data_type == data_type and len(values) == len(att.data):
        att.data.foreach_set('value', values)

def reaction_diffusion_def(ob, bake=False):
    scene = bpy.context.scene
    start = time.time()
    beginning = time.time()
    if type(ob) == bpy.types.Scene: return None
    props = ob.reaction_diffusion_settings

    if bake or props.bool_cache:
        if props.cache_dir == '':
            letters = string.ascii_letters
            random_name = ''.join(rnd.choice(letters) for i in range(6))
            if bpy.context.blend_data.filepath == '':
                folder = Path(bpy.context.preferences.filepaths.temporary_directory)
                folder = folder / 'reaction_diffusion_cache' / random_name
            else:
                folder = '//' + Path(bpy.context.blend_data.filepath).stem
                folder = Path(bpy.path.abspath(folder)) / 'reaction_diffusion_cache' / random_name
            folder.mkdir(parents=True, exist_ok=True)
            props.cache_dir = str(folder)
        else:
            folder = Path(props.cache_dir)

    me = ob.data
    bm = None
    n_verts = len(me.vertices)
    a = np.zeros(n_verts)
    b = np.zeros(n_verts)

    if bake and props.input_mode == 'INTERACTIVE':
        tissue_time(None,'{:7d} Tissue: Reaction-Diffusion...'.format(scene.frame_current), levels=0)
    tissue_time(None,"Running on {}...".format(ob.name),levels=0)
    is_static = props.input_mode == 'STATIC'
    if props.reload_at_start and scene.frame_current == props.cache_frame_start:
        is_static = False
    use_modifiers = props.bool_mod and not is_static

    if props.bool_cache:
        try:
            file_name = folder / "a_{:04d}".format(scene.frame_current)
            a = np.fromfile(file_name)
            file_name = folder / "b_{:04d}".format(scene.frame_current)
            b = np.fromfile(file_name)
        except:
            print('       Cannot read cache.')
            return
    else:
        if use_modifiers:
            me = rd_apply_modifiers(ob)
            if type(me) is str:
                return me

        dt = props.dt
        time_steps = props.time_steps
        f = props.f
        k = props.k
        diff_a = props.diff_a
        diff_b = props.diff_b
        scale = props.diff_mult
        brush_mult = props.brush_mult
        brush = 0

        if is_static or props.input_data == 'ATTRIBUTES':
            if not 'RD_A' in me.attributes:
                me.attributes.new('RD_A', 'FLOAT', 'POINT')
            if not 'RD_B' in me.attributes:
                me.attributes.new('RD_B', 'FLOAT', 'POINT')
            a = np.zeros((n_verts))
            b = np.zeros((n_verts))
            me.attributes['RD_A'].data.foreach_get('value', a)
            me.attributes['RD_B'].data.foreach_get('value', b)
            a = load_attribute_parameter(me, 'RD_A', np.zeros((n_verts)), 'POINT', 'FLOAT')
            b = load_attribute_parameter(me, 'RD_B', np.zeros((n_verts)), 'POINT', 'FLOAT')
            if not (props.input_data == 'WEIGHT' and not props.vertex_group_brush in ob.vertex_groups):
                brush = load_attribute_parameter(me, 'RD_brush', 0, 'POINT', 'FLOAT')
            if not (props.input_data == 'WEIGHT' and not props.vertex_group_diff_a in ob.vertex_groups):
                diff_a = load_attribute_parameter(me, 'RD_diff_a', diff_a, 'POINT', 'FLOAT')
            if not (props.input_data == 'WEIGHT' and not props.vertex_group_diff_b in ob.vertex_groups):
                diff_b = load_attribute_parameter(me, 'RD_diff_b', diff_b, 'POINT', 'FLOAT')
            if not (props.input_data == 'WEIGHT' and not props.vertex_group_scale in ob.vertex_groups):
                scale = load_attribute_parameter(me, 'RD_scale', scale, 'POINT', 'FLOAT')
            if not (props.input_data == 'WEIGHT' and not props.vertex_group_f in ob.vertex_groups):
                f = load_attribute_parameter(me, 'RD_f', f, 'POINT', 'FLOAT')
            if not (props.input_data == 'WEIGHT' and not props.vertex_group_k in ob.vertex_groups):
                k = load_attribute_parameter(me, 'RD_k', k, 'POINT', 'FLOAT')
        else:
            if props.vertex_group_diff_a != '':
                diff_a = np.zeros(n_verts)
            if props.vertex_group_diff_b != '':
                diff_b = np.zeros(n_verts)
            if props.vertex_group_scale != '':
                scale = np.zeros(n_verts)
            if props.vertex_group_f != '':
                f = np.zeros(n_verts)
            if props.vertex_group_k != '':
                k = np.zeros(n_verts)
            if props.vertex_group_brush != '':
                brush = np.zeros(n_verts)
            else: brush = 0

            bm = bmesh.new()   # create an empty BMesh
            bm.from_mesh(me)   # fill it in from a Mesh
            dvert_lay = bm.verts.layers.deform.active

            group_index_a = ob.vertex_groups["A"].index
            group_index_b = ob.vertex_groups["B"].index
            a = bmesh_get_weight_numpy(group_index_a, dvert_lay, bm.verts)
            b = bmesh_get_weight_numpy(group_index_b, dvert_lay, bm.verts)

            if props.vertex_group_diff_a != '':
                group_index = ob.vertex_groups[props.vertex_group_diff_a].index
                diff_a = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts, normalized=True)
                if props.invert_vertex_group_diff_a:
                    vg_bounds = (props.min_diff_a, props.max_diff_a)
                else:
                    vg_bounds = (props.max_diff_a, props.min_diff_a)
                diff_a = np.interp(diff_a, (0,1), vg_bounds)
                if props.input_mode == 'STATIC':
                    store_attribute_parameter(me, 'RD_diff_a', diff_a, 'POINT', 'FLOAT')

            if props.vertex_group_diff_b != '':
                group_index = ob.vertex_groups[props.vertex_group_diff_b].index
                diff_b = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts, normalized=True)
                if props.invert_vertex_group_diff_b:
                    vg_bounds = (props.max_diff_b, props.min_diff_b)
                else:
                    vg_bounds = (props.min_diff_b, props.max_diff_b)
                diff_b = np.interp(diff_b, (0,1), vg_bounds)
                if props.input_mode == 'STATIC':
                    store_attribute_parameter(me, 'RD_diff_b', diff_b, 'POINT', 'FLOAT')

            if props.vertex_group_scale != '':
                group_index = ob.vertex_groups[props.vertex_group_scale].index
                scale = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts, normalized=True)
                if props.invert_vertex_group_scale:
                    vg_bounds = (props.max_scale, props.min_scale)
                else:
                    vg_bounds = (props.min_scale, props.max_scale)
                scale = np.interp(scale, (0,1), vg_bounds)
                if props.input_mode == 'STATIC':
                    store_attribute_parameter(me, 'RD_scale', scale, 'POINT', 'FLOAT')

            if props.vertex_group_f != '':
                group_index = ob.vertex_groups[props.vertex_group_f].index
                f = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts, normalized=True)
                if props.invert_vertex_group_f:
                    vg_bounds = (props.max_f, props.min_f)
                else:
                    vg_bounds = (props.min_f, props.max_f)
                f = np.interp(f, (0,1), vg_bounds, )
                if props.input_mode == 'STATIC':
                    store_attribute_parameter(me, 'RD_f', f, 'POINT', 'FLOAT')

            if props.vertex_group_k != '':
                group_index = ob.vertex_groups[props.vertex_group_k].index
                k = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts, normalized=True)
                if props.invert_vertex_group_k:
                    vg_bounds = (props.max_k, props.min_k)
                else:
                    vg_bounds = (props.min_k, props.max_k)
                k = np.interp(k, (0,1), vg_bounds)
                if props.input_mode == 'STATIC':
                    store_attribute_parameter(me, 'RD_k', k, 'POINT', 'FLOAT')

            if props.vertex_group_brush != '':
                group_index = ob.vertex_groups[props.vertex_group_brush].index
                brush = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts, normalized=True)
                brush *= brush_mult
                if props.input_mode == 'STATIC':
                    store_attribute_parameter(me, 'RD_brush', brush, 'POINT', 'FLOAT')

        diff_a *= scale
        diff_b *= scale

        edge_verts = None
        field_mult = np.zeros((1))
        if is_static and props.cache_mesh in bpy.data.meshes and not props.update_geometry_data:
            rd_mesh = bpy.data.meshes[props.cache_mesh]
            edge_verts = get_edges_numpy_ex(rd_mesh)
            n_edges = len(edge_verts)
            if props.vector_field_mode != 'NONE' and 'RD_vector_field' in rd_mesh.attributes:
                field_mult = load_attribute_parameter(rd_mesh, 'RD_vector_field', np.ones((n_edges)), 'EDGE', 'FLOAT')
        else:
            edge_verts = get_edges_numpy_ex(me)
            n_edges = len(edge_verts)
            if props.cache_mesh in bpy.data.meshes:
                rd_mesh = bpy.data.meshes[props.cache_mesh]
                rd_mesh.clear_geometry()
            else:
                rd_mesh = bpy.data.meshes.new('RD_' + me.name)
                props.cache_mesh = rd_mesh.name
            rd_mesh.from_pydata(get_vertices_numpy(me), edge_verts, [])

            is_vector_field = True

            if props.vector_field_mode != 'NONE':
                if props.vector_field_mode == 'VECTOR':
                    vec = Vector(props.vector)
                    vector_field = [vec]*n_edges

                if props.vector_field_mode == 'OBJECT':
                    if props.vector_field_object:
                        mat = props.vector_field_object.matrix_world
                    else:
                        mat = ob.matrix_world
                    vec = Vector((mat[0][2],mat[1][2],mat[2][2]))
                    vector_field = [vec]*n_edges

                if props.vector_field_mode == 'XYZ':
                    vgk = ob.vertex_groups.keys()
                    if 'x' in vgk and 'y' in vgk and 'z' in vgk:
                        if not bm:
                            bm = bmesh.new()   # create an empty BMesh
                            bm.from_mesh(me)   # fill it in from a Mesh
                            dvert_lay = bm.verts.layers.deform.active
                        group_index = ob.vertex_groups["x"].index
                        field_x = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts)
                        group_index = ob.vertex_groups["y"].index
                        field_y = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts)
                        group_index = ob.vertex_groups["z"].index
                        field_z = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts)
                        field_x = field_x*2-1
                        field_y = field_y*2-1
                        field_z = field_z*2-1
                        vector_field = []
                        for x,y,z in zip(field_x, field_y, field_z):
                            vector_field.append(Vector((x,y,z)).normalized())
                    else:
                        is_vector_field = False

                if props.vector_field_mode == 'GRADIENT':
                    if props.vertex_group_gradient:
                        if props.vertex_group_gradient in ob.vertex_groups.keys():
                            if not bm:
                                bm = bmesh.new()   # create an empty BMesh
                                bm.from_mesh(me)   # fill it in from a Mesh
                                dvert_lay = bm.verts.layers.deform.active
                            group_index = ob.vertex_groups[props.vertex_group_gradient].index
                            weight = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts)
                            vector_field = [None]*n_verts
                            for i,v0 in enumerate(bm.verts):
                                vec = Vector((0,0,0))
                                w0 = weight[v0.index]
                                for e in v0.link_edges:
                                    v1 = e.other_vert(v0)
                                    dw = weight[v1.index]-w0
                                    vec += (v1.co-v0.co)*dw
                                vector_field[i] = vec.normalized()
                        else:
                            is_vector_field = False
                    else:
                        is_vector_field = False

                if props.vector_field_mode == 'VECTOR_ATTRIBUTE':
                    if 'RD_vector_field' in me.attributes:
                        vectors_components = [0]*n_verts*3
                        me.attributes['RD_vector_field'].data.foreach_get('vector', vectors_components)
                        vector_field = [None]*n_verts
                        for i in range(n_verts):
                            x = vectors_components[i*3]
                            y = vectors_components[i*3+1]
                            z = vectors_components[i*3+2]
                            vector_field[i] = Vector((x,y,z)).normalized()
                    else:
                        is_vector_field = False

                if is_vector_field:
                    if props.perp_vector_field:
                        for i, vert in enumerate(bm.verts):
                            vector_field[i] = vector_field[i].cross(vert.normal)
                    field_mult = [1]*n_edges
                    for i, pair in enumerate(edge_verts):
                        id0 = pair[0]
                        id1 = pair[1]
                        v0 = me.vertices[id0].co
                        v1 = me.vertices[id1].co
                        vec = (v1-v0).normalized()
                        mult0 = abs(vec.dot(vector_field[id0]))
                        mult1 = abs(vec.dot(vector_field[id1]))
                        field_mult[i] = (mult0 + mult1)/2
                    field_mult = np.array(field_mult)
                    if props.cache_mesh in bpy.data.meshes and props.input_mode == 'STATIC':
                        rd_mesh = bpy.data.meshes[props.cache_mesh]
                        store_attribute_parameter(rd_mesh, 'RD_vector_field', field_mult, 'EDGE', 'FLOAT')
            else:
                is_vector_field = False
            props.update_geometry_data = False

        edge_verts = edge_verts.reshape((-1))
        field_mult = field_mult*props.anisotropy + (1-props.anisotropy)

        tissue_time(start, "Preparation", levels=1)
        start = time.time()

        frames = range(props.cache_frame_start, props.cache_frame_end+1) if bake and props.input_mode == 'STATIC' else [scene.frame_current]
        for frame in frames:
            if bake and props.input_mode == 'STATIC':
                tissue_time(None,'{:7d} Tissue: Baking Reaction-Diffusion on {}...'.format(frame, ob.name), levels=0)
            try:
                _f = f if type(f) is np.ndarray else np.array((f,))
                _k = k if type(k) is np.ndarray else np.array((k,))
                _diff_a = diff_a if type(diff_a) is np.ndarray else np.array((diff_a,))
                _diff_a *= scale
                _diff_b = diff_b if type(diff_b) is np.ndarray else np.array((diff_b,))
                _diff_b *= scale
                _brush = brush if type(brush) is np.ndarray else np.array((brush,))
                if len(field_mult) == 1:
                    a, b = numba_reaction_diffusion(n_verts, n_edges, edge_verts, a, b, _brush, _diff_a, _diff_b, _f, _k, dt, time_steps)
                else:
                    a, b = numba_reaction_diffusion_anisotropic(n_verts, n_edges, edge_verts, a, b, _brush, _diff_a, _diff_b, _f, _k, dt, time_steps, field_mult)
            except:
                print('Not using Numba! The simulation could be slow.')
                arr = np.arange(n_edges)
                id0 = edge_verts[arr*2]     # first vertex indices for each edge
                id1 = edge_verts[arr*2+1]   # second vertex indices for each edge
                if len(field_mult) == 1: mult = 1
                else: mult = field_mult[arr]   # second vertex indices for each edge
                _diff_a = diff_a*scale
                _diff_b = diff_b*scale
                for i in range(time_steps):
                    b += brush
                    lap_a = np.zeros(n_verts)
                    lap_b = np.zeros(n_verts)
                    lap_a0 =  (a[id1] -  a[id0])*mult   # laplacian increment for first vertex of each edge
                    lap_b0 =  (b[id1] -  b[id0])*mult   # laplacian increment for first vertex of each edge

                    np.add.at(lap_a, id0, lap_a0)
                    np.add.at(lap_b, id0, lap_b0)
                    np.add.at(lap_a, id1, -lap_a0)
                    np.add.at(lap_b, id1, -lap_b0)
                    ab2 = a*b**2
                    a += eval("(_diff_a*lap_a - ab2 + f*(1-a))*dt")
                    b += eval("(_diff_b*lap_b + ab2 - (k+f)*b)*dt")

                    a = nan_to_num(a)
                    b = nan_to_num(b)
            tissue_time(start, "Simulation", levels=1)
            start = time.time()
            if bake:
                if not(os.path.exists(folder)):
                    os.mkdir(folder)
                file_name = folder / "a_{:04d}".format(frame)
                a.tofile(file_name)
                file_name = folder / "b_{:04d}".format(frame)
                b.tofile(file_name)
                if props.input_mode == 'STATIC':
                    tissue_time(start, "Baked", levels=1)
                    tissue_time(beginning, "Reaction-Diffusion on {}".format(ob.name), levels=0)

    start = time.time()
    if props.output_data == 'ATTRIBUTES':
        store_attribute_parameter(ob.data, 'RD_A', a, 'POINT', 'FLOAT')
        store_attribute_parameter(ob.data, 'RD_B', b, 'POINT', 'FLOAT')
        ob.data.update()
    else:
        if props.input_mode == 'STATIC':
            store_attribute_parameter(ob.data, 'RD_A', a, 'POINT', 'FLOAT')
            store_attribute_parameter(ob.data, 'RD_B', b, 'POINT', 'FLOAT')
            ob.data.update()
        if 'A' in ob.vertex_groups.keys():
            vg_a = ob.vertex_groups['A']
        else:
            vg_a = ob.vertex_groups.new(name='A')
        if 'B' in ob.vertex_groups.keys():
            vg_b = ob.vertex_groups['B']
        else:
            vg_b = ob.vertex_groups.new(name='B')
        if ob.mode == 'WEIGHT_PAINT':
            # slower, but prevent crashes
            for i in range(n_verts):
                if vg_a: vg_a.add([i], a[i], 'REPLACE')
                if vg_b: vg_b.add([i], b[i], 'REPLACE')
        else:
            if use_modifiers or props.bool_cache:
                #bm.free()               # release old bmesh
                bm = bmesh.new()        # create an empty BMesh
                bm.from_mesh(ob.data)   # fill it in from a Mesh
                dvert_lay = bm.verts.layers.deform.active
            # faster, but can cause crashes while painting weight
            if vg_a: index_a = vg_a.index
            if vg_b: index_b = vg_b.index
            for i, v in enumerate(bm.verts):
                dvert = v[dvert_lay]
                if vg_a: dvert[index_a] = a[i]
                if vg_b: dvert[index_b] = b[i]
            bm.to_mesh(ob.data)
            bm.free()

    for ps in ob.particle_systems:
        if ps.vertex_group_density == 'B' or ps.vertex_group_density == 'A':
            ps.invert_vertex_group_density = not ps.invert_vertex_group_density
            ps.invert_vertex_group_density = not ps.invert_vertex_group_density

    if use_modifiers and not props.bool_cache: bpy.data.meshes.remove(me)
    tissue_time(start, "Writing data", levels=1)
    tissue_time(beginning, "Reaction-Diffusion on {}".format(ob.name), levels=0)

class TISSUE_PT_reaction_diffusion(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_label = "Tissue Reaction-Diffusion"
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
            row.prop(props, "bool_mod", text="", icon='MODIFIER')
            row.prop(props, "run", text="", icon='TIME')
            col.separator()
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(props, "time_steps")
            row.prop(props, "dt")
            row.enabled = not props.bool_cache
            col.separator()
            row = col.row(align=True)
            col1 = row.column(align=True)
            col1.prop(props, "diff_a")
            col1.enabled = props.vertex_group_diff_a == '' and not props.bool_cache
            col1 = row.column(align=True)
            col1.prop(props, "diff_b")
            col1.enabled = props.vertex_group_diff_b == '' and not props.bool_cache
            row = col.row(align=True)
            row.prop(props, "diff_mult")
            row.enabled = props.vertex_group_scale == '' and not props.bool_cache
            row = col.row(align=True)
            col1 = row.column(align=True)
            col1.prop(props, "f")
            col1.enabled = props.vertex_group_f == '' and not props.bool_cache
            col1 = row.column(align=True)
            col1.prop(props, "k")
            col1.enabled = props.vertex_group_k == '' and not props.bool_cache

class TISSUE_PT_reaction_diffusion_vector_field(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_reaction_diffusion"
    bl_label = "Anisotropic"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return 'A' and 'B' in context.object.vertex_groups

    def draw(self, context):
        ob = context.object
        props = ob.reaction_diffusion_settings
        layout = self.layout
        col = layout.column(align=True)
        col.prop(props, "vector_field_mode", text="Mode")
        if props.vector_field_mode == 'OBJECT':
            col.prop_search(props, "vector_field_object", context.scene, "objects", text='Object')
        if props.vector_field_mode == 'GRADIENT':
            col.prop_search(props, 'vertex_group_gradient', ob, "vertex_groups")
        if props.vector_field_mode == 'XYZ':
            vgk = ob.vertex_groups.keys()
            if 'x' not in vgk:
                col.label(text="Vertex Group 'x' is missing", icon='ERROR')
            if 'y' not in vgk:
                col.label(text="Vertex Group 'y' is missing", icon='ERROR')
            if 'z' not in vgk:
                col.label(text="Vertex Group 'z' is missing", icon='ERROR')
        if props.vector_field_mode == 'VECTOR_ATTRIBUTE':
            vgk = ob.vertex_groups.keys()
            if 'RD_vector_field' not in ob.data.attributes:
                col.label(text="Vector Attribute 'RD_vector_field' is missing", icon='ERROR')
        if props.vector_field_mode == 'VECTOR':
            row = col.row()
            row.prop(props, "vector")
        if props.vector_field_mode != 'NONE':
            col.separator()
            row = col.row()
            row.prop(props, 'perp_vector_field', text='Perpendicular')
            row.prop(props, "anisotropy")

class TISSUE_PT_reaction_diffusion_performance(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_reaction_diffusion"
    bl_label = "Performance"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return 'A' and 'B' in context.object.vertex_groups

    def draw(self, context):
        ob = context.object
        props = ob.reaction_diffusion_settings
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(props, "input_mode", text='Mode')
        if props.input_mode == 'STATIC':
            col.separator()
            row = col.row(align=True)
            row.prop(props, "reload_at_start", icon = 'SORTTIME')
            row.prop(props, "update_geometry_data", icon ='MOD_DATA_TRANSFER')
        col.separator()
        col.prop(props, "input_data", text='Read from')
        col.prop(props, "output_data", text='Write to')
        col.separator()

class TISSUE_PT_reaction_diffusion_weight(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_reaction_diffusion"
    bl_label = "Variable Parameters"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return 'A' and 'B' in context.object.vertex_groups

    def draw(self, context):
        ob = context.object
        props = ob.reaction_diffusion_settings
        layout = self.layout
        col = layout.column(align=True)
        if props.input_data == 'WEIGHT':
            insert_weight_parameter(col, ob, 'brush', text='Brush:')
            insert_weight_parameter(col, ob, 'diff_a', text='Diff A:')
            insert_weight_parameter(col, ob, 'diff_b', text='Diff B:')
            insert_weight_parameter(col, ob, 'scale', text='Scale:')
            insert_weight_parameter(col, ob, 'f', text='f:')
            insert_weight_parameter(col, ob, 'k', text='k:')
        else:
            col.label(text='Using Attributes (Vertex > Float) if existing:')
            insert_attribute_parameter(col, ob, 'RD_brush', text='Brush:')
            insert_attribute_parameter(col, ob, 'RD_diff_a', text='Diff A:')
            insert_attribute_parameter(col, ob, 'RD_diff_b', text='Diff B:')
            insert_attribute_parameter(col, ob, 'RD_scale', text='Scale:')
            insert_attribute_parameter(col, ob, 'RD_f', text='f:')
            insert_attribute_parameter(col, ob, 'RD_k', text='k:')
            if not props.bool_mod:
                col.label(text="'Use Modifiers' is disabled.", icon='INFO')
        col.enabled = not props.bool_cache

class TISSUE_PT_reaction_diffusion_cache(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_reaction_diffusion"
    bl_label = "Cache"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return 'A' and 'B' in context.object.vertex_groups

    def draw(self, context):
        ob = context.object
        props = ob.reaction_diffusion_settings
        layout = self.layout
        col = layout.column(align=True)
        col.label(text='Cache:')
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

def insert_weight_parameter(col, ob, name, text=''):
    props = ob.reaction_diffusion_settings
    split = col.split(factor=0.25, align=True)
    col2 = split.column(align=True)
    col2.label(text=text)
    col2 = split.column(align=True)
    row2 = col2.row(align=True)
    row2.prop_search(props, 'vertex_group_' + name, ob, "vertex_groups", text='')
    if name != 'brush':
        row2.prop(props, "invert_vertex_group_" + name, text="", toggle=True, icon='ARROW_LEFTRIGHT')
    if 'vertex_group_' + name in props:
        if props['vertex_group_' + name] != '':
            if name == 'brush':
                col2.prop(props, "brush_mult")
            else:
                row2 = col2.row(align=True)
                row2.prop(props, "min_" + name, text="Min")
                row2 = col2.row(align=True)
                row2.prop(props, "max_" + name, text="Max")
    col.separator()

def insert_attribute_parameter(col, ob, name, text=''):
    props = ob.reaction_diffusion_settings
    if name in ob.data.attributes.keys():
        col.label(text = text + ' Attribute "' + name + '" found!', icon='KEYFRAME_HLT')
    else:
        col.label(text = text + ' Attribute "' + name + '" not found.', icon='KEYFRAME')
    col.separator()

def rd_apply_modifiers(ob):
    # hide deforming modifiers
    mod_visibility = []
    for m in ob.modifiers:
        mod_visibility.append(m.show_viewport)
        if not (mod_preserve_shape(m) or 'RD' in m.name): m.show_viewport = False

    # evaluated mesh
    dg = bpy.context.evaluated_depsgraph_get()
    ob_eval = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ob_eval, preserve_all_data_layers=True, depsgraph=dg)
    if len(me.vertices) != len(ob.data.vertices):
        return "TISSUE: Modifiers used for Reaction-Diffusion cannot change the number of vertices."

    # set original visibility
    for v, m in zip(mod_visibility, ob.modifiers):
        m.show_viewport = v
    ob.modifiers.update()
    return me
