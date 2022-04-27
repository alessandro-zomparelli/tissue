# SPDX-License-Identifier: GPL-2.0-or-later

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
    "version": (0, 3, 52),
    "blender": (2, 93, 0),
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
    importlib.reload(dual_mesh)
    importlib.reload(lattice)
    importlib.reload(uv_to_mesh)
    importlib.reload(utils)
    importlib.reload(config)
    importlib.reload(material_tools)
    importlib.reload(curves_tools)
    importlib.reload(polyhedra)

else:
    from . import tessellate_numpy
    from . import tissue_properties
    from . import weight_tools
    from . import dual_mesh
    from . import lattice
    from . import uv_to_mesh
    from . import utils
    from . import config
    from . import material_tools
    from . import curves_tools
    from . import polyhedra

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

    weight_tools.face_area_to_vertex_groups,
    weight_tools.vertex_colors_to_vertex_groups,
    weight_tools.vertex_group_to_vertex_colors,
    weight_tools.vertex_group_to_uv,
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

    curves_tools.tissue_to_curve_prop,
    curves_tools.tissue_convert_to_curve,
    curves_tools.tissue_convert_to_curve_update,
    curves_tools.TISSUE_PT_convert_to_curve,

    uv_to_mesh.uv_to_mesh,

    polyhedra.polyhedra_wireframe
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
    bpy.types.Object.tissue_to_curve = PointerProperty(
                                            type=curves_tools.tissue_to_curve_prop
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
