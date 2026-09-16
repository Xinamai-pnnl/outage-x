# OUTAGE-X

**County-Scale Historical Reconstructions and Scenario-Driven Predictions of Weather-Driven Power Outages in the Contiguous United States**

Ning Sun<sup>1</sup>, Tse-Chun Chen<sup>1</sup>, Lili Yao<sup>1</sup>, Zhangshuan Hou<sup>1</sup>, Julian Rice<sup>1</sup>, Karthik Balaguru<sup>1</sup>, Nathalie Voisin<sup>1,2</sup>, Vishvas Chalishazar<sup>1</sup>, Jason Fuller<sup>1</sup>

<sup>1</sup> Pacific Northwest National Laboratory, Richland, Washington, USA  
<sup>2</sup> University of Washington, Seattle, Washington, USA  

*Corresponding author: Ning Sun (ning.sun@pnnl.gov)*

---

## Reproduce Our Data

This repository contains the source code used to generate the datasets and reproduce the models presented in the paper. The code is divided into two main components:

### Part 1: [Placeholder for TC's Section]
*[Placeholder: TC will add their description and code references here]*

---

### Part 2: Extreme Event Library and Outage-Hazard Attribution
The scripts below detail the data processing pipeline used to generate the extreme weather event library and pair them with power outage events.

#### 1. WRF Meteorological Data Processing (Rain, Wind, etc.)
This module processes gridded weather outputs from the Weather Research and Forecasting (WRF) model, extracting variables and spatially aggregating them to the county level before identifying distinct extreme events.

* `extract_wrf_vars.py`
  * **Description:** Extracts target meteorological variables from the original WRF netCDF datasets.
  * **Outputs:** Formatted files such as `tgw_wrf_historical_hourly_{chunk_start_time}.nc`.

* `wrf_grid_to_county_aggregation.py`
  * **Description:** Aggregates gridded atmospheric output from WRF into county-level statistical summaries. The output retains a time-centric structure (one file per hour across CONUS). For every county and specified weather variable, it calculates:
    * **Absolute Extremes:** Maximum and minimum values within the county.
    * **Weighted Mean:** Area-weighted average across the county.
    * **Weighted Percentiles:** 50th, 75th, 80th, 85th, 90th, and 95th percentiles to capture the spatial distribution and intensity of the weather event.
  * **Execution:** `job_wrf_grid_to_county_aggregation.sh`

* `wrf_transpose_to_counties.py`
  * **Description:** Fundamentally reorganizes (transposes) the dataset's architecture from a "time-centric" format (hourly CONUS files) to a "location-centric" format (county-level time series).

* `identify_extreme_events.py`
  * **Description:** Performs extreme event identification and declustering on the hourly time-series data using Autocorrelation Function (ACF) decay to isolate independent meteorological events.
  * **Execution:** `job_identify_extreme_events.sh`

#### 2. Hail Data Processing
This module processes observed hail records into standardized time-series metrics.

* `process_ncei_hail_events.py`
  * **Description:** Processes raw historical NOAA/NCEI Storm Events Database CSV records to build a continuous, county-level, hourly time series of hail hazard intensity.
  * **Execution:** `job_process_ncei_hail_events.sh`

#### 3. Lightning Data Processing
This module converts raw satellite lightning observations into county-level binary occurrence datasets.

* `extract_iss_lis_flash_locations.py`
  * **Description:** Processes raw observation netCDF files from the ISS LIS (International Space Station Lightning Imaging Sensor) instrument to extract and compile lightning flash data over target years.

* `map_iss_lis_lightning_to_counties.py`
  * **Description:** Geospatially maps individual lightning flash observations to US counties and aggregates them into a unified, hourly formatted dataset.

* `generate_county_lightning_binary_series.py`
  * **Description:** Generates a continuous, county-level binary occurrence time series for lightning activity.

* `identify_lightning_events.py`
  * **Description:** Identifies and isolates discrete lightning events from the binary occurrence files.
  * **Execution:** `job_identify_lightning_events.sh`

#### 4. Fire Data Processing
This module aggregates gridded fire data to counties and generates continuous time series and event clusters.

* `aggregate_fire_to_counties.py`
  * **Description:** Performs spatial area-weighted aggregation of gridded fire datasets to US county boundaries across individual time slices.
  * **Execution:** `job_aggregate_fire_to_counties.sh`

* `reorganize_fire_hourly_to_county_timeseries.py`
  * **Description:** Restructures the data from time-slice parquet files into county-level time series CSVs.

* `generate_continuous_hourly_fire.py`
  * **Description:** Transforms daily fire data into a continuous, gap-free hourly time series.

* `binarize_county_fire_series.py`
  * **Description:** Converts continuous, county-level fire hazard metrics into a binary time series.
  * **Execution:** `job_binarize_county_fire_series.sh`

* `identify_fire_events_acf.py`
  * **Description:** Identifies and declusters discrete fire hazard events from continuous county-level binary time series using Autocorrelation Function (ACF) decay analysis.
  * **Execution:** `job_identify_fire_events_acf.sh`

#### 5. Outage Attribution 
This final module synthesizes the processed hazard data with historical power grid outage records to determine the specific meteorological drivers behind power failures.

* `outage_attribution.py`
  * **Description:** Attributes power outage events to specific extreme weather events by evaluating their spatial and temporal overlaps across U.S. counties.
  * **Execution:** `job_outage_attribution.sh`
