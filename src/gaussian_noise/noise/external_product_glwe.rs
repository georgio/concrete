use crate::gaussian_noise::conversion::modular_variance_to_variance;
use crate::utils::square;

pub fn variance_external_product_glwe(
    glwe_dimension: u64,
    polynomial_size: u64,
    log2_base: u64,
    level: u64,
    ciphertext_modulus_log: u32,
    variance_ggsw: f64,
) -> f64 {
    theoretical_variance_external_product_glwe(
        glwe_dimension,
        polynomial_size,
        log2_base,
        level,
        ciphertext_modulus_log,
        variance_ggsw,
    ) + fft_noise_variance_external_product_glwe(
        glwe_dimension,
        polynomial_size,
        log2_base,
        level,
        ciphertext_modulus_log,
    )
}

fn theoretical_variance_external_product_glwe(
    glwe_dimension: u64,
    polynomial_size: u64,
    log2_base: u64,
    level: u64,
    ciphertext_modulus_log: u32,
    variance_ggsw: f64,
) -> f64 {
    let variance_key_coefficient_binary: f64 =
        modular_variance_to_variance(1. / 4., ciphertext_modulus_log);

    let square_expectation_key_coefficient_binary: f64 =
        modular_variance_to_variance(square(1. / 2.), ciphertext_modulus_log);

    let k = glwe_dimension as f64;
    let b = 2_f64.powi(log2_base as i32);
    let b2l = 2_f64.powi((log2_base * 2 * level) as i32);
    let l = level as f64;
    let big_n = polynomial_size as f64;
    let q_square = 2_f64.powi(2 * ciphertext_modulus_log as i32);

    let res_1 = l * (k + 1.) * big_n * (square(b) + 2.) / 12. * variance_ggsw;
    let res_2 = (q_square - b2l) / (24. * b2l)
        * (modular_variance_to_variance(1., ciphertext_modulus_log)
            + k * big_n
                * (variance_key_coefficient_binary + square_expectation_key_coefficient_binary))
        + k * big_n / 8. * variance_key_coefficient_binary
        + 1. / 16. * square(1. - k * big_n) * square_expectation_key_coefficient_binary;

    res_1 + res_2
}

const FFT_SCALING_WEIGHT: f64 = -2.577_224_94;

/// Additional noise generated by fft computation

fn fft_noise_variance_external_product_glwe(
    glwe_dimension: u64,
    polynomial_size: u64,
    log2_base: u64,
    level: u64,
    ciphertext_modulus_log: u32,
) -> f64 {
    // https://github.com/zama-ai/concrete-optimizer/blob/prototype/python/optimizer/noise_formulas/bootstrap.py#L25
    let b = 2_f64.powi(log2_base as i32);
    let l = level as f64;
    let big_n = polynomial_size as f64;
    let k = glwe_dimension;
    assert!(k > 0, "k = {k}");
    assert!(k < 7, "k = {k}");

    // 22 = 2 x 11, 11 = 64 -53
    let scale_margin = (1_u64 << 22) as f64;
    let res =
        f64::exp2(FFT_SCALING_WEIGHT) * scale_margin * l * b * b * big_n.powi(2) * (k as f64 + 1.);
    modular_variance_to_variance(res, ciphertext_modulus_log)
}
