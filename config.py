# SPDX-FileCopyrightText: 2022-2023 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later

import bpy
from bpy.props import (
    IntProperty,
    BoolProperty
    )

evaluatedDepsgraph = None

class tissuePreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    print_stats : IntProperty(
        name="Print Stats",
        description="Print in the console all details about the computing time.",
        default=1,
        min=0,
        max=4
        )

    use_numba_tess : BoolProperty(
        name="Numba Tessellate",
        description="Boost the Tessellation using Numba module. It will be slower during the first execution",
        default=True
        )

    def draw(self, context):

        from .utils_pip import Pip
        Pip._ensure_user_site_package()
        layout = self.layout
        layout.prop(self, "print_stats")
        import importlib
        numba_spec = importlib.util.find_spec('numba')
        found = numba_spec is not None
        if found:
            try:
                import numba
                layout.label(text='Numba module installed correctly!', icon='INFO')
                layout.prop(self, "use_numba_tess")
            except:
                found = False
        if not found:
            layout.label(text='Numba module not installed!', icon='ERROR')
            layout.label(text='Installing Numba will make Tissue faster', icon='INFO')
            row = layout.row()
            row.operator('scene.tissue_install_numba')
            layout.label(text='Internet connection required. It may take few minutes', icon='URL')
        
        # Add links section - using Blender's standard approach
        # Note: doc_url and tracker_url from bl_info are automatically displayed
        # in the addon's info panel. These buttons provide quick access from preferences.
        layout.separator()
        layout.label(text="Links:", icon='WORLD')
        row = layout.row()
        row.scale_y = 1.5
        row.operator('wm.tissue_open_website', icon='HELP')
        row = layout.row()
        row.scale_y = 1.5
        row.operator('wm.tissue_open_issues', icon='URL')

class tissue_install_numba(bpy.types.Operator):
    bl_idname = "scene.tissue_install_numba"
    bl_label = "Install Numba"
    bl_description = ("Install Numba python module")
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Check online access permission (Blender 5+ requirement)
        if not bpy.app.online_access:
            self.report({'ERROR'}, 'Online access is disabled. Please enable it in Preferences > Extensions')
            return {'CANCELLED'}
        
        try:
            from .utils_pip import Pip
            #Pip.upgrade_pip()
            Pip.uninstall('llvmlite')
            Pip.uninstall('numba')
            Pip.install('llvmlite')
            Pip.install('numba')
            from numba import jit, njit, guvectorize, float64, int32, prange
            bool_numba = True
            print('Tissue: Numba successfully installed!')
            self.report({'INFO'}, 'Tissue: Numba successfully installed!')
        except:
            print('Tissue: Numba not loaded correctly. Try restarting Blender')
        return {'FINISHED'}

class TISSUE_OT_open_website(bpy.types.Operator):
    bl_idname = "wm.tissue_open_website"
    bl_label = "Open Documentation"
    bl_description = "Open Tissue documentation in web browser"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Check online access permission (Blender 5+ requirement)
        if not bpy.app.online_access:
            self.report({'ERROR'}, 'Online access is disabled. Please enable it in Preferences > Extensions')
            return {'CANCELLED'}
        
        # Get doc_url from bl_info - conventional approach using module's bl_info
        doc_url = None
        try:
            import sys
            module = sys.modules.get(__package__)
            if module and hasattr(module, 'bl_info'):
                doc_url = module.bl_info.get('doc_url')
        except:
            pass
        
        # If doc_url uses BLENDER_MANUAL_URL placeholder, resolve it
        if doc_url and '{BLENDER_MANUAL_URL}' in doc_url:
            try:
                if hasattr(bpy.utils, 'manual_url'):
                    manual_base = bpy.utils.manual_url()
                    doc_url = doc_url.replace('{BLENDER_MANUAL_URL}', manual_base)
                else:
                    # Fallback: try current Blender version, then 4.1
                    major = bpy.app.version[0]
                    minor = bpy.app.version[1]
                    doc_url = f"https://docs.blender.org/manual/en/{major}.{minor}/addons/mesh/tissue.html"
            except:
                doc_url = "https://docs.blender.org/manual/en/4.1/addons/mesh/tissue.html"
        elif not doc_url:
            # Try Blender manual for current version first, fallback to 4.1
            # Note: Documentation may not exist for all Blender versions
            try:
                major = bpy.app.version[0]
                minor = bpy.app.version[1]
                # Try current version first (e.g., 5.0)
                doc_url = f"https://docs.blender.org/manual/en/{major}.{minor}/addons/mesh/tissue.html"
            except:
                # Fallback to 4.1 (last known version with documentation)
                doc_url = "https://docs.blender.org/manual/en/4.1/addons/mesh/tissue.html"
        
        bpy.ops.wm.url_open(url=doc_url)
        return {'FINISHED'}

class TISSUE_OT_open_issues(bpy.types.Operator):
    bl_idname = "wm.tissue_open_issues"
    bl_label = "Report Issue"
    bl_description = "Open GitHub issues page to report bugs or request features"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Check online access permission (Blender 5+ requirement)
        if not bpy.app.online_access:
            self.report({'ERROR'}, 'Online access is disabled. Please enable it in Preferences > Extensions')
            return {'CANCELLED'}
        
        # Get tracker_url from bl_info - conventional approach using module's bl_info
        tracker_url = None
        try:
            import sys
            module = sys.modules.get(__package__)
            if module and hasattr(module, 'bl_info'):
                tracker_url = module.bl_info.get('tracker_url')
        except:
            pass
        
        # Fallback if not found in bl_info
        if not tracker_url:
            tracker_url = "https://github.com/alessandro-zomparelli/tissue/issues"
        
        bpy.ops.wm.url_open(url=tracker_url)
        return {'FINISHED'}
