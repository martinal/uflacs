

# FIXME: This file probably needs a massive rewrite.


from ufl.classes import Terminal, Indexed, Grad

from uflacs.codeutils.expr_formatter import ExprFormatter
from uflacs.codeutils.format_code import (format_code,
                                                    Block, Indented, Namespace, Class)

from uflacs.representation.compute_expr_ir import compute_expr_ir 
from uflacs.generation.generate import generate_expression_code

from uflacs.backends.dolfin.expression import format_dolfin_expression
from uflacs.backends.dolfin.dolfin_language_formatter import DolfinExpressionLanguageFormatter
from uflacs.backends.dolfin.dolfin_statement_formatter import DolfinExpressionStatementFormatter

from uflacs.params import default_parameters

def compile_dolfin_expression_body(expr, parameters, object_names=None):
    "Generate (code for eval, member names dict) for a single UFL expression."
    # Setup generic compiler arguments (TODO: get from preprocessed expr data?)
    form_argument_mapping = {}
    if object_names is None:
        object_names = {}

    # Compile expression into intermediate representation (partitions in ssa form)
    partitions_ir = compute_expr_ir(expr, parameters)

    # Compile eval function body with generic compiler routine
    code, coefficient_names = generate_expression_code(partitions_ir, form_argument_mapping, object_names,
                                                       DolfinExpressionLanguageFormatter,
                                                       DolfinExpressionStatementFormatter)

    # Format into a single string
    #formatted = format_code(code)

    # Get member function names TODO: Distinguish types of functions?
    member_names = dict(constants=[],
                        mesh_functions=[],
                        generic_functions=coefficient_names,
                        functions=[],
                        )

    return code, member_names

def compile_dolfin_expression_class(expr, name, parameters, object_names):
    """Generate code for a single dolfin Expression from a single UFL Expr.

    *Arguments*

        expr
            An UFL expression to compile.

        name
            Name of expression to compile.

        object_names
            A dictionary with object id:name mapping.

    *Returns*

        (code, classname) for compiled expression.
    """

    classname = 'UflacsExpression_%s' % name
    shape = expr.shape()

    eval_body, member_names = compile_dolfin_expression_body(expr, parameters, object_names)

    # Stitch together the full class
    code = format_dolfin_expression(classname=classname,
                                    shape=shape,
                                    eval_body=eval_body,
                                    **member_names)
    return code, classname

def format_uflacs_header(prefix, file_code):
    """Wrap code in a uflacs header template.

    *Arguments*

        prefix

            String with prefix for naming.

        file_code

            Header contents to wrap.

    *Returns*

        Full contents of header file with include guards etc.
    """
    # Includes we're likely to need, no check for when they're not needed
    includes = ['#include <iostream>',
                '#include <cmath>',
                '#include <boost/shared_ptr.h>',
                '#include <dolfin.h>']

    # File guards
    define = 'UFLACS_' + prefix + '_INCLUDED'
    preguard = [('#ifndef ', define),
                ('#define ', define)]
    postguard = '#endif'

    # Stitch it together
    code = [preguard, '',
            includes, '',
            Namespace(prefix, file_code), '',
            postguard]
    return format_code(code)

def compile_dolfin_expressions_header(expressions, object_names, prefix):
    """Generate code for a dolfin Expression from a UFL Expr.

    *Arguments*

        expressions

            A list of UFL expressions to compile.

        object_names

            A dictionary with object id:name mapping.

        prefix

            String with prefix for naming classes.

    *Returns*

        Full contents of header file with compiled expressions.
    """
    parameters = default_parameters() # FIXME: Get as input

    # Generate code for each expression
    file_code = []
    classnames = []
    for k, expr in enumerate(expressions):
        name = object_names.get(id(expr), 'e%d' % k)
        code, classname = compile_dolfin_expression_class(expr, name, parameters, object_names)
        file_code.append(code)
        classnames.append(classname)

    # Wrap code from each file in its own namespace
    return format_uflacs_header(prefix, file_code)