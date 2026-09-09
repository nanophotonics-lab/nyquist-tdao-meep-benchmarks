"""Lightweight time-domain adjoint helpers built on top of Meep.

Teep intentionally keeps Meep objects visible: users still define sources,
geometry, materials, and simulations with Meep, while Teep provides a small
driver for point-monitor time-domain adjoint objectives.
"""

from .coords import centered_grid_coords
from .fastmeep_grid import (
    FastFieldGrid,
    FastGradientGrid,
    native_sampler_available,
    require_native_sampler,
)
from .tda_objective import TDAObjective

__all__ = [
    "centered_grid_coords",
    "FastFieldGrid",
    "FastGradientGrid",
    "TDAObjective",
    "native_sampler_available",
    "require_native_sampler",
]
