import salem
import dask
from glob import glob
import numpy as np
import gc
import os

# Replace these with your generic or relative paths for the public repository
INPUT_BASE_DIR = '/path/to/tgw-wrf-conus'
OUTPUT_BASE_DIR = '/path/to/output_directory'

# Define all scenarios and their corresponding start/end years
scenarios = {
    'historical': (1980, 2019),
    'rcp45cooler': (2020, 2059),
    'rcp45hotter': (2020, 2059)
}

for scenario, (start_year, end_year) in scenarios.items():
    wrf_path = f'{INPUT_BASE_DIR}/{scenario}_{start_year}_{end_year}/hourly/tgw_wrf_{scenario}_hourly_'

    for year in range(start_year,end_year+1):
        print (year)
        if year == start_year:
            spinup_file = f'{INPUT_BASE_DIR}/spinup_files/{scenario}/hourly/tgw_wrf_{scenario}_hourly_{start_year-1}-12-24_01_00_00.nc'
            wrf_files = sorted(glob(f'{wrf_path}{year}*'))
            wrf_files.insert(0,file_2019)      
        else:
            wrf_files = sorted(glob(f'{wrf_path}{year-1}*') + glob(f'{wrf_path}{year}*'))
            wrf_files = wrf_files[[idx for idx, s in enumerate(wrf_files) if f'{year}' in os.path.basename(s)][0]-1:]
            
        wrf_data = salem.open_mf_wrf_dataset(wrf_files)
        
        wrf_data['Prec'] = wrf_data['RAINC'] + wrf_data['RAINSH'] + wrf_data['RAINNC']
        wrf_data['Prec'].values = np.diff(wrf_data['Prec'].values, axis=0, prepend=np.array([wrf_data['Prec'][0].values]))
        wrf_data['Prec'].attrs['units'] = 'mm'
        
        wrf_data['Snow'] = wrf_data['SNOWNC']
        wrf_data['Snow'].values = np.diff(wrf_data['SNOWNC'].values, axis=0, prepend=np.array([wrf_data['SNOWNC'][0].values]))
        del wrf_data['Snow'].attrs['description']
        
        wrf_data['Wind'] = (wrf_data['U10']**2 + wrf_data['V10']**2) ** (1/2)
        wrf_data['Wind'].attrs['units'] = 'm/s'

        rain = wrf_data['Prec'] - wrf_data['Snow'] 
        rain = rain.clip(min=0)                       
        rain.attrs['units'] = 'mm'
        rain.attrs['description'] = 'Rain (Prec minus Snow)'
        rain.name = 'Rain'
        
        wrf_data['Rain'] = rain

        # # Select only the variables of interest
        selected_vars = ['T2','Prec', 'Snow', 'Wind', 'Rain']
        wrf_selected_data = wrf_data.sel(time=slice(f'{year}-01-01 01:00:00', f'{year+1}-01-01 00:00:00'))[selected_vars]
        wrf_selected_data.attrs = {}
        
        num_chunks = len(wrf_selected_data['time']) // 168
        if len(wrf_selected_data['time']) % 168 !=0:
            num_chunks +=1 
        
        out_path = f'{OUTPUT_BASE_DIR}/tgw_wrf_{scenario}_{start_year}_{end_year}_hourly_processed/'
        if not os.path.exists(out_path):
            os.mkdir(out_path)

        for i in range(52):
            start_idx = i * 168
            end_idx = (i + 1) * 168
        
            if i == 51:
                end_idx = len(wrf_selected_data['time'])  # Extend the last chunk to the end of the available data
                chunk_data = wrf_selected_data.isel(time=slice(start_idx, len(wrf_selected_data['time'])))     
            else:
                # Slice the data for the current chunk
                chunk_data = wrf_selected_data.isel(time=slice(start_idx, end_idx))
        
            chunk_start_time = str(chunk_data['time'].isel(time=0).values.astype('datetime64[s]'))
            chunk_start_time = chunk_start_time.replace('T', '_').replace('-', '_').replace(':', '_')
            
            output_path = f"{out_path}tgw_wrf_historical_hourly_{chunk_start_time}.nc"
            chunk_data.to_netcdf(output_path)
        
        print (year,  'done')
        del wrf_data
        del wrf_selected_data
        del chunk_data
        gc.collect()
    
print ('All done')