use crate::utils::Triple;

/// One bar's `(high, low, close)` — the indicator-side name for
/// [`Triple`](crate::utils::Triple).
///
/// The drivers in `utils` stay arity-generic (they only know they are fed three
/// aligned series); the kernels here say what those three are. Same type, so an
/// `Hlc` filter satisfies `run_ternary`'s `Filter<Input = Triple>` bound
/// directly.
pub(crate) type Hlc = Triple;

pub mod ema;
pub mod mad;
pub mod rma;
pub mod sma;
pub mod wma;
pub mod rsi;
pub mod trange;
pub mod atr;
pub mod cci;
pub mod ker;
pub mod kama;
