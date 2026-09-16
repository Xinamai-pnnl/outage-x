import pandas as pd
import os
import glob
import time
from collections import defaultdict


INPUT_DIR = './County_Stats_Output_File/'
OUTPUT_DIR = './County_Stats_Output_Files_bycounty'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define the desired column order
cols = [
    'timestamp',
    'T2_max', 'Prec_max', 'Snow_max', 'Rain_max', 'Wind_max',
    'T2_min', 'Prec_min', 'Snow_min', 'Rain_min', 'Wind_min',
    'T2_wmean', 'Prec_wmean', 'Snow_wmean', 'Rain_wmean', 'Wind_wmean',
    'T2_wp50', 'T2_wp75', 'T2_wp80', 'T2_wp85', 'T2_wp90', 'T2_wp95',
    'Prec_wp50', 'Prec_wp75', 'Prec_wp80', 'Prec_wp85', 'Prec_wp90', 'Prec_wp95',
    'Snow_wp50', 'Snow_wp75', 'Snow_wp80', 'Snow_wp85', 'Snow_wp90', 'Snow_wp95',
    'Rain_wp50', 'Rain_wp75', 'Rain_wp80', 'Rain_wp85', 'Rain_wp90', 'Rain_wp95',
    'Wind_wp50', 'Wind_wp75', 'Wind_wp80', 'Wind_wp85', 'Wind_wp90', 'Wind_wp95'
]

# Define your year range
years = range(1980, 1991)  # Adjust as needed

batch_size = 100  # Number of files to process at once

for year in years:
    print(f"Processing year: {year}")
    start_time = time.time()

    # Find all files for this year
    pattern = os.path.join(input_dir, f'{year}_*_UTC_County_Stats_Meteorology.parquet')
    year_files = sorted(glob.glob(pattern))

    if not year_files:
        print(f"No files found for {year}, skipping.")
        continue

    total_batches = len(year_files) // batch_size + int(len(year_files) % batch_size != 0)

    fips_data = defaultdict(list)

    for i in range(0, len(year_files), batch_size):
        batch_files = year_files[i:i + batch_size]
        dfs = []

        for file in batch_files:
            df = pd.read_parquet(file)
            timestamp = '_'.join(os.path.basename(file).split('_')[:5])
            df['timestamp'] = timestamp
            dfs.append(df)

        # Combine this batch
        df_batch = pd.concat(dfs, ignore_index=True)

        # Group by FIPS and collect
        for fips, df_group in df_batch.groupby('FIPS'):
            df_group = df_group.drop(columns='FIPS')
            fips_data[fips].append(df_group)

        print(f"Finished batch {i // batch_size + 1}/{total_batches}", end='\r')

    read_duration = time.time() - start_time
    print(f"\nFinished reading {len(year_files)} files for {year} in {read_duration:.2f} seconds.")

    start_time_write = time.time()
    for fips, dfs in fips_data.items():
        
        df_out = pd.concat(dfs).sort_values('timestamp')
        # Reorder columns
        df_out = df_out[[c for c in cols if c in df_out.columns]]

        output_file = os.path.join(output_dir, f'{fips}_raw.csv')

        if os.path.exists(output_file):
            df_out.to_csv(output_file, mode='a', header=False, index=False)
        else:
            df_out.to_csv(output_file, index=False)

    write_duration = time.time() - start_time_write
    print(f"\nFinished writing {len(year_files)} files for {year} in {write_duration:.2f} seconds.")
    print(f"Done writing year {year}\n")
