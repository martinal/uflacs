
from ufl.permutation import build_component_numbering
from ufl.classes import GeometricQuantity

from uflacs.utils.log import uflacs_assert, warning, error

from uflacs.codeutils.format_code import ForRange
from uflacs.codeutils.indexmapping import IndexMapping, AxisMapping

from uflacs.geometry.default_names import names
from uflacs.geometry.generate_geometry_snippets import (
    generate_jacobian_snippets,
    generate_jacobian_determinants_snippets,
    generate_jacobian_inverse_snippets,
    generate_cell_scaling_factor_snippets,
    generate_cell_volume_snippets,
    generate_circumradius_snippets,
    generate_facet_scaling_factor_snippets,
    generate_facet_area_snippets,
    generate_facet_direction_snippets,
    generate_facet_normal_snippets,
    generate_x_from_xi_snippets,
    generate_xi_from_x_snippets)

from uflacs.elementtables.table_utils import generate_psi_table_name, derivative_listing_to_counts

from uflacs.codeutils.cpp_statement_formatting_rules import CppStatementFormattingRules
langfmt = CppStatementFormattingRules()

def format_entity_name(entitytype, r):
    if entitytype == "cell":
        entity = "0" #None # FIXME: Keep 3D tables and use entity 0 for cells or make tables 2D and use None?
    elif entitytype == "facet":
        entity = names.facet + names.restriction_postfix[r]
    elif entitytype == "vertex":
        entity = names.vertex
    return entity

def get_element_table_data(ir, entitytype, num_points, element,
                           flat_component, derivatives,
                           preserved):

    element_counter = ir["element_map"][num_points][element]

    gdim = element.cell().geometric_dimension()
    derivative_counts = derivative_listing_to_counts(derivatives, gdim)

    element_table_name = generate_psi_table_name(element_counter, flat_component,
                                               derivative_counts, entitytype)

    # Hack! To keep some tables accessible without nonzero stripping:
    if preserved:
        element_table_name = "p" + element_table_name

    unique_table_name, begin, end = ir["table_ranges"][element_table_name]

    return unique_table_name, begin, end

def format_element_table_access(ir, entitytype, num_points, element,
                                flat_component, derivatives, entity, idof,
                                preserved):
    unique_table_name, begin, end = get_element_table_data(ir, entitytype, num_points, element,
                                                           flat_component, derivatives, preserved)
    if preserved:
        dof = idof
        uflacs_assert(begin == 0, "Trying to access a preserved table but found nonzero offset (%d, %d)." % (begin, end))
    else:
        dof = langfmt.sum(begin, idof)
    ipoint = names.iq if num_points > 1 else "0"
    return langfmt.array_access(unique_table_name, entity, ipoint, dof)

def get_inline_mapping_row(element, gd, tdim, gdim, r):
    # TODO: Pick right mapping
    if 1:
        mapping_row = [langfmt.array_access("K", langfmt.sum(langfmt.product(ld, gdim), gd)) for ld in range(tdim)]
    else:
        mapping_row = [langfmt.array_access("J", langfmt.sum(langfmt.product(gd, tdim), ld)) for ld in range(tdim)]
    return mapping_row

def build_crdata(reqdata, shape, symmetry):
    crdata = {}
    if shape:
        vi2si, dummy = build_component_numbering(shape, symmetry)
    else:
        # Need scalar component to be None for table naming
        vi2si = {():None}
    #for ((c,d,r,a),varname) in reqdata.iteritems(): # FIXME: Use average
    for ((c,d,r),varname) in reqdata.iteritems():
        c = vi2si[c]
        key = (c,r)
        data = crdata.get(key)
        if not data:
            # Store mapping (c,r) -> (value name, derivative orders set, derivative value names list)
            data = [None,set(),[]]
            crdata[key] = data
        if d:
            data[1].add(len(d))
            data[2].append((d,varname))
        else:
            uflacs_assert(data[0] in (None,varname), "Got two variable names for same component!")
            data[0] = varname
    return crdata

class FFCStatementFormatter(object):
    """Class containing functions for generating definitions of registers,
    argument loops, and output variable names."""
    def __init__(self, dependency_handler, ir):
        # TODO: Make more configurable?

        self._dependency_handler = dependency_handler
        self._integral_type = ir["integral_type"]
        self._cell = ir["cell"]
        self._entitytype = ir["entitytype"]
        self._argument_space_dimensions = ir["prim_idims"] # FIXME: Dimensions with dS?

        self._ir = ir

        # Practical variables
        rank = ir["rank"]
        self._idofs = ["%s%d" % (names.ia, i) for i in range(rank)] # FIXME: Make reusable function for idof

        # TODO: Support multiple quadrature loops, affects several places...
        quadrature_rules = ir["quadrature_weights"]
        if quadrature_rules:
            uflacs_assert(len(quadrature_rules) == 1, "Multiple quadrature rules not implemented.")
            self._num_points = quadrature_rules.keys()[0]
            self._weights, self._points = quadrature_rules[self._num_points]
        else:
            self._num_points = 0
            self._weights = ()
            self._points = ()

        if self._integral_type == "point":
            self._enable_coord_loop = False
            self._enable_accumulation = False
            self._enable_quadrature_rule = False
        else:
            self._enable_coord_loop = True
            self._enable_accumulation = True
            self._enable_quadrature_rule = self._num_points > 0

    def define_registers(self, num_registers, partition=None):
        code = [langfmt.comment("Declaring variables for intermediate computations:")]

        # TODO: Use partitioned registers in compiler, then disallow partition=None
        name = names.s if partition is None else ("%s%d" % (names.s,partition))
        code += [langfmt.double_array_decl(name, num_registers)]

        code.append("")
        return code

    def define_piecewise_geometry(self):
        code = [langfmt.comment("Computing piecewise constant geometry for %s integral on %s in %dD:" % (
            self._integral_type, self._cell.cellname(), self._cell.geometric_dimension()))]

        # TODO: Seed this from terminal data and extend with geometry dependency dict
        needed = {}

        # Generate geometry either for single cell or cells on both sides of facet
        if self._integral_type == "interior_facet":
            restrictions = ("+", "-")
        elif self._integral_type == "point":
            restrictions = ()
        else:
            assert self._integral_type in ("cell", "exterior_facet")
            restrictions = (None,)
        needed["J"] = restrictions
        needed["detJ"] = restrictions
        needed["K"] = restrictions
        needed["volume"] = restrictions
        needed["circumradius"] = restrictions
        needed["det"] = restrictions

        # Generate geometry either for single cell or + side cell of facet
        if self._integral_type == "interior_facet":
            restrictions = ("+",)
        elif self._integral_type == "point":
            restrictions = ()
        else:
            assert self._integral_type in ("cell", "exterior_facet")
            restrictions = (None,)
        needed["facet_area"] = restrictions
        needed["n"] = restrictions # FIXME: normal direction depends on side! Add a - when referencing from - side

        # Generating code in fixed ordering so dependencies are taken care of:

        for r in needed.get("J", ()):
            code.append(generate_jacobian_snippets(self._cell, r))

        for r in needed.get("detJ", ()):
            code.append(generate_jacobian_determinants_snippets(self._cell, r))

        for r in needed.get("K", ()):
            code.append(generate_jacobian_inverse_snippets(self._cell, r))

        if self._entitytype == "cell":
            for r in needed.get("det", ()):
                code.append(generate_cell_scaling_factor_snippets(self._cell))

        elif self._entitytype == "facet":
            for r in needed.get("det", ()):
                code.append(generate_facet_scaling_factor_snippets(self._cell, r))
            for r in needed.get("facet_area", ()):
                code.append(generate_facet_area_snippets(self._cell, r))
            for r in needed.get("n", ()):
                code.append(generate_facet_direction_snippets(self._cell, r))
                code.append(generate_facet_normal_snippets(self._cell, r))
            # TODO: Add facet only geometry stuff here, any more?

        elif self._entitytype == "vertex":
            pass # TODO: Define x and xi for single vertex evaluation here? Not for multiple points!

        for r in needed.get("volume", ()):
            code.append(generate_cell_volume_snippets(self._cell, r))

        for r in needed.get("circumradius", ()):
            code.append(generate_circumradius_snippets(self._cell, r))

        # TODO: Add all cell geometry stuff here, any more?

        code.append("")
        return code

    def _define_piecewise_geometry(self):
        code = [langfmt.comment("Computing piecewise constant geometry:")]

        # A dependency graph like this might be a way to
        # automatically figure out which quantities to generate?
        dependencies = {
            "J": ("vertex_coordinates",),
            "detJ": ("J",),
            "K": ("J", "detJ"),
            "x": ("xi", "J", "vertex_coordinates"),
            "xi": ("x", "K", "vertex_coordinates"),
            }
        geometric_quantity_name = str

        # Get the set of all geometry we need
        needed = set()
        for t, c, d, r in self._dependency_handler.terminal_data:
            if isinstance(t, GeometricQuantity):
                uflacs_assert(not d, "Derivatives of geometry not supported.")
                needed.add((geometric_quantity_name(t), r)) # TODO: Consider component c as well

        # Make an intermediate stable but arbitrary sorting
        workstack = sorted(needed)

        # Make a set of already known quantities
        done = set()
        done.add("vertex_coordinates")

        # Make a set of quantities to postphone
        skip = set(item for item in workstack if item[0] in ("x","xi"))
        # ... but keep these in workstack to build dependencies properly!

        # Build list of geometry including dependencies
        ordered = []
        while workstack:
            # Get next item to do
            item = workstack.pop(0)
            # Drop it if already done
            if item in done:
                continue
            # Get dependencies of item that are not done
            deps = [(d, r) for d in dependencies[item[0]]
                    if (d, r) not in done]
            if deps:
                # If we have any dependencies, put them first on the stack
                workstack = deps + [item] + workstack
            else:
                # If we have no dependencies, do this item next,
                # unless it's postphoned
                if item not in skip:
                    ordered.append(item)

        # Finally we can generate some code
        for name, restriction in ordered:
            code.append(langfmt.comment("TODO: Compute %s%s here" % (name, restriction)))

        code.append("")
        return code

    def define_coord_vars(self):
        code = [langfmt.comment("Computing coordinates in necessary coordinate systems:")]

        # TODO: Skip what's not needed
        # TODO: Parameter to pick behaviour here:
        # For dx, we need xi -> x
        # For ds, we need xi_facet -> xi -> x
        # For dS, we need xi_facet -> xi0,xi1 -> x0,x1
        # For dP(points), we need x -> xi
        # For dP(vertex), we need
        #   x = &vertex_coordinates[vertex*gd]; # TODO: Assumption on ordering of vertices?
        #   xi = &reference_vertex_coordinates[vertex*gd]

        gdim = self._cell.geometric_dimension()
        tdim = self._cell.topological_dimension()

        # format current quadrature point
        point = names.iq if self._num_points > 1 else "0"

        if self._integral_type == "cell":
            # let xi point to current quadrature point
            code += ["const double *%s = &%s[%s*%d];" % (names.xi, names.points, point, tdim)]

            # map local point xi to physical point x
            code.append(generate_x_from_xi_snippets(self._cell, None))

            det_restrictions = (None,)

        elif self._integral_type == "exterior_facet":
            # let xi point to current quadrature point
            code += ["const double *%s = &%s[%s*%d];" % (names.xi, names.points, point, tdim)]

            # FIXME: map local point xi on facet to physical point x
            #code.append(generate_x_from_xi_snippets(self._cell, None))

            det_restrictions = (None,)

        elif self._integral_type == "interior_facet":
            # let xi point to current quadrature point (FIXME: On reference facet cell?)
            code += ["const double *%s = &%s[%s*%d];" % (names.xi, names.points, point, tdim)]

            # FIXME: map xi_facet to xi0, xi1 on reference cells
            # FIXME: map xi_facet or xi0 to physical coordinate x

            det_restrictions = ("+",)

        elif self._integral_type == "point":
            # assuming 'vertex' defined, not arbitrary point integral
            # let x point to specified vertex
            code += ["const double *%s = &%s[%s*%d];" % (names.x, names.vertex_coordinates, names.vertex, tdim)]

            # let xi point to current quadrature point
            #code += ["const double *%s = &%s[%s*%d];" % (names.xi, names.points, point, tdim)]

            assert not self._enable_accumulation

        elif self._integral_type == "pointset": # FIXME: Add pointset domain type to distinguish between the two
            # multiple point evaluation, points are given
            code += ["const double *%s = &%s[%d * %s];" % (
                names.x, names.points, gdim, names.iq)] # TODO: Using 'iq' to mean 'current point' in input coordinate loop, is this ok?

            # map local point xi to physical point x
            code.append(generate_xi_from_x_snippets(self._cell, None))

            assert not self._enable_accumulation

        # Define weights
        if self._enable_accumulation:
            code += ["", langfmt.comment("Compute accumulation weight:")]
            ipoint = names.iq if self._num_points > 1 else "0"
            code += [langfmt.var_decl("const double", names.qw, langfmt.array_access(names.weights, ipoint))]

            for r in det_restrictions:
                det = names.det + names.restriction_postfix[r]
                code += [langfmt.var_decl("const double", names.D, langfmt.product(names.qw, det))]

        code += [""]
        return code

    def _define_coord_dependent_coefficient(self, w, reqdata):
        "Define a single coordinate dependent coefficient."
        code = []

        # Get some properties of w
        wc = w.count()
        element = w.element()

        wsh = w.shape()
        if wsh:
            vi2si, dummy = build_component_numbering(wsh, element.symmetry())
        else:
            # Need scalar component to be () for table naming
            vi2si = {():()}

        # Offset by element space dimension in case of negative restriction.
        #import ffc
        #ffc_element = ffc.fiatinterface.create_element(element)
        #fe_dim = ffc_element.space_dimension()
        fe_dim = self._ir["coeff_idims"][wc] # TODO: Nicer way to get ndofs?

        r_offsets = {"+": 0, "-": fe_dim, None: 0}

        tdim = self._cell.topological_dimension()
        gdim = self._cell.geometric_dimension()

        # Sort all referenced components in a canonical ordering,
        # with components mapped to flat index, including symmetry mapping,
        # and derivatives grouped by component for better code structure
        crdata = build_crdata(reqdata, w.shape(), element.symmetry())

        # Loop over components
        for (c,r) in sorted(crdata.keys()):
            value_varname, derivative_orders, derivative_varnames = crdata[(c,r)]

            # Pick entity index variable name, following ufc argument names
            entity = format_entity_name(self._entitytype, r)

            # Compute coefficient values
            if value_varname:
                body = []

                # Get element value table data
                unique_table_name, begin, end = get_element_table_data(self._ir, self._entitytype, self._num_points, element, c, (), False)

                # Add restriction offset and lower dof index bound to get bounds on dof index loop
                dof_offset = begin + r_offsets[r]
                num_dofs = end - begin

                # Declare variable for coefficient value initialized to zero
                code.append(langfmt.double_decl(value_varname, "0.0"))

                # Format statement accumulating product of dofs and table values
                ipoint = names.iq if self._num_points > 1 else "0"
                wexpr = langfmt.array_access(names.w, wc, langfmt.sum(names.ic, dof_offset))
                feexpr = langfmt.array_access(unique_table_name, entity, ipoint, names.ic)
                w_x_fe = langfmt.product(wexpr, feexpr)
                body.append(langfmt.iadd(value_varname, w_x_fe))

                # Format loop over coefficient dofs
                code.append(ForRange(names.ic, 0, num_dofs, body=body))

            # Compute local gradient (and eventually local hessian etc.) for component c,r
            for order in sorted(derivative_orders):
                uflacs_assert(order == 1, "Higher order derivatives not yet implemented.") # TODO

                # Make name for local gradient of component c,r or coefficient with count wc:
                locgradname = "LD%d_w%d" % (order, wc)
                if c is not None:
                    locgradname += "_c%d" % c
                locgradname += names.restriction_postfix[r]

                # Declare array for local gradient initialized to zero
                dim = tdim**order
                code.append(langfmt.double_array_decl(locgradname, (dim,), "{ 0.0 }"))

                # Add accumulation statement for each local derivative direction
                for ld in range(tdim):
                    body = []
                    # Get element derivative value table data
                    unique_table_name, begin, end = get_element_table_data(self._ir, self._entitytype, self._num_points, element, c, (ld,), False)

                    # Add restriction offset and lower dof index bound to get bounds on dof index loop
                    dof_offset = begin + r_offsets[r]
                    num_dofs = end - begin

                    # Format statement accumulating product of dofs and table values
                    ipoint = names.iq if self._num_points > 1 else "0"
                    wexpr = langfmt.array_access(names.w, wc, langfmt.sum(names.ic, dof_offset))
                    dfeexpr = langfmt.array_access(unique_table_name, entity, ipoint, names.ic)
                    dw_x_fe = langfmt.product(wexpr, dfeexpr)
                    body.append(langfmt.iadd(langfmt.array_access(locgradname, ld), dw_x_fe))

                    # Format loop over coefficient dofs
                    code.append(ForRange(names.ic, 0, num_dofs, body=body)) # TODO: Need same begin,end for each ld to merge loops.

            # Map local derivatives with K (or J^T) to get the global derivatives
            for d, dvalue_varname in sorted(derivative_varnames):
                gd, = d # TODO

                # Get list with direct access to mapping row entries
                mapping_row = get_inline_mapping_row(element, gd, tdim, gdim, r)

                # Get list with direct access to local gradient values
                reference_grad = [langfmt.array_access(locgradname, ld) for ld in range(tdim)]

                # Map local gradient with row of K (or J^T) to get the
                # global derivative direction d
                dvalue_expr = " + ".join(langfmt.product(mapping_row[ld], reference_grad[ld]) for ld in range(tdim))

                # Declare variable for coefficient derivative value initialized
                # with inline mapping expression
                code.append(langfmt.var_decl("const double", dvalue_varname, dvalue_expr))

        return code

    def define_coord_dependent_coefficients(self):
        "Define all coordinate dependent coefficients."
        code = []

        # Compute non-constant coefficients and their derivatives
        for w in self._dependency_handler.mapped_coefficients:

            # Constants are handled by direct reference to dof array
            if w.is_cellwise_constant():
                continue

            # Only compute coefficient components that have been referenced
            reqdata = self._dependency_handler.required.get(w)
            if reqdata is None:
                print
                print "In define_coord_dependent_coefficients: req is None:"
                print 'repr(w):', repr(w)
                print 'str(w): ', str(w)
                print 'required set:'
                print self._dependency_handler.required
                print
                continue

            code.append(langfmt.comment("Compute coefficient %s%d" % (names.w, w.count())))
            code.append(self._define_coord_dependent_coefficient(w, reqdata))

        if code:
            comment = langfmt.comment("Compute coordinate dependent coefficients and their derivatives")
            code = [comment, code, ""]
        return code

    def define_argument_loop_vars(self, argument_number):
        "Define all mapped argument derivatives for this argument count."
        dh = self._dependency_handler
        code = []

        v = self._dependency_handler.mapped_arguments[argument_number]
        assert v.number() == argument_number
        idof = self._idofs[argument_number]

        reqdata = self._dependency_handler.required.get(v)
        if reqdata:
            element = v.element()
            tdim = self._cell.topological_dimension()
            gdim = self._cell.geometric_dimension()

            crdata = build_crdata(reqdata, v.shape(), element.symmetry())

            # Compute mapped derivatives for each argument component c,r
            for (c,r) in sorted(crdata.keys()):
                value_varname, derivative_orders, derivative_varnames = crdata[(c,r)]

                # Ignoring value_varname, since values are fetched directly from tables

                # Pick entity index variable name, following ufc argument names
                entity = format_entity_name(self._entitytype, r)

                # Don't need to generate local derivatives
                uflacs_assert(tuple(derivative_orders) == (1,),
                              "Higher order derivatives not yet implemented.") # TODO

                # Map local derivatives with K (or J^T) to get the global derivatives
                for d, dvalue_varname in sorted(derivative_varnames):
                    gd, = d # TODO

                    # Get list with direct access to mapping row entries
                    mapping_row = get_inline_mapping_row(element, gd, tdim, gdim, r)

                    # Get list with direct access to local gradient values
                    reference_grad = [format_element_table_access(self._ir, self._entitytype,
                                                              self._num_points, element,
                                                              c, (ld,), entity, idof, True)
                                  for ld in range(tdim)]
                    #print c, r, gd, reference_grad

                    # Map local gradient with row of K (or J^T) to get the
                    # global derivative direction d
                    dvalue_expr = " + ".join(langfmt.product(mapping_row[ld], reference_grad[ld])
                                             for ld in range(tdim))

                    # Declare variable for coefficient derivative value initialized
                    # with inline mapping expression
                    code.append(langfmt.var_decl("const double", dvalue_varname, dvalue_expr))

        if code:
            comment = langfmt.comment("Compute mapped derivatives of argument %d" % (argument_number,))
            code = [comment] + code + [""]
        return code