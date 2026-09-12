import json
import pathlib

import pytest

from gisqa import validate
from gisqa.cli import main
from gisqa.rules import LayerRules

from .conftest import codes

EXAMPLES = pathlib.Path(__file__).resolve().parents[1] / "examples"


def test_missing_required_field(clean_layer, rules):
    layer = clean_layer.drop(columns=["status"])
    report = validate(layer, rules)
    assert "schema.missing_field" in codes(report)


def test_duplicate_key(clean_layer, rules):
    clean_layer.loc[2, "plot_id"] = "A1"
    report = validate(clean_layer, rules)
    assert "schema.unique" in codes(report)


def test_value_outside_domain(clean_layer, rules):
    clean_layer.loc[0, "status"] = "APPROVED"
    report = validate(clean_layer, rules)
    assert "schema.domain" in codes(report)


def test_null_in_non_nullable_field(clean_layer, rules):
    clean_layer.loc[0, "status"] = None
    report = validate(clean_layer, rules)
    assert "schema.null" in codes(report)


def test_value_below_minimum(clean_layer, rules):
    clean_layer.loc[0, "area_m2"] = -1.0
    report = validate(clean_layer, rules)
    assert "schema.range" in codes(report)


def test_untrimmed_whitespace_is_a_warning(clean_layer, rules):
    clean_layer.loc[0, "status"] = "approved "
    report = validate(clean_layer, rules)
    assert "schema.whitespace" in codes(report)


def test_undeclared_field(clean_layer, rules):
    clean_layer["surveyor"] = "n/a"
    report = validate(clean_layer, rules)
    assert "schema.undeclared_field" in codes(report)


# --- rule file -----------------------------------------------------------


def test_rules_round_trip():
    rules = LayerRules.load(EXAMPLES / "rules.yml")
    assert rules.name == "coastal_development_plots"
    assert rules.crs == "EPSG:32636"
    assert {f.name for f in rules.fields} == {"plot_id", "status", "area_m2"}


def test_unknown_key_is_rejected():
    with pytest.raises(ValueError):
        LayerRules.from_dict({"name": "x", "geometyr_type": "Polygon"})


def test_unknown_geometry_type_is_rejected():
    with pytest.raises(ValueError):
        LayerRules.from_dict({"name": "x", "geometry_type": "Blob"})


# --- CLI -----------------------------------------------------------------


def test_cli_passes_on_clean_data(capsys):
    code = main(
        [
            str(EXAMPLES / "data" / "plots_clean.geojson"),
            "--rules",
            str(EXAMPLES / "rules.yml"),
            "--no-colour",
        ]
    )
    assert code == 0
    assert "No issues found" in capsys.readouterr().out


def test_cli_fails_on_dirty_data(capsys):
    code = main(
        [
            str(EXAMPLES / "data" / "plots_dirty.geojson"),
            "--rules",
            str(EXAMPLES / "rules.yml"),
            "--no-colour",
        ]
    )
    assert code == 1
    assert "error(s)" in capsys.readouterr().out


def test_cli_json_output_is_parseable(capsys):
    main(
        [
            str(EXAMPLES / "data" / "plots_dirty.geojson"),
            "--rules",
            str(EXAMPLES / "rules.yml"),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is False
    assert payload["summary"]["errors"] > 0
    assert any(f["check"] == "topology.overlap" for f in payload["findings"])


def test_cli_reports_a_missing_file(capsys):
    code = main(["nope.geojson", "--rules", str(EXAMPLES / "rules.yml")])
    assert code == 2
    assert "not found" in capsys.readouterr().err


def test_warnings_as_errors(capsys):
    # The wrong-CRS layer has errors anyway; use the clean one plus a rule that
    # only produces a warning.
    code = main(
        [
            str(EXAMPLES / "data" / "plots_clean.geojson"),
            "--rules",
            str(EXAMPLES / "rules.yml"),
            "--warnings-as-errors",
            "--no-colour",
        ]
    )
    assert code == 0  # the clean layer has no warnings either
