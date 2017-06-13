import bpy, bmesh
from mathutils import Vector, Matrix

bl_info = {
    "name": "Lattice",
    "author": "Alessandro Zomparelli (Co-de-iT)",
    "version": (0, 2),
    "blender": (2, 7, 8),
    "location": "",
    "description": "Generate a Lattice based on a grid mesh",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Mesh"}


def not_in(element, grid):
    output = True
    for loop in grid:
        if element in loop:
            output = False
            break
    return output

class auto_lattice(bpy.types.Operator):
    bl_idname = "object.auto_lattice"
    bl_label = "Auto-Lattice"
    bl_options = {'REGISTER', 'UNDO'}

    flipNormals = bpy.props.BoolProperty(
        name="Flip Normals", default=False,
        description="Flip normals direction")

    swapUV = bpy.props.BoolProperty(
        name="Swap UV", default=False,
        description="Flip grid's U and V")

    flipU = bpy.props.BoolProperty(
        name="Flip U", default=False,
        description="Flip grid's U")

    flipV = bpy.props.BoolProperty(
        name="Flip V", default=False,
        description="Flip grid's V")

    flipW = bpy.props.BoolProperty(
        name="Flip W", default=False,
        description="Flip grid's W")

    use_groups = bpy.props.BoolProperty(
        name="Vertex-group", default=False,
        description="Use active vertex-group for lattice's thickness")

    high_quality_lattice = bpy.props.BoolProperty(
        name="High quality", default=True,
        description="Increase the the subdivisions in normal direction for a more correct result")

    hide_lattice = bpy.props.BoolProperty(
        name="Hide Lattice", default=True,
        description="Automatically hide the Lattice object")

    scale_x = bpy.props.FloatProperty(
        name="Scale X", default=1, min=0.001,
        max=1, description="Object scale")

    scale_y = bpy.props.FloatProperty(
        name="Scale Y", default=1, min=0.001,
        max=1, description="Object scale")

    scale_z = bpy.props.FloatProperty(
        name="Scale Z", default=1, min=0.001,
        max=1, description="Object scale")

    thickness = bpy.props.FloatProperty(
        name="Thickness", default=1, soft_min=0,
        soft_max=5, description="Lattice thickness")

    displace = bpy.props.FloatProperty(
        name="Displace", default=0, soft_min=-1,
        soft_max=1, description="Lattice displace")

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "swapUV")
        col.prop(self, "flipU")
        col.prop(self, "flipV")
        col.prop(self, "flipW")
        col.prop(self, "flipNormals")
        col.prop(
            self, "scale_x", text="Scale X", icon='NONE', expand=False,
            slider=True, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        col.prop(
            self, "scale_y", text="Scale Y", icon='NONE', expand=False,
            slider=True, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        col.prop(
            self, "scale_z", text="Scale Z", icon='NONE', expand=False,
            slider=True, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        col.separator()
        row = col.row()
        row.prop(
            self, "thickness", text="Thickness", icon='NONE', expand=False,
            slider=True, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        row = col.row()
        row.prop(
            self, "displace", text="Displace", icon='NONE', expand=False,
            slider=True, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        row = col.row()
        row.prop(self, "use_groups")
        col.separator()
        row = col.row()
        row.prop(self, "high_quality_lattice")
        row = col.row()
        row.prop(self, "hide_lattice")

    def execute(self, context):
        grid_obj = bpy.context.active_object
        #old_grid_data = grid_obj.data
        #grid_matrix = Matrix(grid_obj.matrix_world)
        #bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        #grid_mesh = grid_obj.to_mesh(bpy.context.scene, apply_modifiers=True, settings = 'PREVIEW')
        #grid_obj.data = grid_mesh.transform(grid_matrix)
        #grid_obj.data.update()

        obj = None
        for o in bpy.context.selected_objects:
            if o.name != grid_obj.name:
                obj = o
                o.select = False
                break
        obj_dim = obj.dimensions
        obj_me = obj.to_mesh(bpy.context.scene, apply_modifiers=True, settings = 'PREVIEW')

        bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked":False, "mode":'TRANSLATION'}, TRANSFORM_OT_translate={"value":(0, 0, 0), "constraint_axis":(False, False, False), "constraint_orientation":'GLOBAL', "mirror":False, "proportional":'DISABLED', "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "snap":False, "snap_target":'CLOSEST', "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0), "gpencil_strokes":False, "texture_space":False, "remove_on_cancel":False, "release_confirm":False})
        grid_obj = bpy.context.active_object
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        grid_mesh = grid_obj.to_mesh(bpy.context.scene, apply_modifiers=True, settings = 'PREVIEW')



        ### CREATING LATTICE ###

        min = Vector((0,0,0))
        max = Vector((0,0,0))

        first = True

        for v in obj_me.vertices:
            vert = obj.matrix_world * v.co

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

        # adding offset
        bb = max-min
        #scale = Vector((bb[0]/self.scale_x, bb[1]/self.scale_y, bb[2]/self.scale_z))
        #if bb.z == 0: offset.z = 1

        lattice_loc = (max+min)/2

        bpy.ops.object.add(type='LATTICE', view_align=False, enter_editmode=False)
        lattice = bpy.context.active_object
        lattice.location = lattice_loc
        lattice.scale = Vector((bb.x/self.scale_x, bb.y/self.scale_y, bb.z/self.scale_z))
        if bb.z == 0: lattice.scale.z = 1

        bpy.context.scene.objects.active = obj
        bpy.ops.object.modifier_add(type='LATTICE')
        obj.modifiers[-1].object = lattice

        # set as parent
        obj.select = True
        lattice.select = True
        #grid_mesh.select = False
        bpy.context.scene.objects.active = lattice
        #bpy.ops.object.parent_set(type='LATTICE')


        #bpy.context.scene.objects.active = grid_mesh
        #grid_mesh.select = True
        #bpy.ops.object.mode_set(mode='EDIT')
        #grid_mesh = bpy.context.edit_object
        #bm = bmesh.from_edit_mesh(grid_mesh.data)
        bm = bmesh.new()
        bm.from_mesh(grid_mesh)



        verts_grid = []
        edges_grid = []
        faces_grid = []

        flip_matrix = True

        running_grid = True
        while running_grid:
            #print("while_grid")
            verts_loop = []
            edges_loop = []
            faces_loop = []

            #print(verts_grid)
            #print(edges_grid)
            #print(faces_grid)

            # storing first point
            verts_candidates = []
            if len(faces_grid) == 0: verts_candidates = bm.verts                                                        # for first loop check all vertices
            else: verts_candidates = [v for v in bm.faces[faces_grid[-1][0]].verts if not_in(v.index, verts_grid)]      # for other loops start form the vertices of the first face  the last loop, skipping already used vertices

            # check for last loop
            is_last = False
            for vert in verts_candidates:
                if len(vert.link_faces) == 1:            # check if corner vertex
                    vert.select = True
                    verts_loop.append(vert.index)
                    is_last = True
                    break
            if not is_last:
                for vert in verts_candidates:
                    new_link_faces = [f for f in vert.link_faces if not_in(f.index, faces_grid)]
                    if len(new_link_faces) < 2:            # check if corner vertex
                        vert.select = True
                        verts_loop.append(vert.index)
                        break

            running_loop = len(verts_loop) > 0

            while running_loop:
                bm.verts.ensure_lookup_table()
                #print("while_loop")

                id = verts_loop[-1]
                link_edges = bm.verts[id].link_edges

                # storing second point
                if len(verts_loop) == 1:                    # only one vertex stored in the loop
                    if len(faces_grid) == 0:                ### first loop ###
                        edge = link_edges[flip_matrix]      # chose direction
                        for vert in edge.verts:
                            if vert.index != id:
                                vert.select = True
                                verts_loop.append(vert.index)                   # new vertex
                                edges_loop.append(edge.index)                   # chosen edge
                                faces_loop.append(edge.link_faces[0].index)     # only one face
                                #edge.link_faces[0].select = True
                    else:                                   ### other loops ###
                        for edge in bm.faces[faces_grid[-1][0]].edges:          # start from the edges of the first face of the last loop
                            if bm.verts[verts_loop[0]] in edge.verts and bm.verts[verts_grid[-1][0]] not in edge.verts:       # chose an edge starting from the first vertex that is not returning back
                                for vert in edge.verts:
                                    if vert.index != id:
                                        vert.select = True
                                        verts_loop.append(vert.index)
                                edges_loop.append(edge.index)
                                for face in edge.link_faces:
                                    if not_in(face.index,faces_grid):
                                        #face.select = True
                                        faces_loop.append(face.index)

                # continuing the loop
                else:
                    for edge in link_edges:#(e for e in link_edges if not_in(e.index,edges_grid)):         # is a new edge. Three possible edges
                        for vert in edge.verts:
                            store_data = False
                            if not_in(vert.index, verts_grid) and vert.index not in verts_loop:
                                if len(faces_loop) > 0:
                                    bm.faces.ensure_lookup_table()
                                    if vert not in bm.faces[faces_loop[-1]].verts: store_data = True
                                else:
                                    store_data = True
                                if store_data:
                                    vert.select = True
                                    verts_loop.append(vert.index)
                                    edges_loop.append(edge.index)
                                    for face in edge.link_faces:
                                        if not_in(face.index, faces_grid):
                                            faces_loop.append(face.index)
                                    break

                # ending condition
                if verts_loop[-1] == id or verts_loop[-1] == verts_loop[0]: running_loop = False

            verts_grid.append(verts_loop)
            edges_grid.append(edges_loop)
            faces_grid.append(faces_loop)

            #n_verts = 0
            #for l in verts_grid:
            #    n_verts += len(l)
            if len(faces_loop) == 0: running_grid = False



        #bmesh.update_edit_mesh(grid_mesh.data, True)


        # setting lattice

        if self.swapUV: verts_grid = list(zip(*verts_grid))


        nu = len(verts_grid)
        nv = len(verts_grid[0])
        nw = 2

        scale_normal = self.thickness

        #print(nu)
        #print(nv)

        #for loop in verts_grid: print(len(loop))

        try:
            lattice.data.points_u = nu
            lattice.data.points_v = nv
            lattice.data.points_w = nw

            for i in range(nu):
                for j in range(nv):
                    for w in range(nw):
                        if self.use_groups:
                            try:
                                displace = grid_obj.vertex_groups.active.weight(verts_grid[i][j])*scale_normal*bb.z
                            except:
                                displace = scale_normal*bb.z
                        else: displace = scale_normal*bb.z
                        #target_point = (bm.verts[verts_grid[i][j]].co + bm.verts[verts_grid[i][j]].normal*w*displace)#*grid_obj.matrix_local - lattice.location + grid_obj.location
                        target_point = (bm.verts[verts_grid[i][j]].co + bm.verts[verts_grid[i][j]].normal*(w + self.displace/2 - 0.5)*displace) - lattice.location
                        if self.flipW: w = 1-w
                        if self.flipU: i = nu-i-1
                        if self.flipV: j = nv-j-1
                        lattice.data.points[i + j*nu + w*nu*nv].co_deform.x = target_point.x / bpy.data.objects[lattice.name].scale.x
                        lattice.data.points[i + j*nu + w*nu*nv].co_deform.y = target_point.y / bpy.data.objects[lattice.name].scale.y
                        lattice.data.points[i + j*nu + w*nu*nv].co_deform.z = target_point.z / bpy.data.objects[lattice.name].scale.z

        except:
            bpy.ops.object.mode_set(mode='OBJECT')
            grid_obj.select = True
            lattice.select = True
            obj.select = False
            bpy.ops.object.delete(use_global=False)
            bpy.context.scene.objects.active = obj
            obj.select = True
            bpy.ops.object.modifier_remove(modifier=obj.modifiers[-1].name)
            if nu > 64 or nv > 64: self.report({'ERROR'}, "Maximum resolution allowed for Lattice is 64")
        else: self.report({'ERROR'}, "The grid mesh is not correct")
            return {'CANCELLED'}
        #grid_obj.data = old_grid_data
        #print(old_grid_matrix)
        #grid_obj.matrix_world = old_grid_matrix

        bpy.ops.object.mode_set(mode='OBJECT')
        grid_obj.select = True
        lattice.select = False
        obj.select = False
        bpy.ops.object.delete(use_global=False)
        bpy.context.scene.objects.active = lattice
        lattice.select = True
        if self.high_quality_lattice: bpy.context.object.data.points_w = 8
        else: bpy.context.object.data.use_outside = True
        if self.hide_lattice:
            bpy.ops.object.hide_view_set(unselected=False)
        bpy.context.scene.objects.active = obj
        obj.select = True
        lattice.select = False
        if self.flipNormals:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.flip_normals()
            bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}


class auto_lattice_panel(bpy.types.Panel):
    bl_label = "Auto-Lattice"
    bl_category = "Tissue"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_context = (("objectmode"))

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        try:
            if bpy.context.active_object.type == 'MESH':
                col.operator("object.auto_lattice", icon="MOD_LATTICE")
        except:
            pass


def register():
    bpy.utils.register_class(auto_lattice)
    bpy.utils.register_class(auto_lattice_panel)


def unregister():
    bpy.utils.unregister_class(auto_lattice)
    bpy.utils.unregister_class(auto_lattice_panel)


if __name__ == "__main__":
    register()
