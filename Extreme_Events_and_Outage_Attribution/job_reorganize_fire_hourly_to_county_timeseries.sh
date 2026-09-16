#!/usr/bin/env bash

#SBATCH -A your_project_account
#SBATCH -N 1
#SBATCH -t 00-01:00:00
#SBATCH --job-name fire_by_county
#SBATCH --mail-type=begin,end,fail
#SBATCH --mail-user=your.email@example.com
#SBATCH --output=fire_by_county_%j.log

export HDF5_USE_FILE_LOCKING=FALSE

# Define path to your specific Python environment
export PATH="/path/to/your/conda/env/bin:$PATH"

python reorganize_fire_hourly_to_county_timeseries.py