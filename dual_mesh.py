#--------------------------- DUAL MESH -------------------------#
#-------------------------- version 0.2 ------------------------#
#                                                               #
# Convert a generic mesh to its dual. With open meshes it can   #
# get some wired effect on the borders.                         #
#                                                               #
#                      Alessandro Zomparelli                    #
#                             (2015)                            #
#                                                               #
# http://www.co-de-it.com/                                      #
#                                                               #
# Creative Commons                                              #
# CC BY-SA 3.0                                                  #
# http://creativecommons.org/licenses/by-sa/3.0/                #
     
# TO DO: 
#     - work in local mode

import bpy
import bmesh

bl_info = { 
	"name": "Dual Mesh",  
	"author": "Alessandro Zomparelli (Co-de-iT)",  
	"version": (0, 1),  
	"blender": (2, 7, 4),  
	"location": "",  
	"description": "Convert a generic mesh to its dual",  
	"warning": "",  
	"wiki_url": "",  
	"tracker_url": "",  
	"category": "Mesh"}  
      
class dual_mesh(bpy.types.Operator):  
    bl_idname = "object.dual_mesh"  
    bl_label = "Dual Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    quad_method = bpy.props.EnumProperty(items=[('BEAUTY', 'Beauty', 'Split the quads in nice triangles, slower method'),
                                        ('FIXED', 'Fixed', 'Split the quads on the 1st and 3rd vertices'),
                                        ('FIXED_ALTERNATE', 'Fixed Alternate', 'Split the quads on the 2nd and 4th vertices'),
                                        ('SHORTEST_DIAGONAL', 'Shortest Diagonal', 'Split the quads based on the distance between the vertices')],
                                        name="Quad Method", description="Method for splitting the quads into triangles", default="FIXED", options={'LIBRARY_EDITABLE'})

    polygon_method = bpy.props.EnumProperty(items=[('BEAUTY', 'Beauty', 'Arrange the new triangles evenly, slower method'),
                                        ('CLIP', 'Clip', 'Split the polygons with an ear clipping algorithm')],
                                        name="Polygon Method", description="Method for splitting the polygons into triangles", default="BEAUTY", options={'LIBRARY_EDITABLE'})
    
    preserve_borders = bpy.props.BoolProperty(name="Preserve Borders", default=True, description="Preserve original borders")
    #multiple_users = bpy.props.BoolProperty(name="Multiple Users Data", default=True, description="Affect linked objects")

    '''
    @classmethod
    def poll(cls, context):
        try:
            sel = bpy.context.selected_objects
            for ob0 in sel:
                if ob0.type == 'MESH': return True
            return False
        except: 
            return False
    '''

    def execute(self, context):
        act = bpy.context.active_object
        sel = bpy.context.selected_objects
        doneMeshes = []
        for ob0 in sel:
            if ob0.type != 'MESH': continue
            if ob0.data.name in doneMeshes: continue
            ##ob = bpy.data.objects.new("dual_mesh_wip", ob0.data.copy())
            ob = ob0
            mesh_name = ob0.data.name

            # store linked objects
            clones = []
            n_users = ob0.data.users
            count = 0
            for o in bpy.data.objects:
                if o.type != 'MESH': continue
                if o.data.name == mesh_name:
                    count+=1
                    clones.append(o)
                if count == n_users: break
            ob.data = ob.data.copy()

            ##bpy.context.scene.objects.link(ob)


            bpy.ops.object.select_all(action='DESELECT')
            ob.select = True
            bpy.context.scene.objects.active = ob0 ##bpy.data.objects['dual_mesh_wip']

            #boolModifiers = []
            #for m in ob.modifiers:
            #    boolModifiers.append(m.show_viewport)
            #    m.show_viewport = False
        
            bpy.ops.object.mode_set(mode = 'EDIT')

            if self.preserve_borders:
                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')
                bpy.ops.mesh.select_non_manifold(extend=False, use_wire=False, use_boundary=True, use_multi_face=False, use_non_contiguous=False, use_verts=False)
                bpy.ops.mesh.extrude_region_move(MESH_OT_extrude_region={"mirror":False}, TRANSFORM_OT_translate={"value":(0, 0, 0), "constraint_axis":(False, False, False), "constraint_orientation":'GLOBAL', "mirror":False, "proportional":'DISABLED', "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "snap":False, "snap_target":'CLOSEST', "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0), "gpencil_strokes":False, "texture_space":False, "remove_on_cancel":False, "release_confirm":False})
        
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT', action='TOGGLE')
            bpy.ops.mesh.select_all(action = 'SELECT')
            bpy.ops.mesh.quads_convert_to_tris(quad_method=self.quad_method, ngon_method=self.polygon_method)
            bpy.ops.mesh.select_all(action = 'DESELECT')
            bpy.ops.object.mode_set(mode = 'OBJECT')
            bpy.ops.object.modifier_add(type='SUBSURF')
            ob.modifiers[-1].name = "dual_mesh_subsurf"
            bpy.ops.object.modifier_apply(apply_as='DATA', modifier='dual_mesh_subsurf')
             
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.mesh.select_all(action = 'DESELECT')
             
            verts = ob.data.vertices
             
            bpy.ops.object.mode_set(mode = 'OBJECT')
            verts[0].select = True
            bpy.ops.object.mode_set(mode = 'EDIT')
            bpy.ops.mesh.select_more(use_face_step=False)

            bpy.ops.mesh.select_similar(type='EDGE', compare='EQUAL', threshold=0.01)
            #bpy.ops.mesh.select_similar(type='FACE', compare='EQUAL', threshold=0.01)
            bpy.ops.mesh.select_all(action='INVERT')
            bpy.ops.mesh.dissolve_verts()
            bpy.ops.mesh.select_all(action = 'DESELECT')

            bpy.ops.mesh.select_non_manifold(extend=False, use_wire=False, use_boundary=True, use_multi_face=False, use_non_contiguous=False, use_verts=False)
            bpy.ops.mesh.select_more()
        
            # find boundaries
            bpy.ops.object.mode_set(mode = 'OBJECT')
            bound_v = [v.index for v in ob.data.vertices if v.select]
            bound_e = [e.index for e in ob.data.edges if e.select]
            bound_p = [p.index for p in ob.data.polygons if p.select]
            bpy.ops.object.mode_set(mode = 'EDIT')

            # select quad faces
            bpy.context.tool_settings.mesh_select_mode = (False, False, True) # face mode
            bpy.ops.mesh.select_face_by_sides(number=4, extend=False)  
   
            # deselect boundaries
            bpy.ops.object.mode_set(mode = 'OBJECT')
            for i in bound_v:
                bpy.context.active_object.data.vertices[i].select = False
            for i in bound_e:
                bpy.context.active_object.data.edges[i].select = False
            for i in bound_p:
                bpy.context.active_object.data.polygons[i].select = False
        
            bpy.ops.object.mode_set(mode = 'EDIT')

            bpy.context.tool_settings.mesh_select_mode = (False, False, True) # face mode
            bpy.ops.mesh.edge_face_add()
            bpy.context.tool_settings.mesh_select_mode = (True, False, False) # vertices mode
            bpy.ops.mesh.select_all(action = 'DESELECT')

            # delete boundaries
            bpy.ops.mesh.select_non_manifold(extend=False, use_wire=True, use_boundary=True, use_multi_face=False, use_non_contiguous=False, use_verts=True)
            bpy.ops.mesh.delete(type='VERT')

            ### remove middle vertices

            # select middle vertices
            bm = bmesh.from_edit_mesh(ob.data)

            for v in bm.verts:
                if len(v.link_edges) == 2 and len(v.link_faces) < 3:
                    v.select_set(True)

            # dissolve
            bpy.ops.mesh.dissolve_verts()
            bpy.ops.mesh.select_all(action = 'DESELECT')

            # clean wires
            bpy.ops.mesh.select_non_manifold(extend=False, use_wire=True, use_boundary=False, use_multi_face=False, use_non_contiguous=False, use_verts=False)
            bpy.ops.mesh.delete(type='EDGE')

            bpy.ops.object.mode_set(mode = 'OBJECT')
            ##ob0.data = ob.data
            ob0.data.name = mesh_name

            doneMeshes.append(mesh_name)
            for o in clones: o.data = ob.data        

            #for i in range(len(ob.modifiers)): ob.modifiers[i].show_viewport = boolModifiers[i]
            ##bpy.ops.object.delete(use_global=False)

        for o in sel: o.select = True
        bpy.context.scene.objects.active = act    
        
        return {'FINISHED'} 
      

class dual_mesh_panel(bpy.types.Panel):
    bl_label = "Dual Mesh"
    bl_category = "Tissue"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_context = (("objectmode"))
         
    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        #col.label(text="Add:")
        if bpy.context.active_object.type == 'MESH': col.operator("object.dual_mesh")
        #col.operator("object.adaptive_duplifaces", icon="MESH_CUBE")

def register():
    bpy.utils.register_class(dual_mesh)
    bpy.utils.register_class(dual_mesh_panel)
    
def unregister():
    bpy.utils.unregister_class(dual_mesh)  
    bpy.utils.unregister_class(dual_mesh_panel)
      
if __name__ == "__main__":  
    register()  
     
