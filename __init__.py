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

# --------------------------------- TISSUE ----------------------------------- #
# ------------------------------- version 0.3 -------------------------------- #
#                                                                              #
# Creates duplicates of selected mesh to active morphing the shape according   #
# to target faces.                                                             #
#                                                                              #
#                            Alessandro Zomparelli                             #
#                                   (2017)                                     #
#                                                                              #
# http://www.co-de-it.com/                                                     #
# http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/Mesh/Tissue      #
#                                                                              #
# ############################################################################ #

bl_info = {
    "name": "Tissue",
    "author": "Alessandro Zomparelli (Co-de-iT)",
    "version": (0, 3, 25),
    "blender": (2, 80, 0),
    "location": "",
    "description": "Tools for Computational Design",
    "warning": "",
    "wiki_url": "https://github.com/alessandro-zomparelli/tissue/wiki",
    "tracker_url": "https://github.com/alessandro-zomparelli/tissue/issues",
    "category": "Mesh"}


if "bpy" in locals():
    import importlib
    importlib.reload(tessellate_numpy)
    importlib.reload(colors_groups_exchanger)
    importlib.reload(dual_mesh)
    importlib.reload(lattice)
    importlib.reload(uv_to_mesh)
    importlib.reload(utils)

else:
    from . import tessellate_numpy
    from . import colors_groups_exchanger
    from . import dual_mesh
    from . import lattice
    from . import uv_to_mesh
    from . import utils

import bpy
from bpy.props import PointerProperty, CollectionProperty, BoolProperty

classes = (
    tessellate_numpy.tissue_tessellate_prop,
    tessellate_numpy.tessellate,
    tessellate_numpy.update_tessellate,
    tessellate_numpy.TISSUE_PT_tessellate,
    tessellate_numpy.rotate_face,
    tessellate_numpy.TISSUE_PT_tessellate_object,

    colors_groups_exchanger.face_area_to_vertex_groups,
    colors_groups_exchanger.vertex_colors_to_vertex_groups,
    colors_groups_exchanger.vertex_group_to_vertex_colors,
    colors_groups_exchanger.TISSUE_PT_weight,
    colors_groups_exchanger.TISSUE_PT_color,
    colors_groups_exchanger.weight_contour_curves,
    colors_groups_exchanger.weight_contour_mask,
    colors_groups_exchanger.weight_contour_displace,
    colors_groups_exchanger.harmonic_weight,
    colors_groups_exchanger.edges_deformation,
    colors_groups_exchanger.edges_bending,
    colors_groups_exchanger.weight_laplacian,
    colors_groups_exchanger.reaction_diffusion,
    colors_groups_exchanger.start_reaction_diffusion,
    colors_groups_exchanger.TISSUE_PT_reaction_diffusion,
    colors_groups_exchanger.reset_reaction_diffusion_weight,
    colors_groups_exchanger.formula_prop,
    colors_groups_exchanger.reaction_diffusion_prop,
    colors_groups_exchanger.weight_formula,
    colors_groups_exchanger.curvature_to_vertex_groups,
    colors_groups_exchanger.weight_formula_wiki,

    dual_mesh.dual_mesh,
    dual_mesh.dual_mesh_tessellated,

    lattice.lattice_along_surface,

    uv_to_mesh.uv_to_mesh
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        bpy.utils.register_class(cls)
    #bpy.utils.register_module(__name__)
    bpy.types.Object.tissue_tessellate = PointerProperty(
                                            type=tessellate_numpy.tissue_tessellate_prop
                                            )
    bpy.types.Object.formula_settings = CollectionProperty(
                                            type=colors_groups_exchanger.formula_prop
                                            )
    bpy.types.Object.reaction_diffusion_settings = PointerProperty(
                        type=colors_groups_exchanger.reaction_diffusion_prop
                        )
    # colors_groups_exchanger
    bpy.app.handlers.frame_change_post.append(colors_groups_exchanger.reaction_diffusion_def)
    #bpy.app.handlers.frame_change_post.append(tessellate_numpy.anim_tessellate)

def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        bpy.utils.unregister_class(cls)
    #tessellate_numpy.unregister()
    #colors_groups_exchanger.unregister()
    #dual_mesh.unregister()
    #lattice.unregister()
    #uv_to_mesh.unregister()

    del bpy.types.Object.tissue_tessellate


if __name__ == "__main__":
    register()
