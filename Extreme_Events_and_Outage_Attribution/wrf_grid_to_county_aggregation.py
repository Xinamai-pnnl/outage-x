import argparse
import datetime
from os.path import isfile, join
from typing import List

# import geopandas as gpd
from joblib import Parallel, delayed
import pandas as pd
# import salem
import xarray as xr

from functools import reduce
import numpy as np
import warnings

    
def compute_county_stats(
    df: pd.DataFrame,
    columns: List[str],
    precisions: List[int],
    county_fips_key: str = 'FIPS',
    normalized_weights_key: str = 'weight',
    weighted_percentiles: List[int] = [50, 75, 80, 85, 90, 95]
) -> pd.DataFrame:
    """
    Compute max, min, 75th percentile, and 90th percentile for each variable by county.

    :param df: Input DataFrame
    :param columns: List of variable names to compute stats for
    :param precisions: Rounding precision for each variable
    :param county_fips_key: Column name for county FIPS
    :return: A merged DataFrame with all stats per county
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

    # weighted mean
    weighted_df = df[columns].multiply(df[normalized_weights_key],axis=0)
    weighted_df[county_fips_key] = df[county_fips_key]
    weighted_grouped = weighted_df.groupby(county_fips_key, as_index=False).sum()
    weighted_grouped[county_fips_key] = weighted_grouped[county_fips_key].astype(int)
    weighted_grouped[columns] = weighted_grouped[columns].round({
        col: precisions[i] for i, col in enumerate(columns)
    })  
    rename_dict = {col: f"{col}_wmean" for col in columns}
    weighted_grouped = weighted_grouped.rename(columns=rename_dict)
    results.append(weighted_grouped)
    
    # 2. Weighted percentiles using NumPy
    def compute_weighted_percentiles(group):
        row = {}
        for col in columns:
            values = group[col].to_numpy()
            weights = group[normalized_weights_key].to_numpy()
            for p in weighted_percentiles:
                val = np.percentile(values, p, weights=weights, method="inverted_cdf")
                colname = f"{col}_wp{p}"
                row[colname] = round(float(val), precisions[columns.index(col)])
        return pd.Series(row)

    wp_df = df.groupby(county_fips_key).apply(compute_weighted_percentiles,include_groups=False).reset_index()
    wp_df[county_fips_key] = wp_df[county_fips_key].astype(int)
    
    results.append(wp_df)
    

    
    final_df = reduce(lambda left, right: pd.merge(left, right, on=county_fips_key), results)
    return final_df


def write_output_file(
        df: pd.DataFrame,
        t: pd.Timestamp,
        output_directory: str,
        filename_suffix: str,
) -> None:
    """
    Write a dataframe to file, using a timestamp to generate a file name.

    :param pandas.DataFrame df: DataFrame to write to file
    :param pandas.Timestamp t: Timestamp that will be used to create the file name
    :param str output_directory: path to a directory to which to write the output file
    :param str filename_suffix: string to append to the timestamp for the output file name
    """
    name = join(output_directory, f'{t.strftime("%Y_%m_%d_%H_UTC")}{filename_suffix}.parquet')
    df.to_parquet(name, index=False)


def process_time_slice(
        df: pd.DataFrame,
        wrf_variables: List[str],
        precisions: List[int],
        mapping: pd.DataFrame,
        output_path: str,
        filename_suffix: str,
) -> None:
    """
    Calculate the county weighted mean for a single time slice of WRF output data.

    :param pandas.DataFrame df: DataFrame containing data for a single time slice
    :param list(str) wrf_variables: list of columns in the DataFrame for which to calculate mean by county
    :param list(int) precisions: list of precisions corresponding to the columns
    :param pandas.DataFrame mapping: DataFrame containing the mapping of df index to county and weight
    :param str output_path: path to which to write the output aggregation
    :param str filename_suffix: string to append to the timestamp for the output file name
    """
    write_output_file(
        compute_county_stats(
            mapping.merge(df, how='left', left_on='cell_index', right_index=True),
            wrf_variables,
            precisions,
        ),
        df.time.iloc[0],
        output_path,
        filename_suffix,
    )


def wrf_to_tell_counties(
        wrf_file: str,
        wrf_variables: List[str],
        precisions: List[int],
        county_shapefile: str = './2020_us_county.shp',
        weight_and_mapping_file: str = './grid_cell_to_county_weight.parquet',
        output_directory: str = './County_Output_Files',
        output_filename_suffix: str = '_County_Stats_Meteorology',
        n_jobs: int = -1,
) -> None:
    """
    Aggregate WRF output data to county level using area weighted average.

    :param str wrf_file: path to the WRF output file to aggregate
    :param list(str) wrf_variables: list of variables to aggregate
    :param list(int) precisions: list of precisions corresponding to the variables to aggregate
    :param str county_shapefile: path to a shapefile (.shp) with county geometries
    :param str weight_and_mapping_file: path to read or write a weights file which maps WRF grid cell to county weight
    :param str output_directory: path to which output should be written
    :param str output_filename_suffix: string to append to the timestamp for the output file name
    :param int n_jobs: number of time slices to process in parallel
    """

    begin_time = datetime.datetime.now()

    if not isfile(wrf_file):
        raise FileNotFoundError('No file to process, exiting...')

    wrf = xr.open_dataset(wrf_file)

    mapping = pd.read_parquet(weight_and_mapping_file)
    t_start = 0

    # create the remaining output for each time slice in each file
    Parallel(n_jobs=n_jobs)(
        delayed(process_time_slice)(
            wrf[wrf_variables].isel(time=i).to_dataframe().reset_index(drop=True),
            wrf_variables,
            precisions,
            mapping,
            output_directory,
            output_filename_suffix,
        ) for i in range(wrf.time.shape[0])[t_start:]
    )

    print('Elapsed time = ', datetime.datetime.now() - begin_time)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Read in a WRF output file and generate county level aggregations per time slice.'
    )
    parser.add_argument(
        'file',
        metavar='/path/to/WRF/output/file',
        type=str,
        help='path to the WRF output file to aggregate',
    )
    parser.add_argument(
        '-v',
        '--variables',
        nargs='+',
        type=str,
        default=['T2', 'Q2', 'U10', 'V10', 'SWDOWN', 'GLW'],
        help='list of variables to aggregate',
    )
    parser.add_argument(
        '-p',
        '--precisions',
        nargs='+',
        type=int,
        default=[2, 5, 2, 2, 2, 2],
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
        default='_County_Mean_Meteorology'
    )
    parser.add_argument(
        '-n',
        '--number-of-tasks',
        type=int,
        help='number of time slices to process in parallel',
        default=-1
    )
    args = parser.parse_args()
    wrf_to_tell_counties(
        wrf_file=args.file,
        wrf_variables=args.variables,
        precisions=args.precisions,
        county_shapefile=args.shapefile_path,
        weight_and_mapping_file=args.weights_file_path,
        output_directory=args.output_directory,
        output_filename_suffix=args.output_filename_suffix,
        n_jobs=args.number_of_tasks,
    )
