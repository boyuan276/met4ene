from math import pi

import numpy as np
import wrf
import xarray as xr
from numpy.core._multiarray_umath import cos, sin
from scipy.spatial import cKDTree
from wrf import latlonutils as llutils


def get_wspd_wdir(netcdf_data, key):
    """
    Formats the wind speed and wind direction so it can be merged into
    an xarray Dataset with all the other variables extracted using getvar
    :param netcdf_data:
    :param key:
    :return:
    """
    var = wrf.getvar(netcdf_data, key, wrf.ALL_TIMES)
    var = xr.DataArray.reset_coords(var, ['wspd_wdir'], drop=True)
    var.name = key
    return var


def _get_proj_params(met_data):
    """
    Return the map projection parameters.

    Args:
        met_data (:class:`xarray.Dataset`): WRF-ARW Dataset
    Returns:
    """
    # Extract the global attributes from the xarray dataset
    attrlist = ("MAP_PROJ", "TRUELAT1", "TRUELAT2", "STAND_LON", "DX", "DY")
    attrs = {attr: met_data.attrs[attr] for attr in attrlist}

    map_proj = attrs["MAP_PROJ"]
    truelat1 = attrs["TRUELAT1"]
    truelat2 = attrs["TRUELAT2"]
    stdlon = attrs["STAND_LON"]
    dx = attrs["DX"]
    dy = attrs["DY"]
    pole_lat = 90.0
    pole_lon = 0.0
    latinc = 0.0
    loninc = 0.0

    xlat = met_data.XLAT
    xlon = met_data.XLONG

    # Not so sure about these...
    ref_lat = np.ravel(xlat[..., 0, 0])
    ref_lon = np.ravel(xlon[..., 0, 0])

    # Note: fortran index
    known_x = 1.0
    known_y = 1.0

    return (map_proj, truelat1, truelat2, stdlon, ref_lat, ref_lon,
            pole_lat, pole_lon, known_x, known_y, dx, dy, latinc, loninc)


def _wrf2xarray(netcdf_data, query_variables):
    """
    Gets data from the netcdf wrfout file and uses wrf-python
    to create an xarray Dataset.

    Parameters
    ----------
    data: netcdf
        Data returned from UNIDATA NCSS query, or from your local forecast.
    query_variables: list
        The variables requested.
    start: Timestamp
        The start time
    end: Timestamp
        The end time

    Returns
    -------
    xarray.Dataset
    """
    first = True
    for key in query_variables:
        if key in ['wspd', 'wdir']:
            var = get_wspd_wdir(netcdf_data, key)
        else:
            var = wrf.getvar(netcdf_data, key, timeidx=wrf.ALL_TIMES)
        if first:
            data = var
            first = False
        else:
            with xr.set_options(keep_attrs=True):
                try:
                    data = xr.merge([data, var])
                except ValueError:
                    data = data.drop_vars('Time')
                    data = xr.merge([data, var])

    # Get global attributes from the NetCDF Dataset
    wrfattrs_names = netcdf_data.ncattrs()
    wrfattrs = wrf.extract_global_attrs(netcdf_data, wrfattrs_names)
    data = data.assign_attrs(wrfattrs)

    # Fix a bug in how wrfout data is read in -- attributes must be strings to be written to NetCDF
    for var in data.data_vars:
        try:
            data[var].attrs['projection'] = str(data[var].attrs['projection'])
        except KeyError:
            pass

    # Fix another bug that creates a conflict in the 'coordinates' attribute
    for var in data.data_vars:
        try:
            del data[var].attrs['coordinates']
        except KeyError:
            pass

    return data


def ll_to_xy(met_data, latitude, longitude):
    """
    Returns an (x,y) location for an input meteorological dataset.
    Note that only a single latitude, longitude pair is accepted at
    this time.

    :param met_data :class:`xarray.Dataset`: Input meteorological dataset
        (generally output from WRF as the proj parameters.
        currently require the WRF naming scheme).
    :param latitude :obj:`float`: Latitude coordinate
        to convert to x, y indicies.
    :param longitude :obj:`float`: Longitude coordinate
        to convert to x, y indicies.
    :return:
    """
    # Extract the projection parameters from the xarray global attributes
    (map_proj, truelat1, truelat2, stdlon, ref_lat, ref_lon,
     pole_lat, pole_lon, known_x, known_y, dx, dy, latinc,
     loninc) = _get_proj_params(met_data)

    result = np.empty((2,), np.float64)
    # The following function wraps an old fortran program that finds the nearest indicies given
    # a lat, lon pair
    fort_out = llutils._lltoxy(map_proj, truelat1, truelat2, stdlon,
                               ref_lat, ref_lon, pole_lat, pole_lon,
                               known_x, known_y, dx, dy, latinc, loninc,
                               latitude, longitude)
    # Note, comes back from fortran as y,x.  So, need to swap them.
    result[0] = fort_out[1]
    result[1] = fort_out[0]

    # Make indexes 0-based
    result = result - 1

    # Make the result an integer
    result = np.rint(result).astype(int)

    return result


class Kdtree_ll_to_xy(object):
    def __init__(self, met_ds, latvarname, lonvarname):
        self.met_ds = met_ds
        self.latvar = self.met_ds[latvarname]
        self.lonvar = self.met_ds[lonvarname]
        # Read latitude and longitude from file into numpy arrays
        rad_factor = pi/180.0  # for trignometry, need angles in radians
        self.latvals = self.latvar[:] * rad_factor
        self.lonvals = self.lonvar[:] * rad_factor
        self.shape = self.latvals.shape
        clat, clon = cos(self.latvals), cos(self.lonvals)
        slat, slon = sin(self.latvals), sin(self.lonvals)
        triples = list(zip(np.ravel(clat*clon), np.ravel(clat*slon), np.ravel(slat)))
        self.kdt = cKDTree(triples)

    def query(self, lat0, lon0):
        rad_factor = pi/180.0
        lat0_rad = lat0 * rad_factor
        lon0_rad = lon0 * rad_factor
        clat0, clon0 = cos(lat0_rad), cos(lon0_rad)
        slat0, slon0 = sin(lat0_rad), sin(lon0_rad)
        dist_sq_min, minindex_1d = self.kdt.query([clat0*clon0, clat0*slon0, slat0])
        iy_min, ix_min = np.unravel_index(minindex_1d, self.shape)
        return iy_min, ix_min