# Agent Instructions

## Multi-Agent Development Guide --- DTINS PV Forecasting

This document defines responsibilities and working rules for AI coding
agents or human developers collaborating on the PV forecasting research
prototype.

------------------------------------------------------------------------

## 1. Project mission

Build a reproducible, offline-first research application for the 3.5 kWp
On-Grid PV system at the DTINS motorcycle-parking area, FV-ITS.

The baseline forecasting model is **univariate multi-horizon LSTM**: -
Input feature: historical `Production Power (W)` only. - Sampling
interval: 5 minutes. - Timestamp is used for ordering, cadence
validation, and display, not as a model input feature. - Output: six
sequential power predictions at +5, +10, +15, +20, +25, and +30
minutes. - Derived outputs: 30-minute forecast energy and
horizon-specific PI 95%.

The first application mode is file-based Historical Replay. Do not
implement or advertise real-time behavior without verified fresh data
acquisition.

## 2. Global rules --- mandatory

1.  Read `PRD.md`, `Design_System.md`, and `Architecture.md` before
    changing code.
2.  Preserve the univariate scope. Do not add irradiance, weather,
    voltage, current, temperature, or calendar variables to the baseline
    model unless the project owner explicitly approves a new research
    scope.
3.  Do not confuse power (W) with voltage (V).
4.  Never convert missing records into 0 W by default. Genuine measured
    nighttime zeros are valid observations.
5.  Do not randomly shuffle time-series partitions.
6.  Fit scalers on training data only.
7.  Do not allow windows or targets to leak across chronological
    partition boundaries.
8.  Keep conformal calibration data separate from model selection and
    independent testing.
9.  Do not tune on the independent test set.
10. Compare LSTM and persistence on identical timestamps and horizons.
11. Never fabricate metrics, model results, dataset row counts, API
    access, or successful tests.
12. Distinguish source-supported facts, implementation assumptions, and
    illustrative examples.
13. Keep units explicit: power W/kW; energy Wh/kWh; voltage V.
14. Every forecast must expose its forecast origin and model version.
15. Do not label historical records as live or near-real-time.
16. Do not store credentials, API keys, passwords, or tokens in source
    code or documentation.
17. Prefer small, testable modules over a monolithic app.
18. Add or update tests for every data/model calculation change.

## 3. Agent roles

### Agent 1 --- Product / Research Analyst

**Mission:** Keep implementation aligned with research objectives and
the PRD.

Responsibilities: - Convert PRD requirements into implementation
tickets. - Maintain a requirements-to-test traceability table. - Clarify
unresolved decisions rather than silently choosing research
assumptions. - Ensure dashboard copy is scientifically accurate. -
Review acceptance criteria before release.

Must not: - Invent research findings. - Change the model feature
definition without approval. - Treat illustrative numbers as
experimental evidence.

Deliverables: - Requirement checklist. - Open-decision log. - Release
acceptance report.

### Agent 2 --- Data Engineering Agent

**Mission:** Build reliable ingestion, cleaning, validation, and
time-series dataset preparation.

Responsibilities: - Read Excel and CSV. - Implement column mapping. -
Parse timestamps with explicit timezone assumptions. - Sort
chronologically. - Detect duplicates, conflicting duplicate values,
invalid numeric values, negative power, missing intervals, and irregular
cadence. - Preserve valid 0 W readings. - Segment continuous 5-minute
sequences. - Produce data-quality summaries and cleaned exports. -
Record row counts and cleaning decisions.

Must not: - Silently drop records. - Fill missing power with zero. -
Interpolate across gaps without explicit approval and documentation. -
Build sliding windows across invalid gaps or partition boundaries.

Required tests: - Duplicate timestamps. - Conflicting duplicates. -
Non-numeric values. - Invalid timestamps. - Real zero-power readings. -
Missing 5-minute interval. - Irregular interval. - Negative power
warning. - Empty or malformed files.

### Agent 3 --- ML / LSTM Agent

**Mission:** Implement the univariate multi-output LSTM training and
inference pipeline.

Responsibilities: - Build sliding windows from `power_w`. - Support
candidate look-back lengths 6, 12, and 24. - Implement a multi-output
LSTM with six output neurons. - Implement controlled hyperparameter
experiments. - Use chronological training and validation. - Use early
stopping and save the best validation checkpoint. - Save training
history, configuration, and model metadata. - Implement inference using
the exact saved scaler.

Must not: - Use timestamp as an input feature in the baseline. - Add
exogenous variables. - Fit scaler on all data. - Select a model using
test metrics. - Return fewer or differently ordered outputs than the six
defined horizons.

Required tests: - Input shape `(batch, lookback, 1)`. - Output shape
`(batch, 6)`. - Target alignment (+5 to +30 minutes). - Correct inverse
scaling. - Deterministic inference for a fixed model/input where
applicable. - Model/scaler metadata compatibility.

### Agent 4 --- Evaluation / Statistics Agent

**Mission:** Ensure point forecasts and uncertainty are evaluated
rigorously.

Responsibilities: - Implement MAE, RMSE, and R² by horizon. - Implement
persistence baseline. - Align LSTM and persistence on identical
timestamps. - Implement horizon-specific conformal calibration using the
calibration partition. - Implement PICP and mean interval width. -
Generate residual diagnostics. - Consider temporal dependence in
bootstrap/significance analysis. - Produce a clear model evaluation
report.

Must not: - Calibrate PI using independent test residuals. - Claim 95%
coverage without reporting empirical coverage. - Claim LSTM is better
across all metrics if results do not support it. - Compare models on
different timestamps.

Required tests: - Metric calculations against hand-computed examples. -
Persistence prediction alignment. - Calibration quantile behavior. -
Interval lower/upper bounds. - PICP and interval-width calculations. -
Test/calibration separation.

### Agent 5 --- Forecasting Domain Agent

**Mission:** Connect model output to interpretable power and energy
outputs.

Responsibilities: - Convert six model outputs to W. - Calculate
30-minute energy from six sequential 5-minute forecasts. - Apply
calibrated PI bounds for each horizon. - Return structured forecast
objects with source timestamp, forecast origin, model version, and
units. - Validate that the forecast input is a continuous valid
sequence.

Energy formula:

\[
E\_{30}(`\mathrm{Wh}`{=tex})=`\sum`{=tex}*{k=1}\^{6}`\hat `{=tex}P*{t+5k}`\times`{=tex}`\frac{5}{60}`{=tex}
\]

Must not: - Calculate 30-minute energy from only three isolated horizon
values without a documented integration method. - Mix W and kW or Wh and
kWh. - Infer a current timestamp as the forecast origin when the data is
stale.

### Agent 6 --- Frontend / Dashboard Agent

**Mission:** Implement the dashboard in line with `Design_System.md`.

Responsibilities: - Build Data Management, Historical Monitoring, LSTM
Forecasting, and Model Validation pages. - Display four primary
indicators: Actual Power, Forecast Power, Forecast Energy, Prediction
Interval 95%. - Show six forecast horizons. - Display actual and
forecast with distinct chart styles. - Display PI as both a shaded band
and numeric lower/upper bounds. - Show forecast origin, last source
timestamp, model version, and Historical Replay mode. - Provide
data-quality warnings and export actions. - Make the layout responsive
and accessible.

Must not: - Hardcode example values as real results. - Display `Live` or
`Now` for historical data. - Reimplement preprocessing/model
calculations in UI code. - Hide missing calibration state behind a
fabricated interval.

### Agent 7 --- QA / Integration Agent

**Mission:** Verify end-to-end behavior and prevent regressions.

Responsibilities: - Run unit and integration tests. - Validate all four
dashboard pages. - Test malformed uploads and missing artifacts. -
Verify model/scaler/calibration compatibility. - Check exported CSV/JSON
schemas. - Verify scientific integrity requirements. - Produce a release
checklist.

Must not: - Mark a test as passed unless it was executed. - Remove a
failing test to make the build green without resolving the underlying
issue. - Modify model assumptions to bypass validation.

## 4. Dependency order

``` mermaid
flowchart TD
    A[Product / Research Analyst: requirements] --> B[Data Engineering: ingestion and cleaning]
    B --> C[ML Agent: windows and LSTM]
    C --> D[Evaluation Agent: point metrics and baseline]
    D --> E[Evaluation Agent: conformal calibration]
    C --> F[Forecasting Domain Agent: power and energy pipeline]
    E --> F
    B --> G[Dashboard Agent: data pages]
    F --> H[Dashboard Agent: forecasting page]
    D --> I[Dashboard Agent: validation page]
    H --> J[QA / Integration]
    I --> J
    G --> J
    J --> K[Product acceptance]
```

Parallel work is allowed only where interfaces are agreed and stable.
For example, dashboard layout can begin using clearly marked mock
fixtures, but mock data must never be confused with real model outputs.

## 5. Shared interfaces

### Canonical input dataframe

``` python
# Required canonical columns
timestamp: datetime
power_w: float
```

### Model contract

``` python
# Input
X.shape == (batch_size, lookback, 1)

# Output
y_pred.shape == (batch_size, 6)
# Output order:
# +5, +10, +15, +20, +25, +30 minutes
```

### Forecast result contract

``` python
{
    "mode": "historical_replay",
    "forecast_origin": "...",
    "last_observation_timestamp": "...",
    "model_version": "...",
    "feature": "Production Power (W)",
    "sampling_minutes": 5,
    "forecasts": [
        {
            "minutes_ahead": 5,
            "power_w": 0.0,
            "lower_95_w": None,
            "upper_95_w": None
        }
    ],
    "energy_30m_wh": 0.0,
    "energy_30m_kwh": 0.0
}
```

The example values are placeholders for interface design, not expected
predictions. The `forecasts` array must contain six entries. If
calibration is unavailable, PI fields remain null and the UI explains
why.

### Evaluation result contract

Each horizon result should identify: - Horizon in minutes. - Number of
evaluated samples. - LSTM MAE, RMSE, R². - Persistence MAE and RMSE. -
PI nominal coverage. - Empirical PICP. - Mean interval width. -
Evaluation partition identifier.

## 6. Repository and coding conventions

-   Use clear module names and type hints where practical.
-   Keep configuration outside core logic.
-   Do not hardcode local absolute paths.
-   Use pathlib for filesystem paths.
-   Add structured logging for ingestion and model runs.
-   Keep raw data immutable.
-   Save generated artifacts under a documented artifact directory.
-   Avoid committing private datasets or credentials.
-   Use `.env.example` only for variable names; never include real
    secrets.
-   Pin or constrain dependency versions for reproducibility.
-   Use meaningful exceptions and actionable UI error messages.

## 7. Definition of done

A task is done only when: - The implementation matches the relevant PRD
requirement. - Tests are added or updated and executed. - No
scientific-integrity rule is violated. - Units and timestamps are
correct. - Logs/errors are understandable. - Documentation is updated. -
No fake metrics, fabricated data, or unverified live status is shown.

The first usable release is complete when: - Excel/CSV import and
data-quality reporting work. - Valid continuous univariate windows can
be constructed. - A six-output LSTM can be trained or loaded and run. -
Persistence comparison is available. - Independent test metrics are
reported. - PI 95% is shown only when calibration artifacts exist. -
30-minute energy is calculated from all six forecasts. - Historical
Replay and forecast origin are explicit. - The dashboard exports
forecast and validation results.

## 8. Agent handoff template

Every agent handoff should include:

``` text
Task:
Files changed:
Requirement IDs addressed:
Assumptions made:
Tests added:
Commands/tests executed:
Results:
Known limitations:
Next dependency / handoff:
```

If an unresolved decision affects research validity, stop and ask the
project owner instead of silently selecting an assumption.

## 9. Recommended implementation sequence

1.  Establish repository structure and configuration.
2.  Implement ingestion and schema validation.
3.  Implement cleaning, continuity segmentation, and data-quality
    report.
4.  Implement chronological four-way partitioning and leakage checks.
5.  Implement training-only scaling and window generation.
6.  Implement persistence baseline.
7.  Implement LSTM training and validation-based selection.
8.  Implement independent test evaluation.
9.  Implement conformal calibration and PI evaluation.
10. Implement energy calculation and forecast response contract.
11. Build Data Management and Historical Monitoring pages.
12. Build Forecasting and Model Validation pages.
13. Integrate exports, metadata, tests, and documentation.
14. Validate Historical Replay behavior end to end.
15. Consider automatic acquisition only as a separate, verified future
    milestone.
