#!/usr/bin/env bash

#SBATCH -A <SLURM_ACCOUNT>
#SBATCH -N 1
#SBATCH --cpus-per-task=8
#SBATCH -t 00-10:20:00
#SBATCH --job-name=process_hail
#SBATCH --mail-type=begin,end,fail
#SBATCH --mail-user=<USER_EMAIL>
#SBATCH --output=logs/process_hail_%j.out
#SBATCH --error=logs/process_hail_%j.err


export HDF5_USE_FILE_LOCKING=FALSE
# Activate project environment (replace <ENV_NAME> with your conda environment)
# source ~/.bashrc
# conda activate <ENV_NAME>

python process_ncei_hail_events.py