mod ema;

use pyo3::prelude::*;
use pyo3_polars::PolarsAllocator;

#[global_allocator]
static ALLOC: PolarsAllocator = PolarsAllocator::new();


#[pymodule]
#[pyo3(name = "plugin")]
fn bearta_plugin(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(ema::ema, m)?)?;
    Ok(())
}
