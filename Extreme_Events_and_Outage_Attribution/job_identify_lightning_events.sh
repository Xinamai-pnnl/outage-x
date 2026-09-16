#!/usr/bin/env bash

#SBATCH -A <SLURM_ACCOUNT>
#SBATCH -N 1
#SBATCH --cpus-per-task=8
#SBATCH -t 00-00:20:00
#SBATCH -p short
#SBATCH --job-name=identify_lightning_events
#SBATCH --mail-type=begin,end,fail
#SBATCH --mail-user=<USER_EMAIL>
#SBATCH --output=logs/lightevent_%j.out
#SBATCH --error=logs/lightevent_%j.err


export HDF5_USE_FILE_LOCKING=FALSE
# Activate project environment (replace <ENV_NAME> with your conda environment)
# source ~/.bashrc
# conda activate <ENV_NAME>

python identify_lightning_events.py