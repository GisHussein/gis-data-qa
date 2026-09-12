"""Small helpers shared by the checks."""

from __future__ import annotations

import warnings


def usable_mask(geom):
    """Boolean mask of geometries that are present and non-empty.

    GeoPandas warns when ``notna()`` is called on a series that contains empty
    geometries, because the meaning of that call changed between versions. The
    combination below is the current, explicit behaviour, so the warning is
    noise rather than information.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="GeoSeries.notna", category=UserWarning)
        return geom.notna() & ~geom.is_empty
