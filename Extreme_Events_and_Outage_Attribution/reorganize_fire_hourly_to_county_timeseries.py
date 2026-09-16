import pandas as pd
import os
import glob
import time
from collections import defaultdict

input_dir = 'path/to/the/input_fire_by_year_folder/'
output_dir = 'path/to/the/output_fire_by_county_folder/'
os.makedirs(output_dir, exist_ok=True)

# Define the desired column order
cols = [
    'timestamp', 'FHS_c8c9_wmean'
]



# Define your year range
years = range(2001, 2021)  

batch_size = 100  # Number of files to process at once

for year in years:
    print(f"Processing year: {year}")
    start_time = time.time()

    # Find all files for this year
    pattern = os.path.join(input_dir, f'{year}_*_UTC_County_Fire.parquet')
    year_files = sorted(glob.glob(pattern))

    if not year_files:
        print(f"No files found for {year}, skipping.")
        continue

    total_batches = len(year_files) // batch_size + int(len(year_files) % batch_size != 0)
    # print(f" Found {len(year_files)} files, processing in {total_batches} batches of {batch_size}...")

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
    # Write or append per FIPS
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
    print(f"\nFinished writting {len(year_files)} files for {year} in {write_duration:.2f} seconds.")
    print(f"Done writing year {year}\n")
