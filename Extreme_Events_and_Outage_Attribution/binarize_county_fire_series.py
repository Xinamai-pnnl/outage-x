import pandas as pd
import numpy as np
import glob
import os
from multiprocessing import Pool, cpu_count
from tqdm import tqdm
import re

# ==== USER SETTINGS ====
INPUT_DIR = '/rcfs/projects/outage-x/yaol088/fire/county_fire_output_by_county_1980-2020/'
THRESHOLD = 5.0  # Threshold for binary (>= 1.0)
OUTPUT_DIR = f"./outputs/fire/county_fire_binary_thrshld{str(THRESHOLD).replace('.', 'p')}"
os.makedirs(OUTPUT_DIR, exist_ok=True)  

FILE_GLOB = "*.csv"  
TIME_COL = 'timestamp'
VALUE_COL = 'FHS_c8c9_wmean'  # Column to binarize
BINARY_COL = 'fire'  # Name of the binary column
NUM_PROCESSES = max(1, cpu_count() - 1)  # Use all but one CPU core
# ========================

def county_from_filename(filename: str) -> str:
    """
    Extract county FIPS from filename assuming format like {fips}_*.csv
    """
    m = re.match(r"^(\d{4,5})_.*\.csv$", filename)
    if not m:
        raise ValueError(f"Cannot parse county FIPS from filename: {filename}")
    return m.group(1)#.zfill(5)

def process_county(filename: str) -> None:
    """
    Process a single county file, create binary 'fire' column, and save to output directory.
    """
    try:
        # Extract FIPS from filename
        fips = county_from_filename(filename)
        print(f"Processing county {fips} ({filename})")
        
        # Read input file
        input_path = os.path.join(INPUT_DIR, filename)
        df = pd.read_csv(input_path)
        
        # Validate required columns
        if TIME_COL not in df.columns or VALUE_COL not in df.columns:
            print(f"[WARN] Missing {TIME_COL} or {VALUE_COL} in {filename}, skipping.")
            return
        
        # Create binary column: 1 if >= THRESHOLD, 0 otherwise (NaN treated as 0 via comparison)
        df[BINARY_COL] = (df[VALUE_COL] >= THRESHOLD).astype(int)
        
        # Create binary DataFrame with timestamp and binary column
        df_binary = df[[TIME_COL, BINARY_COL]].copy()
        
        # Save output
        output_path = os.path.join(OUTPUT_DIR, f'{fips}_binary_fire.csv')
        df_binary.to_csv(output_path, index=False)
        print(f"[OK] Saved binary file for county {fips} -> {output_path}")
        
    except Exception as e:
        print(f"[ERR] Failed to process {filename}: {e}")

def main():
    # Get list of input files
    file_list = glob.glob(os.path.join(INPUT_DIR, FILE_GLOB))
    print(f"Found {len(file_list)} county files to process")
    
    # Process files in parallel with progress bar
    with Pool(processes=NUM_PROCESSES) as pool:
        list(tqdm(pool.imap(process_county, [os.path.basename(f) for f in file_list]), total=len(file_list)))
    
    print("Done")

if __name__ == "__main__":
    main()