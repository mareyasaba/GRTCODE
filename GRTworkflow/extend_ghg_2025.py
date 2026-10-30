"""Append a 2025 row to the GRTCODE greenhouse-gas file using NOAA GML observed growth.

CO2, CH4 and N2O: file_2024 * (NOAA_2025 / NOAA_2024), so the file's own units and
baseline are kept and only NOAA's observed 2024->2025 growth is applied.
cfc12eq and hfc134aeq: NOAA does not publish these equivalents, so they are
extrapolated linearly from the file's 2023->2024 change.
Any other variable on the time axis repeats its 2024 value.

Usage (on a GAEA login node, which has internet):
    python3 extend_ghg_2025.py <input annual_mean_gas_data.nc> <output .nc>
"""
import sys
import urllib.request

import xarray as xr

NOAA = {
    "co2": "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_gl.txt",
    "ch4": "https://gml.noaa.gov/webdata/ccgg/trends/ch4/ch4_annmean_gl.txt",
    "n2o": "https://gml.noaa.gov/webdata/ccgg/trends/n2o/n2o_annmean_gl.txt",
}
EXTRAPOLATE = ["cfc12eq", "hfc134aeq"]


def noaa_annual_means(url):
    """Return {year: global annual mean} from a NOAA GML *_annmean_gl.txt file."""
    text = urllib.request.urlopen(url, timeout=60).read().decode()
    values = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split()
        values[int(fields[0])] = float(fields[1])
    return values


def main(src, dst):
    ds = xr.open_dataset(src, decode_times=False)
    last_time = float(ds["time"][-1])
    if int(last_time) != 2024:
        sys.exit(f"Expected the file to end in 2024, but the last time is {last_time}.")

    new = ds.isel(time=[-1]).copy(deep=True)
    new = new.assign_coords(time=[last_time + 1.0])

    for gas, url in NOAA.items():
        if gas not in ds:
            continue
        noaa = noaa_annual_means(url)
        if 2025 not in noaa:
            sys.exit(f"NOAA {gas} file has no 2025 value yet: {url}")
        ratio = noaa[2025] / noaa[2024]
        new[gas] = ds[gas].isel(time=[-1]).assign_coords(time=new["time"]) * ratio
        print(f"{gas}: NOAA 2024={noaa[2024]:.3f} 2025={noaa[2025]:.3f} ratio={ratio:.6f}; "
              f"file 2024={float(ds[gas][-1].squeeze()):.6g} -> 2025={float(new[gas].squeeze()):.6g}")

    for gas in EXTRAPOLATE:
        if gas not in ds:
            continue
        step = ds[gas].isel(time=-1) - ds[gas].isel(time=-2)
        new[gas] = (ds[gas].isel(time=[-1]) + step).assign_coords(time=new["time"])
        print(f"{gas}: file 2023={float(ds[gas][-2].squeeze()):.6g} 2024={float(ds[gas][-1].squeeze()):.6g} "
              f"-> 2025={float(new[gas].squeeze()):.6g} (linear)")

    out = xr.concat([ds, new], dim="time")
    for name in out.variables:
        out[name].attrs = ds[name].attrs
        out[name].encoding = {k: v for k, v in ds[name].encoding.items()
                              if k in ("dtype", "_FillValue", "units", "calendar")}
    out.attrs = ds.attrs
    out.to_netcdf(dst, unlimited_dims=["time"])
    print(f"Wrote {dst} (time now ends at {float(out['time'][-1])})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
