import os, re, glob
import pandas as pd
import numpy as np
from typing import List, Tuple, Optional
from multiprocessing import Pool, cpu_count

# ==== USER SETTINGS ====
INPUT_DIR = "./outputs/iss_lis_lightning/county_lightning_binary_csvs"
OUTPUT_DIR = "./events/lightning/event_lightning"
OUTPUT_DIR_ACF = "./events/lightning/event_lightning_acf"

os.makedirs(OUTPUT_DIR, exist_ok=True)  
os.makedirs(OUTPUT_DIR_ACF, exist_ok=True)

FILE_GLOB = "*_binary_lightning.csv"  # Updated to use binary data files
TIME_COL = "timestamp"
FLAG_COL = "lightning"  # Binary column (0/1 indicating exceedance)
ACF_THRESHOLD = 0.05  # Threshold for declaring independence
MAX_LAG = 48  # ACF lags to scan
SAVE_FORMAT = "csv"  # "csv" only, per your request
WRITE_COMBINED = True
SUMMARY_PATH = os.path.join(OUTPUT_DIR, "county_summary.csv")
NUM_PROCESSES = max(1, cpu_count() - 1)  # Use all but one CPU core
# ========================

def parse_timestamp_utc(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.replace("_UTC", "", regex=False)
    s = s.str.replace(r"^(\d{4})_(\d{2})_(\d{2})_(\d{2})$",
                      r"\1-\2-\3 \4:00:00", regex=True)
    ts = pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S", utc=True, errors="coerce")
    if ts.isna().any():
        bad = series[ts.isna()].head(5).tolist()
        raise ValueError(f"Some timestamps failed to parse. First few: {bad}")
    return ts

def county_from_filename(path: str) -> str:
    m = re.match(r"^(\d{4,5})_binary_lightning\.csv$", os.path.basename(path))  # Updated regex for binary files
    if not m:
        raise ValueError(f"Cannot parse county FIPS from filename: {path}")
    return m.group(1)#.zfill(5)

def acf_series(x: pd.Series, max_lag: int) -> pd.DataFrame:
    lags = np.arange(1, max_lag+1)
    vals = [x.autocorr(lag=int(k)) for k in lags]
    return pd.DataFrame({"lag": lags, "acf": vals})

def find_declustering_gap(binary_series: pd.Series, acf_threshold=0.05, max_lag=36) -> int:
    acf_df = acf_series(binary_series, max_lag)
    for lag, val in zip(acf_df["lag"], acf_df["acf"]):
        if abs(val) <= acf_threshold:
            return int(lag)
    return int(max_lag)

def runs_declustering(binary_series: pd.Series, run_length: int) -> List[Tuple[int, int]]:
    """
    Merge exceedances separated by < run_length consecutive 0s.
    Returns list of (start_idx, end_idx).
    """
    events = []
    in_event = False
    zeros = 0
    start = None
    for i, val in enumerate(binary_series):
        if val == 1:
            if not in_event:
                in_event = True
                start = i
            zeros = 0
        else:
            if in_event:
                zeros += 1
                if zeros >= run_length:
                    events.append((start, i - zeros))
                    in_event = False
                    zeros = 0
    if in_event:
        events.append((start, len(binary_series) - 1))
    return events

def build_event_indicator(index: pd.DatetimeIndex, events_df: pd.DataFrame) -> pd.Series:
    """
    Returns a 0/1 Series indexed by 'index', with 1 for hours that fall within any event.
    """
    ind = pd.Series(0, index=index, dtype=int)
    for _, r in events_df.iterrows():
        ind.loc[r["start_time"]:r["end_time"]] = 1
    return ind

def process_county(path: str) -> Optional[dict]:
    """
    Process a single county file and return summary data.
    """
    try:
        county_fips = county_from_filename(path)
        print(f"Processing county {county_fips}")
        
        # Read and validate data
        df = pd.read_csv(path, usecols=[TIME_COL, FLAG_COL])
        if TIME_COL not in df.columns or FLAG_COL not in df.columns:
            print(f"[WARN] Missing {TIME_COL} or {FLAG_COL} in {path}, skipping.")
            return None

        # Parse & sort
        df[TIME_COL] = parse_timestamp_utc(df[TIME_COL])
        df = df.sort_values(TIME_COL)
        df[FLAG_COL] = df[FLAG_COL].fillna(0).astype(int)  # Ensure binary data is 0/1

        # Continuous hourly index
        full_idx = pd.date_range(df[TIME_COL].min(), df[TIME_COL].max(), freq="H", tz="UTC")
        dfh = df.set_index(TIME_COL).reindex(full_idx)
        dfh.index.name = TIME_COL
        dfh[FLAG_COL] = dfh[FLAG_COL].fillna(0).astype(int)

        # Pre-declustering ACF and gap
        acf_df = acf_series(dfh[FLAG_COL], MAX_LAG)
        gap = find_declustering_gap(dfh[FLAG_COL], acf_threshold=ACF_THRESHOLD, max_lag=MAX_LAG)
        print(f"[{county_fips}] Suggested declustering gap: {gap} hours")

        # Declustering
        idx_pairs = runs_declustering(dfh[FLAG_COL], run_length=gap)

        # Build events table
        rows = []
        for eid, (sidx, eidx) in enumerate(idx_pairs, start=1):
            start_time = dfh.index[sidx]
            end_time = dfh.index[eidx]
            dur = int((end_time - start_time).total_seconds() // 3600) + 1
            exc = int(dfh[FLAG_COL].iloc[sidx:eidx+1].sum())
            rows.append({
                "county_fips": county_fips,
                "event_id": eid,
                "start_time": start_time,
                "end_time": end_time,
                "duration_hours": dur,
                "exceed_hours": exc,
                "fraction_exceed": (exc / dur) if dur > 0 else np.nan
            })
        events_df = pd.DataFrame(rows)

        # Post-declustering independence check
        if not events_df.empty:
            in_event_indicator = build_event_indicator(dfh.index, events_df)
            pre_acf1 = dfh[FLAG_COL].autocorr(lag=1)
            post_acf1 = in_event_indicator.autocorr(lag=1)
            coverage_fraction = in_event_indicator.mean()  # fraction of hours in events
            n_events = len(events_df)
            mean_dur = events_df["duration_hours"].mean()
            median_dur = events_df["duration_hours"].median()
            mean_frac_exc = events_df["fraction_exceed"].mean()
        else:
            pre_acf1 = dfh[FLAG_COL].autocorr(lag=1)
            post_acf1 = np.nan
            coverage_fraction = 0.0
            n_events = 0
            mean_dur = median_dur = mean_frac_exc = np.nan

        # Save per-county diagnostics
        acf_df_out = acf_df.copy()
        acf_df_out["county_fips"] = county_fips
        acf_df_out.to_csv(os.path.join(OUTPUT_DIR_acf, f"acf_{county_fips}.csv"), index=False)

        # Save per-county events
        out_path = os.path.join(OUTPUT_DIR, f"lightning_events_{county_fips}.csv")
        events_df.to_csv(out_path, index=False)
        print(f"[OK] Saved {len(events_df)} events for county {county_fips} -> {out_path}")

        # Return summary row
        return {
            "county_fips": county_fips,
            "suggested_gap_hours": gap,
            "n_events": n_events,
            "mean_duration_hours": mean_dur,
            "median_duration_hours": median_dur,
            "mean_fraction_exceed": mean_frac_exc,
            "pre_acf_lag1_binary": pre_acf1,
            "post_acf_lag1_event_indicator": post_acf1,
            "coverage_fraction": coverage_fraction
        }
    except Exception as e:
        print(f"[ERR] {path}: {e}")
        return None

def main():
    # Get list of input files
    file_list = glob.glob(os.path.join(INPUT_DIR, FILE_GLOB))
    print(f"Found {len(file_list)} county files to process")

    # Process files in parallel
    with Pool(processes=NUM_PROCESSES) as pool:
        summary_rows = pool.map(process_county, file_list)

    # Filter out None results (from failed counties)
    summary_rows = [row for row in summary_rows if row is not None]

    # Save summary table
    if summary_rows:
        summary_df = pd.DataFrame(summary_rows).sort_values("county_fips")
        summary_df.to_csv(SUMMARY_PATH, index=False)
        print(f"[OK] County summary -> {SUMMARY_PATH}")
    else:
        print("[INFO] No summary to write (no counties processed).")

if __name__ == "__main__":
    main()