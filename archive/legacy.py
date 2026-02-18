from __future__ import annotations
from typing import TYPE_CHECKING

import polars as pl
from pathlib import Path

from polars.plugins import register_plugin_function


PLUGIN_PATH = Path(__file__).parent


if TYPE_CHECKING:
    from bearta.typing import IntoExprColumn




def noop(expr: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="noop",
        is_elementwise=True,
    )


def abs_i64(expr: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="abs_i64",
        is_elementwise=True,
    )


def abs_numeric(expr: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="abs_numeric",
        is_elementwise=True,
    )


def sum_i64(expr: IntoExprColumn, other: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr, other],
        plugin_path=PLUGIN_PATH,
        function_name="sum_i64",
        is_elementwise=True,
    )


def cum_sum(expr: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="cum_sum",
        is_elementwise=False,
    )


def pig_latinnify(expr: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="pig_latinnify",
        is_elementwise=True,
    )


def remove_extension(expr: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="remove_extension",
        is_elementwise=True,
    )


def abs_i64_fast(expr: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="abs_i64_fast",
        is_elementwise=True,
    )


def add_suffix(expr: IntoExprColumn, *, suffix: str) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="add_suffix",
        is_elementwise=True,
        kwargs={"suffix": suffix},
    )


def snowball_stem(expr: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="snowball_stem",
        is_elementwise=True,
    )


def weighted_mean(expr: IntoExprColumn, weights: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr, weights],
        plugin_path=PLUGIN_PATH,
        function_name="weighted_mean",
        is_elementwise=True,
    )


def print_struct_fields(expr: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="print_struct_fields",
        is_elementwise=True,
    )


def shift_struct(expr: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="shift_struct",
        is_elementwise=True,
    )



def non_zero_indices(expr: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="non_zero_indices",
        is_elementwise=True,
    )


def vertical_weighted_mean(values: IntoExprColumn, weights: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[values, weights],
        plugin_path=PLUGIN_PATH,
        function_name="vertical_weighted_mean",
        is_elementwise=False,
        returns_scalar=True,
    )


def interpolate(expr: IntoExprColumn) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="interpolate",
        is_elementwise=False,
    )


def life_step(
    left: IntoExprColumn, mid: IntoExprColumn, right: IntoExprColumn
) -> pl.Expr:
    return register_plugin_function(
        args=[left, mid, right],
        plugin_path=PLUGIN_PATH,
        function_name="life_step",
        is_elementwise=False,
    )


def midpoint_2d(expr: IntoExprColumn, ref_point: tuple[float, float]) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="midpoint_2d",
        is_elementwise=True,
        kwargs={"ref_point": ref_point},
    )

__all__= (
    "noop",
    "abs_i64",
    "abs_numeric",
    "sum_i64",
    "cum_sum",
    "pig_latinnify",
    "remove_extension",
    "abs_i64_fast",
    "add_suffix",
    "snowball_stem",
    "weighted_mean",
    "print_struct_fields",
    "shift_struct",
    "non_zero_indices",
    "vertical_weighted_mean",
    "interpolate",
    "life_step",
    "midpoint_2d"
)
