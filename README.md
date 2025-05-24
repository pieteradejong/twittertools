# Twitter(X) Tools

[![twittertools](https://github.com/pieteradejong/twittertools/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/pieteradejong/twittertools/actions/workflows/ci.yml)

A full-stack application for analyzing and managing Twitter/X data, featuring a Python FastAPI backend and React frontend.

## Features

* Twitter API Integration
  * Fetch and analyze Twitter likes and tweets
  * User authentication and profile management
  * Rate limit handling
* Data Management
  * Local storage of Twitter data
  * Tweet classification and analysis
  * User engagement metrics
* Modern Interface
  * RESTful API with OpenAPI documentation
  * CLI interface for quick data access
  * React frontend for data visualization
  * List management and recommendations

## Prerequisites

* Python 3.8 or higher
* Node.js 16 or higher and npm
* Twitter/X API credentials:
  * API Key
  * API Secret
  * Access Token
  * Access Token Secret
  * Bearer Token

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/pieteradejong/twittertools.git
cd twittertools
```

2. Run the initialization script:
```bash
./init.sh
```

3. Fill in your Twitter API credentials in the `.env` file

4. Start the development servers:
```bash
./run.sh
```

The application will be available at:
* Frontend: http://localhost:5173
* Backend API: http://localhost:8000
* API Documentation: http://localhost:8000/docs

## Development

### Project Structure
```
twittertools/
├── src/                    # Backend Python code
│   ├── main.py            # FastAPI application and CLI
│   ├── config.py          # Configuration management
│   └── __pycache__/       # Python cache files
├── frontend/              # React frontend (Vite)
│   ├── src/              # React source code
│   └── .env              # Frontend environment variables
├── data/                 # Local data storage
│   └── twittertools.db   # SQLite database
├── .env                  # Backend environment variables
├── init.sh               # Setup script
└── run.sh                # Development server script
```

### Backend Development
The backend is built with FastAPI and provides:

#### API Endpoints
* `GET /health` - Health check endpoint
* `GET /api/me` - Get authenticated user info
* `GET /api/likes` - Get recent likes (with optional count parameter)

#### Features
* Twitter API integration with OAuth and Bearer token support
* Data storage and analysis
* RESTful API with OpenAPI documentation
* Tweet classification (coming soon)
* CLI interface for quick data access

To run the backend server separately:
```bash
source env/bin/activate
python -m uvicorn src.main:app --reload
```

To use the CLI interface:
```bash
source env/bin/activate
python -m src.main --number 10  # Fetch 10 recent likes
```

> **Note:** Always run the CLI as a module (with `-m src.main`) from the project root to ensure imports work for both CLI and API modes.

### Frontend Development
The frontend is built with:
* React + TypeScript
* Vite for development
* Mantine UI components
* React Query for data fetching

To run the frontend development server separately:
```bash
cd frontend
npm run dev
```

## API Documentation
Once the backend server is running, visit:
* Swagger UI: http://localhost:8000/docs
* ReDoc: http://localhost:8000/redoc

The API documentation includes:
* Interactive API testing
* Request/response schemas
* Authentication requirements
* Example requests

## Current Status

### Completed Features
* [x] Twitter API integration
* [x] Basic API endpoints
* [x] CLI interface
* [x] Configuration management
* [x] Health check endpoint
* [x] User authentication
* [x] Likes fetching

### In Progress
* [ ] Frontend implementation
* [ ] Tweet classification
* [ ] Data visualization
* [ ] List management

### Planned Features
* [ ] User engagement metrics
* [ ] Tweet analysis
* [ ] List recommendations
* [ ] Block/unblock management
* [ ] Follow/unfollow tracking

## Contributing
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License
[Add your license here]

[DEPRECATED] ~~## Functional requirements~~
* show who I blocked and when, plus reminders to potentially unblock
* show who is not following me back
* show who I am not following back
* attempt to group tweeps I follow into lists that make sense
* attempt to classify and storify my favorites in ways that make sense
* when viewing another user's profile, recommend which if any of your lists that user would be a good fit for
* reply ranking
* for user: ratio replies/original
* for user: how often replies to replies?
* given tweet, find all instances of quoted tweet
* brief into qustionairre to get you started
