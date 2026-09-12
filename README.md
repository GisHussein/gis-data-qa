# gis-data-qa

Validate a spatial layer against a rule file you can read, review and put in
version control — and fail the build when the data does not hold up.

Most GIS programmes do not fall over because the analysis was wrong. They fall
over because a layer arrived with a status field somebody typed by hand, two
parcels that overlap by 30 cm, and a CRS tag that says UTM while the numbers are
still in degrees. Nobody notices until the map is already in a report.

This is the check that runs before that happens.

```
$ gisqa examples/data/plots_dirty.geojson --rules examples/rules.yml

Layer:     coastal_development_plots
Source:    examples/data/plots_dirty.geojson
Features:  10
CRS:       EPSG:32636

[FAIL] geometry.invalid: features fail OGC validity (self-intersection, bad ring order, ...)
        1 feature(s): PLT-006
        reasons: {'Self-intersection': 1}
[FAIL] schema.domain: field 'status' contains values outside its domain
        1 feature(s): PLT-005
        unexpected_values: Approved
[FAIL] schema.unique: field 'plot_id' must be unique but repeats
        1 feature(s): PLT-002
[FAIL] topology.overlap: polygons overlap each other
        2 feature(s): PLT-003, PLT-004
        pairs: 1
[WARN] geometry.sliver_polygon: polygons smaller than min_area (100)
        2 feature(s): PLT-006, PLT-007

7 error(s), 3 warning(s)
$ echo $?
1
```

Findings are reported by **key value, not row number** — `PLT-002`, not `row 2` —
so they still point at the right feature after the next export re-sorts the file.

## Install

```bash
git clone https://github.com/GisHussein/gis-data-qa.git
cd gis-data-qa
pip install -e ".[dev]"
```

## Use it

```bash
# human-readable
gisqa data/plots.gpkg --rules rules/plots.yml --layer plots

# machine-readable, for a pipeline
gisqa data/plots.gpkg --rules rules/plots.yml --format json --output qa.json
```

Exit codes: `0` clean, `1` at least one error, `2` the file or the rules could
not be read. That is the whole integration story — drop it in a CI job or at the
end of a nightly load and it stops bad data at the door.

From Python:

```python
from gisqa import validate_file

report = validate_file("data/plots.gpkg", "rules/plots.yml")
if not report.passed:
    for finding in report.errors:
        print(finding.check, finding.feature_ids)
```

## The rule file

One YAML file per layer. It is the contract, and because it lives in git a
change to what counts as valid data shows up as a diff.

```yaml
name: coastal_development_plots

geometry_type: Polygon
min_area: 100                 # m2 - anything smaller is a clip artefact
max_vertices: 5000            # boundaries heavier than this slow every query
allow_overlaps: false         # plots tile the coast, they do not stack
allow_duplicate_geometries: false

crs: "EPSG:32636"             # UTM 36N
allow_missing_crs: false
coordinate_bounds: [300000, 2600000, 600000, 2950000]

fields:
  - name: plot_id
    dtype: str
    nullable: false
    unique: true              # also becomes the id used in findings

  - name: status
    dtype: str
    nullable: false
    allowed: [approved, pending, rejected]

  - name: area_m2
    dtype: float
    min: 0
    max_null_fraction: 0.05
```

## What it checks

| Check | Severity | Catches |
|---|---|---|
| `geometry.missing` / `geometry.empty` | error | features with no shape at all |
| `geometry.invalid` | error | self-intersections, bad ring order — grouped by reason |
| `geometry.type` | error | a line that found its way into a polygon layer |
| `geometry.non_finite_coordinates` | error | NaN / infinite coordinates |
| `geometry.sliver_polygon` / `geometry.short_line` | warning | clip and snap artefacts |
| `geometry.vertex_count` | warning | the 80k-vertex boundary behind the slow query |
| `topology.overlap` | error | polygons that are meant to tile but stack |
| `topology.duplicate_geometry` | error | the import that ran twice |
| `topology.mixed_multipart` | warning | single- and multi-part mixed in one layer |
| `crs.missing` | error | no CRS defined |
| `crs.mismatch` | error | not the CRS the project agreed on |
| `crs.units_mismatch` | error | degrees in a projected CRS, or metres in a geographic one |
| `crs.outside_study_area` | error | features outside the declared envelope |
| `schema.missing_field` | error | the column the downstream job needs is gone |
| `schema.dtype` | error | numbers that arrived as text |
| `schema.null` / `schema.null_rate` | error / warning | nulls where there should be none |
| `schema.unique` | error | duplicate keys |
| `schema.domain` | error | values outside the picklist |
| `schema.range` | error | negative areas, impossible dates |
| `schema.whitespace` | warning | trailing spaces that silently break every join |
| `schema.undeclared_field` | warning | columns nobody documented |

Errors fail the run. Warnings are reported and do not, unless you pass
`--warnings-as-errors`.

## Why the CRS checks matter

`crs.units_mismatch` is the one that earns its keep. A layer tagged `EPSG:32636`
whose coordinates sit between 25 and 35 was never reprojected — it was
re-labelled. It opens, it draws, and it is a few thousand kilometres from the
site. GeoPandas will not complain, QGIS will not complain, and the mistake
usually surfaces at the worst possible moment.

```
[FAIL] crs.units_mismatch: projected CRS but coordinates are in the degree range
        bounds: [34.9, 25.2, 34.903, 25.201]
        hint: the data was probably never reprojected, only re-labelled
```

## Examples

Three layers are included so the tool can be run straight after cloning:

| File | What it is |
|---|---|
| `plots_clean.geojson` | passes cleanly, exit 0 |
| `plots_dirty.geojson` | one instance of every failure mode |
| `plots_wrong_crs.geojson` | correct-looking data, wrong coordinate system |

Regenerate them with `python examples/make_examples.py`.

## Tests

```bash
pytest
```

34 tests covering every check, both severities, the rule loader and the CLI
exit codes — including the cases that must **not** fire: polygons that share an
edge are a correct parcel fabric, not an overlap.

## Scope

Single-layer validation. Cross-layer checks (does every building fall inside a
parcel, does every road connect) are a different problem and are not here.
Raster is out of scope.

## Licence

MIT.
