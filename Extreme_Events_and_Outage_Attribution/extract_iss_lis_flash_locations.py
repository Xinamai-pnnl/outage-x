# -*- coding: utf-8 -*-

########################################################
#
#        ISS LIS Lightning Flash Heat Map and Flash Location 
#        CSV File
#	
#        Decription: This code pulls ISS LIS NetCDF data files 
#        from a directory, extracts the flash coordinates from 
#        the files and generates a flash heat map plot. This code 
#        also compiles all lightning flash locations into a single 
#        CSV file, so they may be plotted using other software
# 
#        Authors: Amanda Markert and Essence Raphael
#        Information and Technology Systems Center (ITSC)
#        University of Alabama in Huntsville
#
########################################################

#### Import Python packages ####
import sys
import os
import glob
from netCDF4 import Dataset, num2date
import numpy as np
import csv
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.ticker as mticker
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER

BASE_DATA_DIR = "./data/iss_lis_lightning"
OUTPUT_DIR = "./outputs/iss_lis_lightning"
START_YEAR = 2018
END_YEAR = 2018

os.makedirs(OUTPUT_DIR, exist_ok=True)

for year in range(START_YEAR, END_YEAR + 1):
    print (year)
    file_path = os.path.join(BASE_DATA_DIR, str(int(year)))
    raw_files = glob.glob(os.path.join(file_path, '**', 'ISS_LIS_*.nc'), recursive=True)
    files = [os.path.normpath(i) for i in raw_files]    

    orbit_start = []
    orbit_end = []

    for i in files:
        datafile = Dataset(i,'r')
        start_value = datafile.variables['orbit_summary_TAI93_start'][:].data.tolist()
        start_value_units = datafile.variables['orbit_summary_TAI93_start']
        end_value = datafile.variables['orbit_summary_TAI93_end'][:].data.tolist()
        end_value_units = datafile.variables['orbit_summary_TAI93_end']
        orbit_start.append(start_value)
        orbit_end.append(end_value)

    #From the start and end times, calculate the minimum and maximum date of the files
    start_dates = num2date(orbit_start[:], start_value_units.units)
    stop_dates = num2date(orbit_end[:], end_value_units.units)

    begin_date_value = min(start_dates)
    end_date_value = max(stop_dates)

    #Create text and numerical dates to use in file names and plot title
    begin_date = begin_date_value.strftime("%B %d, %Y")
    end_date = end_date_value.strftime("%B %d, %Y")
    begin_int = begin_date_value.strftime("%Y%m%d")
    end_int = end_date_value.strftime("%Y%m%d")

    #Create CSV file and destination
    csvfile = os.path.join(OUTPUT_DIR, 'isslis_flashloc_'+ begin_int + '_' + end_int +'.csv')
    
    #Extract lightning flash locations
    #Create empty arrays to populate lightning flash location coordinates 
    flash_lat = np.array([]) #latitude
    flash_lon = np.array([]) #longitude
    flash_TAI93_time = np.array([])

    #Loop through list of NetCDF files and for each file, extract the lightning flash latidude
    #and longitude, adding them to the respective empty array (flash_lat and flash_lon)
    for i in files:
        datafile = Dataset(i, 'r')
        required_vars = ['lightning_flash_lat', 'lightning_flash_lon', 'lightning_flash_TAI93_time']
        
        # Check if all required variables are present in the dataset
        if all(var in datafile.variables for var in required_vars):

            flash_lat = np.concatenate([flash_lat,datafile.variables['lightning_flash_lat'][:]]) #add to array
            flash_lon = np.concatenate([flash_lon,datafile.variables['lightning_flash_lon'][:]]) #add to array
            flash_TAI93_time = np.concatenate([flash_TAI93_time,datafile.variables['lightning_flash_TAI93_time'][:]]) #add to array
        else:
            # If any required variable is missing, skip the file and print the filename
            print(f"Skipping file {i}, missing required variables")

    flash_time_temp = num2date(flash_TAI93_time, datafile.variables['lightning_flash_TAI93_time'].units) #
    flash_time = [time.strftime("%d.%m.%Y-%H:%M:%S") for time in flash_time_temp]

    print (len(flash_TAI93_time))

    
    #Create CSV files of values from the populated flash_lat/lon arrays  
    with open(csvfile, 'w', newline='') as myfile:
        writer = csv.writer(myfile)
        writer.writerows(zip(["flash_lat"], ["flash_lon"], ["flash_time"])) #Define headers in row (zip creates columns)
        writer.writerows(zip(flash_lat,flash_lon, flash_time)) #Define data rows (zip creates columns)
    
    
    
    #Create plot of lightning flash location heat map
    plt.figure(figsize=((20,20))) #Set plot dimensions
    map = plt.axes(projection=ccrs.PlateCarree(central_longitude=0.0))
    gl = map.gridlines(crs=ccrs.PlateCarree(central_longitude=0.0), draw_labels=True, linewidth=0.8, alpha=0.5, color='white', linestyle='--')
    lightning = map.hexbin(flash_lon, flash_lat, gridsize=300, bins='log',cmap='jet', mincnt=1 ,zorder=10) #Bin flash counts into hexbins using a gridsize of your choice

    #Draw geographic boundaries and meridians/parallels
    # map.set_extent([-180, 180,-90, 90])
    map.set_extent([-125, -66.93457, 24.396308, 49.384358])
    map.coastlines(color='white')
    map.add_feature(cfeature.LAND, facecolor='gray')
    map.add_feature(cfeature.BORDERS, edgecolor='white')
    map.add_feature(cfeature.OCEAN, facecolor='black')
    gl.ylocator = mticker.FixedLocator([-90, -60, -30, 0 ,30, 60, 90])
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER
    gl.xlabels_top=False
    gl.ylabels_right=False

    #Create colorbar
    cbar = plt.colorbar(lightning, orientation='horizontal', pad=0.02, aspect=50) 
    cbar.set_label('Flash Count', fontsize=12) #Remember to change label
        
    #Create plot title based on file dates
    if begin_date != end_date:
        plot_title = 'ISS LIS Detected Lightning Flash Locations ' + begin_date + ' - ' + end_date
    else:
        plot_title = 'ISS LIS Detected Lightning Flash Locations ' + end_date

    plt.title(plot_title, fontsize = 18) 

    #Save the plot as an image
    plt.savefig(os.path.join(OUTPUT_DIR, 'isslis_flashloc_'+ begin_int + '_' + end_int +'_plot.png'), bbox_inches='tight')