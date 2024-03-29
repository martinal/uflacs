"""
This file contains code for setting up C++ unit tests with gtest from within Python tests using py.test.
"""

import pytest
import os
import inspect
from collections import defaultdict

from instant.output import get_status_output


# TODO: For a generic framework, this needs to change somewhat:
_supportcode = '''
#include <ufc.h>
#include <ufc_geometry.h>
#include "mock_cells.h"
//#include "debugging.h"
'''


_gtest_runner_template = """
#include <gtest/gtest.h>

{supportcode}

{testincludes}

int main(int argc, char **argv)
{{
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}}
"""

_gtest_template = """
/** Autogenerated from Python test
    {pytestname}
    at
    {pyfilename}:{pylineno}
*/
TEST ({suite}, {case})
{{
{body}
}}
"""

def find_parent_test_function():
    """Return (filename, lineno, functionname) of the
    first function named "test_*" found on the stack."""

    # Get current frame
    frame = inspect.currentframe()
    info = inspect.getframeinfo(frame)

    # Jump back frames until we're in a 'test_*' function
    while not info[2].startswith("test_"):
        frame = frame.f_back
        info = inspect.getframeinfo(frame)

    # Get info from frame
    filename = info[0]
    lineno = info[1]
    function = info[2]
    #context = info[3]
    #contextindex = info[4]

    assert len(info) == 5
    assert function.startswith("test_")

    return filename, lineno, function

class GTestContext:
    _all = []

    def __init__(self, config):
        self._basedir = os.path.split(__file__)[0]
        self._gendir = os.path.join(self._basedir, "generated")
        self._binary_filename = os.path.join(self._basedir, "run_gtest")
        self._gtest_log = os.path.join(self._basedir, "gtest.log")
        self._code = defaultdict(list)
        self._dirlist = []
        GTestContext._all.append(self)

    def info(self, msg):
        pre = "In gtest generation:"
        if '\n' in msg:
            print(pre)
            print(msg)
        else:
            print(pre, msg)

    def pushdir(self):
        self._dirlist.append(os.path.abspath(os.curdir))
        os.chdir(self._basedir)

    def popdir(self):
        os.chdir(self._dirlist.pop())

    def add(self, body):
        # Look through stack to find frame with test_... function name
        filename, lineno, function = find_parent_test_function()

        # Using function testcase class name as suite and function name as case
        basename = os.path.basename(filename)
        suite = basename.replace(".py", "")
        case = function

        # Use a header filename matching the python filename
        hfilename = os.path.join(self._gendir, basename.replace(".py", ".h"))

        # Get python filename relative to test directory
        pyfilename = os.path.relpath(filename, self._basedir)

        # Format as a test in target framework and store
        code = _gtest_template.format(pyfilename=pyfilename,
                                      pylineno=lineno,
                                      pytestname=function,
                                      suite=suite,
                                      case=case,
                                      body=body)
        self._code[hfilename].append(code)

    def write(self):
        # Make sure we have the directory for generated code
        if not os.path.isdir(self._gendir):
            os.mkdir(self._gendir)

        # Write test code collected during py.test run to files
        headers = []
        header_basenames = []
        for hfilename in sorted(self._code):
            tests = self._code[hfilename]
            code = '\n'.join(tests)
            with open(hfilename, "w") as f:
                f.write(code)
                headers.append(hfilename)

        # Collect headers in include list for runner code
        self._test_header_names = [os.path.split(h)[-1] for h in headers]
        testincludes = '\n'.join('#include "{0}"'.format(h) for h in self._test_header_names)

        # Write test runner code to file
        runner_code = _gtest_runner_template.format(supportcode=_supportcode, testincludes=testincludes)

        self._main_filename = os.path.join(self._gendir, "main.cpp")
        with open(self._main_filename, "w") as f:
            f.write(runner_code)

    def build(self):
        s, o = get_status_output("make")
        if s:
            self.info("Building '{0}' FAILED (code {1}, headers: {2})".format(self._binary_filename,
                                                                              s, self._test_header_names))
            self.info("Build output:")
            self.info(o)
        else:
            self.info("Building ok.")

    def run(self):
        s, o = get_status_output(self._binary_filename)
        if s:
            self.info("Gtest running FAILED with code {0}!".format(s))
        else:
            self.info("Gtest running ok!")
        with open(self._gtest_log, "w") as f:
            f.write(o)
        self.info(o)

    def finalize(self):
        # Write generated test code to files, build and run, all from within a stable basedir
        self.pushdir()
        try:
            self.write()
            self.build()
            self.run()
        finally:
            self.popdir()

#@pytest.fixture("module")
@pytest.fixture("session")
def gtest():
    "create initial files for gtest generation"
    config = None
    gtc = GTestContext(config)
    return gtc

def gtest_sessionfinish(session):
    session.trace("finalizing gtest contexts")
    while GTestContext._all:
        gtc = GTestContext._all.pop()
        gtc.finalize()
    session.trace("done finalizing gtest contexts")

def pytest_sessionfinish(session):
    gtest_sessionfinish(session)
