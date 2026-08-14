mod utils;
mod indicators;

use pyo3::prelude::*;
use pyo3_polars::PolarsAllocator;

#[global_allocator]
static ALLOC: PolarsAllocator = PolarsAllocator::new();


#[pymodule]
fn plugin(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(indicators::ema::ema, m)?)?;
    m.add_function(wrap_pyfunction!(indicators::sma::sma, m)?)?;
    m.add_function(wrap_pyfunction!(indicators::rma::rma, m)?)?;
    m.add_function(wrap_pyfunction!(indicators::wma::wma, m)?)?;
    m.add_function(wrap_pyfunction!(indicators::rsi::rsi, m)?)?;
    m.add_function(wrap_pyfunction!(indicators::trange::trange, m)?)?;
    m.add_function(wrap_pyfunction!(indicators::atr::atr, m)?)?;
    Ok(())
}
