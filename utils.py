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

import bpy
import threading
import numpy as np
import multiprocessing
from multiprocessing import Process, Pool
try: from .numba_functions import numba_lerp2
except: pass

weight = []
n_threads = multiprocessing.cpu_count()

class ThreadVertexGroup(threading.Thread):
    def __init__ ( self, id, vertex_group, n_verts):
        self.id = id
        self.vertex_group = vertex_group
        self.n_verts = n_verts
        threading.Thread.__init__ ( self )

    def run (self):
        global weight
        global n_threads
        verts = np.arange(int(self.n_verts/8))*8 + self.id
        for v in verts:
            try:
                weight[v] = self.vertex_group.weight(v)
            except:
                pass

def thread_read_weight(_weight, vertex_group):
    global weight
    global n_threads
    print(n_threads)
    weight = _weight
    n_verts = len(weight)
    threads = [ThreadVertexGroup(i, vertex_group, n_verts) for i in range(n_threads)]
    for t in threads: t.start()
    for t in threads: t.join()
    return weight

def process_read_weight(id, vertex_group, n_verts):
    global weight
    global n_threads
    verts = np.arange(int(self.n_verts/8))*8 + self.id
    for v in verts:
        try:
            weight[v] = self.vertex_group.weight(v)
        except:
            pass


def read_weight(_weight, vertex_group):
    global weight
    global n_threads
    print(n_threads)
    weight = _weight
    n_verts = len(weight)
    n_cores = multiprocessing.cpu_count()
    pool = Pool(processes=n_cores)
    multiple_results = [pool.apply_async(process_read_weight, (i, vertex_group, n_verts)) for i in range(n_cores)]
    #processes = [Process(target=process_read_weight, args=(i, vertex_group, n_verts)) for i in range(n_threads)]
    #for t in processes: t.start()
    #for t in processes: t.join()
    return weight

#Recursivly transverse layer_collection for a particular name
def recurLayerCollection(layerColl, collName):
    found = None
    if (layerColl.name == collName):
        return layerColl
    for layer in layerColl.children:
        found = recurLayerCollection(layer, collName)
        if found:
            return found

def auto_layer_collection():
    # automatically change active layer collection
    layer = bpy.context.view_layer.active_layer_collection
    layer_collection = bpy.context.view_layer.layer_collection
    if layer.hide_viewport or layer.collection.hide_viewport:
        collections = bpy.context.object.users_collection
        for c in collections:
            lc = recurLayerCollection(layer_collection, c.name)
            if not c.hide_viewport and not lc.hide_viewport:
                bpy.context.view_layer.active_layer_collection = lc

def lerp(a, b, t):
    return a + (b - a) * t

def _lerp2(v1, v2, v3, v4, v):
    v12 = v1.lerp(v2,v.x) # + (v2 - v1) * v.x
    v34 = v3.lerp(v4,v.x) # + (v4 - v3) * v.x
    return v12.lerp(v34, v.y)# + (v34 - v12) * v.y

def lerp2(v1, v2, v3, v4, v):
    v12 = v1 + (v2 - v1) * v.x
    v34 = v3 + (v4 - v3) * v.x
    return v12 + (v34 - v12) * v.y

def lerp3(v1, v2, v3, v4, v):
    loc = lerp2(v1.co, v2.co, v3.co, v4.co, v)
    nor = lerp2(v1.normal, v2.normal, v3.normal, v4.normal, v)
    nor.normalize()
    return loc + nor * v.z

def np_lerp2(v00, v10, v01, v11, vx, vy):
    #try:
    #    co2 = numba_lerp2(v00, v10, v01, v11, vx, vy)
    #except:
    co0 = v00 + (v10 - v00) * vx
    co1 = v01 + (v11 - v01) * vx
    co2 = co0 + (co1 - co0) * vy
    return co2

def _convert_object_to_mesh(ob, apply_modifiers=True, preserve_status=True):
    if not apply_modifiers:
        mod_visibility = [m.show_viewport for m in ob.modifiers]
        for m in ob.modifiers:
            m.show_viewport = False
    if preserve_status:
        # store status
        mode = bpy.context.object.mode
        selected = bpy.context.selected_objects
        active = bpy.context.object
    # change status
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    new_ob = ob.copy()
    new_ob.data = ob.data.copy()
    bpy.context.collection.objects.link(new_ob)
    bpy.context.view_layer.objects.active = new_ob
    new_ob.select_set(True)
    bpy.ops.object.convert(target='MESH')
    if preserve_status:
        # restore status
        bpy.ops.object.select_all(action='DESELECT')
        for o in selected: o.select_set(True)
        bpy.context.view_layer.objects.active = active
        bpy.ops.object.mode_set(mode=mode)
    if not apply_modifiers:
        for m,vis in zip(ob.modifiers,mod_visibility):
            m.show_viewport = vis
    return new_ob

def convert_object_to_mesh(ob, apply_modifiers=True, preserve_status=True):
    try: ob.name
    except: return None
    if ob.type != 'MESH':
        if not apply_modifiers:
            mod_visibility = [m.show_viewport for m in ob.modifiers]
            for m in ob.modifiers: m.show_viewport = False
        #ob.modifiers.update()
        #dg = bpy.context.evaluated_depsgraph_get()
        #ob_eval = ob.evaluated_get(dg)
        #me = bpy.data.meshes.new_from_object(ob_eval, preserve_all_data_layers=True, depsgraph=dg)
        me = simple_to_mesh(ob)
        new_ob = bpy.data.objects.new(ob.data.name, me)
        new_ob.location, new_ob.matrix_world = ob.location, ob.matrix_world
        if not apply_modifiers:
            for m,vis in zip(ob.modifiers,mod_visibility): m.show_viewport = vis
    else:
        if apply_modifiers:
            new_ob = ob.copy()
            new_me = simple_to_mesh(ob)
            new_ob.modifiers.clear()
            new_ob.data = new_me
        else:
            new_ob = ob.copy()
            new_ob.data = ob.data.copy()
            new_ob.modifiers.clear()
    bpy.context.collection.objects.link(new_ob)
    if preserve_status:
        new_ob.select_set(False)
    else:
        for o in bpy.context.view_layer.objects: o.select_set(False)
        new_ob.select_set(True)
        bpy.context.view_layer.objects.active = new_ob
    return new_ob

def simple_to_mesh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ob_eval = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ob_eval, preserve_all_data_layers=True, depsgraph=dg)
    me.calc_normals()
    return me

# Prevent Blender Crashes with handlers
def set_animatable_fix_handler(self, context):
    old_handlers = []
    blender_handlers = bpy.app.handlers.render_init
    for h in blender_handlers:
        if "turn_off_animatable" in str(h):
            old_handlers.append(h)
    for h in old_handlers: blender_handlers.remove(h)
    blender_handlers.append(turn_off_animatable)
    return

def turn_off_animatable(scene):
    for o in bpy.data.objects:
        o.tissue_tessellate.bool_run = False
        o.reaction_diffusion_settings.run = False
        #except: pass
    return
