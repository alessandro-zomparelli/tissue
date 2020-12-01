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

import bpy, bmesh
import threading
import numpy as np
import multiprocessing
from multiprocessing import Process, Pool
from mathutils import Vector
from math import *
try: from .numba_functions import numba_lerp2, numba_lerp2_4
except: pass

from . import config

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

import sys
def np_lerp2(v00, v10, v01, v11, vx, vy):
    if 'numba' in sys.modules and False:
        if len(v00.shape) == 3:
            co2 = numba_lerp2(v00, v10, v01, v11, vx, vy)
        elif len(v00.shape) == 4:
            co2 = numba_lerp2_4(v00, v10, v01, v11, vx, vy)
    #except:
    else:
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
    blender_handlers.append(turn_off_animatable)
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

#evaluatedDepsgraph = 'pippo'

def simple_to_mesh(ob, depsgraph=None):
    #global evaluatedDepsgraph
    if depsgraph == None:
        if config.evaluatedDepsgraph == None:
            dg = bpy.context.evaluated_depsgraph_get()
        else: dg = config.evaluatedDepsgraph
    else:
        dg = depsgraph
    ob_eval = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ob_eval, preserve_all_data_layers=True, depsgraph=dg)
    me.calc_normals()
    return me

def join_objects(objects, link_to_scene=True, make_active=False):
    C = bpy.context
    bm = bmesh.new()

    materials = {}
    faces_materials = []
    if config.evaluatedDepsgraph == None:
        dg = C.evaluated_depsgraph_get()
    else: dg = config.evaluatedDepsgraph

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

def array_mesh(ob, n):
    arr = ob.modifiers.new('Repeat','ARRAY')
    arr.relative_offset_displace[0] = 0
    arr.count = n
    ob.modifiers.update()

    dg = bpy.context.evaluated_depsgraph_get()
    me = simple_to_mesh(ob, depsgraph=dg)
    ob.modifiers.remove(arr)
    return me

def get_mesh_before_subs(ob):
    not_allowed  = ('FLUID_SIMULATION', 'ARRAY', 'BEVEL', 'BOOLEAN', 'BUILD',
                    'DECIMATE', 'EDGE_SPLIT', 'MASK', 'MIRROR', 'REMESH',
                    'SCREW', 'SOLIDIFY', 'TRIANGULATE', 'WIREFRAME', 'SKIN',
                    'EXPLODE', 'PARTICLE_INSTANCE', 'PARTICLE_SYSTEM', 'SMOKE')
    subs = 0
    hide_mods = []
    mods_visibility = []
    for m in ob.modifiers:
        hide_mods.append(m)
        mods_visibility.append(m.show_viewport)
        if m.type in ('SUBSURF','MULTIRES'): subs = m.levels
        elif m.type in not_allowed:
            subs = 0
            hide_mods = []
            mods_visibility = []
    for m in hide_mods: m.show_viewport = False
    me = simple_to_mesh(ob)
    for m, vis in zip(hide_mods,mods_visibility): m.show_viewport = vis
    return me, subs

### MESH FUNCTIONS

def calc_verts_area(me):
    n_verts = len(me.vertices)
    n_faces = len(me.polygons)
    vareas = np.zeros(n_verts)
    vcount = np.zeros(n_verts)
    parea = [0]*n_faces
    pverts = [0]*n_faces*4
    me.polygons.foreach_get('area', parea)
    me.polygons.foreach_get('vertices', pverts)
    parea = np.array(parea)
    pverts = np.array(pverts).reshape((n_faces, 4))
    for a, verts in zip(parea,pverts):
        vareas[verts] += a
        vcount[verts] += 1
    return vareas / vcount

def calc_verts_area_bmesh(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    verts_area = np.zeros(len(me.vertices))
    for v in bm.verts:
        area = 0
        faces = v.link_faces
        for f in faces:
            area += f.calc_area()
        verts_area[v.index] = area if area == 0 else area/len(faces)
    bm.free()
    return verts_area

import time

def get_patches(me_low, me_high, sides, subs, bool_selection, bool_material_id, material_id):
    #start_time = time.time()
    nv = len(me_low.vertices)       # number of vertices
    ne = len(me_low.edges)          # number of edges
    nf = len(me_low.polygons)       # number of polygons
    n = 2**subs + 1
    nev = ne * n               # number of vertices along the subdivided edges
    nevi = nev - 2*ne          # internal vertices along subdividede edges

    n0 = 2**(subs-1) - 1

    # filtered polygonal faces
    poly_sides = np.array([len(p.vertices) for p in me_low.polygons])
    mask = poly_sides == sides
    if bool_material_id:
        mask_material = [1]*nf
        me_low.polygons.foreach_get('material_index',mask_material)
        mask_material = np.array(mask_material) == material_id
        mask = np.logical_and(mask,mask_material)
    if bool_selection:
        mask_selection = [True]*nf
        me_low.polygons.foreach_get('select',mask_selection)
        mask_selection = np.array(mask_selection)
        mask = np.logical_and(mask,mask_selection)
    polys = np.array(me_low.polygons)[mask]
    mult = n0**2 + n0
    ps = poly_sides * mult + 1
    ps = np.insert(ps,0,nv + nevi, axis=0)[:-1]
    ips = ps.cumsum()[mask]                    # incremental polygon sides
    nf = len(polys)

    # when subdivided quad faces follows a different pattern
    if sides == 4:
        n_patches = nf
    else:
        n_patches = nf*sides

    if sides == 4:
        patches = np.zeros((nf,n,n),dtype='int')
        verts = [[vv for vv in p.vertices] for p in polys if len(p.vertices) == sides]
        verts = np.array(verts).reshape((-1,sides))

        # filling corners

        patches[:,0,0] = verts[:,0]
        patches[:,n-1,0] = verts[:,1]
        patches[:,n-1,n-1] = verts[:,2]
        patches[:,0,n-1] = verts[:,3]

        if subs != 0:
            shift_verts = np.roll(verts, -1, axis=1)[:,:,np.newaxis]
            edge_keys = np.concatenate((shift_verts, verts[:,:,np.newaxis]), axis=2)
            edge_keys.sort()

            edge_verts = me_low.edge_keys             # edges keys
            edge_verts = np.array(edge_verts)
            edges_index = np.zeros((ne,ne),dtype='int')
            edges_index[edge_verts[:,0],edge_verts[:,1]] = np.arange(ne)

            evi = np.arange(nevi) + nv
            evi = evi.reshape(ne,n-2)           # edges inner verts
            straight = np.arange(n-2)+1
            inverted = np.flip(straight)
            inners = np.array([[j*(n-2)+i for j in range(n-2)] for i in range(n-2)])

            ek1 = me_high.edge_keys             # edges keys
            ek1 = np.array(ek1)                             # edge keys highres
            keys0 = ek1[np.arange(ne)*(n-1)]                # first inner edge
            keys1 = ek1[np.arange(ne)*(n-1)+n-2]            # last inner edge
            edges_dir = np.zeros((nev,nev), dtype='int')
            edges_dir[keys0[:,0], keys0[:,1]] = 1
            edges_dir[keys1[:,0], keys1[:,1]] = 1
            pick_verts = np.array((inverted,straight))

            patch_index = np.arange(nf)[:,np.newaxis,np.newaxis]

            # edge 0
            e0 = edge_keys[:,0]                             # get edge key (faces, 2)
            edge_id = edges_index[e0[:,0],e0[:,1]]          # edge index
            edge_verts = evi[edge_id]                       # indexes of inner vertices
            dir = edges_dir[verts[:,0], edge_verts[:,0]]       # check correct direction
            ids = pick_verts[dir][:,np.newaxis,:]                           # indexes order along the side
            patches[patch_index,ids,0] = edge_verts[:,np.newaxis,:]                   # assign indexes

            # edge 1
            e0 = edge_keys[:,1]                             # get edge key (faces, 2)
            edge_id = edges_index[e0[:,0],e0[:,1]]          # edge index
            edge_verts = evi[edge_id]                       # indexes of inner vertices
            dir = edges_dir[verts[:,1], edge_verts[:,0]]       # check correct direction
            ids = pick_verts[dir][:,:,np.newaxis]                           # indexes order along the side
            patches[patch_index,n-1,ids] = edge_verts[:,:,np.newaxis]                   # assign indexes

            # edge 2
            e0 = edge_keys[:,2]                             # get edge key (faces, 2)
            edge_id = edges_index[e0[:,0],e0[:,1]]          # edge index
            edge_verts = evi[edge_id]                       # indexes of inner vertices
            dir = edges_dir[verts[:,3], edge_verts[:,0]]       # check correct direction
            ids = pick_verts[dir][:,np.newaxis,:]                           # indexes order along the side
            patches[patch_index,ids,n-1] = edge_verts[:,np.newaxis,:]                   # assign indexes

            # edge 3
            e0 = edge_keys[:,3]                             # get edge key (faces, 2)
            edge_id = edges_index[e0[:,0],e0[:,1]]          # edge index
            edge_verts = evi[edge_id]                       # indexes of inner vertices
            dir = edges_dir[verts[:,0], edge_verts[:,0]]       # check correct direction
            ids = pick_verts[dir][:,:,np.newaxis]                           # indexes order along the side
            patches[patch_index,0,ids] = edge_verts[:,:,np.newaxis]                   # assign indexes

            # fill inners
            patches[:,1:-1,1:-1] = inners[np.newaxis,:,:] + ips[:,np.newaxis,np.newaxis]

    #end_time = time.time()
    #print('Tissue: Got Patches in {:.4f} sec'.format(end_time-start_time))

    return patches, mask

def get_patches_(me_low, me_high, sides, subs):

    start_time = time.time()
    nv = len(me_low.vertices)       # number of vertices
    ne = len(me_low.edges)          # number of edges
    n = 2**subs + 1
    nev = ne * n            # number of vertices along the subdivided edges
    nevi = nev - 2*ne          # internal vertices along subdividede edges

    # filtered polygonal faces
    polys = [p for p in me_low.polygons if len(p.vertices)==sides]
    n0 = 2**(subs-1) - 1
    ps = [nv + nevi]
    for p in me_low.polygons:
        psides = len(p.vertices)
        increment = psides * (n0**2 + n0) + 1
        ps.append(increment)
    ips = np.array(ps).cumsum()                    # incremental polygon sides
    nf = len(polys)
    # when subdivided quad faces follows a different pattern
    if sides == 4:
        n_patches = nf
    else:
        n_patches = nf*sides

    ek = me_low.edge_keys               # edges keys
    ek1 = me_high.edge_keys             # edges keys
    evi = np.arange(nevi) + nv
    evi = evi.reshape(ne,n-2)           # edges verts
    straight = np.arange(n-2)+1
    inverted = np.flip(straight)
    inners = np.array([[j*(n-2)+i for j in range(n-2)] for i in range(n-2)])

    edges_dict = {e : e1 for e,e1 in zip(ek,evi)}
    keys0 = [ek1[i*(n-1)] for i in range(len(ek))]
    keys1 = [ek1[i*(n-1)+n-2] for i in range(len(ek))]
    edges_straight = dict.fromkeys(keys0 + keys1, straight)
    keys2 = [(k0[0],k1[1]) for k0,k1 in zip(keys0, keys1)]
    keys3 = [(k1[0],k0[1]) for k0,k1 in zip(keys0, keys1)]
    edges_inverted = dict.fromkeys(keys2 + keys3, inverted)
    filter_edges = {**edges_straight, **edges_inverted}
    if sides == 4:
        patches = np.zeros((nf,n,n))
        for count, p in enumerate(polys):
            patch = patches[count]
            pid = p.index
            verts = p.vertices

            # filling corners

            patch[0,0] = verts[0]
            patch[n-1,0] = verts[1]
            patch[n-1,n-1] = verts[2]
            patch[0,n-1] = verts[3]

            if subs == 0: continue

            edge_keys = p.edge_keys

            # fill edges
            e0 = edge_keys[0]
            edge_verts = edges_dict[e0]
            e1 = (verts[0], edge_verts[0])
            ids = filter_edges[e1]
            patch[ids,0] = edge_verts

            e0 = edge_keys[1]
            edge_verts = edges_dict[e0]
            e1 = (verts[1], edge_verts[0])
            ids = filter_edges[e1]
            patch[n-1,ids] = evi[ek.index(e0)]

            e0 = edge_keys[2]
            edge_verts = edges_dict[e0]
            e1 = (verts[3], edge_verts[0])
            ids = filter_edges[e1]
            patch[ids,n-1] = evi[ek.index(e0)]

            e0 = edge_keys[3]
            edge_verts = edges_dict[e0]
            e1 = (verts[0], edge_verts[0])
            ids = filter_edges[e1]
            patch[0,ids] = evi[ek.index(e0)]

            # fill inners
            patch[1:-1,1:-1] = inners + ips[pid]

    #end_time = time.time()
    #print('Tissue: Got Patches in {:.4f} sec'.format(end_time-start_time))

    return patches.astype(dtype='int')


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

def get_normals_numpy(mesh):
    n_verts = len(mesh.vertices)
    normals = [0]*n_verts*3
    mesh.vertices.foreach_get('normal', normals)
    normals = np.array(normals).reshape((n_verts,3))
    return normals

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

def curve_from_pydata(points, radii, indexes, name='Curve', skip_open=False, merge_distance=1, set_active=True, only_data=False):
    curve = bpy.data.curves.new(name,'CURVE')
    curve.dimensions = '3D'
    use_rad = True
    for c in indexes:
        bool_cyclic = c[0] == c[-1]
        if bool_cyclic: c.pop(-1)
        # cleanup
        pts = np.array([points[i] for i in c])
        try:
            rad = np.array([radii[i] for i in c])
        except:
            use_rad = False
            rad = 1
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
            if use_rad: rad = rad[mask]

        if skip_open and not bool_cyclic: continue
        s = curve.splines.new('POLY')
        n_pts = len(pts)
        s.points.add(n_pts-1)
        w = np.ones(n_pts).reshape((n_pts,1))
        co = np.concatenate((pts,w),axis=1).reshape((n_pts*4))
        s.points.foreach_set('co',co)
        if use_rad: s.points.foreach_set('radius',rad)
        s.use_cyclic_u = bool_cyclic
    if only_data:
        return curve
    else:
        ob_curve = bpy.data.objects.new(name,curve)
        bpy.context.collection.objects.link(ob_curve)
        if set_active:
            bpy.context.view_layer.objects.active = ob_curve
        return ob_curve

def update_curve_from_pydata(curve, points, radii, indexes, merge_distance=1):
    curve.splines.clear()
    use_rad = True
    for ic, c in enumerate(indexes):
        bool_cyclic = c[0] == c[-1]
        if bool_cyclic: c.pop(-1)

        # cleanup
        pts = np.array([points[i] for i in c if i != None])
        try:
            rad = np.array([radii[i] for i in c if i != None])
        except:
            use_rad = False
            rad = 1
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
            if use_rad: rad = rad[mask]
        #if skip_open and not bool_cyclic: continue
        s = curve.splines.new('POLY')
        n_pts = len(pts)
        s.points.add(n_pts-1)
        w = np.ones(n_pts).reshape((n_pts,1))
        co = np.concatenate((pts,w),axis=1).reshape((n_pts*4))
        s.points.foreach_set('co',co)
        if use_rad: s.points.foreach_set('radius',rad)
        s.use_cyclic_u = bool_cyclic


def loops_from_bmesh(edges):
    todo_edges = list(edges)
    #todo_edges = [e.index for e in bm.edges]
    vert_loops = []
    edge_loops = []
    while len(todo_edges) > 0:
        edge = todo_edges[0]
        vert_loop, edge_loop = run_edge_loop(edge)
        for e in edge_loop:
            try: todo_edges.remove(e)
            except: pass
        edge_loops.append(edge_loop)
        vert_loops.append(vert_loop)
        #if len(todo_edges) == 0: break
    return vert_loops, edge_loops

def run_edge_loop_direction(edge,vert):
    edge0 = edge
    edge_loop = [edge]
    vert_loop = [vert]
    while True:
        link_edges = list(vert.link_edges)
        link_edges.remove(edge)
        n_edges = len(link_edges)
        if n_edges == 1:
            edge = link_edges[0]
        elif n_edges < 4:
            link_faces = edge.link_faces
            edge = None
            for e in link_edges:
                link_faces1 = e.link_faces
                if len(link_faces) == len(link_faces1):
                    common_faces = [f for f in link_faces1 if f in link_faces]
                    if len(common_faces) == 0:
                        edge = e
                        break
        else: break
        if edge == None: break
        edge_loop.append(edge)
        vert = edge.other_vert(vert)
        vert_loop.append(vert)
        if edge == edge0: break
    return vert_loop, edge_loop

def run_edge_loop(edge):
    vert0 = edge.verts[0]
    vert_loop0, edge_loop0 = run_edge_loop_direction(edge, vert0)
    if len(edge_loop0) == 1 or edge_loop0[0] != edge_loop0[-1]:
        vert1 = edge.verts[1]
        vert_loop1, edge_loop1 = run_edge_loop_direction(edge, vert1)
        edge_loop0.reverse()
        vert_loop0.reverse()
        edge_loop = edge_loop0[:-1] + edge_loop1
        vert_loop = vert_loop0 + vert_loop1
    else:
        edge_loop = edge_loop0[1:]
        vert_loop = vert_loop0
    return vert_loop, edge_loop

def curve_from_vertices(indexes, verts, name='Curve'):
    curve = bpy.data.curves.new(name,'CURVE')
    for c in indexes:
        s = curve.splines.new('POLY')
        s.points.add(len(c))
        for i,p in enumerate(c):
            s.points[i].co = verts[p].co.xyz + [1]
            s.points[i].tilt = degrees(asin(verts[p].co.z))
    ob_curve = bpy.data.objects.new(name,curve)
    return ob_curve

def nurbs_from_vertices(indexes, co, radii=[], name='Curve', set_active=True, interpolation='POLY'):
    curve = bpy.data.curves.new(name,'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 2
    curve.bevel_depth = 0.01
    curve.bevel_resolution = 0
    for pts in indexes:
        s = curve.splines.new(interpolation)
        n_pts = len(pts)
        s.points.add(n_pts-1)
        w = np.ones(n_pts).reshape((n_pts,1))
        curve_co = np.concatenate((co[pts],w),axis=1).reshape((n_pts*4))
        s.points.foreach_set('co',curve_co)
        try:
            s.points.foreach_set('radius',radii[pts])
        except: pass
        s.use_endpoint_u = True

    ob_curve = bpy.data.objects.new(name,curve)
    bpy.context.collection.objects.link(ob_curve)
    if set_active:
        bpy.context.view_layer.objects.active = ob_curve
        ob_curve.select_set(True)
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


def bmesh_get_weight_numpy(group_index, layer, verts):
    weight = np.zeros(len(verts))
    for i, v in enumerate(verts):
        dvert = v[layer]
        if group_index in dvert:
            weight[i] = dvert[group_index]
            #dvert[group_index] = 0.5
    return weight

def bmesh_set_weight_numpy(group_index, layer, verts, weight):
    for i, v in enumerate(verts):
        dvert = v[layer]
        if group_index in dvert:
            dvert[group_index] = weight[i]
    return verts

def bmesh_set_weight_numpy(bm, group_index, weight):
    layer = bm.verts.layers.deform.verify()
    for i, v in enumerate(bm.verts):
        dvert = v[layer]
        #if group_index in dvert:
        dvert[group_index] = weight[i]
    return bm

def get_uv_edge_vectors(me, uv_map = 0, only_positive=False):
    count = 0
    uv_vectors = {}
    for i, f in enumerate(me.polygons):
        f_verts = len(f.vertices)
        for j0 in range(f_verts):
            j1 = (j0+1)%f_verts
            uv0 = me.uv_layers[uv_map].data[count+j0].uv
            uv1 = me.uv_layers[uv_map].data[count+j1].uv
            delta_uv = (uv1-uv0).normalized()
            if only_positive:
                delta_uv.x = abs(delta_uv.x)
                delta_uv.y = abs(delta_uv.y)
            edge_key = tuple(sorted([f.vertices[j0], f.vertices[j1]]))
            uv_vectors[edge_key] = delta_uv
        count += f_verts
    uv_vectors = [uv_vectors[tuple(sorted(e.vertices))] for e in me.edges]
    return uv_vectors

def mesh_diffusion(me, values, iter, diff=0.2, uv_dir=0):
    values = np.array(values)
    n_verts = len(me.vertices)

    n_edges = len(me.edges)
    edge_verts = [0]*n_edges*2
    #me.edges.foreach_get("vertices", edge_verts)

    count = 0
    edge_verts = []
    uv_factor = {}
    uv_ang = (0.5 + uv_dir*0.5)*pi/2
    uv_vec = Vector((cos(uv_ang), sin(uv_ang)))
    for i, f in enumerate(me.polygons):
        f_verts = len(f.vertices)
        for j0 in range(f_verts):
            j1 = (j0+1)%f_verts
            if uv_dir != 0:
                uv0 = me.uv_layers[0].data[count+j0].uv
                uv1 = me.uv_layers[0].data[count+j1].uv
                delta_uv = (uv1-uv0).normalized()
                delta_uv.x = abs(delta_uv.x)
                delta_uv.y = abs(delta_uv.y)
                dir = uv_vec.dot(delta_uv)
            else:
                dir = 1
            #dir = abs(dir)
            #uv_factor.append(dir)
            edge_key = [f.vertices[j0], f.vertices[j1]]
            edge_key.sort()
            uv_factor[tuple(edge_key)] = dir
        count += f_verts
    id0 = []
    id1 = []
    uv_mult = []
    for ek, val in uv_factor.items():
        id0.append(ek[0])
        id1.append(ek[1])
        uv_mult.append(val)
    id0 = np.array(id0)
    id1 = np.array(id1)
    uv_mult = np.array(uv_mult)

    #edge_verts = np.array(edge_verts)
    #arr = np.arange(n_edges)*2

    #id0 = edge_verts[arr]     # first vertex indices for each edge
    #id1 = edge_verts[arr+1]   # second vertex indices for each edge
    for ii in range(iter):
        lap = np.zeros(n_verts)
        if uv_dir != 0:
            lap0 =  (values[id1] -  values[id0])*uv_mult   # laplacian increment for first vertex of each edge
        else:
            lap0 =  (values[id1] -  values[id0])
        np.add.at(lap, id0, lap0)
        np.add.at(lap, id1, -lap0)
        values += diff*lap
    return values

def mesh_diffusion_vector(me, vectors, iter, diff, uv_dir=0):
    vectors = np.array(vectors)
    x = vectors[:,0]
    y = vectors[:,1]
    z = vectors[:,2]
    x = mesh_diffusion(me, x, iter, diff, uv_dir)
    y = mesh_diffusion(me, y, iter, diff, uv_dir)
    z = mesh_diffusion(me, z, iter, diff, uv_dir)
    vectors[:,0] = x
    vectors[:,1] = y
    vectors[:,2] = z
    return vectors


### MODIFIERS ###
def mod_preserve_topology(mod):
    same_topology_modifiers = ('DATA_TRANSFER','NORMAL_EDIT','WEIGHTED_NORMAL',
        'UV_PROJECT','UV_WARP','VERTEX_WEIGHT_EDIT','VERTEX_WEIGHT_MIX',
        'VERTEX_WEIGHT_PROXIMITY','ARMATURE','CAST','CURVE','DISPLACE','HOOK',
        'LAPLACIANDEFORM','LATTICE','MESH_DEFORM','SHRINKWRAP','SIMPLE_DEFORM',
        'SMOOTH','CORRECTIVE_SMOOTH','LAPLACIANSMOOTH','SURFACE_DEFORM','WARP',
        'WAVE','CLOTH','COLLISION','DYNAMIC_PAINT','SOFT_BODY'
        )
    return mod.type in same_topology_modifiers

def mod_preserve_shape(mod):
    same_shape_modifiers = ('DATA_TRANSFER','NORMAL_EDIT','WEIGHTED_NORMAL',
        'UV_PROJECT','UV_WARP','VERTEX_WEIGHT_EDIT','VERTEX_WEIGHT_MIX',
        'VERTEX_WEIGHT_PROXIMITY','DYNAMIC_PAINT'
        )
    return mod.type in same_shape_modifiers


# find planar vector according to two axis
def flatten_vector(vec, x, y):
    vx = vec.project(x)
    vy = vec.project(y)
    mult = 1 if vx.dot(x) > 0 else -1
    vx = mult*vx.length
    mult = 1 if vy.dot(y) > 0 else -1
    vy = mult*vy.length
    return Vector((vx, vy))

# find rotations according to X axis
def vector_rotation(vec):
    v0 = Vector((1,0))
    ang = Vector.angle_signed(vec, v0)
    if ang < 0: ang = 2*pi + ang
    return ang
