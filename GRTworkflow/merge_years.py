"""Merge yearly combined ERA5 files (from combine_era5.py) into one monthly time series.

The output follows the layout of the earlier line-by-line merged files:
  * spectral variables are stored as (time, wavenumber, lat, lon),
  * lw_wavenumber is renamed to wavenumber,
  * the -flux-at-level outputs get the old tropopause names
    (rluaf_level -> rlutropaf, rlucsaf_level -> rlutropcsaf,
     rldaf_level -> rldtropaf, rldcsaf_level -> rldtropcsaf).
The yearly files are processed one at a time, so memory use stays at one year.

Usage:
    python3 merge_years.py --output merged_monthly_2000_2025.nc \
        $(for y in $(seq 2000 2025); do echo /path/$y.control-era5.nc; done)
"""
import argparse

from netCDF4 import Dataset, date2num, num2date

RENAME = {
    "lw_wavenumber": "wavenumber",
    "rluaf_level": "rlutropaf",
    "rlucsaf_level": "rlutropcsaf",
    "rldaf_level": "rldtropaf",
    "rldcsaf_level": "rldtropcsaf",
}
SPECTRAL_ORDER = ("time", "lw_wavenumber", "lat", "lon")


def output_dims(dims):
    if "lw_wavenumber" in dims and len(dims) == 4:
        return SPECTRAL_ORDER
    return dims


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("years", nargs="+", help="Yearly files, in time order.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with Dataset(args.years[0]) as first, Dataset(args.output, "w", format="NETCDF4") as out:
        for name, dim in first.dimensions.items():
            out.createDimension(RENAME.get(name, name), None if name == "time" else len(dim))
        for name, var in first.variables.items():
            dims = output_dims(var.dimensions)
            new = out.createVariable(RENAME.get(name, name), var.dtype,
                                     tuple(RENAME.get(d, d) for d in dims),
                                     zlib=True, complevel=1,
                                     fill_value=getattr(var, "_FillValue", None))
            new.setncatts({k: var.getncattr(k) for k in var.ncattrs() if k != "_FillValue"})
            if "time" not in var.dimensions:
                new[:] = var[:]
        out.setncatts({k: first.getncattr(k) for k in first.ncattrs()})

        time_units = first.variables["time"].units
        calendar = getattr(first.variables["time"], "calendar", "standard")
        t0 = 0
        for path in args.years:
            with Dataset(path) as year:
                nt = len(year.dimensions["time"])
                print(f"{path}: months {t0}-{t0+nt-1}")
                for name, var in year.variables.items():
                    if "time" not in var.dimensions:
                        continue
                    dims = output_dims(var.dimensions)
                    data = var[:]
                    if name == "time":
                        # Input years can use different time units (e.g. hours since 1900
                        # vs seconds since 1970), so convert to the first file's units.
                        dates = num2date(data, var.units,
                                         getattr(var, "calendar", "standard"))
                        data = date2num(dates, time_units, calendar)
                    if dims != var.dimensions:
                        data = data.transpose([var.dimensions.index(d) for d in dims])
                    out.variables[RENAME.get(name, name)][t0:t0+nt] = data
                t0 += nt
    print(f"Wrote {args.output} with {t0} months")


if __name__ == "__main__":
    main()
