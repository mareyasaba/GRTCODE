"""Combine the per-node ERA5 output pieces of one GRTCODE run into a single file.

Reads <workdir>/<nametag>/<year>.era5-fluxes.nc.* and writes
<workdir>/<year>.<nametag>-cleansky-integrated.nc (same arguments and output name as
before).  Each piece holds a block of longitudes, recorded in its x_start global
attribute, and every longwave and atmospheric-state variable is copied into its place
on the full longitude grid, so p, t, ts, the fluxes and tau_z all end up in the output.

The longwave grid is averaged onto --resolution (default 1 cm-1): fluxes by a plain
mean, and tau_z by averaging the transmittance, -ln(mean(exp(-tau))), so the band
optical depth stays consistent with the band-averaged fluxes.  Shortwave variables are
dropped unless --keep-shortwave is given.

Usage:
    python3 combiner.py --workdir <work directory> --year 2005 --nametag control
"""
import argparse
import glob
import sys

import numpy as np
from netCDF4 import Dataset

LW = "lw_wavenumber"
SW = "sw_wavenumber"
OPTICAL_DEPTHS = {"tau_z"}


def rebin(data, axis, factor, optical_depth):
    """Average groups of `factor` neighbouring points along `axis`."""
    if factor == 1:
        return data
    n = data.shape[axis] // factor
    data = np.take(data, np.arange(n*factor), axis=axis)
    shape = data.shape[:axis] + (n, factor) + data.shape[axis+1:]
    data = data.reshape(shape)
    if optical_depth:
        return -np.log(np.mean(np.exp(-data), axis=axis+1))
    return np.mean(data, axis=axis+1)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workdir", required=True, help="Path to the working directory.")
    parser.add_argument("--year", type=int, required=True, help="Year of the data to combine.")
    parser.add_argument("--nametag", required=True, help="Experiment name.")
    parser.add_argument("--resolution", type=float, default=1.0,
                        help="Longwave resolution [cm-1] of the output (default 1).")
    parser.add_argument("--keep-shortwave", action="store_true",
                        help="Also copy the shortwave variables.")
    args = parser.parse_args()

    pattern = f"{args.workdir}/{args.nametag}/{args.year}.era5-fluxes.nc.*"
    output = f"{args.workdir}/{args.year}.{args.nametag}-cleansky-integrated.nc"
    pieces = glob.glob(pattern)
    if not pieces:
        sys.exit(f"No files found matching pattern: {pattern}")
    pieces = sorted(pieces, key=lambda p: Dataset(p).getncattr("x_start"))
    with Dataset(pieces[0]) as first:
        nlon = int(first.getncattr("lon_global_size"))
        w = first.variables[LW][:]
        dw = float(w[1] - w[0]) if w.size > 1 else args.resolution
        factor = max(1, int(round(args.resolution/dw)))
        print(f"{len(pieces)} pieces, {nlon} longitudes, lw grid {dw:g} cm-1 -> rebin by {factor}")

        out = Dataset(output, "w", format="NETCDF4")
        for name, dim in first.dimensions.items():
            if name == SW and not args.keep_shortwave:
                continue
            size = len(dim)
            if name == "lon":
                size = nlon
            elif name == LW:
                size = len(dim) // factor
            out.createDimension(name, None if dim.isunlimited() else size)

        for name, var in first.variables.items():
            if any(d not in out.dimensions for d in var.dimensions):
                continue
            dtype = "f8" if name in ("time", "lat", "lon", LW, SW) else "f4"
            new = out.createVariable(name, dtype, var.dimensions, zlib=True, complevel=1,
                                     fill_value=np.float32(np.nan) if dtype == "f4" else None)
            new.setncatts({k: var.getncattr(k) for k in var.ncattrs() if k != "_FillValue"})
            if "lon" not in var.dimensions and name != LW:
                new[:] = var[:]
        lon_full = np.full(nlon, np.nan)
        for path in pieces:
            with Dataset(path) as piece:
                x0 = int(piece.getncattr("x_start"))
                lon_piece = piece.variables["lon"][:]
                lon_full[x0:x0+lon_piece.size] = lon_piece
        out.variables[LW][:] = rebin(w, 0, factor, False)
        out.variables["lon"][:] = lon_full
        out.setncatts({k: first.getncattr(k) for k in first.ncattrs()
                       if k not in ("x_start", "x_stop")})
        out.setncattr("lw_calculation_resolution_cm-1", round(dw, 6))
        out.setncattr("lw_output_resolution_cm-1", round(dw*factor, 6))

    # Assemble one variable at a time in memory and write it in a single call.
    # Writing longitude slices straight into the compressed file is very slow,
    # because every slice rewrites many compressed chunks.
    covered = np.zeros(nlon, dtype=bool)
    handles = [Dataset(path) for path in pieces]
    for h in handles:
        x0 = int(h.getncattr("x_start"))
        covered[x0:x0+len(h.dimensions["lon"])] = True
    for name, outvar in out.variables.items():
        if "lon" not in outvar.dimensions or name == "lon":
            continue
        print(f"{name}: assembling {len(handles)} pieces")
        full = np.full(outvar.shape, np.nan, dtype="f4")
        lon_axis = outvar.dimensions.index("lon")
        for h in handles:
            var = h.variables[name]
            x0 = int(h.getncattr("x_start"))
            n = len(h.dimensions["lon"])
            data = var[:]
            data = data.astype("f8").filled(np.nan) if np.ma.isMA(data) else data.astype("f8")
            if LW in var.dimensions:
                data = rebin(data, var.dimensions.index(LW), factor, name in OPTICAL_DEPTHS)
            index = [slice(None)]*data.ndim
            index[lon_axis] = slice(x0, x0+n)
            full[tuple(index)] = data
        outvar[:] = full
        del full
    for h in handles:
        h.close()
    out.close()

    if not covered.all():
        missing = np.flatnonzero(~covered)
        sys.exit(f"Error: longitudes {missing.tolist()} were not in any piece.")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
