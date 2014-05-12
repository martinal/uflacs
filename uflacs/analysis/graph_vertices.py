
from ufl.common import unique_post_traversal
from ufl.classes import (Terminal, UtilityType,
                         Grad, Restricted, Indexed)
from ufl.algorithms.traversal import traverse_terminals

from uflacs.utils.log import error
from uflacs.analysis.datastructures import (int_array, object_array,
                                              CRS, rows_to_crs, rows_dict_to_crs)
from uflacs.analysis.modified_terminals import is_modified_terminal

def count_nodes_with_unique_post_traversal(expr, e2i=None, skip_terminal_modifiers=False):
    """Yields o for each node o in expr, child before parent.
    Never visits a node twice."""
    if e2i is None:
        e2i = {}

    def getops(e):
        "Get a modifyable list of operands of e, optionally treating modified terminals as a unit."
        if isinstance(e, Terminal) or (skip_terminal_modifiers and is_modified_terminal(e)):
            return []
        else:
            return list(e.operands())

    stack = []
    stack.append((expr, getops(expr)))
    while stack:
        expr, ops = stack[-1]
        for i, o in enumerate(ops):
            if o is not None and o not in e2i:
                stack.append((o, getops(o)))
                ops[i] = None
                break
        else:
            if not isinstance(expr, UtilityType):
                count = len(e2i)
                e2i[expr] = count
            stack.pop()
    return e2i

def build_array_from_counts(e2i):
    nv = len(e2i)
    V = object_array(nv)
    for e,i in e2i.iteritems():
        V[i] = e
    return V

def build_node_counts(expressions):
    e2i = {}
    for expr in expressions:
        count_nodes_with_unique_post_traversal(expr, e2i, False)
    return e2i

def build_scalar_node_counts(expressions):
    # Count unique expression nodes across multiple expressions
    e2i = {}
    for expr in expressions:
        count_nodes_with_unique_post_traversal(expr, e2i, True)
    return e2i

def build_graph_vertices(expressions):
    # Count unique expression nodes
    e2i = build_node_counts(expressions)

    # Make a list of the nodes by their ordering
    V = build_array_from_counts(e2i)

    # Get vertex indices representing input expression roots
    ri = [e2i[expr] for expr in expressions]

    return e2i, V, ri

def build_scalar_graph_vertices(expressions):
    # Count unique expression nodes across multiple expressions, treating modified terminals as a unit
    e2i = build_scalar_node_counts(expressions)

    # Make a list of the nodes by their ordering
    V = build_array_from_counts(e2i)

    # Get vertex indices representing input expression roots
    ri = [e2i[expr] for expr in expressions]

    return e2i, V, ri