import os
import pandas as pd
import warnings
from datetime import datetime
import pytz
import numpy as np


def process_hail_data(input_folder, output_folder):
    # Initialize dictionary to store county data
    counties = {}

    # Create output directory if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Iterate through each file in the input folder
    for filename in os.listdir(input_folder):
        if filename.endswith('.csv'):
            file_path = os.path.join(input_folder, filename)
            print(f"Processing {filename}...")
            
            # Read the CSV file
            df = pd.read_csv(file_path)

            # Filter for Hail events
            hail_df = df[df['EVENT_TYPE'] == 'Hail'].copy()

            # Parse timestamps with the confirmed format
            hail_df['BEGIN_DATE_TIME'] = pd.to_datetime(hail_df['BEGIN_DATE_TIME'], 
                                                       format='%d-%b-%y %H:%M:%S', 
                                                       errors='coerce')
            hail_df['END_DATE_TIME'] = pd.to_datetime(hail_df['END_DATE_TIME'], 
                                                     format='%d-%b-%y %H:%M:%S', 
                                                     errors='coerce')

            # Localize to UTC
            hail_df['BEGIN_DATE_TIME_UTC'] = hail_df['BEGIN_DATE_TIME'].dt.tz_localize('UTC', 
                                                                                     ambiguous='NaT', 
                                                                                     nonexistent='NaT')
            hail_df['END_DATE_TIME_UTC'] = hail_df['END_DATE_TIME'].dt.tz_localize('UTC', 
                                                                                   ambiguous='NaT', 
                                                                                   nonexistent='NaT')
            # Filter out events before 1980
            hail_df = hail_df[hail_df['BEGIN_DATE_TIME_UTC'] >= '1980-01-01'].copy()
            
            # Log dropped NaT rows
            if hail_df['BEGIN_DATE_TIME_UTC'].isna().any() or hail_df['END_DATE_TIME_UTC'].isna().any():
                print(f"Warning: {filename} contains {hail_df['BEGIN_DATE_TIME_UTC'].isna().sum()} invalid start times and "
                      f"{hail_df['END_DATE_TIME_UTC'].isna().sum()} invalid end times.")

            # Group by county (STATE_FIPS and CZ_FIPS)
            for (state_fips, county_fips), county_data in hail_df.groupby(['STATE_FIPS', 'CZ_FIPS']):
                # Validate and convert FIPS codes
                if pd.isna(state_fips) or pd.isna(county_fips):
                    print(f"Skipping NaN FIPS in {filename}: STATE_FIPS={state_fips}, CZ_FIPS={county_fips}")
                    continue
                try:
                    state_fips = int(float(state_fips))  # Convert float to int (e.g., 123.0 -> 123)
                    county_fips = int(float(county_fips))
                except (ValueError, TypeError):
                    print(f"Skipping non-numeric FIPS in {filename}: STATE_FIPS={state_fips}, CZ_FIPS={county_fips}")
                    continue

                # Create full FIPS code
                # full_fips = f"{state_fips:02d}{county_fips:03d}"
                full_fips = f"{state_fips:d}{county_fips:03d}"

                # Initialize county DataFrame if not yet created
                if full_fips not in counties:
                    counties[full_fips] = pd.DataFrame(columns=['timestamp', 'Hail'])              

                # Track events for logging
                hourly_events = {}

                # Process events for this county
                for _, row in county_data.iterrows():
                    event_start = row['BEGIN_DATE_TIME_UTC']
                    event_end = row['END_DATE_TIME_UTC']
                    magnitude = row['MAGNITUDE']
                    event_id = row['EVENT_ID']
                    begin_lat = row['BEGIN_LAT']
                    begin_lon = row['BEGIN_LON']
                    end_lat = row['END_LAT']
                    end_lon = row['END_LON']

                    # # Skip if timestamps are invalid
                    # if pd.isna(event_start) or pd.isna(event_end):
                    #     continue

                    # Normalize timestamps to start of hour
                    event_start = event_start.floor('H')
                    event_end = event_end.floor('H')

                    # Generate hourly range for the event
                    event_hours = pd.date_range(start=event_start, end=event_end, freq='H', tz='UTC')

                    # Create a temporary DataFrame for this event
                    event_df = pd.DataFrame({'timestamp': event_hours, 'Hail': magnitude})
                    event_df.set_index('timestamp', inplace=True)

                    for hour in event_hours:
                        if hour not in hourly_events:
                            hourly_events[hour] = []
                        hourly_events[hour].append({
                            'EVENT_ID': event_id,
                            'Magnitude': magnitude,
                            'Begin_Lat': begin_lat,
                            'Begin_Lon': begin_lon,
                            'End_Lat': end_lat,
                            'End_Lon': end_lon
                        })

                    # Update county DataFrame with max magnitude
                    if not counties[full_fips].empty:
                        counties[full_fips] = pd.concat([counties[full_fips], event_df]).groupby(level=0).max()
                    else:
                        counties[full_fips] = event_df

    # Save county data to CSV
    for full_fips, county_data in counties.items():
        output_filename = os.path.join(output_folder, f"{full_fips}_raw_hail.csv")
        
        # Create full hourly index (1980–2024)
        hourly_index = pd.date_range(start="1980-01-01", end="2024-12-31", freq="H", tz="UTC")
        full_df = pd.DataFrame(index=hourly_index, columns=['Hail'])
        full_df['Hail'] = 0  # Default to 0
        
        # Merge with county data
        if not county_data.empty:
            full_df.update(county_data)
        
        # Reset index and format timestamp
        full_df.reset_index(inplace=True)
        full_df.rename(columns={'index': 'timestamp'}, inplace=True)
        full_df['timestamp'] = full_df['timestamp'].dt.strftime('%Y_%m_%d_%H_UTC')
        
        # Save to CSV
        full_df.to_csv(output_filename, index=False)
        print(f"Saved {output_filename}")

input_folder = './data/ncei_storm_events/csv'
output_folder = './data/ncei_storm_events/output_hail'

if __name__ == '__main__':
    process_hail_data(input_folder, output_folder)