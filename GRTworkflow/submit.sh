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
ghg_path="${GRT_GHG_PATH:-/gpfs/f5/gfdl_m/world-shared/Jing.Feng/GHG}"

# ERA5 input directory (choose one of the options)
# Options: era5_coarse, era5_coarse_noh2o, era5_fo3, era5_fo3strat (48x30), or a full
# 144x90 directory; run-era5.sh reads the grid size from the files.
era5_data="${GRT_ERA5_DATA:-/gpfs/f5/gfdl_m/scratch/Jing.Feng/line-by-line/run/era5_coarse}"

# List of experiments to run (see below for available options)
exps=(${GRT_EXPS:-PI control co2_PI ch4_PI n2o_PI cfc12eq_PI hfc134aeq_PI})
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

# Optional suffix added to each output tag, e.g. GRT_NAME_SUFFIX="_era5full_lw1" gives
# YYYY.control_era5full_lw1-cleansky-integrated.nc in its own subfolder. Empty by default,
# so output names are unchanged unless you set it.
name_suffix="${GRT_NAME_SUFFIX:-}"

# Optional: merge each experiment's yearly files into one file once all the runs above
# have finished, e.g. GRT_MERGE_YEARS="2000 2025" gives control_2000_2025-cleansky-integrated.nc.
# The range can be wider than GRT_YEARS; years not run here must already exist. Off by default.
merge_years="${GRT_MERGE_YEARS:-}"

work_directory="/gpfs/f5/gfdl_m/scratch/$USER/work/grtcode-era5"
job_directory="${GRT_JOB_DIR:-$work_directory/jobs}"
mkdir -p "$job_directory"
export GRT_JOB_DIR="$job_directory"

# Years to run (override with e.g. GRT_YEARS="2000 2025").
read first_year last_year <<< "${GRT_YEARS:-2001 2024}"
for year in $(seq $first_year $last_year); do
  for exp in "${exps[@]}"; do
    name_tag="${exp}${name_suffix}"  # Unique output tag for this configuration
# ------------------------------------------------------------
# Do not change below:
# ------------------------------------------------------------
    # run-era5.sh appends each job id here, so the merge can wait for them.
    export GRT_JOBID_FILE="$job_directory/jobids.$name_tag.$$"
    # Build command and execute
    cmd="$runscript -p $workdir $year $era5_data $ghg_path/${exp}.nc $name_tag"
    echo "Running: $cmd"
    eval "$cmd"
  done
done

# Submit one merge job per experiment that starts only if every year above succeeded.
if [ -n "$merge_years" ]; then
  read merge_first merge_last <<< "$merge_years"
  account="$( sacctmgr --noheader list user $USER format=DefaultAccount%6 )"
  for exp in "${exps[@]}"; do
    name_tag="${exp}${name_suffix}"
    idfile="$job_directory/jobids.$name_tag.$$"
    dependency=""
    if [ -s "$idfile" ]; then
      dependency="--dependency=afterok:$(paste -sd: "$idfile") --kill-on-invalid-dep=yes"
    fi
    sbatch --clusters=c5 --account=$account --partition=batch --qos=normal --nodes=1 --time=720 \
      $dependency -o "$job_directory/merge-$name_tag-${merge_first}_${merge_last}-%j.out" \
      --wrap "${script_dir}/merge-years.sh $name_tag $merge_first $merge_last $work_directory"
    rm -f "$idfile"
  done
fi


