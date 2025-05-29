#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if script is being sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo -e "${RED}Error: This script must be sourced, not executed directly${NC}"
    echo -e "${YELLOW}Please use:${NC}"
    echo "    source ./activate.sh"
    echo "    # or"
    echo "    . ./activate.sh"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}Virtual environment not found.${NC}"
    echo -e "${YELLOW}Please run ./init.sh first to create it.${NC}"
    return 1
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Verify activation
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${RED}Failed to activate virtual environment${NC}"
    return 1
fi

# Show Python version
python_version=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "${GREEN}Virtual environment activated with Python $python_version${NC}"
echo -e "${YELLOW}You can now run Python commands or scripts.${NC}"
echo -e "${YELLOW}To deactivate, simply type 'deactivate'${NC}" 