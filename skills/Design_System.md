# Design System

## DTINS PV Power & Energy Forecasting Dashboard

**Design status:** Baseline visual specification\
**Product mode:** Research prototype --- Historical Replay\
**Primary audience:** Researcher, student, supervisor, and technical
evaluator

------------------------------------------------------------------------

## 1. Design principles

1.  **Research clarity over decoration.** Values, units, time ranges,
    and model status must be immediately understandable.
2.  **Actual and forecast must look different.** Historical measurements
    and future predictions must never be visually confused.
3.  **Uncertainty is first-class information.** PI 95% must be visible
    and explained, not hidden in a tooltip only.
4.  **Data freshness is explicit.** Always show the timestamp of the
    last source observation and the forecast origin.
5.  **No false real-time impression.** The first release is labelled
    Historical Replay.
6.  **Consistent units.** Power uses W/kW; energy uses Wh/kWh; voltage
    is V and is not the prediction target.

## 2. Brand and visual direction

Use a clean technical-instrumentation aesthetic: light neutral surfaces,
dark text, restrained green accents, and clear chart semantics. The
dashboard should feel appropriate for an engineering laboratory and
academic research demonstration.

### Color tokens

  ------------------------------------------------------------------------
  Token                    Hex                     Usage
  ------------------------ ----------------------- -----------------------
  `color.brand.900`        `#123B2A`               Primary dark green,
                                                   navigation/header

  `color.brand.700`        `#1F6B3A`               Primary actions and key
                                                   emphasis

  `color.brand.500`        `#3D9560`               Secondary green accent

  `color.brand.100`        `#E7F3EA`               Soft green surface

  `color.text.primary`     `#17231C`               Main text

  `color.text.secondary`   `#647067`               Supporting labels

  `color.surface`          `#FFFFFF`               Cards and main surfaces

  `color.canvas`           `#F5F7F5`               App background

  `color.border`           `#DDE5DE`               Dividers and card
                                                   outlines

  `color.actual`           `#2878B8`               Actual historical power
                                                   line

  `color.forecast`         `#1F8A55`               Forecast line

  `color.interval`         `#DCEFE2`               PI 95% shaded band

  `color.warning`          `#D99022`               Data-quality warning

  `color.error`            `#C74747`               Invalid data / blocking
                                                   errors

  `color.neutral`          `#89938C`               Persistence baseline /
                                                   secondary series
  ------------------------------------------------------------------------

Do not use color as the only means of communicating status. Pair color
with text, icons, or line styles.

## 3. Typography

Recommended stack: - Primary: Inter, system-ui, sans-serif. - Numeric
values: tabular numerals enabled. - Page title: 24--28 px, semibold. -
Section title: 16--18 px, semibold. - KPI value: 28--36 px, semibold. -
Body: 14--16 px. - Helper text and metadata: 12--13 px.

Use concise labels. Keep units adjacent to values, e.g. `1,420 W`,
`0.735 kWh`, `95% PI`.

## 4. Layout and spacing

-   Desktop-first responsive layout; minimum practical content width 320
    px.
-   Sidebar navigation on desktop; collapsible navigation on narrow
    screens.
-   Main content max width: approximately 1440 px.
-   Use a 12-column desktop grid where supported.
-   Spacing scale: 4, 8, 12, 16, 24, 32, 40 px.
-   Card radius: 10--12 px.
-   Card border: 1 px neutral border; subtle shadow only when needed.
-   Keep KPI cards aligned and equal in visual weight.
-   On mobile, stack KPI cards and charts vertically.

## 5. Application shell

### Header

-   Product name: `DTINS | PV Forecasting`
-   Subtitle: `On-Grid PV 3.5 kWp · Research Prototype`
-   Mode indicator: `Historical Replay`
-   Dataset timestamp / latest observation time.
-   Model version or `Model not loaded` state.

### Navigation

1.  Data Management
2.  Historical Monitoring
3.  LSTM Forecasting
4.  Model Validation

Do not expose a `Live` mode as an available operational feature in the
first release. If shown in a roadmap, mark it clearly as `Planned`.

## 6. Core components

### 6.1 KPI card

Required content: - Label. - Large value. - Unit. - Context or
horizon. - Data status / timestamp when relevant.

Required KPI cards on Forecasting page: 1. **Actual Power** --- latest
valid historical observation. 2. **Forecast Power** --- default focus
+30 min; user can inspect +5 through +30 min. 3. **Forecast Energy** ---
integrated 30-minute energy. 4. **Prediction Interval 95%** --- lower
and upper bounds for the selected horizon.

Never display illustrative example numbers as actual application output.

### 6.2 Horizon selector

Provide selectable horizons: - +5 min - +10 min - +15 min - +20 min -
+25 min - +30 min

Changing the selected horizon updates the highlighted forecast value and
PI bounds. It must not change the underlying forecast run.

### 6.3 Forecast chart

Chart requirements: - X-axis: timestamp with local timezone. - Y-axis:
power (W or kW). - Actual measurements: solid blue line. - Forecast:
dashed green line. - Persistence baseline: neutral dashed line when
comparison mode is enabled. - PI 95%: translucent green band between
lower and upper bounds. - Vertical divider or annotation between
observed and forecast periods. - Tooltip includes timestamp, series
name, value, and unit. - Legend explicitly distinguishes Actual,
Forecast, PI 95%, and optional Persistence.

Do not connect forecast points to historical points in a way that
implies they are measured observations. Use a visible forecast-origin
boundary.

### 6.4 Data-quality summary

Display: - Uploaded filename. - Number of rows. - Time coverage. - First
and last timestamp. - Expected interval: 5 minutes. - Duplicate
timestamp count. - Invalid/non-numeric power count. - Missing/irregular
interval count. - Negative power count. - Continuous valid segment
count. - Forecast readiness status.

Statuses: - `Ready` --- sufficient valid continuous input. - `Warning`
--- import completed but data limitations exist. - `Blocked` --- no
valid sequence for the selected model.

### 6.5 Model metadata panel

Show: - Model name/version. - Training timestamp. - Feature:
`Production Power (W)`. - Sampling interval: 5 minutes. - Look-back
length. - Number of outputs: 6. - Scaler metadata/version. - Calibration
method and calibration dataset identifier. - PI nominal level: 95%.

### 6.6 Metric cards and tables

Validation page: - MAE (W) - RMSE (W) - R² - PICP (%) - Mean interval
width (W)

Display metrics per horizon. Include persistence side-by-side with LSTM.
Lower MAE/RMSE is better; R² is generally higher-is-better; PICP should
be interpreted against nominal 95%; interval width is interpreted
alongside coverage.

## 7. Page specifications

### Page A --- Data Management

**Purpose:** Import and verify the historical time series.

Sections: 1. File uploader (Excel/CSV). 2. Column mapping (timestamp and
power). 3. Preview table. 4. Data-quality KPI row. 5. Time-series
continuity view. 6. Cleaning summary with row counts before/after. 7.
`Prepare dataset` action.

User feedback: - Success: file parsed and validation completed. -
Warning: import succeeded with flagged data-quality issues. - Error:
unsupported format, missing required columns, or no parseable
timestamps.

### Page B --- Historical Monitoring

**Purpose:** Explore the source data without implying live acquisition.

Sections: 1. Date range filter. 2. Historical power chart. 3. Summary:
maximum, mean, median, valid records. 4. Daily profile / selected-day
inspection. 5. Missing-interval markers where practical.

Label the page `Historical data`. Show source timestamp and timezone.

### Page C --- LSTM Forecasting

**Purpose:** Generate and inspect a forecast.

Sections: 1. Forecast origin and source freshness. 2. Four KPI cards. 3.
Horizon selector. 4. Actual-versus-forecast chart with PI 95%. 5.
Six-row forecast table (+5 through +30 min). 6. Forecast energy
calculation details. 7. Export prediction CSV.

Blocking states: - Model artifact missing. - Scaler mismatch. -
Insufficient continuous input points. - Input contains unresolved
invalid values. - Input sequence is stale relative to the selected
replay timestamp.

### Page D --- Model Validation

**Purpose:** Demonstrate scientific performance and uncertainty.

Sections: 1. Evaluation partition and model version. 2. Metrics table by
horizon. 3. LSTM-versus-persistence comparison chart. 4. Prediction
interval coverage and width. 5. Residual distribution /
residual-over-time plot. 6. Experiment configuration and downloadable
report.

Do not use the independent test set to tune hyperparameters or calibrate
intervals.

## 8. Interaction and content rules

-   Always show units with numerical values.
-   Use Indonesian locale formatting if the application language is
    Indonesian; retain standard machine-readable CSV values.
-   Show timezone explicitly (e.g. WIB) when known.
-   Tooltips explain terms such as `Look-back`, `Forecast origin`,
    `Persistence`, and `PI 95%`.
-   Confirm before replacing a previously loaded dataset if unsaved
    analysis would be lost.
-   Avoid unexplained abbreviations in user-facing labels.
-   Distinguish missing data from actual zero-power observations.
-   When the source is historical, use past-tense or historical labels
    rather than `Now` or `Live`.

## 9. Accessibility

-   Maintain readable contrast.
-   Support keyboard navigation for filters, selectors, and upload
    actions.
-   Give charts text summaries or accessible data tables.
-   Use labels in addition to colors and line styles.
-   Keep focus indicators visible.
-   Avoid tiny chart legends and dense table text.

## 10. Empty, loading, warning, and error states

  -----------------------------------------------------------------------
  State                               UI behavior
  ----------------------------------- -----------------------------------
  No dataset                          Explain accepted file types and
                                      required columns.

  Parsing                             Show progress and filename.

  Data warning                        Show warning count and link/section
                                      to inspect records.

  No continuous sequence              Explain required 5-minute
                                      continuity and block forecast.

  Model unavailable                   Explain that model artifact must be
                                      trained or loaded.

  Calibration unavailable             Do not display PI 95%; state that
                                      calibration is not available.

  Forecast ready                      Show forecast origin, six outputs,
                                      energy, and PI.

  Stale historical data               Show the actual source timestamp
                                      and a stale-data warning.
  -----------------------------------------------------------------------

## 11. Design acceptance checklist

-   [ ] Actual and forecast use distinct styles.
-   [ ] Forecast-origin boundary is visible.
-   [ ] PI 95% is shown as a band and as numerical bounds.
-   [ ] Four KPI cards include units and horizon/context.
-   [ ] Historical Replay is visible in the application shell.
-   [ ] Last observation timestamp is always available.
-   [ ] Data-quality warnings are visible and actionable.
-   [ ] Illustrative/demo values are never presented as measurements.
-   [ ] Mobile layout stacks without hiding critical information.
