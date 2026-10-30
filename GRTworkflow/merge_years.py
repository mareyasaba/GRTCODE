"""Merge yearly combined ERA5 files (from combiner.py) into one monthly time series.

Variables, dimensions and names are kept exactly as combiner.py writes them; the
yearly files are only concatenated along time.  Input years can use different time
units (e.g. hours since 1900 vs seconds since 1970), so every year's times are
converted to the units of the first file.  The yearly files are processed one at a
time, so memory use stays at one year.

Usage:
    python3 merge_years.py --output control_2000_2025.nc \
        $(for y in $(seq 2000 2025); do echo /path/$y.control-cleansky-integrated.nc; done)
"""
import argparse

from netCDF4 import Dataset, date2num, num2date


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("years", nargs="+", help="Yearly files, in time order.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with Dataset(args.years[0]) as first, Dataset(args.output, "w", format="NETCDF4") as out:
        for name, dim in first.dimensions.items():
            out.createDimension(name, None if name == "time" else len(dim))
        for name, var in first.variables.items():
            new = out.createVariable(name, var.dtype, var.dimensions,
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
                    data = var[:]
                    if name == "time":
                        dates = num2date(data, var.units, getattr(var, "calendar", "standard"))
                        data = date2num(dates, time_units, calendar)
                    out.variables[name][t0:t0+nt] = data
                t0 += nt
    print(f"Wrote {args.output} with {t0} months")


if __name__ == "__main__":
    main()
