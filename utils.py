# SPDX-License-Identifier: GPL-2.0-or-later

import bpy, bmesh
import threading
import numpy as np
import multiprocessing
from multiprocessing import Process, Pool
from mathutils import Vector, Matrix
from math import *
try: from .numba_functions import *
except: pass

from . import config

def use_numba_tess():
    tissue_addon = bpy.context.preferences.addons[__package__]
    if 'use_numba_tess' in tissue_addon.preferences.keys():
        return tissue_addon.preferences['use_numba_tess']
    else:
        return True

def tissue_time(start_time, name, levels=0):
    tissue_addon = bpy.context.preferences.addons[__package__]
    end_time = time.time()
    if 'print_stats' in tissue_addon.preferences.keys():
        ps = tissue_addon.preferences['print_stats']
    else:
        ps = 1
    if levels < ps:
        if "Tissue: " in name: head = ""
        else: head = "        "
        if start_time:
            print('{}{}{} in {:.4f} sec'.format(head, "|   "*levels, name, end_time - start_time))
        else:
            print('{}{}{}'.format(head, "|   "*levels, name))
    return end_time


# ------------------------------------------------------------------
# MATH
# ------------------------------------------------------------------

def _np_broadcast(arrays):
    shapes = [arr.shape for arr in arrays]
    for i in range(len(shapes[0])):
        ish = [sh[i] for sh in shapes]
        max_len = max(ish)
        for j in range(len(arrays)):
            leng = ish[j]
            if leng == 1: arrays[j] = np.repeat(arrays[j], max_len, axis=i)
    for arr in arrays:
        arr = arr.flatten()
    #vt = v0 + (v1 - v0) * t
    return arrays

def lerp(a, b, t):
    return a + (b - a) * t

def _lerp2(v1, v2, v3, v4, v):
    v12 = v1.lerp(v2,v.x) # + (v2 - v1) * v.x
    v34 = v3.lerp(v4,v.x) # + (v4 - v3) * v.x
    return v12.lerp(v34, v.y)# + (v34 - v12) * v.y

def lerp2(v1, v2, v3, v4, v):
    v12 = v1 + (v2 - v1) * v.x
    v34 = v3 + (v4 - v3) * v.x
    v = v12 + (v34 - v12) * v.y
    return v

def lerp3(v1, v2, v3, v4, v):
    loc = lerp2(v1.co, v2.co, v3.co, v4.co, v)
    nor = lerp2(v1.normal, v2.normal, v3.normal, v4.normal, v)
    nor.normalize()
    return loc + nor * v.z

import sys
def np_lerp2(v00, v10, v01, v11, vx, vy, mode=''):
    if 'numba' in sys.modules and use_numba_tess():
        if mode == 'verts':
            co2 = numba_interp_points(v00, v10, v01, v11, vx, vy)
        elif mode == 'shapekeys':
            co2 = numba_interp_points_sk(v00, v10, v01, v11, vx, vy)
        else:
            co2 = numba_lerp2(v00, v10, v01, v11, vx, vy)
    else:
        co0 = v00 + (v10 - v00) * vx
        co1 = v01 + (v11 - v01) * vx
        co2 = co0 + (co1 - co0) * vy
    return co2

def calc_thickness(co2,n2,vz,a,weight):
    if 'numba' in sys.modules and use_numba_tess():
        if len(co2.shape) == 3:
            if type(a) != np.ndarray:
                a = np.ones(len(co2)).reshape((-1,1,1))
            if type(weight) != np.ndarray:
                weight = np.ones(len(co2)).reshape((-1,1,1))
            co3 = numba_calc_thickness_area_weight(co2,n2,vz,a,weight)
        elif len(co2.shape) == 4:
            n_patches = co2.shape[0]
            n_sk = co2.shape[1]
            n_verts = co2.shape[2]
            if type(a) != np.ndarray:
                a = np.ones(n_patches).reshape((n_patches,1,1,1))
            if type(weight) != np.ndarray:
                weight = np.ones(n_patches).reshape((n_patches,1,1,1))
            na = a.shape[1]-1
            nw = weight.shape[1]-1
            co3 = np.empty((n_sk,n_patches,n_verts,3))
            for i in range(n_sk):
                co3[i] = numba_calc_thickness_area_weight(co2[:,i],n2[:,i],vz[:,i],a[:,min(i,na)],weight[:,min(i,nw)])
            co3 = co3.swapaxes(0,1)
    else:
        use_area = type(a) == np.ndarray
        use_weight = type(weight) == np.ndarray
        if use_area:
            if use_weight:
                co3 = co2 + n2 * vz * a * weight
            else:
                co3 = co2 + n2 * vz * a
        else:
            if use_weight:
                co3 = co2 + n2 * vz * weight
            else:
                co3 = co2 + n2 * vz
    return co3

def combine_and_flatten(arrays):
    if 'numba' in sys.modules:
        new_list = numba_combine_and_flatten(arrays)
    else:
        new_list = np.concatenate(arrays, axis=0)
        new_list = new_list.flatten().tolist()
    return new_list

def np_interp2(grid, vx, vy):
    grid_shape = grid.shape[-2:]
    levels = len(grid.shape)-2
    nu = grid_shape[0]
    nv = grid_shape[1]
    u = np.arange(nu)/(nu-1)
    v = np.arange(nv)/(nv-1)
    u_shape = [1]*levels + [nu]
    v_shape = [1]*levels + [nv]

    co0 = np.interp()
    co1 = np.interp()
    co2 = np.interp()
    return co2

def flatten_vector(vec, x, y):
    """
    Find planar vector according to two axis.
    :arg vec: Input vector.
    :type vec: :class:'mathutils.Vector'
    :arg x: First axis.
    :type x: :class:'mathutils.Vector'
    :arg y: Second axis.
    :type y: :class:'mathutils.Vector'
    :return: Projected 2D Vector.
    :rtype: :class:'mathutils.Vector'
    """
    vx = vec.project(x)
    vy = vec.project(y)
    mult = 1 if vx.dot(x) > 0 else -1
    vx = mult*vx.length
    mult = 1 if vy.dot(y) > 0 else -1
    vy = mult*vy.length
    return Vector((vx, vy))

def vector_rotation(vec):
    """
    Find vector rotation according to X axis.
    :arg vec: Input vector.
    :type vec: :class:'mathutils.Vector'
    :return: Angle in radians.
    :rtype: float
    """
    v0 = Vector((1,0))
    ang = Vector.angle_signed(vec, v0)
    if ang < 0: ang = 2*pi + ang
    return ang

def signed_angle_with_axis(va, vb, axis):
    return atan2(va.cross(vb).dot(axis.normalized()), va.dot(vb))

def round_angle_with_axis(va, vb, axis):
    angle = signed_angle_with_axis(va, vb, axis)
    return 2*pi + angle if angle < 0 else angle

def incenter(vecs):
    lengths = x = y = z = 0
    mid = len(vecs)//2+1
    for vi, vj, vk in zip(vecs, vecs[1:]+vecs[:1], vecs[mid:]+vecs[:mid]):
        length = (vj-vi).length
        lengths += length
        x += length*vk.x
        y += length*vk.y
        z += length*vk.z
    inc = Vector((x/lengths, y/lengths, z/lengths))
    return inc

# ------------------------------------------------------------------
# SCENE
# ------------------------------------------------------------------

def set_animatable_fix_handler(self, context):
    '''
    Prevent Blender Crashes with handlers
    '''
    old_handlers = []
    blender_handlers = bpy.app.handlers.render_init
    for h in blender_handlers:
        if "turn_off_animatable" in str(h):
            old_handlers.append(h)
    for h in old_handlers: blender_handlers.remove(h)
    blender_handlers.append(turn_off_animatable)
    return

def turn_off_animatable(scene):
    '''
    Prevent Blender Crashes with handlers
    '''
    for o in [o for o in bpy.data.objects if o.type == 'MESH']:
        o.tissue_tessellate.bool_run = False
        #if not o.reaction_diffusion_settings.bool_cache:
        #    o.reaction_diffusion_settings.run = False
        #except: pass
    return

# ------------------------------------------------------------------
# OBJECTS
# ------------------------------------------------------------------

def remove_temp_objects():
    # clean objects
    for o in bpy.data.objects:
        if "_tissue_tmp" in o.name:
            bpy.data.objects.remove(o)
    return

def convert_object_to_mesh(ob, apply_modifiers=True, preserve_status=True, mirror_correction = True):
    #mirror_correction = False
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
        if mirror_correction:
            me = simple_to_mesh_mirror(ob)
        else:
            me = simple_to_mesh(ob)
        new_ob = bpy.data.objects.new(ob.data.name, me)
        new_ob.location, new_ob.matrix_world = ob.location, ob.matrix_world
        if not apply_modifiers:
            for m,vis in zip(ob.modifiers,mod_visibility): m.show_viewport = vis
    else:
        if apply_modifiers:
            new_ob = ob.copy()
            if mirror_correction:
                new_me = simple_to_mesh_mirror(ob)
            else:
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

def simple_to_mesh_mirror(ob, depsgraph=None):
    '''
    Convert object to mesh applying Modifiers and Shape Keys.
    Automatically correct Faces rotation for Tessellations.
    '''
    if 'MIRROR' in [m.type for m in ob.modifiers]:

        _ob = ob.copy()
        _ob.name = _ob.name + "_mirror"
        bpy.context.collection.objects.link(_ob)
        # Store modifiers
        mods = list(_ob.modifiers)
        # Store visibility setting
        mods_vis = [m.show_viewport for m in _ob.modifiers]
        # Turn modifiers off
        for m in _ob.modifiers:
            m.show_viewport = False
        while True:
            if len(mods) == 0: break
            remove_mods = []

            for m, vis in zip(mods, mods_vis):
                m.show_viewport = vis
                remove_mods.append(m)
                if m.type == 'MIRROR' and vis:
                    n_axis = m.use_axis[0] + m.use_axis[1] + m.use_axis[2]
                    fraction = 2**n_axis
                    me = simple_to_mesh(_ob, depsgraph)
                    bm = bmesh.new()
                    bm.from_mesh(me)
                    bm.faces.ensure_lookup_table()
                    n_faces = len(bm.faces)
                    if n_axis > 0:
                        bm.faces.ensure_lookup_table()
                        rotate_faces = bm.faces
                        rot_index = []
                        if n_axis == 1: fraction_val = [0,1]
                        elif n_axis == 2: fraction_val = [0,1,1,0]
                        elif n_axis == 3: fraction_val = [0,1,1,0,1,0,0,1]
                        for i in fraction_val:
                            for j in range(n_faces//fraction):
                                rot_index.append(i)
                        for face, shift in zip(rotate_faces, rot_index):
                            if shift == 0: continue
                            vs = face.verts[:]
                            vs2 = vs[-shift:]+vs[:-shift]
                            material_index = face.material_index
                            bm.faces.remove(face)
                            f2 = bm.faces.new(vs2)
                            f2.select = True
                            f2.material_index = material_index
                            bm.normal_update()
                    bm.to_mesh(me)
                    bm.free()
                    for rm in remove_mods:
                        _ob.modifiers.remove(rm)
                        _ob.data = me
                        mods = mods[1:]
                        mods_vis = mods_vis[1:]
                    remove_mods = []
                    break
                if m == mods[-1]:
                    mods = []
                    me = simple_to_mesh(_ob, depsgraph)
                    _ob.data = me
                    _ob.modifiers.clear()
    else:
        me = simple_to_mesh(ob, depsgraph)
    return me

def simple_to_mesh(ob, depsgraph=None):
    '''
    Convert object to mesh applying Modifiers and Shape Keys
    '''
    #global evaluatedDepsgraph
    if depsgraph == None:
        if config.evaluatedDepsgraph == None:
            dg = bpy.context.evaluated_depsgraph_get()
        else: dg = config.evaluatedDepsgraph
    else:
        dg = depsgraph
    ob_eval = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ob_eval, preserve_all_data_layers=True, depsgraph=dg)
    #me.calc_normals()
    return me

def _join_objects(context, objects, link_to_scene=True, make_active=True):
    C = context
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

def join_objects(context, objects):
    generated_data = [o.data for o in objects]
    context.view_layer.update()
    for o in context.view_layer.objects:
        o.select_set(o in objects)
    bpy.ops.object.join()
    new_ob = context.view_layer.objects.active
    new_ob.select_set(True)
    for me in generated_data:
        if me != new_ob.data:
            bpy.data.meshes.remove(me)
    return new_ob

def join_objects(objects):
    new_ob = objects[0]
    override = {'active_object': new_ob, 'selected_editable_objects': objects}
    with bpy.context.temp_override(**override):
        bpy.ops.object.join()
    return new_ob

def repeat_mesh(me, n):
    '''
    Return Mesh data adding and applying an array without offset (Slower)
    '''
    bm = bmesh.new()
    for i in range(n): bm.from_mesh(me)
    new_me = me.copy()
    bm.to_mesh(new_me)
    bm.free()
    return new_me

def array_mesh(ob, n):
    '''
    Return Mesh data adding and applying an array without offset
    '''
    arr = ob.modifiers.new('Repeat','ARRAY')
    arr.relative_offset_displace[0] = 0
    arr.count = n
    #bpy.ops.object.modifier_apply({'active_object':ob},modifier='Repeat')
    #me = ob.data
    ob.modifiers.update()

    dg = bpy.context.evaluated_depsgraph_get()
    me = simple_to_mesh(ob, depsgraph=dg)
    ob.modifiers.remove(arr)
    return me

def array_mesh_object(ob, n):
    '''
    Return Mesh data adding and applying an array without offset
    '''
    arr = ob.modifiers.new('Repeat','ARRAY')
    arr.relative_offset_displace[0] = 0
    arr.count = n
    ob.modifiers.update()
    override = bpy.context.copy()
    override['active_object'] = ob
    override = {'active_object': ob}
    with bpy.context.temp_override(**override):
        bpy.ops.object.modifier_apply(modifier=arr.name)
    return ob


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
        if m.type in ('SUBSURF','MULTIRES'):
            hide_mods = [m]
            subs = m.levels
        elif m.type in not_allowed:
            subs = 0
            hide_mods = []
            mods_visibility = []
    for m in hide_mods: m.show_viewport = False
    me = simple_to_mesh_mirror(ob)
    for m, vis in zip(hide_mods,mods_visibility): m.show_viewport = vis
    return me, subs

# ------------------------------------------------------------------
# MESH FUNCTIONS
# ------------------------------------------------------------------

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

def get_patches____(me_low, me_high, sides, subs, bool_selection, bool_material_id, material_id):
    nv = len(me_low.vertices)       # number of vertices
    ne = len(me_low.edges)          # number of edges
    nf = len(me_low.polygons)       # number of polygons
    n = 2**subs + 1            # number of vertices along each patch edge
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
            shift_verts = np.roll(verts, -1, axis=1)[:,:,None]
            edge_keys = np.concatenate((shift_verts, verts[:,:,None]), axis=2)
            edge_keys.sort()

            edge_verts = np.array(me_low.edge_keys) # edges keys
            edges_index = np.zeros((ne,ne),dtype='int')
            edges_index[edge_verts[:,0],edge_verts[:,1]] = np.arange(ne)

            evi = np.arange(nevi) + nv
            evi = evi.reshape(ne,n-2)           # edges inner verts
            straight = np.arange(n-2)+1
            inverted = np.flip(straight)
            inners = np.array([[j*(n-2)+i for j in range(n-2)] for i in range(n-2)])

            ek1 = np.array(me_high.edge_keys)   # edges keys
            ids0 = np.arange(ne)*(n-1)      # edge keys highres
            keys0 = ek1[ids0]               # first inner edge
            keys1 = ek1[ids0 + n-2]         # last inner edge
            keys = np.concatenate((keys0,keys1))
            pick_verts = np.array((inverted,straight))

            patch_index = np.arange(nf)[:,None,None]

            # edge 0
            e0 = edge_keys[:,0]                             # get edge key (faces, 2)
            edge_id = edges_index[e0[:,0],e0[:,1]]          # edge index
            edge_verts = evi[edge_id]                       # indexes of inner vertices
            test = np.concatenate((verts[:,0,None], edge_verts[:,0,None]),axis=1)
            dir = (test[:,None] == keys).all(2).any(1).astype('int8')
            #dir = np.full(verts[:,0].shape, 0, dtype='int8')
            ids = pick_verts[dir][:,None,:]                           # indexes order along the side
            patches[patch_index,ids,0] = edge_verts[:,None,:]                   # assign indexes
            #patches[:,msk] = inverted # np.flip(patches[msk])

            # edge 1
            e0 = edge_keys[:,1]                             # get edge key (faces, 2)
            edge_id = edges_index[e0[:,0],e0[:,1]]          # edge index
            edge_verts = evi[edge_id]                       # indexes of inner vertices
            test = np.concatenate((verts[:,1,None], edge_verts[:,0,None]),axis=1)
            dir = (test[:,None] == keys).all(2).any(1).astype('int8')
            ids = pick_verts[dir][:,:,None]                           # indexes order along the side
            patches[patch_index,n-1,ids] = edge_verts[:,:,None]                   # assign indexes

            # edge 2
            e0 = edge_keys[:,2]                             # get edge key (faces, 2)
            edge_id = edges_index[e0[:,0],e0[:,1]]          # edge index
            edge_verts = evi[edge_id]                       # indexes of inner vertices
            test = np.concatenate((verts[:,3,None], edge_verts[:,0,None]),axis=1)
            dir = (test[:,None] == keys).all(2).any(1).astype('int8')
            ids = pick_verts[dir][:,None,:]                           # indexes order along the side
            patches[patch_index,ids,n-1] = edge_verts[:,None,:]                   # assign indexes

            # edge 3
            e0 = edge_keys[:,3]                             # get edge key (faces, 2)
            edge_id = edges_index[e0[:,0],e0[:,1]]          # edge index
            edge_verts = evi[edge_id]                       # indexes of inner vertices
            test = np.concatenate((verts[:,0,None], edge_verts[:,0,None]),axis=1)
            dir = (test[:,None] == keys).all(2).any(1).astype('int8')
            ids = pick_verts[dir][:,:,None]                           # indexes order along the side
            patches[patch_index,0,ids] = edge_verts[:,:,None]                   # assign indexes

            # fill inners
            patches[:,1:-1,1:-1] = inners[None,:,:] + ips[:,None,None]

    return patches, mask

def tessellate_prepare_component(ob1, props):
    mode = props['mode']
    bounds_x = props['bounds_x']
    bounds_y = props['bounds_y']
    scale_mode = props['scale_mode']
    normals_mode = props['normals_mode']
    zscale = props['zscale']
    offset = props['offset']
    use_origin_offset = props['use_origin_offset']
    bool_shapekeys = props['bool_shapekeys']

    thres = 0.005

    me1 = ob1.data

    # Component statistics
    n_verts = len(me1.vertices)

    # Component bounding box
    min_c = Vector((0, 0, 0))
    max_c = Vector((0, 0, 0))
    first = True
    for v in me1.vertices:
        vert = v.co
        if vert[0] < min_c[0] or first:
            min_c[0] = vert[0]
        if vert[1] < min_c[1] or first:
            min_c[1] = vert[1]
        if vert[2] < min_c[2] or first:
            min_c[2] = vert[2]
        if vert[0] > max_c[0] or first:
            max_c[0] = vert[0]
        if vert[1] > max_c[1] or first:
            max_c[1] = vert[1]
        if vert[2] > max_c[2] or first:
            max_c[2] = vert[2]
        first = False
    bb = max_c - min_c

    # adaptive XY
    verts1 = []
    for v in me1.vertices:
        if mode == 'BOUNDS':
            vert = v.co - min_c  # (ob1.matrix_world * v.co) - min_c
            if use_origin_offset: vert[2] = v.co[2]
            vert[0] = vert[0] / bb[0] if bb[0] != 0 else 0.5
            vert[1] = vert[1] / bb[1] if bb[1] != 0 else 0.5
            if scale_mode == 'CONSTANT' or normals_mode in ('OBJECT', 'SHAPEKEYS'):
                if not use_origin_offset:
                    vert[2] = vert[2] / bb[2] if bb[2] != 0 else 0
                    vert[2] = vert[2] - 0.5 + offset * 0.5
            else:
                if not use_origin_offset:
                    vert[2] = vert[2] + (-0.5 + offset * 0.5) * bb[2]
            vert[2] *= zscale
        elif mode == 'LOCAL':
            vert = v.co.xyz
            vert[2] *= zscale
            #vert[2] = (vert[2] - min_c[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
        elif mode == 'GLOBAL':
            vert = ob1.matrix_world @ v.co
            vert[2] *= zscale
            try:
                for sk in me1.shape_keys.key_blocks:
                    sk.data[v.index].co = ob1.matrix_world @ sk.data[v.index].co
            except: pass
        v.co = vert

    # ShapeKeys
    if bool_shapekeys and ob1.data.shape_keys:
        for sk in ob1.data.shape_keys.key_blocks:
            source = sk.data
            _sk_uv_quads = [0]*len(verts1)
            _sk_uv = [0]*len(verts1)
            for i, sk_v in enumerate(source):
                if mode == 'BOUNDS':
                    sk_vert = sk_v.co - min_c
                    if use_origin_offset: sk_vert[2] = sk_v.co[2]
                    sk_vert[0] = (sk_vert[0] / bb[0] if bb[0] != 0 else 0.5)
                    sk_vert[1] = (sk_vert[1] / bb[1] if bb[1] != 0 else 0.5)
                    if scale_mode == 'CONSTANT' or normals_mode in ('OBJECT', 'SHAPEKEYS'):
                        if not use_origin_offset:
                            sk_vert[2] = (sk_vert[2] / bb[2] if bb[2] != 0 else sk_vert[2])
                            sk_vert[2] = sk_vert[2] - 0.5 + offset * 0.5
                    else:
                        if not use_origin_offset:
                            sk_vert[2] = sk_vert[2] + (- 0.5 + offset * 0.5) * bb[2]
                    sk_vert[2] *= zscale
                elif mode == 'LOCAL':
                    sk_vert = sk_v.co
                    sk_vert[2] *= zscale
                elif mode == 'GLOBAL':
                    sk_vert = sk_v.co
                    sk_vert[2] *= zscale
                sk_v.co = sk_vert

    if mode != 'BOUNDS' and (bounds_x != 'EXTEND' or bounds_y != 'EXTEND'):
        ob1.active_shape_key_index = 0
        bm = bmesh.new()
        bm.from_mesh(me1)
        # Bound X
        planes_co = []
        planes_no = []
        bounds = []
        if bounds_x != 'EXTEND':
            planes_co += [(0,0,0), (1,0,0)]
            planes_no += [(-1,0,0), (1,0,0)]
            bounds += [bounds_x, bounds_x]
        if bounds_y != 'EXTEND':
            planes_co += [(0,0,0), (0,1,0)]
            planes_no += [(0,-1,0), (0,1,0)]
            bounds += [bounds_y, bounds_y]
        for co, norm, bound in zip(planes_co, planes_no, bounds):
            count = 0
            while True:
                moved = 0
                original_edges = list(bm.edges)
                geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
                bisect = bmesh.ops.bisect_plane(bm, geom=geom, dist=0,
                    plane_co=co, plane_no=norm, use_snap_center=False,
                    clear_outer=bound=='CLIP', clear_inner=False
                    )
                geom = bisect['geom']
                cut_edges = [g for g in bisect['geom_cut'] if type(g)==bmesh.types.BMEdge]
                cut_verts = [g for g in bisect['geom_cut'] if type(g)==bmesh.types.BMVert]

                if True or bound!='CLIP':
                    for e in cut_edges:
                        seam = True
                        # Prevent glitches
                        '''
                        for e1 in original_edges:
                            match_00 = (e.verts[0].co-e1.verts[0].co).length < thres
                            match_11 = (e.verts[1].co-e1.verts[1].co).length < thres
                            match_01 = (e.verts[0].co-e1.verts[1].co).length < thres
                            match_10 = (e.verts[1].co-e1.verts[0].co).length < thres
                            if (match_00 and match_11) or (match_01 and match_10):
                                seam = False
                                break
                        '''
                        e.seam = seam

                if bound == 'CYCLIC':
                    geom_verts = []
                    if norm == (-1,0,0):
                        geom_verts = [v for v in bm.verts if v.co.x < 0]
                    if norm == (1,0,0):
                        geom_verts = [v for v in bm.verts if v.co.x > 1]
                    if norm == (0,-1,0):
                        geom_verts = [v for v in bm.verts if v.co.y < 0]
                    if norm == (0,1,0):
                        geom_verts = [v for v in bm.verts if v.co.y > 1]
                    if len(geom_verts) > 0:
                        geom = bmesh.ops.region_extend(bm, geom=geom_verts,
                            use_contract=False, use_faces=False, use_face_step=True
                            )
                        geom = bmesh.ops.split(bm, geom=geom['geom'], use_only_faces=False)
                        vec = Vector(norm)
                        move_verts = [g for g in geom['geom'] if type(g)==bmesh.types.BMVert]
                        bmesh.ops.translate(bm, vec=-vec, verts=move_verts)
                        for key in bm.verts.layers.shape.keys():
                            sk = bm.verts.layers.shape.get(key)
                            for v in move_verts:
                                v[sk] -= vec
                        moved += len(move_verts)
                count += 1
                if moved == 0 or count > 1000: break
        bm.to_mesh(me1)

    com_area = bb[0]*bb[1]
    return ob1, com_area

def get_quads(me, bool_selection):
    nf = len(me.polygons)

    verts = []
    materials = []
    mask = []
    for poly in me.polygons:
        p = list(poly.vertices)
        sides = len(p)
        if sides == 3:
            verts.append([[p[0], p[-1]], [p[1], p[2]]])
            materials.append(poly.material_index)
            mask.append(poly.select if bool_selection else True)
        elif sides == 4:
            verts.append([[p[0], p[3]], [p[1], p[2]]])
            materials.append(poly.material_index)
            mask.append(poly.select if bool_selection else True)
        else:
            while True:
                new_poly = [[p[-2], p.pop(-1)], [p[1], p.pop(0)]]
                verts.append(new_poly)
                materials.append(poly.material_index)
                mask.append(poly.select if bool_selection else True)
                if len(p) < 3: break
    mask = np.array(mask)
    materials = np.array(materials)[mask]
    verts = np.array(verts)[mask]
    return verts, mask, materials

def get_patches(me_low, me_high, sides, subs, bool_selection): #, bool_material_id, material_id):
    nv = len(me_low.vertices)       # number of vertices
    ne = len(me_low.edges)          # number of edges
    nf = len(me_low.polygons)       # number of polygons
    n = 2**subs + 1
    nev = ne * n               # number of vertices along the subdivided edges
    nevi = nev - 2*ne          # internal vertices along subdividede edges

    n0 = 2**(subs-1) - 1

    # filtered polygonal faces
    poly_sides = [0]*nf
    me_low.polygons.foreach_get('loop_total',poly_sides)
    poly_sides = np.array(poly_sides)
    mask = poly_sides == sides

    if bool_selection:
        mask_selection = [True]*nf
        me_low.polygons.foreach_get('select',mask_selection)
        mask = np.array(mask_selection)

    materials = [1]*nf
    me_low.polygons.foreach_get('material_index',materials)
    materials = np.array(materials)[mask]

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
        patches = np.empty((nf,n,n),dtype='int')
        verts = [list(p.vertices) for p in polys if len(p.vertices) == sides]
        verts = np.array(verts).reshape((-1,sides))

        # filling corners

        patches[:,0,0] = verts[:,0]
        patches[:,n-1,0] = verts[:,1]
        patches[:,n-1,n-1] = verts[:,2]
        patches[:,0,n-1] = verts[:,3]

        if subs != 0:
            shift_verts = np.roll(verts, -1, axis=1)[:,:,None]
            edge_keys = np.concatenate((shift_verts, verts[:,:,None]), axis=2)
            edge_keys.sort()

            edge_verts = np.array(me_low.edge_keys)         # edges keys
            edges_index = np.empty((ne,ne),dtype='int')
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
            edges_dir = np.zeros((nev,nev),dtype='bool')    # Better memory usage
            #edges_dir = np.zeros((nev,nev),dtype='int8')     ### Memory usage not efficient, dictionary as alternative?
            edges_dir[keys0[:,0], keys0[:,1]] = 1
            edges_dir[keys1[:,0], keys1[:,1]] = 1
            pick_verts = np.array((inverted,straight))

            patch_index = np.arange(nf)[:,None,None]

            # edge 0
            e0 = edge_keys[:,0]                             # get edge key (faces, 2)
            edge_id = edges_index[e0[:,0],e0[:,1]]          # edge index
            edge_verts = evi[edge_id]                       # indexes of inner vertices
            dir = edges_dir[verts[:,0], edge_verts[:,0]]    # check correct direction
            ids = pick_verts[dir.astype('int8')][:,None,:]                           # indexes order along the side
            patches[patch_index,ids,0] = edge_verts[:,None,:]                   # assign indexes

            # edge 1
            e0 = edge_keys[:,1]                             # get edge key (faces, 2)
            edge_id = edges_index[e0[:,0],e0[:,1]]          # edge index
            edge_verts = evi[edge_id]                       # indexes of inner vertices
            dir = edges_dir[verts[:,1], edge_verts[:,0]]       # check correct direction
            ids = pick_verts[dir.astype('int8')][:,:,None]                           # indexes order along the side
            patches[patch_index,n-1,ids] = edge_verts[:,:,None]                   # assign indexes

            # edge 2
            e0 = edge_keys[:,2]                             # get edge key (faces, 2)
            edge_id = edges_index[e0[:,0],e0[:,1]]          # edge index
            edge_verts = evi[edge_id]                       # indexes of inner vertices
            dir = edges_dir[verts[:,3], edge_verts[:,0]]       # check correct direction
            ids = pick_verts[dir.astype('int8')][:,None,:]                           # indexes order along the side
            patches[patch_index,ids,n-1] = edge_verts[:,None,:]                   # assign indexes

            # edge 3
            e0 = edge_keys[:,3]                             # get edge key (faces, 2)
            edge_id = edges_index[e0[:,0],e0[:,1]]          # edge index
            edge_verts = evi[edge_id]                       # indexes of inner vertices
            dir = edges_dir[verts[:,0], edge_verts[:,0]]       # check correct direction
            ids = pick_verts[dir.astype('int8')][:,:,None]                           # indexes order along the side
            patches[patch_index,0,ids] = edge_verts[:,:,None]                   # assign indexes

            # fill inners
            patches[:,1:-1,1:-1] = inners[None,:,:] + ips[:,None,None]

    return patches, mask, materials

def get_vertices_numpy(mesh):
    '''
    Create a numpy array with the vertices of a given mesh
    '''
    n_verts = len(mesh.vertices)
    verts = [0]*n_verts*3
    mesh.vertices.foreach_get('co', verts)
    verts = np.array(verts).reshape((n_verts,3))
    return verts

def get_vertices_and_normals_numpy(mesh):
    '''
    Create two numpy arrays with the vertices and the normals of a given mesh
    '''
    n_verts = len(mesh.vertices)
    verts = [0]*n_verts*3
    normals = [0]*n_verts*3
    mesh.vertices.foreach_get('co', verts)
    mesh.vertices.foreach_get('normal', normals)
    verts = np.array(verts).reshape((n_verts,3))
    normals = np.array(normals).reshape((n_verts,3))
    return verts, normals

def get_normals_numpy(mesh):
    '''
    Create a numpy array with the normals of a given mesh
    '''
    n_verts = len(mesh.vertices)
    normals = [0]*n_verts*3
    mesh.vertices.foreach_get('normal', normals)
    normals = np.array(normals).reshape((n_verts,3))
    return normals

def get_edges_numpy(mesh):
    '''
    Create a numpy array with the edges of a given mesh
    '''
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

def get_edges_numpy_ex(mesh):
    '''
    Create a numpy array with the edges of a given mesh, or all the possible
    between the vertices of a same face
    '''
    edges_verts = get_edges_numpy(mesh)
    polygons_diag = []
    for f in mesh.polygons:
        sides = len(f.vertices)
        if sides < 4: continue
        for i in range(sides-2):
            v0 = f.vertices[i]
            for j in range(i+2, sides-1 if i == 0 else sides):
                v1 = f.vertices[j]
                polygons_diag.append((v0,v1))
    if len(polygons_diag) == 0:
        return edges_verts
    polygons_diag = np.array(polygons_diag,dtype=np.int32)
    return np.concatenate((edges_verts, polygons_diag), axis=0)

def get_polygons_select_numpy(mesh):
    n_polys = len(mesh.polygons)
    selections = [0]*n_polys*2
    mesh.polygons.foreach_get('select', selections)
    selections = np.array(selections)
    return selections

def get_attribute_numpy(elements_list, attribute='select', mult=1, size=None):
    '''
    Generate a numpy array getting attribute from a list of element using
    the foreach_get() function.
    '''
    if size:
        n_elements = size
    else:
        n_elements = len(elements_list)
    values = np.zeros(int(n_elements*mult))
    elements_list.foreach_get(attribute, values)
    values = np.array(values)
    if mult > 1: values = values.reshape((n_elements,mult))
    return values

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

def find_curves_attribute(edges, n_verts, attribute):
    # dictionary with a list for every point
    verts_dict = {key:[] for key in range(n_verts)}
    # get neighbors for every point
    for e in edges:
        verts_dict[e[0]].append(e[1])
        verts_dict[e[1]].append(e[0])
    curves = []
    ordered_attr = []
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
        attr = []
        if len(v01) > 1:
            curve.append(v01[1])    # add neighbors
            attr.append(attribute[v01[1]])    # add neighbors
        curve.append(v)         # add starting point
        attr.append(attribute[v])
        curve.append(v01[0])    # add neighbors
        attr.append(attribute[v01[0]])
        verts_dict.pop(v)
        # start building curve
        while True:
            #last_point = curve[-1]
            #if last_point not in verts_dict: break

            # try to change direction if needed
            if curve[-1] in verts_dict: pass
            elif curve[0] in verts_dict:
                curve.reverse()
                attr.reverse()
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
            ordered_attr.append(attr)
            verts_dict.pop(last_point)
            if curve[0] == curve[-1]:
                verts_dict.pop(new_point)
                break
        if(len(curve)>0):
            curves.append(curve)
    return curves, ordered_attr

def curve_from_points(points, name='Curve'):
    curve = bpy.data.curves.new(name,'CURVE')
    for c in points:
        s = curve.splines.new('POLY')
        s.points.add(len(c))
        for i,p in enumerate(c): s.points[i].co = p.xyz + [1]
    ob_curve = bpy.data.objects.new(name,curve)
    return ob_curve

def curve_from_pydata(points, radii, indexes, name='Curve', skip_open=False, merge_distance=1, set_active=True, only_data=False, curve=None, spline_type='POLY'):
    if not curve:
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
            dist = np.linalg.norm(np.array(pts1-pts, dtype=np.float64), axis=1)
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
        s = curve.splines.new(spline_type)
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

def update_curve_from_pydata_simple(curve, points, radii, indexes, skip_open=False, merge_distance=1, set_active=True, only_data=False, spline_type='POLY'):
    curve.splines.clear()
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
        s = curve.splines.new(spline_type)
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

def update_curve_from_pydata(curve, points, normals, radii, indexes, merge_distance=1, pattern=[1,0], depth=0.1, offset=0):
    curve.splines.clear()
    use_rad = True
    for ic, c in enumerate(indexes):
        bool_cyclic = c[0] == c[-1]
        if bool_cyclic: c.pop(-1)

        # cleanup
        pts = np.array([points[i] for i in c if i != None])
        nor = np.array([normals[i] for i in c if i != None])
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
            nor = nor[mask]
            if use_rad: rad = rad[mask]
        #if skip_open and not bool_cyclic: continue
        n_pts = len(pts)
        series = np.arange(n_pts)
        if pattern[0]*pattern[1] != 0:
            patt1 = series + (series-series%pattern[1])/pattern[1]*pattern[0]+pattern[0]
            patt1 = patt1[patt1<n_pts].astype('int')
            patt0 = series + (series-series%pattern[0])/pattern[0]*pattern[1]
            patt0 = patt0[patt0<n_pts].astype('int')
            nor[patt0] *= 0.5*depth*(1 + offset)
            nor[patt1] *= 0.5*depth*(-1 + offset)
            pts += nor
        s = curve.splines.new('POLY')
        s.points.add(n_pts-1)
        w = np.ones(n_pts).reshape((n_pts,1))
        co = np.concatenate((pts,w),axis=1).reshape((n_pts*4))
        s.points.foreach_set('co',co)
        if use_rad: s.points.foreach_set('radius',rad)
        s.use_cyclic_u = bool_cyclic

def loops_from_bmesh(edges):
    """
    Return one or more loops given some starting edges.
    :arg edges: Edges used as seeds.
    :type edges: List of :class:'bmesh.types.BMEdge'
    :return: Elements in each loop (Verts, Edges), where:
        - Verts - List of Lists of :class:'bmesh.types.BMVert'
        - Edges - List of Lists of :class:'bmesh.types.BMEdge'
    :rtype: tuple
    """
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
    """
    Return vertices and edges along a loop in a specific direction.
    :arg edge: Edges used as seed.
    :type edges: :class:'bmesh.types.BMEdge'
    :arg edge: Vertex of the Edge used for the direction.
    :type vert: :class:'bmesh.types.BMVert'
    :return: Elements in the loop (Verts, Edges), where:
        - Verts - List of :class:'bmesh.types.BMVert'
        - Edges - List of :class:'bmesh.types.BMEdge'
    :rtype: tuple
    """
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
            if len(link_faces) == 0: break
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
    """
    Return vertices and edges along a loop in both directions.
    :arg edge: Edges used as seed.
    :type edges: :class:'bmesh.types.BMEdge'
    :return: Elements in the loop (Verts, Edges), where:
        - Verts - List of :class:'bmesh.types.BMVert'
        - Edges - List of :class:'bmesh.types.BMEdge'
    :rtype: tuple
    """
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
    """
    Curve data from given vertices.
    :arg indexes: List of Lists of indexes of the vertices.
    :type indexes: List of Lists of int
    :arg verts: List of vertices.
    :type verts: List of :class:'bpy.types.MeshVertex'
    :arg name: Name of the Curve data.
    :type name: str
    :return: Generated Curve data
    :rtype: :class:'bpy.types.Curve'
    """
    curve = bpy.data.curves.new(name,'CURVE')
    for c in indexes:
        s = curve.splines.new('POLY')
        s.points.add(len(c))
        for i,p in enumerate(c):
            s.points[i].co = verts[p].co.xyz + [1]
            #s.points[i].tilt = degrees(asin(verts[p].co.z))
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

# ------------------------------------------------------------------
# VERTEX GROUPS AND WEIGHT
# ------------------------------------------------------------------

def get_weight(vertex_group, n_verts):
    """
    Read weight values from given Vertex Group.
    :arg vertex_group: Vertex Group.
    :type vertex_group: :class:'bpy.types.VertexGroup'
    :arg n_verts: Number of Vertices (output list size).
    :type n_verts: int
    :return: Readed weight values.
    :rtype: list
    """
    weight = [0]*n_verts
    for i in range(n_verts):
        try: weight[i] = vertex_group.weight(i)
        except: pass
    return weight

def get_weight_numpy(vertex_group, n_verts):
    """
    Read weight values from given Vertex Group.
    :arg vertex_group: Vertex Group.
    :type vertex_group: :class:'bpy.types.VertexGroup'
    :arg n_verts: Number of Vertices (output list size).
    :type n_verts: int
    :return: Readed weight values as numpy array.
    :rtype: :class:'numpy.ndarray'
    """
    weight = np.zeros(n_verts)
    for i in range(n_verts):
        try: weight[i] = vertex_group.weight(i)
        except: pass
    return weight

def bmesh_get_weight_numpy(group_index, layer, verts, normalized=False):
    weight = np.zeros(len(verts))
    for i, v in enumerate(verts):
        dvert = v[layer]
        if group_index in dvert:
            weight[i] = dvert[group_index]
            #dvert[group_index] = 0.5
    if normalized:
        weight = (weight - np.min(weight))/np.ptp(weight)
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

def set_weight_numpy(vg, weight):
    for i, w in enumerate(weight):
        vg.add([i], w, 'REPLACE')
    return vg

def uv_from_bmesh(bm, uv_index=None):
    if uv_index:
        uv_lay = bm.loops.layers.uv[uv_index]
    else:
        uv_lay = bm.loops.layers.uv.active
    uv_co = [0]*len(bm.verts)

    for face in bm.faces:
        for vert,loop in zip(face.verts, face.loops):
            uv_co[vert.index] = loop[uv_lay].uv
    return uv_co

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

def fill_neighbors_attribute(verts,weight,attribute):
    neigh = {}
    for v0 in verts:
        for f in v0.link_faces:
            for v1 in f.verts:
                if attribute == 'GEODESIC':
                    dist = weight[v0.index] + (v0.co-v1.co).length
                elif attribute == 'TOPOLOGY':
                    dist = weight[v0.index] + 1.0
                w1 = weight[v1.index]
                if w1 == None or w1 > dist:
                    weight[v1.index] = dist
                    neigh[v1] = 0
    if len(neigh) == 0: return weight
    else: return fill_neighbors_attribute(neigh.keys(), weight, attribute)

# ------------------------------------------------------------------
# MODIFIERS
# ------------------------------------------------------------------

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


def recurLayerCollection(layerColl, collName):
    '''
    Recursivly transverse layer_collection for a particular name.
    '''
    found = None
    if (layerColl.name == collName):
        return layerColl
    for layer in layerColl.children:
        found = recurLayerCollection(layer, collName)
        if found:
            return found

def auto_layer_collection():
    '''
    Automatically change active layer collection.
    '''
    layer = bpy.context.view_layer.active_layer_collection
    layer_collection = bpy.context.view_layer.layer_collection
    if layer.hide_viewport or layer.collection.hide_viewport:
        collections = bpy.context.object.users_collection
        for c in collections:
            lc = recurLayerCollection(layer_collection, c.name)
            if not c.hide_viewport and not lc.hide_viewport:
                bpy.context.view_layer.active_layer_collection = lc

def np_remap_image_values(img, channel=0, min=0, max=1, invert=False):
    nx = img.size[1]
    ny = img.size[0]
    px = np.float32(np.zeros(nx*ny*4))
    img.pixels.foreach_get(px)
    px = np.array(px).reshape((-1,4))
    values = px[:,channel]
    values = values.reshape((nx,ny))
    if invert:
        values = 1-values
    return min + values*(max-min)
