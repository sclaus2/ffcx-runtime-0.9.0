# Code generation format strings for UFC (Unified Form-assembly Code)
# This code is released into the public domain.
#
# The FEniCS Project (http://www.fenicsproject.org/) 2018
"""Code generation strings for an integral."""

declaration = """
extern ufcx_integral {factory_name};
"""

factory = """
// Code for integral {factory_name}

void tabulate_tensor_{factory_name}({scalar_type}* restrict A,
                                    const {scalar_type}* restrict w,
                                    const {scalar_type}* restrict c,
                                    const {geom_type}* restrict coordinate_dofs,
                                    const int* restrict entity_local_index,
                                    const uint8_t* restrict quadrature_permutation)
{{
{tabulate_tensor}
}}

{enabled_coefficients_init}

ufcx_integral {factory_name} =
{{
  .enabled_coefficients = {enabled_coefficients},
  {tabulate_tensor_float32}
  {tabulate_tensor_float64}
  {tabulate_tensor_complex64}
  {tabulate_tensor_complex128}
  .needs_facet_permutations = {needs_facet_permutations},
  .coordinate_element_hash = {coordinate_element_hash},
}};

// End of code for integral {factory_name}
"""
factory_runtime_quad = """
// Code for integral {factory_name}

void tabulate_tensor_runtime_quad_{factory_name}({scalar_type}* restrict A,
                                    const {scalar_type}* restrict w,
                                    const {scalar_type}* restrict c,
                                    const {geom_type}* restrict coordinate_dofs,
                                    const int* restrict entity_local_index,
                                    const uint8_t* restrict quadrature_permutation,
                                    const basix_element* elements,
                                    const int* restrict num_points,
                                    const {geom_type}* restrict points,
                                    const {geom_type}* restrict weights)
{{
{tabulate_tensor}
}}

{finite_element_hashes_init}
{enabled_coefficients_init}

ufcx_integral {factory_name} =
{{
  .enabled_coefficients = {enabled_coefficients},
  {tabulate_tensor_runtime_quad_float32}
  {tabulate_tensor_runtime_quad_float64}
  {tabulate_tensor_runtime_quad_complex64}
  {tabulate_tensor_runtime_quad_complex128}
  .needs_facet_permutations = {needs_facet_permutations},
  .coordinate_element_hash = {coordinate_element_hash},
  .finite_element_hashes = {finite_element_hashes},
}};

// End of code for integral {factory_name}
"""