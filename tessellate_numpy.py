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

# ---------------------------- ADAPTIVE DUPLIFACES ----------------------------#
#-------------------------------- version 0.83 --------------------------------#
#                                                                              #
# Creates duplicates of selected mesh to active morphing the shape according   #
# to target faces.                                                             #
#                                                                              #
#                    (c)  Alessandro Zomparelli                                #
#                             (2017)                                           #
#                                                                              #
# http://www.co-de-it.com/                                                     #
#                                                                              #
################################################################################


import bpy
from mathutils import Vector
import numpy as np
from math import sqrt
import random


def lerp(a,b,t):
    return a + (b-a)*t


def lerp2(v1, v2, v3, v4, v):
    v12 = v1 + (v2-v1)*v.x
    v43 = v4 + (v3-v4)*v.x
    return v12 + (v43-v12)*v.y


def lerp3(v1, v2, v3, v4, v):
    loc = lerp2(v1.co, v2.co, v3.co, v4.co, v)
    nor = lerp2(v1.normal, v2.normal, v3.normal, v4.normal, v)
    nor.normalize()
    return loc + nor*v.z


def tassellate(ob0, ob1, offset, zscale, gen_modifiers, com_modifiers, mode,
               scale_mode, rotation_mode, rand_seed, fill_mode,
               bool_vertex_group, bool_selection, bool_shapekeys):
    random.seed(rand_seed)
    old_me0 = ob0.data      # Store generator mesh
    if gen_modifiers:       # Apply generator modifiers
        me0 = ob0.to_mesh(bpy.context.scene, apply_modifiers=True,
                          settings = 'PREVIEW')
    else: me0 = ob0.data
    ob0.data = me0
    base_polygons = []

    # Check if zero faces are selected
    if bool_selection:
        for p in ob0.data.polygons:
            if p.select: base_polygons.append(p)
    else:
        base_polygons = ob0.data.polygons
    if len(base_polygons) == 0: return 0

    # Apply component modifiers
    if com_modifiers:
        me1 = ob1.to_mesh(bpy.context.scene, apply_modifiers=True,
                          settings = 'PREVIEW')
    else: me1 = ob1.data

    verts0 = me0.vertices   # Collect generator vertices

    # Component statistics
    n_verts = len(me1.vertices)
    n_edges = len(me1.edges)
    n_faces = len(me1.polygons)

    # Component transformations
    loc = ob1.location
    dim = ob1.dimensions
    scale = ob1.scale

    # Create empty lists
    new_verts = []
    new_edges = []
    new_faces = []
    new_verts_np = np.array(())

    # Component bounding box
    min = Vector((0,0,0))
    max = Vector((0,0,0))
    first = True
    for v in me1.vertices:
        vert = v.co
        if vert[0] < min[0] or first:
            min[0] = vert[0]
        if vert[1] < min[1] or first:
            min[1] = vert[1]
        if vert[2] < min[2] or first:
            min[2] = vert[2]
        if vert[0] > max[0] or first:
            max[0] = vert[0]
        if vert[1] > max[1] or first:
            max[1] = vert[1]
        if vert[2] > max[2] or first:
            max[2] = vert[2]
        first = False
    bb = max-min

    # adaptive XY
    verts1 = []
    for v in me1.vertices:
        if mode=="ADAPTIVE":
            vert = v.co - min#( ob1.matrix_world * v.co ) - min
            vert[0] = (vert[0] / bb[0] if bb[0] != 0 else 0.5)
            vert[1] = (vert[1] / bb[1] if bb[1] != 0 else 0.5)
            vert[2] = (vert[2] + (-0.5 + offset*0.5)*bb[2])*zscale
        else:
            vert = v.co.xyz
            vert[2] = (vert[2] - min[2] + (-0.5 + offset*0.5)*bb[2])*zscale
        verts1.append(vert)

    # component vertices
    vs1 = np.array([v for v in verts1]).reshape(len(verts1),3,1)
    vx = vs1[:,0]
    vy = vs1[:,1]
    vz = vs1[:,2]

    # Component polygons
    fs1 = [[i for i in p.vertices] for p in me1.polygons]
    new_faces = fs1[:]

    # Component edges
    es1 = [[i for i in e.vertices] for e in me1.edges if e.is_loose]
    new_edges = es1[:]

    # SHAPE KEYS
    shapekeys = []
    do_shapekeys = False
    if me1.shape_keys is not None and bool_shapekeys:
        if len(me1.shape_keys.key_blocks) > 1:
            do_shapekeys = True

            # Read active key
            active_key = ob1.active_shape_key_index
            if active_key == 0: active_key = 1

            for v in me1.shape_keys.key_blocks[active_key].data:
                if mode=="ADAPTIVE":
                    vert = v.co - min
                    #vert = ( ob1.matrix_world * v.co ) - min
                    vert[0] = vert[0] / bb[0]
                    vert[1] = vert[1] / bb[1]
                    vert[2] = (vert[2] + (-0.5 + offset*0.5)*bb[2]) * zscale
                else:
                    vert = v.co.xyz
                    vert[2] = (vert[2] - min[2] + (-0.5 + offset*0.5)*bb[2]) * \
                              zscale
                shapekeys.append(vert)

            # Component vertices
            key1 = np.array([v for v in shapekeys]).reshape(len(shapekeys),3,1)
            vx_key = key1[:,0]
            vy_key = key1[:,1]
            vz_key = key1[:,2]

    # Active vertex group
    if bool_vertex_group:
        try:
            weight = []
            group_index = ob0.vertex_groups.active_index
            active_vertex_group = ob0.vertex_groups[group_index]
            for v in me0.vertices:
                try:
                    weight.append(active_vertex_group.weight(v.index))
                except:
                    weight.append(0)
        except:
            bool_vertex_group = False

    # FAN tessellation mode
    if fill_mode == 'FAN':
        fan_verts = [v.co.to_tuple() for v in me0.vertices]
        fan_polygons = []
        selected_faces = []
        for p in base_polygons:
            #if bool_selection and not p.select: continue
            fan_center = Vector((0,0,0))
            for v in p.vertices:
                fan_center += me0.vertices[v].co
            fan_center /= len(p.vertices)
            last_vert = len(fan_verts)
            fan_verts.append(fan_center.to_tuple())

            # Vertex Group
            if bool_vertex_group:
                center_weight = sum([weight[i] for i in p.vertices])/ \
                                len(p.vertices)
                weight.append(center_weight)

            for i in range(len(p.vertices)):
                fan_polygons.append((p.vertices[i],
                                     p.vertices[(i+1)%len(p.vertices)],
                                     last_vert, last_vert))
                #if bool_selection: selected_faces.append(p.select)
        fan_me = bpy.data.meshes.new('Fan.Mesh')
        fan_me.from_pydata(tuple(fan_verts), [], tuple(fan_polygons))
        me0 = fan_me
        verts0 = me0.vertices
        base_polygons = me0.polygons
        #for i in range(len(selected_faces)):
        #    fan_me.polygons[i].select = selected_faces[i]
    count = 0   # necessary for UV calculation

    # TESSELLATION
    j = 0
    for p in base_polygons:
        # Random rotation
        if rotation_mode == 'RANDOM':
            shifted_vertices = []
            n_poly_verts = len(p.vertices)
            rand = random.randint(0,n_poly_verts)
            for i in range(n_poly_verts):
                shifted_vertices.append(p.vertices[(i+rand)%n_poly_verts])
            vs0 = np.array([verts0[i].co for i in shifted_vertices])
            nvs0 = np.array([verts0[i].normal for i in shifted_vertices])
            # vertex weight
            if bool_vertex_group:
                ws0 = []
                for i in shifted_vertices:
                    try: ws0.append(weight[i])
                    except: ws0.append(0)
                ws0 = np.array(ws0)

        # UV rotation
        elif rotation_mode == 'UV' and len(ob0.data.uv_layers) > 0 \
                and fill_mode != 'FAN':
            i = p.index
            v01 = (me0.uv_layers.active.data[count].uv + \
                   me0.uv_layers.active.data[count+1].uv)
            if len(p.vertices) > 3:
                v32 = (me0.uv_layers.active.data[count+3].uv + \
                       me0.uv_layers.active.data[count+2].uv)
            else:
                v32 = (me0.uv_layers.active.data[count].uv + \
                       me0.uv_layers.active.data[count+2].uv)
            v0132 = v32-v01
            v0132.normalize()

            v12 = (me0.uv_layers.active.data[count+1].uv + \
                   me0.uv_layers.active.data[count+2].uv)
            if len(p.vertices) > 3:
                v03 = (me0.uv_layers.active.data[count].uv + \
                       me0.uv_layers.active.data[count+3].uv)
            else:
                v03 = (me0.uv_layers.active.data[count].uv + \
                       me0.uv_layers.active.data[count].uv)
            v1203 = v03 - v12
            v1203.normalize()

            vertUV = []
            dot1203 = v1203.x
            dot0132 = v0132.x
            if(abs(dot1203) < abs(dot0132)):
                if(dot0132 > 0): vertUV = p.vertices[1:] + p.vertices[:1]
                else: vertUV = p.vertices[3:] + p.vertices[:3]
            else:
                if(dot1203 < 0): vertUV = p.vertices[:]
                else: vertUV = p.vertices[2:] + p.vertices[:2]
            vs0 = np.array([verts0[i].co for i in vertUV])
            nvs0 = np.array([verts0[i].normal for i in vertUV])

            # Vertex weight
            if bool_vertex_group:
                ws0 = []
                for i in vertUV:
                    try: ws0.append(weight[i])
                    except: ws0.append(0)
                ws0 = np.array(ws0)

            count += len(p.vertices)

        # Default rotation
        else:
            vs0 = np.array([verts0[i].co for i in p.vertices])
            nvs0 = np.array([verts0[i].normal for i in p.vertices])
            # Vertex weight
            if bool_vertex_group:
                ws0 = []
                for i in p.vertices:
                    try: ws0.append(weight[i])
                    except: ws0.append(0)
                ws0 = np.array(ws0)

        # considering only 4 vertices
        vs0 = np.array((vs0[0], vs0[1], vs0[2], vs0[-1]))
        nvs0 = np.array((nvs0[0], nvs0[1], nvs0[2], nvs0[-1]))

        # remapped vertex coordinates
        v0 = vs0[0] + (vs0[1] -vs0[0])*vx
        v1 = vs0[3] + (vs0[2] -vs0[3])*vx
        v2 = v0 + (v1 - v0)*vy

        # remapped vertex normal
        nv0 = nvs0[0] + (nvs0[1] -nvs0[0])*vx
        nv1 = nvs0[3] + (nvs0[2] -nvs0[3])*vx
        nv2 = nv0 + (nv1 - nv0)*vy

        # vertex z to normal
        v3 = v2 + nv2*vz*(sqrt(p.area) if scale_mode == "ADAPTIVE" else 1)

        if bool_vertex_group:
            ws0 = np.array((ws0[0], ws0[1], ws0[2], ws0[-1]))
            # Interpolate vertex weight
            w0 = ws0[0] + (ws0[1] -ws0[0])*vx
            w1 = ws0[3] + (ws0[2] -ws0[3])*vx
            w2 = w0 + (w1 - w0)*vy

            # Shapekeys
            if do_shapekeys:
                # remapped vertex coordinates
                v0 = vs0[0] + (vs0[1] -vs0[0])*vx_key
                v1 = vs0[3] + (vs0[2] -vs0[3])*vx_key
                v2 = v0 + (v1 - v0)*vy_key
                # remapped vertex normal
                nv0 = nvs0[0] + (nvs0[1] -nvs0[0])*vx_key
                nv1 = nvs0[3] + (nvs0[2] -nvs0[3])*vx_key
                nv2 = nv0 + (nv1 - nv0)*vy_key
                # vertex z to normal
                v3_key = v2 + nv2*vz_key*(sqrt(p.area) \
                         if scale_mode == "ADAPTIVE" else 1)
                v3 = v3 + (v3_key - v3) * w2

        if j == 0:
            new_verts_np = v3
            if bool_vertex_group: new_vertex_group_np = w2
        else:
            # Appending vertices
            new_verts_np = np.concatenate((new_verts_np, v3), axis=0)
            # Appending vertex group
            if bool_vertex_group:
                new_vertex_group_np = np.concatenate((new_vertex_group_np, w2),
                                                     axis=0)
            # Appending faces
            for p in fs1: new_faces.append([i+n_verts*j for i in p])
            # Appending edges
            for e in es1: new_edges.append([i+n_verts*j for i in e])

        j += 1

    new_verts = new_verts_np.tolist()
    new_name = ob0.name + "_" + ob1.name
    new_me = bpy.data.meshes.new(new_name)
    new_me.from_pydata(new_verts, new_edges, new_faces)
    #new_me.from_pydata(new_verts, new_edges, [])
    new_me.update(calc_edges=True)
    new_ob = bpy.data.objects.new("tessellate_temp", new_me)

    # vertex group
    if bool_vertex_group:
        new_ob.vertex_groups.new("generator_group")
        for i in range(len(new_vertex_group_np)):
            new_ob.vertex_groups["generator_group"].add([i],
                                                        new_vertex_group_np[i],
                                                        "ADD")
    ob0.data = old_me0
    return new_ob


def store_parameters(operator, ob):
    ob.tissue_tessellate.generator = operator.generator
    ob.tissue_tessellate.component = operator.component
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
    return ob


class tissue_tessellate_prop(bpy.types.PropertyGroup):
    generator = bpy.props.StringProperty()
    component = bpy.props.StringProperty()
    offset = bpy.props.FloatProperty()
    zscale = bpy.props.FloatProperty(default=1)
    merge = bpy.props.BoolProperty()
    merge_thres = bpy.props.FloatProperty()
    gen_modifiers = bpy.props.BoolProperty()
    com_modifiers = bpy.props.BoolProperty()
    mode = bpy.props.StringProperty()
    rotation_mode = bpy.props.StringProperty()
    scale_mode = bpy.props.StringProperty()
    fill_mode = bpy.props.StringProperty()
    bool_random = bpy.props.BoolProperty()
    random_seed = bpy.props.IntProperty()
    vertexgroup = bpy.props.StringProperty()
    bool_vertex_group = bpy.props.BoolProperty()
    bool_selection = bpy.props.BoolProperty()
    bool_shapekeys = bpy.props.BoolProperty()


class tessellate(bpy.types.Operator):
    bl_idname = "object.tessellate"
    bl_label = "Tessellate"
    bl_description = ("Create a copy of selected object on the active object's "
                      "faces, adapting the shape to the different faces.")
    bl_options = {'REGISTER', 'UNDO'}

    object_name = bpy.props.StringProperty(
        name="", description="Name of the generated object")
    zscale = bpy.props.FloatProperty(
        name="Scale", default=1, soft_min=0, soft_max=10,
        description="Scale factor for the component thickness")
    scale_mode = bpy.props.EnumProperty(
        items=(('CONSTANT', "Constant", ""), ('ADAPTIVE', "Proportional", "")),
        default='CONSTANT', name="Z-Scale according to faces size")
    offset = bpy.props.FloatProperty(
        name="Surface Offset", default=0, min=-1, max=1,  soft_min=-1,
        soft_max=1, description="Surface offset")
    mode = bpy.props.EnumProperty(
        items=(('CONSTANT', "Constant", ""), ('ADAPTIVE', "Adaptive", "")),
        default='ADAPTIVE', name="Component Mode")
    rotation_mode = bpy.props.EnumProperty(
        items=(('RANDOM', "Random", ""), ('UV', "Active UV", ""),
        ('DEFAULT', "Default", "")), default='DEFAULT',
        name="Component Rotation")
    fill_mode = bpy.props.EnumProperty(
        items=(('QUAD', "Quad", ""), ('FAN', "Fan", "")), default='QUAD',
        name="Fill Mode")
    gen_modifiers = bpy.props.BoolProperty(
        name="Generator Modifiers", default=False,
        description="Apply modifiers to base object")
    com_modifiers = bpy.props.BoolProperty(
        name="Component Modifiers", default=False,
        description="Apply modifiers to component object")
    merge = bpy.props.BoolProperty(
        name="Merge", default=False,
        description="Merge vertices in adjacent duplicates")
    merge_thres = bpy.props.FloatProperty(
        name="Distance", default=0.001, soft_min=0, soft_max=10,
        description="Limit below which to merge vertices")
    generator = bpy.props.StringProperty(
        name="", description="Base object for the tessellation")
    component = bpy.props.StringProperty(
        name="", description="Component object for the tessellation")
    bool_random = bpy.props.BoolProperty(
        name="Randomize", default=False,
        description="Randomize component rotation")
    random_seed = bpy.props.IntProperty(
        name="Seed", default=0, soft_min=0, soft_max=10,
        description="Random seed")
    bool_vertex_group = bpy.props.BoolProperty(
        name="Map Vertex Group", default=False, description=("Map the active "
        "Vertex Group from the Base object to generated geometry"))
    bool_selection = bpy.props.BoolProperty(
        name="On selected Faces", default=False,
        description="Create Tessellation only on selected faces")
    bool_shapekeys = bpy.props.BoolProperty(
        name="Use Shape Keys", default=False, description=("Use component's "
        "active Shape Key according to active Vertex Group of the base object"))
    working_on = ""

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
                if o.type != 'MESH': bool_meshes = False

        if len(sel) != 2 and not bool_working:
            layout = self.layout
            layout.label(icon='INFO')
            layout.label(text="Please, select two different objects")
            layout.label(text="Select first the Component object, then select")
            layout.label(text="the Base mesh.")
        elif not bool_meshes and not bool_working:
            layout = self.layout
            layout.label(icon='INFO')
            layout.label(text="Please, select two Mesh objects")
        else:
            try:
                ob0 = bpy.data.Objects[self.generator]
            except:
                ob0 = bpy.context.active_object
                self.generator = ob0.name

            for o in sel:
                if(o.name == ob0.name or o.type != 'MESH'): continue
                else:
                    ob1 = o
                    self.component = o.name
                    no_component = False
                    break

            # Checks for Tool Shelf panel, it loose the original Selection
            if bpy.context.active_object.name == self.object_name:
                ob1 = bpy.data.objects[
                    bpy.context.active_object.tissue_tessellate.component]
                self.component = ob1.name
                ob0 = bpy.data.objects[
                    bpy.context.active_object.tissue_tessellate.generator]
                self.generator = ob0.name
                no_component = False

            # new object name
            if self.object_name == "":
                if self.generator == "": self.object_name = "Tessellation"
                else: self.object_name = self.generator + "_Tessellation"

            layout = self.layout
            # Base and Component
            col = layout.column(align=True)
            row = col.row(align=True)
            row.label(text="BASE : " + self.generator)
            row.label(text="COMPONENT : " + self.component)
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(self, "gen_modifiers", text="Use Modifiers")
            if len(bpy.data.objects[self.generator].modifiers) == 0:
                col2.enabled = False
                self.gen_modifiers = False
            col2 = row.column(align=True)
            col2.prop(self, "com_modifiers", text="Use Modifiers")
            if len(bpy.data.objects[self.component].modifiers) == 0:
                col2.enabled = False
                self.com_modifiers = False

            # On selected faces
            row = col.row(align=True)
            row.prop(self, "bool_selection", text="On selected Faces")
            col.separator()

            # General
            col = layout.column(align=True)
            col.label(text="New Object Name:")
            col.prop(self, "object_name")

            # Count number of faces
            try:
                polygons = 0
                if self.gen_modifiers: me_temp = ob0.to_mesh(bpy.context.scene,
                    apply_modifiers=True, settings = 'PREVIEW')
                else: me_temp = ob0.data
                for p in me_temp.polygons:
                    if not self.bool_selection or p.select:
                        if self.fill_mode == "FAN": polygons += len(p.vertices)
                        else: polygons += 1

                if self.com_modifiers: me_temp = bpy.data.objects[
                    self.component].to_mesh(bpy.context.scene,
                    apply_modifiers=True, settings = 'PREVIEW')
                else: me_temp = bpy.data.objects[self.component].data
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
            row.separator()
            row.label(text="Rotation:")
            row = col.row(align=True)

            # Fill
            row.prop(
                self, "fill_mode", text="", icon='NONE', expand=False,
                slider=True, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)
            row.separator()

            # Rotation
            row.prop(
                self, "rotation_mode", text="", icon='NONE', expand=False,
                slider=True, toggle=False, icon_only=False, event=False,
                full_event=False, emboss=True, index=-1)
            if self.rotation_mode == 'RANDOM':
                row = col.row(align=True)
                row.prop(self, "random_seed")
            if self.rotation_mode == 'UV':
                uv_error = False
                if self.fill_mode == 'FAN':
                    row = col.row(align=True)
                    row.label(text="UV rotation doesn't work in FAN mode",
                              icon='ERROR')
                    uv_error = True
                if len(bpy.data.objects[self.generator].data.uv_layers) == 0:
                    row = col.row(align=True)
                    row.label(text="'" + bpy.data.objects[self.generator].name \
                        + "' doesn't have UV Maps", icon='ERROR')
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
            if self.merge: row.prop(self, "merge_thres")
            row = col.row(align=True)

            # ADVANCED
            col = layout.column(align=True)
            col.label(text="Advanced Settings:")
            # vertex group + shape keys
            row = col.row(align=True)
            col2 = row.column(align=True)
            col2.prop(self, "bool_vertex_group")
            if len(bpy.data.objects[self.generator].vertex_groups) == 0:
                col2.enabled = False
                bool_vertex_group = False
            col2 = row.column(align=True)
            col2.prop(self, "bool_shapekeys", text="Use Shape Keys")
            if len(bpy.data.objects[self.generator].vertex_groups) == 0 or \
                    bpy.data.objects[self.component].data.shape_keys == None:
                col2.enabled = False
                bool_shapekeys = False
            elif len(bpy.data.objects[self.generator].vertex_groups) == 0 or \
                    bpy.data.objects[self.component].data.shape_keys != None:
                if len(bpy.data.objects[
                        self.component].data.shape_keys.key_blocks) < 2:
                    col2.enabled = False
                    bool_shapekeys = False

    def execute(self, context):
        try:
            ob0 = bpy.context.active_object
            self.generator = ob0.name
        except:
            self.report({'ERROR'}, "A Generator mesh object must be selected")

        # component object
        sel = bpy.context.selected_objects
        no_component = True
        for o in sel:
            if(o.name == ob0.name or o.type != 'MESH'): continue
            else:
                ob1 = o
                self.component = o.name
                no_component = False
                break

        # Checks for Tool Shelf panel, it loose the original Selection
        if bpy.context.active_object == self.object_name:
            ob1 = bpy.data.objects[
                bpy.context.active_object.tissue_tessellate.component]
            self.component = ob1.name
            ob0 = bpy.data.objects[
                bpy.context.active_object.tissue_tessellate.generator]
            self.generator = ob0.name
            no_component = False

        if(no_component):
            #self.report({'ERROR'}, "A component mesh object must be selected")
            return {'CANCELLED'}

        # new object name
        if self.object_name == "":
            if self.generator == "": self.object_name = "Tessellation"
            else: self.object_name = self.generator + "_Tessellation"

        if bpy.data.objects[self.component].type != 'MESH':
            message = "Component must be Mesh Objects!"
            self.report({'ERROR'}, message)
            self.component = ""
        if bpy.data.objects[self.generator].type != 'MESH':
            message = "Generator must be Mesh Objects!"
            self.report({'ERROR'}, message)
            self.generator = ""
        if self.component != "" and self.generator != "":
            bpy.ops.object.select_all(action='TOGGLE')

            new_ob = tassellate(
                ob0, ob1, self.offset, self.zscale, self.gen_modifiers,
                self.com_modifiers, self.mode, self.scale_mode,
                self.rotation_mode, self.random_seed, self.fill_mode,
                self.bool_vertex_group, self.bool_selection,
                self.bool_shapekeys)

            if new_ob == 0:
                message = "Zero faces selected in the Base mesh!"
                self.report({'ERROR'}, message)
                return {'CANCELLED'}

            new_ob.name = self.object_name
            #new_ob = bpy.data.objects.new(self.object_name, new_me)

            new_ob.location = ob0.location
            new_ob.matrix_world = ob0.matrix_world

            scene = bpy.context.scene
            scene.objects.link(new_ob)
            new_ob.select = True
            bpy.context.scene.objects.active = new_ob
            if self.merge:
                bpy.ops.object.mode_set(mode = 'EDIT')
                bpy.ops.mesh.select_mode(
                    use_extend=False, use_expand=False, type='VERT')
                bpy.ops.mesh.select_non_manifold(
                    extend=False, use_wire=False, use_boundary=True,
                    use_multi_face=False, use_non_contiguous=False,
                    use_verts=False)
                bpy.ops.mesh.remove_doubles(
                    threshold=self.merge_thres, use_unselected=False)
                bpy.ops.object.mode_set(mode = 'OBJECT')
            new_ob = store_parameters(self, new_ob)
            self.object_name = new_ob.name
            self.working_on = self.object_name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='OBJECT')

        # MATERIALS
        try:
            # create materials list
            polygon_materials = [p.material_index for p in ob1.data.polygons]*int(
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

        return {'FINISHED'}

    def check(self, context):
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class update_tessellate(bpy.types.Operator):
#class adaptive_duplifaces(bpy.types.Panel):
    bl_idname = "object.update_tessellate"
    bl_label = "Refresh"
    bl_description = ("Fast update the tessellated mesh according to base and "
                      "component changes")
    bl_options = {'REGISTER', 'UNDO'}
    go = False
    ob = bpy.types.Object

    @classmethod
    def poll(cls, context):
        try:
            return context.active_object.tissue_tessellate.generator != "" and \
                context.active_object.tissue_tessellate.component != ""
        except: return False

    def execute(self, context):
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

        if(generator == "" or component == ""):
            self.report({'ERROR'},
                        "Active object must be Tessellate before Update")
            return {'CANCELLED'}

        ob0 = bpy.data.objects[generator]
        ob1 = bpy.data.objects[component]
        me0 = ob0.data
        verts = me0.vertices

        temp_ob = tassellate(
            ob0, ob1, offset, zscale, gen_modifiers, com_modifiers,
            mode, scale_mode, rotation_mode, random_seed, fill_mode,
            bool_vertex_group, bool_selection, bool_shapekeys)

        if temp_ob == 0:
            message = "Zero faces selected in the Base mesh!"
            self.report({'ERROR'}, message)
            return {'CANCELLED'}

        ob.data = temp_ob.data
        bpy.data.objects.remove(temp_ob)
        if merge:
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.mesh.select_mode(
                use_extend=False, use_expand=False, type='VERT')
            bpy.ops.mesh.select_non_manifold(
                extend=False, use_wire=False, use_boundary=True,
                use_multi_face=False, use_non_contiguous=False, use_verts=False)
            bpy.ops.mesh.remove_doubles(
                threshold=merge_thres, use_unselected=False)
            bpy.ops.object.mode_set(mode = 'OBJECT')
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='OBJECT')

        # MATERIALS
        try:
            # create materials list
            polygon_materials = [p.material_index for p in ob1.data.polygons]*int(
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

        return {'FINISHED'}

    def check(self, context):
        return True


class settings_tessellate(bpy.types.Operator):
#class adaptive_duplifaces(bpy.types.Panel):
    bl_idname = "object.settings_tessellate"
    bl_label = "Settings"
    bl_description = ("Update the tessellated mesh according to base and "
        "component changes. Allow also to change tessellation's parameters")
    bl_options = {'REGISTER', 'UNDO'}

    object_name = bpy.props.StringProperty(
        name="", description="Name of the generated object")
    zscale = bpy.props.FloatProperty(
        name="Scale", default=1, soft_min=0, soft_max=10,
        description="Scale factor for the component thickness")
    scale_mode = bpy.props.EnumProperty(
        items=(('CONSTANT', "Constant", ""), ('ADAPTIVE', "Proportional", "")),
        default='ADAPTIVE', name="Scale variation")
    offset = bpy.props.FloatProperty(
        name="Surface Offset", default=0, min=-1, max=1,  soft_min=-1,
        soft_max=1, description="Surface offset")
    mode = bpy.props.EnumProperty(
        items=(('CONSTANT', "Constant", ""), ('ADAPTIVE', "Adaptive", "")),
        default='ADAPTIVE', name="Component Mode")
    rotation_mode = bpy.props.EnumProperty(
        items=(('RANDOM', "Random", ""), ('UV', "Active UV", ""),
        ('DEFAULT', "Default", "")), default='DEFAULT',
        name="Component Rotation")
    fill_mode = bpy.props.EnumProperty(
        items=(('QUAD', "Quad", ""), ('FAN', "Fan", "")), default='QUAD',
        name="Fill Mode")
    gen_modifiers = bpy.props.BoolProperty(
        name="Generator Modifiers", default=False,
        description="Apply modifiers to base object")
    com_modifiers = bpy.props.BoolProperty(
        name="Component Modifiers", default=False,
        description="Apply modifiers to component object")
    merge = bpy.props.BoolProperty(
        name="Merge", default=False,
        description="Merge vertices in adjacent duplicates")
    merge_thres = bpy.props.FloatProperty(
        name="Distance", default=0.001, soft_min=0, soft_max=10,
        description="Limit below which to merge vertices")
    generator = bpy.props.StringProperty(
        name="", description="Base object for the tessellation")
    component = bpy.props.StringProperty(
        name="", description="Component object for the tessellation")
    bool_random = bpy.props.BoolProperty(
        name="Randomize", default=False,
        description="Randomize component rotation")
    random_seed = bpy.props.IntProperty(
        name="Seed", default=0, soft_min=0, soft_max=10,
        description="Random seed")
    bool_vertex_group = bpy.props.BoolProperty(
        name="Map Vertex Group", default=False, description=("Map on generated "
        "geometry the active Vertex Group from the base object"))
    bool_selection = bpy.props.BoolProperty(
        name="On selected Faces", default=False,
        description="Create Tessellation only on select faces")
    bool_shapekeys = bpy.props.BoolProperty(
        name="Use Shape Keys", default=False, description=("Use component's "
        "active Shape Key according to active Vertex Group of the base object"))
    go = False
    ob = bpy.types.Object

    @classmethod
    def poll(cls, context):
        try:
            return context.active_object.tissue_tessellate.generator != "" and \
                context.active_object.tissue_tessellate.component != ""
        except: return False

    def draw(self, context):
        layout = self.layout
        ob0 = bpy.context.active_object

        if not self.go:
            self.generator = ob0.tissue_tessellate.generator
            self.component = ob0.tissue_tessellate.component
            self.zscale = ob0.tissue_tessellate.zscale
            self.scale_mode = ob0.tissue_tessellate.scale_mode
            self.rotation_mode = ob0.tissue_tessellate.rotation_mode
            self.offset = ob0.tissue_tessellate.offset
            self.merge = ob0.tissue_tessellate.merge
            self.merge_thres = ob0.tissue_tessellate.merge_thres
            self.gen_modifiers = ob0.tissue_tessellate.gen_modifiers
            self.com_modifiers = ob0.tissue_tessellate.com_modifiers
            self.bool_random = ob0.tissue_tessellate.bool_random
            self.random_seed = ob0.tissue_tessellate.random_seed
            self.fill_mode = ob0.tissue_tessellate.fill_mode
            self.bool_vertex_group = ob0.tissue_tessellate.bool_vertex_group
            self.bool_selection = ob0.tissue_tessellate.bool_selection
            self.bool_shapekeys = ob0.tissue_tessellate.bool_shapekeys
            self.mode = ob0.tissue_tessellate.mode

        # start drawing
        layout = self.layout
        #ob0 = bpy.context.active_object
        # Base and Component
        col = layout.column(align=True)
        row = col.row(align=True)
        row.label(text="BASE :")
        row.label(text="COMPONENT :")
        row = col.row(align=True)

        col2 = row.column(align=True)
        col2.prop_search(self, "generator", bpy.data, "objects")
        row.separator()
        col2 = row.column(align=True)
        col2.prop_search(self, "component", bpy.data, "objects")

        row = col.row(align=True)
        col2 = row.column(align=True)
        col2.prop(self, "gen_modifiers", text="Use Modifiers")
        if len(bpy.data.objects[self.generator].modifiers) == 0:
            col2.enabled = False
            self.gen_modifiers = False
        col2 = row.column(align=True)
        col2.prop(self, "com_modifiers", text="Use Modifiers")
        if len(bpy.data.objects[self.component].modifiers) == 0:
            col2.enabled = False
            self.com_modifiers = False

        # On selected faces
        row = col.row(align=True)
        row.prop(self, "bool_selection", text="On selected Faces")
        col.separator()

        # Count number of faces
        try:
            polygons = 0
            if self.gen_modifiers:
                me_temp = bpy.data.objects[self.generator].to_mesh(
                    bpy.context.scene, apply_modifiers=True,
                    settings = 'PREVIEW')
            else: me_temp = bpy.data.objects[self.generator].data
            for p in me_temp.polygons:
                if not self.bool_selection or p.select:
                    if self.fill_mode == "FAN": polygons += len(p.vertices)
                    else: polygons += 1

            if self.com_modifiers:
                me_temp = bpy.data.objects[self.component].to_mesh(
                    bpy.context.scene, apply_modifiers=True,
                    settings = 'PREVIEW')
            else: me_temp = bpy.data.objects[self.component].data
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
        row.separator()
        row.label(text="Rotation:")
        row = col.row(align=True)

        # fill
        row.prop(self, "fill_mode", text="", icon='NONE', expand=False,
                 slider=True, toggle=False, icon_only=False, event=False,
                 full_event=False, emboss=True, index=-1)
        row.separator()

        # rotation
        row.prop(self, "rotation_mode", text="", icon='NONE', expand=False,
                 slider=True, toggle=False, icon_only=False, event=False,
                 full_event=False, emboss=True, index=-1)
        if self.rotation_mode == 'RANDOM':
            row = col.row(align=True)
            row.prop(self, "random_seed")
        if self.rotation_mode == 'UV':
            uv_error = False
            if self.fill_mode == 'FAN':
                row = col.row(align=True)
                row.label(text="UV rotation doesn't work in FAN mode",
                          icon='ERROR')
                uv_error = True
            if len(bpy.data.objects[self.generator].data.uv_layers) == 0:
                row = col.row(align=True)
                row.label(text="'" + bpy.data.objects[self.generator].name + \
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
        row.prop(self, "mode", text="Component XY", icon='NONE', expand=True,
                 slider=False, toggle=False, icon_only=False, event=False,
                 full_event=False, emboss=True, index=-1)

        # component Z
        col.label(text="Component Z:")
        row = col.row(align=True)
        row.prop(self, "scale_mode", text="Scale Mode", icon='NONE',
                 expand=True, slider=False, toggle=False, icon_only=False,
                 event=False, full_event=False, emboss=True, index=-1)
        col.prop(self, "zscale", text="Scale", icon='NONE', expand=False,
                 slider=True, toggle=False, icon_only=False, event=False,
                 full_event=False, emboss=True, index=-1)
        col.prop(self, "offset", text="Offset", icon='NONE', expand=False,
                 slider=True, toggle=False, icon_only=False, event=False,
                 full_event=False, emboss=True, index=-1)

        # merge
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(self, "merge")
        if self.merge: row.prop(self, "merge_thres")
        row = col.row(align=True)

        ### ADVANCED ###
        col = layout.column(align=True)
        tessellate.rotation_mode

        col.label(text="Advanced Settings:")
        # vertex group + shape keys
        row = col.row(align=True)
        col2 = row.column(align=True)
        col2.prop(self, "bool_vertex_group")
        if len(bpy.data.objects[self.generator].vertex_groups) == 0:
            col2.enabled = False
            bool_vertex_group = False
        col2 = row.column(align=True)
        col2.prop(self, "bool_shapekeys", text="Use Shape Keys")
        if len(bpy.data.objects[self.generator].vertex_groups) == 0 or \
                bpy.data.objects[self.component].data.shape_keys == None:
            col2.enabled = False
            bool_shapekeys = False
        elif len(bpy.data.objects[self.generator].vertex_groups) == 0 or \
                bpy.data.objects[self.component].data.shape_keys != None:
            if len(bpy.data.objects[self.component].data.shape_keys.key_blocks) < 2:
                col2.enabled = False
                bool_shapekeys = False
        self.go = True

    def execute(self, context):
        self.ob = bpy.context.active_object
        old_material = None
        if(len(self.ob.material_slots) > 0):
            old_material = self.ob.material_slots[0].material
        if not self.go:
            self.generator = self.ob.tissue_tessellate.generator
            self.component = self.ob.tissue_tessellate.component
            self.zscale = self.ob.tissue_tessellate.zscale
            self.scale_mode = self.ob.tissue_tessellate.scale_mode
            self.rotation_mode = self.ob.tissue_tessellate.rotation_mode
            self.offset = self.ob.tissue_tessellate.offset
            self.merge = self.ob.tissue_tessellate.merge
            self.merge_thres = self.ob.tissue_tessellate.merge_thres
            self.gen_modifiers = self.ob.tissue_tessellate.gen_modifiers
            self.com_modifiers = self.ob.tissue_tessellate.com_modifiers
            self.bool_random = self.ob.tissue_tessellate.bool_random
            self.random_seed = self.ob.tissue_tessellate.random_seed
            self.fill_mode = self.ob.tissue_tessellate.fill_mode
            self.bool_vertex_group = self.ob.tissue_tessellate.bool_vertex_group
            self.bool_selection = self.ob.tissue_tessellate.bool_selection
            self.bool_shapekeys = self.ob.tissue_tessellate.bool_shapekeys

        if(self.generator == "" or self.component == ""):
            self.report({'ERROR'},
                        "Active object must be Tessellate before Update")
            return {'CANCELLED'}
        if(bpy.data.objects[self.generator].type != 'MESH'):
            self.report({'ERROR'}, "Base object must be a Mesh")
            return {'CANCELLED'}
        if(bpy.data.objects[self.component].type != 'MESH'):
            self.report({'ERROR'}, "Component object must be a Mesh")
            return {'CANCELLED'}

        ob0 = bpy.data.objects[self.generator]
        ob1 = bpy.data.objects[self.component]
        me0 = ob0.data
        verts = me0.vertices

        temp_ob = tassellate(
            ob0, ob1, self.offset, self.zscale, self.gen_modifiers,
            self.com_modifiers, self.mode, self.scale_mode, self.rotation_mode,
            self.random_seed, self.fill_mode, self.bool_vertex_group,
            self.bool_selection, self.bool_shapekeys)

        if temp_ob == 0:
            message = "Zero faces selected in the Base mesh!"
            self.report({'ERROR'}, message)
            return {'CANCELLED'}

        # Transfer mesh data
        self.ob.data = temp_ob.data

        # Create object in order to transfer vertex group
        scene = bpy.context.scene
        scene.objects.link(temp_ob)
        temp_ob.select = True
        bpy.context.scene.objects.active = temp_ob
        try:
            bpy.ops.object.vertex_group_copy_to_linked()
        except:
            pass
        scene.objects.unlink(temp_ob)
        bpy.data.objects.remove(temp_ob)
        bpy.context.scene.objects.active = self.ob

        if self.merge:
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.mesh.select_mode(
                use_extend=False, use_expand=False, type='VERT')
            bpy.ops.mesh.select_non_manifold(
                extend=False, use_wire=False, use_boundary=True,
                use_multi_face=False, use_non_contiguous=False, use_verts=False)
            bpy.ops.mesh.remove_doubles(
                threshold=self.merge_thres, use_unselected=False)
            bpy.ops.object.mode_set(mode = 'OBJECT')
        self.ob = store_parameters(self, self.ob)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='OBJECT')

        # MATERIALS
        try:
            # create materials list
            polygon_materials = [p.material_index for p in ob1.data.polygons] * \
                int(len(self.ob.data.polygons) / len(ob1.data.polygons))
            # assign old material
            component_materials = [slot.material for slot in ob1.material_slots]
            for i in range(len(component_materials)):
                bpy.ops.object.material_slot_add()
                bpy.context.object.material_slots[i].material = \
                    component_materials[i]
            for i in range(len(self.ob.data.polygons)):
                self.ob.data.polygons[i].material_index = polygon_materials[i]
        except:
            pass

        return {'FINISHED'}

    def check(self, context):
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class tessellate_panel(bpy.types.Panel):
    bl_label = "Tissue"
    bl_category = "Create"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_options = {'DEFAULT_CLOSED'}
    #bl_context = "objectmode"

    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Tessellate Add:")
        col.operator("object.tessellate")#, icon="STRANDS")
        #col.enable = False
        #col.operator("object.adaptive_duplifaces", icon="MESH_CUBE")
        col = layout.column(align=True)
        col.label(text="Tessellate Edit:")
        col.operator("object.settings_tessellate")
        col.operator("object.update_tessellate")
        col = layout.column(align=True)
        col.operator("mesh.rotate_face")
        act = context.active_object
        sel = act #context.selected_objects[0]

        for ob1 in context.selected_objects:
            if(ob1.name == act.name or ob1.type != 'MESH'): continue
            sel = ob1

        col.separator()
        col.label(text="Other:")
        col.operator("object.lattice_along_surface", icon="OUTLINER_OB_LATTICE")

        #col.separator()
        #col.label(text="Add Modifier:")
        try:
            if bpy.context.object.type == 'MESH':
                col.operator("object.uv_to_mesh", icon="GROUP_UVS")
        except:
            pass



class rotate_face(bpy.types.Operator):
    bl_idname = "mesh.rotate_face"
    bl_label = "Rotate Faces"
    bl_description = "Rotate selected faces and update tessellated meshes."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        ob = bpy.context.active_object
        me = ob.data
        bpy.ops.object.mode_set(mode='OBJECT')

        for p in [f for f in me.polygons if f.select]:
            p.vertices = p.vertices[1:] + p.vertices[:1]

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.flip_normals()
        bpy.ops.mesh.flip_normals()
        #me.vertices[0].co[0] = 10
        me.update(calc_edges=True)

        #update tessellated meshes
        bpy.ops.object.mode_set(mode='OBJECT')
        for o in [object for object in bpy.data.objects if \
                object.tissue_tessellate.generator == ob.name]:
            bpy.context.scene.objects.active = o
            bpy.ops.object.update_tessellate()
        bpy.context.scene.objects.active = ob
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


def register():
    bpy.utils.register_class(tissue_tessellate_prop)
    bpy.utils.register_class(tessellate)
    bpy.utils.register_class(update_tessellate)
    bpy.utils.register_class(settings_tessellate)
    bpy.utils.register_class(tessellate_panel)
    bpy.utils.register_class(rotate_face)


def unregister():
    bpy.utils.unregister_class(tissue_tessellate_prop)
    bpy.utils.unregister_class(tessellate)
    bpy.utils.unregister_class(update_tessellate)
    bpy.utils.unregister_class(settings_tessellate)
    bpy.utils.unregister_class(tessellate_panel)
    bpy.utils.unregister_class(rotate_face)


if __name__ == "__main__":
    register()
