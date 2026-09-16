import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from astropy.time import Time, TimeDelta

DATA_DIR = "./data/iss_lis_lightning"

SHAPEFILE_PATH = "./ancillary_data/2020_us_county_WGS84.shp"
OUTPUT_FILE = "./outputs/iss_lis_lightning/lightning_within_conus_county_processed.csv"

county_gdf = gpd.read_file(SHAPEFILE_PATH)
county_gdf = county_gdf[['GEOID', 'geometry']]

file_list= ['isslis_flashloc_20170301_20180101.csv',
            'isslis_flashloc_20180101_20190101.csv',
            'isslis_flashloc_20190101_20191231.csv',
            'isslis_flashloc_20200101_20210101.csv',
            'isslis_flashloc_20210101_20220101.csv', 
            'isslis_flashloc_20220101_20230101.csv',
            'isslis_flashloc_20230101_20231116.csv']

all_lightning = []

for file in file_list:
    print(f"Processing {file}...")
    
    lightning_df = pd.read_csv(f'{path}{file}')
    
    
    lightning_df = lightning_df[
        (lightning_df['flash_lon'] >= -126) & 
        (lightning_df['flash_lon'] <= -66) &
        (lightning_df['flash_lat'] >= 24) & 
        (lightning_df['flash_lat'] <= 51)
    ]
    
    geometry = [Point(lon, lat) for lon, lat in zip(lightning_df['flash_lon'],lightning_df['flash_lat'])]
    lightning_gdf = gpd.GeoDataFrame(lightning_df, geometry=geometry, crs="EPSG:4326")
    
    lightning_within_conus = gpd.sjoin(lightning_gdf, county_gdf, how='inner', predicate='intersects')
    lightning_within_conus = lightning_within_conus[['flash_lat', 'flash_lon', 'flash_time', 'geometry', 'GEOID']]
    
    lightning_within_conus['flash_time'] = pd.to_datetime(lightning_within_conus['flash_time'],format="%d.%m.%Y-%H:%M:%S",utc=True)
    # --- Generate hourly UTC timestamp string ---
    lightning_within_conus['utc_hour_str'] = lightning_within_conus['flash_time'].apply(
        lambda x: f"{x.year:04d}_{x.month:02d}_{x.day:02d}_{x.hour:02d}_UTC"
    )
    
    lightning_within_conus = lightning_within_conus.drop(columns='geometry')

    all_lightning.append(lightning_within_conus)

merged_df = pd.concat(all_lightning, ignore_index=True)
merged_df.to_csv(OUTPUT_FILE, index=False)
print ('done')