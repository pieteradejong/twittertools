#!/bin/bash

# USAGE: after running init.sh, don't forget to activate virtualenv: 'source venv/bin/activate'

# create Python virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# activate virtual environment
source venv/bin/activate

# install dependencies
pip install -r requirements.txt

# Additional setup steps can be added here

echo
echo -e "\033[0;32mInitialization complete! Use 'source venv/bin/activate' to activate the virtual environment.\033[0m"
