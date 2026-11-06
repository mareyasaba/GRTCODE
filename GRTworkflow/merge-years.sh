#!/bin/bash -e
# Merge the yearly GRTCODE outputs of one experiment into a single file along time.
#
# Usage: merge-years.sh <name_tag> <first_year> <last_year> [work_directory]
#   e.g. merge-years.sh control 2000 2025
# Writes <work_directory>/<name_tag>_<first>_<last>-cleansky-integrated.nc.
# submit.sh submits this automatically (GRT_MERGE_YEARS) once all its runs have finished.

name_tag="$1"
first_year="$2"
last_year="$3"
work_directory="${4:-/gpfs/f5/gfdl_m/scratch/$USER/work/grtcode-era5}"
if [ -z "$last_year" ]; then
  echo "Usage: $0 <name_tag> <first_year> <last_year> [work_directory]"
  exit 1
fi

module load nco
cd "$work_directory"

# Stop before merging if any year is missing.
files=()
for year in $(seq $first_year $last_year); do
  f="$year.$name_tag-cleansky-integrated.nc"
  if [ ! -s "$f" ]; then
    echo "Error: $work_directory/$f is missing; not merging."
    exit 1
  fi
  files+=("$f")
done

# ncrcat joins along the record dimension, so make time the record dimension where it is not yet.
for f in "${files[@]}"; do
  if ncdump -h "$f" | grep -q UNLIMITED; then
    echo "already record: $f"
  else
    echo "record dim: $f"
    ncks -O --mk_rec_dmn time "$f" "$f"
  fi
done

out="${name_tag}_${first_year}_${last_year}-cleansky-integrated.nc"
ncrcat -O -4 -L 1 "${files[@]}" "$out.tmp"
mv "$out.tmp" "$out"
echo "merged: $work_directory/$out"
