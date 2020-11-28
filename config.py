import bpy

evaluatedDepsgraph = None

class tissuePreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    add_bevel: bpy.props.EnumProperty(
        items=[
            ('bevel', 'Add bevel', '', '', 0),
            ('no_bevel', 'No bevel', '', '', 1)
        ],
        default='no_bevel'
    )

    def draw(self, context):

        from .utils_pip import Pip
        Pip._ensure_user_site_package()
        layout = self.layout
        import importlib
        numba_spec = importlib.util.find_spec('numba')
        found = numba_spec is not None
        if found:
            layout.label(text='Numba module installed correctly!', icon='INFO')
        else:
            layout.label(text='Numba module not installed!', icon='ERROR')
            layout.label(text='Installing Numba will make Tissue faster', icon='INFO')
            row = layout.row()
            row.operator('scene.tissue_install_numba')
            layout.label(text='Internet connection required. It may take few minutes', icon='URL')

class tissue_install_numba(bpy.types.Operator):
    bl_idname = "scene.tissue_install_numba"
    bl_label = "Install Numba"
    bl_description = ("Install Numba python module")
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            from .utils_pip import Pip
            #Pip.upgrade_pip()
            Pip.install('llvmlite')
            Pip.install('numba')
            from numba import jit, njit, guvectorize, float64, int32, prange
            bool_numba = True
            print('Tissue: Numba successfully installed!')
            self.report({'INFO'}, 'Tissue: Numba successfully installed!')
        except:
            print('Tissue: Numba not loaded correctly. Try restarting Blender')
        return {'FINISHED'}
