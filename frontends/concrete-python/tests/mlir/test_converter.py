"""
Tests of `Converter` class.
"""

import numpy as np
import pytest

from concrete import fhe
from concrete.fhe.mlir import GraphConverter


def assign(x, y):
    """
    Assign scalar `y` into vector `x`.
    """

    x[0] = y
    return x


@pytest.mark.parametrize(
    "function,encryption_statuses,inputset,expected_error,expected_message",
    [
        pytest.param(
            lambda x, y: x + y,
            {"x": "encrypted", "y": "encrypted"},
            [(0.0, 0), (7.0, 7), (0.0, 7), (7.0, 0)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                  # EncryptedScalar<float64>        ∈ [0.0, 7.0]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ only integers are supported
%1 = y                  # EncryptedScalar<uint3>          ∈ [0, 7]
%2 = add(%0, %1)        # EncryptedScalar<float64>        ∈ [0.0, 14.0]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ only integers are supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: fhe.conv(x, [[[3, 1, 0, 2]]]),
            {"x": "encrypted"},
            [np.ones(shape=(1, 1, 10), dtype=np.int64)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                                                                              # EncryptedTensor<uint1, shape=(1, 1, 10)>        ∈ [1, 1]
%1 = [[[3 1 0 2]]]                                                                  # ClearTensor<uint2, shape=(1, 1, 4)>             ∈ [0, 3]
%2 = conv1d(%0, %1, [0], pads=(0, 0), strides=(1,), dilations=(1,), group=1)        # EncryptedTensor<uint3, shape=(1, 1, 7)>         ∈ [6, 6]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 1-dimensional convolutions are not supported at the moment
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: fhe.conv(x, [[[[[1, 3], [4, 2]]]]]),
            {"x": "encrypted"},
            [np.ones(shape=(1, 1, 3, 4, 5), dtype=np.int64)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                                                                                                    # EncryptedTensor<uint1, shape=(1, 1, 3, 4, 5)>        ∈ [1, 1]
%1 = [[[[[1 3]    [4 2]]]]]                                                                               # ClearTensor<uint3, shape=(1, 1, 1, 2, 2)>            ∈ [1, 4]
%2 = conv3d(%0, %1, [0], pads=(0, 0, 0, 0, 0, 0), strides=(1, 1, 1), dilations=(1, 1, 1), group=1)        # EncryptedTensor<uint4, shape=(1, 1, 3, 3, 4)>        ∈ [10, 10]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 3-dimensional convolutions are not supported at the moment
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: fhe.maxpool(x, kernel_shape=(3,)),
            {"x": "encrypted"},
            [np.ones(shape=(1, 1, 10), dtype=np.int64)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                                                                                                   # EncryptedTensor<uint1, shape=(1, 1, 10)>        ∈ [1, 1]
%1 = maxpool1d(%0, kernel_shape=(3,), strides=(1,), pads=(0, 0), dilations=(1,), ceil_mode=False)        # EncryptedTensor<uint1, shape=(1, 1, 8)>         ∈ [1, 1]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 1-dimensional maxpooling is not supported at the moment
return %1

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: fhe.maxpool(x, kernel_shape=(3, 1, 2)),
            {"x": "encrypted"},
            [np.ones(shape=(1, 1, 3, 4, 5), dtype=np.int64)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                                                                                                                              # EncryptedTensor<uint1, shape=(1, 1, 3, 4, 5)>        ∈ [1, 1]
%1 = maxpool3d(%0, kernel_shape=(3, 1, 2), strides=(1, 1, 1), pads=(0, 0, 0, 0, 0, 0), dilations=(1, 1, 1), ceil_mode=False)        # EncryptedTensor<uint1, shape=(1, 1, 1, 4, 4)>        ∈ [1, 1]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 3-dimensional maxpooling is not supported at the moment
return %1

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: x + y,
            {"x": "clear", "y": "clear"},
            [(0, 0), (7, 7), (0, 7), (7, 0)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                  # ClearScalar<uint3>        ∈ [0, 7]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ lhs is clear
%1 = y                  # ClearScalar<uint3>        ∈ [0, 7]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ rhs is clear
%2 = add(%0, %1)        # ClearScalar<uint4>        ∈ [0, 14]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but clear-clear additions are not supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: x - y,
            {"x": "clear", "y": "clear"},
            [(0, 0), (7, 7), (0, 7), (7, 0)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                       # ClearScalar<uint3>        ∈ [0, 7]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ lhs is clear
%1 = y                       # ClearScalar<uint3>        ∈ [0, 7]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ rhs is clear
%2 = subtract(%0, %1)        # ClearScalar<int4>         ∈ [-7, 7]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but clear-clear subtractions are not supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: x * y,
            {"x": "clear", "y": "clear"},
            [(0, 0), (7, 7), (0, 7), (7, 0)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                       # ClearScalar<uint3>        ∈ [0, 7]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ lhs is clear
%1 = y                       # ClearScalar<uint3>        ∈ [0, 7]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ rhs is clear
%2 = multiply(%0, %1)        # ClearScalar<uint6>        ∈ [0, 49]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but clear-clear multiplications are not supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: np.dot(x, y),
            {"x": "clear", "y": "clear"},
            [([1, 2], [3, 4])],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                  # ClearTensor<uint2, shape=(2,)>        ∈ [1, 2]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ lhs is clear
%1 = y                  # ClearTensor<uint3, shape=(2,)>        ∈ [3, 4]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ rhs is clear
%2 = dot(%0, %1)        # ClearScalar<uint4>                    ∈ [11, 11]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but clear-clear dot products are not supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: np.broadcast_to(x, shape=(2, 2)),
            {"x": "clear"},
            [[1, 2], [3, 4]],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                                     # ClearTensor<uint3, shape=(2,)>          ∈ [1, 4]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ value is clear
%1 = broadcast_to(%0, shape=(2, 2))        # ClearTensor<uint3, shape=(2, 2)>        ∈ [1, 4]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but clear values cannot be broadcasted
return %1

            """,  # noqa: E501
        ),
        pytest.param(
            assign,
            {"x": "clear", "y": "encrypted"},
            [([1, 2, 3], 0)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                   # ClearTensor<uint2, shape=(3,)>        ∈ [0, 3]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ tensor is clear
%1 = y                   # EncryptedScalar<uint1>                ∈ [0, 0]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ assigned value is encrypted
%2 = (%0[0] = %1)        # ClearTensor<uint2, shape=(3,)>        ∈ [0, 3]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but encrypted values cannot be assigned to clear tensors
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: x**2 + (x + 1_000_000),
            {"x": "encrypted"},
            [100_000],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                    # EncryptedScalar<uint17>        ∈ [100000, 100000]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ this 34-bit value is used as an input to a table lookup
                                                                              (note that it's assigned 34-bits during compilation because of its relation with other operations)
%1 = 2                    # ClearScalar<uint2>             ∈ [2, 2]
%2 = power(%0, %1)        # EncryptedScalar<uint34>        ∈ [10000000000, 10000000000]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but only up to 16-bit table lookups are supported
%3 = 1000000              # ClearScalar<uint20>            ∈ [1000000, 1000000]
%4 = add(%0, %3)          # EncryptedScalar<uint21>        ∈ [1100000, 1100000]
%5 = add(%2, %4)          # EncryptedScalar<uint34>        ∈ [10001100000, 10001100000]
return %5

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: x & y,
            {"x": "encrypted", "y": "encrypted"},
            [(-2, 4)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                          # EncryptedScalar<int2>         ∈ [-2, -2]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ lhs is signed
%1 = y                          # EncryptedScalar<uint3>        ∈ [4, 4]
%2 = bitwise_and(%0, %1)        # EncryptedScalar<uint3>        ∈ [4, 4]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but only unsigned-unsigned bitwise operations are supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: x & y,
            {"x": "encrypted", "y": "encrypted"},
            [(4, -2)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                          # EncryptedScalar<uint3>        ∈ [4, 4]
%1 = y                          # EncryptedScalar<int2>         ∈ [-2, -2]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ rhs is signed
%2 = bitwise_and(%0, %1)        # EncryptedScalar<uint3>        ∈ [4, 4]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but only unsigned-unsigned bitwise operations are supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: np.concatenate((x, y)),
            {"x": "clear", "y": "clear"},
            [([1, 2], [3, 4])],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                            # ClearTensor<uint2, shape=(2,)>        ∈ [1, 2]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ value is clear
%1 = y                            # ClearTensor<uint3, shape=(2,)>        ∈ [3, 4]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ value is clear
%2 = concatenate((%0, %1))        # ClearTensor<uint3, shape=(4,)>        ∈ [1, 4]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but clear concatenation is not supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: fhe.conv(x, [[[[2, 1], [0, 3]]]]),
            {"x": "clear"},
            [np.ones(shape=(1, 1, 10, 10), dtype=np.int64)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                                                                                        # ClearTensor<uint1, shape=(1, 1, 10, 10)>          ∈ [1, 1]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ operand is clear
%1 = [[[[2 1]   [0 3]]]]                                                                      # ClearTensor<uint2, shape=(1, 1, 2, 2)>            ∈ [0, 3]
%2 = conv2d(%0, %1, [0], pads=(0, 0, 0, 0), strides=(1, 1), dilations=(1, 1), group=1)        # EncryptedTensor<uint3, shape=(1, 1, 9, 9)>        ∈ [6, 6]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but clear convolutions are not supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: fhe.conv(x, weight=y),
            {"x": "encrypted", "y": "encrypted"},
            [
                (
                    np.ones(shape=(1, 1, 10, 10), dtype=np.int64),
                    np.ones(shape=(1, 1, 2, 2), dtype=np.int64),
                )
            ],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                                                                                        # EncryptedTensor<uint1, shape=(1, 1, 10, 10)>        ∈ [1, 1]
%1 = y                                                                                        # EncryptedTensor<uint1, shape=(1, 1, 2, 2)>          ∈ [1, 1]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ weight is encrypted
%2 = conv2d(%0, %1, [0], pads=(0, 0, 0, 0), strides=(1, 1), dilations=(1, 1), group=1)        # EncryptedTensor<uint3, shape=(1, 1, 9, 9)>          ∈ [4, 4]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but convolutions with encrypted weights are not supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: fhe.conv(x, weight=[[[[2, 1], [0, 3]]]], bias=y),
            {"x": "encrypted", "y": "encrypted"},
            [
                (
                    np.ones(shape=(1, 1, 10, 10), dtype=np.int64),
                    np.ones(shape=(1,), dtype=np.int64),
                )
            ],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                                                                                       # EncryptedTensor<uint1, shape=(1, 1, 10, 10)>        ∈ [1, 1]
%1 = y                                                                                       # EncryptedTensor<uint1, shape=(1,)>                  ∈ [1, 1]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ bias is encrypted
%2 = [[[[2 1]   [0 3]]]]                                                                     # ClearTensor<uint2, shape=(1, 1, 2, 2)>              ∈ [0, 3]
%3 = conv2d(%0, %2, %1, pads=(0, 0, 0, 0), strides=(1, 1), dilations=(1, 1), group=1)        # EncryptedTensor<uint3, shape=(1, 1, 9, 9)>          ∈ [7, 7]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but convolutions with encrypted biases are not supported
return %3

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: np.dot(x, y),
            {"x": "encrypted", "y": "encrypted"},
            [
                (
                    np.ones(shape=(3,), dtype=np.int64),
                    np.ones(shape=(3,), dtype=np.int64),
                )
            ],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                  # EncryptedTensor<uint1, shape=(3,)>        ∈ [1, 1]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ lhs is encrypted
%1 = y                  # EncryptedTensor<uint1, shape=(3,)>        ∈ [1, 1]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ rhs is encrypted
%2 = dot(%0, %1)        # EncryptedScalar<uint2>                    ∈ [3, 3]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but encrypted-encrypted dot products are not supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: x @ y,
            {"x": "clear", "y": "clear"},
            [([[1, 2], [3, 4]], [[4, 3], [2, 1]])],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                     # ClearTensor<uint3, shape=(2, 2)>        ∈ [1, 4]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ lhs is clear
%1 = y                     # ClearTensor<uint3, shape=(2, 2)>        ∈ [1, 4]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ rhs is clear
%2 = matmul(%0, %1)        # ClearTensor<uint5, shape=(2, 2)>        ∈ [5, 20]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but clear-clear matrix multiplications are not supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: x @ y,
            {"x": "encrypted", "y": "encrypted"},
            [([[1, 2], [3, 4]], [[4, 3], [2, 1]])],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                     # EncryptedTensor<uint3, shape=(2, 2)>        ∈ [1, 4]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ lhs is encrypted
%1 = y                     # EncryptedTensor<uint3, shape=(2, 2)>        ∈ [1, 4]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ rhs is encrypted
%2 = matmul(%0, %1)        # EncryptedTensor<uint5, shape=(2, 2)>        ∈ [5, 20]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but encrypted-encrypted matrix multiplications are not supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: fhe.maxpool(x, kernel_shape=(3, 2)),
            {"x": "clear"},
            [np.ones(shape=(1, 1, 10, 5), dtype=np.int64)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                                                                                                               # ClearTensor<uint1, shape=(1, 1, 10, 5)>        ∈ [1, 1]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ operand is clear
%1 = maxpool2d(%0, kernel_shape=(3, 2), strides=(1, 1), pads=(0, 0, 0, 0), dilations=(1, 1), ceil_mode=False)        # ClearTensor<uint1, shape=(1, 1, 8, 4)>         ∈ [1, 1]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but clear maxpooling is not supported
return %1

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: x**2,
            {"x": "clear"},
            [3, 4, 5],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                    # ClearScalar<uint3>        ∈ [3, 5]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ this clear value is used as an input to a table lookup
%1 = 2                    # ClearScalar<uint2>        ∈ [2, 2]
%2 = power(%0, %1)        # ClearScalar<uint5>        ∈ [9, 25]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but only encrypted table lookups are supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: np.sum(x),
            {"x": "clear"},
            [[1, 2]],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x              # ClearTensor<uint2, shape=(2,)>        ∈ [1, 2]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ operand is clear
%1 = sum(%0)        # ClearScalar<uint2>                    ∈ [3, 3]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but clear summation is not supported
return %1

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: x << y,
            {"x": "encrypted", "y": "encrypted"},
            [(-2, 4)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                         # EncryptedScalar<int2>         ∈ [-2, -2]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ lhs is signed
%1 = y                         # EncryptedScalar<uint3>        ∈ [4, 4]
%2 = left_shift(%0, %1)        # EncryptedScalar<int6>         ∈ [-32, -32]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but only unsigned-unsigned bitwise shifts are supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x, y: x >> y,
            {"x": "encrypted", "y": "encrypted"},
            [(4, -2)],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                          # EncryptedScalar<uint3>        ∈ [4, 4]
%1 = y                          # EncryptedScalar<int2>         ∈ [-2, -2]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ rhs is signed
%2 = right_shift(%0, %1)        # EncryptedScalar<uint1>        ∈ [0, 0]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but only unsigned-unsigned bitwise shifts are supported
return %2

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: -x,
            {"x": "clear"},
            [10],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                   # ClearScalar<uint4>        ∈ [10, 10]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ operand is clear
%1 = negative(%0)        # ClearScalar<int5>         ∈ [-10, -10]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but clear negations are not supported
return %1

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: fhe.LookupTable([fhe.LookupTable([0, 1]), fhe.LookupTable([1, 0])])[x],
            {"x": "clear"},
            [[1, 1], [1, 0], [0, 1], [0, 0]],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                                     # ClearTensor<uint1, shape=(2,)>        ∈ [0, 1]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ this clear value is used as an input to a table lookup
%1 = tlu(%0, table=[[0, 1] [1, 0]])        # ClearTensor<uint1, shape=(2,)>        ∈ [0, 1]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but only encrypted table lookups are supported
return %1

            """,  # noqa: E501
        ),
        pytest.param(
            lambda x: fhe.round_bit_pattern(x, lsbs_to_remove=2),
            {"x": "clear"},
            [10, 20, 30],
            RuntimeError,
            """

Function you are trying to compile cannot be compiled

%0 = x                                              # ClearScalar<uint5>        ∈ [10, 30]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ operand is clear
%1 = round_bit_pattern(%0, lsbs_to_remove=2)        # ClearScalar<uint6>        ∈ [12, 32]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ but clear round bit pattern is not supported
%2 = identity(%1)                                   # ClearScalar<uint6>
return %2

            """,  # noqa: E501
        ),
    ],
)
def test_converter_bad_convert(
    function,
    encryption_statuses,
    inputset,
    expected_error,
    expected_message,
    helpers,
):
    """
    Test unsupported graph conversion.
    """

    configuration = helpers.configuration()
    compiler = fhe.Compiler(function, encryption_statuses)

    with pytest.raises(expected_error) as excinfo:
        compiler.compile(inputset, configuration)

    helpers.check_str(expected_message, str(excinfo.value))


@pytest.mark.parametrize(
    "function,parameters,expected_graph",
    [
        pytest.param(
            lambda x: (x**2) + 100,
            {
                "x": {"range": [0, 10], "status": "encrypted"},
            },
            """

%0 = x                    # EncryptedScalar<uint4>        ∈ [0, 10]
%1 = 2                    # ClearScalar<uint5>            ∈ [2, 2]
%2 = power(%0, %1)        # EncryptedScalar<uint8>        ∈ [0, 100]
%3 = 100                  # ClearScalar<uint9>            ∈ [100, 100]
%4 = add(%2, %3)          # EncryptedScalar<uint8>        ∈ [100, 200]
return %4

            """,
        )
    ],
)
def test_converter_process_multi_precision(function, parameters, expected_graph, helpers):
    """
    Test `process` method of `Converter` with multi precision.
    """

    parameter_encryption_statuses = helpers.generate_encryption_statuses(parameters)
    configuration = helpers.configuration().fork(single_precision=False)

    compiler = fhe.Compiler(function, parameter_encryption_statuses)

    inputset = helpers.generate_inputset(parameters)
    graph = compiler.trace(inputset, configuration)

    processed_graph = GraphConverter().process(graph, configuration)
    for node in processed_graph.query_nodes():
        if "original_bit_width" in node.properties:
            del node.properties["original_bit_width"]

    helpers.check_str(expected_graph, processed_graph.format())


@pytest.mark.parametrize(
    "function,parameters,expected_graph",
    [
        pytest.param(
            lambda x: (x**2) + 100,
            {
                "x": {"range": [0, 10], "status": "encrypted"},
            },
            """

%0 = x                    # EncryptedScalar<uint8>        ∈ [0, 10]
%1 = 2                    # ClearScalar<uint9>            ∈ [2, 2]
%2 = power(%0, %1)        # EncryptedScalar<uint8>        ∈ [0, 100]
%3 = 100                  # ClearScalar<uint9>            ∈ [100, 100]
%4 = add(%2, %3)          # EncryptedScalar<uint8>        ∈ [100, 200]
return %4

            """,
        )
    ],
)
def test_converter_process_single_precision(function, parameters, expected_graph, helpers):
    """
    Test `process` method of `Converter` with single precision.
    """

    parameter_encryption_statuses = helpers.generate_encryption_statuses(parameters)
    configuration = helpers.configuration().fork(single_precision=True)

    compiler = fhe.Compiler(function, parameter_encryption_statuses)

    inputset = helpers.generate_inputset(parameters)
    graph = compiler.trace(inputset, configuration)

    processed_graph = GraphConverter().process(graph, configuration)
    for node in processed_graph.query_nodes():
        if "original_bit_width" in node.properties:
            del node.properties["original_bit_width"]

    helpers.check_str(expected_graph, processed_graph.format())
