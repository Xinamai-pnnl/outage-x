import pandas as pd
import os 
from tqdm import tqdm
import geopandas as gpd
import numpy as np

INPUT_CSV = "./outputs/iss_lis_lightning/lightning_within_conus_county_processed.csv"
COUNTY_SHAPEFILE = "./ancillary_data/2020_us_county_WGS84_CONUS.shp"
OUTPUT_DIR = "./outputs/iss_lis_lightning/county_lightning_binary_csvs"

START_DATE = "1980-01-01 01:00:00"
END_DATE = "2025-01-01 00:00:00"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load spatially joined lightning observations
merged_df = pd.read_csv(INPUT_CSV)
full_time_index = pd.date_range(start=start, end=end, freq='H')
timestamp_strings = full_time_index.strftime("%Y_%m_%d_%H_UTC")

template_df = pd.DataFrame({'timestamp': timestamp_strings})
template_df['lightning'] = pd.NA

lightning_df = merged_df[['GEOID', 'utc_hour_str']].drop_duplicates() # when a county has lightning in a hour, tag 1, no matter how many lightning was observed within the same county in the same hour

county_gdf = gpd.read_file(COUNTY_SHAPEFILE)
all_counties = county_gdf['GEOID'].astype(str).unique()

output_dir = '/pscratch/sd/l/liliyao/outage-x/iss_lis_lightning/county_lightning_binary_csvs'
os.makedirs(output_dir, exist_ok=True)

for geoid in tqdm(all_counties, desc="Processing counties"):
    
    county_df = template_df.copy()

    # Find lightning hours for this county
    lightning_hours = lightning_df.loc[lightning_df['GEOID'] == int(geoid), 'utc_hour_str']
    county_df.loc[county_df['timestamp'].isin(lightning_hours), 'lightning'] = 1

    # Strip leading zeros from GEOID
    geoid_stripped = str(int(geoid))
    out_file = os.path.join(OUTPUT_DIR, f"{geoid_stripped}_binary_lightning.csv")
    county_df.to_csv(out_file, index=False)

