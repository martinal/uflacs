#!/usr/bin/env python

"""
Tests of C++ formatting rules.
"""

# These are thin wrappers on top of unittest.TestCase and unittest.main
from ufltestcase import UflTestCase, main

import ufl

def format_expression_as_test_cpp(expr, variables=None):
    "This is a test specific function for formatting ufl to C++."
    from ufl.algorithms import preprocess_expression
    from uflacs.codeutils.code_formatter import CodeFormatter
    from uflacs.codeutils.cpp_format import CppFormatterRules, CppDefaultFormatter

    # Preprocessing expression before applying formatting.
    # In a compiler, one should probably assume that these
    # have been applied and use CodeFormatter directly.
    expr_data = preprocess_expression(expr)

    # This formatter is a multifunction implementing target
    # specific formatting rules, here using default formatting rules.
    target_formatter = CppDefaultFormatter()

    # This formatter is a multifunction with single operator
    # formatting rules for generic C++ formatting
    cpp_formatter = CppFormatterRules(target_formatter)

    # This final formatter implements a generic framework handling indices etc etc.
    variables = variables or {}
    code_formatter = CodeFormatter(cpp_formatter, variables)
    code = code_formatter.visit(expr_data.preprocessed_expr)
    return code

class CppFormatterTest(UflTestCase):

    def assertCppEqual(self, expr, code, variables=None):
        r = format_expression_as_test_cpp(expr, variables)
        self.assertEqual(code, r)

    def test_cpp_formatting_of_literals(self):
        # Test literals
        self.assertCppEqual(ufl.as_ufl(2), "2")
        self.assertCppEqual(ufl.as_ufl(3.14), '3.14')
        self.assertCppEqual(ufl.as_ufl(0), "0")
        # These are actually converted to int before formatting:
        self.assertCppEqual(ufl.Identity(2)[0,0], "1")
        self.assertCppEqual(ufl.Identity(2)[0,1], "0")
        self.assertCppEqual(ufl.Identity(2)[1,0], "0")
        self.assertCppEqual(ufl.Identity(2)[1,1], "1")
        self.assertCppEqual(ufl.PermutationSymbol(3)[1,2,3], "1")
        self.assertCppEqual(ufl.PermutationSymbol(3)[2,1,3], "-1")
        self.assertCppEqual(ufl.PermutationSymbol(3)[1,1,3], "0")

    def test_cpp_formatting_of_geometry(self):
        # Test geometry quantities (faked for testing!)
        x = ufl.cell1D.x
        self.assertCppEqual(x, "x[0]")
        x, y = ufl.cell2D.x
        self.assertCppEqual(x, "x[0]")
        self.assertCppEqual(y, "x[1]")
        nx, ny = ufl.cell2D.n
        self.assertCppEqual(nx, "n[0]")
        self.assertCppEqual(ny, "n[1]")
        Kv = ufl.cell2D.volume
        self.assertCppEqual(Kv, "K_vol")
        Kr = ufl.cell2D.circumradius
        self.assertCppEqual(Kr, "K_rad")

    def test_cpp_formatting_of_form_arguments(self):
        # Test form arguments (faked for testing!)
        V = ufl.FiniteElement("CG", ufl.cell2D, 1)
        f = ufl.Coefficient(V).reconstruct(count=0)
        self.assertCppEqual(f, "w0")
        v = ufl.Argument(V).reconstruct(count=0)
        self.assertCppEqual(v, "v0")

        V = ufl.VectorElement("CG", ufl.cell2D, 1)
        f = ufl.Coefficient(V).reconstruct(count=1)
        self.assertCppEqual(f[0], "w0[0]") # Renumbered to 0...
        v = ufl.Argument(V).reconstruct(count=3)
        self.assertCppEqual(v[1], "v0[1]") # Renumbered to 0...

        V = ufl.TensorElement("CG", ufl.cell2D, 1)
        f = ufl.Coefficient(V).reconstruct(count=2)
        self.assertCppEqual(f[1,0], "w0[1][0]") # Renumbered to 0...
        v = ufl.Argument(V).reconstruct(count=3)
        self.assertCppEqual(v[0,1], "v0[0][1]") # Renumbered to 0...

        # TODO: Test mixed functions
        # TODO: Test tensor functions with symmetries

    def test_cpp_formatting_of_arithmetic(self):
        x, y = ufl.triangle.x
        # Test basic arithmetic operators
        self.assertCppEqual(x + 3, "3 + x[0]")
        self.assertCppEqual(x * 2, "2 * x[0]")
        self.assertCppEqual(x / 2, "x[0] / 2")
        self.assertCppEqual(x*x, "std::pow(x[0], 2)") # TODO: Will gcc optimize this to x*x for us?
        self.assertCppEqual(x**3, "std::pow(x[0], 3)")
        # TODO: Test all basic operators

    def test_cpp_formatting_of_cmath(self):
        x, y = ufl.triangle.x
        # Test cmath functions
        self.assertCppEqual(ufl.exp(x), "std::exp(x[0])")
        self.assertCppEqual(ufl.ln(x), "std::log(x[0])")
        self.assertCppEqual(ufl.sqrt(x), "std::sqrt(x[0])")
        self.assertCppEqual(abs(x), "std::abs(x[0])")
        self.assertCppEqual(ufl.sin(x), "std::sin(x[0])")
        self.assertCppEqual(ufl.cos(x), "std::cos(x[0])")
        self.assertCppEqual(ufl.tan(x), "std::tan(x[0])")
        self.assertCppEqual(ufl.asin(x), "std::asin(x[0])")
        self.assertCppEqual(ufl.acos(x), "std::acos(x[0])")
        self.assertCppEqual(ufl.atan(x), "std::atan(x[0])")

    def test_cpp_formatting_of_derivatives(self):
        x, y = ufl.triangle.x
        # Test derivatives of basic operators
        self.assertCppEqual(ufl.Identity(2)[0,0].dx(0), "0")
        self.assertCppEqual(x.dx(0), "1")
        self.assertCppEqual(x.dx(1), "0")
        self.assertCppEqual(ufl.sin(x).dx(0), "std::cos(x[0])")

        # Test derivatives of target specific test fakes
        V = ufl.FiniteElement("CG", ufl.cell2D, 1)
        f = ufl.Coefficient(V).reconstruct(count=0)
        self.assertCppEqual(f.dx(0), "d1_w0[0]")
        v = ufl.Argument(V).reconstruct(count=3)
        self.assertCppEqual(v.dx(1), "d1_v0[1]") # Renumbered to 0...
        # TODO: Test more derivatives
        # TODO: Test variable derivatives using diff

    def test_cpp_formatting_of_conditionals(self):
        x, y = ufl.triangle.x
        # Test conditional expressions
        self.assertCppEqual(ufl.conditional(ufl.lt(x, 2), y, 3),
                    "x[0] < 2 ? x[1]: 3")
        self.assertCppEqual(ufl.conditional(ufl.gt(x, 2), 4+y, 3),
                    "x[0] > 2 ? 4 + x[1]: 3")
        self.assertCppEqual(ufl.conditional(ufl.And(ufl.le(x, 2), ufl.ge(y, 4)), 7, 8),
                    "x[0] <= 2 && x[1] >= 4 ? 7: 8")
        self.assertCppEqual(ufl.conditional(ufl.Or(ufl.eq(x, 2), ufl.ne(y, 4)), 7, 8),
                    "x[0] == 2 || x[1] != 4 ? 7: 8")
        # TODO: Some tests of nested conditionals with correct precedences?

    def test_cpp_formatting_precedence_handling(self):
        x, y = ufl.triangle.x
        # Test precedence handling with sums
        # Note that the automatic sorting is reflected in formatting!
        self.assertCppEqual(y + (2 + x), "x[1] + (2 + x[0])")
        self.assertCppEqual((x + 2) + y, "x[1] + (2 + x[0])")

        self.assertCppEqual((2 + x) + (3 + y), "(2 + x[0]) + (3 + x[1])")

        self.assertCppEqual((x + 3) + 2 + y, "x[1] + (2 + (3 + x[0]))")
        self.assertCppEqual(2 + (x + 3) + y, "x[1] + (2 + (3 + x[0]))")
        self.assertCppEqual(2 + (3 + x) + y, "x[1] + (2 + (3 + x[0]))")
        self.assertCppEqual(y + (2 + (3 + x)), "x[1] + (2 + (3 + x[0]))")

        self.assertCppEqual(2 + x + 3 + y, "x[1] + (3 + (2 + x[0]))")
        self.assertCppEqual(2 + x + 3 + y, "x[1] + (3 + (2 + x[0]))")

        # Test precedence handling with divisions
        # This is more stable than sums since there is no sorting.
        self.assertCppEqual((x / 2) / 3, "(x[0] / 2) / 3")
        self.assertCppEqual(x / (y / 3), "x[0] / (x[1] / 3)")
        self.assertCppEqual((x / 2) / (y / 3), "(x[0] / 2) / (x[1] / 3)")
        self.assertCppEqual(x / (2 / y) / 3, "(x[0] / (2 / x[1])) / 3")

        # Test precedence handling with highest level types
        self.assertCppEqual(ufl.sin(x), "std::sin(x[0])")
        self.assertCppEqual(ufl.cos(x+2), "std::cos(2 + x[0])")
        self.assertCppEqual(ufl.tan(x/2), "std::tan(x[0] / 2)")
        self.assertCppEqual(ufl.acos(x + 3 * y), "std::acos(x[0] + 3 * x[1])")
        self.assertCppEqual(ufl.asin(ufl.atan(x**4)), "std::asin(std::atan(std::pow(x[0], 4)))")
        self.assertCppEqual(ufl.sin(y) + ufl.tan(x), "std::sin(x[1]) + std::tan(x[0])")

        # Test precedence handling with mixed types
        self.assertCppEqual(3 * (2 + x), "3 * (2 + x[0])")
        self.assertCppEqual((2 * x) + (3 * y), "2 * x[0] + 3 * x[1]")
        self.assertCppEqual(2 * (x + 3) * y, "x[1] * (2 * (3 + x[0]))")
        self.assertCppEqual(2 * (x + 3)**4 * y, "x[1] * (2 * std::pow(3 + x[0], 4))")
        # TODO: More tests covering all types and more combinations!

    def test_cpp_formatting_with_variables(self):
        x, y = ufl.triangle.x
        # Test user-provided C variables for subexpressions
        # we can use variables for x[0], and sum, and power
        self.assertCppEqual(x**2 + y**2, "x2 + y2", variables={x**2: 'x2', y**2: 'y2'})
        self.assertCppEqual(x**2 + y**2, "std::pow(z, 2) + y2", variables={x: 'z', y**2: 'y2'})
        self.assertCppEqual(x**2 + y**2, "q", variables={x**2 + y**2: 'q'})
        # we can use variables in conditionals
        self.assertCppEqual(ufl.conditional(ufl.Or(ufl.eq(x, 2), ufl.ne(y, 4)), 7, 8),
                    "c1 || c2 ? 7: 8",
                    variables={ufl.eq(x, 2): 'c1', ufl.ne(y, 4): 'c2'})
        # we can replace coefficients (formatted by user provided code)
        V = ufl.FiniteElement("CG", ufl.cell2D, 1)
        f = ufl.Coefficient(V).reconstruct(count=0)
        self.assertCppEqual(f, "f", variables={f: 'f'})
        self.assertCppEqual(f**3, "std::pow(f, 3)", variables={f: 'f'})
        # variables do not replace derivatives of variable expressions
        self.assertCppEqual(f.dx(0), "d1_w0[0]", variables={f: 'f'})
        # variables do replace variable expressions that are themselves derivatives
        self.assertCppEqual(f.dx(0), "df", variables={f.dx(0): 'df'})

        # TODO: Test variables in more situations with indices and derivatives

    # TODO: Test various compound operators


if __name__ == "__main__":
    main()