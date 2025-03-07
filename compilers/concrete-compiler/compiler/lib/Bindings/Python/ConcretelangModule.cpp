// Part of the Concrete Compiler Project, under the BSD3 License with Zama
// Exceptions. See
// https://github.com/zama-ai/concrete-compiler-internal/blob/main/LICENSE.txt
// for license information.

#include "concretelang-c/Dialect/FHE.h"
#include "concretelang-c/Dialect/FHELinalg.h"
#include "concretelang/Bindings/Python/CompilerAPIModule.h"
#include "concretelang/Bindings/Python/DialectModules.h"
#include "concretelang/Support/Constants.h"
#include "mlir-c/Bindings/Python/Interop.h"
#include "mlir-c/IR.h"
#include "mlir-c/RegisterEverything.h"
#include "mlir/Bindings/Python/PybindAdaptors.h"
#include "mlir/IR/DialectRegistry.h"

#include "llvm-c/ErrorHandling.h"
#include "llvm/Support/Signals.h"

#include <pybind11/pybind11.h>
namespace py = pybind11;

PYBIND11_MODULE(_concretelang, m) {
  m.doc() = "Concretelang Python Native Extension";
  llvm::sys::PrintStackTraceOnErrorSignal(/*argv=*/"");
  LLVMEnablePrettyStackTrace();

  m.def(
      "register_dialects",
      [](py::object capsule) {
        // Get the MlirContext capsule from PyMlirContext capsule.
        auto wrappedCapsule = capsule.attr(MLIR_PYTHON_CAPI_PTR_ATTR);
        const MlirContext context =
            mlirPythonCapsuleToContext(wrappedCapsule.ptr());

        const MlirDialectRegistry registry = mlirDialectRegistryCreate();
        mlirRegisterAllDialects(registry);
        mlirContextAppendDialectRegistry(context, registry);

        const MlirDialectHandle fhe = mlirGetDialectHandle__fhe__();
        mlirDialectHandleRegisterDialect(fhe, context);

        const MlirDialectHandle fhelinalg = mlirGetDialectHandle__fhelinalg__();
        mlirDialectHandleRegisterDialect(fhelinalg, context);

        mlirContextLoadAllAvailableDialects(context);
      },
      "Register Concretelang dialects on a PyMlirContext.");

  py::module fhe = m.def_submodule("_fhe", "FHE API");
  mlir::concretelang::python::populateDialectFHESubmodule(fhe);

  py::module api = m.def_submodule("_compiler", "Compiler API");
  mlir::concretelang::python::populateCompilerAPISubmodule(api);
}
