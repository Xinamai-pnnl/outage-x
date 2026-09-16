#!/usr/bin/env /bin/bash

#SBATCH -A outage-x
#SBATCH -N 2
#SBATCH --ntasks-per-node=1     
#SBATCH --cpus-per-task=64     
#SBATCH -t 00-04:40:00
#SBATCH --job-name cali38ID
#SBATCH --mail-type=begin,end,fail
#SBATCH --mail-user=your.email@example.com
#SBATCH --output=outage_attr_%j.out
#SBATCH --error=outage_attr_%j.err

export HDF5_USE_FILE_LOCKING=FALSE
export OMP_NUM_THREADS=1                 

CONDA_ENV_PYTHON="/path/to/your/conda/env/bin/python"

# Verify it exists (optional, but helpful)
echo "Using Python: $CONDA_ENV_PYTHON"
$CONDA_ENV_PYTHON -c "import pandas, numpy, sys; print('Python:', sys.version); print('pandas version:', pandas.__version__)"

# Run script with the correct python directly
srun $CONDA_ENV_PYTHON outage_attribution.py

