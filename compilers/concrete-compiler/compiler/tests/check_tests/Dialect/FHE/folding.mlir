// RUN: concretecompiler --action=dump-fhe %s 2>&1| FileCheck %s

// CHECK-LABEL: func.func @add_eint_int(%arg0: !FHE.eint<2>) -> !FHE.eint<2>
func.func @add_eint_int(%arg0: !FHE.eint<2>) -> !FHE.eint<2> {
  // CHECK-NEXT: return %arg0 : !FHE.eint<2>

  %0 = arith.constant 0 : i3
  %1 = "FHE.add_eint_int"(%arg0, %0): (!FHE.eint<2>, i3) -> (!FHE.eint<2>)
  return %1: !FHE.eint<2>
}

// CHECK-LABEL: func.func @sub_eint_int(%arg0: !FHE.eint<2>) -> !FHE.eint<2>
func.func @sub_eint_int(%arg0: !FHE.eint<2>) -> !FHE.eint<2> {
  // CHECK-NEXT: return %arg0 : !FHE.eint<2>

  %0 = arith.constant 0 : i3
  %1 = "FHE.sub_eint_int"(%arg0, %0): (!FHE.eint<2>, i3) -> (!FHE.eint<2>)
  return %1: !FHE.eint<2>
}

// CHECK-LABEL: func.func @mul_eint_int(%arg0: !FHE.eint<2>) -> !FHE.eint<2>
func.func @mul_eint_int(%arg0: !FHE.eint<2>) -> !FHE.eint<2> {
  // CHECK-NEXT: return %arg0 : !FHE.eint<2>

  %0 = arith.constant 1 : i3
  %1 = "FHE.mul_eint_int"(%arg0, %0): (!FHE.eint<2>, i3) -> (!FHE.eint<2>)
  return %1: !FHE.eint<2>
}
