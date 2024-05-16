#!/bin/csh

#SBATCH -J real			# Job name
#SBATCH -o /home/by276/models/met4ene/wrfout/logs/output.real.%j		# Name of stdout output file(%j expands to jobId)
#SBATCH -e /home/by276/models/met4ene/wrfout/logs/errors.real.%j		# Name of stderr output file(%j expands to jobId)
#SBATCH --ntasks=8		# Total number of tasks to be configured for. 
#SBATCH --tasks-per-node=8	# sets number of tasks to run on each node.
#SBATCH --cpus-per-task=1	# sets number of cpus needed by each task (if task is "make -j3" number should be 3).
#SBATCH --get-user-env		# tells sbatch to retrieve the users login environment. 
#SBATCH -t 00:30:00		# Run time (hh:mm:ss) 
#SBATCH --mem=10000M		# memory required per node
#SBATCH --partition=default_partition	# Which queue it should run on.

if ( $#argv == 1 ) then
    cd $argv
    set wrfoutdir = $argv
else
    echo " runreal.csh takes at most one input. "
    set wrfoutdir = "./"
endif

limit stacksize unlimited

### -----------  run real ---------------------------
/usr/bin/mpirun -np 8 ${argv}real.exe

exit
