mod ema;
mod sma;
mod rma;
mod wma;
mod trange;

use pyo3::prelude::*;
use pyo3_polars::PolarsAllocator;

#[global_allocator]
static ALLOC: PolarsAllocator = PolarsAllocator::new();


#[pymodule]
fn plugin(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(ema::ema, m)?)?;
    m.add_function(wrap_pyfunction!(sma::sma, m)?)?;
    m.add_function(wrap_pyfunction!(rma::rma, m)?)?;
    m.add_function(wrap_pyfunction!(wma::wma, m)?)?;
    m.add_function(wrap_pyfunction!(trange::trange, m)?)?;
    Ok(())
}
