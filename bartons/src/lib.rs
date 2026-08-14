mod utils;
mod kernels;

use pyo3::prelude::*;
use pyo3_polars::PolarsAllocator;

#[global_allocator]
static ALLOC: PolarsAllocator = PolarsAllocator::new();


#[pymodule]
fn plugin(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(kernels::ema::ema_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::sma::sma_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::rma::rma_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::wma::wma_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::rsi::rsi_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::trange::trange_py, m)?)?;
    m.add_function(wrap_pyfunction!(kernels::atr::atr_py, m)?)?;
    Ok(())
}
