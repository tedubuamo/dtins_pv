# Product Requirements Document (PRD)

## DTINS PV Power & Energy Forecasting --- Univariate Multi-Horizon LSTM

**Status:** Draft / baseline specification\
**Project type:** Research prototype and offline dashboard\
**System under study:** PLTS On-Grid 3.5 kWp, area parkir sepeda motor
Departemen Teknik Instrumentasi, FV-ITS\
**Primary data source:** Historical inverter production-power records
exported as Excel/CSV

------------------------------------------------------------------------

## 1. Product overview

The product is a research-oriented application that imports historical
PV inverter power records, validates and preprocesses the time series,
runs a trained univariate multi-horizon LSTM model, and presents three
connected forecasting outputs:

1.  **Forecast Power** --- predicted PV output power at 5-minute
    intervals up to 30 minutes.
2.  **Forecast Energy** --- estimated energy generated over the next 30
    minutes, calculated from the six predicted power values.
3.  **Prediction Interval (PI 95%)** --- calibrated uncertainty bounds
    for each forecast horizon.

The dashboard also provides actual-power context, historical charts,
data-quality information, and model-validation metrics.

The first release is an **offline Historical Replay** application. It
must not describe an old imported record as a live measurement or claim
real-time monitoring. Automatic cloud acquisition is a future extension
that depends on verified access to an official data interface and the
availability of new inverter records.

## 2. Problem statement

The PLTS dataset contains time-stamped inverter production power. It
does not consistently provide irradiance, module temperature, ambient
temperature, or weather measurements. Therefore, the baseline research
scope is univariate: the model learns from historical
`Production Power (W)` only.

The application must turn those historical records into a reproducible
forecasting workflow while making data limitations, forecast horizon,
model performance, and prediction uncertainty visible to the researcher.

## 3. Goals

-   Import historical inverter data from Excel and CSV.
-   Validate timestamp and power columns and report data-quality issues.
-   Preserve the 5-minute time-series structure and identify missing or
    irregular intervals.
-   Train or load a univariate LSTM that produces six consecutive
    5-minute forecasts.
-   Calculate 30-minute forecast energy from the six predicted power
    values.
-   Produce calibrated 95% prediction intervals using a dedicated
    calibration dataset.
-   Evaluate the selected model on an untouched chronological test set.
-   Compare LSTM forecasts with a persistence baseline at matching
    timestamps.
-   Present outputs and validation evidence in a clear research
    dashboard.
-   Make the experiment reproducible through saved configuration,
    metrics, and prediction outputs.

## 4. Non-goals for the first release

-   No claim of live or near-real-time inverter monitoring.
-   No control of inverter, battery, grid, or electrical equipment.
-   No weather, irradiance, voltage, current, or temperature inputs to
    the baseline model.
-   No multi-site fleet management or user/role administration.
-   No cloud deployment requirement.
-   No automatic SOLARMAN synchronization until access and data
    freshness are verified.
-   No guarantee that the trained model generalizes to every season or
    operating condition.

## 5. Users and primary use cases

### Primary user: Researcher / student

-   Upload a historical Excel/CSV file.
-   Inspect data coverage, sampling intervals, missing values,
    duplicates, and invalid values.
-   Select a trained model and run a forecast from the latest valid
    continuous sequence.
-   Review power predictions, energy estimate, and PI 95%.
-   Inspect model metrics and compare LSTM against persistence.
-   Export cleaned data, predictions, and evaluation reports.

### Secondary user: Supervisor / evaluator

-   Review the methodology and data-quality evidence.
-   Inspect forecast plots and uncertainty bounds.
-   Verify that test data was not used for model selection or
    calibration.
-   Review model-versus-baseline performance.

## 6. Functional requirements

  --------------------------------------------------------------------------------
  ID               Requirement                   Priority Acceptance criteria
  ---------------- ---------------- --------------------- ------------------------
  FR-01            Excel/CSV upload                  Must User can upload
                                                          supported files and
                                                          receives a clear error
                                                          for unsupported or
                                                          malformed files.

  FR-02            Column mapping                    Must User can map timestamp
                                                          and
                                                          `Production Power (W)`
                                                          columns if names differ.

  FR-03            Data validation                   Must App reports invalid
                                                          timestamps, non-numeric
                                                          power, duplicates,
                                                          missing intervals, and
                                                          negative values.

  FR-04            Time ordering                     Must Records are sorted
                                                          chronologically before
                                                          sequence construction.

  FR-05            Duplicate                         Must Duplicate timestamps are
                   handling                               reported and handled by
                                                          a documented
                                                          deterministic rule;
                                                          conflicting duplicates
                                                          are flagged.

  FR-06            Interval                          Must App identifies whether
                   validation                             consecutive valid
                                                          records follow the
                                                          expected 5-minute
                                                          interval.

  FR-07            Nighttime zero                    Must Genuine zero-power
                   handling                               observations are
                                                          retained; missing
                                                          records are not silently
                                                          converted to zero.

  FR-08            Forecast                          Must Model receives only
                   inference                              historical power values
                                                          and returns six
                                                          forecasts at +5, +10,
                                                          +15, +20, +25, +30
                                                          minutes.

  FR-09            Forecast energy                   Must Energy is calculated
                                                          from all six 5-minute
                                                          forecast values and
                                                          displayed in Wh (and
                                                          optionally kWh).

  FR-10            Prediction                        Must PI 95% is generated from
                   interval                               calibration residuals
                                                          and displayed per
                                                          horizon.

  FR-11            Historical                        Must The dashboard states the
                   replay                                 timestamp of the last
                                                          observation used as
                                                          forecast origin.

  FR-12            Validation                        Must MAE, RMSE, and R² are
                   metrics                                reported by horizon on
                                                          independent test data.

  FR-13            Baseline                          Must LSTM and persistence are
                   comparison                             compared on identical
                                                          test timestamps and
                                                          horizons.

  FR-14            Export                          Should User can export forecast
                                                          rows, cleaned data, and
                                                          metrics as CSV/JSON.

  FR-15            Model metadata                  Should App displays model
                                                          version, training date,
                                                          look-back, sampling
                                                          interval, and feature
                                                          definition.

  FR-16            Automated data                   Later Only implemented after
                   sync                                   an official API/data
                                                          pathway and fresh
                                                          records are confirmed.
  --------------------------------------------------------------------------------

## 7. Forecasting specification

### 7.1 Input

-   Feature: `Production Power (W)` only.
-   Timestamp: used for sorting, interval validation, window
    construction, and display; it is not a model feature in the
    univariate baseline.
-   Sampling interval: 5 minutes.
-   Look-back: configurable during experiments. Candidate values: 6, 12,
    and 24 samples.
-   Example: look-back 6 represents the previous 30 minutes of power
    observations.

### 7.2 Output

The recommended operational model has six output values:

\[ \[`\hat `{=tex}P\_{t+5}, `\hat `{=tex}P\_{t+10},
`\hat `{=tex}P\_{t+15}, `\hat `{=tex}P\_{t+20}, `\hat `{=tex}P\_{t+25},
`\hat `{=tex}P\_{t+30}\] \]

All values are power in watts (W). Do not label power as voltage (V).

### 7.3 Forecast energy

For six consecutive 5-minute forecast intervals:

\[ E\_{30}(`\mathrm{Wh}`{=tex}) = `\sum`{=tex}*{k=1}\^{6}
`\hat `{=tex}P*{t+5k}`\times `{=tex}`\frac{5}{60}`{=tex} \]

\[ E\_{30}(`\mathrm{kWh}`{=tex}) =
`\frac{E_{30}(\mathrm{Wh})}{1000}`{=tex} \]

Use the six consecutive outputs for energy integration. Three isolated
forecasts (+5, +15, +30) are not sufficient to represent all six
5-minute intervals without an additional interpolation or prediction
method.

### 7.4 Prediction interval

Use a separate conformal calibration partition. For each horizon,
calculate absolute calibration residuals and the quantile required for
the nominal 95% interval. The interval is:

\[ \[`\hat `{=tex}P\_{t+h}-q_h, `\hat `{=tex}P\_{t+h}+q_h\] \]

Document the exact finite-sample quantile convention used. Do not
calibrate on the independent test set. If a non-negative lower bound is
clipped to zero for physical display, retain and document the unclipped
interval for statistical evaluation.

## 8. Data and experiment requirements

-   Keep the original raw file unchanged.
-   Create a reproducible cleaned dataset and a data-quality report.
-   Sort by timestamp and inspect duplicate timestamps.
-   Identify missing and irregular 5-minute intervals.
-   Distinguish actual nighttime 0 W from missing or invalid
    observations.
-   Do not interpolate across long gaps without a documented rule.
-   Create continuous valid sequences before sliding-window generation.
-   Split chronologically into four partitions: training, validation,
    conformal calibration, and independent testing.
-   Fit normalization/scaling parameters on training data only; reuse
    them for all later partitions and inference.
-   Prevent leakage from overlapping windows/targets across partition
    boundaries. Use a suitable temporal gap/embargo.
-   Keep the independent test partition untouched until the final
    evaluation.
-   Use rolling-origin evaluation as a robustness extension where data
    volume permits.

## 9. Model development and evaluation

### Candidate experiment parameters

-   Look-back: 6, 12, 24 samples.
-   Hidden units: 32, 64, 128.
-   LSTM layers: 1--2.
-   Dropout: 0--0.2.
-   Learning rate: 0.001 and 0.0005.
-   Batch size: 16, 32, 64.

These are experiment candidates, not fixed claims of an optimal
architecture. Record every experiment and select using validation data
only.

### Required comparisons

-   LSTM versus persistence forecasting.
-   Same forecast origin timestamps and same horizons.
-   Report MAE and RMSE as primary metrics; R² as supporting metric.
-   Report metrics separately for +5, +10, +15, +20, +25, +30 minutes.
-   For PI 95%, report empirical coverage (PICP) and average interval
    width by horizon.
-   Discuss whether the nominal coverage is achieved and whether
    intervals are excessively wide.
-   Consider temporal dependence when performing significance or
    bootstrap analysis.

## 10. Dashboard information architecture

1.  **Data Management**
    -   Upload Excel/CSV.
    -   Map columns.
    -   Show preview, data range, row count, duplicates, invalid
        records, missing intervals, and last timestamp.
    -   Show whether data is suitable for forecasting.
2.  **Historical Monitoring**
    -   Historical power curve.
    -   Date/time filters.
    -   Daily or selected-period summary.
    -   Clearly label as historical data.
3.  **LSTM Forecasting**
    -   Actual Power / last valid observation.
    -   Forecast Power by horizon.
    -   Forecast Energy for 30 minutes.
    -   PI 95% by horizon.
    -   Actual-versus-forecast chart with interval band.
    -   Forecast origin and data freshness.
4.  **Model Validation**
    -   MAE, RMSE, R² by horizon.
    -   LSTM versus persistence comparison.
    -   PI coverage and interval width.
    -   Experiment/model metadata and downloadable reports.

## 11. Non-functional requirements

-   **Scientific integrity:** no data leakage; test set is independent.
-   **Traceability:** every forecast identifies input file, forecast
    origin, model version, and configuration.
-   **Usability:** errors and warnings use clear language and explain
    how to resolve them.
-   **Reliability:** invalid or discontinuous input sequences must block
    forecasting rather than silently generate misleading outputs.
-   **Reproducibility:** fixed random seeds where practical; save
    dependencies and experiment configuration.
-   **Performance:** inference should be responsive for a single
    forecast request on a normal research workstation; benchmark rather
    than promise an unsupported latency.
-   **Offline capability:** core upload, preprocessing, inference, and
    dashboard functions work locally after dependencies and model
    artifacts are installed.

## 12. Acceptance criteria for the first usable release

-   A researcher can upload a valid Excel/CSV and see a data-quality
    summary.
-   The system identifies the latest valid continuous 5-minute sequence.
-   The selected model receives only the power history and generates six
    future power values.
-   Forecast energy is calculated from all six outputs using the stated
    unit conversion.
-   PI 95% is derived from a separate calibration partition and its
    method is documented.
-   The interface clearly labels forecast origin and Historical Replay
    mode.
-   The validation page displays LSTM and persistence metrics on the
    same independent test timestamps.
-   Exported outputs contain timestamps, actual values where available,
    predictions, lower/upper bounds, and model metadata.
-   No UI element labels illustrative or stale values as live inverter
    readings.

## 13. Risks and mitigations

  -----------------------------------------------------------------------
  Risk                                Mitigation
  ----------------------------------- -----------------------------------
  Missing or irregular records        Validate 5-minute continuity;
                                      segment sequences and block invalid
                                      windows.

  Nighttime zeros dominate learning   Report day/night performance
                                      separately as an analysis; do not
                                      delete genuine zeros by default.

  Data leakage                        Chronological four-way split,
                                      training-only scaler fit, and
                                      temporal embargo.

  LSTM does not beat persistence on   Report honestly by horizon and
  all metrics                         metric; do not claim universal
                                      superiority.

  PI coverage below 95%               Revisit calibration method, sample
                                      size, and distribution drift;
                                      report empirical PICP.

  Stale cloud records                 Display source timestamp and
                                      Historical Replay status.

  API access unavailable              Keep file import as the supported
                                      baseline; treat automated
                                      acquisition as a later milestone.
  -----------------------------------------------------------------------

## 14. Milestones

1.  Dataset audit and data dictionary.
2.  Cleaning and continuity validation.
3.  Exploratory analysis and baseline persistence model.
4.  LSTM windowing, training, and validation-based tuning.
5.  Independent test evaluation.
6.  Conformal calibration and PI evaluation.
7.  Forecast energy calculation.
8.  Offline dashboard integration.
9.  Reproducibility checks, documentation, and research reporting.
10. Optional API/data-logger integration after access verification.

## 15. Open decisions

-   Final column names and timestamp timezone in the actual master file.
-   Final chronological proportions/dates for the four partitions.
-   Final look-back and architecture selected through validation.
-   Whether PI 95% is calibrated per horizon using split conformal or a
    justified rolling/adaptive variant.
-   Dashboard implementation framework and deployment target.
-   Whether an official SOLARMAN API credential and fresh data access
    can be obtained.
