
from uflacs.utils.log import info, warning, error
from uflacs.utils.assertions import uflacs_assert

import ufl
from ufl.algorithms.transformations import Transformer

from uflacs.codeutils.precedence import build_precedence_map

class CodeFormatter(Transformer):
    """Language independent formatting class containing rules for
    handling indexing operators such that value and derivative
    indices are propagated to terminal handlers to be implemented
    for a particular language and target."""

    def __init__(self, language_formatter, variables):
        super(CodeFormatter, self).__init__()
        self.language_formatter = language_formatter
        self.variables = variables
        self.precedence = build_precedence_map()
        self.max_precedence = max(self.precedence.itervalues())

    def expr(self, o):
        v = self.variables.get(o)
        if v is not None:
            return v

        # Visit children and wrap in () if necessary.
        # This could be improved by considering the
        # parsing order to avoid some (), but that
        # may be language dependent? (usually left-right).
        # Keeping it simple and safe for now at least.
        ops = []
        for op in o.operands():
            opc = self.visit(op)
            # Skip () around variables
            if not op in self.variables:
                po = self.precedence[o._uflclass]
                pop = self.precedence[op._uflclass]
                # Ignore left-right rule and just add slightly more () than strictly necessary
                if po < self.max_precedence and pop <= po:
                    opc = '(' + opc + ')'
            ops.append(opc)

        #ops = [self.visit(op) for op in o.operands()]
        #ops = [("(%s)" % op) for op in ops]

        return self.language_formatter(o, *ops)

    def terminal(self, o):
        v = self.variables.get(o)
        if v is not None:
            return v

        return self.language_formatter(o)

    def multi_index(self, o):
        "Expecting expand_indices to have been applied, so all indices are fixed."
        return tuple(map(int, o))

    def spatial_derivative(self, o):
        return self.spatial_derivative_component(o, ())

    def spatial_derivative_component(self, o, component):
        """Gets derivative indices and passes on control to
        either indexed or target specific terminal handler."""

        # TODO: Test variables/component/derivatives combos more!
        if 0 and self.variables:
            print ""
            print "spatial_derivative_component:"
            print self.variables
            print
            print repr(o)
            print
            print repr(self.variables.get(o))
            print
        # Use eventual given variable
        v = self.variables.get(o)
        if v is not None:
            return v

        # Note that we do not want to look for a variable for f,
        # since o represents the value of the derivative of f, not f itself.

        # o is f.dx(di)
        f, di = o.operands()

        # Sorting derivative indices, can do this because the derivatives commute
        derivatives = sorted(self.multi_index(di))

        if isinstance(f, ufl.classes.Terminal):
            # o is the derivative of a terminal expression f
            expr = f
        elif isinstance(f, ufl.classes.Indexed):
            # Since expand_indices moves Indexed in to the terminals,
            # SpatialDerivative can be outside an Indexed:
            # o is A[ci].dx(di)
            A, ci = f.operands()
            component = self.multi_index(ci)
            expr = A
        else:
            error("Invalid type %s in spatial_derivate formatter, "\
                  "have you applied expand_derivatives?" % type(o))

        # Ask the formatter to make the string
        return self.language_formatter(expr, component, derivatives)

    def indexed(self, o):
        """Gets value indices and passes on control to either
        spatial_derivative or a target specific terminal formatter."""

        # TODO: Test variables/component/derivatives combos more!
        if 0 and self.variables:
            print
            print "indexed:"
            print self.variables
            print
            print repr(o)
            print
            print repr(self.variables.get(o))
            print

        # Use eventual given variable
        v = self.variables.get(o)
        if v is not None:
            return v

        # Note that we do not want to look for a variable for
        # A, but rather for the specific component of A.
        # By only using scalar variables we keep the variables construct simple.

        # o is A[ci]
        A, ci = o.operands()
        component = self.multi_index(ci)

        if isinstance(A, ufl.classes.Terminal):
            # o is the component of a terminal A
            # Ask the formatter to make the string
            return self.language_formatter(A, component)
        elif isinstance(A, ufl.classes.SpatialDerivative):
            # A is f.dx(...)  <->  o is f.dx(...)[ci]
            # Pass on control to derivative evaluation
            return self.spatial_derivative_component(A, component)
        else:
            error("Invalid type %s in indexed formatter, "\
                  "have you applied expand_derivatives?" % type(A))