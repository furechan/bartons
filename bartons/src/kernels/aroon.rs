use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use super::HighLowInput;
use crate::ring_buffer::RingBuffer;
use crate::utils::{run_filter, Filter, FilterOutput};

#[derive(Deserialize)]
pub struct AroonKwargs {
    period: i64,
}

pub(crate) struct AroonOutput {
    aroondown: f64,
    aroonup: f64,
}

pub(crate) struct AroonBuilder {
    name: PlSmallStr,
    aroondown: PrimitiveChunkedBuilder<Float64Type>,
    aroonup: PrimitiveChunkedBuilder<Float64Type>,
}

impl FilterOutput for AroonOutput {
    type Builder = AroonBuilder;

    fn builder(name: &str, capacity: usize) -> Self::Builder {
        AroonBuilder {
            name: name.into(),
            aroondown: PrimitiveChunkedBuilder::new("aroondown".into(), capacity),
            aroonup: PrimitiveChunkedBuilder::new("aroonup".into(), capacity),
        }
    }

    fn append(builder: &mut Self::Builder, value: Option<Self>) {
        match value {
            Some(value) => {
                builder.aroondown.append_value(value.aroondown);
                builder.aroonup.append_value(value.aroonup);
            },
            None => {
                builder.aroondown.append_null();
                builder.aroonup.append_null();
            },
        }
    }

    fn finish(builder: Self::Builder) -> Series {
        let fields = [
            builder.aroondown.finish().into_series(),
            builder.aroonup.finish().into_series(),
        ];
        StructChunked::from_series(builder.name, fields[0].len(), fields.iter())
            .expect("equal-length AROON fields")
            .into_series()
    }
}

/// Streaming Aroon filter over `period + 1` high/low observations.
pub struct AroonFilter {
    buffer: RingBuffer<(f64, f64)>,
    factor: f64,
}

impl AroonFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period < 2 {
            return Err("AROON period must be >= 2".to_string());
        }

        Ok(Self {
            buffer: RingBuffer::new(period as usize + 1),
            factor: 100.0 / period as f64,
        })
    }
}

impl Filter for AroonFilter {
    type Input = HighLowInput;
    type Output = AroonOutput;

    fn next(&mut self, (high, low): HighLowInput) -> Option<Self::Output> {
        let Some(current) = high.zip(low) else {
            self.buffer.clear();
            return None;
        };
        self.buffer.push(current);

        if !self.buffer.is_full() {
            return None;
        }

        let &(mut highest, mut lowest) = self.buffer.oldest().unwrap();
        let mut highest_index = 0;
        let mut lowest_index = 0;

        for (index, &(high, low)) in self.buffer.iter().enumerate().skip(1) {
            if high >= highest {
                highest = high;
                highest_index = index;
            }
            if low <= lowest {
                lowest = low;
                lowest_index = index;
            }
        }

        Some(AroonOutput {
            aroondown: self.factor * lowest_index as f64,
            aroonup: self.factor * highest_index as f64,
        })
    }
}

fn invalid_period(error: String) -> PolarsError {
    PolarsError::InvalidOperation(error.into())
}

fn aroon(high: &Series, low: &Series, period: i64) -> PolarsResult<Series> {
    run_filter(
        (high, low),
        "aroon",
        AroonFilter::new(period).map_err(invalid_period)?,
    )
}

fn aroon_output(_input_fields: &[Field]) -> PolarsResult<Field> {
    Ok(Field::new(
        "aroon".into(),
        DataType::Struct(vec![
            Field::new("aroondown".into(), DataType::Float64),
            Field::new("aroonup".into(), DataType::Float64),
        ]),
    ))
}

#[polars_expr(output_type_func = aroon_output)]
fn aroon_expr(inputs: &[Series], kwargs: AroonKwargs) -> PolarsResult<Series> {
    aroon(&inputs[0], &inputs[1], kwargs.period)
}

/// Aroon Up and Down.
///
/// Args:
///     high: high prices.
///     low: low prices.
///     period: maximum age of an extreme (default 14).
///
/// Returns:
///     A Struct series with Float64 fields `aroondown` and `aroonup`.
#[pyfunction]
#[pyo3(name = "aroon", signature = (high, low, *, period=14))]
pub fn aroon_py(high: PySeries, low: PySeries, period: i64) -> PyResult<PySeries> {
    let high: Series = high.into();
    let low: Series = low.into();
    let result = aroon(&high, &low, period).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn period_is_maximum_age_and_ties_choose_newest() {
        let mut filter = AroonFilter::new(2).unwrap();
        assert!(filter.next((Some(3.0), Some(2.0))).is_none());
        assert!(filter.next((Some(2.0), Some(1.0))).is_none());
        let output = filter.next((Some(3.0), Some(2.0))).unwrap();
        assert_eq!(output.aroonup, 100.0);
        assert_eq!(output.aroondown, 50.0);
    }

    #[test]
    fn missing_bar_restarts_warmup() {
        let mut filter = AroonFilter::new(2).unwrap();
        filter.next((Some(3.0), Some(2.0)));
        filter.next((Some(2.0), Some(1.0)));
        assert!(filter.next((None, Some(0.0))).is_none());
        assert!(filter.next((Some(3.0), Some(2.0))).is_none());
    }
}
