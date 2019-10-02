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
from mathutils import Vector
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


# Prevent Blender Crashes with handlers
def set_animatable_fix_handler(self, context):
    old_handlers = []
    blender_handlers = bpy.app.handlers.render_init
    for h in blender_handlers:
        if "turn_off_animatable" in str(h):
            old_handlers.append(h)
    for h in old_handlers: blender_handlers.remove(h)
    ################ blender_handlers.append(turn_off_animatable)
    return

def turn_off_animatable(scene):
    for o in bpy.data.objects:
        o.tissue_tessellate.bool_run = False
        o.reaction_diffusion_settings.run = False
        #except: pass
    return

### OBJECTS ###

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

def join_objects(objects, link_to_scene=True, make_active=False):
    C = bpy.context
    bm = bmesh.new()

    materials = {}
    faces_materials = []
    dg = C.evaluated_depsgraph_get()
    for o in objects:
        bm.from_object(o, dg)
        # add object's material to the dictionary
        for m in o.data.materials:
            if m not in materials: materials[m] = len(materials)
        for f in o.data.polygons:
            index = f.material_index
            mat = o.material_slots[index].material
            new_index = materials[mat]
            faces_materials.append(new_index)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    # assign new indexes
    for index, f in zip(faces_materials, bm.faces): f.material_index = index
    # create object
    me = bpy.data.meshes.new('joined')
    bm.to_mesh(me)
    me.update()
    ob = bpy.data.objects.new('joined', me)
    if link_to_scene: C.collection.objects.link(ob)
    # make active
    if make_active:
        for o in C.view_layer.objects: o.select_set(False)
        ob.select_set(True)
        C.view_layer.objects.active = ob
    # add materials
    for m in materials.keys(): ob.data.materials.append(m)
    return ob

### MESH FUNCTIONS

def get_vertices_numpy(mesh):
    n_verts = len(mesh.vertices)
    verts = [0]*n_verts*3
    mesh.vertices.foreach_get('co', verts)
    verts = np.array(verts).reshape((n_verts,3))
    return verts

def get_vertices_and_normals_numpy(mesh):
    n_verts = len(mesh.vertices)
    verts = [0]*n_verts*3
    normals = [0]*n_verts*3
    mesh.vertices.foreach_get('co', verts)
    mesh.vertices.foreach_get('normal', normals)
    verts = np.array(verts).reshape((n_verts,3))
    normals = np.array(normals).reshape((n_verts,3))
    return verts, normals

def get_edges_numpy(mesh):
    n_edges = len(mesh.edges)
    edges = [0]*n_edges*2
    mesh.edges.foreach_get('vertices', edges)
    edges = np.array(edges).reshape((n_edges,2)).astype('int')
    return edges

def get_edges_id_numpy(mesh):
    n_edges = len(mesh.edges)
    edges = [0]*n_edges*2
    mesh.edges.foreach_get('vertices', edges)
    edges = np.array(edges).reshape((n_edges,2))
    indexes = np.arange(n_edges).reshape((n_edges,1))
    edges = np.concatenate((edges,indexes), axis=1)
    return edges

def get_vertices(mesh):
    n_verts = len(mesh.vertices)
    verts = [0]*n_verts*3
    mesh.vertices.foreach_get('co', verts)
    verts = np.array(verts).reshape((n_verts,3))
    verts = [Vector(v) for v in verts]
    return verts

def get_faces(mesh):
    faces = [[v for v in f.vertices] for f in mesh.polygons]
    return faces

def get_faces_numpy(mesh):
    faces = [[v for v in f.vertices] for f in mesh.polygons]
    return np.array(faces)

def get_faces_edges_numpy(mesh):
    faces = [v.edge_keys for f in mesh.polygons]
    return np.array(faces)

#try:
#from numba import jit, njit
#from numba.typed import List
'''
@jit
def find_curves(edges, n_verts):
    #verts_dict = {key:[] for key in range(n_verts)}
    verts_dict = {}
    for key in range(n_verts): verts_dict[key] = []
    for e in edges:
        verts_dict[e[0]].append(e[1])
        verts_dict[e[1]].append(e[0])
    curves = []#List()
    loop1 = True
    while loop1:
        if len(verts_dict) == 0:
            loop1 = False
            continue
        # next starting point
        v = list(verts_dict.keys())[0]
        # neighbors
        v01 = verts_dict[v]
        if len(v01) == 0:
            verts_dict.pop(v)
            continue
        curve = []#List()
        curve.append(v)         # add starting point
        curve.append(v01[0])    # add neighbors
        verts_dict.pop(v)
        loop2 = True
        while loop2:
            last_point = curve[-1]
            #if last_point not in verts_dict: break
            v01 = verts_dict[last_point]
            # curve end
            if len(v01) == 1:
                verts_dict.pop(last_point)
                loop2 = False
                continue
            if v01[0] == curve[-2]:
                curve.append(v01[1])
                verts_dict.pop(last_point)
            elif v01[1] == curve[-2]:
                curve.append(v01[0])
                verts_dict.pop(last_point)
            else:
                loop2 = False
                continue
            if curve[0] == curve[-1]:
                loop2 = False
                continue
        curves.append(curve)
    return curves
'''
def find_curves(edges, n_verts):
    verts_dict = {key:[] for key in range(n_verts)}
    for e in edges:
        verts_dict[e[0]].append(e[1])
        verts_dict[e[1]].append(e[0])
    curves = []
    while True:
        if len(verts_dict) == 0: break
        # next starting point
        v = list(verts_dict.keys())[0]
        # neighbors
        v01 = verts_dict[v]
        if len(v01) == 0:
            verts_dict.pop(v)
            continue
        curve = []
        if len(v01) > 1: curve.append(v01[1])    # add neighbors
        curve.append(v)         # add starting point
        curve.append(v01[0])    # add neighbors
        verts_dict.pop(v)
        # start building curve
        while True:
            #last_point = curve[-1]
            #if last_point not in verts_dict: break

            # try to change direction if needed
            if curve[-1] in verts_dict: pass
            elif curve[0] in verts_dict: curve.reverse()
            else: break

            # neighbors points
            last_point = curve[-1]
            v01 = verts_dict[last_point]

            # curve end
            if len(v01) == 1:
                verts_dict.pop(last_point)
                if curve[0] in verts_dict: continue
                else: break

            # chose next point
            new_point = None
            if v01[0] == curve[-2]: new_point = v01[1]
            elif v01[1] == curve[-2]: new_point = v01[0]
            #else: break

            #if new_point != curve[1]:
            curve.append(new_point)
            verts_dict.pop(last_point)
            if curve[0] == curve[-1]:
                verts_dict.pop(new_point)
                break
        curves.append(curve)
    return curves

def curve_from_points(points, name='Curve'):
    curve = bpy.data.curves.new(name,'CURVE')
    for c in points:
        s = curve.splines.new('POLY')
        s.points.add(len(c))
        for i,p in enumerate(c): s.points[i].co = p.xyz + [1]
    ob_curve = bpy.data.objects.new(name,curve)
    return ob_curve

def curve_from_pydata(points, indexes, name='Curve', skip_open=False, merge_distance=1, set_active=True):
    curve = bpy.data.curves.new(name,'CURVE')
    curve.dimensions = '3D'
    for c in indexes:
        # cleanup
        pts = np.array([points[i] for i in c])
        if merge_distance > 0:
            pts1 = np.roll(pts,1,axis=0)
            dist = np.linalg.norm(pts1-pts, axis=1)
            count = 0
            n = len(dist)
            mask = np.ones(n).astype('bool')
            for i in range(n):
                count += dist[i]
                if count > merge_distance: count = 0
                else: mask[i] = False
            pts = pts[mask]

        bool_cyclic = c[0] == c[-1]
        if skip_open and not bool_cyclic: continue
        s = curve.splines.new('POLY')
        n_pts = len(pts)
        s.points.add(n_pts-1)
        w = np.ones(n_pts).reshape((n_pts,1))
        co = np.concatenate((pts,w),axis=1).reshape((n_pts*4))
        s.points.foreach_set('co',co)
        s.use_cyclic_u = bool_cyclic
    ob_curve = bpy.data.objects.new(name,curve)
    bpy.context.collection.objects.link(ob_curve)
    if set_active:
        bpy.context.view_layer.objects.active = ob_curve
    return ob_curve

def curve_from_vertices(indexes, verts, name='Curve'):
    curve = bpy.data.curves.new(name,'CURVE')
    for c in indexes:
        s = curve.splines.new('POLY')
        s.points.add(len(c))
        for i,p in enumerate(c): s.points[i].co = verts[p].co.xyz + [1]
    ob_curve = bpy.data.objects.new(name,curve)
    return ob_curve

### WEIGHT FUNCTIONS ###

def get_weight(vertex_group, n_verts):
    weight = [0]*n_verts
    for i in range(n_verts):
        try: weight[i] = vertex_group.weight(i)
        except: pass
    return weight

def get_weight_numpy(vertex_group, n_verts):
    weight = [0]*n_verts
    for i in range(n_verts):
        try: weight[i] = vertex_group.weight(i)
        except: pass
    return np.array(weight)
