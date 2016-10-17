# tsim TinyOS TOSSIM simulation helper.

tsim is a TOSSIM simulation tool that configures the simulation environment and
runs the simulation according to external configuration files.

## TOSSIM and TOSSIM Live

The tsim simulation helper can run regular and live simulations. To run a TOSSIM
Live simulation compile your code for the sim-sf target and start tsim.py with
the --live option. TOSSIM Live simulations can also be run without the --live
option.

## Booting nodes

Node booting can be specified in the boot configuration file. The format of the
file is simple, the first item of each line is the node id written in base 16.
After that boot and shutdown times follow, separated by commas:
    NODE_ID, start1, stop1, start2, stop2, ...

The start and stop times are in milliseconds. There should only be one line per
node, the number of start and stop times are not limited, though they should
always increase, that is start2 > stop1 > start1.

See tsim_boots.txt for examples

## Node radio links

Node connections can be configured through a CSV table. The header line of the
CSV file needs to start with ---- and must contain all referenced node id's.
The following lines start with the node id and each cell of the table indicates
a gain from this node to the node indicated in the column header. An empty cell
indicates no connection.

The following table specifies symmetric links between 1<->2 and 2<->3, 1 and 3
cannot hear each other.

----,0001,0002,0003
0001,    , -50,
0002, -50,    , -50
0003,    , -50,

See tsim_links.csv for examples.

A nice CSV editing tool is DMcsvEditor: http://code.google.com/p/dmcsveditor

## Log configuration

Tossim has a logging system that is used with the dbg command from nesC code.
Messages to dbg end up in different channels. These channels can be directed to
different files through the logs configuration file. In the configuration file
the first item on a line is the file name and the second is the channel name.
Log messages can be sent to stdout by specifying the file name stdout.

All loglevels.h based messages end up in the TOSSIM dbg channel called
"dbgchannel".

See tsim_logs.txt for examples.

Additionally it is possible to configure some log processing for the stdout and
save a processed log in a file. This is done with the --process-stdout and
--pretty_stdout options. The side effect is that everything directed to stdout
also gets saved in stdout.txt.

## Simulation scripts

It is possible to write custom simulation scripts and load them from tsim. The
simulation script file is specified with the --simulation-script option and the
file needs to contain a function get_simulation_script that takes the
TossimSimulation object as an argument. The returned object must have a tick()
function, which will be called by tsim once every simulation loop.

See tsim_script.py for an example.

--------------------------------------------------------------------------------

## Requirements
tinyos
python-dev