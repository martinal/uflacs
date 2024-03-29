#!/usr/bin/env python
"""
Tests of manipulations of the ssa form of expressions.
"""

from __future__ import print_function

from six.moves import map
from ufl import *
from ufl import product
from ufl.permutation import compute_indices

from uflacs.analysis.graph import build_graph

# Tests need this but it has been removed. Rewrite tests!
#from uflacs.analysis.graph_rebuild import rebuild_scalar_e2i

#from uflacs.analysis.graph_rebuild import rebuild_expression_from_graph

#from uflacs.analysis.indexing import (map_indexed_arg_components,
#                                        map_indexed_arg_components2,
#                                        map_component_tensor_arg_components)
#from uflacs.analysis.graph_symbols import (map_list_tensor_symbols,
#                                             map_transposed_symbols, get_node_symbols)
#from uflacs.analysis.graph_dependencies import (compute_dependencies,
#                                                mark_active,
#                                                mark_image)
#from uflacs.analysis.graph_ssa import (mark_partitions,
#                                       compute_dependency_count,
#                                       invert_dependencies,
#                                       default_cache_score_policy,
#                                       compute_cache_scores,
#                                       allocate_registers)

def xtest_dependency_construction():
    cell = triangle
    d = cell.geometric_dimension()
    x = SpatialCoordinate(cell)
    n = FacetNormal(cell)

    U = FiniteElement("CG", cell, 1)
    V = VectorElement("CG", cell, 1)
    W = TensorElement("CG", cell, 1)
    u = Coefficient(U)
    v = Coefficient(V)
    w = Coefficient(W)

    i, j, k, l = indices(4)

    expressions = [as_ufl(1),
                   as_ufl(3.14),
                   as_ufl(0),
                   x[0],
                   n[0],
                   u,
                   v[0],
                   v[1],
                   w[0, 1],
                   w[0, 0]+w[1, 1],
                   (2*v+w[1,:])[i]*v[i],
                   ]

    for expr in expressions:
        G = build_graph([expr])
        ne2i, NV, W, terminals, nvs = rebuild_scalar_e2i(G)

        e2i = ne2i
        V = NV

        dependencies = compute_dependencies(e2i, V)

        max_symbol = len(V)
        targets = (max_symbol-1,)
        active, num_active = mark_active(max_symbol, dependencies, targets)

        partitions = mark_partitions(V, active, dependencies, {})

        depcount = compute_dependency_count(dependencies)

        inverse_dependencies = invert_dependencies(dependencies, depcount)

        scores = compute_cache_scores(V,
                                      active,
                                      dependencies,
                                      inverse_dependencies,
                                      partitions,
                                      cache_score_policy=default_cache_score_policy)

        max_registers = 4
        score_threshold = 1
        allocations = allocate_registers(active, partitions, targets,
                                         scores, max_registers, score_threshold)

        if 0:
            print()
            print("====== expr                \n", expr)
            print("====== V                   \n", '\n'.join(map(str, V)))
            print("====== dependencies        \n", dependencies)
            print("====== active              \n", active)
            print("====== partitions          \n", partitions)
            print("====== depcount            \n", depcount)
            print("====== inverse_dependencies\n", inverse_dependencies)
            print("====== scores              \n", scores)
            print("====== allocations         \n", allocations)
            print()
