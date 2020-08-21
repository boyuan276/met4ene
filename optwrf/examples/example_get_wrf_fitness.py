"""
Get WRF Fitness
===============

This example lets you manually determine the fitness for any physics option set on any date
(provided that it's within the ERA5 date range).
"""

import optwrf.optimize_wrf_physics as owp


# Specify desired physics options set below
param_ids = [8, 7, 3, 1, 1, 10, 1]

# Specify the desired start date below
start_date = 'Dec 11  2011'
end_date = 'Dec 12 2011'

# Run get wrf fitness function
fitness, ghi_mean_error, wpd_mean_error, runtime = owp.get_wrf_fitness(param_ids, start_date, end_date,
                                                                       disable_timeout=True, verbose=True)
print(f'==========================================================================')
print(f'Physics Options Set: {param_ids}\tStart Date: {start_date}')
print(f'Fitness: {fitness}\tGHI Error: {ghi_mean_error}\tWPD Error: {wpd_mean_error}\tSim Runtime: {runtime}')