#!/bin/bash
# GUI_Start.sh
# Created: 4/25/13
# Last Modified: 5/16/13
# Author: Ryan Blais

# Description:
# Starts the experimental control gui. 

LABRAD_ACTIVATE="/home/resonator/.virtualenvs/labrad/bin/activate" # virtualenv activate script
GUI_SCRIPT="/home/resonator/labrad/resonator/clients/ResonatorGUI.py" # script that starts the gui (from python)
GUI_SWITCH="/home/resonator/labrad/resonator/clients/SWITCH_CONTROL.py" #script that starts the gui (from python)
VIRTUALENV_ERR=111 # error accessing virtualenv
GUI_START_ERR=129 # could not start the gui

# Activate the labrad virtualenv
if [ -f $LABRAD_ACTIVATE ]; then
    source $LABRAD_ACTIVATE
else
    echo "Error: Could not activate the labrad virtual environment."
    printf "Press ENTER to close"; read close
    exit $VIRTUALENV_ERR
fi

# Start the gui
if [ -f $GUI_SCRIPT ]; then
    python $GUI_SCRIPT &
    python $GUI_SWITCH

else
    echo "Error: Could not find the gui startup script: $GUI_SCRIPT"
    printf "Press ENTER to close"; read close
    exit $GUI_START_ERR
fi
