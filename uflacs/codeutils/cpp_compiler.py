
from ufl.classes import Terminal
from ufl.algorithms import Graph, expand_indices
from uflacs.codeutils.format_code import format_code
from uflacs.codeutils.code_formatter import CodeFormatter
from uflacs.codeutils.cpp_format import CppFormatterRules, CppDefaultFormatter

def compile_form(form):

    # This formatter is a multifunction implementing target
    # specific formatting rules, here using the default rules.
    target_formatter = CppDefaultFormatter()

    # This formatter is a multifunction with single operator
    # formatting rules for generic C++ formatting
    cpp_formatter = CppFormatterRules(target_formatter)

    # First we preprocess the form in standard UFL fashion
    fd = form.compute_form_data()

    # We'll place all code in a list while building the program
    code = []

    # Then we iterate over the integrals
    for data in fd.integral_data:
        domain_type, domain_id, integrals, metadata = data
        for itg in integrals:
            # Fetch the expression
            integrand = itg.integrand()

            # Then we apply the additional expand_indices preprocessing that form preprocessing does not
            expr = expand_indices(integrand)

            # And build the computational graph of the expression
            G = Graph(expr)
            V, E = G

            # In this dictionary we will place ufl expression to C++
            # variable name mappings while building the program
            variables = {}

            # This final formatter implements a generic framework handling indices etc etc.
            code_formatter = CodeFormatter(cpp_formatter, variables)
            integral_code = [] # TODO: Use code formatting utils

            nv = len(V)
            vnum = 0
            for i, v in enumerate(V):
                # Check if we should make a variable here
                if i == nv-1:
                    vname = 'integrand'
                elif v.shape() == () and not isinstance(v, Terminal):
                    vname = 'v%d' % vnum
                    vnum += 1
                else:
                    vname = None
                # If so, generate code for it
                if vname is not None:
                    vcode = code_formatter.visit(v)
                    integral_code.append("%s = %s;" % (vname, vcode))
                    code_formatter.variables[v] = vname

            # Join code to what we have
            code.append(integral_code)

    return format_code(code)