# SPDX-License-Identifier: GPL-2.0-or-later
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
# https://docs.blender.org/manual/en/latest/addons/mesh/tissue.html            #
#                                                                              #
# ############################################################################ #

bl_info = {
    "name": "Tissue",
    "author": "Alessandro Zomparelli",
    "version": (0, 3, 70),
    "blender": (4, 0, 2),
    "location": "",
    "description": "Tools for Computational Design",
    "warning": "",
    "doc_url": "{BLENDER_MANUAL_URL}/addons/mesh/tissue.html",
    "tracker_url": "https://github.com/alessandro-zomparelli/tissue/issues",
    "category": "Mesh",
}


if "bpy" in locals():
    import importlib
    importlib.reload(tessellate_numpy)
    importlib.reload(tissue_properties)
    importlib.reload(weight_tools)
    importlib.reload(weight_reaction_diffusion)
    importlib.reload(dual_mesh)
    importlib.reload(lattice)
    importlib.reload(uv_to_mesh)
    importlib.reload(utils)
    importlib.reload(config)
    importlib.reload(material_tools)
    importlib.reload(curves_tools)
    importlib.reload(polyhedra)
    importlib.reload(texture_reaction_diffusion)
    importlib.reload(contour_curves)

else:
    from . import tessellate_numpy
    from . import tissue_properties
    from . import weight_tools
    from . import weight_reaction_diffusion
    from . import dual_mesh
    from . import lattice
    from . import uv_to_mesh
    from . import utils
    from . import config
    from . import material_tools
    from . import curves_tools
    from . import polyhedra
    from . import texture_reaction_diffusion
    from . import contour_curves

import bpy
from bpy.props import PointerProperty, CollectionProperty, BoolProperty


classes = (
    config.tissuePreferences,
    config.tissue_install_numba,

    tissue_properties.tissue_prop,
    tissue_properties.tissue_tessellate_prop,
    tessellate_numpy.tissue_tessellate,
    tessellate_numpy.tissue_update_tessellate,
    tessellate_numpy.tissue_update_tessellate_deps,
    tessellate_numpy.TISSUE_PT_tessellate,
    tessellate_numpy.tissue_rotate_face_left,
    tessellate_numpy.tissue_rotate_face_right,
    tessellate_numpy.tissue_rotate_face_flip,
    tessellate_numpy.TISSUE_PT_tessellate_object,
    tessellate_numpy.TISSUE_PT_tessellate_frame,
    tessellate_numpy.TISSUE_PT_tessellate_component,
    tessellate_numpy.TISSUE_PT_tessellate_thickness,
    tessellate_numpy.TISSUE_PT_tessellate_direction,
    tessellate_numpy.TISSUE_PT_tessellate_options,
    tessellate_numpy.TISSUE_PT_tessellate_coordinates,
    tessellate_numpy.TISSUE_PT_tessellate_rotation,
    tessellate_numpy.TISSUE_PT_tessellate_selective,
    tessellate_numpy.TISSUE_PT_tessellate_morphing,
    tessellate_numpy.TISSUE_PT_tessellate_iterations,
    tessellate_numpy.tissue_render_animation,
    tessellate_numpy.tissue_remove,

    weight_tools.face_area_to_vertex_groups,
    weight_tools.vertex_colors_to_vertex_groups,
    weight_tools.vertex_group_to_vertex_colors,
    weight_tools.vertex_group_to_uv,
    weight_tools.TISSUE_PT_weight,
    weight_tools.TISSUE_PT_color,
    weight_tools.weight_contour_mask,
    weight_tools.weight_contour_displace,
    weight_tools.harmonic_weight,
    weight_tools.edges_deformation,
    weight_tools.edges_bending,
    weight_tools.weight_laplacian,
    weight_reaction_diffusion.start_reaction_diffusion,
    weight_reaction_diffusion.TISSUE_PT_reaction_diffusion,
    weight_reaction_diffusion.TISSUE_PT_reaction_diffusion_performance,
    weight_reaction_diffusion.TISSUE_PT_reaction_diffusion_vector_field,
    weight_reaction_diffusion.TISSUE_PT_reaction_diffusion_weight,
    weight_reaction_diffusion.TISSUE_PT_reaction_diffusion_cache,
    weight_reaction_diffusion.reset_reaction_diffusion_weight,
    weight_tools.formula_prop,
    weight_reaction_diffusion.reaction_diffusion_prop,
    weight_tools.weight_formula,
    weight_tools.update_weight_formula,
    weight_tools.curvature_to_vertex_groups,
    weight_tools.weight_formula_wiki,
    weight_tools.tissue_weight_distance,
    weight_tools.random_weight,
    weight_reaction_diffusion.bake_reaction_diffusion,
    weight_reaction_diffusion.reaction_diffusion_free_data,
    weight_tools.tissue_weight_streamlines,

    contour_curves.tissue_weight_contour_curves_pattern,
    contour_curves.tissue_update_contour_curves,
    contour_curves.tissue_contour_curves_prop,
    contour_curves.TISSUE_PT_contour_curves,

    dual_mesh.dual_mesh,
    dual_mesh.dual_mesh_tessellated,

    lattice.lattice_along_surface,

    material_tools.random_materials,
    material_tools.weight_to_materials,

    curves_tools.tissue_to_curve_prop,
    curves_tools.tissue_convert_to_curve,
    curves_tools.tissue_update_convert_to_curve,
    curves_tools.TISSUE_PT_convert_to_curve,

    uv_to_mesh.uv_to_mesh,

    polyhedra.polyhedral_wireframe,
    polyhedra.tissue_update_polyhedra,
    polyhedra.tissue_polyhedra_prop,
    polyhedra.TISSUE_PT_polyhedra_object,

    texture_reaction_diffusion.tex_reaction_diffusion_prop,
    texture_reaction_diffusion.start_tex_reaction_diffusion,
    texture_reaction_diffusion.reset_tex_reaction_diffusion,
    texture_reaction_diffusion.TISSUE_PT_tex_reaction_diffusion,
    texture_reaction_diffusion.TISSUE_PT_tex_reaction_diffusion_images
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        bpy.utils.register_class(cls)
    #bpy.utils.register_module(__name__)
    bpy.types.Object.tissue = PointerProperty(
                                    type=tissue_properties.tissue_prop
                                    )
    bpy.types.Object.tissue_tessellate = PointerProperty(
                                            type=tissue_properties.tissue_tessellate_prop
                                            )
    bpy.types.Object.tissue_polyhedra = PointerProperty(
                                            type=polyhedra.tissue_polyhedra_prop
                                            )
    bpy.types.Object.tissue_to_curve = PointerProperty(
                                            type=curves_tools.tissue_to_curve_prop
                                            )
    bpy.types.Object.tissue_contour_curves = PointerProperty(
                                            type=contour_curves.tissue_contour_curves_prop
                                            )
    bpy.types.Object.formula_settings = CollectionProperty(
                                            type=weight_tools.formula_prop
                                            )
    bpy.types.Object.reaction_diffusion_settings = PointerProperty(
                        type=weight_reaction_diffusion.reaction_diffusion_prop
                        )
    bpy.types.Object.tex_reaction_diffusion_settings = PointerProperty(
        type=texture_reaction_diffusion.tex_reaction_diffusion_prop
        )
    # weight_tools
    bpy.app.handlers.frame_change_post.append(weight_reaction_diffusion.reaction_diffusion_def)
    bpy.app.handlers.frame_change_post.append(texture_reaction_diffusion.tex_reaction_diffusion_def)

def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Object.tissue_tessellate


if __name__ == "__main__":
    register()
