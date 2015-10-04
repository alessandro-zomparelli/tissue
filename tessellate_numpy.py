# --------------------- ADAPTIVE DUPLIFACES --------------------#
#-------------------------- version 0.5 ------------------------#
#                                                               #
# Creates duplicates of selected mesh to active morphing the    #
# shape according to target faces.                              #
#                                                               #
#                      Alessandro Zomparelli                    #
#                             (2015)                            #
#                                                               #
# http://www.co-de-it.com/                                      #
#                                                               #
# Creative Commons                                              #
# CC BY-SA 3.0                                                  #
# http://creativecommons.org/licenses/by-sa/3.0/                #

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

def tassellate(ob0, ob1, offset, zscale, gen_modifiers, com_modifiers, mode, scale_mode, randomize, rand_seed, fill_mode):
    random.seed(rand_seed)

    if gen_modifiers:
        me0 = ob0.to_mesh(bpy.context.scene, apply_modifiers=True, settings = 'PREVIEW')
    else: me0 = ob0.data

    if com_modifiers:
        me1 = ob1.to_mesh(bpy.context.scene, apply_modifiers=True, settings = 'PREVIEW')
    else: me1 = ob1.data

    verts0 = me0.vertices

    n_verts = len(me1.vertices)
    n_edges = len(me1.edges)
    n_faces = len(me1.polygons)

    loc = ob1.location
    dim = ob1.dimensions
    scale = ob1.scale

    new_verts = []
    new_edges = []
    new_faces = []
    new_verts_np = np.array(())

    min = Vector((0,0,0))
    max = Vector((0,0,0))

    first = True

    for v in me1.vertices:
        vert = ( ob1.matrix_world * v.co )

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

    verts1 = []

    for v in me1.vertices:
        if mode=="ADAPTIVE":
            vert = ( ob1.matrix_world * v.co ) - min
            vert[0] = vert[0] / bb[0]
            vert[1] = vert[1] / bb[1]
            vert[2] = (vert[2] + (-0.5 + offset*0.5)*bb[2])*zscale
        else:
            vert = v.co.xyz
            vert[2] *= zscale

        verts1.append(vert)

    # component vertices
    vs1 = np.array([v for v in verts1]).reshape(len(verts1),3,1)
    vx = vs1[:,0]
    vy = vs1[:,1]
    vz = vs1[:,2]

    # component polygons
    fs1 = [[i for i in p.vertices] for p in me1.polygons]
    new_faces = fs1[:]

    j = 0

    if fill_mode == 'FAN':
        fan_verts = [v.co.to_tuple() for v in me0.vertices]
        fan_polygons = []
        for p in me0.polygons:
            fan_center = Vector((0,0,0))
            for v in p.vertices:
                fan_center += me0.vertices[v].co
            fan_center /= len(p.vertices)
            last_vert = len(fan_verts)
            fan_verts.append(fan_center.to_tuple())
            for i in range(len(p.vertices)):
                fan_polygons.append((p.vertices[i], p.vertices[(i+1)%len(p.vertices)], last_vert, last_vert))
        #print(fan_verts)
        #print(fan_polygons)
        fan_me = bpy.data.meshes.new('Fan.Mesh')
        fan_me.from_pydata(tuple(fan_verts), [], tuple(fan_polygons))
        me0 = fan_me
        verts0 = me0.vertices


    for p in me0.polygons:

        #polygon vertices

        if randomize:
            shifted_vertices = []
            n_poly_verts = len(p.vertices)
            rand = random.randint(0,n_poly_verts)
            for i in range(n_poly_verts):
                shifted_vertices.append(p.vertices[(i+rand)%n_poly_verts])
            vs0 = np.array([verts0[i].co for i in shifted_vertices])
            nvs0 = np.array([verts0[i].normal for i in shifted_vertices])
        else:
            vs0 = np.array([verts0[i].co for i in p.vertices])
            nvs0 = np.array([verts0[i].normal for i in p.vertices])

        vs0 = np.array((vs0[0], vs0[1], vs0[2], vs0[-1]))
        #polygon normals

        nvs0 = np.array((nvs0[0], nvs0[1], nvs0[2], nvs0[-1]))

        v0 = vs0[0] + (vs0[1] -vs0[0])*vx
        v1 = vs0[3] + (vs0[2] -vs0[3])*vx
        v2 = v0 + (v1 - v0)*vy

        nv0 = nvs0[0] + (nvs0[1] -nvs0[0])*vx
        nv1 = nvs0[3] + (nvs0[2] -nvs0[3])*vx
        nv2 = nv0 + (nv1 - nv0)*vy

        v3 = v2 + nv2*vz*(sqrt(p.area) if scale_mode == "ADAPTIVE" else 1)

        if j == 0: new_verts_np = v3
        else:
            new_verts_np = np.concatenate((new_verts_np, v3), axis=0)
            for p in fs1: new_faces.append([i+n_verts*j for i in p])

        j+=1

    new_verts = new_verts_np.tolist()

    new_name = ob0.name + "_" + ob1.name
    new_me = bpy.data.meshes.new(new_name)
    new_me.from_pydata(new_verts, [], new_faces)
    #new_me.from_pydata(new_verts, new_edges, [])
    new_me.update()

    return new_me

def store_parameters(operator, ob):
    ob.tissue_tessellate.generator = operator.generator
    ob.tissue_tessellate.component = operator.component
    ob.tissue_tessellate.zscale = operator.zscale
    ob.tissue_tessellate.offset = operator.offset
    ob.tissue_tessellate.gen_modifiers = operator.gen_modifiers
    ob.tissue_tessellate.com_modifiers = operator.com_modifiers
    ob.tissue_tessellate.mode = operator.mode
    ob.tissue_tessellate.merge = operator.merge
    ob.tissue_tessellate.merge_thres = operator.merge_thres
    ob.tissue_tessellate.scale_mode = operator.scale_mode
    ob.tissue_tessellate.bool_random = operator.bool_random
    ob.tissue_tessellate.random_seed = operator.random_seed
    ob.tissue_tessellate.fill_mode = operator.fill_mode
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
    scale_mode = bpy.props.StringProperty()
    fill_mode = bpy.props.StringProperty()
    bool_random = bpy.props.BoolProperty()
    random_seed = bpy.props.IntProperty()
    vertexgroup = bpy.props.StringProperty()






class tessellate(bpy.types.Operator):
#class adaptive_duplifaces(bpy.types.Panel):
    bl_idname = "object.tessellate"
    bl_label = "Tessellate"
    bl_description = "Create a copy of selected object on the active object's faces, adapting the shape to the different faces."
    bl_options = {'REGISTER', 'UNDO'}

    object_name = bpy.props.StringProperty(name="", description="Name of the generated object")
    zscale = bpy.props.FloatProperty(name="Scale", default=1, soft_min=0, soft_max=10, description="Scale factor for the component thickness")
    scale_mode = bpy.props.EnumProperty(items=(('COSTANT', "Costant", ""), ('ADAPTIVE', "Proportional", "")), default='COSTANT', name="Z-Scale according to faces size")
    offset = bpy.props.FloatProperty(name="Surface Offset", default=0, min=-1, max=1,  soft_min=-1, soft_max=1, description="Surface offset")
    mode = bpy.props.EnumProperty(items=(('COSTANT', "Costant", ""), ('ADAPTIVE', "Adaptive", "")), default='ADAPTIVE', name="Component Mode")
    fill_mode = bpy.props.EnumProperty(items=(('QUAD', "Quad", ""), ('FAN', "Fan", "")), default='QUAD', name="Fill Mode")
    gen_modifiers = bpy.props.BoolProperty(name="Generator Modifiers", default=False, description="Apply modifiers to base object")
    com_modifiers = bpy.props.BoolProperty(name="Component Modifiers", default=False, description="Apply modifiers to component object")
    merge = bpy.props.BoolProperty(name="Merge", default=False, description="Merge vertices in adjacent duplicates")
    merge_thres = bpy.props.FloatProperty(name="Distance", default=0.001, soft_min=0, soft_max=10, description="Limit below which to merge vertices")
    generator = bpy.props.StringProperty(name="", description="Base object for the tessellation")
    component = bpy.props.StringProperty(name="", description="Component object for the tessellation")
    bool_random = bpy.props.BoolProperty(name="Randomize", default=False, description="Randomize component rotation")
    random_seed = bpy.props.IntProperty(name="Seed", default=0, soft_min=0, soft_max=10, description="Random seed")
    #vertex_group = layout.prop_search(act, "vertexgroup", act, "vertex_groups", text="Scale")

    working_on = ""

    @classmethod
    def poll(cls, context):
        try:
            working_on = context.active_object.name
            working = False
            if len(context.selected_objects) == 1:
               if context.active_object.tissue_tessellate.generator == working_on and working_on != "": working = True
               else: working_on = ""
            return len(context.selected_objects) == 2 or context.active_object.tissue_tessellate.generator != ""
        except: return False

    def draw(self, context):
        layout = self.layout
        ob0 = bpy.context.active_object

        col = layout.column(align=True)
        col.label(text="New Object Name:")
        col.prop(self, "object_name")#, icon='OBJECT_DATAMODE')

        layout.separator()

        layout.label(text="Generator : " + self.generator)
        box = layout.box()

        #col = box.column(align=True)
        #col.label(text="Generator:")
        #row = box.row(align=True)
        #row.prop_search(self, "generator", bpy.data, "objects")
        if len(bpy.data.objects[self.generator].modifiers) > 0: box.prop(self, "gen_modifiers", text="Modifiers")

        col = box.column(align=True)
        #col.label(text="Tessellation")
        row = col.row(align=True)
        row.label(text="Fill Mode:")
        row = col.row(align=True)
        row.prop(self, "fill_mode", text="", icon='NONE', expand=False, slider=True, toggle=False, icon_only=False, event=False, full_event=False, emboss=True, index=-1)

        col = box.column(align=True)
        row = col.row(align=True)
        row.prop(self, "merge")
        if self.merge: row.prop(self, "merge_thres")
        row = col.row(align=True)
        row.prop(self, "bool_random")
        if self.bool_random: row.prop(self, "random_seed")


        layout.label(text="Component : " + self.component)
        box = layout.box()

        col = box.column(align=True)
        #col.label(text="Component:")
        row = col.row(align=True)
        #row.prop_search(self, "component", bpy.data, "objects")
        if len(bpy.data.objects[self.component].modifiers) > 0: row.prop(self, "com_modifiers", text="Modifiers")

        row = col.row(align=True)
        row.label(text="Component XY:")
        row = col.row(align=True)
        row.prop(self, "mode", text="Component XY", icon='NONE', expand=True, slider=False, toggle=False, icon_only=False, event=False, full_event=False, emboss=True, index=-1)

        col = box.column(align=True)
        col.label(text="Component Z:")
        row = col.row(align=True)
        row.prop(self, "scale_mode", text="Scale Mode", icon='NONE', expand=True, slider=False, toggle=False, icon_only=False, event=False, full_event=False, emboss=True, index=-1)
        col.prop(self, "zscale", text="Scale", icon='NONE', expand=False, slider=True, toggle=False, icon_only=False, event=False, full_event=False, emboss=True, index=-1)
        col.prop(self, "offset", text="Offset", icon='NONE', expand=False, slider=True, toggle=False, icon_only=False, event=False, full_event=False, emboss=True, index=-1)




        """
        col = layout.column(align=True)
        col.label(text="Generator:")
        col.prop_search(self, "generator", bpy.data, "objects")
        if len(bpy.data.objects[self.generator].modifiers) > 0: col.prop(self, "gen_modifiers", text="Use Modifiers")

        col = layout.column(align=True)
        col.label(text="Component:")
        col.prop_search(self, "component", bpy.data, "objects")
        if len(bpy.data.objects[self.component].modifiers) > 0: col.prop(self, "com_modifiers", text="Use Modifiers")



        act = context.active_object
        sel = context.selected_objects[0]

        for ob1 in context.selected_objects:
            if(ob1.name == act.name or ob1.type != 'MESH'): continue
            sel = ob1

#           col.prop_search(act, "vertexgroup", act, "vertex_groups", text="Scale")
        """


    def execute(self, context):
        #for o in bpy.data.objects:
         #   if o.type == 'MESH':
                #self.mesh_objects = (o.name)


        # generator object
        try:
            ob0 = bpy.context.active_object
            self.generator = ob0.name
        except:
            self.report({'ERROR'}, "A Generator mesh object must be selected")
        #ob0 = bpy.data.objects[self.generator]

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
        if(no_component):
            self.report({'ERROR'}, "A component mesh object must be selected")
            return {'CANCELLED'}
        '''
        else:
            for o in sel:
                if(o.name == ob0.name or o.type != 'MESH' or o.name != self.component): continue
                else:
                    ob1 = o
                    no_component = False
                    break
            if(no_component):
                self.report({'ERROR'}, "A component mesh object must be selected")
                return {'CANCELLED'}
            else: ob1 = bpy.data.objects[self.component]
        '''

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

            new_me = tassellate(ob0, ob1, self.offset, self.zscale, self.gen_modifiers, self.com_modifiers, self.mode, self.scale_mode, self.bool_random, self.random_seed, self.fill_mode)

            new_ob = bpy.data.objects.new(self.object_name, new_me)
            new_ob.location = ob0.location
            new_ob.matrix_world = ob0.matrix_world

            scene = bpy.context.scene
            scene.objects.link(new_ob)
            new_ob.select = True
            bpy.context.scene.objects.active = new_ob
            if self.merge:
                bpy.ops.object.mode_set(mode = 'EDIT')
                bpy.ops.mesh.remove_doubles(threshold=self.merge_thres, use_unselected=True)
                bpy.ops.object.mode_set(mode = 'OBJECT')

            # storing parameters as object's properties
            new_ob = store_parameters(self, new_ob)

            self.object_name = new_ob.name

        return {'FINISHED'}

class update_tessellate(bpy.types.Operator):
#class adaptive_duplifaces(bpy.types.Panel):
    bl_idname = "object.update_tessellate"
    bl_label = "Update"
    bl_description = "Update the tessellated mesh according to base and component changes. Allow also to change tessellation's parameters"
    bl_options = {'REGISTER', 'UNDO'}

    object_name = bpy.props.StringProperty(name="", description="Name of the generated object")
    zscale = bpy.props.FloatProperty(name="Scale", default=1, soft_min=0, soft_max=10, description="Scale factor for the component thickness")
    scale_mode = bpy.props.EnumProperty(items=(('COSTANT', "Costant", ""), ('ADAPTIVE', "Proportional", "")), default='ADAPTIVE', name="Scale variation")
    offset = bpy.props.FloatProperty(name="Surface Offset", default=0, min=-1, max=1,  soft_min=-1, soft_max=1, description="Surface offset")
    mode = bpy.props.EnumProperty(items=(('COSTANT', "Costant", ""), ('ADAPTIVE', "Adaptive", "")), default='ADAPTIVE', name="Component Mode")
    fill_mode = bpy.props.EnumProperty(items=(('QUAD', "Quad", ""), ('FAN', "Fan", "")), default='QUAD', name="Fill Mode")
    gen_modifiers = bpy.props.BoolProperty(name="Generator Modifiers", default=False, description="Apply modifiers to base object")
    com_modifiers = bpy.props.BoolProperty(name="Component Modifiers", default=False, description="Apply modifiers to component object")
    merge = bpy.props.BoolProperty(name="Merge", default=False, description="Merge vertices in adjacent duplicates")
    merge_thres = bpy.props.FloatProperty(name="Distance", default=0.001, soft_min=0, soft_max=10, description="Limit below which to merge vertices")
    generator = bpy.props.StringProperty(name="", description="Base object for the tessellation")
    component = bpy.props.StringProperty(name="", description="Component object for the tessellation")
    #vertex_group = layout.prop_search(act, "vertexgroup", act, "vertex_groups", text="Scale")
    bool_random = bpy.props.BoolProperty(name="Randomize", default=False, description="Randomize component rotation")
    random_seed = bpy.props.IntProperty(name="Seed", default=0, soft_min=0, soft_max=10, description="Random seed")
    go = False

    ob = bpy.types.Object

    @classmethod
    def poll(cls, context):
        try:
            return context.active_object.tissue_tessellate.generator != ""
        except: return False


    def draw(self, context):
        layout = self.layout
        ob0 = bpy.context.active_object


        layout.label(text="Generator : " + self.generator)
        box = layout.box()

        #col = box.column(align=True)
        #col.label(text="Generator:")
        #row = box.row(align=True)
        box.prop_search(self, "generator", bpy.data, "objects")
        if len(bpy.data.objects[self.generator].modifiers) > 0: box.prop(self, "gen_modifiers", text="Modifiers")

        col = box.column(align=True)
        #col.label(text="Tessellation")
        row = col.row(align=True)
        row.label(text="Fill Mode:")
        row = col.row(align=True)
        row.prop(self, "fill_mode", text="", icon='NONE', expand=False, slider=True, toggle=False, icon_only=False, event=False, full_event=False, emboss=True, index=-1)

        col = box.column(align=True)
        row = col.row(align=True)
        row.prop(self, "merge")
        if self.merge: row.prop(self, "merge_thres")
        row = col.row(align=True)
        row.prop(self, "bool_random")
        if self.bool_random: row.prop(self, "random_seed")


        layout.label(text="Component : " + self.component)
        box = layout.box()

        col = box.column(align=True)
        #col.label(text="Component:")
        row = col.row(align=True)
        row.prop_search(self, "component", bpy.data, "objects")
        if len(bpy.data.objects[self.component].modifiers) > 0: row.prop(self, "com_modifiers", text="Modifiers")

        row = col.row(align=True)
        row.label(text="Component XY:")
        row = col.row(align=True)
        row.prop(self, "mode", text="Component XY", icon='NONE', expand=True, slider=False, toggle=False, icon_only=False, event=False, full_event=False, emboss=True, index=-1)

        col = box.column(align=True)
        col.label(text="Component Z:")
        row = col.row(align=True)
        row.prop(self, "scale_mode", text="Scale Mode", icon='NONE', expand=True, slider=False, toggle=False, icon_only=False, event=False, full_event=False, emboss=True, index=-1)
        col.prop(self, "zscale", text="Scale", icon='NONE', expand=False, slider=True, toggle=False, icon_only=False, event=False, full_event=False, emboss=True, index=-1)
        col.prop(self, "offset", text="Offset", icon='NONE', expand=False, slider=True, toggle=False, icon_only=False, event=False, full_event=False, emboss=True, index=-1)


        #self.ob = store_parameters(self, self.ob)
        self.go = True

    def execute(self, context):

        self.ob = bpy.context.active_object

        if not self.go:
            self.generator = self.ob.tissue_tessellate.generator
            self.component = self.ob.tissue_tessellate.component
            self.zscale = self.ob.tissue_tessellate.zscale
            self.scale_mode = self.ob.tissue_tessellate.scale_mode
            self.offset = self.ob.tissue_tessellate.offset
            self.merge = self.ob.tissue_tessellate.merge
            self.merge_thres = self.ob.tissue_tessellate.merge_thres
            self.gen_modifiers = self.ob.tissue_tessellate.gen_modifiers
            self.com_modifiers = self.ob.tissue_tessellate.com_modifiers
            self.bool_random = self.ob.tissue_tessellate.bool_random
            self.random_seed = self.ob.tissue_tessellate.random_seed
            self.fill_mode = self.ob.tissue_tessellate.fill_mode

        if(self.generator == "" or self.component == ""):
            self.report({'ERROR'}, "Active object must be Tessellate before Update")
            return {'CANCELLED'}

        ob0 = bpy.data.objects[self.generator]
        ob1 = bpy.data.objects[self.component]

        me0 = ob0.data
        verts = me0.vertices

        self.ob.data = tassellate(ob0, ob1, self.offset, self.zscale, self.gen_modifiers, self.com_modifiers, self.mode, self.scale_mode, self.bool_random, self.random_seed, self.fill_mode)
        #tassellate(ob0, ob1, ob.tissue_tessellate.offset, ob.tissue_tessellate.zscale, ob.tissue_tessellate.gen_modifiers, ob.tissue_tessellate.com_modifiers, ob.tissue_tessellate.mode, ob.tissue_tessellate.scale_mode)
        #else: ob.data = tassellate(ob0, ob1, self.offset, self.zscale, self.gen_modifiers, self.com_modifiers, self.mode, self.scale_mode)

        if self.merge:
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.mesh.remove_doubles(threshold=self.merge_thres, use_unselected=True)
            bpy.ops.object.mode_set(mode = 'OBJECT')

        self.ob = store_parameters(self, self.ob)

        return {'FINISHED'}



class tessellate_panel(bpy.types.Panel):
    bl_label = "Tessellate"
    bl_category = "Tissue"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_context = "objectmode"

    #vertexgroup = bpy.props.StringProperty(name="Vertex group")
    #vertexgroup = bpy.props.StringProperty()

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.label(text="Add:")
        col.operator("object.tessellate")#, icon="STRANDS")
        #col.enable = False
        col.operator("object.update_tessellate")
        #col.operator("object.adaptive_duplifaces", icon="MESH_CUBE")



        act = context.active_object
        sel = act #context.selected_objects[0]

        for ob1 in context.selected_objects:
            if(ob1.name == act.name or ob1.type != 'MESH'): continue
            sel = ob1
 #     col.prop_search(act, "vertexgroup", act, "vertex_groups", text="Scale")


def register():
    bpy.utils.register_class(tissue_tessellate_prop)
    bpy.utils.register_class(tessellate)
    bpy.utils.register_class(update_tessellate)
    bpy.utils.register_class(tessellate_panel)




def unregister():
    bpy.utils.unregister_class(tissue_tessellate_prop)
    bpy.utils.unregister_class(tessellate)
    bpy.utils.unregister_class(update_tessellate)
    bpy.utils.unregister_class(tessellate_panel)



if __name__ == "__main__":
    register()
