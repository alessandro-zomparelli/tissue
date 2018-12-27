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
from mathutils import Vector
import numpy as np
from math import sqrt
import random, time
import bmesh


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

def anim_tessellate_active(self, context):
    ob = context.object
    props = ob.tissue_tessellate
    if not props.bool_hold:
        try:
            props.generator.name
            props.component.name
            bpy.ops.object.update_tessellate()
        except: pass

def anim_tessellate_object(ob):
    try:
        #bpy.context.view_layer.objects.active = ob
        bpy.ops.object.update_tessellate()
    except:
        return None

from bpy.app.handlers import persistent

@persistent
def anim_tessellate(scene):
    # store selected objects
    scene = bpy.context.scene
    try: active_object = bpy.context.object
    except: active_object = None
    selected_objects = bpy.context.selected_objects
    if bpy.context.mode in ('OBJECT', 'PAINT_WEIGHT'):
        old_mode = bpy.context.mode
        if old_mode == 'PAINT_WEIGHT': old_mode = 'WEIGHT_PAINT'
        print(old_mode)
        for ob in scene.objects:
            if ob.tissue_tessellate.bool_run:
                for o in scene.objects: ob.select_set(False)
                bpy.context.view_layer.objects.active = ob
                ob.select_set(True)
                try: bpy.ops.object.update_tessellate()
                except: pass
        # restore selected objects
        for o in scene.objects: ob.select_set(False)
        for o in selected_objects:
            o.select_set(True)
        bpy.context.view_layer.objects.active = active_object
        bpy.ops.object.mode_set(mode=old_mode)

class tissue_tessellate_prop(PropertyGroup):
    bool_hold : BoolProperty(
        name="Hold Update",
        description="Prevent automatic update while other properties are changed",
        default=False
        )
    bool_run : BoolProperty(
        name="Animatable Tessellation",
        description="Automatically recompute the tessellation when the frame is changed",
        default=False
        )
    zscale : FloatProperty(
        name="Scale", default=1, soft_min=0, soft_max=10,
        description="Scale factor for the component thickness",
        update = anim_tessellate_active
        )
    scale_mode : EnumProperty(
        items=(('CONSTANT', "Constant", ""), ('ADAPTIVE', "Proportional", "")),
        default='CONSTANT',
        name="Z-Scale according to faces size",
        update = anim_tessellate_active
        )
    offset : FloatProperty(
        name="Surface Offset",
        default=0,
        min=-1,
        max=1,
        soft_min=-1,
        soft_max=1,
        description="Surface offset",
        update = anim_tessellate_active
        )
    mode : EnumProperty(
        items=(('CONSTANT', "Constant", ""), ('ADAPTIVE', "Adaptive", "")),
        default='ADAPTIVE',
        name="Component Mode",
        update = anim_tessellate_active
        )
    rotation_mode : EnumProperty(
        items=(('RANDOM', "Random", ""),
               ('UV', "Active UV", ""),
               ('DEFAULT', "Default", "")),
        default='DEFAULT',
        name="Component Rotation",
        update = anim_tessellate_active
        )
    fill_mode : EnumProperty(
        items=(('QUAD', "Quad", ""), ('FAN', "Fan", ""), ('PATCH', "Patch", "")),
        default='QUAD',
        name="Fill Mode",
        update = anim_tessellate_active
        )
    gen_modifiers : BoolProperty(
        name="Generator Modifiers",
        default=False,
        description="Apply modifiers to base object",
        update = anim_tessellate_active
        )
    com_modifiers : BoolProperty(
        name="Component Modifiers",
        default=False,
        description="Apply modifiers to component object",
        update = anim_tessellate_active
        )
    merge : BoolProperty(
        name="Merge",
        default=False,
        description="Merge vertices in adjacent duplicates",
        update = anim_tessellate_active
        )
    merge_thres : FloatProperty(
        name="Distance",
        default=0.001,
        soft_min=0,
        soft_max=10,
        description="Limit below which to merge vertices",
        update = anim_tessellate_active
        )
    generator : PointerProperty(
        type=bpy.types.Object,
        name="",
        description="Base object for the tessellation",
        update = anim_tessellate_active
        )
    component : PointerProperty(
        type=bpy.types.Object,
        name="",
        description="Component object for the tessellation",
        #default="",
        update = anim_tessellate_active
        )
    bool_random : BoolProperty(
        name="Randomize",
        default=False,
        description="Randomize component rotation",
        update = anim_tessellate_active
        )
    random_seed : IntProperty(
        name="Seed",
        default=0,
        soft_min=0,
        soft_max=10,
        description="Random seed",
        update = anim_tessellate_active
        )
    bool_vertex_group : BoolProperty(
        name="Map Vertex Group",
        default=False,
        description="Transfer all Vertex Groups from Base object",
        update = anim_tessellate_active
        )
    bool_selection : BoolProperty(
        name="On selected Faces",
        default=False,
        description="Create Tessellation only on selected faces",
        update = anim_tessellate_active
        )
    bool_shapekeys : BoolProperty(
        name="Use Shape Keys",
        default=False,
        description="Transfer Component's Shape Keys. If the name of Vertex "
                    "Groups and Shape Keys are the same, they will be "
                    "automatically combined",
        update = anim_tessellate_active
        )
    bool_smooth : BoolProperty(
        name="Smooth Shading",
        default=False,
        description="Output faces with smooth shading rather than flat shaded",
        update = anim_tessellate_active
        )
    bool_materials : BoolProperty(
        name="Transfer Materials",
        default=False,
        description="Preserve component's materials",
        update = anim_tessellate_active
        )
    bool_crease : BoolProperty(
        name="Transfer Edge Crease",
        default=False,
        description="Preserve component's edges crease",
        update = anim_tessellate_active
        )
    bool_material_id : BoolProperty(
        name="Tessellation on Material ID",
        default=False,
        description="Apply the component only on the selected Material",
        update = anim_tessellate_active
        )
    material_id : IntProperty(
        name="Material ID",
        default=0,
        min=0,
        description="Material ID",
        update = anim_tessellate_active
        )
    bool_dissolve_seams : BoolProperty(
        name="Dissolve Seams",
        default=False,
        description="Dissolve all seam edges",
        update = anim_tessellate_active
        )

def store_parameters(operator, ob):
    ob.tissue_tessellate.bool_hold = True
    ob.tissue_tessellate.generator = bpy.data.objects[operator.generator]
    ob.tissue_tessellate.component = bpy.data.objects[operator.component]
    ob.tissue_tessellate.zscale = operator.zscale
    ob.tissue_tessellate.offset = operator.offset
    ob.tissue_tessellate.gen_modifiers = operator.gen_modifiers
    ob.tissue_tessellate.com_modifiers = operator.com_modifiers
    ob.tissue_tessellate.mode = operator.mode
    ob.tissue_tessellate.rotation_mode = operator.rotation_mode
    ob.tissue_tessellate.merge = operator.merge
    ob.tissue_tessellate.merge_thres = operator.merge_thres
    ob.tissue_tessellate.scale_mode = operator.scale_mode
    ob.tissue_tessellate.bool_random = operator.bool_random
    ob.tissue_tessellate.random_seed = operator.random_seed
    ob.tissue_tessellate.fill_mode = operator.fill_mode
    ob.tissue_tessellate.bool_vertex_group = operator.bool_vertex_group
    ob.tissue_tessellate.bool_selection = operator.bool_selection
    ob.tissue_tessellate.bool_shapekeys = operator.bool_shapekeys
    ob.tissue_tessellate.bool_smooth = operator.bool_smooth
    ob.tissue_tessellate.bool_materials = operator.bool_materials
    ob.tissue_tessellate.bool_material_id = operator.bool_material_id
    ob.tissue_tessellate.material_id = operator.material_id
    ob.tissue_tessellate.bool_dissolve_seams = operator.bool_dissolve_seams
    ob.tissue_tessellate.bool_hold = False
    return ob

def tassellate_patch(ob0, ob1, offset, zscale, com_modifiers, mode,
               scale_mode, rotation_mode, rand_seed, bool_vertex_group,
               bool_selection, bool_shapekeys, bool_material_id, material_id):
    random.seed(rand_seed)
    old_me0 = ob0.data      # Store generator mesh

    me0 = ob0.to_mesh(bpy.context.depsgraph, True)

    # Check if zero faces are selected
    bool_cancel = True
    for p in me0.polygons:
        check_sel = check_mat = False
        if not bool_selection or p.select: check_sel = True
        if not bool_material_id or p.material_index == material_id: check_mat = True
        if check_sel and check_mat:
                bool_cancel = False
                break
    if bool_cancel:
        return 0

    ob0.data = me0

    levels = 0
    sculpt_levels = 0
    render_levels = 0
    bool_multires = False
    multires_name = ""
    for m in ob0.modifiers:
        if m.type in ('SUBSURF', 'MULTIRES') and m.show_viewport:
            levels = m.levels
            if m.type == 'MULTIRES':
                bool_multires = True
                multires_name = m.name
                sculpt_levels = m.sculpt_levels
                render_levels = m.render_levels
            else: bool_multires = False

    # set Shape Keys to zero
    if bool_shapekeys:
        try:
            original_key_values = []
            for sk in ob1.data.shape_keys.key_blocks:
                original_key_values.append(sk.value)
                sk.value = 0
        except:
            bool_shapekeys = False

    # Apply component modifiers
    mod_visibility = []
    if com_modifiers:
        me1 = ob1.to_mesh(bpy.context.depsgraph, apply_modifiers=True)
    elif not bool_shapekeys:
        # must use to_mesh in order to apply the shape keys
        for m in ob1.modifiers:
            mod_visibility.append(m.show_viewport)
            m.show_viewport = False
        me1 = ob1.to_mesh(bpy.context.depsgraph, apply_modifiers=True)
    else: me1 = ob1.data

    verts0 = me0.vertices   # Collect generator vertices

    # Component statistics
    n_verts = len(me1.vertices)

    # Create empty lists
    new_verts = []
    new_edges = []
    new_faces = []
    new_verts_np = np.array(())

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
        if mode == "ADAPTIVE":
            vert = v.co - min_c  # (ob1.matrix_world * v.co) - min_c
            vert[0] = (vert[0] / bb[0] if bb[0] != 0 else 0.5)
            vert[1] = (vert[1] / bb[1] if bb[1] != 0 else 0.5)
            vert[2] = (vert[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
        else:
            vert = v.co.xyz
            vert[2] = (vert[2] - min_c[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
        verts1.append(vert)

    patch_faces = 4**levels
    sides = int(sqrt(patch_faces))
    sides0 = sides-2
    patch_faces0 = int((sides-2)**2)
    n_patches = int(len(me0.polygons)/patch_faces)

    new_verts = []
    new_edges = []
    new_faces = []

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    new_patch = None

    # All vertex group
    if bool_vertex_group:
        try:
            weight = []
            #group_index = ob0.vertex_groups.active_index
            #active_vertex_group = ob0.vertex_groups[group_index]
            for vg in ob0.vertex_groups:
                _weight = []
                for v in me0.vertices:
                    try:
                        _weight.append(vg.weight(v.index))
                    except:
                        _weight.append(0)
                weight.append(_weight)
        except:
            bool_vertex_group = False

    # Adaptive Z
    if scale_mode == 'ADAPTIVE':
        mult = bb[2]/(bb[0]*bb[1])*patch_faces
        verts_area = []
        bm = bmesh.new()
        bm.from_mesh(me0)
        bm.verts.ensure_lookup_table()
        for v in bm.verts:
            area = 0
            faces = v.link_faces
            for f in faces:
                area += f.calc_area()
            area/=len(faces)
            area*=mult
            verts_area.append(sqrt(area))

    random.seed(rand_seed)
    bool_correct = False
    for i in range(n_patches):
        poly = me0.polygons[i*patch_faces]
        if bool_selection and not poly.select: continue
        if bool_material_id and not poly.material_index == material_id: continue

        bool_correct = True
        new_patch = bpy.data.objects.new("patch", me1.copy())
        bpy.context.collection.objects.link(new_patch)
        new_patch.select_set(True)
        bpy.context.view_layer.objects.active = new_patch

        # Vertex Group
        if bool_vertex_group:
            for vg in ob0.vertex_groups:
                new_patch.vertex_groups.new(name=vg.name)

        # find patch faces
        faces = [[[0] for ii in range(sides)] for jj in range(sides)]
        for j in range(patch_faces):
            if j < patch_faces0:
                if levels == 0:
                    faces[j%sides0][j//sides0] = me0.polygons[j+i*patch_faces]
                else:
                    faces[j%sides0+1][j//sides0+1] = me0.polygons[j+i*patch_faces]
            elif j < patch_faces0 + sides:
                jj = j-patch_faces0
                faces[jj][0] = me0.polygons[j+i*patch_faces]
            elif j < patch_faces0 + sides*2-1:
                jj = j-(patch_faces0 + sides)+1
                faces[sides-1][jj] = me0.polygons[j+i*patch_faces]
            elif j < patch_faces0 + sides*3-2:
                jj = j-(patch_faces0 + sides*2-1)
                faces[sides-jj-2][sides-1] = me0.polygons[j+i*patch_faces]
            else:
                jj = j-(patch_faces0 + sides*3-2)
                faces[0][sides-jj-2] = me0.polygons[j+i*patch_faces]

        # generate vertices grid
        verts = [[[0] for ii in range(int(sqrt(patch_faces)+1))] for jj in range(int(sqrt(patch_faces)+1))]
        for v in range(sides+1):
            for u in range(sides+1):
                if v == sides and u == sides:
                    verts[u][v] = me0.vertices[faces[u-1][v-1].vertices[2]]
                elif v < sides and u == sides:
                    verts[u][v] = me0.vertices[faces[u-1][v].vertices[1]]
                elif v == sides and u < sides:
                    verts[u][v] = me0.vertices[faces[u][v-1].vertices[3]]
                else:
                    verts[u][v] = me0.vertices[faces[u][v].vertices[0]]

        # Random rotation
        if rotation_mode == 'RANDOM':
            rand = random.randint(0, 3)
            if rand == 1:
                verts = [[verts[k][w] for w in range(sides,-1,-1)] for k in range(sides,-1,-1)]
            elif rand == 2:
                verts = [[verts[w][k] for w in range(sides,-1,-1)] for k in range(sides+1)]
            elif rand == 3:
                verts = [[verts[w][k] for w in range(sides+1)] for k in range(sides,-1,-1)]

        # UV rotation
        elif rotation_mode == 'UV' and len(ob0.data.uv_layers) > 0:
            uv0 = me0.uv_layers.active.data[faces[0][0].index*4].uv
            uv1 = me0.uv_layers.active.data[faces[0][-1].index*4 + 3].uv
            uv2 = me0.uv_layers.active.data[faces[-1][-1].index*4 + 2].uv
            uv3 = me0.uv_layers.active.data[faces[-1][0].index*4 + 1].uv
            v01 = (uv0 + uv1)
            v32 = (uv3 + uv2)
            v0132 = v32 - v01
            v0132.normalize()
            v12 = (uv1 + uv2)
            v03 = (uv0 + uv3)
            v1203 = v03 - v12
            v1203.normalize()

            vertUV = []
            dot1203 = v1203.x
            dot0132 = v0132.x
            if(abs(dot1203) < abs(dot0132)):
                if (dot0132 > 0):
                    pass
                else:
                    verts = [[verts[k][w] for w in range(sides,-1,-1)] for k in range(sides,-1,-1)]
            else:
                if(dot1203 < 0):
                    verts = [[verts[w][k] for w in range(sides,-1,-1)] for k in range(sides+1)]
                else:
                    verts = [[verts[w][k] for w in range(sides+1)] for k in range(sides,-1,-1)]

        step = 1/sides

        for vert, patch_vert in zip(verts1, new_patch.data.vertices):
            u = int(vert[0]//step)
            v = int(vert[1]//step)
            fu = (vert[0]%step)/step
            fv = (vert[1]%step)/step

            v00 = verts[u][v]
            v10 = verts[min(u+1,sides)][v]
            v01 = verts[u][min(v+1, sides)]
            v11 = verts[min(u+1,sides)][min(v+1,sides)]

            fw = vert.z
            if scale_mode == 'ADAPTIVE':
                a00 = verts_area[v00.index]
                a10 = verts_area[v10.index]
                a01 = verts_area[v01.index]
                a11 = verts_area[v11.index]
                fw*=lerp2(a00,a10,a01,a11,Vector((fu,fv,0)))

            fvec = Vector((fu,fv,fw))
            patch_vert.co = lerp3(v00, v10, v01, v11, fvec)

            # Vertex Group
            if bool_vertex_group:
                for _weight, vg in zip(weight, new_patch.vertex_groups):
                    w00 = _weight[v00.index]
                    w10 = _weight[v10.index]
                    w01 = _weight[v01.index]
                    w11 = _weight[v11.index]
                    wuv = lerp2(w00,w10,w01,w11, fvec)
                    vg.add([patch_vert.index], wuv, "ADD")

        if bool_shapekeys:
            basis = com_modifiers
            for sk in ob1.data.shape_keys.key_blocks:
                # set all keys to 0
                for _sk in ob1.data.shape_keys.key_blocks: _sk.value = 0
                sk.value = 1
                if com_modifiers: new_patch.shape_key_add(name=sk.name)

                if basis:
                    basis = False
                    continue

                # Apply component modifiers
                if com_modifiers:
                    sk_data = ob1.to_mesh(bpy.context.depsgraph, apply_modifiers=True)
                    source = sk_data.vertices
                else:
                    source = sk.data

                #sk_verts0 = sk_me0.vertices   # Collect generator vertices
                #sk_verts1 = []
                for sk_v, _v in zip(source, me1.vertices):
                    #if sk_v.co == _v.co: continue
                    if mode == "ADAPTIVE":
                        sk_vert = sk_v.co - min_c  # (ob1.matrix_world * v.co) - min_c
                        sk_vert[0] = (sk_vert[0] / bb[0] if bb[0] != 0 else 0.5)
                        sk_vert[1] = (sk_vert[1] / bb[1] if bb[1] != 0 else 0.5)
                        sk_vert[2] = (sk_vert[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
                    else:
                        sk_vert = sk_v.co.xyz
                        sk_vert[2] = (sk_vert[2] - min_c[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
                    #sk_verts1.append(sk_vert)

                    u = max(min(sides, int(sk_vert[0]//step)),0)
                    v = max(min(sides, int(sk_vert[1]//step)),0)
                    fu = (sk_vert[0]%step)/step
                    fv = (sk_vert[1]%step)/step

                    v00 = verts[u][v]
                    v10 = verts[min(u+1,sides)][v]
                    v01 = verts[u][min(v+1, sides)]
                    v11 = verts[min(u+1,sides)][min(v+1,sides)]

                    fw = sk_vert.z
                    if scale_mode == 'ADAPTIVE':
                        a00 = verts_area[v00.index]
                        a10 = verts_area[v10.index]
                        a01 = verts_area[v01.index]
                        a11 = verts_area[v11.index]
                        fw*=lerp2(a00,a10,a01,a11,Vector((fu,fv,0)))

                    fvec = Vector((fu,fv,fw))
                    sk_co = lerp3(v00, v10, v01, v11, fvec)

                    new_patch.data.shape_keys.key_blocks[sk.name].data[_v.index].co = sk_co

    ob0.data = old_me0
    if not bool_correct: return 0

    bpy.ops.object.join()

    if bool_shapekeys:
        for sk, val in zip(ob1.data.shape_keys.key_blocks, original_key_values):
            sk.value = val
            new_patch.data.shape_keys.key_blocks[sk.name].value = val
        if bool_vertex_group:
            for sk in new_patch.data.shape_keys.key_blocks:
                for vg in new_patch.vertex_groups:
                    if sk.name == vg.name:
                        sk.vertex_group = vg.name

    new_name = ob0.name + "_" + ob1.name
    new_patch.name = "tessellate_temp"

    if bool_multires:
        for m in ob0.modifiers:
            if m.type == 'MULTIRES' and m.name == multires_name:
                m.levels = levels
                m.sculpt_levels = sculpt_levels
                m.render_levels = render_levels
    # restore original modifiers visibility for component object
    if not com_modifiers:
        for m, vis in zip(ob1.modifiers, mod_visibility):
            m.show_viewport = vis

    return new_patch

def tassellate(ob0, ob1, offset, zscale, gen_modifiers, com_modifiers, mode,
               scale_mode, rotation_mode, rand_seed, fill_mode,
               bool_vertex_group, bool_selection, bool_shapekeys,
               bool_material_id, material_id):
    random.seed(rand_seed)
    old_me0 = ob0.data      # Store generator mesh

    if gen_modifiers:       # Apply generator modifiers
        me0 = ob0.to_mesh(bpy.context.depsgraph, apply_modifiers=True)
    else:
        me0 = ob0.data
    ob0.data = me0
    base_polygons = []

    # Check if zero faces are selected
    if bool_selection:
        for p in ob0.data.polygons:
            if p.select:
                base_polygons.append(p)
    else:
        base_polygons = ob0.data.polygons
    if len(base_polygons) == 0:
        return 0

    if bool_shapekeys:
        try:
            original_key_values = []
            for sk in ob1.data.shape_keys.key_blocks:
                original_key_values.append(sk.value)
                sk.value = 0
        except:
            bool_shapekeys = False

    # Apply component modifiers
    if com_modifiers:
        me1 = ob1.to_mesh(bpy.context.depsgraph, apply_modifiers=True)
    else:
        me1 = ob1.data

    verts0 = me0.vertices   # Collect generator vertices

    # Component statistics
    n_verts = len(me1.vertices)
    # n_edges = len(me1.edges)
    # n_faces = len(me1.polygons)

    # Component transformations
    # loc = ob1.location
    # dim = ob1.dimensions
    # scale = ob1.scale

    # Create empty lists
    new_verts = []
    new_edges = []
    new_faces = []
    new_verts_np = np.array(())

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
        if mode == "ADAPTIVE":
            vert = v.co - min_c  # (ob1.matrix_world * v.co) - min_c
            vert[0] = (vert[0] / bb[0] if bb[0] != 0 else 0.5)
            vert[1] = (vert[1] / bb[1] if bb[1] != 0 else 0.5)
            vert[2] = (vert[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
        else:
            vert = v.co.xyz
            vert[2] = (vert[2] - min_c[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
        verts1.append(vert)

    # component vertices
    vs1 = np.array([v for v in verts1]).reshape(len(verts1), 3, 1)
    vx = vs1[:, 0]
    vy = vs1[:, 1]
    vz = vs1[:, 2]

    # Component polygons
    fs1 = [[i for i in p.vertices] for p in me1.polygons]
    new_faces = fs1[:]

    # Component edges
    es1 = [[i for i in e.vertices] for e in me1.edges if e.is_loose]
    new_edges = es1[:]

    # SHAPE KEYS
    if bool_shapekeys:
        basis = com_modifiers
        vx_key = []
        vy_key = []
        vz_key = []
        sk_np = []
        for sk in ob1.data.shape_keys.key_blocks:
            do_shapekeys = True
            # set all keys to 0
            for _sk in ob1.data.shape_keys.key_blocks: _sk.value = 0
            sk.value = 1

            if basis:
                basis = False
                continue

            # Apply component modifiers
            if com_modifiers:
                sk_data = ob1.to_mesh(bpy.context.depsgraph, apply_modifiers=True)
                source = sk_data.vertices
            else:
                source = sk.data

            shapekeys = []
            for v in source:
                if mode == "ADAPTIVE":
                    vert = v.co - min_c
                    vert[0] = vert[0] / bb[0]
                    vert[1] = vert[1] / bb[1]
                    vert[2] = (vert[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
                else:
                    vert = v.co.xyz
                    vert[2] = (vert[2] - min_c[2] + (-0.5 + offset * 0.5) * bb[2]) * \
                              zscale
                shapekeys.append(vert)

            # Component vertices
            key1 = np.array([v for v in shapekeys]).reshape(len(shapekeys), 3, 1)
            vx_key.append(key1[:, 0])
            vy_key.append(key1[:, 1])
            vz_key.append(key1[:, 2])
            sk_np.append([])
        print(sk_np)

    # All vertex group
    if bool_vertex_group:
        try:
            weight = []
            #group_index = ob0.vertex_groups.active_index
            #active_vertex_group = ob0.vertex_groups[group_index]
            for vg in ob0.vertex_groups:
                _weight = []
                for v in me0.vertices:
                    try:
                        _weight.append(vg.weight(v.index))
                    except:
                        _weight.append(0)
                weight.append(_weight)
        except:
            bool_vertex_group = False

    # FAN tessellation mode
    if fill_mode == 'FAN':
        fan_verts = [v.co.to_tuple() for v in me0.vertices]
        fan_polygons = []
        # selected_faces = []
        for p in base_polygons:
            # if bool_selection and not p.select: continue
            fan_center = Vector((0, 0, 0))
            for v in p.vertices:
                fan_center += me0.vertices[v].co
            fan_center /= len(p.vertices)
            last_vert = len(fan_verts)
            fan_verts.append(fan_center.to_tuple())

            # Vertex Group
            if bool_vertex_group:
                for w in weight:
                    center_weight = sum([w[i] for i in p.vertices]) / len(p.vertices)
                    w.append(center_weight)

            for i in range(len(p.vertices)):
                fan_polygons.append((p.vertices[i],
                                     p.vertices[(i + 1) % len(p.vertices)],
                                     last_vert, last_vert))
                # if bool_selection: selected_faces.append(p.select)
        fan_me = bpy.data.meshes.new('Fan.Mesh')
        fan_me.from_pydata(tuple(fan_verts), [], tuple(fan_polygons))
        me0 = fan_me
        verts0 = me0.vertices
        base_polygons = me0.polygons
        """
        for i in range(len(selected_faces)):
            fan_me.polygons[i].select = selected_faces[i]
        """

    # Adaptive Z
    if scale_mode == 'ADAPTIVE':
        mult = bb[2]/(bb[0]*bb[1])
        verts_area = []
        bm = bmesh.new()
        bm.from_mesh(me0)
        bm.verts.ensure_lookup_table()
        for v in bm.verts:
            area = 0
            faces = v.link_faces
            for f in faces:
                area += f.calc_area()
            try:
                area/=len(faces)
                area*=mult
                verts_area.append(sqrt(area))
            except:
                verts_area.append(0)
    count = 0   # necessary for UV calculation

    # TESSELLATION
    j = 0
    bool_correct = False
    for p in base_polygons:
        if bool_selection and not p.select: continue
        if bool_material_id and not p.material_index == material_id: continue

        bool_correct = True

        # Random rotation
        if rotation_mode == 'RANDOM':
            shifted_vertices = []
            n_poly_verts = len(p.vertices)
            rand = random.randint(0, n_poly_verts)
            for i in range(n_poly_verts):
                shifted_vertices.append(p.vertices[(i + rand) % n_poly_verts])
            vs0 = np.array([verts0[i].co for i in shifted_vertices])
            nvs0 = np.array([verts0[i].normal for i in shifted_vertices])
            # vertex weight
            if bool_vertex_group:
                ws0 = []
                for w in weight:
                    _ws0 = []
                    for i in shifted_vertices:
                        try:
                            _ws0.append(w[i])
                        except:
                            _ws0.append(0)
                    ws0.append(np.array(_ws0))

        # UV rotation
        elif rotation_mode == 'UV' and len(ob0.data.uv_layers) > 0 and \
                fill_mode != 'FAN':
            i = p.index
            v01 = (me0.uv_layers.active.data[count].uv +
                   me0.uv_layers.active.data[count + 1].uv)
            if len(p.vertices) > 3:
                v32 = (me0.uv_layers.active.data[count + 3].uv +
                       me0.uv_layers.active.data[count + 2].uv)
            else:
                v32 = (me0.uv_layers.active.data[count].uv +
                       me0.uv_layers.active.data[count + 2].uv)
            v0132 = v32 - v01
            v0132.normalize()

            v12 = (me0.uv_layers.active.data[count + 1].uv +
                   me0.uv_layers.active.data[count + 2].uv)
            if len(p.vertices) > 3:
                v03 = (me0.uv_layers.active.data[count].uv +
                       me0.uv_layers.active.data[count + 3].uv)
            else:
                v03 = (me0.uv_layers.active.data[count].uv +
                       me0.uv_layers.active.data[count].uv)
            v1203 = v03 - v12
            v1203.normalize()

            vertUV = []
            dot1203 = v1203.x
            dot0132 = v0132.x
            if(abs(dot1203) < abs(dot0132)):
                if (dot0132 > 0):
                    vertUV = p.vertices[1:] + p.vertices[:1]
                else:
                    vertUV = p.vertices[3:] + p.vertices[:3]
            else:
                if(dot1203 < 0):
                    vertUV = p.vertices[:]
                else:
                    vertUV = p.vertices[2:] + p.vertices[:2]
            vs0 = np.array([verts0[i].co for i in vertUV])
            nvs0 = np.array([verts0[i].normal for i in vertUV])

            # Vertex weight
            if bool_vertex_group:
                ws0 = []
                for w in weight:
                    _ws0 = []
                    for i in vertUV:
                        try:
                            _ws0.append(w[i])
                        except:
                            _ws0.append(0)
                    ws0.append(np.array(_ws0))

            count += len(p.vertices)

        # Default rotation
        else:
            vs0 = np.array([verts0[i].co for i in p.vertices])
            nvs0 = np.array([verts0[i].normal for i in p.vertices])
            # Vertex weight
            if bool_vertex_group:
                ws0 = []
                for w in weight:
                    _ws0 = []
                    for i in p.vertices:
                        try:
                            _ws0.append(w[i])
                        except:
                            _ws0.append(0)
                    ws0.append(np.array(_ws0))
                print(ws0)

        # considering only 4 vertices
        vs0 = np.array((vs0[0], vs0[1], vs0[2], vs0[-1]))
        nvs0 = np.array((nvs0[0], nvs0[1], nvs0[2], nvs0[-1]))

        # remapped vertex coordinates
        v0 = vs0[0] + (vs0[1] - vs0[0]) * vx
        v1 = vs0[3] + (vs0[2] - vs0[3]) * vx
        v2 = v0 + (v1 - v0) * vy

        # remapped vertex normal
        nv0 = nvs0[0] + (nvs0[1] - nvs0[0]) * vx
        nv1 = nvs0[3] + (nvs0[2] - nvs0[3]) * vx
        nv2 = nv0 + (nv1 - nv0) * vy

        # vertex z to normal
        if scale_mode == "ADAPTIVE":
            sz = np.array([verts_area[i] for i in p.vertices])
            # Interpolate vertex weight
            sz0 = sz[0] + (sz[1] - sz[0]) * vx
            sz1 = sz[3] + (sz[2] - sz[3]) * vx
            sz2 = sz0 + (sz1 - sz0) * vy
            v3 = v2 + nv2 * vz * sz2
        else:
            v3 = v2 + nv2 * vz

        if bool_vertex_group:
            w2 = []
            for _ws0 in ws0:
                print(_ws0)
                _ws0 = np.array((_ws0[0], _ws0[1], _ws0[2], _ws0[-1]))
                # Interpolate vertex weight
                w0 = _ws0[0] + (_ws0[1] - _ws0[0]) * vx
                w1 = _ws0[3] + (_ws0[2] - _ws0[3]) * vx
                w2.append(w0 + (w1 - w0) * vy)

        # Shapekeys
        if bool_shapekeys:
            sk_count = 0
            for vxk, vyk, vzk in zip(vx_key, vy_key, vz_key):
                # remapped vertex coordinates
                v0 = vs0[0] + (vs0[1] - vs0[0]) * vxk
                v1 = vs0[3] + (vs0[2] - vs0[3]) * vxk
                v2 = v0 + (v1 - v0) * vyk
                # remapped vertex normal
                nv0 = nvs0[0] + (nvs0[1] - nvs0[0]) * vxk
                nv1 = nvs0[3] + (nvs0[2] - nvs0[3]) * vxk
                nv2 = nv0 + (nv1 - nv0) * vyk
                # vertex z to normal
                v3_key = v2 + nv2 * vzk * (sqrt(p.area) if
                                              scale_mode == "ADAPTIVE" else 1)
                if j == 0:
                    sk_np[sk_count] = v3_key
                else:
                    sk_np[sk_count] = np.concatenate((sk_np[sk_count], v3_key), axis=0)
                #v3 = v3 + (v3_key - v3) * w2
                sk_count += 1

        if j == 0:
            new_verts_np = v3
            if bool_vertex_group:
                vg_np = [np.array(_w2) for _w2 in w2]
        else:
            # Appending vertices
            new_verts_np = np.concatenate((new_verts_np, v3), axis=0)
            # Appending vertex group
            if bool_vertex_group:
                for id in range(len(w2)):
                    print(id)
                    vg_np[id] = np.concatenate((vg_np[id], w2[id]), axis=0)
            # Appending faces
            for p in fs1:
                new_faces.append([i + n_verts * j for i in p])
            # Appending edges
            for e in es1:
                new_edges.append([i + n_verts * j for i in e])

        j += 1

    ob0.data = old_me0

    if not bool_correct: return 0

    new_verts = new_verts_np.tolist()
    new_name = ob0.name + "_" + ob1.name
    new_me = bpy.data.meshes.new(new_name)
    new_me.from_pydata(new_verts, new_edges, new_faces)
    new_me.update(calc_edges=True)
    new_ob = bpy.data.objects.new("tessellate_temp", new_me)

    # vertex group
    if bool_vertex_group:
        for vg in ob0.vertex_groups:
            new_ob.vertex_groups.new(name=vg.name)
            for i in range(len(vg_np[vg.index])):
                new_ob.vertex_groups[vg.name].add([i], vg_np[vg.index][i],"ADD")

    if bool_shapekeys:
        sk_count = 0
        for sk, val in zip(ob1.data.shape_keys.key_blocks, original_key_values):
            sk.value = val
            new_ob.shape_key_add(name=sk.name)
            new_ob.data.shape_keys.key_blocks[sk.name].value = val
            # set shape keys vertices
            sk_data = new_ob.data.shape_keys.key_blocks[sk.name].data
            if sk_count == 0:
                sk_count += 1
                continue
            for id in range(len(sk_data)):
                sk_data[id].co = sk_np[sk_count-1][id]
            sk_count += 1
        if bool_vertex_group:
            for sk in new_ob.data.shape_keys.key_blocks:
                for vg in new_ob.vertex_groups:
                    if sk.name == vg.name:
                        sk.vertex_group = vg.name

    return new_ob


class tessellate(Operator):
    bl_idname = "object.tessellate"
    bl_label = "Tessellate"
    bl_description = ("Create a copy of selected object on the active object's "
                      "faces, adapting the shape to the different faces")
    bl_options = {'REGISTER', 'UNDO'}


    object_name : StringProperty(
            name="",
            description="Name of the generated object"
            )
    zscale : FloatProperty(
            name="Scale",
            default=1,
            soft_min=0,
            soft_max=10,
            description="Scale factor for the component thickness"
            )
    scale_mode : EnumProperty(
            items=(('CONSTANT', "Constant", ""), ('ADAPTIVE', "Proportional", "")),
            default='CONSTANT',
            name="Z-Scale according to faces size"
            )
    offset : FloatProperty(
            name="Surface Offset",
            default=0,
            min=-1, max=1,
            soft_min=-1,
            soft_max=1,
            description="Surface offset"
            )
    mode : EnumProperty(
            items=(('CONSTANT', "Constant", ""), ('ADAPTIVE', "Adaptive", "")),
            default='ADAPTIVE',
            name="Component Mode"
            )
    rotation_mode : EnumProperty(
            items=(('RANDOM', "Random", ""),
                   ('UV', "Active UV", ""),
                   ('DEFAULT', "Default", "")),
            default='DEFAULT',
            name="Component Rotation"
            )
    fill_mode : EnumProperty(
            items=(('QUAD', "Quad", ""), ('FAN', "Fan", ""), ('PATCH', 'Patch', '')),
            default='QUAD',
            name="Fill Mode"
            )
    gen_modifiers : BoolProperty(
            name="Generator Modifiers",
            default=False,
            description="Apply modifiers to base object"
            )
    com_modifiers : BoolProperty(
            name="Component Modifiers",
            default=False,
            description="Apply modifiers to component object"
            )
    merge : BoolProperty(
            name="Merge",
            default=False,
            description="Merge vertices in adjacent duplicates"
            )
    merge_thres : FloatProperty(
            name="Distance",
            default=0.001,
            soft_min=0,
            soft_max=10,
            description="Limit below which to merge vertices"
            )
    bool_random : BoolProperty(
            name="Randomize",
            default=False,
            description="Randomize component rotation"
            )
    random_seed : IntProperty(
            name="Seed",
            default=0,
            soft_min=0,
            soft_max=10,
            description="Random seed"
            )
    bool_vertex_group : BoolProperty(
            name="Map Vertex Group",
            default=False,
            description="Transfer all Vertex Groups from Base object"
            )
    bool_selection : BoolProperty(
            name="On selected Faces",
            default=False,
            description="Create Tessellation only on selected faces"
            )
    bool_shapekeys : BoolProperty(
            name="Use Shape Keys",
            default=False,
            description="Transfer Component's Shape Keys. If the name of Vertex "
                        "Groups and Shape Keys are the same, they will be "
                        "automatically combined"
            )
    bool_smooth : BoolProperty(
            name="Smooth Shading",
            default=False,
            description="Output faces with smooth shading rather than flat shaded"
            )
    bool_materials : BoolProperty(
            name="Transfer Materials",
            default=True,
            description="Preserve component's materials"
            )
    bool_crease : BoolProperty(
            name="Transfer Edge Crease",
            default=False,
            description="Preserve component's edges crease"
            )
    generator : StringProperty(
            name="",
            description="Base object for the tessellation",
            default = ""
            )
    component : StringProperty(
            name="",
            description="Component object for the tessellation",
            default = ""
            )
    bool_material_id : BoolProperty(
            name="Tessellation on Material ID",
            default=False,
            description="Apply the component only on the selected Material"
            )
    bool_dissolve_seams : BoolProperty(
            name="Dissolve Seams",
            default=False,
            description="Dissolve all seam edges"
            )
    material_id : IntProperty(
            name="Material ID",
            default=0,
            min=0,
            description="Material ID"
            )
    working_on : ""

    def draw(self, context):
        try:
            bool_working = self.working_on == self.object_name and \
            self.working_on != ""
        except:
            bool_working = False

        sel = bpy.context.selected_objects

        bool_meshes = False
        if len(sel) == 2:
            bool_meshes = True
            for o in sel:
                if o.type != 'MESH':
                    bool_meshes = False

        if len(sel) != 2 and not bool_working:
            layout = self.layout
            layout.label(icon='INFO')
            layout.label(text="Please, select two different objects")
            layout.label(text="Select first the Component object, then select")
            layout.label(text="the Base mesh")
        elif not bool_meshes and not bool_working:
            layout = self.layout
            layout.label(icon='INFO')
            layout.label(text="Please, select two Mesh objects")
        else:
            try:
                ob0 = bpy.data.objects[self.generator]
            except:
                ob0 = bpy.context.active_object
                self.generator = ob0.name

            for o in sel:
                if (o.name == ob0.name or o.type != 'MESH'):
                    continue
                else:
                    ob1 = o
                    self.component = o.name
                    self.no_component = False
                    break

            # Checks for Tool Shelf panel, it lost the original Selection
            if bpy.context.active_object.name == self.object_name:
                # checks if the objects were deleted
                ob1 = bpy.context.active_object.tissue_tessellate.component
                self.component = ob1.name

                ob0 = bpy.context.active_object.tissue_tessellate.generator
                self.generator = ob0.name
                self.no_component = False

            # new object name
            if self.object_name == "":
                if self.generator == "":
                    self.object_name = "Tessellation"
                else:
                    self.object_name = self.generator + "_Tessellation"

            layout = self.layout
            # Base and Component
            col = layout.column(align=True)
            row = col.row(align=True)
            row.label(text="BASE : " + self.generator)
            row.label(text="COMPONENT : " + self.component)
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(self, "gen_modifiers", text="Use Modifiers", icon='MODIFIER')

            if len(bpy.data.objects[self.generator].modifiers) == 0:
                col2.enabled = False
                self.gen_modifiers = False
            row.separator()
            col2 = row.column(align=True)
            col2.prop(self, "com_modifiers", text="Use Modifiers", icon='MODIFIER')

            if len(bpy.data.objects[self.component].modifiers) == 0:
                col2.enabled = False
                self.com_modifiers = False

            # General
            col = layout.column(align=True)
            col.label(text="New Object Name:")
            col.prop(self, "object_name")

            # Count number of faces
            try:
                polygons = 0
                if self.gen_modifiers:
                    me_temp = ob0.to_mesh(
                                    bpy.context.depsgraph,
                                    apply_modifiers=True
                                    )
                else:
                    me_temp = ob0.data

                for p in me_temp.polygons:
                    if not self.bool_selection or p.select:
                        if self.fill_mode == "FAN":
                            polygons += len(p.vertices)
                        else:
                            polygons += 1

                if self.com_modifiers:
                    me_temp = bpy.data.objects[self.component].to_mesh(
                                            bpy.context.depsgraph,
                                            apply_modifiers=True
                                            )
                else:
                    me_temp = bpy.data.objects[self.component].data
                polygons *= len(me_temp.polygons)

                str_polygons = '{:0,.0f}'.format(polygons)
                if polygons > 200000:
                    col.label(text=str_polygons + " polygons will be created!",
                              icon='ERROR')
                else:
                    col.label(text=str_polygons + " faces will be created!",
                              icon='INFO')
            except:
                pass
            col.separator()

            # Fill and Rotation
            row = col.row(align=True)
            row.label(text="Fill Mode:")
            row.label(text="Rotation:")
            row = col.row(align=True)
            #col2 = row.column(align=True)
            row.prop(
                self, "fill_mode", text="", icon='NONE', expand=False,
                slider=True, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)

            # Rotation
            row.separator()
            col2 = row.column(align=True)
            col2.prop(
                self, "rotation_mode", text="", icon='NONE', expand=False,
                slider=True, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)
            if self.rotation_mode == 'RANDOM':
                col2.prop(self, "random_seed")

            if self.rotation_mode == 'UV':
                uv_error = False
                if self.fill_mode == 'FAN':
                    row = col.row(align=True)
                    row.label(text="UV rotation doesn't work in FAN mode",
                              icon='ERROR')
                    uv_error = True

                if len(ob0.data.uv_layers) == 0:
                    row = col.row(align=True)
                    check_name = self.generator
                    row.label(text="'" + check_name +
                              "' doesn't have UV Maps", icon='ERROR')
                    uv_error = True
                if uv_error:
                    row = col.row(align=True)
                    row.label(text="Default rotation will be used instead",
                              icon='INFO')

            # Component XY
            row = col.row(align=True)
            row.label(text="Component XY:")
            row = col.row(align=True)
            row.prop(
                self, "mode", text="Component XY", icon='NONE', expand=True,
                slider=False, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)

            # Component Z
            col.label(text="Component Z:")
            row = col.row(align=True)
            row.prop(
                self, "scale_mode", text="Scale Mode", icon='NONE', expand=True,
                slider=False, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)
            col.prop(
                self, "zscale", text="Scale", icon='NONE', expand=False,
                slider=True, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)
            col.prop(
                self, "offset", text="Offset", icon='NONE', expand=False,
                slider=True, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)

            # Merge
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(self, "merge")
            if self.merge:
                row.prop(self, "merge_thres")
            row = col.row(align=True)

            row = col.row(align=True)
            row.prop(self, "bool_smooth")
            if self.merge:
                row.prop(self, "bool_dissolve_seams")

            # LIMITED TESSELLATION
            col = layout.column(align=True)
            col.label(text="Limited Tessellation:")
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(self, "bool_selection", text="On selected Faces", icon='RESTRICT_SELECT_OFF')
            row.separator()
            col2 = row.column(align=True)
            col2.prop(self, "bool_material_id", icon='MATERIAL_DATA', text="Material ID")
            if self.bool_material_id:
                #col2 = row.column(align=True)
                col2.prop(self, "material_id")

            # ADVANCED #
            col = layout.column(align=True)
            col.label(text="Advanced Settings:")
            # vertex group + shape keys
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(self, "bool_vertex_group", icon='GROUP_VERTEX')
            #col2.prop_search(props, "vertex_group", props.generator, "vertex_groups")

            if len(ob0.vertex_groups) == 0:
                col2.enabled = False
            row.separator()
            col2 = row.column(align=True)
            row2 = col2.row(align=True)
            row2.prop(self, "bool_shapekeys", text="Use Shape Keys",  icon='SHAPEKEY_DATA')

            if len(ob0.vertex_groups) == 0 or \
                    ob1.data.shape_keys is None:
                row2.enabled = False
                #props.bool_shapekeys = False
            elif len(ob0.vertex_groups) == 0 or \
                    ob1.data.shape_keys is not None:
                if len(ob1.data.shape_keys.key_blocks) < 2:
                    row2.enabled = False
                    #prop.bool_shapekeys = False

            # TRANFER DATA
            if self.fill_mode != 'PATCH':
                col = layout.column(align=True)
                col.label(text="Component Data:")
                row = col.row(align=True)
                col2 = row.column(align=True)
                col2.prop(self, "bool_materials", icon='MATERIAL_DATA')
                row.separator()
                col2 = row.column(align=True)
                col2.prop(self, "bool_crease", icon='EDGESEL')
                if self.fill_mode == 'PATCH':
                    col.enabled = False
                    col.label(text='Not needed in Patch mode', icon='INFO')

    def execute(self, context):
        try:
            ob0 = bpy.context.active_object
            self.generator = ob0.name
        except:
            self.report({'ERROR'}, "A Generator mesh object must be selected")

        # managing handlers for realtime update
        old_handlers = []
        for h in bpy.app.handlers.frame_change_post:
            if "anim_tessellate" in str(h):
                old_handlers.append(h)
        for h in old_handlers: bpy.app.handlers.frame_change_post.remove(h)
        bpy.app.handlers.frame_change_post.append(anim_tessellate)

        # component object
        sel = bpy.context.selected_objects
        no_component = True
        for o in sel:
            if (o.name == ob0.name or o.type != 'MESH'):
                continue
            else:
                ob1 = o
                self.component = o.name
                no_component = False
                break

        # Checks for Tool Shelf panel, it lost the original Selection
        if bpy.context.active_object == self.object_name:
            ob1 = bpy.data.objects[context.object.tissue_tessellate.component]
            self.component = ob1.name
            ob0 = bpy.data.objects[context.object.tissue_tessellate.generator]
            self.generator = ob0.name
            no_component = False

        if no_component:
            # self.report({'ERROR'}, "A component mesh object must be selected")
            return {'CANCELLED'}

        # new object name
        if self.object_name == None:
            if self.generator == "":
                self.object_name = "Tessellation"
            else:
                self.object_name = self.generator.name + "_Tessellation"

        if ob1.type != 'MESH':
            message = "Component must be Mesh Objects!"
            self.report({'ERROR'}, message)
            self.component = None

        if ob0.type != 'MESH':
            message = "Generator must be Mesh Objects!"
            self.report({'ERROR'}, message)
            self.generator = ""
        if self.component != "" and self.generator != "":
            if bpy.ops.object.select_all.poll():
                bpy.ops.object.select_all(action='TOGGLE')

            if self.fill_mode == 'PATCH':
                new_ob = tassellate_patch(
                        ob0, ob1, self.offset, self.zscale,
                        self.com_modifiers, self.mode, self.scale_mode,
                        self.rotation_mode, self.random_seed,
                        self.bool_vertex_group, self.bool_selection,
                        self.bool_shapekeys, self.bool_material_id,
                        self.material_id
                        )
            else:
                new_ob = tassellate(
                        ob0, ob1, self.offset, self.zscale, self.gen_modifiers,
                        self.com_modifiers, self.mode, self.scale_mode,
                        self.rotation_mode, self.random_seed, self.fill_mode,
                        self.bool_vertex_group, self.bool_selection,
                        self.bool_shapekeys, self.bool_material_id,
                        self.material_id
                        )

            if new_ob == 0:
                message = "Zero faces selected in the Base mesh!"
                self.report({'ERROR'}, message)
                return {'CANCELLED'}

            new_ob.name = self.object_name

            new_ob.location = ob0.location
            new_ob.matrix_world = ob0.matrix_world

            if self.fill_mode != 'PATCH':
                bpy.context.collection.objects.link(new_ob)
            new_ob.select_set(True)
            bpy.context.view_layer.objects.active = new_ob


            # MERGE VERTICES
            if self.merge and self.bool_dissolve_seams and self.fill_mode != 'PATCH':
                # map seams
                bm = bmesh.new()
                bm.from_mesh(ob1.data)
                seams = []
                for f in bm.faces:
                    for e in f.edges:
                        seams.append(e.seam)
                bm = bmesh.new()
                bm.from_mesh(new_ob.data)
                count = 0
                for f in bm.faces:
                    for e in f.edges:
                        new_ob.data.edges[e.index].use_seam = seams[count % len(seams)]
                        count+=1
                new_ob.data.edges.update()

            if self.merge:
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_mode(
                    use_extend=False, use_expand=False, type='VERT')
                bpy.ops.mesh.select_non_manifold(
                    extend=False, use_wire=False, use_boundary=True,
                    use_multi_face=False, use_non_contiguous=False,
                    use_verts=False)
                bpy.ops.mesh.remove_doubles(
                    threshold=self.merge_thres, use_unselected=False)
                bpy.ops.object.mode_set(mode='OBJECT')
                if self.bool_dissolve_seams:
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_mode(type='EDGE')
                    bpy.ops.mesh.select_all(action='DESELECT')
                    bpy.ops.object.mode_set(mode='OBJECT')
                    for e in new_ob.data.edges:
                        e.select = e.use_seam
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.dissolve_edges()
                    bpy.ops.object.mode_set(mode='OBJECT')

            # store object properties
            new_ob = store_parameters(self, new_ob)

            self.object_name = new_ob.name
            self.working_on = self.object_name

        if not self.fill_mode == 'PATCH':
            # EDGE CREASES
            if self.bool_crease:
                creases = [e.crease for e in ob1.data.edges]
                for e in new_ob.data.edges:
                    e.crease = creases[e.index % len(creases)]

            # MATERIALS
            if self.bool_materials:
                try:
                    # create materials list
                    polygon_materials = [p.material_index for p in ob1.data.polygons] * int(
                            len(new_ob.data.polygons) / len(ob1.data.polygons))
                    # assign old material
                    component_materials = [slot.material for slot in ob1.material_slots]
                    for i in range(len(component_materials)):
                        bpy.ops.object.material_slot_add()
                        bpy.context.object.material_slots[i].material = \
                            component_materials[i]
                    for i in range(len(new_ob.data.polygons)):
                        new_ob.data.polygons[i].material_index = polygon_materials[i]
                except:
                    pass

        # smooth
        if self.bool_smooth: bpy.ops.object.shade_smooth()
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class update_tessellate(Operator):
    bl_idname = "object.update_tessellate"
    bl_label = "Refresh"
    bl_description = ("Fast update the tessellated mesh according to base and "
                      "component changes")
    bl_options = {'REGISTER', 'UNDO'}

    go = False

    @classmethod
    def poll(cls, context):
        try:
            return context.object.tissue_tessellate.generator != None and \
                context.object.tissue_tessellate.component != None
        except:
            return False

    @staticmethod
    def check_gen_comp(checking):
        # note pass the stored name key in here to check it out
        return checking in bpy.data.objects.keys()

    def execute(self, context):
        start_time = time.time()

        # managing handlers for realtime update
        old_handlers = []
        for h in bpy.app.handlers.frame_change_post:
            if "anim_tessellate" in str(h):
                old_handlers.append(h)
        for h in old_handlers: bpy.app.handlers.frame_change_post.remove(h)
        bpy.app.handlers.frame_change_post.append(anim_tessellate)

        ob = bpy.context.active_object
        if not self.go:
            generator = ob.tissue_tessellate.generator
            component = ob.tissue_tessellate.component
            zscale = ob.tissue_tessellate.zscale
            scale_mode = ob.tissue_tessellate.scale_mode
            rotation_mode = ob.tissue_tessellate.rotation_mode
            offset = ob.tissue_tessellate.offset
            merge = ob.tissue_tessellate.merge
            merge_thres = ob.tissue_tessellate.merge_thres
            gen_modifiers = ob.tissue_tessellate.gen_modifiers
            com_modifiers = ob.tissue_tessellate.com_modifiers
            bool_random = ob.tissue_tessellate.bool_random
            random_seed = ob.tissue_tessellate.random_seed
            fill_mode = ob.tissue_tessellate.fill_mode
            bool_vertex_group = ob.tissue_tessellate.bool_vertex_group
            bool_selection = ob.tissue_tessellate.bool_selection
            bool_shapekeys = ob.tissue_tessellate.bool_shapekeys
            mode = ob.tissue_tessellate.mode
            bool_smooth = ob.tissue_tessellate.bool_smooth
            bool_materials = ob.tissue_tessellate.bool_materials
            bool_crease = ob.tissue_tessellate.bool_crease
            bool_dissolve_seams = ob.tissue_tessellate.bool_dissolve_seams
            bool_material_id = ob.tissue_tessellate.bool_material_id
            material_id = ob.tissue_tessellate.material_id

        try:
            generator.name
            component.name
        except:
            self.report({'ERROR'},
                        "Active object must be Tessellate before Update")
            return {'CANCELLED'}

        mod_visibility = [m.show_viewport for m in bpy.context.object.modifiers]
        for m in ob.modifiers: m.show_viewport = False

        ob0 = generator
        ob1 = component

        if fill_mode == 'PATCH':
            temp_ob = tassellate_patch(
                    ob0, ob1, offset, zscale, com_modifiers, mode, scale_mode,
                    rotation_mode, random_seed, bool_vertex_group,
                    bool_selection, bool_shapekeys, bool_material_id, material_id
                    )
        else:
            temp_ob = tassellate(
                    ob0, ob1, offset, zscale, gen_modifiers, com_modifiers,
                    mode, scale_mode, rotation_mode, random_seed, fill_mode,
                    bool_vertex_group, bool_selection, bool_shapekeys,
                    bool_material_id, material_id
                    )

        if temp_ob == 0:
            for m, vis in zip(ob.modifiers, mod_visibility): m.show_viewport = vis
            message = "Zero faces selected in the Base mesh!"
            self.report({'ERROR'}, message)
            return {'CANCELLED'}

        ob.data = temp_ob.data.copy()

        # copy vertex group
        if bool_vertex_group:
            for vg in temp_ob.vertex_groups:
                if not vg.name in ob.vertex_groups.keys():
                    ob.vertex_groups.new(name=vg.name)
                new_vg = ob.vertex_groups[vg.name]
                for i in range(len(ob.data.vertices)):
                    weight = vg.weight(i)
                    new_vg.add([i], weight, 'REPLACE')

        bpy.data.objects.remove(temp_ob)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob

        if fill_mode != 'PATCH':
            # EDGE CREASES
            if bool_crease:
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.transform.edge_crease(value=1)
                bpy.ops.object.mode_set(mode='OBJECT')

                bm = bmesh.new()
                bm.from_mesh(ob1.data)
                creases = []
                for f in bm.faces:
                    for e in f.edges:
                        creases.append(ob1.data.edges[e.index].crease)

                bm.from_mesh(ob.data)
                count = 0
                for f in bm.faces:
                    for e in f.edges:
                        ob.data.edges[e.index].crease = creases[count % len(creases)]
                        count+=1
                ob.data.edges.update()

            # MATERIALS
            if bool_materials:
                try:
                    # create materials list
                    polygon_materials = [p.material_index for p in ob1.data.polygons] * int(
                            len(ob.data.polygons) / len(ob1.data.polygons))
                    # assign old material
                    component_materials = [slot.material for slot in ob1.material_slots]
                    for i in range(len(component_materials)):
                        bpy.ops.object.material_slot_add()
                        bpy.context.object.material_slots[i].material = \
                            component_materials[i]
                    for i in range(len(ob.data.polygons)):
                        ob.data.polygons[i].material_index = polygon_materials[i]
                except:
                    pass

        # MERGE VERTICES
        if merge and bool_dissolve_seams and fill_mode != 'PATCH':
            # map seams
            bm = bmesh.new()
            bm.from_mesh(ob1.data)
            seams = []
            for f in bm.faces:
                for e in f.edges:
                    seams.append(e.seam)
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            count = 0
            for f in bm.faces:
                for e in f.edges:
                    ob.data.edges[e.index].use_seam = seams[count % len(seams)]
                    count+=1
            ob.data.edges.update()

        if merge:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(
                use_extend=False, use_expand=False, type='VERT')
            bpy.ops.mesh.select_non_manifold(
                extend=False, use_wire=False, use_boundary=True,
                use_multi_face=False, use_non_contiguous=False, use_verts=False)
            bpy.ops.mesh.remove_doubles(
                threshold=merge_thres, use_unselected=False)
            bpy.ops.object.mode_set(mode='OBJECT')
            if bool_dissolve_seams:
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_mode(type='EDGE')
                bpy.ops.mesh.select_all(action='DESELECT')
                bpy.ops.object.mode_set(mode='OBJECT')
                for e in ob.data.edges:
                    e.select = e.use_seam
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.dissolve_edges()

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='OBJECT')

        if bool_smooth: bpy.ops.object.shade_smooth()

        for m, vis in zip(ob.modifiers, mod_visibility): m.show_viewport = vis

        end_time = time.time()
        print(end_time-start_time)

        return {'FINISHED'}

    def check(self, context):
        return True

class tessellate_panel(Panel):
    bl_label = "Tissue Tools"
    bl_category = "Tissue"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    #bl_options = {'DEFAULT_OPEN'}

    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.label(text="Tessellate:")
        col.operator("object.tessellate")
        col.separator()
        #col = layout.column(align=True)
        #col.label(text="Tessellate Edit:")
        #col.operator("object.settings_tessellate")
        col.operator("object.update_tessellate", icon='FILE_REFRESH')

        #col = layout.column(align=True)
        col.operator("mesh.rotate_face", icon='FACESEL')

        col.separator()
        col.label(text="Other:")
        col.operator("object.dual_mesh")
        col.operator("object.lattice_along_surface", icon="OUTLINER_OB_LATTICE")

        act = context.active_object
        if act and act.type == 'MESH':
            col.operator("object.uv_to_mesh", icon="GROUP_UVS")


class tessellate_object_panel(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_label = "Tissue - Tessellate"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):

        # managing handlers for realtime update
        old_handlers = []
        for h in bpy.app.handlers.frame_change_post:
            if "anim_tessellate" in str(h):
                old_handlers.append(h)
        for h in old_handlers: bpy.app.handlers.frame_change_post.remove(h)
        bpy.app.handlers.frame_change_post.append(anim_tessellate)

        ob = context.object
        props = ob.tissue_tessellate
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(props, "bool_run", text="Animatable")
        row.operator("object.update_tessellate", icon='FILE_REFRESH')
        if props.generator == None or props.component == None:
            col.enabled = False


        col = layout.column(align=True)
        row = col.row(align=True)
        row.label(text="BASE :")
        row.label(text="COMPONENT :")
        row = col.row(align=True)

        col2 = row.column(align=True)
        #col2.prop_search(props, "generator", bpy.data, "objects", text="")
        #col2.prop_search(props, "generator", context.scene, "objects")

        row2 = col2.row(align=True)
        row2.prop_search(props, "generator", context.scene, "objects")
        if props.fill_mode != 'PATCH':
            row2.prop(props, "gen_modifiers", text="", icon='MODIFIER')

        row.separator()
        col2 = row.column(align=True)

        row2 = col2.row(align=True)
        row2.prop_search(props, "component", context.scene, "objects")
        row2.prop(props, "com_modifiers", text="", icon='MODIFIER')

        #row.separator()
        #col2 = row.column(align=True)
        #col2.prop_search(props, "component", context.scene, "objects", text="")
        #bool_tessellated = False
        try: bool_tessellated = props.generator and props.component != None
        except: bool_tessellated = False
        if bool_tessellated:
            row = col.row(align=True)
            col2 = row.column(align=True)
            #col2.prop(props, "gen_modifiers", text="", icon='MODIFIER')

            if len(props.generator.modifiers) == 0 or props.fill_mode == 'PATCH':
                col2.enabled = False
                #props.gen_modifiers = False

            col2 = row.column(align=True)
            #col2.prop(props, "com_modifiers", text="Use Modifiers")

            if len(props.component.modifiers) == 0:
                col2.enabled = False
                #props.com_modifiers = False
            col.separator()

            # Fill and Rotation
            row = col.row(align=True)
            row.label(text="Fill Mode:")
            row.separator()
            row.label(text="Rotation:")
            row = col.row(align=True)

            # fill
            row.prop(props, "fill_mode", text="", icon='NONE', expand=False,
                     slider=True, toggle=False, icon_only=False, event=False,
                     full_event=False, emboss=True, index=-1)
            row.separator()

            # rotation
            col2 = row.column(align=True)
            col2.prop(props, "rotation_mode", text="", icon='NONE', expand=False,
                     slider=True, toggle=False, icon_only=False, event=False,
                     full_event=False, emboss=True, index=-1)

            if props.rotation_mode == 'RANDOM':
                #row = col.row(align=True)
                col2.prop(props, "random_seed")

            if props.rotation_mode == 'UV':
                uv_error = False
                if props.fill_mode == 'FAN':
                    row = col.row(align=True)
                    row.label(text="UV rotation doesn't work in FAN mode",
                              icon='ERROR')
                    uv_error = True

                if len(props.generator.data.uv_layers) == 0:
                    row = col.row(align=True)
                    row.label(text="'" + props.generator.name +
                              " doesn't have UV Maps", icon='ERROR')
                    uv_error = True
                if uv_error:
                    row = col.row(align=True)
                    row.label(text="Default rotation will be used instead",
                              icon='INFO')

            # component XY
            row = col.row(align=True)
            row.label(text="Component XY:")
            row = col.row(align=True)
            row.prop(props, "mode", expand=True)

            # component Z
            col.label(text="Component Z:")
            row = col.row(align=True)
            row.prop(props, "scale_mode", expand=True)
            col.prop(props, "zscale", text="Scale", icon='NONE', expand=False,
                     slider=True, toggle=False, icon_only=False, event=False,
                     full_event=False, emboss=True, index=-1)
            col.prop(props, "offset", text="Offset", icon='NONE', expand=False,
                     slider=True, toggle=False, icon_only=False, event=False,
                     full_event=False, emboss=True, index=-1)


            # merge
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(props, "merge")
            if props.merge:
                row.prop(props, "merge_thres")
            row = col.row(align=True)
            row.prop(props, "bool_smooth")
            if props.merge:
                row.prop(props, "bool_dissolve_seams")

            # LIMITED TESSELLATION
            col = layout.column(align=True)
            col.label(text="Limited Tessellation:")
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(props, "bool_selection", text="On selected Faces", icon='RESTRICT_SELECT_OFF')
            row.separator()
            col2 = row.column(align=True)
            col2.prop(props, "bool_material_id", icon='MATERIAL_DATA', text="Material ID")
            if props.bool_material_id:
                #col2 = row.column(align=True)
                col2.prop(props, "material_id")

            # ADVANCED #
            col = layout.column(align=True)
            col.label(text="Advanced Settings:")
            # vertex group + shape keys
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(props, "bool_vertex_group", icon='GROUP_VERTEX')
            #col2.prop_search(props, "vertex_group", props.generator, "vertex_groups")

            if len(props.generator.vertex_groups) == 0:
                col2.enabled = False
            row.separator()
            col2 = row.column(align=True)
            row2 = col2.row(align=True)
            row2.prop(props, "bool_shapekeys", text="Use Shape Keys",  icon='SHAPEKEY_DATA')

            if len(props.generator.vertex_groups) == 0 or \
                    props.component.data.shape_keys is None:
                row2.enabled = False
                #props.bool_shapekeys = False
            elif len(props.generator.vertex_groups) == 0 or \
                    props.component.data.shape_keys is not None:
                if len(props.component.data.shape_keys.key_blocks) < 2:
                    row2.enabled = False
                    #prop.bool_shapekeys = False

            # TRANFER DATA
            if props.fill_mode != 'PATCH':
                col = layout.column(align=True)
                col.label(text="Component Data:")
                row = col.row(align=True)
                col2 = row.column(align=True)
                col2.prop(props, "bool_materials", icon='MATERIAL_DATA')
                row.separator()
                col2 = row.column(align=True)
                col2.prop(props, "bool_crease", icon='EDGESEL')
                if props.fill_mode == 'PATCH':
                    col.enabled = False
                    col.label(text='Not needed in Patch mode', icon='INFO')


class rotate_face(Operator):
    bl_idname = "mesh.rotate_face"
    bl_label = "Rotate Faces"
    bl_description = "Rotate selected faces and update tessellated meshes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        ob = bpy.context.active_object
        me = ob.data
        #bpy.ops.object.mode_set(mode='OBJECT')

        bm = bmesh.from_edit_mesh(me)

        for face in bm.faces:
            if (face.select):
                vs = face.verts[:]
                vs2 = vs[1:]+vs[:1]  # put first vertex on end of list to rotate right
                # face.verts =vs2 # fails because verts is read-only
                bm.faces.remove(face)
                f2 = bm.faces.new(vs2)
                f2.select = True
                bm.normal_update()

        # trigger UI update
        bmesh.update_edit_mesh(me)
        ob.select_set(False)

        # update tessellated meshes
        bpy.ops.object.mode_set(mode='OBJECT')
        for o in [obj for obj in bpy.data.objects if
                  obj.tissue_tessellate.generator == ob]:
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.update_tessellate()
            o.select_set(False)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}

'''
classes = (
    tissue_tessellate_prop,
    tessellate,
    update_tessellate,
    tessellate_panel,
    rotate_face,
    tessellate_object_panel
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
'''
