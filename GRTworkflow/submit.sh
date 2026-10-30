#!/bin/bash

# ============================================================
# Script to run ERA5 radiative transfer experiments for GHGs
# Get the absolute path to this script and the run script
script_dir="$(dirname "$(readlink -f "$0")")"
runscript="${script_dir}/run-era5.sh"

# Your GRTCODE clone (the folder that contains GRTworkflow/ and build/).
workdir="$(readlink -f "${script_dir}/..")"

# ------------------------------------------------------------
# Define experiment settings
# ------------------------------------------------------------
# Directory containing greenhouse gas input NetCDF files
ghg_path="/gpfs/f5/gfdl_m/scratch/$USER/GHG"

# ERA5 input directory (choose one of the options)
# 144x90 grid (set nlon="144" in run-era5.sh); era5_coarse is 48x30 (nlon="48").
# 2025 must come from a complete 12-month file; the shared 2025 files only hold 6 months.
era5_data="/gpfs/f5/gfdl_m/world-shared/David.Paynter/line-by-line/run/era5"

# List of experiments to run (see below for available options)
exps=(control)
# ------------------------------------------------------------
# Available experiment options for exps:
# ------------------------------------------------------------
# Each experiment corresponds to a GHG input file at $ghg_path/${exp}.nc
#
# • Single-gas experiments:
#   co2_PI, co2_2xPI, co2_3xPI, co2_4xPI, co2_PD, co2_4x
#   ch4_PI, ch4_2xPI, ch4_3xPI, ch4_4xPI, ch4_PD, ch4_4x
#   n2o_PI, n2o_2xPI, n2o_3xPI, n2o_4xPI, n2o_PD, n2o_4x
#   hfc134aeq_PI, hfc134aeq_2xPI, hfc134aeq_3xPI, hfc134aeq_4xPI, hfc134aeq_PD, hfc134aeq_4x
#   cfc12eq_PI, cfc12eq_2xPI, cfc12eq_3xPI, cfc12eq_4xPI, cfc12eq_PD, cfc12eq_4x
#
# • Multi-gas/control experiments:
#   control   → time-varying WMGHGs (CMIP7)
#   PI        → fixed 1850 WMGHGs (pre-industrial baseline)
# ------------------------------------------------------------


# Get the absolute path to this script and the run script
script_dir="$(dirname "$(readlink -f "$0")")"
runscript="${script_dir}/run-era5.sh"
# ------------------------------------------------------------
# Loop over years and experiments
# ------------------------------------------------------------

for year in $(seq 2000 2025); do
  for exp in "${exps[@]}"; do
    name_tag="${exp}"  # Unique output tag for this configuration
# ------------------------------------------------------------
# Do not change below:
# ------------------------------------------------------------
    # Build command and execute
    cmd="$runscript -p $workdir $year $era5_data $ghg_path/${exp}.nc $name_tag"
    echo "Running: $cmd"
    eval "$cmd"
  done
done


