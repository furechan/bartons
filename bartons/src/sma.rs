use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;
use pyo3::exceptions::PyRuntimeError;

#[derive(Deserialize)]
pub struct SmaKwargs {
    period: i64,
}

fn calc_sma(series: &Series, period: i64) -> PolarsResult<Series> {
    let series = series.cast(&DataType::Float64)?;
    let ca = series.f64()?;
    let len = ca.len();
    let name = "sma";

    if period <= 0 {
        return Err(PolarsError::ComputeError("SMA period must be > 0".into()));
    }

    let p = period as usize;
    let mut buf = vec![0.0f64; p]; // ring buffer of the current run's window
    let mut idx = 0usize; // next write slot == oldest element once full
    let mut count: i64 = 0;
    let mut sum = 0.0f64;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(name.into(), len);

    for opt_val in ca.iter() {
        // A null breaks the current run: reset, emit null, and continue.
        let Some(val) = opt_val else {
            count = 0;
            sum = 0.0;
            idx = 0;
            builder.append_null();
            continue;
        };

        if count >= period {
            sum -= buf[idx]; // evict the oldest value
        } else {
            count += 1;
        }
        sum += val;
        buf[idx] = val;
        idx = (idx + 1) % p;

        // Warmup period emits null; otherwise the rolling mean.
        if count >= period {
            builder.append_value(sum / period as f64);
        } else {
            builder.append_null();
        }
    }

    let output = builder.finish().into_series();

    Ok(output)
}

#[polars_expr(output_type = Float64)]
fn sma_expr(inputs: &[Series], kwargs: SmaKwargs) -> PolarsResult<Series> {
    calc_sma(&inputs[0], kwargs.period)
}

#[pyfunction]
#[pyo3(signature = (series, *, period=20))]
pub fn sma(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();

    let result = match calc_sma(&series, period) {
        Ok(s) => s,
        Err(e) => return Err(PyRuntimeError::new_err(e.to_string())),
    };

    let result: PySeries = PySeries(result);
    Ok(result)
}
