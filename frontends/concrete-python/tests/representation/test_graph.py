"""
Tests of `Graph` class.
"""

import os
import re

import numpy as np
import pytest

import tests
from concrete import fhe

tests_directory = os.path.dirname(tests.__file__)


def g(z):
    """
    Example function with a tag.
    """

    with fhe.tag("def"):
        a = 120 - z
        b = a // 4
    return b


def f(x):
    """
    Example function with nested tags.
    """

    with fhe.tag("abc"):
        x = x * 2
        with fhe.tag("foo"):
            y = x + 42
        z = np.sqrt(y).astype(np.int64)

    return g(z + 3) * 2


def test_graph_format_show_lines(helpers):
    """
    Test `format` method of `Graph` class with show_lines=True.
    """

    configuration = helpers.configuration()

    compiler = fhe.Compiler(f, {"x": "encrypted"})
    graph = compiler.trace(range(10), configuration)

    # pylint: disable=line-too-long
    expected = f"""

 %0 = x                            # EncryptedScalar<uint4>        ∈ [0, 9]                             {tests_directory}/representation/test_graph.py:50
 %1 = 2                            # ClearScalar<uint2>            ∈ [2, 2]            @ abc            {tests_directory}/representation/test_graph.py:34
 %2 = multiply(%0, %1)             # EncryptedScalar<uint5>        ∈ [0, 18]           @ abc            {tests_directory}/representation/test_graph.py:34
 %3 = 42                           # ClearScalar<uint6>            ∈ [42, 42]          @ abc.foo        {tests_directory}/representation/test_graph.py:36
 %4 = add(%2, %3)                  # EncryptedScalar<uint6>        ∈ [42, 60]          @ abc.foo        {tests_directory}/representation/test_graph.py:36
 %5 = subgraph(%4)                 # EncryptedScalar<uint3>        ∈ [6, 7]            @ abc            {tests_directory}/representation/test_graph.py:37
 %6 = 3                            # ClearScalar<uint2>            ∈ [3, 3]                             {tests_directory}/representation/test_graph.py:39
 %7 = add(%5, %6)                  # EncryptedScalar<uint4>        ∈ [9, 10]                            {tests_directory}/representation/test_graph.py:39
 %8 = 120                          # ClearScalar<uint7>            ∈ [120, 120]        @ def            {tests_directory}/representation/test_graph.py:23
 %9 = subtract(%8, %7)             # EncryptedScalar<uint7>        ∈ [110, 111]        @ def            {tests_directory}/representation/test_graph.py:23
%10 = 4                            # ClearScalar<uint3>            ∈ [4, 4]            @ def            {tests_directory}/representation/test_graph.py:24
%11 = floor_divide(%9, %10)        # EncryptedScalar<uint5>        ∈ [27, 27]          @ def            {tests_directory}/representation/test_graph.py:24
%12 = 2                            # ClearScalar<uint2>            ∈ [2, 2]                             {tests_directory}/representation/test_graph.py:39
%13 = multiply(%11, %12)           # EncryptedScalar<uint6>        ∈ [54, 54]                           {tests_directory}/representation/test_graph.py:39
return %13

Subgraphs:

    %5 = subgraph(%4):

        %0 = input                         # EncryptedScalar<uint2>          @ abc.foo        {tests_directory}/representation/test_graph.py:36
        %1 = sqrt(%0)                      # EncryptedScalar<float64>        @ abc            {tests_directory}/representation/test_graph.py:37
        %2 = astype(%1, dtype=int_)        # EncryptedScalar<uint1>          @ abc            {tests_directory}/representation/test_graph.py:37
        return %2

    """  # noqa: E501
    # pylint: enable=line-too-long

    actual = graph.format(show_locations=True)

    assert (
        actual.strip() == expected.strip()
    ), f"""

Expected Output
===============
{expected}

Actual Output
=============
{actual}

            """


@pytest.mark.parametrize(
    "function,inputset,tag_filter,operation_filter,expected_result",
    [
        pytest.param(
            lambda x: x + 1,
            range(5),
            None,
            None,
            3,
        ),
        pytest.param(
            lambda x: x + 42,
            range(10),
            None,
            None,
            6,
        ),
        pytest.param(
            lambda x: x + 42,
            range(50),
            None,
            None,
            7,
        ),
        pytest.param(
            lambda x: x + 1.2,
            [1.5, 4.2],
            None,
            None,
            -1,
        ),
        pytest.param(
            f,
            range(10),
            None,
            None,
            7,
        ),
        pytest.param(
            f,
            range(10),
            "",
            None,
            6,
        ),
        pytest.param(
            f,
            range(10),
            "abc",
            None,
            5,
        ),
        pytest.param(
            f,
            range(10),
            ["abc", "def"],
            None,
            7,
        ),
        pytest.param(
            f,
            range(10),
            re.compile(".*b.*"),
            None,
            6,
        ),
        pytest.param(
            f,
            range(10),
            None,
            "input",
            4,
        ),
        pytest.param(
            f,
            range(10),
            None,
            "constant",
            7,
        ),
        pytest.param(
            f,
            range(10),
            None,
            "subgraph",
            3,
        ),
        pytest.param(
            f,
            range(10),
            None,
            "add",
            6,
        ),
        pytest.param(
            f,
            range(10),
            None,
            ["subgraph", "add"],
            6,
        ),
        pytest.param(
            f,
            range(10),
            None,
            re.compile("sub.*"),
            7,
        ),
        pytest.param(
            f,
            range(10),
            "abc.foo",
            "add",
            6,
        ),
        pytest.param(
            f,
            range(10),
            "abc",
            "floor_divide",
            -1,
        ),
    ],
)
def test_graph_maximum_integer_bit_width(
    function,
    inputset,
    tag_filter,
    operation_filter,
    expected_result,
    helpers,
):
    """
    Test `maximum_integer_bit_width` method of `Graph` class.
    """

    configuration = helpers.configuration()

    compiler = fhe.Compiler(function, {"x": "encrypted"})
    graph = compiler.trace(inputset, configuration)

    assert graph.maximum_integer_bit_width(tag_filter, operation_filter) == expected_result


@pytest.mark.parametrize(
    "function,inputset,tag_filter,operation_filter,is_encrypted_filter,expected_result",
    [
        pytest.param(
            lambda x: x + 42,
            range(-10, 10),
            None,
            None,
            None,
            (-10, 51),
        ),
        pytest.param(
            lambda x: x + 1.2,
            [1.5, 4.2],
            None,
            None,
            None,
            None,
        ),
        pytest.param(
            f,
            range(10),
            None,
            None,
            None,
            (0, 120),
        ),
        pytest.param(
            f,
            range(10),
            "",
            None,
            None,
            (0, 54),
        ),
        pytest.param(
            f,
            range(10),
            "abc",
            None,
            None,
            (0, 18),
        ),
        pytest.param(
            f,
            range(10),
            ["abc", "def"],
            None,
            None,
            (0, 120),
        ),
        pytest.param(
            f,
            range(10),
            re.compile(".*b.*"),
            None,
            None,
            (0, 60),
        ),
        pytest.param(
            f,
            range(10),
            None,
            "input",
            None,
            (0, 9),
        ),
        pytest.param(
            f,
            range(10),
            None,
            "constant",
            None,
            (2, 120),
        ),
        pytest.param(
            f,
            range(10),
            None,
            "subgraph",
            None,
            (6, 7),
        ),
        pytest.param(
            f,
            range(10),
            None,
            "add",
            None,
            (9, 60),
        ),
        pytest.param(
            f,
            range(10),
            None,
            ["subgraph", "add"],
            None,
            (6, 60),
        ),
        pytest.param(
            f,
            range(10),
            None,
            re.compile("sub.*"),
            None,
            (6, 111),
        ),
        pytest.param(
            f,
            range(10),
            "abc.foo",
            "add",
            None,
            (42, 60),
        ),
        pytest.param(
            f,
            range(10),
            "abc",
            "floor_divide",
            None,
            None,
        ),
        pytest.param(
            lambda x: x - 2,
            range(5, 10),
            None,
            None,
            True,
            (3, 9),
        ),
        pytest.param(
            lambda x: x - 2,
            range(5, 10),
            None,
            None,
            False,
            (2, 2),
        ),
    ],
)
def test_graph_integer_range(
    function,
    inputset,
    tag_filter,
    operation_filter,
    is_encrypted_filter,
    expected_result,
    helpers,
):
    """
    Test `integer_range` method of `Graph` class.
    """

    configuration = helpers.configuration()

    compiler = fhe.Compiler(function, {"x": "encrypted"})
    graph = compiler.trace(inputset, configuration)

    assert graph.integer_range(tag_filter, operation_filter, is_encrypted_filter) == expected_result


def test_direct_graph_integer_range(helpers):
    """
    Test `integer_range` method of `Graph` class where `graph.is_direct` is `True`.
    """

    # pylint: disable=import-outside-toplevel
    from concrete.fhe.dtypes import Integer
    from concrete.fhe.values import Value

    # pylint: enable=import-outside-toplevel

    circuit = fhe.Compiler.assemble(
        lambda x: x,
        {"x": Value(dtype=Integer(is_signed=False, bit_width=8), shape=(), is_encrypted=True)},
        configuration=helpers.configuration(),
    )
    assert circuit.graph.integer_range() is None
