import argparse
import datetime
from os.path import isfile, join
from typing import List
from joblib import Parallel, delayed
import pandas as pd
import xarray as xr
from functools import reduce
import numpy as np
import warnings
import os


def compute_county_stats(
    df: pd.DataFrame,
    columns: List[str],
    precisions: List[int],
    county_fips_key: str = 'FIPS',
    normalized_weights_key: str = 'weight',
) -> pd.DataFrame:
    """
    Compute max, min, and weighted mean for each variable by county.
    """
  
    stats = {
        'max': lambda g: g.max(),
        'min': lambda g: g.min(),
    }

    # Store each result
    results = []

    for label, func in stats.items():
        grouped = df[columns + [county_fips_key]].groupby(county_fips_key).agg(func).reset_index()
        grouped[columns] = grouped[columns].round({
            col: precisions[i] for i, col in enumerate(columns)
        })
        grouped = grouped.rename(columns={col: f"{col}_{label}" for col in columns})
        grouped[county_fips_key] = grouped[county_fips_key].astype(int)
        results.append(grouped)

    # Weighted mean
    weighted_df = df[columns].multiply(df[normalized_weights_key], axis=0)
    weighted_df[county_fips_key] = df[county_fips_key]
    weighted_grouped = weighted_df.groupby(county_fips_key, as_index=False).sum()
    weighted_grouped[county_fips_key] = weighted_grouped[county_fips_key].astype(int)
    weighted_grouped[columns] = weighted_grouped[columns].round({
        col: precisions[i] for i, col in enumerate(columns)
    })
    rename_dict = {col: f"{col}_wmean" for col in columns}
    weighted_grouped = weighted_grouped.rename(columns=rename_dict)
    results.append(weighted_grouped)

    final_df = reduce(lambda left, right: pd.merge(left, right, on=county_fips_key), results)
    return final_df


def write_output_file(
    df: pd.DataFrame,
    t: pd.Timestamp,
    output_directory: str,
    filename_suffix: str,
) -> None:
    """Write DataFrame to Parquet using standardized UTC timestamp."""
    os.makedirs(output_directory, exist_ok=True)
    name = os.path.join(output_directory, f'{t.strftime("%Y_%m_%d_%H_UTC")}{filename_suffix}.parquet')
    df.to_parquet(name, index=False)


def process_time_slice(
    df: pd.DataFrame,
    fire_variables: List[str],
    precisions: List[int],
    mapping: pd.DataFrame,
    output_directory: str,
    filename_suffix: str,
) -> None:
    """Calculate the county weighted stats for a single time slice."""
    write_output_file(
        compute_county_stats(
            mapping.merge(df, how='left', left_on='cell_index', right_index=True),
            fire_variables,
            precisions,
        ),
        df.time.iloc[0],
        output_directory,
        filename_suffix,
    )


def compute_fire_to_counties(
    fire_file: str,
    fire_variables: List[str],
    precisions: List[int],
    county_shapefile: str,
    weight_and_mapping_file: str,
    output_directory: str,
    output_filename_suffix: str = '_County_Mean_Fire',
    n_jobs: int = -1,
) -> None:
    """Aggregate fire NetCDF output data to county level using area weighted average."""
    begin_time = datetime.datetime.now()

    if not os.path.isfile(fire_file):
        raise FileNotFoundError(f'Fire file {fire_file} not found, exiting...')

    fire_ds = xr.open_dataset(fire_file)

    mapping = pd.read_parquet(weight_and_mapping_file)

    t_start = 0

    # Process each time slice in parallel
    Parallel(n_jobs=n_jobs)(
        delayed(process_time_slice)(
            fire_ds[fire_variables].isel(time=i).to_dataframe().reset_index(drop=True),
            fire_variables,
            precisions,
            mapping,
            output_directory,
            output_filename_suffix,
        ) for i in range(fire_ds.time.shape[0])[t_start:]
    )

    print('Elapsed time = ', datetime.datetime.now() - begin_time)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='Aggregate fire output data to county level using area weighted average.'
    )
    parser.add_argument(
        'file',
        metavar='/path/to/fire/output/file',
        type=str,
        help='path to the fire output file to aggregate (e.g., ComExDBM_2001_Fires_V02.nc)',
    )
    parser.add_argument(
        '-v',
        '--variables',
        nargs='+',
        type=str,
        default=['maxFRP_c8c9', 'FHS_c8c9', 'maxFRP_c9', 'FHS_c9', 'BA_km2'],
        help='list of variables to aggregate',
    )
    parser.add_argument(
        '-p',
        '--precisions',
        nargs='+',
        type=int,
        default=[2, 2, 2, 2, 2],
        help='list of precisions for the variables to aggregate',
    )
    parser.add_argument(
        '-s',
        '--shapefile-path',
        type=str,
        help='path to a shapefile (.shp) with county geometries',
        required=True,
    )
    parser.add_argument(
        '-w',
        '--weights-file-path',
        type=str,
        help='path to the weights file mapping grid cell to county and weight; will be created if it does not exist',
        required=True,
    )
    parser.add_argument(
        '-o',
        '--output-directory',
        type=str,
        help='path to which output should be written',
        required=True,
    )
    parser.add_argument(
        '--output-filename-suffix',
        type=str,
        help='string to append to the timestamp for the output file name',
        default='_County_Mean_Fire'
    )
    parser.add_argument(
        '-n',
        '--number-of-tasks',
        type=int,
        help='number of time slices to process in parallel',
        default=-1
    )
    args = parser.parse_args()
    compute_fire_to_counties(
        fire_file=args.file,
        fire_variables=args.variables,
        precisions=args.precisions,
        county_shapefile=args.shapefile_path,
        weight_and_mapping_file=args.weights_file_path,
        output_directory=args.output_directory,
        output_filename_suffix=args.output_filename_suffix,
        n_jobs=args.number_of_tasks,
    )