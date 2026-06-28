use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;
use pyo3::exceptions::PyRuntimeError;

#[derive(Deserialize)]
pub struct RmaKwargs {
    period: i64,
}

fn calc_rma(series: &Series, period: i64) -> PolarsResult<Series> {
    let series = series.cast(&DataType::Float64)?;
    let ca = series.f64()?;
    let len = ca.len();
    let name = "rma";

    if period <= 0 {
        return Err(PolarsError::ComputeError("RMA period must be > 0".into()));
    }

    let alpha = 1.0 / period as f64; // Wilder smoothing factor
    let mut rma = f64::NAN;
    let mut total = 0.0f64;
    let mut count: i64 = 0;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(name.into(), len);

    for opt_val in ca.iter() {
        // A null breaks the current run: reset, emit null, and continue.
        let Some(val) = opt_val else {
            rma = f64::NAN;
            total = 0.0;
            count = 0;
            builder.append_null();
            continue;
        };

        count += 1;
        if count <= period {
            // Simple-average seeding until `period` values are accumulated.
            total += val;
            rma = total / count as f64;
        } else {
            // Wilder smoothing: rma += (val - rma) / period.
            rma += alpha * (val - rma);
        }

        // Warmup period emits null; otherwise the running RMA value.
        if count >= period {
            builder.append_value(rma);
        } else {
            builder.append_null();
        }
    }

    let output = builder.finish().into_series();

    Ok(output)
}

#[polars_expr(output_type = Float64)]
fn rma_expr(inputs: &[Series], kwargs: RmaKwargs) -> PolarsResult<Series> {
    calc_rma(&inputs[0], kwargs.period)
}

#[pyfunction]
#[pyo3(signature = (series, *, period=20))]
pub fn rma(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();

    let result = match calc_rma(&series, period) {
        Ok(s) => s,
        Err(e) => return Err(PyRuntimeError::new_err(e.to_string())),
    };

    let result: PySeries = PySeries(result);
    Ok(result)
}
