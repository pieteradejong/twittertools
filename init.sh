#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Initializing Twitter Tools...${NC}"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is required but not installed. Please install Python 3 first.${NC}"
    exit 1
fi

# Check if Node.js and npm are installed
if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
    echo -e "${RED}Node.js and npm are required but not installed. Please install them first.${NC}"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "env" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv env
    echo -e "${GREEN}Virtual environment created.${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source env/bin/activate

# Install/upgrade pip and requirements
echo -e "${YELLOW}Upgrading pip and installing requirements...${NC}"
pip install --upgrade pip
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
echo "2. Activate the virtual environment: source env/bin/activate"
echo "3. Start the development servers: ./run.sh"
echo -e "\n${YELLOW}Project structure:${NC}"
echo "├── src/              # Backend Python code"
echo "├── frontend/         # React frontend"
echo "├── data/            # Local data storage"
echo "├── .env             # Backend environment variables"
echo "└── frontend/.env    # Frontend environment variables"
