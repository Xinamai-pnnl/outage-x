#!/bin/bash
#SBATCH -A <SLURM_ACCOUNT>
#SBATCH -N 2
#SBATCH --ntasks-per-node=24
#SBATCH -p short
#SBATCH -t 00-00:30:00
#SBATCH --job-name=countyfire
#SBATCH --mail-type=begin,end,fail
#SBATCH --mail-user=<USER_EMAIL>
#SBATCH --output=logs/countyfire_%j.out
#SBATCH --error=logs/countyfire_%j.err

export HDF5_USE_FILE_LOCKING=FALSE
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
# Activate project environment (replace <ENV_NAME> with your conda environment)
# source ~/.bashrc
# conda activate <ENV_NAME>

FIRE_DATA_DIR="./data/fire/02_FireData"
WEIGHTS_FILE="./ancillary_data/fire_grid_to_county_weight.parquet"
OUTPUT_DIR="./outputs/county_fire"
OUTPUT_SUFFIX="_County_Fire"
NUM_TASKS=32

# Loop over years 2001 to 2020
for year in {2001..2020}; do
    fire_file="${FIRE_DATA_DIR}/ComExDBM_${year}_Fires_V02.nc"
    if [ -f "$fire_file" ]; then
        echo "Processing $fire_file for year $year"
        python aggregate_fire_to_counties.py \
            --number-of-tasks "${NUM_TASKS}" \
            "$fire_file" \
            --variables FHS_c8c9 \
            --precisions 2 \
            --weights-file-path "${WEIGHTS_FILE}" \
            --output-directory "${OUTPUT_DIR}" \
            --output-filename-suffix "${OUTPUT_SUFFIX} \
    else
        echo "File $fire_file not found, skipping..."
    fi
done