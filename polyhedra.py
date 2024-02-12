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

# ---------------------------- ADAPTIVE DUPLIFACES --------------------------- #
# ------------------------------- version 0.84 ------------------------------- #
#                                                                              #
# Creates duplicates of selected mesh to active morphing the shape according   #
# to target faces.                                                             #
#                                                                              #
#                    (c)  Alessandro Zomparelli                                #
#                             (2017)                                           #
#                                                                              #
# http://www.co-de-it.com/                                                     #
#                                                                              #
# ############################################################################ #


import bpy
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
        PointerProperty
        )
from mathutils import Vector, Quaternion, Matrix
import numpy as np
from math import *
import random, time, copy
import bmesh
from .utils import *

def anim_polyhedra_active(self, context):
    ob = context.object
    props = ob.tissue_polyhedra
    if ob.tissue.tissue_type=='POLYHEDRA' and not ob.tissue.bool_lock:
        props.object.name
        bpy.ops.object.tissue_update_polyhedra()

class tissue_polyhedra_prop(PropertyGroup):
    object : PointerProperty(
        type=bpy.types.Object,
        name="Object",
        description="Source object",
        update = anim_polyhedra_active
        )

    mode : EnumProperty(
        items=(
                ('POLYHEDRA', "Polyhedra", "Polyhedral Complex Decomposition, the result are disconnected polyhedra geometries"),
                ('WIREFRAME', "Wireframe", "Polyhedral Wireframe through edges tickening")
                ),
        default='POLYHEDRA',
        name="Polyhedra Mode",
        update = anim_polyhedra_active
        )

    bool_modifiers : BoolProperty(
        name="Use Modifiers",
        description="",
        default=True,
        update = anim_polyhedra_active
        )

    dissolve : EnumProperty(
        items=(
                ('NONE', "None", "Keeps original topology"),
                ('INNER', "Inner", "Dissolve inner loops"),
                ('OUTER', "Outer", "Dissolve outer loops")
                ),
        default='NONE',
        name="Dissolve",
        update = anim_polyhedra_active
        )

    thickness : FloatProperty(
        name="Thickness", default=1, soft_min=0, soft_max=10,
        description="Thickness along the edges",
        update = anim_polyhedra_active
        )

    crease : FloatProperty(
        name="Crease", default=0, min=0, max=1,
        description="Crease Inner Loops",
        update = anim_polyhedra_active
        )

    segments : IntProperty(
        name="Segments",
        default=0,
        min=1,
        soft_max=20,
        description="Segments for every edge",
        update = anim_polyhedra_active
        )

    proportional_segments : BoolProperty(
        name="Proportional Segments", default=True,
        description="The number of segments is proportional to the length of the edges",
        update = anim_polyhedra_active
        )

    selective_wireframe : EnumProperty(
        name="Selective",
        items=(
                ('NONE', "None", "Apply wireframe to every cell"),
                ('THICKNESS', "Thickness", "Wireframe only on bigger cells compared to the thickness"),
                ('AREA', "Area", "Wireframe based on cells dimensions"),
                ('WEIGHT', "Weight", "Wireframe based on vertex groups")
                ),
        default='NONE',
        update = anim_polyhedra_active
        )

    thickness_threshold_correction : FloatProperty(
        name="Correction", default=1, min=0, soft_max=2,
        description="Adjust threshold based on thickness",
        update = anim_polyhedra_active
        )

    area_threshold : FloatProperty(
        name="Threshold", default=0, min=0, soft_max=10,
        description="Use only faces with an area greater than the threshold",
        update = anim_polyhedra_active
        )

    thicken_all : BoolProperty(
        name="Thicken all",
        description="Thicken original faces as well",
        default=True,
        update = anim_polyhedra_active
        )

    vertex_group_thickness : StringProperty(
            name="Thickness weight", default='',
            description="Vertex Group used for thickness",
            update = anim_polyhedra_active
            )
    invert_vertex_group_thickness : BoolProperty(
            name="Invert", default=False,
            description="Invert the vertex group influence",
            update = anim_polyhedra_active
            )
    vertex_group_thickness_factor : FloatProperty(
            name="Factor",
            default=0,
            min=0,
            max=1,
            description="Thickness factor to use for zero vertex group influence",
            update = anim_polyhedra_active
            )

    vertex_group_selective : StringProperty(
            name="Thickness weight", default='',
            description="Vertex Group used for selective wireframe",
            update = anim_polyhedra_active
            )
    invert_vertex_group_selective : BoolProperty(
            name="Invert", default=False,
            description="Invert the vertex group influence",
            update = anim_polyhedra_active
            )
    vertex_group_selective_threshold : FloatProperty(
            name="Threshold",
            default=0.5,
            min=0,
            max=1,
            description="Selective wireframe threshold",
            update = anim_polyhedra_active
            )
    bool_smooth : BoolProperty(
            name="Smooth Shading",
            default=False,
            description="Output faces with smooth shading rather than flat shaded",
            update = anim_polyhedra_active
            )

    error_message : StringProperty(
        name="Error Message",
        default=""
        )

class polyhedral_wireframe(Operator):
    bl_idname = "object.polyhedral_wireframe"
    bl_label = "Tissue Polyhedral Wireframe"
    bl_description = "Generate wireframes around the faces.\
                      \nDoesn't works with boundary edges.\
                      \n(Experimental)"
    bl_options = {'REGISTER', 'UNDO'}

    thickness : FloatProperty(
        name="Thickness", default=0.1, min=0.001, soft_max=200,
        description="Wireframe thickness"
        )

    crease : FloatProperty(
        name="Crease", default=0, min=0, max=1,
        description="Crease Inner Loops"
        )

    segments : IntProperty(
        name="Segments", default=1, min=1, soft_max=10,
        description="Segments for every edge"
        )

    proportional_segments : BoolProperty(
        name="Proportional Segments", default=True,
        description="The number of segments is proportional to the length of the edges"
        )

    mode : EnumProperty(
        items=(
                ('POLYHEDRA', "Polyhedra", "Polyhedral Complex Decomposition, the result are disconnected polyhedra geometries"),
                ('WIREFRAME', "Wireframe", "Polyhedral Wireframe through edges tickening")
                ),
        default='POLYHEDRA',
        name="Polyhedra Mode"
        )

    dissolve : EnumProperty(
        items=(
                ('NONE', "None", "Keeps original topology"),
                ('INNER', "Inner", "Dissolve inner loops"),
                ('OUTER', "Outer", "Dissolve outer loops")
                ),
        default='NONE',
        name="Dissolve"
        )

    selective_wireframe : EnumProperty(
        items=(
                ('NONE', "None", "Apply wireframe to every cell"),
                ('THICKNESS', "Thickness", "Wireframe only on bigger cells compared to the thickness"),
                ('AREA', "Area", "Wireframe based on cells dimensions"),
                ('WEIGHT', "Weight", "Wireframe based on vertex groups")
                ),
        default='NONE',
        name="Selective"
        )

    thickness_threshold_correction : FloatProperty(
        name="Correction", default=1, min=0, soft_max=2,
        description="Adjust threshold based on thickness"
        )

    area_threshold : FloatProperty(
        name="Threshold", default=0, min=0, soft_max=10,
        description="Use only faces with an area greater than the threshold"
        )

    thicken_all : BoolProperty(
        name="Thicken all",
        description="Thicken original faces as well",
        default=True
        )

    vertex_group_thickness : StringProperty(
        name="Thickness weight", default='',
        description="Vertex Group used for thickness"
        )

    invert_vertex_group_thickness : BoolProperty(
        name="Invert", default=False,
        description="Invert the vertex group influence"
        )

    vertex_group_thickness_factor : FloatProperty(
        name="Factor",
        default=0,
        min=0,
        max=1,
        description="Thickness factor to use for zero vertex group influence"
        )

    vertex_group_selective : StringProperty(
        name="Thickness weight", default='',
        description="Vertex Group used for thickness"
        )

    invert_vertex_group_selective : BoolProperty(
        name="Invert", default=False,
        description="Invert the vertex group influence"
        )

    vertex_group_selective_threshold : FloatProperty(
        name="Threshold",
        default=0.5,
        min=0,
        max=1,
        description="Selective wireframe threshold"
        )

    bool_smooth : BoolProperty(
        name="Smooth Shading",
        default=False,
        description="Output faces with smooth shading rather than flat shaded"
        )

    bool_hold : BoolProperty(
            name="Hold",
            description="Wait...",
            default=False
        )

    def draw(self, context):
        ob = context.object
        layout = self.layout
        col = layout.column(align=True)
        self.bool_hold = True
        if self.mode == 'WIREFRAME':
            col.separator()
            col.prop(self, "thickness")
            col.separator()
            col.prop(self, "segments")
        return

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        ob0 = context.object

        self.object_name = "Polyhedral Wireframe"
        # Check if existing object with same name
        names = [o.name for o in bpy.data.objects]
        if self.object_name in names:
            count_name = 1
            while True:
                test_name = self.object_name + '.{:03d}'.format(count_name)
                if not (test_name in names):
                    self.object_name = test_name
                    break
                count_name += 1

        if ob0.type not in ('MESH'):
            message = "Source object must be a Mesh!"
            self.report({'ERROR'}, message)

        if bpy.ops.object.select_all.poll():
            bpy.ops.object.select_all(action='TOGGLE')
        bpy.ops.object.mode_set(mode='OBJECT')

        bool_update = False
        auto_layer_collection()
        new_ob = convert_object_to_mesh(ob0,False,False)
        new_ob.data.name = self.object_name
        new_ob.name = self.object_name

        # Store parameters
        props = new_ob.tissue_polyhedra
        lock_status = new_ob.tissue.bool_lock
        new_ob.tissue.bool_lock = True
        props.mode = self.mode
        props.thickness = self.thickness
        props.segments = self.segments
        props.dissolve = self.dissolve
        props.proportional_segments = self.proportional_segments
        props.crease = self.crease
        props.object = ob0

        new_ob.tissue.tissue_type = 'POLYHEDRA'
        try: bpy.ops.object.tissue_update_polyhedra()
        except RuntimeError as e:
            bpy.data.objects.remove(new_ob)
            remove_temp_objects()
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        if not bool_update:
            self.object_name = new_ob.name
            new_ob.location = ob0.location
            new_ob.matrix_world = ob0.matrix_world

        # Assign collection of the base object
        old_coll = new_ob.users_collection
        if old_coll != ob0.users_collection:
            for c in old_coll:
                c.objects.unlink(new_ob)
            for c in ob0.users_collection:
                c.objects.link(new_ob)
        context.view_layer.objects.active = new_ob

        # unlock
        new_ob.tissue.bool_lock = lock_status

        return {'FINISHED'}

class tissue_update_polyhedra(Operator):
    bl_idname = "object.tissue_update_polyhedra"
    bl_label = "Tissue Update Polyhedral Wireframe"
    bl_description = "Update a previously generated polyhedral object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.object
        tissue_time(None,'Tissue: Polyhedral Wireframe of "{}"...'.format(ob.name), levels=0)
        start_time = time.time()
        begin_time = time.time()
        props = ob.tissue_polyhedra
        thickness = props.thickness

        merge_dist = thickness*0.0001

        subs = props.segments
        if props.mode == 'POLYHEDRA': subs = 1


        # Source mesh
        ob0 = props.object
        if props.bool_modifiers:
            me = simple_to_mesh(ob0)
        else:
            me = ob0.data.copy()

        bm = bmesh.new()
        bm.from_mesh(me)

        pre_processing(bm)
        polyhedral_subdivide_edges(bm, subs, props.proportional_segments)
        tissue_time(start_time,'Subdivide edges',levels=1)
        start_time = time.time()

        thickness = np.ones(len(bm.verts))*props.thickness
        if(props.vertex_group_thickness in ob.vertex_groups.keys()):
            dvert_lay = bm.verts.layers.deform.active
            group_index_thickness = ob.vertex_groups[props.vertex_group_thickness].index
            thickness_weight = bmesh_get_weight_numpy(group_index_thickness, dvert_lay, bm.verts)
            if 'invert_vertex_group_thickness' in props.keys():
                if props['invert_vertex_group_thickness']:
                    thickness_weight = 1-thickness_weight
            fact = 0
            if 'vertex_group_thickness_factor' in props.keys():
                fact = props['vertex_group_thickness_factor']
            if fact > 0:
                thickness_weight = thickness_weight*(1-fact) + fact
            thickness *= thickness_weight
        thickness_dict = dict(zip([tuple(v.co) for v in bm.verts],thickness))

        bm1 = get_double_faces_bmesh(bm)
        polyhedra = get_decomposed_polyhedra(bm)
        if(type(polyhedra) is str):
            bm.free()
            bm1.free()
            self.report({'ERROR'}, polyhedra)
            return {'CANCELLED'}

        selective_dict = None
        accurate = False
        if props.selective_wireframe == 'THICKNESS':
            filter_faces = True
            accurate = True
            area_threshold = (thickness*props.thickness_threshold_correction)**2
        elif props.selective_wireframe == 'AREA':
            filter_faces = True
            area_threshold = props.area_threshold
        elif props.selective_wireframe == 'WEIGHT':
            filter_faces = True
            if(props.vertex_group_selective in ob.vertex_groups.keys()):
                dvert_lay = bm.verts.layers.deform.active
                group_index_selective = ob.vertex_groups[props.vertex_group_selective].index
                thresh = props.vertex_group_selective_threshold
                selective_weight = bmesh_get_weight_numpy(group_index_selective, dvert_lay, bm.verts)
                selective_weight = selective_weight >= thresh
                invert = False
                if 'invert_vertex_group_selective' in props.keys():
                    if props['invert_vertex_group_selective']:
                        invert = True
                if invert:
                    selective_weight = selective_weight <= thresh
                else:
                    selective_weight = selective_weight >= thresh
                selective_dict = dict(zip([tuple(v.co) for v in bm.verts],selective_weight))
            else:
                filter_faces = False
        else:
            filter_faces = False

        bm.free()

        end_time = time.time()
        tissue_time(start_time,'Found {} polyhedra'.format(len(polyhedra)),levels=1)
        start_time = time.time()

        bm1.faces.ensure_lookup_table()
        bm1.faces.index_update()

        #unique_verts_dict = dict(zip([tuple(v.co) for v in bm1.verts],bm1.verts))
        bm1, all_faces_dict, polyhedra_faces_id, polyhedra_faces_id_neg = combine_polyhedra_faces(bm1, polyhedra)

        if props.mode == 'POLYHEDRA':
            poly_me = me.copy()
            bm1.to_mesh(poly_me)
            poly_me.update()
            old_me = ob.data
            ob.data = poly_me
            mesh_name = old_me.name
            bpy.data.meshes.remove(old_me)
            bpy.data.meshes.remove(me)
            ob.data.name = mesh_name
            end_time = time.time()
            print('Tissue: Polyhedral wireframe in {:.4f} sec'.format(end_time-start_time))
            return {'FINISHED'}

        delete_faces = set({})
        wireframe_faces = []
        not_wireframe_faces = []
        #flat_faces = []
        count = 0
        outer_faces = get_outer_faces(bm1)
        for faces_id in polyhedra_faces_id:
            delete_faces_poly = []
            wireframe_faces_poly = []
            for id in faces_id:
                if id in delete_faces: continue
                delete = False
                cen = None
                f = None
                if filter_faces:
                    f = all_faces_dict[id]
                    if selective_dict:
                        for v in f.verts:
                            if selective_dict[tuple(v.co)]:
                                delete = True
                                break
                    elif accurate:
                        cen = f.calc_center_median()
                        for e in f.edges:
                            v0 = e.verts[0]
                            v1 = e.verts[1]
                            mid = (v0.co + v1.co)/2
                            vec1 = v0.co - v1.co
                            vec2 = mid - cen
                            ang = Vector.angle(vec1,vec2)
                            length = vec2.length
                            length = sin(ang)*length
                            thick0 = thickness_dict[tuple(v0.co)]
                            thick1 = thickness_dict[tuple(v1.co)]
                            thick = (thick0 + thick1)/4
                            if length < thick*props.thickness_threshold_correction:
                                delete = True
                                break
                    else:
                        delete = f.calc_area() < area_threshold
                if delete:
                    if props.thicken_all:
                        delete_faces_poly.append(id)
                else:
                    wireframe_faces_poly.append(id)
            if len(wireframe_faces_poly) <= 2:
                delete_faces.update(set([id for id in faces_id]))
                not_wireframe_faces += [polyhedra_faces_id_neg[id] for id in faces_id]
            else:
                wireframe_faces += wireframe_faces_poly
                #flat_faces += delete_faces_poly
        wireframe_faces_id = [i for i in wireframe_faces if i not in not_wireframe_faces]
        wireframe_faces = [all_faces_dict[i] for i in wireframe_faces_id]
        #flat_faces = [all_faces_dict[i] for i in flat_faces]
        delete_faces = [all_faces_dict[i] for i in delete_faces if all_faces_dict[i] not in outer_faces]

        tissue_time(start_time,'Merge and delete',levels=1)
        start_time = time.time()

        ############# FRAME #############
        new_faces, outer_wireframe_faces = create_frame_faces(
            bm1,
            wireframe_faces,
            wireframe_faces_id,
            polyhedra_faces_id_neg,
            thickness_dict,
            outer_faces
        )
        faces_to_delete = wireframe_faces+delete_faces
        outer_wireframe_faces += [f for f in outer_faces if not f in faces_to_delete]
        bmesh.ops.delete(bm1, geom=faces_to_delete, context='FACES')

        bm1.verts.ensure_lookup_table()
        bm1.edges.ensure_lookup_table()
        bm1.faces.ensure_lookup_table()
        bm1.verts.index_update()

        wireframe_indexes = [f.index for f in new_faces]
        outer_indexes = [f.index for f in outer_wireframe_faces]
        edges_to_crease = [f.edges[2].index for f in new_faces]
        layer_is_wireframe = bm1.faces.layers.int.new('tissue_is_wireframe')
        for id in wireframe_indexes:
            bm1.faces[id][layer_is_wireframe] = 1
        layer_is_outer = bm1.faces.layers.int.new('tissue_is_outer')
        for id in outer_indexes:
            bm1.faces[id][layer_is_outer] = 1
        if props.crease > 0 and props.dissolve != 'INNER':
            crease_layer = bm1.edges.layers.float.new('crease_edge')
            bm1.edges.index_update()
            crease_edges = []
            for edge_index in edges_to_crease:
                bm1.edges[edge_index][crease_layer] = props.crease

        tissue_time(start_time,'Generate frames',levels=1)
        start_time = time.time()

        ### Displace vertices ###
        corners = [[] for i in range(len(bm1.verts))]
        normals = [0]*len(bm1.verts)
        vertices = [0]*len(bm1.verts)
        # Define vectors direction
        for f in bm1.faces:
            v0 = f.verts[0]
            v1 = f.verts[1]
            id = v0.index
            corners[id].append((v1.co - v0.co).normalized())
            v0.normal_update()
            normals[id] = v0.normal.copy()
            vertices[id] = v0
        # Displace vertices
        for i, vecs in enumerate(corners):
            if len(vecs) > 0:
                v = vertices[i]
                nor = normals[i]
                ang = 0
                for vec in vecs:
                    if nor == Vector((0,0,0)): continue
                    ang += nor.angle(vec)
                ang /= len(vecs)
                div = sin(ang)
                if div == 0: div = 1
                v.co += nor*thickness_dict[tuple(v.co)]/div

        tissue_time(start_time,'Corners displace',levels=1)
        start_time = time.time()

        if props.dissolve != 'NONE':
            if props.dissolve == 'INNER': dissolve_id = 2
            if props.dissolve == 'OUTER': dissolve_id = 0
            bm1.edges.index_update()
            dissolve_edges = []
            for f in bm1.faces:
                e = f.edges[dissolve_id]
                if e not in dissolve_edges:
                    dissolve_edges.append(e)
            bmesh.ops.dissolve_edges(bm1, edges=dissolve_edges, use_verts=True, use_face_split=False)

        for v in bm1.verts: v.select_set(False)
        for f in bm1.faces: f.select_set(False)

        dissolve_verts = [v for v in bm1.verts if len(v.link_edges) < 3]
        bmesh.ops.dissolve_verts(bm1, verts=dissolve_verts, use_face_split=False, use_boundary_tear=False)

        # clean meshes
        bm1.to_mesh(me)
        if props.bool_smooth: me.shade_smooth()
        me.update()
        old_me = ob.data
        ob.data = me
        mesh_name = old_me.name
        bpy.data.meshes.remove(old_me)
        ob.data.name = mesh_name
        bm1.free()

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.reset()
        bpy.ops.object.mode_set(mode='OBJECT')

        tissue_time(start_time,'Clean mesh',levels=1)
        start_time = time.time()

        tissue_time(begin_time,'Polyhedral Wireframe',levels=0)
        return {'FINISHED'}

def pre_processing(bm):
    delete = [e for e in bm.edges if len(e.link_faces) < 2]
    while len(delete) > 0:
        bmesh.ops.delete(bm, geom=delete, context='EDGES')
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        delete = [e for e in bm.edges if len(e.link_faces) < 2]
    return bm

def get_outer_faces(bm):
    bm_copy = bm.copy()
    bmesh.ops.recalc_face_normals(bm_copy, faces=bm_copy.faces)
    outer = []
    for f1, f2 in zip(bm.faces, bm_copy.faces):
        f1.normal_update()
        if f1.normal == f2.normal:
            outer.append(f1)
    return outer

def create_frame_faces(
    bm,
    wireframe_faces,
    wireframe_faces_id,
    polyhedra_faces_id_neg,
    thickness_dict,
    outer_faces
):
    new_faces = []
    for f in wireframe_faces:
        f.normal_update()
    all_loops = [[loop for loop in f.loops] for f in wireframe_faces]
    is_outer = [f in outer_faces for f in wireframe_faces]
    outer_wireframe_faces = []
    frames_verts_dict = {}
    for loops_index, loops in enumerate(all_loops):
        n_loop = len(loops)
        frame_id = wireframe_faces_id[loops_index]
        single_face_id = min(frame_id,polyhedra_faces_id_neg[frame_id])
        verts_inner = []
        loops_keys = [tuple(loop.vert.co) + tuple((single_face_id,)) for loop in loops]
        if loops_keys[0] in frames_verts_dict:
            verts_inner = [frames_verts_dict[key] for key in loops_keys]
        else:
            tangents = []
            nor = wireframe_faces[loops_index].normal
            for loop in loops:
                tan = loop.calc_tangent() #nor.cross(loop.calc_tangent().cross(nor)).normalized()
                thickness = thickness_dict[tuple(loop.vert.co)]
                tangents.append(tan/sin(loop.calc_angle()/2)*thickness)
            for i in range(n_loop):
                loop = loops[i]
                new_co = loop.vert.co + tangents[i]
                new_vert = bm.verts.new(new_co)
                frames_verts_dict[loops_keys[i]] = new_vert
                verts_inner.append(new_vert)
        # add faces
        loops += [loops[0]]
        verts_inner += [verts_inner[0]]
        for i in range(n_loop):
            v0 = loops[i].vert
            v1 = loops[i+1].vert
            v2 = verts_inner[i+1]
            v3 = verts_inner[i]
            face_verts = [v0,v1,v2,v3]
            new_face = bm.faces.new(face_verts)
            new_face.select = True
            new_faces.append(new_face)
            if is_outer[loops_index]:
                outer_wireframe_faces.append(new_face)
            new_face.normal_update()
    return new_faces, outer_wireframe_faces

def polyhedral_subdivide_edges(bm, subs, proportional_segments):
    if subs > 1:
        if proportional_segments:
            wire_length = [e.calc_length() for e in bm.edges]
            all_edges = list(bm.edges)
            max_segment = max(wire_length)/subs+0.00001 # prevent out_of_bounds
            split_edges = [[] for i in range(subs)]
            for e, l in zip(all_edges, wire_length):
                split_edges[int(l//max_segment)].append(e)
            for i in range(1,subs):
                bmesh.ops.bisect_edges(bm, edges=split_edges[i], cuts=i)
        else:
            bmesh.ops.bisect_edges(bm, edges=bm.edges, cuts=subs-1)

def get_double_faces_bmesh(bm):
    double_faces = []
    for f in bm.faces:
        verts0 = [v.co for v in f.verts]
        verts1 = verts0.copy()
        verts1.reverse()
        double_faces.append(verts0)
        double_faces.append(verts1)
    bm1 = bmesh.new()
    for verts_co in double_faces:
        bm1.faces.new([bm1.verts.new(v) for v in verts_co])
    bm1.verts.ensure_lookup_table()
    bm1.edges.ensure_lookup_table()
    bm1.faces.ensure_lookup_table()
    return bm1

def get_decomposed_polyhedra(bm):
    polyhedra_from_facekey = {}
    count = 0
    to_merge = []
    for e in bm.edges:
        done = []
        # ERROR: Naked edges
        link_faces = e.link_faces
        n_radial_faces = len(link_faces)
        if n_radial_faces < 2:
            return "Naked edges are not allowed"
        vert0 = e.verts[0]
        vert1 = e.verts[1]
        edge_vec =  vert1.co - vert0.co

        for id1 in range(n_radial_faces-1):
            f1 = link_faces[id1]
            facekey1 = f1.index+1
            verts1 = [v.index for v in f1.verts]
            v0_index = verts1.index(vert0.index)
            v1_index = verts1.index(vert1.index)

            ref_loop_dir = v0_index == (v1_index+1)%len(verts1)
            edge_vec1 = edge_vec if ref_loop_dir else -edge_vec
            tan1 = f1.normal.cross(edge_vec1)

            # faces to compare with
            faceskeys2, normals2 = get_second_faces(
                link_faces,
                vert0.index,
                vert1.index,
                ref_loop_dir,
                f1
            )

            tangents2 = [nor.cross(-edge_vec1) for nor in normals2]

            # positive side
            facekey2_pos = get_closest_face(
                faceskeys2,
                tangents2,
                tan1,
                edge_vec1,
                True
            )
            polyhedra_from_facekey, count, to_merge = store_neighbor_faces(
                facekey1,
                facekey2_pos,
                polyhedra_from_facekey,
                count,
                to_merge
            )
            # negative side
            facekey2_neg = get_closest_face(
                faceskeys2,
                tangents2,
                tan1,
                edge_vec1,
                False
            )
            polyhedra_from_facekey, count, to_merge = store_neighbor_faces(
                -facekey1,
                facekey2_neg,
                polyhedra_from_facekey,
                count,
                to_merge
            )

    polyhedra = [ [] for i in range(count)]
    unique_index = get_unique_polyhedra_index(count, to_merge)
    for key, val in polyhedra_from_facekey.items():
        polyhedra[unique_index[val]].append(key)
    polyhedra = list(set(tuple(i) for i in polyhedra if i))
    polyhedra = remove_double_faces_from_polyhedra(polyhedra)
    return polyhedra

def remove_double_faces_from_polyhedra(polyhedra):
    new_polyhedra = []
    for polyhedron in polyhedra:
        new_polyhedron = [key for key in polyhedron if not -key in polyhedron]
        new_polyhedra.append(new_polyhedron)
    return new_polyhedra

def get_unique_polyhedra_index(count, to_merge):
    out = list(range(count))
    keep_going = True
    while keep_going:
        keep_going = False
        for pair in to_merge:
            if out[pair[1]] != out[pair[0]]:
                out[pair[0]] = out[pair[1]] = min(out[pair[0]], out[pair[1]])
                keep_going = True
    return out

def get_closest_face(faces, tangents, ref_vector, axis, is_positive):
    facekey = None
    min_angle = 1000000
    for fk, tangent in zip(faces, tangents):
        rot_axis = -axis if is_positive else axis
        angle = round_angle_with_axis(ref_vector, tangent, rot_axis)
        if angle < min_angle:
            facekey = fk
            min_angle = angle
    return facekey if is_positive else -facekey

def get_second_faces(face_list, edge_v0, edge_v1, reference_loop_dir, self):
    nFaces = len(face_list)-1
    facekeys = [None]*nFaces
    normals = [None]*nFaces
    count = 0
    for face in face_list:
        if(face == self): continue
        verts = [v.index for v in face.verts]
        v0_index = verts.index(edge_v0)
        v1_index = verts.index(edge_v1)
        loop_dir = v0_index == (v1_index+1)%len(verts)
        if reference_loop_dir != loop_dir:
            facekeys[count] = face.index+1
            normals[count] = face.normal
        else:
            facekeys[count] = -(face.index+1)
            normals[count] = -face.normal
        count+=1
    return facekeys, normals

def store_neighbor_faces(
    key1,
    key2,
    polyhedra,
    polyhedra_count,
    to_merge
):
    poly1 = polyhedra.get(key1)
    poly2 = polyhedra.get(key2)
    if poly1 and poly2:
        if poly1 != poly2:
            to_merge.append((poly1, poly2))
    elif poly1:
        polyhedra[key2] = poly1
    elif poly2:
        polyhedra[key1] = poly2
    else:
        polyhedra[key1] = polyhedra[key2] = polyhedra_count
        polyhedra_count += 1
    return polyhedra, polyhedra_count, to_merge

def add_polyhedron(bm,source_faces):
    faces_verts_key = [[tuple(v.co) for v in f.verts] for f in source_faces]
    polyhedron_verts_key = [key for face_key in faces_verts_key for key in face_key]
    polyhedron_verts = [bm.verts.new(co) for co in polyhedron_verts_key]
    polyhedron_verts_dict = dict(zip(polyhedron_verts_key, polyhedron_verts))
    new_faces = [None]*len(faces_verts_key)
    count = 0
    for verts_keys in faces_verts_key:
        new_faces[count] = bm.faces.new([polyhedron_verts_dict.get(key) for key in verts_keys])
        count+=1

    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    return new_faces

def combine_polyhedra_faces(bm,polyhedra):
    new_bm = bmesh.new()
    polyhedra_faces_id = [None]*len(polyhedra)
    all_faces_dict = {}
    #polyhedra_faces_pos = {}
    polyhedra_faces_id_neg = {}
    vertices_key = [tuple(v.co) for v in bm.verts]
    count = 0
    for p in polyhedra:
        faces_id = [(f-1)*2 if f > 0 else (-f-1)*2+1 for f in p]
        faces_id_neg = [(-f-1)*2 if f < 0 else (f-1)*2+1 for f in p]
        new_faces = add_polyhedron(new_bm,[bm.faces[f_id] for f_id in faces_id])
        faces_dict = {}
        for i in range(len(new_faces)):
            face = new_faces[i]
            id = faces_id[i]
            id_neg = faces_id_neg[i]
            polyhedra_faces_id_neg[id] = id_neg
            all_faces_dict[id] = face
        polyhedra_faces_id[count] = faces_id
        count+=1
    return new_bm, all_faces_dict, polyhedra_faces_id, polyhedra_faces_id_neg

class TISSUE_PT_polyhedra_object(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_label = "Tissue Polyhedra"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try:
            ob = context.object
            return ob.type == 'MESH' and ob.tissue.tissue_type == 'POLYHEDRA'
        except: return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_polyhedra
        tissue_props = ob.tissue

        bool_polyhedra = tissue_props.tissue_type == 'POLYHEDRA'
        layout = self.layout
        if not bool_polyhedra:
            layout.label(text="The selected object is not a Polyhedral object",
                        icon='INFO')
        else:
            if props.error_message != "":
                layout.label(text=props.error_message,
                            icon='ERROR')
            col = layout.column(align=True)
            row = col.row(align=True)

            #set_tessellate_handler(self,context)
            row.operator("object.tissue_update_tessellate_deps", icon='FILE_REFRESH', text='Refresh') ####
            lock_icon = 'LOCKED' if tissue_props.bool_lock else 'UNLOCKED'
            #lock_icon = 'PINNED' if props.bool_lock else 'UNPINNED'
            deps_icon = 'LINKED' if tissue_props.bool_dependencies else 'UNLINKED'
            row.prop(tissue_props, "bool_dependencies", text="", icon=deps_icon)
            row.prop(tissue_props, "bool_lock", text="", icon=lock_icon)
            col2 = row.column(align=True)
            col2.prop(tissue_props, "bool_run", text="",icon='TIME')
            col2.enabled = not tissue_props.bool_lock
            col2 = row.column(align=True)
            col2.operator("mesh.tissue_remove", text="", icon='X')
            #layout.use_property_split = True
            #layout.use_property_decorate = False  # No animation.
            col = layout.column(align=True)
            col.label(text='Polyhedral Mode:')
            col.prop(props, 'mode', text='')
            col.separator()
            col.label(text='Source object:')
            row = col.row(align=True)
            row.prop_search(props, "object", context.scene, "objects", text='')
            col2 = row.column(align=True)
            col2.prop(props, "bool_modifiers", text='Use Modifiers',icon='MODIFIER')
            if props.mode == 'WIREFRAME':
                col.separator()
                col.prop(props, 'thickness')
                row = col.row(align=True)
                ob0 = props.object
                row.prop_search(props, 'vertex_group_thickness',
                    ob0, "vertex_groups", text='')
                col2 = row.column(align=True)
                row2 = col2.row(align=True)
                row2.prop(props, "invert_vertex_group_thickness", text="",
                    toggle=True, icon='ARROW_LEFTRIGHT')
                row2.prop(props, "vertex_group_thickness_factor")
                row2.enabled = props.vertex_group_thickness in ob0.vertex_groups.keys()
                col.prop(props, 'bool_smooth')
                col.separator()
                col.label(text='Selective Wireframe:')
                col.prop(props, 'selective_wireframe', text='Mode')
                col.separator()
                if props.selective_wireframe == 'THICKNESS':
                    col.prop(props, 'thickness_threshold_correction')
                elif props.selective_wireframe == 'AREA':
                    col.prop(props, 'area_threshold')
                elif props.selective_wireframe == 'WEIGHT':
                    row = col.row(align=True)
                    row.prop_search(props, 'vertex_group_selective',
                        ob0, "vertex_groups", text='')
                    col2 = row.column(align=True)
                    row2 = col2.row(align=True)
                    row2.prop(props, "invert_vertex_group_selective", text="",
                        toggle=True, icon='ARROW_LEFTRIGHT')
                    row2.prop(props, "vertex_group_selective_threshold")
                    row2.enabled = props.vertex_group_selective in ob0.vertex_groups.keys()
                #if props.selective_wireframe != 'NONE':
                #    col.prop(props, 'thicken_all')
                col.separator()
                col.label(text='Subdivide edges:')
                row = col.row()
                row.prop(props, 'segments')
                row.prop(props, 'proportional_segments', text='Proportional')
                col.separator()
                col.label(text='Loops:')
                col.prop(props, 'dissolve')
                col.separator()
                col.prop(props, 'crease')
