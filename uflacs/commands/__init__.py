"Collecting all commands here for automatic inclusion in cmdline utils."

from uflacs.commands.load     import add_load_options,     run_load

from uflacs.commands.printing import add_str_options,      run_str
from uflacs.commands.printing import add_repr_options,     run_repr
from uflacs.commands.printing import add_tree_options,     run_tree

from uflacs.commands.graphviz import add_graphviz_options, run_graphviz
from uflacs.commands.latex    import add_latex_options,    run_latex

from uflacs.commands.analyse  import add_analyse_options,  run_analyse

from uflacs.commands.compile_toy     import add_compile_toy_options,   run_compile_toy
from uflacs.commands.compile_dolfin  import add_compile_dolfin_options, run_compile_dolfin

from uflacs.commands.debug import add_debug_options, run_debug

from uflacs.commands.shared import get_version, add_default_options, add_skipping_options