"""gis-data-qa - validate a spatial layer against a written set of rules."""

from .core import validate, validate_file
from .report import Finding, Report
from .rules import FieldRule, LayerRules

__version__ = "0.1.0"

__all__ = [
    "validate",
    "validate_file",
    "LayerRules",
    "FieldRule",
    "Report",
    "Finding",
]
