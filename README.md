# Twitter(X) Tools

[![twittertools](https://github.com/pieteradejong/twittertools/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/pieteradejong/twittertools/actions/workflows/ci.yml)

A full-stack application for analyzing and managing Twitter/X data, featuring a Python FastAPI backend and React frontend.

## Features

* Twitter API Integration
  * Fetch and analyze Twitter likes, tweets, and bookmarks
  * User authentication and profile management
  * Rate limit handling with automatic retries
  * Secure credential caching
* Data Management
  * Local SQLite storage of Twitter data
  * Tweet classification and analysis
  * User engagement metrics
  * Media attachment tracking
* Modern Interface
  * RESTful API with OpenAPI documentation
  * CLI interface for quick data access
  * React frontend for data visualization
  * List management and recommendations
* Development Tools
  * Colored logging with status indicators
  * Progress tracking and resumable downloads
  * Comprehensive error handling
  * Rate limit monitoring

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
├── scripts/               # Utility scripts
│   └── download_x_data.py # Twitter data downloader
├── frontend/              # React frontend (Vite)
│   ├── src/              # React source code
│   └── .env              # Frontend environment variables
├── data/                 # Local data storage
│   ├── x_data.db        # SQLite database
│   └── auth_cache.json  # Credential cache
├── logs/                 # Application logs
│   └── download.log     # Data download logs
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
* `GET /api/tweets` - Get user tweets
* `GET /api/bookmarks` - Get user bookmarks

#### Features
* Twitter API integration with OAuth and Bearer token support
* Data storage and analysis
* RESTful API with OpenAPI documentation
* Tweet classification (coming soon)
* CLI interface for quick data access
* Colored logging with status indicators
* Rate limit handling with automatic retries

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

To download Twitter data:
```bash
source env/bin/activate
python scripts/download_x_data.py  # Downloads tweets, likes, and bookmarks
```

> **Note:** Always run the CLI as a module (with `-m src.main`) from the project root to ensure imports work for both CLI and API modes.

### Frontend Development
The frontend is built with:
* React + TypeScript
* Vite for development
* **Tailwind CSS** for all styling
* **Headless UI** for accessible interactive components
* React Query for data fetching

> **Note:** The UI was migrated from Mantine to Tailwind CSS + Headless UI. All new UI should use Tailwind CSS and Headless UI only.

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
* [x] Tweets fetching
* [x] Bookmarks fetching
* [x] Colored logging system
* [x] Rate limit handling
* [x] Progress tracking
* [x] Media attachment tracking
* [x] Secure credential caching

### In Progress
* [ ] Frontend implementation
* [ ] Tweet classification
* [ ] Data visualization
* [ ] List management
* [ ] User engagement metrics

### Planned Features
* [ ] Categorize follows into X List suggestions
* [ ] Tweet analysis
* [ ] List recommendations
* [ ] Block/unblock management
* [ ] Follow/unfollow tracking
* [ ] Reply analysis
* [ ] User interaction metrics
* [ ] Automated list suggestions

## Contributing
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License
[Add your license here]

## Credential Authentication Cache

To minimize unnecessary API calls, this project caches the validity of Twitter credentials (for both user-level and app-level authentication) using SHA-256 hashes. No secrets are ever stored—only a hash of the credentials and the authentication status (success/failure) are saved locally. This means:

- If you use the same credentials, the system will remember they worked and skip redundant authentication API calls.
- The cache is stored in `data/auth_cache.json`.
- TTL is infinite: once a credential is validated, it is trusted until you change credentials.
- This improves speed and reduces rate limit risk during development.

**Security:** Only hashes are stored, never the actual credentials.

## Logging System

The application uses a comprehensive logging system with the following features:

- Colored console output for better visibility
- Different colors for different types of messages:
  - Auth messages (Cyan)
  - Fetch operations (Magenta)
  - Data processing (Green)
  - Rate limits (Yellow)
  - Errors (Red)
- Emoji indicators for quick status recognition
- Separate file logging (plain text) for parsing
- Detailed progress tracking
- Rate limit monitoring
- Error tracking with full context

Logs are stored in `logs/download.log` and can be used for debugging or monitoring the application's behavior.

## Local Twitter Archive Data Files

The application now uses local data files from your Twitter archive (located in `twitter-archive-2025-05-31/data/`) as the primary data source. Below are the most relevant files and their purposes:

- `tweets.js`: All tweets posted by the account, including text, metadata, and references to media.
- `like.js`: All tweets liked by the account.
- `block.js`: Accounts blocked by the user.
- `mute.js`: Accounts muted by the user.
- `lists-created.js`: Lists created by the user.
- `lists-member.js`: Lists the user is a member of.
- `lists-subscribed.js`: Lists the user is subscribed to.
- `follower.js`: Accounts following the user.
- `following.js`: Accounts the user is following.
- `direct-messages.js`: One-on-one direct messages.
- `direct-messages-group.js`: Group direct messages.
- `deleted-tweets.js`: Tweets deleted by the user.
- `profile.js`: Profile information (bio, avatar, etc.).
- `account.js`: Account-level information (email, username, creation date, etc.).
- `tweet-headers.js`: Metadata for tweets.
- `tweetdeck.js`: TweetDeck-related data.
- `moments_media/`, `tweets_media/`, `profile_media/`, etc.: Folders containing images, videos, and GIFs shared in tweets, DMs, or as profile media.

For a full list and detailed descriptions, see the `twitter-archive-2025-05-31/data/README.txt` file in your archive.

## Resetting and Reloading the Database

If you need to reset your local SQLite database (for example, after updating your Twitter archive or to fix schema issues), follow these steps:

1. **Reset the database:**
   This will delete the existing database and recreate an empty one with all required tables.
   ```bash
   ./data/reset_db.sh
   ```

2. **Reload your data from the Twitter archive:**
   This will repopulate the database with all your archive data.
   ```bash
   python scripts/load_local_data.py
   ```

This is the recommended way to ensure your database is in sync with your latest Twitter archive. You can safely run these scripts any time you want to start fresh.

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
