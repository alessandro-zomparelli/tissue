#------------------- COLORS / GROUPS EXCHANGER -----------------#
#                                                               #
# Vertex Color to Vertex Group allow you to convert colors      #
# channles to weight maps.                                      #
# The main purpose is to use vertex colors to store information #
# when importing files from other softwares.                    #
# The script works on the active vertex color slot.             #
# For use the command "Vertex Clors to Vertex Groups" use the   #
# search bar (space bar).                                       #
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
import math

bl_info = { 
	"name": "Colors/Groups Exchanger",  
	"author": "Alessandro Zomparelli (Co-de-iT)",  
	"version": (0, 1),  
	"blender": (2, 7, 4),  
	"location": "",  
	"description": "Convert vertex colors channels to vertex groups and vertex groups to colors",  
	"warning": "",  
	"wiki_url": "",  
	"tracker_url": "",  
	"category": "Mesh"}  
      
class vertex_colors_to_vertex_groups(bpy.types.Operator):  
    bl_idname = "object.vertex_colors_to_vertex_groups"  
    bl_label = "Weight from Colors"
    bl_options = {'REGISTER', 'UNDO'}
    
    red = bpy.props.BoolProperty(name="red channel", default=False, description="convert red channel")
    green = bpy.props.BoolProperty(name="green channel", default=False, description="convert green channel")
    blue = bpy.props.BoolProperty(name="blue channel", default=False, description="convert blue channel")
    value = bpy.props.BoolProperty(name="value channel", default=True, description="convert value channel")
    invert = bpy.props.BoolProperty(name="invert", default=False, description="invert all color channels")
      
    def execute(self, context):
        obj = bpy.context.active_object
        id = len(obj.vertex_groups)
        id_red = id
        id_green = id
        id_blue = id
        id_value = id
        
        boolCol = len(obj.data.vertex_colors)
        if(boolCol): col_name = obj.data.vertex_colors.active.name
        
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        
        if(self.red and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_red = id
            obj.vertex_groups[id_red].name = col_name + '_red'
            id+=1
        if(self.green and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_green = id
            obj.vertex_groups[id_green].name = col_name + '_green'
            id+=1
        if(self.blue and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_blue = id
            obj.vertex_groups[id_blue].name = col_name + '_blue'
            id+=1
        if(self.value and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_value = id
            obj.vertex_groups[id_value].name = col_name + '_value'
            id+=1
        
        mult = 1
        if(self.invert): mult = -1
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        sub_red = 1 + self.value + self.blue + self.green
        sub_green = 1 + self.value + self.blue
        sub_blue = 1 + self.value
        sub_value = 1
        
        id = len(obj.vertex_groups)
        if(id_red <= id and id_green <= id and id_blue <= id and id_value <= id and boolCol):
            v_colors = obj.data.vertex_colors.active.data
            i = 0
            for f in obj.data.polygons:
                for v in f.vertices:
                    gr = obj.data.vertices[v].groups
                    if(self.red): gr[min(len(gr)-sub_red, id_red)].weight = self.invert + mult * v_colors[i].color.r
                    if(self.green): gr[min(len(gr)-sub_green, id_green)].weight = self.invert + mult * v_colors[i].color.g
                    if(self.blue): gr[min(len(gr)-sub_blue, id_blue)].weight = self.invert + mult * v_colors[i].color.b
                    if(self.value): gr[min(len(gr)-sub_value, id_value)].weight = self.invert + mult * v_colors[i].color.v
                    #if(self.value and len(obj.data.vertices[v].groups)>id_value): obj.data.vertices[v].groups[id_value].weight = self.invert + mult * v_colors[i].color.v
                    i+=1
                    
            bpy.ops.paint.weight_paint_toggle()
        
        return {'FINISHED'}  
      
      
class vertex_group_to_vertex_colors(bpy.types.Operator):  
    bl_idname = "object.vertex_group_to_vertex_colors"  
    bl_label = "Colors from Weight"
    bl_options = {'REGISTER', 'UNDO'}
    
    channel = bpy.props.EnumProperty(items=[('Blue', 'Blue Channel', 'Convert to Blue Channel'),
                                        ('Green', 'Green Channel', 'Convert to Green Channel'),
                                        ('Red', 'Red Channel', 'Convert to Red Channel'),
                                        ('Value', 'Value Channel', 'Convert to Grayscale'),
                                        ('False Colors', 'False Colors', 'Convert to False Colors')],
                                        name="Convert to", description="Choose how to convert vertex group", default="Value", options={'LIBRARY_EDITABLE'})
    
    invert = bpy.props.BoolProperty(name="invert", default=False, description="invert color channel")
      
    def execute(self, context):
        obj = bpy.context.active_object
        
        group_id = obj.vertex_groups.active_index
        
        if (group_id == -1):
            return {'FINISHED'}
                
        bpy.ops.object.mode_set(mode='OBJECT')
        
        group_name = obj.vertex_groups[group_id].name
        bpy.ops.mesh.vertex_color_add()
        colors_id = obj.data.vertex_colors.active_index
        
        colors_name = group_name
        if(self.channel == 'False Colors'): colors_name += "_false_colors"
        elif(self.channel == 'Value'):  colors_name += "_value"
        elif(self.channel == 'Red'):  colors_name += "_red"
        elif(self.channel == 'Green'):  colors_name += "_green"
        elif(self.channel == 'Blue'):  colors_name += "_blue"
        bpy.context.object.data.vertex_colors[colors_id].name = colors_name
        
        v_colors = obj.data.vertex_colors.active.data
        
        mult = 1
        if(self.invert): mult = -1
        
        i = 0
        for f in obj.data.polygons:
            for v in f.vertices:
                gr = obj.data.vertices[v].groups
                
                if(self.channel == 'False Colors'): v_colors[i].color = (0,0,1)
                else: v_colors[i].color = (0,0,0)
                
                for g in gr:
                    if g.group == group_id:
                        if(self.channel == 'False Colors'):
                            if(g.weight < 0.25): v_colors[i].color = (0,g.weight*4,1)
                            elif(g.weight < 0.5): v_colors[i].color = (0,1,1-(g.weight-0.25)*4)
                            elif(g.weight < 0.75): v_colors[i].color = ((g.weight-0.5)*4,1,0)
                            else: v_colors[i].color = (1,1-(g.weight-0.75)*4,0)
                        elif(self.channel == 'Value'):
                            v_colors[i].color = (self.invert + mult * g.weight, self.invert + mult * g.weight, self.invert + mult * g.weight)
                        elif(self.channel == 'Red'):
                            v_colors[i].color = (self.invert + mult * g.weight,0,0)
                        elif(self.channel == 'Green'):
                            v_colors[i].color = (0, self.invert + mult * g.weight,0)
                        elif(self.channel == 'Blue'):
                            v_colors[i].color = (0,0, self.invert + mult * g.weight)
                i+=1
            
        bpy.ops.paint.vertex_paint_toggle()
        bpy.context.object.data.vertex_colors[colors_id].active_render = True

        return {'FINISHED'}  
      

class colors_groups_exchanger_panel(bpy.types.Panel):
    bl_label = "Colors-Weight Exchanger"
    bl_category = "Tissue"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    #bl_context = "objectmode"
         
    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        #col.label(text="Add:")
        col.operator("object.vertex_group_to_vertex_colors", icon="GROUP_VCOL")
        col.operator("object.vertex_colors_to_vertex_groups", icon="GROUP_VERTEX")
        #col.operator("object.adaptive_duplifaces", icon="MESH_CUBE")
      
def register():
    bpy.utils.register_class(vertex_colors_to_vertex_groups)
    bpy.utils.register_class(vertex_group_to_vertex_colors) 
    bpy.utils.register_class(colors_groups_exchanger_panel)  
      
def unregister():
    bpy.utils.unregister_class(vertex_colors_to_vertex_groups)  
    bpy.utils.unregister_class(vertex_group_to_vertex_colors)  
    bpy.utils.unregister_class(colors_groups_exchanger_panel)  
      
if __name__ == "__main__":  
    register()  
