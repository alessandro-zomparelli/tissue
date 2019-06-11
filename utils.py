import bpy

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
    if not ob.name: return None
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
            for m in ob.modifiers:
                print(m)
                print(m.show_viewport)
                print(m.levels)
            new_ob = ob.copy()
            for m in new_ob.modifiers:
                print(m)
                print(m.show_viewport)
                print(m.levels)
            new_ob.data = simple_to_mesh(ob) #bpy.data.meshes.new_from_object(ob_eval, preserve_all_data_layers=True, depsgraph=dg)
            #new_ob = ob.copy()
            #dg = bpy.context.evaluated_depsgraph_get()
            #ob_eval = ob.evaluated_get(dg)
            #new_ob.data = bpy.data.meshes.new_from_object(ob_eval, preserve_all_data_layers=True, depsgraph=dg)
            #new_ob.modifiers.clear()
            print(len(new_ob.data.polygons))
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
