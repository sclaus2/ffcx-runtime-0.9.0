# Copyright (C) 2015-2021 Martin Sandve Alnæs, Michal Habera, Igor Baratta
#
# This file is part of FFCx. (https://www.fenicsproject.org)
#
# SPDX-License-Identifier:    LGPL-3.0-or-later
"""Generate UFC code for an integral."""

import logging
import sys
import string

import numpy as np

from ffcx.codegeneration.backend import FFCXBackend
from ffcx.codegeneration.C import integrals_template as ufcx_integrals
from ffcx.codegeneration.C.c_implementation import CFormatter
from ffcx.codegeneration.integral_generator import IntegralGenerator
from ffcx.codegeneration.utils import dtype_to_c_type, dtype_to_scalar_dtype
from ffcx.ir.representation import IntegralIR

logger = logging.getLogger("ffcx")


def generator(ir: IntegralIR, options):
    """Generate C code for an integral."""
    logger.info("Generating code for integral:")
    logger.info(f"--- type: {ir.expression.integral_type}")
    logger.info(f"--- name: {ir.expression.name}")

    """Generate code for an integral."""
    factory_name = ir.expression.name

    # Format declaration
    declaration = ufcx_integrals.declaration.format(factory_name=factory_name)

    # Create FFCx C backend
    backend = FFCXBackend(ir, options)

    # Configure kernel generator
    ig = IntegralGenerator(ir, backend)

    num_runtime_rules = 0
    for rule in ir.expression.integrand.keys():
      if(rule.is_runtime):
         num_runtime_rules +=1

    assert(num_runtime_rules<2)

    remove_rules = []
    runtime_part = []
    body_runtime = []

    for rule in ir.expression.integrand.keys():
      if(rule.is_runtime):
         #generate different parts here
         runtime_part = ig.generate_runtime(rule)
         remove_rules.append(rule)

    #Delete all runtime rules from IR to generate code for standard integrals with remainder
    for rule in remove_rules:
       ir.expression.integrand.pop(rule)

    if(len(remove_rules)>0):
      CF = CFormatter(options["scalar_type"])
      body_runtime = CF.c_format(runtime_part)

    #reinitialize IntegralGenerator for geometric data
    ig = IntegralGenerator(ir, backend)

    parts = []
    body = []

    #check if there is any standard integral
    if(len(ir.expression.integrand)>0):
      # Generate code ast for the tabulate_tensor body
      parts = ig.generate()

      # Format code as string
      CF = CFormatter(options["scalar_type"])
      body = CF.c_format(parts)

    # Generate generic FFCx code snippets and add specific parts
    code = {}
    implementation_parts = []
    np_scalar_type = np.dtype(options["scalar_type"]).name

    code["tabulate_tensor_float32"] = ".tabulate_tensor_float32 = NULL,"
    code["tabulate_tensor_float64"] = ".tabulate_tensor_float64 = NULL,"
    code["tabulate_tensor_runtime_float32"] = ".tabulate_tensor_runtime_float32 = NULL,"
    code["tabulate_tensor_runtime_float64"] = ".tabulate_tensor_runtime_float64 = NULL,"
    if sys.platform.startswith("win32"):
          code["tabulate_tensor_complex64"] = ""
          code["tabulate_tensor_complex128"] = ""
    else:
          code["tabulate_tensor_complex64"] = ".tabulate_tensor_complex64 = NULL,"
          code["tabulate_tensor_complex128"] = ".tabulate_tensor_complex128 = NULL,"

    #Generate code string for standard integral
    if(len(body)>0):
      # Take care of standard integrals first
      code[f"tabulate_tensor_{np_scalar_type}"] = (
          f".tabulate_tensor_{np_scalar_type} = tabulate_tensor_{factory_name},"
      )

      code["tabulate_tensor"] = body

      tabulate_tensor_string = ufcx_integrals.factory_tabulate.format(
          factory_name=factory_name,
          tabulate_tensor=code["tabulate_tensor"],
          scalar_type=dtype_to_c_type(options["scalar_type"]),
          geom_type=dtype_to_c_type(dtype_to_scalar_dtype(options["scalar_type"])),
      )

      implementation_parts.append(tabulate_tensor_string)

    #Generate code string for runtime integral
    if(len(body_runtime)>0):
      if(np_scalar_type in ("complex64", "complex128")):
        print("Not implemented for runtime integrals")

      code[f"tabulate_tensor_runtime_{np_scalar_type}"] = (
          f".tabulate_tensor_runtime_{np_scalar_type} = tabulate_tensor_runtime_{factory_name},"
      )

      code["tabulate_tensor_runtime"] = body_runtime

      runtime_tabulate_tensor_string = ufcx_integrals.factory_runtime_tabulate.format(
          factory_name=factory_name,
          tabulate_tensor_runtime=code["tabulate_tensor_runtime"],
          scalar_type=dtype_to_c_type(options["scalar_type"]),
          geom_type=dtype_to_c_type(dtype_to_scalar_dtype(options["scalar_type"])),
      )

      implementation_parts.append(runtime_tabulate_tensor_string)

    #Generate code string for ufcx integral
    if len(ir.enabled_coefficients) > 0:
        values = ", ".join("1" if i else "0" for i in ir.enabled_coefficients)
        sizes = len(ir.enabled_coefficients)
        code["enabled_coefficients_init"] = (
            f"bool enabled_coefficients_{ir.expression.name}[{sizes}] = {{{values}}};"
        )
        code["enabled_coefficients"] = f"enabled_coefficients_{ir.expression.name}"
    else:
        code["enabled_coefficients_init"] = ""
        code["enabled_coefficients"] = "NULL"

    element_hash = 0 if ir.coordinate_element_hash is None else ir.coordinate_element_hash

    num_elements = len(ir.expression.finite_element_hashes)
    assert(num_elements == len(ir.expression.finite_element_deriv_order))

    if num_elements> 0:
      values = ", ".join(
          f"UINT64_C({0 if el is None else el})" for el in ir.expression.finite_element_hashes
      )
      sizes = num_elements
      code["finite_element_hashes_init"] = (
          f"uint64_t finite_element_hashes_{ir.expression.name}[{sizes}] = {{{values}}};"
      )
      code["finite_element_hashes"] = f"finite_element_hashes_{ir.expression.name}"

      values = ", ".join(str(i) for i in ir.expression.finite_element_deriv_order)
      code["finite_element_deriv_order_init"] = (
          f"int finite_element_deriv_order_{ir.expression.name}[{sizes}] = {{{values}}};"
      )
      code["finite_element_deriv_order"] = f"finite_element_deriv_order_{ir.expression.name}"
    else:
      code["finite_element_hashes_init"] = ""
      code["finite_element_hashes"] = "NULL"
      code["finite_element_deriv_order_init"] = ""
      code["finite_element_deriv_order"] = "NULL"

    ufcx_integral_string = ufcx_integrals.factory_integral.format(
        factory_name=factory_name,
        enabled_coefficients=code["enabled_coefficients"],
        enabled_coefficients_init=code["enabled_coefficients_init"],
        num_finite_elements = num_elements,
        finite_element_hashes=code["finite_element_hashes"],
        finite_element_hashes_init=code["finite_element_hashes_init"],
        finite_element_deriv_order=code["finite_element_deriv_order"],
        finite_element_deriv_order_init=code["finite_element_deriv_order_init"],
        needs_facet_permutations="true" if ir.expression.needs_facet_permutations else "false",
        scalar_type=dtype_to_c_type(options["scalar_type"]),
        geom_type=dtype_to_c_type(dtype_to_scalar_dtype(options["scalar_type"])),
        coordinate_element_hash=f"UINT64_C({element_hash})",
        tabulate_tensor_float32=code["tabulate_tensor_float32"],
        tabulate_tensor_float64=code["tabulate_tensor_float64"],
        tabulate_tensor_complex64=code["tabulate_tensor_complex64"],
        tabulate_tensor_complex128=code["tabulate_tensor_complex128"],
        tabulate_tensor_runtime_float32=code["tabulate_tensor_runtime_float32"],
        tabulate_tensor_runtime_float64=code["tabulate_tensor_runtime_float64"],
    )

    implementation_parts.append(ufcx_integral_string)

    implementation = "\n".join(implementation_parts)

    return declaration, implementation
