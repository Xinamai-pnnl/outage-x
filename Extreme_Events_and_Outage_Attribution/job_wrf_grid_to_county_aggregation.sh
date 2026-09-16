#!/usr/bin/env /bin/bash

#SBATCH -A <SLURM_ACCOUNT>
#SBATCH -N 2
#SBATCH --ntasks-per-node=24
#SBATCH -t 00-15:00:00
#SBATCH --job-name <job-name>
#SBATCH --mail-type=begin,end,fail
#SBATCH --mail-user=<USER_EMAIL>

# ------------------------------------------------------------------------------
# Environment Setup
# ------------------------------------------------------------------------------
export HDF5_USE_FILE_LOCKING=FALSE
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
# Activate project environment (replace <ENV_NAME> with your conda environment)
# source ~/.bashrc
# conda activate <ENV_NAME>

PROJECT_DIR="."
DATA_DIR="${PROJECT_DIR}/tgw_wrf_historical_hourly"
ANCILLARY_DIR="${PROJECT_DIR}/ancillary_data"
OUTPUT_DIR="${PROJECT_DIR}/County_Stats_Output_Files"


parallel --retries 3 --jobs 32 'python wrf_to_counties_stats.py \
    --number-of-tasks 32 \
    --variables T2 Prec Snow Wind Rain \
    --precisions 4 4 4 4 4 \
    --shapefile-path ${ANCILLARY_DIR}/2020_us_county.shp \
    --weights-file-path ${ANCILLARY_DIR}/wrf_grid_cell_to_county_weight.parquet \
    --output-directory ${OUTPUT_DIR} \
    --output-filename-suffix _County_Stats_Meteorology \
    {}' ::: "${DATA_DIR}"/tgw_wrf_historical_hourly_*.nc
