#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Initializing Twitter Tools...${NC}"

# Function to check Python version
check_python_version() {
    local version
    version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if [[ $(echo "$version 3.12" | awk '{print ($1 >= $2)}') -eq 0 ]]; then
        echo -e "${RED}Python 3.12 is required, but found version $version${NC}"
        echo -e "${YELLOW}Please install Python 3.12:${NC}"
        echo "  - macOS: brew install python@3.12"
        echo "  - Linux: Use your distribution's package manager"
        echo "  - Windows: Download from python.org"
        exit 1
    fi
    echo -e "${GREEN}Found Python $version${NC}"
}

# Check if Python 3.12 is installed and available
if ! command -v python3.12 &> /dev/null; then
    echo -e "${RED}Python 3.12 is required but not installed.${NC}"
    echo -e "${YELLOW}Please install Python 3.12:${NC}"
    echo "  - macOS: brew install python@3.12"
    echo "  - Linux: Use your distribution's package manager"
    echo "  - Windows: Download from python.org"
    exit 1
fi

# Verify Python version
check_python_version

# Check if Node.js and npm are installed
if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
    echo -e "${RED}Node.js and npm are required but not installed. Please install them first.${NC}"
    exit 1
fi

# Remove any existing env directory if it exists (we use venv)
if [ -d "env" ]; then
    echo -e "${YELLOW}Removing old env directory...${NC}"
    rm -rf env
    echo -e "${GREEN}Old env directory removed.${NC}"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment with Python 3.12...${NC}"
    python3.12 -m venv venv
    echo -e "${GREEN}Virtual environment created.${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists.${NC}"
    echo -e "${YELLOW}Checking Python version in virtual environment...${NC}"
    source venv/bin/activate
    venv_version=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if [[ $(echo "$venv_version 3.12" | awk '{print ($1 >= $2)}') -eq 0 ]]; then
        echo -e "${RED}Virtual environment is using Python $venv_version, but 3.12 is required${NC}"
        echo -e "${YELLOW}Removing old virtual environment...${NC}"
        deactivate
        rm -rf venv
        echo -e "${YELLOW}Creating new virtual environment with Python 3.12...${NC}"
        python3.12 -m venv venv
        echo -e "${GREEN}New virtual environment created.${NC}"
    else
        echo -e "${GREEN}Virtual environment is using Python $venv_version${NC}"
    fi
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Verify we're using the right Python version in the virtual environment
venv_python_version=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if [[ "$venv_python_version" != "3.12" ]]; then
    echo -e "${RED}Error: Virtual environment is using Python $venv_python_version instead of 3.12${NC}"
    echo -e "${YELLOW}Please remove the venv directory and run init.sh again:${NC}"
    echo "    rm -rf venv"
    echo "    ./init.sh"
    exit 1
fi

# Install/upgrade pip and requirements
echo -e "${YELLOW}Upgrading pip and installing requirements...${NC}"
python -m pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo -e "${RED}requirements.txt not found. Please create one with your dependencies.${NC}"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env template file...${NC}"
    python3 -c "from config import create_env_template; create_env_template()"
    echo -e "${GREEN}.env template created. Please fill in your Twitter API credentials.${NC}"
fi

# Create data directory for local storage
if [ ! -d "data" ]; then
    echo -e "${YELLOW}Creating data directory for local storage...${NC}"
    mkdir -p data
    echo -e "${GREEN}Data directory created.${NC}"
fi

# Set up frontend if it doesn't exist
if [ ! -d "frontend" ]; then
    echo -e "${YELLOW}Setting up React frontend with Vite...${NC}"
    npm create vite@latest frontend -- --template react-ts
    cd frontend
    npm install
    # Add additional frontend dependencies
    npm install @tanstack/react-query axios @mantine/core @mantine/hooks @emotion/react
    cd ..
    echo -e "${GREEN}Frontend setup complete.${NC}"
fi

# Create frontend .env file if it doesn't exist
if [ ! -f "frontend/.env" ]; then
    echo -e "${YELLOW}Creating frontend .env file...${NC}"
    cat > frontend/.env << EOL
VITE_API_URL=http://localhost:8000
EOL
    echo -e "${GREEN}Frontend .env file created.${NC}"
fi

echo -e "${GREEN}Initialization complete!${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Fill in your Twitter API credentials in the .env file"
echo "2. Activate the virtual environment: source venv/bin/activate"
echo "3. Start the development servers: ./run.sh"
echo -e "\n${YELLOW}Project structure:${NC}"
echo "├── src/              # Backend Python code"
echo "├── frontend/         # React frontend"
echo "├── data/            # Local data storage"
echo "├── .env             # Backend environment variables"
echo "└── frontend/.env    # Frontend environment variables"
echo -e "\n${YELLOW}Python version:${NC}"
echo "Using Python 3.12 in virtual environment"
