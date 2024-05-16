#!/bin/csh

#SBATCH -J wrf			# Job name
#SBATCH -o /home/by276/models/met4ene/wrfout/logs/output.wrf.%j		# Name of stdout output file(%j expands to jobId)
#SBATCH -e /home/by276/models/met4ene/wrfout/logs/errors.wrf.%j		# Name of stderr output file(%j expands to jobId)
#SBATCH --ntasks=32		# Total number of tasks to be configured for.
#SBATCH --tasks-per-node=32	# sets number of tasks to run on each node.
#SBATCH --cpus-per-task=1	# sets number of cpus needed by each task (if task is "make -j3" number should be 3).
#SBATCH --get-user-env		# tells sbatch to retrieve the users login environment. 
#SBATCH -t 200:00:00		# Run time (hh:mm:ss)
#SBATCH --mem=50000M		# memory required per node
#SBATCH --partition=default_partition	# Which queue it should run on.

if ( $#argv == 1 ) then
    cd $argv
    set runwrfdir = $argv
else
    echo "Warning: runwrf.csh takes at most one input."
    echo "         running WRF in current directory."
    set runwrfdir = "./"
endif

limit stacksize unlimited

### -----------  run wrf ---------------------------
/usr/bin/mpirun -np 32 ${argv}wrf.exe

exit
