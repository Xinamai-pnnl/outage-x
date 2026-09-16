#!/usr/bin/env bash

#SBATCH -A <SLURM_ACCOUNT>
#SBATCH -N 1
#SBATCH --cpus-per-task=8
#SBATCH -t 00-00:20:00
#SBATCH -p short
#SBATCH --job-name=fireevent
#SBATCH --mail-type=begin,end,fail
#SBATCH --mail-user=<USER_EMAIL>
#SBATCH --output=logs/fireevent_%j.out
#SBATCH --error=logs/fireevent_%j.err


export HDF5_USE_FILE_LOCKING=FALSE
# Activate project environment (replace <ENV_NAME> with your conda environment)
# source ~/.bashrc
# conda activate <ENV_NAME>

python identify_fire_events.py