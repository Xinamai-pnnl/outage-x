import pandas as pd
import numpy as np
import glob
import os
from multiprocessing import Pool, cpu_count
from tqdm import tqdm
from intervaltree import Interval, IntervalTree
from typing import List, Dict, Optional
from itertools import combinations
from datetime import datetime, timedelta
import re
from mpi4py import MPI  

# Initialize MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()  # Node ID (0 or 1 for two nodes)
size = comm.Get_size()  # Number of nodes (should be 2)

# ==== USER SETTINGS ====
OUTAGE_DIR = "path/to/the/outage_events/folder"
EXTREME_DIRS = {
    "rain": "path/to/the/rain_event/folder",
    "wind": "path/to/the/wind_event/folder",
    "snow": "path/to/the/snow_event/folder",
    "fire": "path/to/the/fire_event/folder",
    "hail": "path/to/the/hail_event/folder",
    "lightning": "path/to/the/lightning_event/folder"
}

OUTPUT_DIR = "path/to/the/output/folder"
os.makedirs(OUTPUT_DIR, exist_ok=True)

FILE_GLOB_OUTAGE = "events_*.csv"  
FILE_GLOB_EXTREME = "*_events_*.csv"  
FIPS_CLUSTER_FILE = "path/to/the/metadata/wrf_county_cluster.csv"

TIME_CUTOFF = pd.Timestamp("2024-12-31 23:59:59", tz="UTC") 
BUFFER_HOURS = 24  # Buffer period (hours) for associating outages with extremes

NUM_PROCESSES = int(os.environ.get('SLURM_CPUS_PER_TASK', 64))
SUMMARY_PATH = os.path.join(OUTPUT_DIR, "outage_attribution_summary.csv")


# ========================
def county_from_filename(filename: str, suffix: str = "_outages.csv") -> str:
    """Extract county FIPS from filename, handling different suffixes.
    
    For outages: Matches 'events_{fips}.csv' (e.g., events_50025.csv).
    For extreme events: Matches '{type}_events_{fips}.csv' (e.g., rain_events_50025.csv).
    """
    if suffix == "_outages.csv":
        pattern = r"^events_(\d{4,5})\.csv$"
    else:
        pattern = r"^\w+_events_(\d{4,5})\.csv$"  # Matches {type}_events_{fips}.csv
    m = re.match(pattern, os.path.basename(filename))
    if not m:
        raise ValueError(f"Cannot parse county FIPS from filename: {filename}")
    return m.group(1)#.zfill(5)

def build_interval_tree(events: pd.DataFrame) -> IntervalTree:
    """Build an interval tree from event start/end times."""
    tree = IntervalTree()
    for _, row in events.iterrows():
        start = row["start_time"]
        end = row["end_time"] + pd.Timedelta(seconds=1)  # Include end time
        tree[start:end] = row["event_id"]
    return tree

def process_county(outage_file: str) -> Optional[Dict]:
    try:
        county_fips = county_from_filename(outage_file)
        print(f"[INFO] Processing county {county_fips} for file {outage_file}")

        # Load fips-cluster mapping
        try:
            fips_cluster = pd.read_csv(FIPS_CLUSTER_FILE, dtype={'fips': str})
            if not all(col in fips_cluster.columns for col in ['fips', 'cluster']):
                raise ValueError(f"Missing 'fips' or 'cluster' columns in {FIPS_CLUSTER_FILE}")
        except Exception as e:
            print(f"[ERR] Failed to load {FIPS_CLUSTER_FILE}: {e}")
            return None

        # Check if this county_fips exists in the CSV; if not, skip
        if county_fips not in fips_cluster['fips'].values:
            print(f"[INFO] County {county_fips} not found in {FIPS_CLUSTER_FILE}, skipping.")
            return None

        # Get the cluster for this fips
        cluster_row = fips_cluster[fips_cluster['fips'] == county_fips]
        cluster_id = cluster_row['cluster'].values[0]   
        print(f"[INFO] County {county_fips} belongs to cluster {cluster_id}")    

        # Get all fips in the same cluster
        cluster_fips_list = fips_cluster[fips_cluster['cluster'] == cluster_id]['fips'].tolist()
        print(f"[INFO] Cluster {cluster_id} includes fips: {cluster_fips_list}")

        # Load outage data
        outage_path = os.path.join(OUTAGE_DIR, outage_file)
        print(f"[INFO] Attempting to read {outage_path}")
        try:
            outages = pd.read_csv(outage_path, skip_blank_lines=True, on_bad_lines='warn')
            print(f"[INFO] Successfully read {outage_file}. Columns: {outages.columns.tolist()}, Rows: {len(outages)}")
        except pd.errors.EmptyDataError as e:
            print(f"[ERR] {outage_file}: EmptyDataError - {e}")
            return None
        except pd.errors.ParserError as e:
            print(f"[ERR] {outage_file}: ParserError - {e}. Trying alternative parsing.")
            try:
                outages = pd.read_csv(outage_path, skip_blank_lines=True, on_bad_lines='skip')
                print(f"[INFO] Successfully read {outage_file} with alternative parsing. Columns: {outages.columns.tolist()}, Rows: {len(outages)}")
            except Exception as e2:
                print(f"[ERR] {outage_file}: Failed alternative parsing - {e2}")
                return None
        except Exception as e:
            print(f"[ERR] {outage_file}: Unexpected error during CSV read - {e}")
            return None

        if outages.empty:
            print(f"[WARN] {outage_file}: File is empty after parsing, skipping.")
            return None
        if not all(col in outages.columns for col in ["start_time", "end_time"]):
            print(f"[WARN] Missing start_time or end_time in {outage_path}, skipping.")
            return None

        # Parse timestamps and filter by cutoff
        outages["start_time"] = pd.to_datetime(outages["start_time"], utc=True, errors="coerce")
        outages["end_time"] = pd.to_datetime(outages["end_time"], utc=True, errors="coerce")
        if outages[["start_time", "end_time"]].isna().any().any():
            bad_rows = outages[outages[["start_time", "end_time"]].isna().any(axis=1)].head(5)
            print(f"[WARN] Invalid timestamps in {outage_path}: {bad_rows[['start_time', 'end_time']].to_dict()}")
        outages = outages.dropna(subset=["start_time", "end_time"])
        outages = outages[outages["start_time"] <= TIME_CUTOFF].copy()
        if outages.empty:
            print(f"[INFO] No valid outages before 2024 for {county_fips}, skipping.")
            return None

        # Add outage_id
        outages["outage_id"] = [f"{county_fips}_{i+1}" for i in range(len(outages))]

        # Load extreme events from ALL fips in the cluster
        extreme_events = []
        for cluster_fips in cluster_fips_list:
            for type_name, dir_path in EXTREME_DIRS.items():
                extreme_file = os.path.join(dir_path, f"{type_name}_events_{cluster_fips}.csv")
                if not os.path.exists(extreme_file):
                    print(f"[INFO] No {type_name} events file for {cluster_fips}: {extreme_file}")
                    continue
                try:
                    df = pd.read_csv(extreme_file, skip_blank_lines=True, on_bad_lines='warn')
                    print(f"[INFO] Successfully read {extreme_file}. Columns: {df.columns.tolist()}, Rows: {len(df)}")
                except Exception as e:
                    print(f"[ERR] {extreme_file}: Failed to read extreme events file - {e}")
                    continue
                if not all(col in df.columns for col in ["start_time", "end_time"]):
                    print(f"[WARN] Missing start_time or end_time in {extreme_file}, skipping.")
                    continue
                df["type"] = type_name
                df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
                df["end_time"] = pd.to_datetime(df["end_time"], utc=True, errors="coerce")
                if df[["start_time", "end_time"]].isna().any().any():
                    bad_rows = df[df[["start_time", "end_time"]].isna().any(axis=1)].head(5)
                    print(f"[WARN] Invalid timestamps in {extreme_file}: {bad_rows[['start_time', 'end_time']].to_dict()}")
                df = df.dropna(subset=["start_time", "end_time"])
                if df.empty:
                    print(f"[INFO] Empty or invalid {type_name} events for {cluster_fips} after processing")
                    continue
                df["full_event_id"] = df["type"] + "_" + cluster_fips + "_" + df["event_id"].astype(str)
                extreme_events.append(df[["type", "full_event_id", "start_time", "end_time"]].rename(columns={"full_event_id": "event_id"}))
                # extreme_events.append(df[["type", "event_id", "start_time", "end_time"]])



        if not extreme_events:
            print(f"[INFO] No valid extreme events for cluster {cluster_id} (including {county_fips}), skipping.")
            return None
        extremes = pd.concat(extreme_events, ignore_index=True)

        # Build interval trees per type
        trees = {type_name: build_interval_tree(extremes[extremes["type"] == type_name])
                 for type_name in extremes["type"].unique()}

        # Process outages
        outage_attributions = []
        compound_counts = {}
        single_counts = {type_name: 0 for type_name in EXTREME_DIRS.keys()}
        single_counts["unattributed"] = 0

        for _, outage in outages.iterrows():
            outage_start = outage["start_time"]
            outage_end = outage["end_time"] + pd.Timedelta(seconds=1)
            outage_id = outage["outage_id"]

            # Apply buffer
            query_start = outage_start - pd.Timedelta(hours=BUFFER_HOURS)
            query_end = outage_end

            # Find overlapping extreme events
            overlapping_types = set()
            overlapping_events = []
            triggering_events = []
            for type_name, tree in trees.items():
                overlaps = tree[query_start:query_end]
                # To enforce outage_start >= extreme_start, uncomment the line below:
                overlaps = [iv for iv in overlaps if iv.begin <= outage_start]
                
                if overlaps:
                    overlapping_types.add(type_name)
                    overlapping_events.extend([(type_name, iv.data, iv.begin, iv.end) for iv in overlaps])
                    for iv in overlaps:
                        event_id = iv.data
                        triggering_events.append(event_id)

            # Attribution
            if not overlapping_types:
                attribution = "unattributed"
                triggering_str = ""
                single_counts["unattributed"] += 1
            elif len(overlapping_types) == 1:
                attribution = list(overlapping_types)[0] + "_only"
                single_counts[list(overlapping_types)[0]] += 1
                triggering_str = " | ".join(triggering_events)
            else:
                compound_key = "+".join(sorted(overlapping_types))
                compound_counts[compound_key] = compound_counts.get(compound_key, 0) + 1
                attribution = compound_key
                triggering_str = " | ".join(triggering_events)

            outage_attributions.append({
                "county_fips": county_fips,
                "outage_id": outage_id,
                "start_time": outage_start,
                "end_time": outage_end,
                "attribution": attribution,
                "triggering_events": triggering_str
            })

        # Save per-county results
        county_out = pd.DataFrame(outage_attributions)
        county_out_path = os.path.join(OUTPUT_DIR, f"outage_attribution_{county_fips}.csv")
        county_out.to_csv(county_out_path, index=False)
        print(f"[OK] Saved {len(county_out)} outage attributions for {county_fips} -> {county_out_path}")

        # Summary stats
        summary = {
            "county_fips": county_fips,
            "total_outages": len(outages),
            **{f"{k}_count": v for k, v in single_counts.items()},
            **{f"{k}_count": v for k, v in compound_counts.items()}
        }
        return summary

    except Exception as e:
        print(f"[ERR] {outage_file}: Unexpected error - {e}")
        return None

def main():
    # Get list of outage files
    file_list = glob.glob(os.path.join(OUTAGE_DIR, FILE_GLOB_OUTAGE))
    if rank == 0:
        print(f"[INFO] Found {len(file_list)} county outage files to process")

    # Split the file list across nodes
    files_per_node = len(file_list) // size
    remainder = len(file_list) % size
    if rank < remainder:
        start = rank * (files_per_node + 1)
        end = start + files_per_node + 1
    else:
        start = rank * files_per_node + remainder
        end = start + files_per_node
    local_files = file_list[start:end]
    if rank == 0:
        print(f"[INFO] Node {rank}: Processing {len(local_files)} files: {local_files}")
    else:
        print(f"[INFO] Node {rank}: Processing {len(local_files)} files")

    with Pool(processes=NUM_PROCESSES) as pool:
        local_summaries = list(tqdm(pool.imap_unordered(process_county, local_files), total=len(local_files), desc=f"Node {rank}"))

    # Gather summaries from all nodes
    all_summaries = comm.gather(local_summaries, root=0)

    # Combine summaries on root node (rank 0)
    if rank == 0:
        summaries = []
        for node_summaries in all_summaries:
            summaries.extend([s for s in node_summaries if s is not None])
        print(f"[INFO] Successfully processed {len(summaries)} counties")
        if summaries:
            summary_df = pd.DataFrame(summaries).sort_values("county_fips")
            summary_df.to_csv(SUMMARY_PATH, index=False)
            print(f"[OK] Global summary -> {SUMMARY_PATH}")
        else:
            print(f"[INFO] No summaries to write (no counties processed).")

if __name__ == "__main__":
    main()