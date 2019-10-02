import bpy, os
import numpy as np
import mathutils
from mathutils import Vector
from math import pi
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
from .utils import *

def change_speed_mode(self, context):
    props = context.scene.tissue_gcode
    if props.previous_speed_mode != props.speed_mode:
        if props.speed_mode == 'SPEED':
            props.speed = props.feed/60
            props.speed_vertical = props.feed_vertical/60
            props.speed_horizontal = props.feed_horizontal/60
        else:
            props.feed = props.speed*60
            props.feed_vertical = props.speed_vertical*60
            props.feed_horizontal = props.speed_horizontal*60
    props.previous_speed_mode == props.speed_mode
    return

class tissue_gcode_prop(PropertyGroup):
    last_e : FloatProperty(name="Pull", default=5.0, min=0, soft_max=10)
    path_length : FloatProperty(name="Pull", default=5.0, min=0, soft_max=10)

    folder : StringProperty(
        name="File", default="", subtype='FILE_PATH',
        description = 'Destination folder.\nIf missing, the file folder will be used'
        )
    pull : FloatProperty(
        name="Pull", default=5.0, min=0, soft_max=10,
        description='Pull material before lift'
        )
    push : FloatProperty(
        name="Push", default=5.0, min=0, soft_max=10,
        description='Push material before start extruding'
        )
    dz : FloatProperty(
        name="dz", default=2.0, min=0, soft_max=20,
        description='Z movement for lifting the nozzle before travel'
        )
    flow_mult : FloatProperty(
        name="Flow Mult", default=1.0, min=0, soft_max=3,
        description = 'Flow multiplier.\nUse a single value or a list of values for changing it during the printing path'
        )
    feed : IntProperty(
        name="Feed Rate (F)", default=3600, min=0, soft_max=20000,
        description='Printing speed'
        )
    feed_horizontal : IntProperty(
        name="Feed Horizontal", default=7200, min=0, soft_max=20000,
        description='Travel speed'
        )
    feed_vertical : IntProperty(
        name="Feed Vertical", default=3600, min=0, soft_max=20000,
        description='Lift movements speed'
        )

    speed : IntProperty(
        name="Speed", default=60, min=0, soft_max=100,
        description='Printing speed'
        )
    speed_horizontal : IntProperty(
        name="Travel", default=120, min=0, soft_max=200,
        description='Travel speed'
        )
    speed_vertical : IntProperty(
        name="Z-Lift", default=60, min=0, soft_max=200,
        description='Lift movements speed'
        )

    esteps : FloatProperty(
        name="E Steps/Unit", default=5, min=0, soft_max=100)
    start_code : StringProperty(
        name="Start", default='', description = 'Text block for starting code'
        )
    end_code : StringProperty(
        name="End", default='', description = 'Text block for ending code'
        )
    auto_sort_layers : BoolProperty(
        name="Auto Sort Layers", default=True,
        description = 'Sort layers according to the Z of the median point'
        )
    auto_sort_points : BoolProperty(
        name="Auto Sort Points", default=False,
        description = 'Shift layer points trying to automatically reduce needed travel movements'
        )
    close_all : BoolProperty(
        name="Close Shapes", default=False,
        description = 'Repeat the starting point at the end of the vertices list for each layer'
        )
    nozzle : FloatProperty(
        name="Nozzle", default=0.4, min=0, soft_max=10,
        description='Nozzle diameter'
        )
    layer_height : FloatProperty(
        name="Layer Height", default=0.1, min=0, soft_max=10,
        description = 'Average layer height, needed for a correct extrusion'
        )
    filament : FloatProperty(
        name="Filament (\u03A6)", default=1.75, min=0, soft_max=120,
        description='Filament (or material container) diameter'
        )

    gcode_mode : EnumProperty(items=[
            ("CONT", "Continuous", ""),
            ("RETR", "Retraction", "")
        ], default='CONT', name="Mode",
        description = 'If retraction is used, then each separated list of vertices\nwill be considered as a different layer'
        )
    speed_mode : EnumProperty(items=[
            ("SPEED", "Speed (mm/s)", ""),
            ("FEED", "Feed (mm/min)", "")
        ], default='SPEED', name="Speed Mode",
        description = 'Speed control mode',
        update = change_speed_mode
        )
    previous_speed_mode : StringProperty(
        name="previous_speed_mode", default='', description = ''
        )
    retraction_mode : EnumProperty(items=[
            ("FIRMWARE", "Firmware", ""),
            ("GCODE", "Gcode", "")
        ], default='GCODE', name="Retraction Mode",
        description = 'If firmware retraction is used, then the retraction parameters will be controlled by the printer'
        )
    animate : BoolProperty(
        name="Animate", default=False,
        description = 'Show print progression according to current frame'
        )


class TISSUE_PT_gcode_exporter(Panel):
    bl_category = "Tissue Gcode"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    #bl_space_type = 'PROPERTIES'
    #bl_region_type = 'WINDOW'
    #bl_context = "data"
    bl_label = "Tissue Gcode Export"
    #bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        try: return context.object.type in ('CURVE','MESH')
        except: return False

    def draw(self, context):
        props = context.scene.tissue_gcode

        #addon = context.user_preferences.addons.get(sverchok.__name__)
        #over_sized_buttons = addon.preferences.over_sized_buttons
        layout = self.layout
        col = layout.column(align=True)
        row = col.row()
        row.prop(props, 'folder', toggle=True, text='')
        col = layout.column(align=True)
        row = col.row()
        row.prop(props, 'gcode_mode', expand=True, toggle=True)
        #col = layout.column(align=True)
        col = layout.column(align=True)
        col.label(text="Extrusion:", icon='MOD_FLUIDSIM')
        #col.prop(self, 'esteps')
        col.prop(props, 'filament')
        col.prop(props, 'nozzle')
        col.prop(props, 'layer_height')
        col.separator()
        col.label(text="Speed (Feed Rate F):", icon='DRIVER')
        col.prop(props, 'speed_mode', text='')
        speed_prefix = 'feed' if props.speed_mode == 'FEED' else 'speed'
        col.prop(props, speed_prefix, text='Print')
        if props.gcode_mode == 'RETR':
            col.prop(props, speed_prefix + '_vertical', text='Z Lift')
            col.prop(props, speed_prefix + '_horizontal', text='Travel')
        col.separator()
        if props.gcode_mode == 'RETR':
            col = layout.column(align=True)
            col.label(text="Retraction Mode:", icon='NOCURVE')
            row = col.row()
            row.prop(props, 'retraction_mode', expand=True, toggle=True)
            if props.retraction_mode == 'GCODE':
                col.separator()
                col.label(text="Retraction:", icon='PREFERENCES')
                col.prop(props, 'pull', text='Retraction')
                col.prop(props, 'dz', text='Z Hop')
                col.prop(props, 'push', text='Preload')
                col.separator()
            #col.label(text="Layers options:", icon='ALIGN_JUSTIFY')
        col.separator()
        col.prop(props, 'auto_sort_layers', text="Sort Layers (Z)")
        col.prop(props, 'auto_sort_points', text="Sort Points (XY)")
        #col.prop(props, 'close_all')
        col.separator()
        col.label(text='Custom Code:', icon='TEXT')
        col.prop_search(props, 'start_code', bpy.data, 'texts')
        col.prop_search(props, 'end_code', bpy.data, 'texts')
        col.separator()
        row = col.row(align=True)
        row.scale_y = 2.0
        row.operator('scene.tissue_gcode_export')
        #col.separator()
        #col.prop(props, 'animate', icon='TIME')


class tissue_gcode_export(Operator):
    bl_idname = "scene.tissue_gcode_export"
    bl_label = "Export Gcode"
    bl_description = ("Export selected curve object as Gcode file")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            return context.object.type in ('CURVE', 'MESH')
        except:
            return False

    def execute(self, context):
        scene = context.scene
        props = scene.tissue_gcode
        # manage data
        if props.speed_mode == 'SPEED':
            props.feed = props.speed*60
            props.feed_vertical = props.speed_vertical*60
            props.feed_horizontal = props.speed_horizontal*60
        feed = props.feed
        feed_v = props.feed_vertical
        feed_h = props.feed_horizontal
        layer = props.layer_height
        flow_mult = props.flow_mult
        #if context.object.type != 'CURVE':
        #    self.report({'ERROR'}, 'Please select a Curve object')
        #    return {'CANCELLED'}
        ob = context.object
        matr = ob.matrix_world
        if ob.type == 'MESH':
            dg = context.evaluated_depsgraph_get()
            mesh = ob.evaluated_get(dg).data
            edges = [list(e.vertices) for e in mesh.edges]
            verts = [v.co for v in mesh.vertices]
            ordered_verts = find_curves(edges, len(mesh.vertices))
            ob = curve_from_pydata(verts, ordered_verts, name='__temp_curve__', merge_distance=0.1, set_active=False)

        vertices = [[matr @ p.co.xyz for p in s.points] for s in ob.data.splines]
        cyclic_u = [s.use_cyclic_u for s in ob.data.splines]

        if ob.name == '__temp_curve__': bpy.data.objects.remove(ob)

        if len(vertices) == 1: props.gcode_mode = 'CONT'
        export = True

        # open file
        if(export):
            if props.folder == '':
                folder = '//' + os.path.splitext(bpy.path.basename(bpy.context.blend_data.filepath))[0]
            else:
                folder = props.folder
            if '.gcode' not in folder: folder += '.gcode'
            path = bpy.path.abspath(folder)
            file = open(path, 'w')
            try:
                for line in bpy.data.texts[props.start_code].lines:
                    file.write(line.body + '\n')
            except:
                pass

        #if props.gcode_mode == 'RETR':

        # sort layers (Z)
        if props.auto_sort_layers:
            sorted_verts = []
            for curve in vertices:
                # mean z
                listz = [v[2] for v in curve]
                meanz = np.mean(listz)
                # store curve and meanz
                sorted_verts.append((curve, meanz))
            vertices = [data[0] for data in sorted(sorted_verts, key=lambda height: height[1])]

        # sort vertices (XY)
        if props.auto_sort_points:
            # curves median point
            median_points = [np.mean(verts,axis=0) for verts in vertices]

            # chose starting point for each curve
            for j, curve in enumerate(vertices):
                # for closed curves finds the best starting point
                if cyclic_u[j]:
                    # create kd tree
                    kd = mathutils.kdtree.KDTree(len(curve))
                    for i, v in enumerate(curve):
                        kd.insert(v, i)
                    kd.balance()

                    if props.gcode_mode == 'RETR':
                        if j==0:
                            # close to next two curves median point
                            co_find = np.mean(median_points[j+1:j+3],axis=0)
                        elif j < len(vertices)-1:
                            co_find = np.mean([median_points[j-1],median_points[j+1]],axis=0)
                        else:
                            co_find = np.mean(median_points[j-2:j],axis=0)
                        #flow_mult[j] = flow_mult[j][index:]+flow_mult[j][:index]
                        #layer[j] = layer[j][index:]+layer[j][:index]
                    else:
                        if j==0:
                            # close to next two curves median point
                            co_find = np.mean(median_points[j+1:j+3],axis=0)
                        else:
                            co_find = vertices[j-1][-1]
                    co, index, dist = kd.find(co_find)
                    vertices[j] = vertices[j][index:]+vertices[j][:index+1]
                else:
                    if j > 0:
                        p0 = curve[0]
                        p1 = curve[-1]
                        last = vertices[j-1][-1]
                        d0 = (last-p0).length
                        d1 = (last-p1).length
                        if d1 < d0: vertices[j].reverse()



            '''
            #  close shapes
            if props.close_all:
                for i in range(len(vertices)):
                    vertices[i].append(vertices[i][0])
                    #flow_mult[i].append(flow_mult[i][0])
                    #layer[i].append(layer[i][0])
            '''
        # calc bounding box
        min_corner = np.min(vertices[0],axis=0)
        max_corner = np.max(vertices[0],axis=0)
        for i in range(1,len(vertices)):
            eval_points = vertices[i] + [min_corner]
            min_corner = np.min(eval_points,axis=0)
            eval_points = vertices[i] + [max_corner]
            max_corner = np.max(eval_points,axis=0)

        # initialize variables
        e = 0
        last_vert = Vector((0,0,0))
        maxz = 0
        path_length = 0
        travel_length = 0

        printed_verts = []
        printed_edges = []
        travel_verts = []
        travel_edges = []

        # write movements
        for i in range(len(vertices)):
            curve = vertices[i]
            first_id = len(printed_verts)
            for j in range(len(curve)):
                v = curve[j]
                v_flow_mult = flow_mult#[i][j]
                v_layer = layer#[i][j]

                # record max z
                maxz = np.max((maxz,v[2]))
                #maxz = max(maxz,v[2])

                # first point of the gcode
                if i == j == 0:
                    printed_verts.append(v)
                    if(export):
                        file.write('G92 E0 \n')
                        params = v[:3] + (feed,)
                        to_write = 'G1 X{0:.4f} Y{1:.4f} Z{2:.4f} F{3:.0f}\n'.format(*params)
                        file.write(to_write)
                else:
                    # start after retraction
                    if j == 0 and props.gcode_mode == 'RETR':
                        if(export):
                            params = v[:2] + (maxz+props.dz,) + (feed_h,)
                            to_write = 'G1 X{0:.4f} Y{1:.4f} Z{2:.4f} F{3:.0f}\n'.format(*params)
                            file.write(to_write)
                            params = v[:3] + (feed_v,)
                            to_write = 'G1 X{0:.4f} Y{1:.4f} Z{2:.4f} F{3:.0f}\n'.format(*params)
                            file.write(to_write)
                            to_write = 'G1 F{:.0f}\n'.format(feed)
                            file.write(to_write)
                            if props.retraction_mode == 'GCODE':
                                e += props.push
                                file.write( 'G1 E' + format(e, '.4f') + '\n')
                            else:
                                file.write('G11\n')
                        printed_verts.append((v[0], v[1], maxz+props.dz))
                        travel_edges.append((len(printed_verts)-1, len(printed_verts)-2))
                        travel_length += (Vector(printed_verts[-1])-Vector(printed_verts[-2])).length
                        printed_verts.append(v)
                        travel_edges.append((len(printed_verts)-1, len(printed_verts)-2))
                        travel_length += maxz+props.dz - v[2]
                    # regular extrusion
                    else:
                        printed_verts.append(v)
                        v1 = Vector(v)
                        v0 = Vector(curve[j-1])
                        dist = (v1-v0).length
                        area = v_layer * props.nozzle + pi*(v_layer/2)**2 # rectangle + circle
                        cylinder = pi*(props.filament/2)**2
                        flow = area / cylinder * (0 if j == 0 else 1)
                        e += dist * v_flow_mult * flow
                        params = v[:3] + (e,)
                        if(export):
                            to_write = 'G1 X{0:.4f} Y{1:.4f} Z{2:.4f} E{3:.4f}\n'.format(*params)
                            file.write(to_write)
                        path_length += dist
                        printed_edges.append([len(printed_verts)-1, len(printed_verts)-2])
            if props.gcode_mode == 'RETR':
                v0 = Vector(curve[-1])
                if props.close_all and False:
                    #printed_verts.append(v0)
                    printed_edges.append([len(printed_verts)-1, first_id])

                    v1 = Vector(curve[0])
                    dist = (v0-v1).length
                    area = v_layer * props.nozzle + pi*(v_layer/2)**2 # rectangle + circle
                    cylinder = pi*(props.filament/2)**2
                    flow = area / cylinder
                    e += dist * v_flow_mult * flow
                    params = v1[:3] + (e,)
                    if(export):
                        to_write = 'G1 X{0:.4f} Y{1:.4f} Z{2:.4f} E{3:.4f}\n'.format(*params)
                        file.write(to_write)
                    path_length += dist
                    v0 = v1
                if i < len(vertices)-1:
                    if(export):
                        if props.retraction_mode == 'GCODE':
                            e -= props.pull
                            file.write('G0 E' + format(e, '.4f') + '\n')
                        else:
                            file.write('G10\n')
                        params = v0[:2] + (maxz+props.dz,) + (feed_v,)
                        to_write = 'G1 X{0:.4f} Y{1:.4f} Z{2:.4f} F{3:.0f}\n'.format(*params)
                        file.write(to_write)
                    printed_verts.append(v0.to_tuple())
                    printed_verts.append((v0.x, v0.y, maxz+props.dz))
                    travel_edges.append((len(printed_verts)-1, len(printed_verts)-2))
                    travel_length += maxz+props.dz - v0.z
        if(export):
            # end code
            try:
                for line in bpy.data.texts[props.end_code].lines:
                    file.write(line.body + '\n')
            except:
                pass
            file.close()
            print("Saved gcode to " + path)
        bb = list(min_corner) + list(max_corner)
        info = 'Bounding Box:\n'
        info += '\tmin\tX: {0:.1f}\tY: {1:.1f}\tZ: {2:.1f}\n'.format(*bb)
        info += '\tmax\tX: {3:.1f}\tY: {4:.1f}\tZ: {5:.1f}\n'.format(*bb)
        info += 'Extruded Filament: ' + format(e, '.2f') + '\n'
        info += 'Extruded Volume: ' + format(e*pi*(props.filament/2)**2, '.2f') + '\n'
        info += 'Printed Path Length: ' + format(path_length, '.2f') + '\n'
        info += 'Travel Length: ' + format(travel_length, '.2f')
        '''
        # animate
        if scene.animate:
            scene = bpy.context.scene
            try:
                param = (scene.frame_current - scene.frame_start)/(scene.frame_end - scene.frame_start)
            except:
                param = 1
            last_vert = max(int(param*len(printed_verts)),1)
            printed_verts = printed_verts[:last_vert]
            printed_edges = [e for e in printed_edges if e[0] < last_vert and e[1] < last_vert]
            travel_edges = [e for e in travel_edges if e[0] < last_vert and e[1] < last_vert]
        '''
        return {'FINISHED'}
