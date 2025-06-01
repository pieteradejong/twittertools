#!/usr/bin/env python3
# (DEPRECATED) This script is no longer used. All data is now loaded from local Twitter archive files in twitter-archive-2025-05-31/data/.
# API authentication is disabled to avoid rate limits and improve privacy.
"""
Twitter Authentication Test Script

This script tests the Twitter API authentication process and provides detailed
feedback about each step of the authentication process.

Usage:
    # First activate the virtual environment:
    source env/bin/activate
    
    # Then run the script:
    python -m scripts.test_auth
"""

import os
import sys
import logging
from pathlib import Path
import time
from typing import Optional

# Check if we're running in the virtual environment
if not os.environ.get('VIRTUAL_ENV'):
    print("Error: Virtual environment not activated!")
    print("\nPlease activate the virtual environment first:")
    print("    source env/bin/activate")
    print("\nThen run the script again:")
    print("    python -m scripts.test_auth")
    sys.exit(1)

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich import print as rprint
except ImportError:
    print("Error: Required packages not installed!")
    print("\nPlease install the required packages:")
    print("    pip install -r requirements.txt")
    sys.exit(1)

try:
    from src.main import TwitterClient, AuthStatus, RateLimitInfo
    from src.settings import get_settings
except ImportError as e:
    print(f"Error: Could not import project modules: {e}")
    print("\nMake sure you're running the script from the project root directory")
    print("and that the virtual environment is activated.")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def format_wait_time(seconds: int) -> str:
    """Format wait time in minutes, rounded up."""
    minutes = (seconds + 59) // 60  # Round up to nearest minute
    if minutes == 1:
        return "1 minute"
    return f"{minutes} minutes"

def check_rate_limit(client: TwitterClient, endpoint: str) -> Optional[RateLimitInfo]:
    """Check if we're rate limited for a specific endpoint."""
    rate_limit = client.rate_limit_info
    if rate_limit and rate_limit.is_rate_limited and rate_limit.endpoint == endpoint:
        return rate_limit
    return None

def test_authentication() -> AuthStatus:
    """Test Twitter authentication and return detailed status."""
    console = Console()
    auth_steps = []
    rate_limited_endpoints = set()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        # Initialize the task
        task = progress.add_task("Testing authentication...", total=None)
        
        try:
            # Initialize the client (this will trigger the auth tests)
            client = TwitterClient()
            
            # Test OAuth 1.0a User Context authentication (required)
            progress.update(task, description="Testing OAuth 1.0a User Context authentication...")
            
            # Check rate limit before auth test
            rate_limit = check_rate_limit(client, "users/me")
            if rate_limit:
                rate_limited_endpoints.add(("users/me", rate_limit))
                auth_steps.append(f"Rate limited: User info endpoint. Try again in {format_wait_time(rate_limit.wait_seconds)}")
                return AuthStatus(
                    is_authenticated=False,
                    error="Rate limited on user info endpoint",
                    auth_steps=auth_steps,
                    current_step="Rate limited",
                    rate_limit=rate_limit
                )
            
            me = client.client.get_me()
            username = me['data']['username']
            user_id = me['data']['id']
            name = me['data'].get('name', '')
            auth_steps.append(f"OAuth 1.0a User Context: Authenticated as {name} (@{username})")
            auth_steps.append(f"User ID: {user_id}")
            
            # Test App-level authentication if available (single request)
            if client.app_client:
                progress.update(task, description="Testing App-level authentication...")
                
                # Check rate limit before app-level test
                rate_limit = check_rate_limit(client, "tweets")
                if rate_limit:
                    rate_limited_endpoints.add(("tweets", rate_limit))
                    auth_steps.append(f"Rate limited: Tweet lookup endpoint. Try again in {format_wait_time(rate_limit.wait_seconds)}")
                else:
                    try:
                        # Use a known tweet ID to minimize unnecessary requests
                        test_tweet = client.get_tweet("20", use_app_auth=True)  # Twitter's first tweet
                        auth_steps.append("App-level authentication: Successfully tested tweet lookup")
                    except Exception as e:
                        if "rate limit" in str(e).lower():
                            auth_steps.append(f"Rate limited: Tweet lookup endpoint. Try again in {format_wait_time(client.rate_limit_info.wait_seconds)}")
                        else:
                            auth_steps.append(f"App-level authentication test failed: {str(e)}")
            else:
                auth_steps.append("App-level authentication: Not configured (Bearer Token not set)")
            
            # Test one user context endpoint as a sample (bookmarks)
            progress.update(task, description="Testing user context endpoint (bookmarks)...")
            
            # Check rate limit before bookmarks test
            rate_limit = check_rate_limit(client, "bookmarks")
            if rate_limit:
                rate_limited_endpoints.add(("bookmarks", rate_limit))
                auth_steps.append(f"Rate limited: Bookmarks endpoint. Try again in {format_wait_time(rate_limit.wait_seconds)}")
            else:
                try:
                    bookmarks = client.client.get_bookmarks(max_results=5)
                    if bookmarks.data:
                        auth_steps.append(f"User Context: Can access bookmarks (found {len(bookmarks.data)} recent bookmarks)")
                    else:
                        auth_steps.append("User Context: Bookmarks endpoint accessible (no bookmarks found)")
                except Exception as e:
                    if "rate limit" in str(e).lower():
                        auth_steps.append(f"Rate limited: Bookmarks endpoint. Try again in {format_wait_time(client.rate_limit_info.wait_seconds)}")
                    else:
                        auth_steps.append(f"User Context: Bookmarks access failed: {str(e)}")
            
            # Test tweet fetching with minimal requests
            progress.update(task, description="Testing tweet fetching...")
            
            # Check rate limit before tweet fetch
            rate_limit = check_rate_limit(client, "users/:id/tweets")
            if rate_limit:
                rate_limited_endpoints.add(("users/:id/tweets", rate_limit))
                auth_steps.append(f"Rate limited: Tweet fetching endpoint. Try again in {format_wait_time(rate_limit.wait_seconds)}")
            else:
                try:
                    # Only test with User Context to minimize requests
                    tweets = client.get_users_tweets(
                        user_id,
                        max_results=5,
                        tweet_fields=['created_at', 'public_metrics', 'text'],
                        use_app_auth=False  # Stick to User Context to minimize requests
                    )
                    if tweets.data:
                        auth_steps.append(f"User Context: Can fetch tweets (found {len(tweets.data)} recent tweets)")
                    else:
                        auth_steps.append("User Context: Tweet fetching successful (no tweets found)")
                except Exception as e:
                    if "rate limit" in str(e).lower():
                        auth_steps.append(f"Rate limited: Tweet fetching endpoint. Try again in {format_wait_time(client.rate_limit_info.wait_seconds)}")
                    else:
                        auth_steps.append(f"Tweet fetching failed: {str(e)}")
            
            progress.update(task, description="Authentication tests completed!")
            
            # If we hit any rate limits, add a summary
            if rate_limited_endpoints:
                auth_steps.append("\nRate Limit Summary:")
                for endpoint, rate_limit in sorted(rate_limited_endpoints, key=lambda x: x[1].wait_seconds, reverse=True):
                    auth_steps.append(f"  • {endpoint}: Try again in {format_wait_time(rate_limit.wait_seconds)}")
            
            return AuthStatus(
                is_authenticated=True,
                username=username,
                can_fetch_data=True,
                auth_steps=auth_steps,
                current_step="All tests completed"
            )
            
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            progress.update(task, description="Authentication failed!")
            return AuthStatus(
                is_authenticated=False,
                error=str(e),
                auth_steps=auth_steps,
                current_step="Authentication failed"
            )

def display_status(status: AuthStatus) -> None:
    """Display authentication status in a formatted way."""
    console = Console()
    
    # Create a table for the status
    table = Table(show_header=False, box=None)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    # Add status information
    table.add_row("Authentication Status", 
                 "[green]✓ Authenticated[/green]" if status.is_authenticated else "[red]✗ Not Authenticated[/red]")
    
    if status.username:
        table.add_row("Username", f"@{status.username}")
    
    if status.can_fetch_data:
        table.add_row("Data Access", "[green]✓ Can fetch data[/green]")
    
    if status.error:
        table.add_row("Error", f"[red]{status.error}[/red]")
    
    if status.rate_limit and status.rate_limit.is_rate_limited:
        wait_time = format_wait_time(status.rate_limit.wait_seconds)
        table.add_row("Rate Limit", 
                     f"[yellow]Rate limited on {status.rate_limit.endpoint}. "
                     f"Try again in {wait_time}[/yellow]")
    
    # Display the table in a panel
    console.print(Panel(table, title="Twitter Authentication Status", border_style="blue"))
    
    # Display authentication steps if any
    if status.auth_steps:
        console.print("\n[bold]Test Results:[/bold]")
        for step in status.auth_steps:
            if step.startswith("\nRate Limit Summary:"):
                console.print("\n[yellow]Rate Limit Summary:[/yellow]")
                continue
            if step.startswith("  • "):  # Rate limit summary item
                console.print(f"  [yellow]⚠[/yellow] {step}")
            elif "rate limited" in step.lower():
                console.print(f"  [yellow]⚠[/yellow] {step}")
            elif "failed" in step.lower():
                console.print(f"  [red]✗[/red] {step}")
            elif "not configured" in step.lower():
                console.print(f"  [yellow]⚠[/yellow] {step}")
            else:
                console.print(f"  [green]✓[/green] {step}")
        
        # Add note about rate limits if any were encountered
        if any("rate limited" in step.lower() for step in status.auth_steps):
            console.print("\n[yellow]Note:[/yellow] Some endpoints were rate limited. The script will not wait for rate limits to reset.")
            console.print("To test all endpoints, run the script again after the rate limits reset.")

def main():
    """Main entry point for the script."""
    console = Console()
    
    # Check if credentials are configured
    settings = get_settings()
    required_oauth_creds = [
        "TWITTER_API_KEY",
        "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN",
        "TWITTER_ACCESS_TOKEN_SECRET"
    ]
    
    # Check required OAuth credentials
    missing_oauth = []
    for cred in required_oauth_creds:
        try:
            getattr(settings, cred)
        except ValueError:
            missing_oauth.append(cred)
    
    if missing_oauth:
        console.print("[red]Error: Missing required OAuth credentials[/red]")
        console.print("\nPlease ensure your .env file contains all required Twitter OAuth credentials:")
        for cred in missing_oauth:
            console.print(f"  - {cred}")
        sys.exit(1)
    
    # Check optional App-level credentials
    try:
        settings.TWITTER_BEARER_TOKEN
    except ValueError:
        console.print("[yellow]Warning: TWITTER_BEARER_TOKEN not set. App-level authentication will not be available.[/yellow]")
    
    # Run the authentication test
    console.print("[bold blue]Testing Twitter API Authentication...[/bold blue]")
    console.print("[dim]Note: The script minimizes API requests to avoid rate limits.[/dim]\n")
    status = test_authentication()
    
    # Display the results
    display_status(status)
    
    # Exit with appropriate status code
    sys.exit(0 if status.is_authenticated else 1)

if __name__ == "__main__":
    main() 