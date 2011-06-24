
import ufl

def build_precedence_list():
    "Builds a list of operator types by precedence order in the C language."
    # FIXME: Add all types we need here. Missing at least lifting and restriction.
    pl = []
    pl.append((ufl.classes.Conditional,))
    pl.append((ufl.classes.OrCondition,))
    pl.append((ufl.classes.AndCondition,))
    pl.append((ufl.classes.EQ, ufl.classes.NE))
    pl.append((ufl.classes.Condition,)) # <,>,<=,>=
    pl.append((ufl.classes.Sum,))
    pl.append((ufl.classes.Product, ufl.classes.Division,))
    # The highest precedence items will never need
    # parentheses around them or their operands
    pl.append((ufl.classes.Power, ufl.classes.MathFunction, ufl.classes.Abs,
               ufl.classes.Indexed, ufl.classes.SpatialDerivative,
               ufl.classes.Terminal))
    return pl

def build_precedence_map():
    from ufl.precedence import build_precedence_mapping
    pm, missing = build_precedence_mapping(build_precedence_list())
    if 0 and missing: # Enable to see which types we are missing
        print "Missing precedence levels for the types:"
        print "\n".join('  %s' % c for c in missing)
    return pm