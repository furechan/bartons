mod kernels;
pub mod samples;
mod utils;

use pyo3::prelude::*;
#[cfg(feature = "extension-module")]
use pyo3_polars::PolarsAllocator;

#[cfg(feature = "extension-module")]
#[global_allocator]
static ALLOC: PolarsAllocator = PolarsAllocator::new();

#[pymodule(name = "kernels")]
fn python_kernels(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(kernels::ema::ema_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::dema::dema_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::tema::tema_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::hma::hma_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::sma::sma_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::rma::rma_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::wma::wma_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::rsi::rsi_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::trange::trange_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::atr::atr_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::mad::mad_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::cci::cci_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::ker::ker_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::kama::kama_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::sar::sar_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::streak::streak_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::linreg::linreg_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::quadreg::quadreg_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::mfi::mfi_py, m)?)?;
    m.add_function(wrap_pyfunction!(samples::random_prices_py, m)?)?;
    m.add_function(wrap_pyfunction!(samples::with_n_chunks_py, m)?)?;
    Ok(())
}
