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
    "version": (0, 3, 45),
    "blender": (2, 83, 2),
    "location": "",
    "description": "Tools for Computational Design",
    "warning": "",
    "wiki_url": "https://github.com/alessandro-zomparelli/tissue/wiki",
    "tracker_url": "https://github.com/alessandro-zomparelli/tissue/issues",
    "category": "Mesh"}


if "bpy" in locals():
    import importlib
    importlib.reload(tessellate_numpy)
    importlib.reload(weight_tools)
    importlib.reload(dual_mesh)
    importlib.reload(lattice)
    importlib.reload(uv_to_mesh)
    importlib.reload(utils)
    importlib.reload(preferences)
    importlib.reload(material_tools)

else:
    from . import tessellate_numpy
    from . import weight_tools
    from . import dual_mesh
    from . import lattice
    from . import uv_to_mesh
    from . import utils
    from . import preferences
    from . import material_tools

import bpy
from bpy.props import PointerProperty, CollectionProperty, BoolProperty

classes = (
    preferences.tissuePreferences,
    preferences.tissue_install_numba,

    tessellate_numpy.tissue_tessellate_prop,
    tessellate_numpy.tissue_tessellate,
    tessellate_numpy.tissue_update_tessellate,
    tessellate_numpy.tissue_refresh_tessellate,
    tessellate_numpy.TISSUE_PT_tessellate,
    tessellate_numpy.tissue_rotate_face_left,
    tessellate_numpy.tissue_rotate_face_right,
    tessellate_numpy.TISSUE_PT_tessellate_object,
    tessellate_numpy.TISSUE_PT_tessellate_frame,
    tessellate_numpy.TISSUE_PT_tessellate_thickness,
    tessellate_numpy.TISSUE_PT_tessellate_coordinates,
    tessellate_numpy.TISSUE_PT_tessellate_rotation,
    tessellate_numpy.TISSUE_PT_tessellate_options,
    tessellate_numpy.TISSUE_PT_tessellate_selective,
    tessellate_numpy.TISSUE_PT_tessellate_morphing,
    tessellate_numpy.TISSUE_PT_tessellate_iterations,
    tessellate_numpy.polyhedra_wireframe,

    weight_tools.face_area_to_vertex_groups,
    weight_tools.vertex_colors_to_vertex_groups,
    weight_tools.vertex_group_to_vertex_colors,
    weight_tools.TISSUE_PT_weight,
    weight_tools.TISSUE_PT_color,
    weight_tools.weight_contour_curves,
    weight_tools.tissue_weight_contour_curves_pattern,
    weight_tools.weight_contour_mask,
    weight_tools.weight_contour_displace,
    weight_tools.harmonic_weight,
    weight_tools.edges_deformation,
    weight_tools.edges_bending,
    weight_tools.weight_laplacian,
    weight_tools.reaction_diffusion,
    weight_tools.start_reaction_diffusion,
    weight_tools.TISSUE_PT_reaction_diffusion,
    weight_tools.TISSUE_PT_reaction_diffusion_weight,
    weight_tools.reset_reaction_diffusion_weight,
    weight_tools.formula_prop,
    weight_tools.reaction_diffusion_prop,
    weight_tools.weight_formula,
    weight_tools.update_weight_formula,
    weight_tools.curvature_to_vertex_groups,
    weight_tools.weight_formula_wiki,
    weight_tools.tissue_weight_distance,
    weight_tools.random_weight,
    weight_tools.bake_reaction_diffusion,
    weight_tools.reaction_diffusion_free_data,
    weight_tools.tissue_weight_streamlines,

    dual_mesh.dual_mesh,
    dual_mesh.dual_mesh_tessellated,

    lattice.lattice_along_surface,

    material_tools.random_materials,
    material_tools.weight_to_materials,

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
                                            type=weight_tools.formula_prop
                                            )
    bpy.types.Object.reaction_diffusion_settings = PointerProperty(
                        type=weight_tools.reaction_diffusion_prop
                        )
    # weight_tools
    bpy.app.handlers.frame_change_post.append(weight_tools.reaction_diffusion_def)
    #bpy.app.handlers.frame_change_post.append(tessellate_numpy.anim_tessellate)

def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Object.tissue_tessellate


if __name__ == "__main__":
    register()
