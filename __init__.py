# --------------------------- TISSUE ---------------------------#
#-------------------------- version 0.2 ------------------------#
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



if "bpy" in locals():
    import importlib
    importlib.reload(tessellate_numpy)
    importlib.reload(colors_groups_exchanger)
    importlib.reload(dual_mesh)

else:
    from . import tessellate_numpy
    from . import colors_groups_exchanger
    from . import dual_mesh

import bpy
from mathutils import Vector
#bpy.types.Object.vertexgroup = bpy.props.StringProperty()
#bpy.types.Panel.vertexgroup = bpy.props.StringProperty()

bl_info = {
	"name": "Tissue",
	"author": "Alessandro Zomparelli (Co-de-iT)",
	"version": (0, 2),
	"blender": (2, 7, 4),
	"location": "",
	"description": "Tools for Computational Design",
	"warning": "",
	"wiki_url": "https://github.com/alessandro-zomparelli/tissue/wiki",
	"tracker_url": "https://plus.google.com/u/0/+AlessandroZomparelli/",
	"category": "Mesh"}

def register():
    bpy.utils.register_module(__name__)
    #tessellate.register()
    #bpy.types.Object.tissue_tessellate = bpy.props.PointerProperty(tessellate_numpy.tissue_tessellate_props)
    #bpy.types.Panel.vertexgroup = bpy.props.StringProperty()
    bpy.types.Object.tissue_tessellate = bpy.props.PointerProperty(type=tessellate_numpy.tissue_tessellate_prop)


def unregister():
    #bpy.utils.register_module(__name__)
    tessellate_numpy.unregister()
    colors_groups_exchanger.unregister()

if __name__ == "__main__":
    register()
