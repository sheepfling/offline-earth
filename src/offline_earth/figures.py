"""Dependency-free, explicit figure ownership shared by optional plotters.

A post-plot callback replaces default saving/closing. It receives the figure,
``path`` (an output Path), and the supplied keyword arguments. Return
that figure or a replacement to transfer ownership to the caller, or None to
release it. Callbacks are responsible for saving when desired. No figures are
retained globally. Matplotlib originals are closed on discard or replacement;
figures created inside a callback remain that callback's responsibility on error.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TypeVar

FigureT = TypeVar("FigureT")
PostPlot = Callable[..., Any | None]


def validate_post_plot(
    post_plot: PostPlot | None, post_plot_kwargs: Mapping[str, Any] | None,
) -> None:
    """Reject malformed options before allocating a figure or loading assets."""
    if post_plot is not None and not callable(post_plot):
        raise TypeError("post_plot must be callable")
    if post_plot_kwargs is not None and not isinstance(post_plot_kwargs, Mapping):
        raise TypeError("post_plot_kwargs must be a mapping")
    if post_plot_kwargs and "path" in post_plot_kwargs:
        raise ValueError("path is reserved for the renderer's output path")
    if post_plot is None and post_plot_kwargs:
        raise ValueError("post_plot_kwargs requires post_plot")


def finish_figure(
    figure: FigureT,
    path: Path,
    *,
    post_plot: PostPlot | None,
    post_plot_kwargs: Mapping[str, Any] | None,
    save: Callable[[], None],
    close: Callable[[FigureT], None] = lambda figure: None,
) -> FigureT | None:
    """Apply the default or callback, closing originals not handed to callers."""
    result = None
    try:
        if post_plot is None:
            if post_plot_kwargs:
                raise ValueError("post_plot_kwargs requires post_plot")
            save()
        else:
            candidate = post_plot(figure, path=path, **(post_plot_kwargs or {}))
            if candidate is not None and not isinstance(candidate, type(figure)):
                raise TypeError("post_plot must return a figure of the same backend or None")
            result = candidate
        return result
    finally:
        if result is not figure:
            close(figure)
