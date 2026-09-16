import pandas as pd
import os
from datetime import datetime

# Define the time range
start_date =  '2001-01-01 01:00:00'  
end_date = '2021-01-01 00:00:00'
time_series = pd.date_range(start=start_date, end=end_date, freq='h').tz_localize(None)  

# Function to process each county CSV
def process_county_csv(county_file, output_dir):
    county_fips = os.path.basename(county_file).split('_')[0]
    
    df = pd.read_csv(county_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='%Y_%m_%d_%H_UTC', utc=False).dt.tz_localize(None)

    # Create daily values DataFrame
    df['date'] = df['timestamp'].dt.date
    daily_df = df.groupby('date').first()[['FHS_c8c9_max', 'FHS_c8c9_min', 'FHS_c8c9_wmean']].reset_index()
    
    # Create a complete time series DataFrame
    full_df = pd.DataFrame({'timestamp': time_series})
    full_df['date'] = full_df['timestamp'].dt.date

    # Merge with daily data to assign the same value to all hours in the day
    merged_df = pd.merge(full_df, daily_df, on='date', how='left')
    merged_df[['FHS_c8c9_max', 'FHS_c8c9_min', 'FHS_c8c9_wmean']] = merged_df[['FHS_c8c9_max', 'FHS_c8c9_min', 'FHS_c8c9_wmean']].fillna(0)

    # Drop the 'date' column as it's no longer needed
    merged_df = merged_df.drop(columns=['date'])
    
    # Format timestamp back to the original string format
    merged_df['timestamp'] = merged_df['timestamp'].dt.strftime('%Y_%m_%d_%H_UTC')
    
    # Save the output
    output_file = os.path.join(output_dir, f'{county_fips}_extended.csv')
    merged_df.to_csv(output_file, index=False)
    print(f"Saved extended time series to {output_file}")

# Directory containing county CSV files (update as needed)
input_dir = './data/county_fire_output_2001-2020'  
output_dir = './data/county_fire_output_2001-2020_hourly'

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

# Process all county CSV files
county_files = [f for f in os.listdir(input_dir) if f.endswith('_raw.csv')]
for county_file in county_files:
    process_county_csv(os.path.join(input_dir, county_file), output_dir)