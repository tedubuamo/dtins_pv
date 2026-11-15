# System Architecture

## DTINS PV Power & Energy Forecasting --- Univariate Multi-Horizon LSTM

**Architecture status:** Proposed baseline\
**Deployment target:** Local research workstation, offline-first\
**Primary data flow:** Excel/CSV → validation → preprocessing → LSTM →
energy/PI calculation → dashboard

------------------------------------------------------------------------

## 1. Architecture objectives

-   Keep the forecasting pipeline reproducible and separable from the
    UI.
-   Enforce a genuinely univariate model input: historical
    `Production Power (W)` only.
-   Preserve chronological ordering and prevent data leakage.
-   Support six-step, 5-minute multi-output forecasting.
-   Derive forecast energy and prediction intervals from the same
    forecast run.
-   Clearly separate model training/evaluation from dashboard inference.
-   Support Historical Replay first; leave automatic acquisition behind
    a future adapter.

## 2. High-level architecture

``` mermaid
flowchart TD
    A[Historical inverter Excel / CSV] --> B[File ingestion]
    B --> C[Schema and timestamp validation]
    C --> D[Data quality report]
    C --> E[Cleaning and 5-minute continuity checks]
    E --> F[Chronological dataset partitions]
    F --> G[Training-only scaler fit]
    G --> H[Sliding-window builder]
    H --> I[Univariate Multi-output LSTM]
    I --> J[Validation-based model selection]
    J --> K[Independent test evaluation]
    J --> L[Conformal calibration]
    K --> M[Model package]
    L --> M
    M --> N[Forecast inference]
    N --> O[Six Power forecasts]
    O --> P[30-minute Energy calculation]
    O --> Q[PI 95% calculation]
    P --> R[Dashboard]
    Q --> R
    O --> R
    D --> R
```

## 3. Recommended logical modules

``` text
project/
├── app.py
├── pages/
│   ├── 1_Data_Management.py
│   ├── 2_Historical_Monitoring.py
│   ├── 3_LSTM_Forecasting.py
│   └── 4_Model_Validation.py
├── src/
│   ├── ingestion/
│   │   ├── readers.py
│   │   └── schema.py
│   ├── preprocessing/
│   │   ├── cleaning.py
│   │   ├── continuity.py
│   │   ├── scaling.py
│   │   └── windowing.py
│   ├── models/
│   │   ├── lstm.py
│   │   ├── train.py
│   │   ├── predict.py
│   │   └── persistence.py
│   ├── evaluation/
│   │   ├── metrics.py
│   │   ├── comparison.py
│   │   └── conformal.py
│   ├── forecasting/
│   │   ├── energy.py
│   │   └── pipeline.py
│   └── utils/
│       ├── config.py
│       └── logging.py
├── artifacts/
│   ├── model/
│   ├── scaler/
│   ├── calibration/
│   └── metadata/
├── data/
│   ├── raw/
│   ├── processed/
│   └── exports/
├── tests/
├── configs/
│   └── experiment.yaml
├── requirements.txt
└── README.md
```

The structure is a recommendation, not a claim that these files already
exist.

## 4. Data contract

### 4.1 Required fields

  ---------------------------------------------------------------------------------
  Logical field    Type                          Required Meaning
  ---------------- ---------------- --------------------- -------------------------
  `timestamp`      datetime                           Yes Measurement time; used
                                                          for ordering and display.

  `power_w`        float                              Yes `Production Power (W)`;
                                                          sole model feature and
                                                          target.
  ---------------------------------------------------------------------------------

Original export column names may vary. The ingestion layer should
support configurable column mapping.

### 4.2 Data rules

-   Parse timestamps with explicit timezone handling.
-   Sort ascending by timestamp.
-   Detect duplicate timestamps.
-   Flag duplicate rows with conflicting power values for review.
-   Convert power to numeric and flag invalid values.
-   Flag negative values for review; do not silently discard without a
    documented rule.
-   Preserve genuine zero-power readings, including nighttime zeros.
-   Detect missing 5-minute intervals.
-   Segment data into continuous valid sequences.
-   Never fill missing records with zero by default.
-   Do not create windows that cross invalid gaps or partition
    boundaries.

### 4.3 Provenance

For every processed dataset, retain: - Source filename and file hash
where practical. - Import timestamp. - Original and mapped column
names. - Timezone assumption. - Row counts before and after each
cleaning step. - Duplicate, invalid, and missing-interval counts. -
Cleaning configuration/version.

## 5. Preprocessing and dataset construction

### Step 1 --- Ingestion

Read Excel or CSV and map source fields to canonical `timestamp` and
`power_w`.

### Step 2 --- Validation

Check required columns, timestamp parseability, numeric power,
duplicates, chronological ordering, and 5-minute cadence.

### Step 3 --- Cleaning and segmentation

Apply documented duplicate and invalid-row rules. Segment at missing or
irregular intervals. Genuine zero power remains valid unless domain
inspection identifies a data fault.

### Step 4 --- Chronological partitioning

Create four temporally ordered partitions: 1. Training 2. Validation 3.
Conformal calibration 4. Independent test

Exact date boundaries and proportions must be selected based on
available coverage and documented in experiment metadata. Do not assume
a split ratio before inspecting the actual dataset.

Use an embargo/gap where needed so that overlapping input/target windows
do not leak information across partitions.

### Step 5 --- Scaling

Fit the scaler using training values only. Save scaler parameters and
reuse them unchanged for validation, calibration, test, and inference.
Inverse-transform model outputs before showing W/Wh to users.

### Step 6 --- Sliding windows

For look-back length `L` and forecast output length `H=6`:

\[ X_i=\[P\_{i-L+1},...,P_i\], `\quad`{=tex}
Y_i=\[P\_{i+1},...,P\_{i+6}\] \]

Model input shape: `(batch_size, L, 1)`\
Model output shape: `(batch_size, 6)`

Candidate look-back values: 6, 12, and 24 samples. At 5-minute cadence,
these represent 30, 60, and 120 minutes of history.

## 6. LSTM model

### 6.1 Baseline architecture

``` mermaid
flowchart LR
    A[Power history: L × 1] --> B[LSTM layer]
    B --> C[Optional second LSTM / representation]
    C --> D[Dropout]
    D --> E[Dense output: 6 neurons]
    E --> F[Power +5, +10, +15, +20, +25, +30 min]
```

Recommended implementation is a single multi-output network rather than
six independent models. Final layer has six neurons, one per 5-minute
horizon.

### 6.2 Candidate hyperparameters

  Parameter       Candidate values
  --------------- ------------------
  Look-back       6, 12, 24
  Hidden units    32, 64, 128
  LSTM layers     1, 2
  Dropout         0.0--0.2
  Learning rate   0.001, 0.0005
  Batch size      16, 32, 64

These are candidates for controlled experiments. The winning
configuration is determined from validation results, not assumed in
advance.

### 6.3 Training controls

-   Use chronological train/validation data.
-   Use early stopping based on validation loss or a declared validation
    metric.
-   Save best checkpoint and training history.
-   Record random seed, library versions, architecture, optimizer, loss,
    batch size, and epoch.
-   Do not use calibration or test data for model selection.

## 7. Baseline and evaluation

### 7.1 Persistence baseline

For each horizon, persistence predicts future power as the last observed
power value:

\[ `\hat `{=tex}P\_{t+h}\^{persist}=P_t \]

Compare LSTM and persistence on identical forecast origins, targets, and
horizons.

### 7.2 Metrics

\[
MAE=`\frac{1}{n}`{=tex}`\sum`{=tex}\_{i=1}\^{n}\|y_i-`\hat `{=tex}y_i\|
\]

\[ RMSE=`\sqrt{\frac{1}{n}\sum_{i=1}^{n}(y_i-\hat y_i)^2}`{=tex} \]

Report R² as a supporting metric. Calculate metrics separately for each
of the six horizons. Also consider day/night or operating-regime
breakdowns as analysis, without changing the univariate input
definition.

### 7.3 Test discipline

-   Tune using validation only.
-   Calibrate PI using calibration only.
-   Evaluate final point forecasts and interval performance on
    independent test only.
-   Do not repeatedly inspect test results to tune the model.
-   If conducting bootstrap/significance analysis, account for temporal
    dependence (e.g. day-block resampling where appropriate).

## 8. Conformal prediction interval

For each horizon `h`, use calibration predictions and actual values:

\[ r\_{i,h}=\|y\_{i,h}-`\hat `{=tex}y\_{i,h}\| \]

Compute the finite-sample conformal quantile `q_h` at nominal
miscoverage 5%, following a documented quantile convention.

\[ L\_{t,h}=`\hat `{=tex}P\_{t,h}-q_h \] \[
U\_{t,h}=`\hat `{=tex}P\_{t,h}+q_h \]

The dashboard displays `[L, U]` for each horizon. Evaluate: - PICP:
proportion of actual values covered by the interval. - Mean interval
width. - Results by horizon.

Do not label an interval as calibrated 95% if it has not been generated
from the documented calibration procedure. Do not calibrate on the test
set. If using rolling/adaptive conformal calibration, document the
window size, minimum residual count, update timing, and assumptions.

## 9. Energy calculation

For a 5-minute interval:

\[ `\Delta `{=tex}t=`\frac{5}{60}`{=tex}`\text{ hour}`{=tex} \]

\[
`\hat `{=tex}E\_{30}(`\mathrm{Wh}`{=tex})=`\sum`{=tex}*{k=1}\^{6}`\hat `{=tex}P*{t+5k}`\Delta `{=tex}t
\]

The six model outputs are the six sequential 5-minute power estimates.
Store energy in Wh and optionally display kWh. Clearly state the
integration convention and whether the forecast points represent
interval-average or interval-end power; the data/model definition must
be consistent.

## 10. Inference pipeline

1.  User selects an imported dataset and replay timestamp.
2.  Pipeline finds the latest valid continuous sequence ending at or
    before that timestamp.
3.  Verify that enough input points exist for the model look-back.
4.  Transform power values using the saved training scaler.
5.  Run the LSTM.
6.  Inverse-transform six predictions to W.
7.  Apply horizon-specific conformal quantiles to produce PI bounds.
8.  Integrate six predicted powers to estimate 30-minute energy.
9.  Return structured result plus provenance metadata.
10. Dashboard renders forecast and labels the exact forecast origin.

If the latest source observation is stale, show its actual timestamp.
Never shift the forecast origin to the current wall-clock time unless
fresh data exists.

## 11. Suggested inference response schema

``` json
{
  "mode": "historical_replay",
  "source_file": "uploaded_dataset.xlsx",
  "forecast_origin": "2025-11-30T10:00:00+07:00",
  "sampling_minutes": 5,
  "feature": "Production Power (W)",
  "model_version": "lstm-mh-v1",
  "horizons": [
    {
      "minutes_ahead": 5,
      "forecast_power_w": 1200.0,
      "lower_95_w": 900.0,
      "upper_95_w": 1500.0
    }
  ],
  "forecast_energy_30m_wh": 650.0,
  "forecast_energy_30m_kwh": 0.65
}
```

The numbers above are schema examples only, not measured or validated
results. A production response contains all six horizon entries.

## 12. Dashboard architecture

Recommended initial implementation: local Python dashboard
(e.g. Streamlit) with separate page modules and a reusable Python
forecasting package.

Pages: - Data Management - Historical Monitoring - LSTM Forecasting -
Model Validation

The UI calls service functions; it must not contain model-training logic
or duplicate preprocessing rules.

### Layer responsibilities

  -----------------------------------------------------------------------
  Layer                               Responsibility
  ----------------------------------- -----------------------------------
  Presentation                        Uploads, filters, charts, KPI
                                      cards, status and exports.

  Application/service                 Orchestrates validation, forecast
                                      requests, and report generation.

  Domain                              Canonical data rules, window
                                      construction, energy, metrics,
                                      conformal logic.

  ML                                  Model definition, training,
                                      checkpoint loading, inference.

  Infrastructure                      Excel/CSV readers, filesystem
                                      artifacts, logging, optional future
                                      API adapter.
  -----------------------------------------------------------------------

## 13. Artifact and experiment management

Save: - Model weights/checkpoint. - Scaler. - Conformal quantiles by
horizon. - Model metadata. - Training history. - Validation metrics. -
Independent test predictions and metrics. - Experiment configuration. -
Data-cleaning report.

Each model package must include compatible scaler and calibration
artifacts. Reject mismatched versions.

## 14. Future data acquisition extension

The first release is file-based Historical Replay. A later adapter may
retrieve records from an official cloud API or a verified local
inverter/data-logger interface.

Before implementing: - Confirm official access and permitted use. -
Verify new records are actually arriving. - Store source timestamp and
received timestamp separately. - Track connection state and data age. -
Retain the same canonical data contract and forecasting service.

A future live/near-real-time mode must be gated by verified freshness.
Historical records must never be relabelled as live.

## 15. Testing strategy

### Unit tests

-   Timestamp parsing and timezone behavior.
-   Duplicate handling.
-   Invalid and negative power handling.
-   Zero-power retention.
-   5-minute continuity segmentation.
-   Sliding-window shapes and target alignment.
-   Training-only scaler behavior.
-   Energy formula and units.
-   Conformal quantile and interval calculation.
-   Metrics calculations.

### Integration tests

-   Excel/CSV upload to cleaned dataset.
-   Dataset to model inference.
-   Model output to energy and PI calculation.
-   Forecast result to dashboard rendering.
-   Export schema and metadata.

### Scientific validation checks

-   No train/validation/calibration/test temporal overlap leakage.
-   Test timestamps match between LSTM and persistence.
-   Calibration residuals do not come from test data.
-   All metrics identify the evaluated partition and horizon.
-   Stale data state is surfaced.

## 16. Key architectural decisions

  Decision                  Baseline
  ------------------------- ----------------------------------------
  Model input               Univariate power only
  Timestamp role            Ordering, cadence validation, display
  Sampling                  5 minutes
  Forecast structure        Multi-output, six sequential horizons
  Energy horizon            30 minutes
  PI                        Horizon-specific conformal calibration
  Split                     Chronological four partitions
  Baseline                  Persistence
  Initial data access       Excel/CSV
  Initial dashboard mode    Historical Replay
  Future live acquisition   Separate, conditional extension
