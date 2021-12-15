#include <mlir/Dialect/Arithmetic/IR/Arithmetic.h>
#include <mlir/Dialect/MemRef/IR/MemRef.h>
#include <mlir/Dialect/SCF/SCF.h>
#include <mlir/Dialect/StandardOps/IR/Ops.h>
#include <mlir/IR/PatternMatch.h>
#include <mlir/Transforms/GreedyPatternRewriteDriver.h>

#include <zamalang/Dialect/HLFHE/IR/HLFHEOps.h>
#include <zamalang/Dialect/HLFHE/IR/HLFHETypes.h>
#include <zamalang/Dialect/HLFHELinalg/IR/HLFHELinalgOps.h>
#include <zamalang/Dialect/HLFHELinalg/Transforms/Tiling.h>
#include <zamalang/Support/Constants.h>

namespace mlir {
namespace zamalang {

namespace {

// Creates a `tensor.extract_slice` operation that extracts a
// contiguous, 2-dimensional slice with a static size specified by
// `sizes` at the dynamic offset `offsets`.
mlir::tensor::ExtractSliceOp
extractContiguous2DSlice(mlir::OpBuilder &builder, mlir::Location loc,
                         mlir::Value T, llvm::ArrayRef<int64_t> sizes,
                         llvm::ArrayRef<mlir::OpFoldResult> offsets) {
  assert(sizes.size() == 2 && offsets.size() == 2 &&
         "The number of dimensions for the size and offset must be 2");

  mlir::Type elTy = T.getType().cast<mlir::TensorType>().getElementType();

  return builder.create<mlir::tensor::ExtractSliceOp>(
      loc, mlir::RankedTensorType::get(sizes, elTy), T, offsets,
      llvm::SmallVector<mlir::OpFoldResult, 2>{
          builder.getI64IntegerAttr(sizes[0]),
          builder.getI64IntegerAttr(sizes[1])},
      llvm::SmallVector<mlir::OpFoldResult, 2>{builder.getI64IntegerAttr(1),
                                               builder.getI64IntegerAttr(1)});
}

// Creates a perfect loop nest of SCF for loops with the lower bounds
// `lbs`, the upper bounds `ubs` and the steps `steps` in the order
// from the outermost to the innermost loop. The values specified in
// `loopCarriedDeps` are loop-carried dependencies carried across all
// loops.
//
// The function `func` is called with a builder for the body of the
// innermost loop, the original location `loc`, a vector with all
// induction variables from the outermost to the innermost loop and the
// loop-carried dependencies.
//
// Returns the outermost loop.
mlir::scf::ForOp buildLoopNestWithLoopCarriedDependency(
    mlir::OpBuilder builder, mlir::Location loc,
    llvm::ArrayRef<mlir::Value> lbs, llvm::ArrayRef<mlir::Value> ubs,
    llvm::ArrayRef<mlir::Value> steps,
    llvm::ArrayRef<mlir::Value> loopCarriedDeps,
    function_ref<void(OpBuilder &, Location, ValueRange, ValueRange)> func =
        nullptr) {

  size_t nLoops = lbs.size();

  assert(nLoops > 0 && ubs.size() == nLoops && steps.size() == nLoops &&
         "Attempting to build loop nest with incomplete specification");

  llvm::SmallVector<mlir::Value> loopCarriedDepsUpd(loopCarriedDeps.begin(),
                                                    loopCarriedDeps.end());
  llvm::SmallVector<mlir::Value> inductionVars;
  llvm::SmallVector<mlir::scf::ForOp> fops;

  // Create the loops and construct body of the innermost loop using the
  // callback function
  for (size_t i = 0; i < nLoops; i++) {
    mlir::scf::ForOp fop = builder.create<mlir::scf::ForOp>(
        loc, lbs[i], ubs[i], steps[i], loopCarriedDepsUpd,

        [&](mlir::OpBuilder &builder, mlir::Location location,
            mlir::Value indVar, mlir::ValueRange iterArgs) -> void {
          loopCarriedDepsUpd = iterArgs;
          inductionVars.push_back(indVar);

          mlir::OpBuilder opb(builder);

          if (i == nLoops - 1 && func)
            func(opb, location, inductionVars, iterArgs);
        });

    builder.setInsertionPoint(fop.getBody(), fop.getBody()->end());

    fops.push_back(fop);
  }

  // Return updated loop-carried dependencies via scf.yield operations
  for (size_t i = 0; i < nLoops - 1; i++) {
    builder.setInsertionPoint(fops[i].getBody(), fops[i].getBody()->end());
    builder.create<mlir::scf::YieldOp>(loc, fops[i + 1].getResults());
  }

  return fops[0];
}

// Marker to avoid infinite recursion of the rewriting pattern
static const mlir::StringLiteral kTransformMarker =
    "__internal_hlfhe_linalg_tiling_marker__";

// Rewrite an `HLFHELinalg.matmul_eint_int` operation as an equivalent
// sequence of operations consisting of a perfect loop nest of SCF for
// loops with a `HLFHELinalg.matmul_eint_int` operation that performs
// a matrix multiplication on a single tile.
//
// The terminology is as follows:
//
//   - A: The input matrix of encrypted integers of size `NxM`
//   - B: The input matrix of plaintext integers of size `MxK`
//   - C: The output matrix of encrypted integers of size `NxK`
//
// At each iteration of the innermost loop, the generated
// `HLFHELinalg.matmul_eint_int` operation performs a multiplication
// of a matrix tile of size `TxU` and a matrix of size `UxV`,
// producing a tile of size `UxV`.
//
// Partial tiles are currently not supported, i.e., `N` must be a
// multiple of `T`, `M` a multiple of `U` and `K` a multiple of `V`.
class MatMulTilingPattern : public mlir::OpRewritePattern<
                                mlir::zamalang::HLFHELinalg::MatMulEintIntOp> {
public:
  MatMulTilingPattern(mlir::MLIRContext *context)
      : mlir::OpRewritePattern<mlir::zamalang::HLFHELinalg::MatMulEintIntOp>(
            context, ::mlir::zamalang::DEFAULT_PATTERN_BENEFIT) {}

  mlir::LogicalResult
  matchAndRewrite(mlir::zamalang::HLFHELinalg::MatMulEintIntOp op,
                  mlir::PatternRewriter &rewriter) const override {
    // Avoid infinite recursion by marking each matmul operation and
    // bailing out  for the marker
    if (op->hasAttr(kTransformMarker))
      return mlir::failure();

    // Only tile operations that are explicitly marked for tiling with
    // tile sizes
    if (!op->hasAttr("tile-sizes"))
      return mlir::failure();

    // Original location of the operation to be replaced with the
    // tiling
    mlir::Location origLoc = op->getLoc();

    mlir::ArrayAttr tileSizes =
        op->getAttrOfType<mlir::ArrayAttr>("tile-sizes");

    if (!tileSizes) {
      op->emitError("Wrong type for attribute \"tile-size\"");
      return mlir::failure();
    }

    if (tileSizes.size() != 3) {
      op->emitError("Need 3 tile sizes, but got ") << tileSizes.size();
      return mlir::failure();
    }

    // Extract tile sizes
    mlir::IntegerAttr attrT =
        tileSizes[0].dyn_cast_or_null<mlir::IntegerAttr>();
    mlir::IntegerAttr attrU =
        tileSizes[1].dyn_cast_or_null<mlir::IntegerAttr>();
    mlir::IntegerAttr attrV =
        tileSizes[2].dyn_cast_or_null<mlir::IntegerAttr>();

    if (!attrT || !attrU || !attrV) {
      op->emitError("Wrong type for tile sizes");
      return mlir::failure();
    }

    mlir::OpBuilder::InsertionGuard guard(rewriter);
    rewriter.startRootUpdate(op);
    rewriter.setInsertionPointAfter(op);

    // Plain integer tile sizes
    int64_t iT = attrT.getInt();
    int64_t iU = attrU.getInt();
    int64_t iV = attrV.getInt();

    mlir::Value A = op.getOperand(0);
    mlir::Value B = op.getOperand(1);

    // Initialization of the output matrix with zeros
    mlir::zamalang::HLFHELinalg::ZeroOp Cinit =
        rewriter.create<mlir::zamalang::HLFHELinalg::ZeroOp>(
            origLoc, op.getResult().getType());

    mlir::TensorType ATTy = A.getType().cast<mlir::TensorType>();
    mlir::TensorType BTTy = B.getType().cast<mlir::TensorType>();
    mlir::TensorType CTTy =
        Cinit.getResult().getType().cast<mlir::TensorType>();

    if (!ATTy.hasStaticShape() || !BTTy.hasStaticShape() ||
        !CTTy.hasStaticShape()) {
      op.emitError() << "Can only tile matrix multiplications on statically "
                        "shaped tensors";
      return mlir::failure();
    }

    // Check that no partial tiles are necessary
    if (ATTy.getDimSize(0) % iT != 0 || ATTy.getDimSize(1) % iU != 0 ||
        BTTy.getDimSize(1) % iV != 0) {
      op.emitError() << "Dimensions of the tensors must be a multiple of the "
                        "tile size. Partial tiles are currently not supported.";
      return mlir::failure();
    }

    mlir::arith::ConstantIndexOp T =
        rewriter.create<mlir::arith::ConstantIndexOp>(origLoc, iT);

    mlir::arith::ConstantIndexOp U =
        rewriter.create<mlir::arith::ConstantIndexOp>(origLoc, iU);

    mlir::arith::ConstantIndexOp V =
        rewriter.create<mlir::arith::ConstantIndexOp>(origLoc, iV);

    // Lower bound for all for loops
    mlir::arith::ConstantIndexOp lb =
        rewriter.create<mlir::arith::ConstantIndexOp>(origLoc, 0);

    // Upper bounds are determined by the size of the operands
    mlir::arith::ConstantIndexOp ubT =
        rewriter.create<mlir::arith::ConstantIndexOp>(origLoc,
                                                      ATTy.getDimSize(0));

    mlir::arith::ConstantIndexOp ubU =
        rewriter.create<mlir::arith::ConstantIndexOp>(origLoc,
                                                      ATTy.getDimSize(1));

    mlir::arith::ConstantIndexOp ubV =
        rewriter.create<mlir::arith::ConstantIndexOp>(origLoc,
                                                      BTTy.getDimSize(1));

    // Bounds and steps in vector form
    llvm::SmallVector<mlir::Value, 3> lbs{lb, lb, lb};
    llvm::SmallVector<mlir::Value, 3> ubs{ubT, ubU, ubV};
    llvm::SmallVector<mlir::Value, 3> steps{T, U, V};

    // Callback function to build the body of the innermost loop
    auto innermostBodyBuilder = [&](mlir::OpBuilder &builder,
                                    mlir::Location location,
                                    mlir::ValueRange inductionVars,
                                    mlir::ValueRange iterArgs) {
      // TxU tile from A
      mlir::tensor::ExtractSliceOp ATile = extractContiguous2DSlice(
          builder, origLoc, A, {iT, iU}, {inductionVars[0], inductionVars[1]});
      // UxV tile from B
      mlir::tensor::ExtractSliceOp BTile = extractContiguous2DSlice(
          builder, origLoc, B, {iU, iV}, {inductionVars[1], inductionVars[2]});

      // TxV tile from C
      mlir::tensor::ExtractSliceOp CTile = extractContiguous2DSlice(
          builder, origLoc, *iterArgs.begin(), {iT, iV},
          {inductionVars[0], inductionVars[2]});

      // Multiplication of the tiles
      mlir::zamalang::HLFHELinalg::MatMulEintIntOp tiledMul =
          builder.create<mlir::zamalang::HLFHELinalg::MatMulEintIntOp>(
              origLoc,
              mlir::RankedTensorType::get(llvm::SmallVector<int64_t, 2>{iT, iV},
                                          CTTy.getElementType()),
              ATile, BTile);

      // Mark matrix multiplication to prevent recursive
      // application of the rewriting pattern
      tiledMul.getOperation()->setAttr(kTransformMarker,
                                       rewriter.getUnitAttr());

      // Add result of the multiplication of the tiles to the
      // result tile from C
      mlir::zamalang::HLFHELinalg::AddEintOp accuTile =
          builder.create<mlir::zamalang::HLFHELinalg::AddEintOp>(origLoc, CTile,
                                                                 tiledMul);

      // Write updated C tile back into C
      mlir::tensor::InsertSliceOp Cupdated =
          builder.create<mlir::tensor::InsertSliceOp>(
              origLoc, accuTile, *iterArgs.begin(),

              llvm::SmallVector<mlir::OpFoldResult, 2>{inductionVars[0],
                                                       inductionVars[2]},

              llvm::SmallVector<mlir::OpFoldResult, 2>{
                  rewriter.getI64IntegerAttr(iT),
                  rewriter.getI64IntegerAttr(iV)},

              llvm::SmallVector<mlir::OpFoldResult, 2>{
                  rewriter.getI64IntegerAttr(1),
                  rewriter.getI64IntegerAttr(1)});

      builder.create<mlir::scf::YieldOp>(origLoc, Cupdated.getResult());
    };

    mlir::scf::ForOp outermost = buildLoopNestWithLoopCarriedDependency(
        rewriter, origLoc, lbs, ubs, steps, Cinit.getResult(),
        innermostBodyBuilder);

    rewriter.replaceOp(op, outermost.getResult(0));

    rewriter.finalizeRootUpdate(op);

    return mlir::success();
  }
};

// Perfoms the actual tiling of `HLFHELinalg.matmul_eint_int`
// operations that have been marked with a "tile-sizes" attribute.
class HLFHELinalgTilingPass
    : public HLFHELinalgTilingBase<HLFHELinalgTilingPass> {
public:
  void runOnOperation() override {
    mlir::Operation *op = getOperation();

    mlir::RewritePatternSet patterns(op->getContext());
    patterns.add<MatMulTilingPattern>(op->getContext());

    if (mlir::applyPatternsAndFoldGreedily(op, std::move(patterns)).failed()) {
      this->signalPassFailure();
    }

    op->walk([](mlir::zamalang::HLFHELinalg::MatMulEintIntOp matmulOp) {
      matmulOp.getOperation()->removeAttr(kTransformMarker);
    });
  }
};

// Marks all `HLFHELinalg.matmul_eint_int` operations that with a
// "tile-sizes" attribute containing the specified tile sizes.
class HLFHELinalgTilingMarkerPass
    : public HLFHELinalgTilingMarkerBase<HLFHELinalgTilingMarkerPass> {
public:
  HLFHELinalgTilingMarkerPass(llvm::ArrayRef<int64_t> tileSizes)
      : tileSizes(tileSizes.vec()) {}

  void runOnOperation() override {
    mlir::Operation *op = getOperation();

    mlir::ArrayAttr tileAttr =
        mlir::Builder(&this->getContext()).getI64ArrayAttr(tileSizes);

    op->walk([&](mlir::zamalang::HLFHELinalg::MatMulEintIntOp matmulOp) {
      matmulOp.getOperation()->setAttr("tile-sizes", tileAttr);
    });
  }

protected:
  std::vector<int64_t> tileSizes;
};
} // end anonymous namespace

std::unique_ptr<mlir::OperationPass<>> createHLFHELinalgTilingPass() {
  return std::make_unique<HLFHELinalgTilingPass>();
}

std::unique_ptr<mlir::OperationPass<>>
createHLFHELinalgTilingMarkerPass(llvm::ArrayRef<int64_t> tileSizes) {
  return std::make_unique<HLFHELinalgTilingMarkerPass>(tileSizes);
}
} // namespace zamalang
} // namespace mlir
