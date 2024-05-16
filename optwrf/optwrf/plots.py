"""
Plotting functions
"""

import matplotlib.pyplot as plt
from matplotlib.cm import get_cmap
from matplotlib import ticker
from matplotlib.colors import LogNorm
from mpl_toolkits.axes_grid1 import make_axes_locatable, axes_size
import cartopy.feature as cfeature
import cartopy.crs as ccrs
import cartopy.io.shapereader as shpreader
import numpy as np
import xarray as xr
import wrf as wrfpy

import optwrf.regridding
from optwrf import runwrf, postwrf, helper_functions


def get_wrf_proj(wrfds, var):
    """
    Extracts the WRF projection information from the variable string attribute.

    :param wrfds:
    :param var:
    :return:
    """
    # I have to do this tedious string parsing below to get the projection from the processed wrfout file.
    try:
        wrf_proj_params = wrfds[var].attrs['projection']
    except AttributeError:
        raise ValueError('Variable does not contain projection information')
    wrf_proj_params = wrf_proj_params.replace('(', ', ')
    wrf_proj_params = wrf_proj_params.replace(')', '')
    wrf_proj_params = wrf_proj_params.split(',')
    wrf_proj = wrf_proj_params[0]
    stand_lon = float(wrf_proj_params[1].split('=')[1])
    moad_cen_lat = float(wrf_proj_params[2].split('=')[1])
    truelat1 = float(wrf_proj_params[3].split('=')[1])
    truelat2 = float(wrf_proj_params[4].split('=')[1])
    pole_lat = float(wrf_proj_params[5].split('=')[1])
    pole_lon = float(wrf_proj_params[6].split('=')[1])

    # Fortunately, it still apppears to work.
    if wrf_proj == 'LambertConformal':
        wrf_cartopy_crs = ccrs.LambertConformal(central_longitude=stand_lon,
                                                central_latitude=moad_cen_lat,
                                                standard_parallels=[truelat1, truelat2])
        return wrf_cartopy_crs
    else:
        print('Your WRF projection is not the expected Lambert Conformal.')
        raise ValueError


def get_domain_boundary(wrfds, cartopy_crs):
    """
    Finds the boundary of the WRF domain.

    :param wrfds:
    :param cartopy_crs:
    :return:
    """
    # Rename the lat-lon corrdinates to get wrf-python to recognize them
    variables = {'lat': 'XLAT',
                 'lon': 'XLONG'}
    try:
        wrfds = xr.Dataset.rename(wrfds, variables)
    except ValueError:
        print(f'Variables {variables} cannot be renamed, '
              f'those on the left are not in this dataset.')

    # I need to manually convert the boundaries of the WRF domain into Plate Carree to set the limits.
    # Get the raw map bounds using a wrf-python utility
    raw_bounds = wrfpy.geo_bounds(wrfds)

    # Get the projected bounds telling cartopy that the input coordinates are lat/lon (Plate Carree)
    projected_bounds = cartopy_crs.transform_points(ccrs.PlateCarree(),
                                                    np.array([raw_bounds.bottom_left.lon, raw_bounds.top_right.lon]),
                                                    np.array([raw_bounds.bottom_left.lat, raw_bounds.top_right.lat]))
    return projected_bounds


def format_cnplot_axis(axis, cn, proj_bounds, title_str='Contour Plot',
                       add_colorbar=True,
                       cbar_ticks=(0, 5000, 10000, 15000, 20000, 25000, 30000, 35000),
                       cbar_tick_labels=None):
    """
    Formats a contour plot axis.

    :param add_colorbar:
    :param cbar_ticks:
    :param cbar_tick_labels:
    :param axis:
    :param cn:
    :param proj_bounds:
    :param title_str:
    :return:
    """
    # Format the projected bounds so they can be used in the xlim and ylim attributes
    proj_xbounds = [proj_bounds[0, 0], proj_bounds[1, 0]]
    proj_ybounds = [proj_bounds[0, 1], proj_bounds[1, 1]]

    # Finally, set the x and y limits
    axis.set_xlim(proj_xbounds)
    axis.set_ylim(proj_ybounds)

    # Download and add the states, coastlines, and lakes
    shapename = 'admin_1_states_provinces_lakes'
    states_shp = shpreader.natural_earth(resolution='10m',
                                         category='cultural', 
                                         name=shapename)
    # Add features to the maps
    axis.add_geometries(
        shpreader.Reader(states_shp).geometries(),
        ccrs.PlateCarree(),
        facecolor='none',
        linewidth=.5, 
        edgecolor="black"
        )

    # Download and add the states, coastlines, and lakes
    states = cfeature.NaturalEarthFeature(category="cultural", scale="50m",
                                          facecolor="none",
                                          name="admin_1_states_provinces_lines")

    # Add features to the maps
    axis.add_feature(states, linewidth=.5, edgecolor="black")
    axis.add_feature(cfeature.LAKES)
    axis.add_feature(cfeature.OCEAN)
    axis.add_feature(cfeature.BORDERS)
    axis.coastlines('50m', linewidth=0.8)

    # Add color bars
    if add_colorbar is True:
        cbar = plt.colorbar(cn,
                            ax=axis,
                            ticks=cbar_ticks,
                            shrink=0.46,
                            pad=0.05
                            )
        if cbar_tick_labels is not None:
            cbar.ax.set_yticklabels(cbar_tick_labels)  # vertically oriented colorbar

    # Add the axis title
    axis.set_title(title_str, fontsize=10)


def specify_clormap(variable):
    """
    Retruns a color map based on the user-specified variable

    :param variable: string
    :return color_map: object
    """
    if variable in ['ghi', 'ghi_error']:
        colormap = get_cmap("hot_r")
    elif variable in ['wpd', 'wpd_error']:
        colormap = get_cmap("Greens")
    elif variable == 'fitness':
        colormap = get_cmap("Greys")
    else:
        colormap = get_cmap("YlGnBu")
    return colormap


def specify_contour_levels(variable, hourly=False, **kwargs):
    """
    Returns an array with the contour levels.

    :param variable:
    :param hourly:
    :param kwargs:
    :return contourlevels: numpy array
    """
    # First, set the minimum and number of bins based on kwargs
    minimum = kwargs.get('min', 0)
    n_bins = kwargs.get('n', 21)
    # Now, determine the maximum based upon which varible will be plotted
    if hourly:
        if variable in ['ghi', 'ghi_error']:
            maximum = kwargs.get('max', 0.75)
            contourlevels = np.linspace(minimum, maximum, n_bins)
        elif variable in ['wpd', 'wpd_error']:
            maximum = kwargs.get('max', 2500)
            contourlevels = np.linspace(minimum, maximum, n_bins)
        elif variable == 'fitness':
            maximum = kwargs.get('max', 1.5)
            contourlevels = np.linspace(minimum, maximum, n_bins)
        else:
            maximum = kwargs.get('max', 100)
            contourlevels = np.linspace(minimum, maximum, n_bins)
    else:
        if variable in ['ghi', 'ghi_error']:
            maximum = kwargs.get('max', 5)
            contourlevels = np.linspace(minimum, maximum, n_bins)
        elif variable in ['wpd', 'wpd_error']:
            maximum = kwargs.get('max', 50000)
            contourlevels = np.linspace(minimum, maximum, n_bins)
        elif variable == 'fitness':
            maximum = kwargs.get('max', 10)
            contourlevels = np.linspace(minimum, maximum, n_bins)
        else:
            maximum = kwargs.get('max', 1000)
            contourlevels = np.linspace(minimum, maximum, n_bins)
    contourlevels = np.round(contourlevels, 1)
    return contourlevels


def wrf_era5_plot(var, wrfds, erads, paramstr, src='wrf', hourly=False, save_fig=False,
                  wrf_dir='./', era_dir='./', short_title_str='Title', fig_path='./', verbose=False, **kwargs):
    """
    Creates a single WRF or ERA5 plot, using the WRF bounds, producing either a plot every hour
    or a single plot for the day.

    :param var:
    :param wrfds:
    :param erads:
    :param paramstr:
    :param src:
    :param hourly:
    :param save_fig:
    :param wrf_dir:
    :param era_dir:
    :param short_title_str:
    :param fig_path:
    :param verbose:
    :param kwargs:

    :return: None
    """
    # Format the var input
    if type(var) is not str:
        print(f'The var input, {var}, must be a string.')
        raise TypeError
    if var in ['GHI', 'ghi']:
        var = 'ghi'
        wrf_var = 'ghi'
        era_var = 'GHI'
    elif var in ['WPD', 'wpd']:
        var = 'wpd'
        wrf_var = 'wpd'
        era_var = 'WPD'
    elif var in ['ghi_error', 'GHI_ERROR']:
        var = 'ghi_error'
        wrf_var = var
    elif var in ['wpd_error', 'WPD_ERROR']:
        var = 'wpd_error'
        wrf_var = var
    elif var in ['fitness', 'Fitness', 'FITNESS']:
        var = 'fitness'
        wrf_var = var
    else:
        print(f'Variable {var} is not supported.')
        raise KeyError

    # Get the start_date and create the date string
    datestr = str(wrfds.Time.dt.strftime('%Y-%m-%d')[0].values)

    # To start, we need to get the WRF map projection information (a Lambert Conformal grid),
    # and find the domain boundaries in this projection.
    # NOTE: this task MUST occurr before we regrid the WRF variables or the coordinates change and become incompatible.
    wrf_cartopy_proj = get_wrf_proj(wrfds, 'dni')
    proj_bounds = get_domain_boundary(wrfds, wrf_cartopy_proj)

    # We can use a basic Plate Carree projection for ERA5
    era5_cartopy_proj = ccrs.PlateCarree()

    # Now, get the desired variables
    if var in ['ghi_error', 'wpd_error', 'fitness']:
        # Due to some obnioxious xarry nuance, the easiest way to keep the regridding function from adding additional
        # variables and coordinates to the xarray dataset in the outter scope, is just to open new datasets within
        # wrf_era5_regrid_xesmf; so that's why we must again specify the wrf and era5 file names below.
        wrf_file = f'wrfout_processed_d01_{datestr}_{paramstr}.nc'
        era_file = f'ERA5_EastUS_WPD-GHI_{datestr.split("-")[0]}-{datestr.split("-")[1]}.nc'
        wrfdat_proc, eradat_proc = optwrf.regridding.wrf_era5_regrid_xesmf(wrfdir=wrf_dir, wrffile=wrf_file,
                                                                           eradir=era_dir, erafile=era_file)

        # Calculate the error in GHI and WPD
        wrfdat_proc = optwrf.regridding.wrf_era5_error(wrfdat_proc, eradat_proc)
        if verbose:
            print(wrfdat_proc)

        # Calculate the fitness
        correction_factor = 0.0004218304553577255
        daylight_factor = helper_functions.daylight_frac(datestr)  # daylight fraction
        wrfdat_proc['fitness'] = daylight_factor * wrfdat_proc.ghi_error \
                                 + correction_factor * wrfdat_proc.wpd_error

    # Define the time indicies from the times variable
    time_indicies = range(0, len(wrfds.Time))
    # Format the times for title slides
    times_strings_f = wrfds.Time.dt.strftime('%b %d, %Y %H:%M')
    # Get the desired variable(s)
    for tidx in time_indicies:
        timestr = wrfds.Time[tidx].values
        timestr_f = times_strings_f[tidx].values
        if hourly:
            title_str = f'{short_title_str}\n{timestr_f} (UTC)'
        else:
            time_string_f = wrfds.Time[0].dt.strftime('%b %d, %Y')
            title_str = f'{short_title_str}\n{time_string_f.values}'

        # WRF Variable (divide by 1000 to convert from W to kW or Wh to kWh)
        if not hourly and tidx != 0:
            if src == 'wrf':
                if var in ['ghi', 'wpd']:
                    plot_var = plot_var + (wrfds[wrf_var].sel(Time=np.datetime_as_string(timestr)) / 1000)
                else:
                    plot_var = plot_var + wrfdat_proc[wrf_var].sel(Time=np.datetime_as_string(timestr))
            elif src == 'era5':
                if var in ['ghi', 'wpd']:
                    plot_var = plot_var + (erads[era_var].sel(Time=np.datetime_as_string(timestr)) / 1000)
                else:
                    print(f'Variable {var} is not provided by {src}')
                    raise ValueError
        else:
            if src == 'wrf':
                if var in ['ghi', 'wpd']:
                    plot_var = wrfds[wrf_var].sel(Time=np.datetime_as_string(timestr)) / 1000
                else:
                    plot_var = wrfdat_proc[wrf_var].sel(Time=np.datetime_as_string(timestr))
            elif src == 'era5':
                if var in ['ghi', 'wpd']:
                    plot_var = erads[era_var].sel(Time=np.datetime_as_string(timestr)) / 1000
                else:
                    print(f'Variable {var} is not provided by {src}')
                    raise ValueError

        if hourly:
            # Create a figure
            fig = plt.figure(figsize=(4, 4))

            # Set the GeoAxes to the projection used by WRF
            ax = fig.add_subplot(1, 1, 1, projection=wrf_cartopy_proj)

            # Make the countour lines for filled contours for the GHI
            contour_levels = specify_contour_levels(var, hourly=True, **kwargs)

            # Add the filled contour levels
            color_map = specify_clormap(var)
            if src == 'wrf' and var in ['ghi', 'wpd']:
                cn = ax.contourf(wrfpy.to_np(wrfds.lon), wrfpy.to_np(wrfds.lat), wrfpy.to_np(plot_var),
                                 contour_levels, transform=ccrs.PlateCarree(), cmap=color_map)
            else:
                cn = ax.contourf(wrfpy.to_np(erads.longitude), wrfpy.to_np(erads.latitude), wrfpy.to_np(plot_var),
                                 contour_levels, transform=ccrs.PlateCarree(), cmap=color_map)

            # Format the plot
            format_cnplot_axis(ax, cn, proj_bounds, title_str=title_str)

            # Save the figure(s)
            if save_fig:
                fig_path_temp = fig_path + str(tidx).zfill(2)
                plt.savefig(fig_path_temp + '.png', dpi=300, transparent=True, bbox_inches='tight')

            plt.show()

    if not hourly:
        # Create a figure
        fig = plt.figure(figsize=(4, 4))

        # Set the GeoAxes to the projection used by WRF
        ax = fig.add_subplot(1, 1, 1, projection=wrf_cartopy_proj)

        # Make the countour lines for filled contours
        contour_levels = specify_contour_levels(var, hourly=False, **kwargs)

        # Add the filled contour levels
        color_map = specify_clormap(var)
        if src == 'wrf' and var in ['ghi', 'wpd']:
            cn = ax.contourf(wrfpy.to_np(wrfds.lon), wrfpy.to_np(wrfds.lat), wrfpy.to_np(plot_var),
                             contour_levels, transform=ccrs.PlateCarree(), cmap=color_map)
        else:
            cn = ax.contourf(wrfpy.to_np(erads.longitude), wrfpy.to_np(erads.latitude), wrfpy.to_np(plot_var),
                             contour_levels, transform=ccrs.PlateCarree(), cmap=color_map)

        # Format the plot
        format_cnplot_axis(ax, cn, proj_bounds, title_str=title_str)

        # Save the figure(s)
        if save_fig:
            file_type = kwargs.get('file_type', '.pdf')
            plt.savefig(fig_path + file_type, dpi=300, transparent=True, bbox_inches='tight')

        plt.show()


def compare_wrf_era5_plot(var, wrfds, erads, hourly=False, save_fig=False, fig_path='./', **kwargs):
    """
    Creates a side-by-side comparison plot of WRF and ERA5 producing either a plot every hour
    or a single plot for the day.

    :param var:
    :param wrfds:
    :param erads:
    :param hourly:
    :param save_fig:
    :param fig_path:
    :param kwargs:

    :return: None
    """
    # Format the var input
    log_contour = False
    if type(var) is not str:
        print(f'The var input, {var}, must be a string.')
        raise TypeError
    if var in ['GHI', 'ghi']:
        var = 'ghi'
        wrf_var = 'ghi'
        era_var = 'GHI'
    elif var in ['WPD', 'wpd']:
        var = 'wpd'
        wrf_var = 'wpd'
        era_var = 'WPD'
        log_contour = True
    else:
        print(f'Variable {var} is not supported.')
        raise KeyError

    # To start, we need to get the WRF map projection information (a Lambert Conformal grid),
    # and find the domain boundaries in this projection.
    # NOTE: this task MUST occurr before we regrid the WRF variables or the coordinates change and become incompatible.
    wrf_cartopy_proj = get_wrf_proj(wrfds, 'dni')
    proj_bounds = get_domain_boundary(wrfds, wrf_cartopy_proj)

    # We can use a basic Plate Carree projection for ERA5
    era5_cartopy_proj = ccrs.PlateCarree()

    # Now, get the desired variables
    # Define the time indicies from the times variable
    time_indicies = range(0, len(wrfds.Time))
    # Format the times for title slides
    times_strings_f = wrfds.Time.dt.strftime('%b %d, %Y %H:%M')
    times_strings_ff = wrfds.Time.dt.strftime('%b %d, %Y %H:00')
    # Get the desired variable(s)
    for tidx in time_indicies:
        timestr = wrfds.Time[tidx].values
        timestr_f = times_strings_f[tidx].values
        timestr_ff = times_strings_ff[tidx].values
        if hourly:
            title_str = f'{era_var} (kW m-2)\n{timestr_f} (UTC)'
        else:
            time_string_f = wrfds.Time[0].dt.strftime('%b %d, %Y')
            title_str = f'{era_var} (kWh m$^{{-2}}$ day$^{{-1}}$) \n{time_string_f.values}'

        # WRF Variable (divide by 1000 to convert from W to kW or Wh to kWh)
        if not hourly and tidx != 0:
            plot_wrfvar = plot_wrfvar + (wrfds[wrf_var].sel(Time=np.datetime_as_string(timestr)) / 1000)
        else:
            plot_wrfvar = wrfds[wrf_var].sel(Time=np.datetime_as_string(timestr)) / 1000

        # ERA5 GHI (divide by 1000 to convert from W to kW or Wh to kWh)
        if not hourly and tidx != 0:
            # plot_era5var = plot_era5var + (erads[era_var].sel(Time=timestr_f) / 1000)
            plot_era5var = plot_era5var + (erads[era_var].sel(Time=timestr_ff) / 1000)
        else:
            # plot_era5var = erads[era_var].sel(Time=timestr_f) / 1000
            plot_era5var = erads[era_var].sel(Time=timestr_ff) / 1000

        # Create hourly plots
        if hourly:
            # Create a figure
            # fig, (ax_wrf, ax_era5, cax) = plt.subplots(ncols=3, figsize=(6.5, 2.4),
            #                                            gridspec_kw={"width_ratios": [1, 1, 0.05]})
            fig = plt.figure(figsize=(6.5, 2.4))

            # Set the GeoAxes to the projection used by WRF
            ax_wrf = fig.add_subplot(1, 2, 1, projection=wrf_cartopy_proj)
            ax_era5 = fig.add_subplot(1, 2, 2, projection=wrf_cartopy_proj, sharey=ax_wrf)

            # Make the countour lines for filled contours for the GHI
            contour_levels = specify_contour_levels(var, hourly=True, **kwargs)

            # Add the filled contour levels
            color_map = specify_clormap(var)
            wrf_cn = ax_wrf.contourf(wrfpy.to_np(wrfds.lon), wrfpy.to_np(wrfds.lat), wrfpy.to_np(plot_wrfvar),
                                     contour_levels, transform=ccrs.PlateCarree(), cmap=color_map)
            era5_cn = ax_era5.contourf(wrfpy.to_np(erads.longitude), wrfpy.to_np(erads.latitude),
                                       wrfpy.to_np(plot_era5var),
                                       contour_levels, transform=era5_cartopy_proj, cmap=color_map)

            # Format the plots
            format_cnplot_axis(ax_wrf, wrf_cn, proj_bounds,
                               title_str=f'OptWRF {title_str}', add_colorbar=False)
            format_cnplot_axis(ax_era5, era5_cn, proj_bounds,
                               title_str=f'ERA5 {title_str}', add_colorbar=False)

            # Add a color bar to the full plot
            fig.subplots_adjust(right=0.85)
            cbar_ax = fig.add_axes([0.90, 0.2, 0.03, 0.6])
            fig.colorbar(era5_cn, cax=cbar_ax)

            # Save the figures
            if save_fig:
                fig_path_temp = fig_path + str(tidx).zfill(2)
                plt.savefig(fig_path_temp + '.png', dpi=300, transparent=True, bbox_inches='tight')

            plt.show()

    if not hourly:
        # Create a figure
        fig = plt.figure(figsize=(6.5, 2.4))

        # Set the GeoAxes to the projection used by WRF
        ax_wrf = fig.add_subplot(1, 2, 1, projection=wrf_cartopy_proj)
        ax_era5 = fig.add_subplot(1, 2, 2, projection=wrf_cartopy_proj, sharey=ax_wrf)

        # Add the filled contour levels
        color_map = specify_clormap(var)
        if log_contour:
            maximum = kwargs.get('max', 50000)
            wrf_cn = ax_wrf.contourf(wrfpy.to_np(wrfds.lon), wrfpy.to_np(wrfds.lat), wrfpy.to_np(plot_wrfvar),
                                     locator=ticker.LogLocator(subs='all'), norm=LogNorm(vmax=maximum),
                                     transform=ccrs.PlateCarree(), cmap=color_map)
            era5_cn = ax_era5.contourf(wrfpy.to_np(erads.longitude), wrfpy.to_np(erads.latitude),
                                       wrfpy.to_np(plot_era5var),
                                       locator=ticker.LogLocator(subs='all'), norm=LogNorm(vmax=maximum),
                                       transform=era5_cartopy_proj, cmap=color_map)
        else:
            # Make the countour lines for filled contours for the GHI
            contour_levels = specify_contour_levels(var, hourly=False, **kwargs)

            wrf_cn = ax_wrf.contourf(wrfpy.to_np(wrfds.lon), wrfpy.to_np(wrfds.lat), wrfpy.to_np(plot_wrfvar),
                                     contour_levels, transform=ccrs.PlateCarree(), cmap=color_map)
            era5_cn = ax_era5.contourf(wrfpy.to_np(erads.longitude), wrfpy.to_np(erads.latitude), wrfpy.to_np(plot_era5var),
                                       contour_levels, transform=era5_cartopy_proj, cmap=color_map)

        # Format the plots
        format_cnplot_axis(ax_wrf, wrf_cn, proj_bounds,
                           title_str=f'OptWRF {title_str}', add_colorbar=False)
        format_cnplot_axis(ax_era5, era5_cn, proj_bounds,
                           title_str=f'ERA5 {title_str}', add_colorbar=False)

        # Add a color bar to the full plot
        # cbar_tick_labels = ['0', '1', '2', '3', '4', '5']
        fig.subplots_adjust(right=0.85)
        cbar_ax = fig.add_axes([0.85, 0.125, 0.02, 0.755])  # dimensions [left, bottom, width, height] of the new axes

        cbar = fig.colorbar(era5_cn, cax=cbar_ax,
                            ticks=ticker.LogLocator(),
                            )
        # cbar.ax.set_yticklabels(cbar_tick_labels)  # vertically oriented colorbar

        # Save the figure
        if save_fig:
            file_type = kwargs.get('file_type', '.pdf')
            plt.savefig(fig_path + file_type, dpi=300, transparent=True, bbox_inches='tight')
        plt.show()


def wrf_errorandfitness_plot(wrfds, paramstr, save_fig=False, wrf_dir='./', era_dir='./',
                             fig_path='./', verbose=False, fitness_short_title='Model Fitness',
                             ghi_error_short_title='GHI Error (kWh m-2 day-1)',
                             wpd_error_short_title='WPD Error (kWh m-2 day-1)', **kwargs):
    """
    Plots the GHI error, WPD error, and fitness maps all within one 3-panel plot.

    :param wrfds:
    :param paramstr:
    :param save_fig:
    :param wrf_dir:
    :param era_dir:
    :param fig_path:
    :param verbose:
    :param fitness_short_title:
    :param ghi_error_short_title:
    :param wpd_error_short_title:
    :param kwargs:

    :return: None
    """
    # Get the start_date and create the date string
    start_date = str(wrfds.Time.dt.strftime('%b %d %Y')[0].values)
    datestr = str(wrfds.Time.dt.strftime('%Y-%m-%d')[0].values)

    # To start, we need to get the WRF map projection information (a Lambert Conformal grid),
    # and find the domain boundaries in this projection.
    # NOTE: this task MUST occurr before we regrid the WRF variables or the coordinates change and become incompatible.
    wrf_cartopy_proj = get_wrf_proj(wrfds, 'dni')
    proj_bounds = get_domain_boundary(wrfds, wrf_cartopy_proj)
    if verbose:
        print(f'WRF Projection:\n{wrf_cartopy_proj}')
        print(f'\nDomain Boundaries:\n{proj_bounds}')

    # Regrid the wrf GHI and WPD
    # Due to some obnioxious xarry nuance, the easiest way to keep the regridding function from adding additional
    # variables and coordinates to the xarray dataset in the outter scope, is just to open new datasets within
    # wrf_era5_regrid_xesmf; so that's why we must again specify the wrf and era5 file names below.
    # wrf_file = f'wrfout_processed_d01_{datestr}_{paramstr}.nc'
    wrf_file = f'processed_wrfout_d01_{datestr}_00:00:00'                            
    era_file = f'ERA5_EastUS_WPD-GHI_{datestr.split("-")[0]}-{datestr.split("-")[1]}.nc'
    if verbose:
        print(wrf_dir+wrf_file)
        print(era_dir+era_file)
    wrfds, eradata = optwrf.regridding.wrf_era5_regrid_xesmf(wrfdir=wrf_dir, wrffile=wrf_file,
                                                             eradir=era_dir, erafile=era_file)

    # Calculate the error in GHI and WPD
    wrfds = optwrf.regridding.wrf_era5_error(wrfds, eradata)

    # Calculate the fitness
    correction_factor = 0.0004218304553577255
    daylight_factor = helper_functions.daylight_frac(start_date)  # daylight fraction
    wrfds['fitness'] = daylight_factor * wrfds.total_ghi_error + correction_factor * wrfds.total_wpd_error

    # Create a figure
    fig = plt.figure(figsize=(9.5, 3))

    # Set the GeoAxes to the projection used by WRF
    ax_fitness = fig.add_subplot(1, 3, 1, projection=wrf_cartopy_proj)
    ax_ghierr = fig.add_subplot(1, 3, 2, projection=wrf_cartopy_proj, sharey=ax_fitness)
    ax_wpderr = fig.add_subplot(1, 3, 3, projection=wrf_cartopy_proj, sharey=ax_ghierr)

    # Create the filled contour levels
    fitness_cn = ax_fitness.contourf(wrfpy.to_np(wrfds.lon), wrfpy.to_np(wrfds.lat),
                                     wrfpy.to_np(wrfds['fitness']),
                                     # np.linspace(0, np.amax(wrfds['fitness']), 22),
                                     np.linspace(0, 7, 22),
                                     transform=ccrs.PlateCarree(), cmap=get_cmap("Greys"))
    ghierr_cn = ax_ghierr.contourf(wrfpy.to_np(wrfds.lon), wrfpy.to_np(wrfds.lat),
                                   wrfpy.to_np(wrfds['total_ghi_error']),
                                   # np.linspace(0, np.amax(wrfds['total_ghi_error']), 22),
                                   np.linspace(0, 2.5, 22),
                                   transform=ccrs.PlateCarree(), cmap=get_cmap("hot_r"))
    wpderr_cn = ax_wpderr.contourf(wrfpy.to_np(wrfds.lon), wrfpy.to_np(wrfds.lat),
                                   wrfpy.to_np(wrfds['total_wpd_error']),
                                   # np.linspace(0, np.amax(wrfds['total_wpd_error']), 22),
                                   # np.linspace(0, 5000, 22),
                                   locator=ticker.LogLocator(subs='all'), norm=LogNorm(vmax=5000),
                                   transform=ccrs.PlateCarree(), cmap=get_cmap("Greens"))

    # Format the axes
    time_string_f = wrfds.Time[0].dt.strftime('%b %d, %Y')
    format_cnplot_axis(ax_fitness, fitness_cn, proj_bounds,
                       title_str=f'{fitness_short_title}\n{time_string_f.values}',
                       cbar_ticks=[0, 1, 2, 3, 4, 5, 6, 7],
                       cbar_tick_labels=['0', '1', '2', '3', '4', '5', '6', '7'])
    format_cnplot_axis(ax_ghierr, ghierr_cn, proj_bounds,
                       title_str=f'{ghi_error_short_title}\n{time_string_f.values}',
                       cbar_ticks=[0, 0.5, 1.0, 1.5, 2.0, 2.5],
                       cbar_tick_labels=['0', '0.5', '1.0', '1.5', '2.0', '2.5'])
    format_cnplot_axis(ax_wpderr, wpderr_cn, proj_bounds,
                       title_str=f'{wpd_error_short_title}\n{time_string_f.values}',
                       cbar_ticks=ticker.LogLocator()
                       )
    if save_fig:
        file_type = kwargs.get('file_type', '.pdf')
        plt.savefig(fig_path + file_type, dpi=300, transparent=True, bbox_inches='tight')

    plt.show()


def wrf_plot(var, wrfds, hourly=False, save_fig=False, manual_color_map=None,
             short_title_str='Title', fig_path='./', verbose=False, **kwargs):
    """
    Creates a single WRF or ERA5 plot, using the WRF bounds, producing either a plot every hour
    or a single plot for the day.

    :param var:
    :param wrfds:
    :param hourly:
    :param save_fig:
    :param short_title_str:
    :param fig_path:
    :param verbose:
    :param kwargs:

    :return: None
    """
    # Get the start_date and create the date string
    datestr = str(wrfds.Time.dt.strftime('%Y-%m-%d')[0].values)

    # To start, we need to get the WRF map projection information (a Lambert Conformal grid),
    # and find the domain boundaries in this projection.
    # NOTE: this task MUST occurr before we regrid the WRF variables or the coordinates change and become incompatible.
    wrf_cartopy_proj = get_wrf_proj(wrfds, 'temp')
    wrf_cartopy_proj = get_wrf_proj(wrfds, 'dni')
    proj_bounds = get_domain_boundary(wrfds, wrf_cartopy_proj)

    # Now, get the desired variables
    # Define the time indicies from the times variable
    time_indicies = range(0, len(wrfds.Time))
    # Format the times for title slides
    times_strings_f = wrfds.Time.dt.strftime('%b %d, %Y %H:%M')
    # Get the desired variable(s)
    for tidx in time_indicies:
        timestr = wrfds.Time[tidx].values
        timestr_f = times_strings_f[tidx].values
        if hourly:
            title_str = f'{short_title_str}\n{timestr_f} (UTC)'
        else:
            time_string_f = wrfds.Time[0].dt.strftime('%b %d, %Y')
            title_str = f'{short_title_str}\n{time_string_f.values}'

        # WRF Variable
        if not hourly and tidx != 0:
            plot_var = plot_var + wrfds[var].sel(Time=np.datetime_as_string(timestr))

        else:
            plot_var = wrfds[var].sel(Time=np.datetime_as_string(timestr))

        if hourly:
            # Create a figure
            fig = plt.figure(figsize=(4, 4))

            # Set the GeoAxes to the projection used by WRF
            ax = fig.add_subplot(1, 1, 1, projection=wrf_cartopy_proj)

            # Make the countour lines for filled contours
            contour_levels = specify_contour_levels(var, hourly=True, **kwargs)

            # Add the filled contour levels
            if manual_color_map is not None:
                color_map = get_cmap(manual_color_map)
            else:
                color_map = specify_clormap(var)
            # cn = ax.contourf(wrfpy.to_np(wrfds.XLONG), wrfpy.to_np(wrfds.XLAT), wrfpy.to_np(plot_var),
            #                  contour_levels, transform=ccrs.PlateCarree(), cmap=color_map)
            cn = ax.contourf(wrfpy.to_np(wrfds.lon), wrfpy.to_np(wrfds.lat), wrfpy.to_np(plot_var),
                             contour_levels, transform=ccrs.PlateCarree(), cmap=color_map)

            # Format the plot
            format_cnplot_axis(ax, cn, proj_bounds, title_str=title_str)

            # Save the figure(s)
            if save_fig:
                fig_path_temp = fig_path + str(tidx).zfill(2)
                plt.savefig(fig_path_temp + '.png', dpi=300, transparent=True, bbox_inches='tight')

            plt.show()

    if not hourly:
        # Create a figure
        fig = plt.figure(figsize=(4, 4))

        # Set the GeoAxes to the projection used by WRF
        ax = fig.add_subplot(1, 1, 1, projection=wrf_cartopy_proj)

        # Make the countour lines for filled contours
        contour_levels = specify_contour_levels(var, hourly=False, **kwargs)

        # Add the filled contour levels
        if manual_color_map is not None:
            color_map = get_cmap(manual_color_map)
        else:
            color_map = specify_clormap(var)
        # cn = ax.contourf(wrfpy.to_np(wrfds.XLONG), wrfpy.to_np(wrfds.XLAT), wrfpy.to_np(plot_var),
        #                  contour_levels, transform=ccrs.PlateCarree(), cmap=color_map)
        cn = ax.contourf(wrfpy.to_np(wrfds.lon), wrfpy.to_np(wrfds.lat), wrfpy.to_np(plot_var),
                         contour_levels, transform=ccrs.PlateCarree(), cmap=color_map)

        # Format the plot
        format_cnplot_axis(ax, cn, proj_bounds, title_str=title_str)

        # Save the figure(s)
        if save_fig:
            file_type = kwargs.get('file_type', '.pdf')
            plt.savefig(fig_path + file_type, dpi=300, transparent=True, bbox_inches='tight')

        plt.show()
