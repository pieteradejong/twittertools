# (DEPRECATED) This script is no longer used. All data is now loaded from local Twitter archive files in twitter-archive-2025-05-31/data/.
# API fetching is disabled to avoid rate limits and improve privacy.
import json
import sqlite3
import time
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from colorama import init, Fore, Style
import requests
from requests_oauthlib import OAuth1
from requests.exceptions import RequestException, HTTPError

# Initialize colorama
init()

# Load environment variables
ENV_FILE = Path(__file__).parent.parent / '.env'
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

# Set up logging with more detailed format and colors
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log messages based on level."""
    
    COLORS = {
        'DEBUG': Fore.BLUE,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }
    
    STATUS_COLORS = {
        'auth': Fore.CYAN,
        'fetch': Fore.MAGENTA,
        'data': Fore.GREEN,
        'rate': Fore.YELLOW,
        'error': Fore.RED,
    }
    
    def format(self, record):
        # Add color based on log level
        if record.levelname in self.COLORS:
            record.msg = f"{self.COLORS[record.levelname]}{record.msg}{Style.RESET_ALL}"
        
        # Add color based on status type if present
        if hasattr(record, 'status_type') and record.status_type in self.STATUS_COLORS:
            record.msg = f"{self.STATUS_COLORS[record.status_type]}{record.msg}{Style.RESET_ALL}"
        
        return super().format(record)

# Set up logging
logger = logging.getLogger("x_data_downloader")
logger.setLevel(logging.INFO)

# File handler (no colors in file)
file_handler = logging.FileHandler(LOGS_DIR / "download.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"))
logger.addHandler(file_handler)

# Console handler (with colors)
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)

def log_status(message: str, status_type: str, level: int = logging.INFO):
    """Log a message with a specific status type and color."""
    extra = {'status_type': status_type}
    logger.log(level, message, extra=extra)

# Constants
BASE_URL = "https://api.twitter.com/2"
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "x_data.db"
RATE_LIMIT_WINDOW = 15 * 60  # 15 minutes in seconds

# Rate limit configurations
RATE_LIMITS = {
    "tweets": {"requests": 300, "max_results": 100},
    "likes": {"requests": 75, "max_results": 100},
    "bookmarks": {"requests": 180, "max_results": 500},
    "users_me": {"requests": 150}  # Rate limit for /2/users/me
}

def get_env_var(name: str) -> str:
    """Get required environment variable or raise error."""
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Required environment variable {name} not found")
    return value

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Load credentials from environment
try:
    auth = OAuth1(
        get_env_var('TWITTER_API_KEY'),
        get_env_var('TWITTER_API_SECRET'),
        get_env_var('TWITTER_ACCESS_TOKEN'),
        get_env_var('TWITTER_ACCESS_TOKEN_SECRET')
    )
except ValueError as e:
    logging.error(f"Failed to load Twitter credentials: {e}")
    print(f"Error: {e}")
    print("Please ensure all required Twitter credentials are set in your .env file:")
    print("TWITTER_API_KEY")
    print("TWITTER_API_SECRET")
    print("TWITTER_ACCESS_TOKEN")
    print("TWITTER_ACCESS_TOKEN_SECRET")
    exit(1)

# Database setup
def setup_database():
    logger.info("Setting up database at %s", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Create data tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tweets (
                id TEXT PRIMARY KEY,
                text TEXT,
                created_at TEXT,
                conversation_id TEXT,
                author_id TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                id TEXT PRIMARY KEY,
                text TEXT,
                created_at TEXT,
                author_id TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                id TEXT PRIMARY KEY,
                text TEXT,
                created_at TEXT,
                author_id TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media (
                tweet_id TEXT,
                media_url TEXT,
                type TEXT,
                FOREIGN KEY(tweet_id) REFERENCES tweets(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                data_type TEXT PRIMARY KEY,
                last_marker TEXT,
                last_fetched_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
        logger.info("Database tables created/verified successfully")
    except sqlite3.Error as e:
        logger.error("Database setup failed: %s", str(e))
        raise
    return conn, cursor

# Cache user_id
def get_user_id_from_db(cursor):
    cursor.execute("SELECT value FROM user WHERE key = 'user_id'")
    result = cursor.fetchone()
    return result[0] if result else None

def save_user_id_to_db(cursor, conn, user_id):
    cursor.execute(
        "INSERT OR REPLACE INTO user (key, value) VALUES (?, ?)",
        ("user_id", user_id)
    )
    conn.commit()

# Fetch user_id with retry on 429
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=60, max=900),  # Wait between 60s and 15m
    retry=retry_if_exception_type(HTTPError),
    before_sleep=lambda retry_state: logging.info(
        f"Rate limit hit for /2/users/me. Retrying in {retry_state.next_action.sleep} seconds..."
    )
)
def fetch_user_id():
    response = requests.get(f"{BASE_URL}/users/me", auth=auth)
    if response.status_code == 429:
        logging.warning("Rate limit exceeded for /2/users/me. Retrying...")
        raise HTTPError(response=response)
    response.raise_for_status()
    return response.json()["data"]["id"]

# Progress tracking
def get_progress(cursor, data_type):
    cursor.execute(
        "SELECT last_marker, last_fetched_at FROM progress WHERE data_type = ?",
        (data_type,)
    )
    result = cursor.fetchone()
    if result:
        last_marker, last_fetched_at = result
        last_fetched_at = (datetime.fromisoformat(last_fetched_at)
                          if last_fetched_at else None)
        return last_marker, last_fetched_at
    return None, None

def update_progress(cursor, conn, data_type, last_marker, last_fetched_at=None):
    if last_fetched_at is None:
        last_fetched_at = datetime.utcnow().isoformat()
    cursor.execute(
        "INSERT OR REPLACE INTO progress (data_type, last_marker, last_fetched_at) "
        "VALUES (?, ?, ?)",
        (data_type, last_marker, last_fetched_at)
    )
    conn.commit()

# Rate limit handling
def wait_for_rate_limit(last_fetched_at, data_type):
    if not last_fetched_at:
        return
    elapsed = (datetime.utcnow() - last_fetched_at).total_seconds()
    if elapsed < RATE_LIMIT_WINDOW:
        sleep_time = RATE_LIMIT_WINDOW - elapsed
        logger.info(
            "Rate limit window active for %s. Elapsed: %.2fs, Sleeping for %.2fs. "
            "Window resets in %.2fs",
            data_type, elapsed, sleep_time, RATE_LIMIT_WINDOW
        )
        time.sleep(sleep_time)

def log_rate_limit_status(data_type: str, request_count: int, max_requests: int):
    """Log current rate limit status for a data type."""
    remaining = max_requests - request_count
    logger.info(
        "Rate limit status for %s: %d/%d requests used (%d remaining)",
        data_type, request_count, max_requests, remaining
    )

def verify_auth_credentials():
    """Verify that the authentication credentials are valid."""
    log_status("Verifying Twitter API credentials...", "auth")
    try:
        # Try to fetch user info as a credential test
        response = requests.get(f"{BASE_URL}/users/me", auth=auth)
        response.raise_for_status()
        user_data = response.json()["data"]
        log_status(
            f"✓ Authentication successful! Connected as: {user_data.get('username', 'Unknown')} "
            f"(ID: {user_data.get('id', 'Unknown')})",
            "auth"
        )
        return True
    except Exception as e:
        log_status(
            f"✗ Authentication failed: {str(e)}",
            "error",
            level=logging.ERROR
        )
        return False

def fetch_data(endpoint, params, data_type, cursor, conn, user_id):
    url = f"{BASE_URL}{endpoint}"
    params["max_results"] = RATE_LIMITS[data_type]["max_results"]
    max_requests = RATE_LIMITS[data_type]["requests"]
    
    log_status(f"🚀 Initiating fetch for {data_type} from endpoint {endpoint}", "fetch")
    
    # Get progress
    last_marker, last_fetched_at = get_progress(cursor, data_type)
    if last_marker:
        log_status(f"↻ Resuming {data_type} fetch from marker: {last_marker}", "fetch")
        if data_type == "tweets":
            params["since_id"] = last_marker
        elif data_type in ["likes", "bookmarks"]:
            params["pagination_token"] = last_marker
    
    request_count = 0
    total_items_processed = 0
    
    while True:
        # Check rate limit
        if request_count >= max_requests:
            log_status(f"⏳ Rate limit reached for {data_type}. Saving progress and waiting...", "rate")
            update_progress(cursor, conn, data_type, last_marker, datetime.utcnow().isoformat())
            wait_for_rate_limit(last_fetched_at, data_type)
            request_count = 0
            last_fetched_at = datetime.utcnow()
        
        log_rate_limit_status(data_type, request_count, max_requests)
        
        try:
            log_status(f"📡 Making API request to {endpoint}", "fetch", level=logging.DEBUG)
            response = requests.get(url, auth=auth, params=params)
            response.raise_for_status()
        except requests.RequestException as e:
            log_status(
                f"❌ Error fetching {data_type}: {str(e)}. Status: {getattr(e.response, 'status_code', 'N/A')}. "
                f"Response: {getattr(e.response, 'text', 'N/A')}. Retrying in 60 seconds...",
                "error"
            )
            time.sleep(60)
            continue
        
        request_count += 1
        data = response.json()
        
        # Process data
        items = data.get("data", [])
        if not items:
            log_status(
                f"✅ No more {data_type} to fetch. Total items processed: {total_items_processed}",
                "data"
            )
            update_progress(cursor, conn, data_type, None)
            break
        
        items_processed = 0
        for item in items:
            try:
                if data_type == "tweets":
                    cursor.execute(
                        "INSERT OR IGNORE INTO tweets (id, text, created_at, conversation_id, author_id) VALUES (?, ?, ?, ?, ?)",
                        (item["id"], item["text"], item["created_at"], item.get("conversation_id"), item["author_id"])
                    )
                    last_marker = max(last_marker or "0", item["id"])
                    # Extract media
                    if "attachments" in item and "media_keys" in item["attachments"]:
                        media = data.get("includes", {}).get("media", [])
                        for m in media:
                            if m.get("type") in ["photo", "video"]:
                                cursor.execute(
                                    "INSERT INTO media (tweet_id, media_url, type) VALUES (?, ?, ?)",
                                    (item["id"], m.get("url") or m.get("preview_image_url"), m["type"])
                                )
                elif data_type == "likes":
                    cursor.execute(
                        "INSERT OR IGNORE INTO likes (id, text, created_at, author_id) VALUES (?, ?, ?, ?)",
                        (item["id"], item["text"], item["created_at"], item["author_id"])
                    )
                elif data_type == "bookmarks":
                    cursor.execute(
                        "INSERT OR IGNORE INTO bookmarks (id, text, created_at, author_id) VALUES (?, ?, ?, ?)",
                        (item["id"], item["text"], item["created_at"], item["author_id"])
                    )
                items_processed += 1
            except sqlite3.Error as e:
                log_status(
                    f"❌ Database error processing {data_type} item {item.get('id', 'unknown')}: {str(e)}",
                    "error"
                )
                continue
        
        total_items_processed += items_processed
        log_status(
            f"📊 Processed {items_processed} {data_type} in this batch. Total processed: {total_items_processed}",
            "data"
        )
        
        conn.commit()
        
        # Update progress
        next_token = data.get("meta", {}).get("next_token")
        if data_type == "tweets":
            update_progress(cursor, conn, data_type, last_marker, datetime.utcnow().isoformat())
        else:
            last_marker = next_token
            update_progress(cursor, conn, data_type, last_marker, datetime.utcnow().isoformat())
        
        if not next_token and data_type != "tweets":
            log_status(
                f"✅ Finished fetching all {data_type}. Total items processed: {total_items_processed}",
                "data"
            )
            update_progress(cursor, conn, data_type, None)
            break
        
        params["pagination_token"] = next_token
        log_status(f"↻ Next pagination token for {data_type}: {next_token}", "fetch", level=logging.DEBUG)

def main():
    log_status("🚀 Starting X data download process", "fetch")
    start_time = datetime.utcnow()
    
    try:
        # Verify credentials first
        if not verify_auth_credentials():
            log_status("❌ Authentication verification failed. Exiting.", "error")
            return
        
        conn, cursor = setup_database()
        
        # Try to get user_id from database
        user_id = get_user_id_from_db(cursor)
        if not user_id:
            try:
                log_status("🔑 Fetching user ID from X API...", "auth")
                user_id = fetch_user_id()
                save_user_id_to_db(cursor, conn, user_id)
                log_status(f"✅ User ID {user_id} saved to database", "auth")
            except RequestException as e:
                log_status(f"❌ Error fetching user ID: {str(e)}", "error")
                conn.close()
                return
        
        # Fetch each data type
        for data_type, endpoint, params in [
            ("tweets", f"/users/{user_id}/tweets", {
                "tweet.fields": "created_at,conversation_id,author_id,attachments",
                "expansions": "attachments.media_keys",
                "media.fields": "url,preview_image_url,type"
            }),
            ("likes", f"/users/{user_id}/liked_tweets", {
                "tweet.fields": "created_at,author_id"
            }),
            ("bookmarks", f"/users/{user_id}/bookmarks", {
                "tweet.fields": "created_at,author_id"
            })
        ]:
            log_status(f"🚀 Starting fetch for {data_type}...", "fetch")
            fetch_start = datetime.utcnow()
            fetch_data(endpoint, params, data_type, cursor, conn, user_id)
            fetch_duration = datetime.utcnow() - fetch_start
            log_status(f"✅ Completed {data_type} fetch in {fetch_duration}", "data")
        
        conn.close()
        total_duration = datetime.utcnow() - start_time
        log_status(f"🎉 Data fetching complete. Total duration: {total_duration}", "fetch")
    except Exception as e:
        log_status(f"❌ Unexpected error during data fetch: {str(e)}", "error", level=logging.ERROR)
        raise

if __name__ == "__main__":
    main()