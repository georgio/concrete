// Part of the Concrete Compiler Project, under the BSD3 License with Zama
// Exceptions. See
// https://github.com/zama-ai/concrete-compiler-internal/blob/main/LICENSE.txt
// for license information.

#ifndef CONCRETELANG_RUNTIME_CONTEXT_H
#define CONCRETELANG_RUNTIME_CONTEXT_H

#include <assert.h>
#include <map>
#include <mutex>
#include <pthread.h>

#include "concretelang/ClientLib/EvaluationKeys.h"
#include "concretelang/Runtime/seeder.h"

#include "concrete-core-ffi.h"
#include "concretelang/Common/Error.h"

namespace mlir {
namespace concretelang {

typedef struct RuntimeContext {

  RuntimeContext() {
    CAPI_ASSERT_ERROR(new_default_engine(best_seeder, &default_engine));
  }

  /// Ensure that the engines map is not copied
  RuntimeContext(const RuntimeContext &ctx)
      : evaluationKeys(ctx.evaluationKeys) {
    CAPI_ASSERT_ERROR(new_default_engine(best_seeder, &default_engine));
  }
  RuntimeContext(const RuntimeContext &&other)
      : evaluationKeys(other.evaluationKeys),
        default_engine(other.default_engine) {}

  ~RuntimeContext() {
    CAPI_ASSERT_ERROR(destroy_default_engine(default_engine));
    for (const auto &key : fft_engines) {
      CAPI_ASSERT_ERROR(destroy_fft_engine(key.second));
    }
    if (fbsk != nullptr) {
      CAPI_ASSERT_ERROR(destroy_fft_fourier_lwe_bootstrap_key_u64(fbsk));
    }
  }

  FftEngine *get_fft_engine() {
    pthread_t threadId = pthread_self();
    std::lock_guard<std::mutex> guard(engines_map_guard);
    auto engineIt = fft_engines.find(threadId);
    if (engineIt == fft_engines.end()) {
      FftEngine *fft_engine = nullptr;

      CAPI_ASSERT_ERROR(new_fft_engine(&fft_engine));

      engineIt =
          fft_engines
              .insert(std::pair<pthread_t, FftEngine *>(threadId, fft_engine))
              .first;
    }
    assert(engineIt->second && "No engine available in context");
    return engineIt->second;
  }

  DefaultEngine *get_default_engine() { return default_engine; }

  FftFourierLweBootstrapKey64 *get_fft_fourier_bsk() {

    if (fbsk != nullptr) {
      return fbsk;
    }

    const std::lock_guard<std::mutex> guard(fbskMutex);
    if (fbsk == nullptr) {
      CAPI_ASSERT_ERROR(
          fft_engine_convert_lwe_bootstrap_key_to_fft_fourier_lwe_bootstrap_key_u64(
              get_fft_engine(), evaluationKeys.getBsk(), &fbsk));
    }
    return fbsk;
  }

  LweBootstrapKey64 *get_bsk() { return evaluationKeys.getBsk(); }

  LweKeyswitchKey64 *get_ksk() { return evaluationKeys.getKsk(); }

  LweCircuitBootstrapPrivateFunctionalPackingKeyswitchKeys64 *get_fpksk() {
    return evaluationKeys.getFpksk();
  }

  RuntimeContext &operator=(const RuntimeContext &rhs) {
    this->evaluationKeys = rhs.evaluationKeys;
    return *this;
  }

  ::concretelang::clientlib::EvaluationKeys evaluationKeys;

private:
  std::mutex fbskMutex;
  FftFourierLweBootstrapKey64 *fbsk = nullptr;
  DefaultEngine *default_engine;
  std::map<pthread_t, FftEngine *> fft_engines;
  std::mutex engines_map_guard;

} RuntimeContext;

} // namespace concretelang
} // namespace mlir

extern "C" {
LweKeyswitchKey64 *
get_keyswitch_key_u64(mlir::concretelang::RuntimeContext *context);

FftFourierLweBootstrapKey64 *
get_fft_fourier_bootstrap_key_u64(mlir::concretelang::RuntimeContext *context);

LweBootstrapKey64 *
get_bootstrap_key_u64(mlir::concretelang::RuntimeContext *context);

DefaultEngine *get_engine(mlir::concretelang::RuntimeContext *context);

FftEngine *get_fft_engine(mlir::concretelang::RuntimeContext *context);
}
#endif
