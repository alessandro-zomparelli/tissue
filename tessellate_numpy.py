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

#from bpy.app.handlers import persistent

#@persistent
def anim_tessellate(scene):
    # store selected objects
    #scene = context.scene
    try: active_object = bpy.context.object
    except: active_object = None
    try: selected_objects = bpy.context.selected_objects
    except: selected_objects = []
    if bpy.context.mode in ('OBJECT', 'PAINT_WEIGHT'):
        old_mode = bpy.context.mode
        if old_mode == 'PAINT_WEIGHT': old_mode = 'WEIGHT_PAINT'
        for ob in scene.objects:
            if ob.tissue_tessellate.bool_run:
                hidden = ob.hide_viewport
                ob.hide_viewport = False
                for o in scene.objects:
                    if not o.hide_viewport: ob.select_set(False)
                bpy.context.view_layer.objects.active = ob
                ob.select_set(True)
                try: bpy.ops.object.update_tessellate()
                except: pass
                ob.hide_viewport = hidden
        # restore selected objects
        for o in scene.objects:
            if not o.hide_viewport: o.select_set(False)
        for o in selected_objects:
            if not o.hide_viewport: o.select_set(True)
        bpy.context.view_layer.objects.active = active_object
        try: bpy.ops.object.mode_set(mode=old_mode)
        except: pass
    return

def set_tessellate_handler(self, context):
    old_handlers = []
    for h in bpy.app.handlers.frame_change_post:
        if "anim_tessellate" in str(h):
            old_handlers.append(h)
    for h in old_handlers: bpy.app.handlers.frame_change_post.remove(h)
    for o in context.scene.objects:
        if o.tissue_tessellate.bool_run:
            bpy.app.handlers.frame_change_post.append(anim_tessellate)
            break
    return

class tissue_tessellate_prop(PropertyGroup):
    bool_hold : BoolProperty(
        name="Hold Update",
        description="Prevent automatic update while other properties are changed",
        default=False
        )
    bool_run : BoolProperty(
        name="Animatable Tessellation",
        description="Automatically recompute the tessellation when the frame is changed",
        default = False,
        update = set_tessellate_handler
        )
    zscale : FloatProperty(
        name="Scale", default=1, soft_min=0, soft_max=10,
        description="Scale factor for the component thickness",
        update = anim_tessellate_active
        )
    scale_mode : EnumProperty(
        items=(
                ('CONSTANT', "Constant", "Uniform thinkness"),
                ('ADAPTIVE', "Proportional", "Preserve component's proportions")
                ),
        default='ADAPTIVE',
        name="Z-Scale according to faces size",
        update = anim_tessellate_active
        )
    offset : FloatProperty(
        name="Surface Offset",
        default=1,
        min=-1,
        max=1,
        soft_min=-1,
        soft_max=1,
        description="Surface offset",
        update = anim_tessellate_active
        )
    mode : EnumProperty(
        items=(
            ('BOUNDS', "Bounds", "The component fits automatically the size of the target face"),
            ('LOCAL', "Local", "Based on Local coordinates, from 0 to 1"),
            ('GLOBAL', 'Global', "Based on Global coordinates, from 0 to 1")),
        default='BOUNDS',
        name="Component Mode",
        update = anim_tessellate_active
        )
    rotation_mode : EnumProperty(
        items=(('RANDOM', "Random", "Random faces rotation"),
               ('UV', "Active UV", "Rotate according to UV coordinates"),
               ('DEFAULT', "Default", "Default rotation")),
        default='DEFAULT',
        name="Component Rotation",
        update = anim_tessellate_active
        )
    fill_mode : EnumProperty(
        items=(
            ('QUAD', 'Quad', 'Regular quad tessellation. Uses only 3 or 4 vertices'),
            ('FAN', 'Fan', 'Radial tessellation for polygonal faces'),
            ('PATCH', 'Patch', 'Curved tessellation according to the last ' +
            'Subsurf\n(or Multires) modifiers. Works only with 4 sides ' +
            'patches.\nAfter the last Subsurf (or Multires) only ' +
            'deformation\nmodifiers can be used')),
        default='QUAD',
        name="Fill Mode",
        update = anim_tessellate_active
        )
    combine_mode : EnumProperty(
        items=(
            ('LAST', 'Last', 'Show only the last iteration'),
            ('UNUSED', 'Unused', 'Combine each iteration with the unused faces of the previous iteration. Used for branching systems'),
            ('ALL', 'All', 'Combine the result of all iterations')),
        default='LAST',
        name="Combine Mode",
        update = anim_tessellate_active
        )
    gen_modifiers : BoolProperty(
        name="Generator Modifiers",
        default=False,
        description="Apply Modifiers and Shape Keys to the base object",
        update = anim_tessellate_active
        )
    com_modifiers : BoolProperty(
        name="Component Modifiers",
        default=False,
        description="Apply Modifiers and Shape Keys to the component object",
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
        default=True,
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
    iterations : IntProperty(
        name="Iterations",
        default=1,
        min=1,
        soft_max=5,
        description="Automatically repeat the Tessellation using the "
                    + "generated geometry as new base object.\nUsefull for "
                    + "for branching systems. Dangerous!",
        update = anim_tessellate_active
        )
    bool_combine : BoolProperty(
        name="Combine unused",
        default=False,
        description="Combine the generated geometry with unused faces",
        update = anim_tessellate_active
        )
    bool_advanced : BoolProperty(
        name="Advanced Settings",
        default=False,
        description="Show more settings"
        )
    normals_mode : EnumProperty(
        items=(
            ('VERTS', 'Along Normals', 'Consistent direction based on vertices normal'),
            ('FACES', 'Individual Faces', 'Based on individual faces normal')),
        default='VERTS',
        name="Direction",
        update = anim_tessellate_active
        )
    bool_multi_components : BoolProperty(
        name="Multi Components",
        default=False,
        description="Combine different components according to materials name",
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
    ob.tissue_tessellate.iterations = operator.iterations
    ob.tissue_tessellate.bool_advanced = operator.bool_advanced
    ob.tissue_tessellate.normals_mode = operator.normals_mode
    ob.tissue_tessellate.bool_combine = operator.bool_combine
    ob.tissue_tessellate.bool_multi_components = operator.bool_multi_components
    ob.tissue_tessellate.combine_mode = operator.combine_mode
    ob.tissue_tessellate.bool_hold = False
    return ob

def tessellate_patch(ob0, ob1, offset, zscale, com_modifiers, mode,
               scale_mode, rotation_mode, rand_seed, bool_vertex_group,
               bool_selection, bool_shapekeys, bool_material_id, material_id):
    random.seed(rand_seed)
    if ob0.type == 'MESH': old_me0 = ob0.data      # Store generator mesh
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

    if ob0.type == 'MESH': ob0.data = me0
    verts0 = me0.vertices

    levels = 0
    sculpt_levels = 0
    render_levels = 0
    bool_multires = False
    multires_name = ""
    not_allowed  = ['FLUID_SIMULATION', 'ARRAY', 'BEVEL', 'BOOLEAN', 'BUILD',
                    'DECIMATE', 'EDGE_SPLIT', 'MASK', 'MIRROR', 'REMESH',
                    'SCREW', 'SOLIDIFY', 'TRIANGULATE', 'WIREFRAME', 'SKIN',
                    'EXPLODE', 'PARTICLE_INSTANCE', 'PARTICLE_SYSTEM', 'SMOKE']
    modifiers0 = list(ob0.modifiers)#[m for m in ob0.modifiers]
    show_modifiers = [m.show_viewport for m in ob0.modifiers]
    show_modifiers.reverse()
    modifiers0.reverse()
    for m in modifiers0:
        visible = m.show_viewport
        #m.show_viewport = False
        if m.type in ('SUBSURF', 'MULTIRES') and visible:
            levels = m.levels
            multires_name = m.name
            if m.type == 'MULTIRES':
                bool_multires = True
                multires_name = m.name
                sculpt_levels = m.sculpt_levels
                render_levels = m.render_levels
            else: bool_multires = False
            break
        elif m.type in not_allowed:
            ob0.data = old_me0
            bpy.data.meshes.remove(me0)
            return "modifiers_error"

    before = ob0.copy()
    if ob0.type == 'MESH': before.data = old_me0
    before_mod = list(before.modifiers)
    before_mod.reverse()
    for m in before_mod:
        if m.type in ('SUBSURF', 'MULTIRES') and m.show_viewport:
            before.modifiers.remove(m)
            break
        else: before.modifiers.remove(m)
    before.modifiers.update()

    before_subsurf = before.to_mesh(bpy.context.depsgraph, True)
    if len(before_subsurf.polygons)*(4**levels) != len(me0.polygons):
        if ob0.type == 'MESH': ob0.data = old_me0
        bpy.data.objects.remove(before)
        bpy.data.meshes.remove(me0)
        return "topology_error"

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
    else:
        #me1 = ob1.data
        me1 = ob1.to_mesh(bpy.context.depsgraph, apply_modifiers=False)

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
        if mode == 'BOUNDS':
            vert = v.co - min_c  # (ob1.matrix_world * v.co) - min_c
            vert[0] = (vert[0] / bb[0] if bb[0] != 0 else 0.5)
            vert[1] = (vert[1] / bb[1] if bb[1] != 0 else 0.5)
            vert[2] = (vert[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
        elif mode == 'LOCAL':
            vert = v.co.xyz
            vert[2] *= zscale
            #vert[2] = (vert[2] - min_c[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
        elif mode == 'GLOBAL':
            vert = ob1.matrix_world @ v.co
            vert[2] *= zscale
        verts1.append(vert)

    patch_faces = 4**levels
    sides = int(sqrt(patch_faces))
    sides0 = sides-2
    patch_faces0 = int((sides-2)**2)
    n_patches = int(len(me0.polygons)/patch_faces)
    if len(me0.polygons)%patch_faces != 0:
        ob0.data = old_me0
        return "topology_error"

    new_verts = []
    new_edges = []
    new_faces = []

    #bpy.ops.object.mode_set(mode='OBJECT')
    for o in bpy.context.view_layer.objects: o.select_set(False)
    #bpy.ops.object.select_all(action='DESELECT')
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
        if mode == 'BOUNDS': com_area = (bb[0]*bb[1])
        else: com_area = 1
        mult = 1/com_area*patch_faces
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

    _faces = [[[0] for ii in range(sides)] for jj in range(sides)]
    _verts = [[[0] for ii in range(sides+1)] for jj in range(sides+1)]

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
        faces = _faces.copy()
        verts = _verts.copy()
        shift1 = sides
        shift2 = sides*2-1
        shift3 = sides*3-2
        for j in range(patch_faces):
            if j < patch_faces0:
                if levels == 0:
                    u = j%sides0
                    v = j//sides0
                else:
                    u = j%sides0+1
                    v = j//sides0+1
            elif j < patch_faces0 + shift1:
                u = j-patch_faces0
                v = 0
            elif j < patch_faces0 + shift2:
                u = sides-1
                v = j-(patch_faces0 + sides)+1
            elif j < patch_faces0 + shift3:
                jj = j-(patch_faces0 + shift2)
                u = sides-jj-2
                v = sides-1
            else:
                jj = j-(patch_faces0 + shift3)
                u = 0
                v = sides-jj-2
            face = me0.polygons[j+i*patch_faces]
            faces[u][v] = face
            verts[u][v] = verts0[face.vertices[0]]
            if u == sides-1:
                verts[sides][v] = verts0[face.vertices[1]]
            if v == sides-1:
                verts[u][sides] = verts0[face.vertices[3]]
            if u == v == sides-1:
                verts[sides][sides] = verts0[face.vertices[2]]

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
        elif rotation_mode == 'UV' and ob0.type == 'MESH':
            if len(ob0.data.uv_layers) > 0:
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
            # grid coordinates
            u = int(vert[0]//step)
            v = int(vert[1]//step)
            u1 = min(u+1, sides)
            v1 = min(v+1, sides)
            if mode != 'BOUNDS':
                if u > sides-1:
                    u = sides-1
                    u1 = sides
                if u < 0:
                    u = 0
                    u1 = 1
                if v > sides-1:
                    v = sides-1
                    v1 = sides
                if v < 0:
                    v = 0
                    v1 = 1
            v00 = verts[u][v]
            v10 = verts[u1][v]
            v01 = verts[u][v1]
            v11 = verts[u1][v1]
            # factor coordinates
            fu = (vert[0]-u*step)/step
            fv = (vert[1]-v*step)/step
            fw = vert.z
            # interpolate Z scaling factor
            fvec2d = Vector((fu,fv,0))
            if scale_mode == 'ADAPTIVE':
                a00 = verts_area[v00.index]
                a10 = verts_area[v10.index]
                a01 = verts_area[v01.index]
                a11 = verts_area[v11.index]
                fw*=lerp2(a00,a10,a01,a11,fvec2d)
            # build factor vector
            fvec = Vector((fu,fv,fw))
            # interpolate vertex on patch
            patch_vert.co = lerp3(v00, v10, v01, v11, fvec)

            # Vertex Group
            if bool_vertex_group:
                for _weight, vg in zip(weight, new_patch.vertex_groups):
                    w00 = _weight[v00.index]
                    w10 = _weight[v10.index]
                    w01 = _weight[v01.index]
                    w11 = _weight[v11.index]
                    wuv = lerp2(w00,w10,w01,w11, fvec2d)
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
                for sk_v, _v in zip(source, me1.vertices):
                    if mode == 'BOUNDS':
                        sk_vert = sk_v.co - min_c  # (ob1.matrix_world * v.co) - min_c
                        sk_vert[0] = (sk_vert[0] / bb[0] if bb[0] != 0 else 0.5)
                        sk_vert[1] = (sk_vert[1] / bb[1] if bb[1] != 0 else 0.5)
                        sk_vert[2] = (sk_vert[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
                    elif mode == 'LOCAL':
                        sk_vert = sk_v.co.xyzco
                        sk_vert[2] *= zscale
                        #sk_vert[2] = (sk_vert[2] - min_c[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
                    elif mode == 'GLOBAL':
                        sk_vert = ob1.matrix_world @ sk_v.co
                        sk_vert[2] *= zscale

                    # grid coordinates
                    u = int(sk_vert[0]//step)
                    v = int(sk_vert[1]//step)
                    u1 = min(u+1, sides)
                    v1 = min(v+1, sides)
                    if mode != 'BOUNDS':
                        if u > sides-1:
                            u = sides-1
                            u1 = sides
                        if u < 0:
                            u = 0
                            u1 = 1
                        if v > sides-1:
                            v = sides-1
                            v1 = sides
                        if v < 0:
                            v = 0
                            v1 = 1
                    v00 = verts[u][v]
                    v10 = verts[u1][v]
                    v01 = verts[u][v1]
                    v11 = verts[u1][v1]
                    # factor coordinates
                    fu = (sk_vert[0]-u*step)/step
                    fv = (sk_vert[1]-v*step)/step
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

    if ob0.type == 'MESH': ob0.data = old_me0
    if not bool_correct: return 0

    bpy.ops.object.join()

    if bool_shapekeys:
        # set original values and combine Shape Keys and Vertex Groups
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

def tessellate_original(ob0, ob1, offset, zscale, gen_modifiers, com_modifiers, mode,
               scale_mode, rotation_mode, rand_seed, fill_mode,
               bool_vertex_group, bool_selection, bool_shapekeys,
               bool_material_id, material_id, normals_mode):

    random.seed(rand_seed)

    if ob0.type == 'MESH': old_me0 = ob0.data      # Store generator mesh

    me0 = ob0.to_mesh(bpy.context.depsgraph, apply_modifiers = gen_modifiers)
    if ob0.type == 'MESH': ob0.data = me0
    base_polygons = []
    base_face_normals = []

    # Check if zero faces are selected
    if (bool_selection and ob0.type == 'MESH') or bool_material_id:
        for p in ob0.data.polygons:
            if (bool_selection and ob0.type == 'MESH'):
                is_sel = p.select
            else: is_sel = True
            if bool_material_id:
                is_mat = p.material_index == material_id
            else: is_mat = True
            if is_sel and is_mat:
                base_polygons.append(p)
                base_face_normals.append(p.normal)
    else:
        base_polygons = me0.polygons
        base_face_normals = [p.normal for p in me0.polygons]
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

    me1 = ob1.to_mesh(bpy.context.depsgraph, apply_modifiers = com_modifiers)

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
        if mode == 'BOUNDS':
            vert = v.co - min_c  # (ob1.matrix_world * v.co) - min_c
            vert[0] = (vert[0] / bb[0] if bb[0] != 0 else 0.5)
            vert[1] = (vert[1] / bb[1] if bb[1] != 0 else 0.5)
            vert[2] = (vert[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
        elif mode == 'LOCAL':
            vert = v.co.xyz
            #vert[2] = (vert[2] - min_c[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
            vert[2] *= zscale
        elif mode == 'GLOBAL':
            vert = ob1.matrix_world @ v.co
            vert[2] *= zscale
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
    es1 = np.array([[i for i in e.vertices] for e in me1.edges])
    #es1 = [[i for i in e.vertices] for e in me1.edges if e.is_loose]
    new_edges = es1[:]

    # SHAPE KEYS
    if bool_shapekeys:
        basis = True #com_modifiers
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
                if mode == 'BOUNDS':
                    vert = v.co - min_c
                    vert[0] = vert[0] / bb[0]
                    vert[1] = vert[1] / bb[1]
                    vert[2] = (vert[2] + (-0.5 + offset * 0.5) * bb[2]) * zscale
                elif mode == 'LOCAL':
                    vert = v.co.xyz
                    vert[2] *= zscale
                    #vert[2] = (vert[2] - min_c[2] + (-0.5 + offset * 0.5) * bb[2]) * \
                    #          zscale
                elif mode == 'GLOBAL':
                    vert = ob1.matrix_world @ v.co
                    vert[2] *= zscale
                shapekeys.append(vert)

            # Component vertices
            key1 = np.array([v for v in shapekeys]).reshape(len(shapekeys), 3, 1)
            vx_key.append(key1[:, 0])
            vy_key.append(key1[:, 1])
            vz_key.append(key1[:, 2])
            sk_np.append([])

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
        if mode == 'BOUNDS': com_area = (bb[0]*bb[1])
        else: com_area = 1
        if com_area == 0: mult = 1
        else: mult = 1/com_area
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
                verts_area.append(1)

    # FAN tessellation mode
    if fill_mode == 'FAN':
        fan_verts = [v.co.to_tuple() for v in me0.vertices]
        fan_polygons = []
        fan_select = []
        fan_material = []
        fan_normals = []
        # selected_faces = []
        for p in base_polygons:
            # if bool_selection and not p.select: continue
            fan_center = Vector((0, 0, 0))
            center_area = 0
            for v in p.vertices:
                fan_center += me0.vertices[v].co
                if scale_mode == 'ADAPTIVE':
                    center_area += verts_area[v]
            fan_center /= len(p.vertices)
            center_area /= len(p.vertices)
            last_vert = len(fan_verts)
            fan_verts.append(fan_center.to_tuple())
            if scale_mode == 'ADAPTIVE':
                verts_area.append(center_area)

            # Vertex Group
            if bool_vertex_group:
                for w in weight:
                    center_weight = sum([w[i] for i in p.vertices]) / len(p.vertices)
                    w.append(center_weight)

            for i in range(len(p.vertices)):
                fan_polygons.append((p.vertices[i],
                                     p.vertices[(i + 1) % len(p.vertices)],
                                     last_vert, last_vert))

                if bool_material_id: fan_material.append(p.material_index)
                if bool_selection: fan_select.append(p.select)
                if normals_mode == 'FACES':
                    fan_normals.append(p.normal)

        fan_me = bpy.data.meshes.new('Fan.Mesh')
        fan_me.from_pydata(tuple(fan_verts), [], tuple(fan_polygons))
        me0 = fan_me.copy()
        bpy.data.meshes.remove(fan_me)
        verts0 = me0.vertices
        base_polygons = me0.polygons
        if normals_mode == 'FACES': base_face_normals = fan_normals

    count = 0   # necessary for UV calculation

    # TESSELLATION
    j = 0
    jj = -1
    bool_correct = False
    for p in base_polygons:
        #if fill_mode == 'FAN':
        #    jj += 1
        #    if bool_selection and not fan_select[jj]: continue
        #    if bool_material_id and not fan_material[jj] == material_id: continue
        #else:
        #    if bool_selection and not p.select: continue
        #    if bool_material_id and not p.material_index == material_id: continue

        bool_correct = True
        if rotation_mode == 'UV' and ob0.type != 'MESH':
            rotation_mode = 'DEFAULT'

        # Random rotation
        if rotation_mode == 'RANDOM':
            shifted_vertices = []
            n_poly_verts = len(p.vertices)
            rand = random.randint(0, n_poly_verts)
            for i in range(n_poly_verts):
                shifted_vertices.append(p.vertices[(i + rand) % n_poly_verts])
            verts_area0 = np.array([verts_area[i] for i in shifted_vertices])
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
        elif rotation_mode == 'UV':
            if len(ob0.data.uv_layers) > 0 and fill_mode != 'FAN':
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
            else: rotation_mode = 'DEFAULT'

        # Default rotation
        if rotation_mode == 'DEFAULT':
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

        # considering only 4 vertices
        vs0 = np.array((vs0[0], vs0[1], vs0[2], vs0[-1]))
        nvs0 = np.array((nvs0[0], nvs0[1], nvs0[2], nvs0[-1]))
        if normals_mode == 'FACES':
            fn = np.array(base_face_normals[j].to_tuple())
            nvs0 = [fn]*4

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
            poly_faces = (p.vertices[0], p.vertices[1], p.vertices[2], p.vertices[-1])
            if rotation_mode == 'RANDOM': sz = verts_area0
            else: sz = np.array([verts_area[i] for i in poly_faces])
            # Interpolate vertex height
            sz0 = sz[0] + (sz[1] - sz[0]) * vx
            sz1 = sz[3] + (sz[2] - sz[3]) * vx
            sz2 = sz0 + (sz1 - sz0) * vy
            v3 = v2 + nv2 * vz * sz2
        else:
            v3 = v2 + nv2 * vz

        if bool_vertex_group:
            w2 = []
            for _ws0 in ws0:
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
                if scale_mode == 'ADAPTIVE':
                    precise_height = True
                    if precise_height:
                        sz0 = sz[0] + (sz[1] - sz[0]) * vxk
                        sz1 = sz[3] + (sz[2] - sz[3]) * vxk
                        sz2 = sz0 + (sz1 - sz0) * vyk
                    v3_key = v2 + nv2 * vzk * sz2
                else: v3_key = v2 + nv2 * vzk
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
                    vg_np[id] = np.concatenate((vg_np[id], w2[id]), axis=0)
            # Appending faces
            for p in fs1:
                new_faces.append([i + n_verts * j for i in p])
            # Appending edges
            add_edges = es1 + (n_verts * j)
            new_edges = np.concatenate((new_edges, add_edges), axis=0)

        j += 1

    if ob0.type == 'MESH': ob0.data = old_me0

    if not bool_correct: return 0

    new_verts = new_verts_np.tolist()
    new_name = ob0.name + "_" + ob1.name
    new_me = bpy.data.meshes.new(new_name)
    new_me.from_pydata(new_verts, new_edges.tolist(), new_faces)
    new_me.update(calc_edges=True)
    new_ob = bpy.data.objects.new("tessellate_temp", new_me)

    # vertex group
    if bool_vertex_group:
        for vg in ob0.vertex_groups:
            new_ob.vertex_groups.new(name=vg.name)
            for i in range(len(vg_np[vg.index])):
                new_ob.vertex_groups[vg.name].add([i], vg_np[vg.index][i],"ADD")

    if bool_shapekeys:
        basis = com_modifiers
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
            items=(
                ('CONSTANT', "Constant", "Uniform thickness"),
                ('ADAPTIVE', "Proportional", "Preserve component's proportions")
                ),
            default='ADAPTIVE',
            name="Z-Scale according to faces size"
            )
    offset : FloatProperty(
            name="Surface Offset",
            default=1,
            min=-1, max=1,
            soft_min=-1,
            soft_max=1,
            description="Surface offset"
            )
    mode : EnumProperty(
            items=(
                ('BOUNDS', "Bounds", "The component fits automatically the size of the target face"),
                ('LOCAL', "Local", "Based on Local coordinates, from 0 to 1"),
                ('GLOBAL', 'Global', "Based on Global coordinates, from 0 to 1")),
            default='BOUNDS',
            name="Component Mode"
            )
    rotation_mode : EnumProperty(
            items=(('RANDOM', "Random", "Random faces rotation"),
                   ('UV', "Active UV", "Face rotation is based on UV coordinates"),
                   ('DEFAULT', "Default", "Default rotation")),
            default='DEFAULT',
            name="Component Rotation"
            )
    fill_mode : EnumProperty(
            items=(
                ('QUAD', 'Quad', 'Regular quad tessellation. Uses only 3 or 4 vertices'),
                ('FAN', 'Fan', 'Radial tessellation for polygonal faces'),
                ('PATCH', 'Patch', 'Curved tessellation according to the last ' +
                'Subsurf\n(or Multires) modifiers. Works only with 4 sides ' +
                'patches.\nAfter the last Subsurf (or Multires) only ' +
                'deformation\nmodifiers can be used')),
            default='QUAD',
            name="Fill Mode"
            )
    combine_mode : EnumProperty(
            items=(
                ('LAST', 'Last', 'Show only the last iteration'),
                ('UNUSED', 'Unused', 'Combine each iteration with the unused faces of the previous iteration. Used for branching systems'),
                ('ALL', 'All', 'Combine the result of all iterations')),
            default='LAST',
            name="Combine Mode",
            )
    gen_modifiers : BoolProperty(
            name="Generator Modifiers",
            default=False,
            description="Apply Modifiers and Shape Keys to the base object"
            )
    com_modifiers : BoolProperty(
            name="Component Modifiers",
            default=False,
            description="Apply Modifiers and Shape Keys to the component object"
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
            name="Map Vertex Groups",
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
            default=True,
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
    iterations : IntProperty(
            name="Iterations",
            default=1,
            min=1,
            soft_max=5,
            description="Automatically repeat the Tessellation using the "
                        + "generated geometry as new base object.\nUsefull for "
                        + "for branching systems. Dangerous!"
            )
    bool_combine : BoolProperty(
            name="Combine unused",
            default=False,
            description="Combine the generated geometry with unused faces"
            )
    bool_advanced : BoolProperty(
            name="Advanced Settings",
            default=False,
            description="Show more settings"
            )
    normals_mode : EnumProperty(
            items=(
                ('VERTS', 'Along Normals', 'Consistent direction based on vertices normal'),
                ('FACES', 'Individual Faces', 'Based on individual faces normal')),
            default='VERTS',
            name="Direction"
            )
    bool_multi_components : BoolProperty(
            name="Multi Components",
            default=False,
            description="Combine different components according to materials name"
            )
    working_on : ""

    def draw(self, context):
        allowed_obj = ('MESH', 'CURVE', 'SURFACE', 'FONT')
        try:
            bool_working = self.working_on == self.object_name and \
            self.working_on != ""
        except:
            bool_working = False

        sel = bpy.context.selected_objects

        bool_allowed = False
        if len(sel) == 2:
            bool_allowed = True
            for o in sel:
                if o.type not in allowed_obj:
                    bool_allowed = False

        if len(sel) != 2 and not bool_working:
            layout = self.layout
            layout.label(icon='INFO')
            layout.label(text="Please, select two different objects")
            layout.label(text="Select first the Component object, then select")
            layout.label(text="the Base object.")
        elif not bool_allowed and not bool_working:
            layout = self.layout
            layout.label(icon='INFO')
            layout.label(text="Only Mesh, Curve, Surface or Text objects are allowed")
        else:
            try:
                ob0 = bpy.data.objects[self.generator]
            except:
                ob0 = bpy.context.active_object
                self.generator = ob0.name

            for o in sel:
                if (o.name == ob0.name or o.type not in allowed_obj):
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
                    #self.object_name = self.generator + "_Tessellation"
                    self.object_name = "Tessellation"

            layout = self.layout
            # Base and Component
            col = layout.column(align=True)
            row = col.row(align=True)
            row.label(text="BASE : " + self.generator)
            row.label(text="COMPONENT : " + self.component)

            # Base Modifiers
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(self, "gen_modifiers", text="Use Modifiers", icon='MODIFIER')
            base = bpy.data.objects[self.generator]
            if not (base.modifiers or base.data.shape_keys):
                col2.enabled = False
                self.gen_modifiers = False

            # Component Modifiers
            row.separator()
            col3 = row.column(align=True)
            col3.prop(self, "com_modifiers", text="Use Modifiers", icon='MODIFIER')
            component = bpy.data.objects[self.component]
            if not (component.modifiers or component.data.shape_keys):
                col3.enabled = False
                self.com_modifiers = False
            col.separator()

            # General
            #col = layout.column(align=True)
            #col.label(text="New Object Name:")
            #col.prop(self, "object_name")
            '''
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
            '''

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

                if ob0.type != 'MESH':
                    row = col.row(align=True)
                    row.label(
                        text="UV rotation supported only for Mesh objects",
                        icon='ERROR')
                    uv_error = True
                else:
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
            row.label(text="Component Coordinates:")
            row = col.row(align=True)
            row.prop(
                self, "mode", text="Component XY", icon='NONE', expand=True,
                slider=False, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)

            # Component Z
            col.label(text="Thickness:")
            row = col.row(align=True)
            row.prop(
                self, "scale_mode", text="Scale Mode", icon='NONE', expand=True,
                slider=False, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)
            col.prop(
                self, "zscale", text="Scale", icon='NONE', expand=False,
                slider=True, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)
            if self.mode == 'BOUNDS':
                col.prop(
                    self, "offset", text="Offset", icon='NONE', expand=False,
                    slider=True, toggle=False, icon_only=False, event=False,
                    full_event=False, emboss=True, index=-1)

            # Direction
            row = col.row(align=True)
            row.label(text="Direction:")
            row = col.row(align=True)
            row.prop(
                self, "normals_mode", text="Direction", icon='NONE', expand=True,
                slider=False, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)
            row.enabled = self.fill_mode != 'PATCH'

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
                col2 = row.column(align=True)
                col2.prop(self, "bool_dissolve_seams")
                if ob1.type != 'MESH': col2.enabled = False

            # Advanced Settings
            col = layout.column(align=True)
            col.separator()
            col.separator()
            row = col.row(align=True)
            row.prop(self, "bool_advanced", icon='SETTINGS')
            if self.bool_advanced:
                allow_multi = False
                allow_shapekeys = True
                for m in ob0.data.materials:
                    try:
                        o = bpy.data.objects[m.name]
                        allow_multi = True
                        try:
                            if o.data.shape_keys is None: continue
                            elif len(o.data.shape_keys.key_blocks) < 2: continue
                            else: allow_shapekeys = True
                        except: pass
                    except: pass
                # DATA #
                col = layout.column(align=True)
                col.label(text="Morphing:")
                # vertex group + shape keys
                row = col.row(align=True)
                col2 = row.column(align=True)
                col2.prop(self, "bool_vertex_group", icon='GROUP_VERTEX')
                #col2.prop_search(props, "vertex_group", props.generator, "vertex_groups")
                try:
                    if len(ob0.vertex_groups) == 0:
                        col2.enabled = False
                except:
                    col2.enabled = False
                row.separator()
                col2 = row.column(align=True)
                row2 = col2.row(align=True)
                row2.prop(self, "bool_shapekeys", text="Use Shape Keys",  icon='SHAPEKEY_DATA')
                row2.enabled = allow_shapekeys

                # LIMITED TESSELLATION
                col = layout.column(align=True)
                col.label(text="Limited Tessellation:")
                row = col.row(align=True)
                col2 = row.column(align=True)
                col2.prop(self, "bool_multi_components", icon='MOD_TINT')
                if not allow_multi:
                    col2.enabled = False
                    self.bool_multi_components = False
                col.separator()
                row = col.row(align=True)
                col2 = row.column(align=True)
                col2.prop(self, "bool_selection", text="On selected Faces", icon='RESTRICT_SELECT_OFF')
                #if self.bool_material_id or self.bool_selection or self.bool_multi_components:
                    #col2 = row.column(align=True)
                #    col2.prop(self, "bool_combine")
                row.separator()
                if ob0.type != 'MESH':
                    col2.enabled = False
                col2 = row.column(align=True)
                col2.prop(self, "bool_material_id", icon='MATERIAL_DATA', text="Material ID")
                if self.bool_material_id and not self.bool_multi_components:
                    #col2 = row.column(align=True)
                    col2.prop(self, "material_id")
                col2.enabled = not self.bool_multi_components

                col.separator()
                row = col.row(align=True)
                row.label(text='Reiterate Tessellation:', icon='FILE_REFRESH')
                row.prop(self, 'iterations', text='Repeat', icon='SETTINGS')

                col.separator()
                row = col.row(align=True)
                row.label(text='Combine Iterations:')
                row = col.row(align=True)
                row.prop(
                    self, "combine_mode", icon='NONE', expand=True,
                    slider=False, toggle=False, icon_only=False, event=False,
                    full_event=False, emboss=True, index=-1)

    def execute(self, context):
        try:
            ob0 = bpy.context.active_object
            self.generator = ob0.name
        except:
            self.report({'ERROR'}, "A Generator object (Mesh, Curve, Surface, Text) must be selected")
            return {'CANCELLED'}

        # component object
        sel = bpy.context.selected_objects
        no_component = True
        allowed_obj = ('MESH', 'CURVE', 'META', 'SURFACE', 'FONT')
        for o in sel:
            if (o.name == ob0.name or o.type not in allowed_obj):
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
            self.report({'ERROR'}, "A component object (Mesh, Curve, Surface, Text) must be selected")
            return {'CANCELLED'}

        # new object name
        if self.object_name == None:
            if self.generator == "":
                self.object_name = "Tessellation"
            else:
                self.object_name = self.generator.name + "_Tessellation"
        self.object_name = "Tessellation"
        # Check if existing object with same name
        try:
            names = [o.name for o in bpy.data.objects]
            if self.object_name in names:
                count_name = 1
                while True:
                    test_name = self.object_name + '.{:03d}'.format(count_name)
                    if not test_name in names:
                        self.object_name = test_name
                        break
                    count_name += 1
        except: pass

        if ob1.type not in allowed_obj:
            message = "Component must be Mesh, Curve, Surface or Text object!"
            self.report({'ERROR'}, message)
            self.component = None

        if ob0.type not in allowed_obj:
            message = "Generator must be Mesh, Curve, Surface or Text object!"
            self.report({'ERROR'}, message)
            self.generator = ""

        if self.component not in ("",None) and self.generator not in ("",None):
            if bpy.ops.object.select_all.poll():
                bpy.ops.object.select_all(action='TOGGLE')
            bpy.ops.object.mode_set(mode='OBJECT')

            data0 = ob0.to_mesh(bpy.context.depsgraph, False)
            new_ob = bpy.data.objects.new(self.object_name, data0)
            new_ob.data.name = self.object_name
            bpy.context.collection.objects.link(new_ob)
            bpy.context.view_layer.objects.active = new_ob
            #new_ob.name = self.object_name
            new_ob.select_set(True)
            new_ob = store_parameters(self, new_ob)
            try: bpy.ops.object.update_tessellate()
            except RuntimeError as e:
                bpy.data.objects.remove(new_ob)
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}
            self.object_name = new_ob.name
            self.working_on = self.object_name
            new_ob.location = ob0.location
            new_ob.matrix_world = ob0.matrix_world
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
        #try:
        if context.object == None: return False
        return context.object.tissue_tessellate.generator != None and \
            context.object.tissue_tessellate.component != None
        #except:
        #    return False

    @staticmethod
    def check_gen_comp(checking):
        # note pass the stored name key in here to check it out
        return checking in bpy.data.objects.keys()

    def execute(self, context):
        start_time = time.time()

        ob = bpy.context.object
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
            iterations = ob.tissue_tessellate.iterations
            bool_combine = ob.tissue_tessellate.bool_combine
            normals_mode = ob.tissue_tessellate.normals_mode
            bool_advanced = ob.tissue_tessellate.bool_advanced
            bool_multi_components = ob.tissue_tessellate.bool_multi_components
            combine_mode = ob.tissue_tessellate.combine_mode

        try:
            generator.name
            component.name
        except:
            self.report({'ERROR'},
                        "Active object must be Tessellate before Update")
            return {'CANCELLED'}

        starting_mode = bpy.context.mode
        if starting_mode == 'PAINT_WEIGHT': starting_mode = 'WEIGHT_PAINT'
        bpy.ops.object.mode_set(mode='OBJECT')

        mod_visibility = [m.show_viewport for m in bpy.context.object.modifiers]
        for m in ob.modifiers: m.show_viewport = False

        ob0 = generator
        ob1 = component

        if fill_mode == 'PATCH':
            new_ob = ob0.copy()
            new_ob.data = ob0.data.copy()
            bpy.context.collection.objects.link(new_ob)
        else:
            data0 = ob0.to_mesh(bpy.context.depsgraph, gen_modifiers)
            if ob0.type == 'MESH': new_ob = ob0.copy()
            else: new_ob = bpy.data.objects.new("_temp_tessellation_", data0)
            bpy.context.collection.objects.link(new_ob)
        bpy.context.view_layer.objects.active = new_ob

        #new_ob.location = ob.location
        #new_ob.matrix_world = ob.matrix_world
        new_ob.modifiers.update()
        bpy.ops.object.select_all(action='DESELECT')
        iter_objects = [new_ob]
        base_ob = new_ob#.copy()

        for iter in range(iterations):
            same_iteration = []
            matched_materials = []
            if bool_multi_components: mat_iter = len(base_ob.material_slots)
            else: mat_iter = 1
            for m_id in range(mat_iter):
                if bool_multi_components:
                    try:
                        mat = base_ob.material_slots[m_id].material
                        ob1 = bpy.data.objects[mat.name]
                        material_id = m_id
                        matched_materials.append(m_id)
                        bool_material_id = True
                    except:
                        continue

                # EDGES CREASE for QUAD and FAN
                do_crease = bool_crease
                data1 = ob1.to_mesh(bpy.context.depsgraph, com_modifiers)
                verts1 = len(data1.vertices)
                n_edges1 = len(data1.edges)
                if bool_crease:
                    creases1 = [0]*n_edges1
                    data1.edges.foreach_get("crease", creases1)
                    do_crease = sum(creases1) > 0

                if iter != 0: gen_modifiers = True
                if fill_mode == 'PATCH':
                    new_ob = tessellate_patch(
                            base_ob, ob1, offset, zscale, com_modifiers, mode, scale_mode,
                            rotation_mode, random_seed, bool_vertex_group,
                            bool_selection, bool_shapekeys, bool_material_id, material_id
                            )
                else:
                    new_ob = tessellate_original(
                            base_ob, ob1, offset, zscale, gen_modifiers, com_modifiers,
                            mode, scale_mode, rotation_mode, random_seed, fill_mode,
                            bool_vertex_group, bool_selection, bool_shapekeys,
                            bool_material_id, material_id, normals_mode
                            )
                    if type(new_ob) is bpy.types.Object:
                        bpy.context.collection.objects.link(new_ob)
                        #new_ob.select_set(True)
                        bpy.context.view_layer.objects.active = new_ob
                    else:
                        continue
                    n_components = int(len(new_ob.data.edges) / n_edges1)
                    # EDGE CREASES
                    if do_crease:
                        for o in iter_objects:
                            o.select_set(False)
                        bpy.ops.object.mode_set(mode='EDIT')
                        bpy.ops.mesh.select_all(action='SELECT')
                        bpy.ops.transform.edge_crease(value=1)
                        bpy.ops.object.mode_set(mode='OBJECT')
                        all_creases = creases1*n_components
                        new_ob.data.edges.foreach_set('crease', all_creases)
                    # MATERIALS
                    if bool_materials or bool_material_id:
                        #try:
                        # create materials list
                        n_poly1 = len(data1.polygons)
                        polygon_materials = [0]*n_poly1
                        data1.polygons.foreach_get("material_index", polygon_materials)
                        polygon_materials *= n_components
                        # assign old material
                        for m in ob1.material_slots: new_ob.data.materials.append(m.material)
                        new_ob.data.polygons.foreach_set("material_index", polygon_materials)
                        new_ob.data.update() ###
                        #except:
                        #    pass
                    # SELECTION
                    if bool_selection:
                        try:
                            # create selection list
                            polygon_selection = [p.select for p in ob1.data.polygons] * int(
                                    len(new_ob.data.polygons) / len(ob1.data.polygons))
                            new_ob.data.polygons.foreach_set("select", polygon_selection)
                            #for i in range(len(new_ob.data.polygons)):
                            #    new_ob.data.polygons[i].select = polygon_selection[i]
                        except:
                            pass
                    # SEAMS
                    if merge and bool_dissolve_seams and fill_mode != 'PATCH' and ob1.type == 'MESH':
                        seams = [0]*n_edges1
                        data1.edges.foreach_get("use_seam",seams)
                        seams = seams*n_components
                        new_ob.data.edges.foreach_set("use_seam",seams)

                if type(new_ob) == str: break

                if bool_multi_components and type(new_ob) not in (int,str):
                    same_iteration.append(new_ob)
                    new_ob.select_set(True)
                    bpy.context.view_layer.objects.active = new_ob
                #if not bool_multi_components: break

            if type(new_ob) == str: break

            #bpy.data.objects.remove(base_ob)
            if bool_multi_components:
                bpy.context.view_layer.update()
                bpy.context.view_layer.objects.active.select_set(True)
                for o in bpy.data.objects:
                    if o in same_iteration:
                        o.select_set(True)
                        #bpy.context.view_layer.objects.active = o
                        o.location = ob.location
                    else:
                        try:
                            o.select_set(False)
                        except: pass#bpy.data.objects.remove(o)
                #bpy.context.view_layer.objects.active = new_ob
                bpy.ops.object.join()
                new_ob = bpy.context.view_layer.objects.active
                new_ob.select_set(True)
                new_ob.data.update()

            #try:
            # combine object
            if (bool_selection or bool_material_id) and combine_mode == 'UNUSED':
                # remove faces from last mesh
                bm = bmesh.new()
                last_mesh = iter_objects[-1].data.copy()
                if fill_mode == 'PATCH':
                    last_mesh = iter_objects[-1].to_mesh(bpy.context.depsgraph, True)
                bm.from_mesh(last_mesh)
                bm.faces.ensure_lookup_table()
                if bool_multi_components:
                    remove_materials = matched_materials
                elif bool_material_id:
                    remove_materials = [material_id]
                else: remove_materials = []
                if bool_selection:
                    remove_faces = [f for f in bm.faces if f.material_index in remove_materials and f.select]
                else:
                    remove_faces = [f for f in bm.faces if f.material_index in remove_materials]
                bmesh.ops.delete(bm, geom=remove_faces, context='FACES')
                bm.to_mesh(last_mesh)

                last_mesh.update()
                if len(last_mesh.vertices) > 0:
                    iter_objects[-1].data = last_mesh
                    iter_objects[-1].data.update()
                else:
                    bpy.data.objects.remove(iter_objects[-1])
                    iter_objects = iter_objects[:-1]
                base_ob = new_ob.copy()
                #if bool_shapekeys and iter < iterations:
                #new_ob.data = new_ob.to_mesh(bpy.context.depsgraph, True)
                iter_objects.append(new_ob)
                new_ob.location = ob.location
                new_ob.matrix_world = ob.matrix_world
                #bpy.context.collection.objects.link(base_ob)
            elif combine_mode == 'ALL':
                base_ob = new_ob.copy()
                iter_objects.append(new_ob)
                new_ob.location = ob.location
                new_ob.matrix_world = ob.matrix_world
            else:
                #if iter_objects[0] != new_ob:
                #bpy.data.objects.remove(iter_objects[0])
                if base_ob != new_ob:
                    bpy.data.objects.remove(base_ob)
                base_ob = new_ob#.copy()
                iter_objects = [new_ob]
            #except:
            #    if iter > 0:
            #        new_ob = iter_objects[-1]
            #    break

        if new_ob == 0:
            for m, vis in zip(ob.modifiers, mod_visibility): m.show_viewport = vis
            message = "Zero faces selected in the Base mesh!"
            bpy.ops.object.mode_set(mode=starting_mode)
            self.report({'ERROR'}, message)
            return {'CANCELLED'}
        if new_ob == "modifiers_error":
            for o in iter_objects: bpy.data.objects.remove(o)
            message = "Modifiers that change the topology of the mesh \n" \
                      "after the last Subsurf (or Multires) are not allowed."
            bpy.ops.object.mode_set(mode=starting_mode)
            self.report({'ERROR'}, message)
            return {'CANCELLED'}
        if new_ob == "topology_error":
            for o in iter_objects: bpy.data.objects.remove(o)
            message = "Make sure that the topology of the mesh before \n" \
                      "the last Subsurf (or Multires) is quads only."
            try: bpy.ops.object.mode_set(mode=starting_mode)
            except: pass
            self.report({'ERROR'}, message)
            return {'CANCELLED'}

        new_ob.location = ob.location
        new_ob.matrix_world = ob.matrix_world

        ### REPEAT
        if combine_mode != 'LAST' and len(iter_objects)>0:
            if base_ob not in iter_objects: bpy.data.objects.remove(base_ob)
            for o in iter_objects:
                o.location = ob.location
                o.select_set(True)
            bpy.ops.object.join()
            new_ob.data.update()

        ob.data = new_ob.data

        # copy vertex group
        if bool_vertex_group:
            for vg in new_ob.vertex_groups:
                if not vg.name in ob.vertex_groups.keys():
                    ob.vertex_groups.new(name=vg.name)
                new_vg = ob.vertex_groups[vg.name]
                for i in range(len(ob.data.vertices)):
                    try:
                        weight = vg.weight(i)
                    except:
                        weight = 0
                    new_vg.add([i], weight, 'REPLACE')

        selected_objects = [o for o in bpy.context.selected_objects]
        for o in selected_objects: o.select_set(False)

        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob

        if fill_mode != 'PATCH':
            # MATERIALS
            if bool_materials:
                try:
                    # assign old material
                    component_materials = [slot.material for slot in ob1.material_slots]
                    for i in range(len(component_materials)):
                        bpy.ops.object.material_slot_add()
                        bpy.context.object.material_slots[i].material = \
                            component_materials[i]
                except:
                    pass
        bpy.data.objects.remove(new_ob)

        if merge:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(
                use_extend=False, use_expand=False, type='VERT')
            bpy.ops.mesh.select_non_manifold(
                extend=False, use_wire=False, use_boundary=True,
                use_multi_face=False, use_non_contiguous=False, use_verts=False)

            #bpy.ops.mesh.select_all(action='SELECT') ####

            bpy.ops.mesh.remove_doubles(
                threshold=merge_thres, use_unselected=False)

            #bpy.ops.mesh.normals_make_consistent(inside=False) ####

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
        print("Tessellation time: {:.4f} sec".format(end_time-start_time))

        for mesh in bpy.data.meshes:
            if not mesh.users: bpy.data.meshes.remove(mesh)

        for o in selected_objects:
            try: o.select_set(True)
            except: pass

        bpy.ops.object.mode_set(mode=starting_mode)
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
        col.operator("object.dual_mesh_tessellated")
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

    @classmethod
    def poll(cls, context):
        try: return context.object.type == 'MESH'
        except: return False

    def draw(self, context):
        ob = context.object
        props = ob.tissue_tessellate
        allowed_obj = ('MESH','CURVE','SURFACE','FONT')

        try:
            bool_tessellated = props.generator or props.component != None
            ob0 = props.generator
            ob1 = props.component
        except: bool_tessellated = False
        layout = self.layout
        if not bool_tessellated:
            layout.label(text="The selected object is not a Tessellated object",
                        icon='INFO')
        else:
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(props, "bool_run", text="Animatable")
            row.operator("object.update_tessellate", icon='FILE_REFRESH')

            col = layout.column(align=True)
            row = col.row(align=True)
            row.label(text="BASE :")
            row.label(text="COMPONENT :")
            row = col.row(align=True)

            col2 = row.column(align=True)
            col2.prop_search(props, "generator", context.scene, "objects")
            row.separator()
            col2 = row.column(align=True)
            col2.prop_search(props, "component", context.scene, "objects")
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(props, "gen_modifiers", text="Use Modifiers", icon='MODIFIER')
            row.separator()
            if not (ob0.modifiers or ob0.data.shape_keys) or props.fill_mode == 'PATCH':
                col2.enabled = False
            col2 = row.column(align=True)
            col2.prop(props, "com_modifiers", text="Use Modifiers", icon='MODIFIER')
            if not (props.component.modifiers or props.component.data.shape_keys):
                col2.enabled = False
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
                if props.generator.type != 'MESH':
                    row = col.row(align=True)
                    row.label(
                        text="UV rotation supported only for Mesh objects",
                        icon='ERROR')
                    uv_error = True
                else:
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
            row.label(text="Component Coordinates:")
            row = col.row(align=True)
            row.prop(props, "mode", expand=True)

            # component Z
            col.label(text="Thickness:")
            row = col.row(align=True)
            row.prop(props, "scale_mode", expand=True)
            col.prop(props, "zscale", text="Scale", icon='NONE', expand=False,
                     slider=True, toggle=False, icon_only=False, event=False,
                     full_event=False, emboss=True, index=-1)
            if props.mode == 'BOUNDS':
                col.prop(props, "offset", text="Offset", icon='NONE', expand=False,
                         slider=True, toggle=False, icon_only=False, event=False,
                         full_event=False, emboss=True, index=-1)

            # Direction
            row = col.row(align=True)
            row.label(text="Direction:")
            row = col.row(align=True)
            row.prop(
            props, "normals_mode", text="Direction", icon='NONE', expand=True,
                slider=False, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)
            row.enabled = props.fill_mode != 'PATCH'

            # merge
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(props, "merge")
            if props.merge:
                row.prop(props, "merge_thres")
            row = col.row(align=True)
            row.prop(props, "bool_smooth")
            if props.merge:
                col2 = row.column(align=True)
                col2.prop(props, "bool_dissolve_seams")
                if props.component.type != 'MESH': col2.enabled = False

            # Advanced Settings
            col = layout.column(align=True)
            col.separator()
            col.separator()
            row = col.row(align=True)
            row.prop(props, "bool_advanced", icon='SETTINGS')
            if props.bool_advanced:
                allow_multi = False
                allow_shapekeys = True
                for m in ob0.data.materials:
                    try:
                        o = bpy.data.objects[m.name]
                        allow_multi = True
                        try:
                            if o.data.shape_keys is None: continue
                            elif len(o.data.shape_keys.key_blocks) < 2: continue
                            else: allow_shapekeys = True
                        except: pass
                    except: pass
                # DATA #
                col = layout.column(align=True)
                col.label(text="Morphing:")
                row = col.row(align=True)
                col2 = row.column(align=True)
                col2.prop(props, "bool_vertex_group", icon='GROUP_VERTEX')
                #col2.prop_search(props, "vertex_group", props.generator, "vertex_groups")
                try:
                    if len(props.generator.vertex_groups) == 0:
                        col2.enabled = False
                except:
                    col2.enabled = False
                row.separator()
                col2 = row.column(align=True)
                row2 = col2.row(align=True)
                row2.prop(props, "bool_shapekeys", text="Use Shape Keys",  icon='SHAPEKEY_DATA')
                row2.enabled = allow_shapekeys

                # LIMITED TESSELLATION
                col = layout.column(align=True)
                col.label(text="Limited Tessellation:")
                row = col.row(align=True)
                col2 = row.column(align=True)
                col2.prop(props, "bool_multi_components", icon='MOD_TINT')
                if not allow_multi:
                    col2.enabled = False
                col.separator()
                row = col.row(align=True)
                col2 = row.column(align=True)
                col2.prop(props, "bool_selection", text="On selected Faces", icon='RESTRICT_SELECT_OFF')
                #if props.bool_material_id or props.bool_selection or props.bool_multi_components:
                    #col2 = row.column(align=True)
                #    col2.prop(props, "bool_combine")
                row.separator()
                if props.generator.type != 'MESH':
                    col2.enabled = False
                col2 = row.column(align=True)
                col2.prop(props, "bool_material_id", icon='MATERIAL_DATA', text="Material ID")
                if props.bool_material_id and not props.bool_multi_components:
                    #col2 = row.column(align=True)
                    col2.prop(props, "material_id")
                if props.bool_multi_components:
                    col2.enabled = False

                # TRANFER DATA ### OFF
                if props.fill_mode != 'PATCH' and False:
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

                col.separator()
                row = col.row(align=True)
                row.label(text='Reiterate Tessellation:', icon='FILE_REFRESH')
                row.prop(props, 'iterations', text='Repeat', icon='SETTINGS')
                col.separator()
                row = col.row(align=True)
                row.label(text='Combine Iterations:')
                row = col.row(align=True)
                row.prop(
                    props, "combine_mode", text="Combine:",icon='NONE', expand=True,
                    slider=False, toggle=False, icon_only=False, event=False,
                    full_event=False, emboss=True, index=-1)

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

        bm = bmesh.from_edit_mesh(me)
        mesh_select_mode = [sm for sm in context.tool_settings.mesh_select_mode]

        for face in bm.faces:
            if (face.select):
                vs = face.verts[:]
                vs2 = vs[1:]+vs[:1]  # put first vertex on end of list to rotate right
                # face.verts =vs2 # fails because verts is read-only
                material_index = face.material_index
                bm.faces.remove(face)
                f2 = bm.faces.new(vs2)
                f2.select = True
                f2.material_index = material_index
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
        context.tool_settings.mesh_select_mode = mesh_select_mode

        return {'FINISHED'}
