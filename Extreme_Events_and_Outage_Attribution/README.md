# Extreme Event Library and Outage Attribution

This folder contains the Python and Slurm shell scripts used to process raw meteorological data, identify extreme weather events, and attribute power outages to these events. 

For detailed descriptions of each script's functionality, please refer to the main repository README.

## File Manifest

### 1. WRF Meteorological Data Processing
* `extract_wrf_vars.py`
* `wrf_grid_to_county_aggregation.py`
* `job_wrf_grid_to_county_aggregation.sh`
* `wrf_transpose_to_counties.py`
* `identify_extreme_events.py`
* `job_identify_extreme_events.sh`

### 2. Hail Data Processing
* `process_ncei_hail_events.py`
* `job_process_ncei_hail_events.sh`

### 3. Lightning Data Processing
* `extract_iss_lis_flash_locations.py`
* `map_iss_lis_lightning_to_counties.py`
* `generate_county_lightning_binary_series.py`
* `identify_lightning_events.py`
* `job_identify_lightning_events.sh`

### 4. Fire Data Processing
* `aggregate_fire_to_counties.py`
* `job_aggregate_fire_to_counties.sh`
* `reorganize_fire_hourly_to_county_timeseries.py`
* `generate_continuous_hourly_fire.py`
* `binarize_county_fire_series.py`
* `job_binarize_county_fire_series.sh`
* `identify_fire_events_acf.py`
* `job_identify_fire_events_acf.sh`

### 5. Outage Attribution
* `outage_attribution.py`
* `job_outage_attribution.sh`
