// Part of the Concrete Compiler Project, under the BSD3 License with Zama
// Exceptions. See
// https://github.com/zama-ai/concrete-compiler-internal/blob/main/LICENSE.txt
// for license information.

#include "concretelang/Runtime/context.h"
#include "concretelang/Common/Error.h"
#include <assert.h>
#include <stdio.h>

namespace clientlib = ::concretelang::clientlib;
namespace mlir {
namespace concretelang {

FFT::FFT(size_t polynomial_size)
    : fft(nullptr), polynomial_size(polynomial_size) {
  fft = (struct Fft *)aligned_alloc(CONCRETE_FFT_ALIGN, CONCRETE_FFT_SIZE);
  concrete_cpu_construct_concrete_fft(fft, polynomial_size);
}

FFT::FFT(FFT &&other) : fft(other.fft), polynomial_size(other.polynomial_size) {
  other.fft = nullptr;
}

FFT::~FFT() {
  if (fft != nullptr) {
    concrete_cpu_destroy_concrete_fft(fft);
    free(fft);
  }
}

RuntimeContext::RuntimeContext(clientlib::EvaluationKeys evaluationKeys)
    : evaluationKeys(evaluationKeys) {
  {

    // Initialize for each bootstrap key the fourier one
    for (auto bsk : evaluationKeys.getBootstrapKeys()) {
      auto param = bsk.parameters();

      size_t decomposition_level_count = param.level;
      size_t decomposition_base_log = param.baseLog;
      size_t glwe_dimension = param.glweDimension;
      size_t polynomial_size = param.polynomialSize;
      size_t input_lwe_dimension = param.inputLweDimension;

      // Create the FFT
      FFT fft(polynomial_size);

      // Allocate scratch for key conversion
      size_t scratch_size;
      size_t scratch_align;
      concrete_cpu_bootstrap_key_convert_u64_to_fourier_scratch(
          &scratch_size, &scratch_align, fft.fft);
      auto scratch = (uint8_t *)aligned_alloc(scratch_align, scratch_size);

      // Allocate the fourier_bootstrap_key
      auto fourier_data = std::make_shared<std::vector<double>>();
      fourier_data->resize(bsk.size());
      auto bsk_data = bsk.buffer();

      // Convert bootstrap_key to the fourier domain
      concrete_cpu_bootstrap_key_convert_u64_to_fourier(
          bsk_data, fourier_data->data(), decomposition_level_count,
          decomposition_base_log, glwe_dimension, polynomial_size,
          input_lwe_dimension, fft.fft, scratch, scratch_size);

      // Store the fourier_bootstrap_key in the context
      fourier_bootstrap_keys.push_back(fourier_data);
      ffts.push_back(std::move(fft));
      free(scratch);
    }

#ifdef CONCRETELANG_CUDA_SUPPORT
    assert(cudaGetDeviceCount(&num_devices) == cudaSuccess);
    bsk_gpu.resize(num_devices, nullptr);
    ksk_gpu.resize(num_devices, nullptr);
    for (int i = 0; i < num_devices; ++i) {
      bsk_gpu_mutex.push_back(std::make_unique<std::mutex>());
      ksk_gpu_mutex.push_back(std::make_unique<std::mutex>());
    }
#endif
  }
}

} // namespace concretelang
} // namespace mlir
