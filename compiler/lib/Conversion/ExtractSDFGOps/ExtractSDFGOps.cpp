// Part of the Concrete Compiler Project, under the BSD3 License with Zama
// Exceptions. See
// https://github.com/zama-ai/concrete-compiler-internal/blob/main/LICENSE.txt
// for license information.

#include "concretelang/Conversion/Passes.h"
#include "concretelang/Dialect/SDFG/IR/SDFGDialect.h"
#include "concretelang/Dialect/SDFG/IR/SDFGOps.h"
#include "concretelang/Dialect/SDFG/IR/SDFGTypes.h"
#include "concretelang/Dialect/SDFG/Interfaces/SDFGConvertibleInterface.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/ImplicitLocOpBuilder.h"
#include "mlir/IR/Visitors.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Transforms/DialectConversion.h"
#include "mlir/Transforms/RegionUtils.h"
#include "llvm/ADT/DenseMap.h"
#include "llvm/ADT/STLExtras.h"
#include "llvm/ADT/SmallVector.h"
#include "llvm/Support/Casting.h"

namespace SDFG = mlir::concretelang::SDFG;

namespace {
enum class StreamMappingKind { ON_DEVICE, TO_DEVICE, SPLICE, TO_HOST, NONE };

SDFG::MakeStream makeStream(mlir::ImplicitLocOpBuilder &builder,
                            SDFG::StreamKind kind, mlir::Type type,
                            mlir::Value dfg, unsigned &streamNumber) {
  SDFG::StreamType streamType = builder.getType<SDFG::StreamType>(type);
  mlir::StringAttr name = builder.getStringAttr(llvm::Twine("stream") +
                                                llvm::Twine(streamNumber++));

  return builder.create<SDFG::MakeStream>(streamType, dfg, name, kind);
}

StreamMappingKind determineStreamMappingKind(mlir::Value v) {
  // Determine stream type for operands:
  //
  //  - If an operand is produced by a non-convertible op, there
  //    needs to be just a host-to-device stream
  //
  //  - If an operand is produced by a convertible op and there
  //    are no other consumers, a device-to-device stream may be
  //    used
  //
  //  - If an operand is produced by a convertible op and there is
  //    at least one other non-convertible consumer, there needs
  //    to be a device-to-host stream, and a host-to-device stream
  //
  if (llvm::dyn_cast_or_null<SDFG::SDFGConvertibleOpInterface>(
          v.getDefiningOp())) {
    // All convertible consumers?
    if (llvm::all_of(v.getUses(), [](mlir::OpOperand &o) {
          return !!llvm::dyn_cast_or_null<SDFG::SDFGConvertibleOpInterface>(
              o.getOwner());
        })) {
      return StreamMappingKind::ON_DEVICE;
    }
    // All non-convertible consumers?
    else if (llvm::all_of(v.getUses(), [](mlir::OpOperand &o) {
               return !llvm::dyn_cast_or_null<SDFG::SDFGConvertibleOpInterface>(
                   o.getOwner());
             })) {
      return StreamMappingKind::TO_HOST;
    }
    // Mix of convertible and non-convertible users
    else {
      return StreamMappingKind::SPLICE;
    }
  } else {
    if (llvm::any_of(v.getUses(), [](mlir::OpOperand &o) {
          return !!llvm::dyn_cast_or_null<SDFG::SDFGConvertibleOpInterface>(
              o.getOwner());
        })) {
      return StreamMappingKind::TO_DEVICE;
    } else {
      return StreamMappingKind::NONE;
    }
  }
}

void setInsertionPointAfterValueOrRestore(mlir::OpBuilder &builder,
                                          mlir::Value v,
                                          mlir::OpBuilder::InsertPoint &pos) {
  if (v.isa<mlir::BlockArgument>())
    builder.restoreInsertionPoint(pos);
  else
    builder.setInsertionPointAfterValue(v);
}

struct ExtractSDFGOpsPass : public ExtractSDFGOpsBase<ExtractSDFGOpsPass> {

  ExtractSDFGOpsPass() {}

  void runOnOperation() override {
    mlir::func::FuncOp func = getOperation();
    mlir::IRRewriter rewriter(func.getContext());

    mlir::DenseMap<mlir::Value, SDFG::MakeStream> processOutMapping;
    mlir::DenseMap<mlir::Value, SDFG::MakeStream> processInMapping;
    mlir::DenseMap<mlir::Value, mlir::Value> replacementMapping;

    llvm::SmallVector<SDFG::SDFGConvertibleOpInterface> convertibleOps;

    unsigned streamNumber = 0;

    func.walk([&](SDFG::SDFGConvertibleOpInterface op) {
      convertibleOps.push_back(op);
    });

    if (convertibleOps.size() == 0)
      return;

    // Insert Prelude
    rewriter.setInsertionPointToStart(&func.getBlocks().front());
    mlir::Value dfg = rewriter.create<SDFG::Init>(
        func.getLoc(), rewriter.getType<SDFG::DFGType>());
    SDFG::Start start = rewriter.create<SDFG::Start>(func.getLoc(), dfg);

    rewriter.setInsertionPoint(func.getBlocks().front().getTerminator());
    rewriter.create<SDFG::Shutdown>(func.getLoc(), dfg);

    mlir::ImplicitLocOpBuilder ilb(func.getLoc(), rewriter);

    auto mapValueToStreams = [&](mlir::Value v) {
      if (processInMapping.find(v) != processInMapping.end() ||
          processOutMapping.find(v) != processOutMapping.end())
        return;

      StreamMappingKind smk = determineStreamMappingKind(v);

      SDFG::MakeStream prodOutStream;
      SDFG::MakeStream consInStream;

      if (smk == StreamMappingKind::SPLICE ||
          smk == StreamMappingKind::TO_HOST) {
        ilb.setInsertionPoint(start);
        prodOutStream = makeStream(ilb, SDFG::StreamKind::device_to_host,
                                   v.getType(), dfg, streamNumber);
        processOutMapping.insert({v, prodOutStream});

        ilb.setInsertionPointAfter(start);
        mlir::OpBuilder::InsertPoint pos = ilb.saveInsertionPoint();
        setInsertionPointAfterValueOrRestore(ilb, v, pos);
        mlir::Value newOutVal =
            ilb.create<SDFG::Get>(v.getType(), prodOutStream.getResult());
        replacementMapping.insert({v, newOutVal});
      } else if (smk == StreamMappingKind::ON_DEVICE) {
        ilb.setInsertionPoint(start);
        prodOutStream = makeStream(ilb, SDFG::StreamKind::on_device,
                                   v.getType(), dfg, streamNumber);
        processOutMapping.insert({v, prodOutStream});
      }

      if (smk == StreamMappingKind::ON_DEVICE) {
        processInMapping.insert({v, prodOutStream});
      } else if (smk == StreamMappingKind::SPLICE ||
                 smk == StreamMappingKind::TO_DEVICE ||
                 smk == StreamMappingKind::ON_DEVICE) {
        ilb.setInsertionPoint(start);
        consInStream = makeStream(ilb, SDFG::StreamKind::host_to_device,
                                  v.getType(), dfg, streamNumber);
        processInMapping.insert({v, consInStream});

        if (smk == StreamMappingKind::TO_DEVICE) {
          ilb.setInsertionPointAfter(start);
          mlir::OpBuilder::InsertPoint pos = ilb.saveInsertionPoint();
          setInsertionPointAfterValueOrRestore(ilb, v, pos);
          ilb.create<SDFG::Put>(consInStream.getResult(), v);
        }
      }
    };

    for (SDFG::SDFGConvertibleOpInterface convertibleOp : convertibleOps) {
      llvm::SmallVector<mlir::Value> ins;
      llvm::SmallVector<mlir::Value> outs;
      ilb.setLoc(convertibleOp.getLoc());

      for (mlir::Value res : convertibleOp->getResults()) {
        mapValueToStreams(res);
        outs.push_back(processOutMapping.find(res)->second.getResult());
      }

      for (mlir::Value operand : convertibleOp->getOperands()) {
        mapValueToStreams(operand);
        ins.push_back(processInMapping.find(operand)->second.getResult());
      }

      ilb.setInsertionPoint(start);
      SDFG::MakeProcess process = convertibleOp.convert(ilb, dfg, ins, outs);

      assert(process && "Conversion to SDFG operation failed");
    }

    for (auto it : replacementMapping) {
      it.first.replaceAllUsesWith(it.second);
    }

    (void)mlir::simplifyRegions(rewriter, func->getRegions());
  }
};
} // namespace

namespace mlir {
namespace concretelang {

std::unique_ptr<OperationPass<mlir::func::FuncOp>> createExtractSDFGOpsPass() {
  return std::make_unique<ExtractSDFGOpsPass>();
}
} // namespace concretelang
} // namespace mlir
