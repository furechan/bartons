use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use super::rma::RmaFilter;
use super::trange::TrangeFilter;
use super::HighLowCloseInput;
use crate::utils::{run_filter, Filter, FilterOutput};

#[derive(Deserialize)]
pub struct DmiKwargs {
    period: i64,
}

pub(crate) struct DmiOutput {
    adx: Option<f64>,
    pdi: Option<f64>,
    mdi: Option<f64>,
}

pub(crate) struct DmiBuilder {
    name: PlSmallStr,
    adx: PrimitiveChunkedBuilder<Float64Type>,
    pdi: PrimitiveChunkedBuilder<Float64Type>,
    mdi: PrimitiveChunkedBuilder<Float64Type>,
}

impl FilterOutput for DmiOutput {
    type Builder = DmiBuilder;

    fn builder(name: &str, capacity: usize) -> Self::Builder {
        DmiBuilder {
            name: name.into(),
            adx: PrimitiveChunkedBuilder::new("adx".into(), capacity),
            pdi: PrimitiveChunkedBuilder::new("pdi".into(), capacity),
            mdi: PrimitiveChunkedBuilder::new("mdi".into(), capacity),
        }
    }

    fn append(builder: &mut Self::Builder, value: Option<Self>) {
        let value = value.unwrap_or(DmiOutput {
            adx: None,
            pdi: None,
            mdi: None,
        });
        builder.adx.append_option(value.adx);
        builder.pdi.append_option(value.pdi);
        builder.mdi.append_option(value.mdi);
    }

    fn finish(builder: Self::Builder) -> Series {
        let fields = [
            builder.adx.finish().into_series(),
            builder.pdi.finish().into_series(),
            builder.mdi.finish().into_series(),
        ];
        StructChunked::from_series(builder.name, fields[0].len(), fields.iter())
            .expect("equal-length DMI fields")
            .into_series()
    }
}

/// Streaming Directional Movement Index filter.
///
/// True range and positive/negative directional movement are smoothed in one
/// pass. Their directional indices then feed Wilder's ADX smoothing.
pub struct DmiFilter {
    trange: TrangeFilter,
    atr: RmaFilter,
    plus_dm: RmaFilter,
    minus_dm: RmaFilter,
    adx: RmaFilter,
    previous: Option<(f64, f64)>,
}

impl DmiFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        Ok(Self {
            trange: TrangeFilter::new(),
            atr: RmaFilter::new(period)?,
            plus_dm: RmaFilter::new(period)?,
            minus_dm: RmaFilter::new(period)?,
            adx: RmaFilter::new(period)?,
            previous: None,
        })
    }
}

impl Filter for DmiFilter {
    type Input = HighLowCloseInput;
    type Output = DmiOutput;

    fn next(&mut self, (high, low, close): HighLowCloseInput) -> Option<Self::Output> {
        let tr = self.trange.next((high, low, close));
        let atr = self.atr.next(tr);

        let current = high.zip(low);
        let movement = current
            .zip(self.previous)
            .map(|((high, low), (prev_high, prev_low))| {
                let up = high - prev_high;
                let down = prev_low - low;
                (
                    if up > down && up > 0.0 { up } else { 0.0 },
                    if down > up && down > 0.0 { down } else { 0.0 },
                )
            });
        self.previous = current;

        let plus_dm = self.plus_dm.next(movement.map(|value| value.0));
        let minus_dm = self.minus_dm.next(movement.map(|value| value.1));
        let (pdi, mdi) = match (atr, plus_dm, minus_dm) {
            (Some(atr), Some(plus_dm), Some(minus_dm)) if atr != 0.0 => {
                (Some(100.0 * plus_dm / atr), Some(100.0 * minus_dm / atr))
            },
            (Some(_), Some(_), Some(_)) => (Some(0.0), Some(0.0)),
            _ => (None, None),
        };

        let dx = pdi.zip(mdi).map(|(pdi, mdi)| {
            let total = pdi + mdi;
            if total == 0.0 {
                0.0
            } else {
                100.0 * (pdi - mdi).abs() / total
            }
        });

        Some(DmiOutput {
            adx: self.adx.next(dx),
            pdi,
            mdi,
        })
    }
}

fn dmi(high: &Series, low: &Series, close: &Series, period: i64) -> PolarsResult<Series> {
    let filter = DmiFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter((high, low, close), "dmi", filter)
}

fn dmi_output(_input_fields: &[Field]) -> PolarsResult<Field> {
    Ok(Field::new(
        "dmi".into(),
        DataType::Struct(vec![
            Field::new("adx".into(), DataType::Float64),
            Field::new("pdi".into(), DataType::Float64),
            Field::new("mdi".into(), DataType::Float64),
        ]),
    ))
}

#[polars_expr(output_type_func = dmi_output)]
fn dmi_expr(inputs: &[Series], kwargs: DmiKwargs) -> PolarsResult<Series> {
    dmi(&inputs[0], &inputs[1], &inputs[2], kwargs.period)
}

/// Directional Movement Index.
///
/// Args:
///     high: high prices.
///     low: low prices.
///     close: close prices.
///     period: Wilder smoothing period (default 14).
///
/// Returns:
///     A Struct series with Float64 fields `adx`, `pdi`, and `mdi`.
#[pyfunction]
#[pyo3(name = "dmi", signature = (high, low, close, *, period=14))]
pub fn dmi_py(high: PySeries, low: PySeries, close: PySeries, period: i64) -> PyResult<PySeries> {
    let high: Series = high.into();
    let low: Series = low.into();
    let close: Series = close.into();
    let result = dmi(&high, &low, &close, period).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rising_prices_have_only_positive_directional_movement() {
        let mut filter = DmiFilter::new(2).unwrap();
        let rows = [(10.0, 8.0, 9.0), (12.0, 9.0, 11.0), (13.0, 10.0, 12.0)];
        let values: Vec<_> = rows
            .into_iter()
            .map(|(high, low, close)| filter.next((Some(high), Some(low), Some(close))).unwrap())
            .collect();
        assert_eq!(values[2].mdi, Some(0.0));
        assert!(values[2].pdi.unwrap() > 0.0);
    }
}
