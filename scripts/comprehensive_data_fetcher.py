#!/usr/bin/env python3
"""
Comprehensive X API Data Fetcher

This script provides a command-line interface to fetch all types of data
from the X (Twitter) API v2 using the comprehensive service.
"""

import argparse
import logging
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from comprehensive_x_api_service import ComprehensiveXAPIService, DataType

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComprehensiveDataFetcher:
    """Command-line interface for comprehensive X API data fetching."""
    
    def __init__(self):
        self.service = ComprehensiveXAPIService()
    
    def fetch_user_data(self, user_id: str, data_types: List[str], max_results: int = 100):
        """Fetch various types of data for a specific user."""
        results = {}
        
        for data_type in data_types:
            logger.info(f"Fetching {data_type} for user {user_id}...")
            
            try:
                if data_type == "tweets":
                    result = self.service.fetch_user_tweets(user_id, max_results)
                elif data_type == "likes":
                    result = self.service.fetch_user_likes(user_id, max_results)
                elif data_type == "bookmarks":
                    result = self.service.fetch_user_bookmarks(user_id, max_results)
                elif data_type == "followers":
                    result = self.service.fetch_user_followers(user_id, max_results)
                elif data_type == "following":
                    result = self.service.fetch_user_following(user_id, max_results)
                elif data_type == "lists":
                    result = self.service.fetch_user_lists(user_id, max_results)
                else:
                    logger.warning(f"Unknown data type: {data_type}")
                    continue
                
                results[data_type] = result
                
                # Log summary
                data_count = len(result.get("data", []))
                logger.info(f"✅ Fetched {data_count} {data_type} for user {user_id}")
                
            except Exception as e:
                logger.error(f"❌ Error fetching {data_type} for user {user_id}: {str(e)}")
                results[data_type] = {"error": str(e)}
        
        return results
    
    def search_tweets(self, query: str, search_type: str = "recent", max_results: int = 100):
        """Search for tweets."""
        logger.info(f"Searching {search_type} tweets for query: {query}")
        
        try:
            if search_type == "recent":
                result = self.service.search_tweets_recent(query, max_results)
            elif search_type == "all":
                result = self.service.search_tweets_all(query, max_results)
            else:
                raise ValueError(f"Invalid search type: {search_type}")
            
            data_count = len(result.get("data", []))
            logger.info(f"✅ Found {data_count} tweets for query: {query}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error searching tweets: {str(e)}")
            return {"error": str(e)}
    
    def fetch_spaces(self, query: Optional[str] = None, max_results: int = 100):
        """Fetch or search Spaces."""
        logger.info(f"Fetching Spaces" + (f" for query: {query}" if query else ""))
        
        try:
            result = self.service.fetch_spaces(query, max_results)
            
            data_count = len(result.get("data", []))
            logger.info(f"✅ Found {data_count} Spaces")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error fetching Spaces: {str(e)}")
            return {"error": str(e)}
    
    def fetch_direct_messages(self, participant_id: str, max_results: int = 100):
        """Fetch direct messages with a specific participant."""
        logger.info(f"Fetching direct messages with participant {participant_id}")
        
        try:
            result = self.service.fetch_direct_messages(participant_id, max_results)
            
            data_count = len(result.get("data", []))
            logger.info(f"✅ Found {data_count} direct messages")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error fetching direct messages: {str(e)}")
            return {"error": str(e)}
    
    def search_communities(self, query: str, max_results: int = 100):
        """Search for communities."""
        logger.info(f"Searching communities for query: {query}")
        
        try:
            result = self.service.search_communities(query, max_results)
            
            data_count = len(result.get("data", []))
            logger.info(f"✅ Found {data_count} communities")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error searching communities: {str(e)}")
            return {"error": str(e)}
    
    def fetch_trends(self, woeid: int = 1):
        """Fetch trending topics."""
        logger.info(f"Fetching trends for WOEID: {woeid}")
        
        try:
            result = self.service.fetch_trends(woeid)
            
            data_count = len(result.get("data", []))
            logger.info(f"✅ Found {data_count} trending topics")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error fetching trends: {str(e)}")
            return {"error": str(e)}
    
    def get_stats(self):
        """Get comprehensive statistics."""
        logger.info("Getting comprehensive API statistics...")
        
        try:
            cached_stats = self.service.get_cached_data_stats()
            
            stats = {
                "cached_data": cached_stats,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info("✅ Retrieved comprehensive statistics")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting statistics: {str(e)}")
            return {"error": str(e)}
    
    def save_results(self, results: Dict[str, Any], output_file: str):
        """Save results to a JSON file."""
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"✅ Results saved to {output_path}")
            
        except Exception as e:
            logger.error(f"❌ Error saving results: {str(e)}")

def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Comprehensive X API Data Fetcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch tweets and likes for a user
  python comprehensive_data_fetcher.py user --user-id 123456789 --data-types tweets likes
  
  # Search recent tweets
  python comprehensive_data_fetcher.py search --query "python programming" --search-type recent
  
  # Fetch trending topics
  python comprehensive_data_fetcher.py trends --woeid 1
  
  # Get comprehensive statistics
  python comprehensive_data_fetcher.py stats
  
  # Search communities
  python comprehensive_data_fetcher.py communities --query "tech"
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # User data command
    user_parser = subparsers.add_parser('user', help='Fetch user data')
    user_parser.add_argument('--user-id', required=True, help='User ID to fetch data for')
    user_parser.add_argument('--data-types', nargs='+', 
                           choices=['tweets', 'likes', 'bookmarks', 'followers', 'following', 'lists'],
                           default=['tweets'], help='Types of data to fetch')
    user_parser.add_argument('--max-results', type=int, default=100, help='Maximum results per data type')
    user_parser.add_argument('--output', help='Output file to save results')
    
    # Search tweets command
    search_parser = subparsers.add_parser('search', help='Search tweets')
    search_parser.add_argument('--query', required=True, help='Search query')
    search_parser.add_argument('--search-type', choices=['recent', 'all'], default='recent',
                             help='Search type (recent = last 7 days, all = full archive)')
    search_parser.add_argument('--max-results', type=int, default=100, help='Maximum results')
    search_parser.add_argument('--output', help='Output file to save results')
    
    # Spaces command
    spaces_parser = subparsers.add_parser('spaces', help='Fetch Spaces')
    spaces_parser.add_argument('--query', help='Search query for Spaces')
    spaces_parser.add_argument('--max-results', type=int, default=100, help='Maximum results')
    spaces_parser.add_argument('--output', help='Output file to save results')
    
    # Direct messages command
    dm_parser = subparsers.add_parser('dm', help='Fetch direct messages')
    dm_parser.add_argument('--participant-id', required=True, help='Participant ID for DM conversation')
    dm_parser.add_argument('--max-results', type=int, default=100, help='Maximum results')
    dm_parser.add_argument('--output', help='Output file to save results')
    
    # Communities command
    communities_parser = subparsers.add_parser('communities', help='Search communities')
    communities_parser.add_argument('--query', required=True, help='Search query for communities')
    communities_parser.add_argument('--max-results', type=int, default=100, help='Maximum results')
    communities_parser.add_argument('--output', help='Output file to save results')
    
    # Trends command
    trends_parser = subparsers.add_parser('trends', help='Fetch trending topics')
    trends_parser.add_argument('--woeid', type=int, default=1, help='Where On Earth ID (1 = worldwide)')
    trends_parser.add_argument('--output', help='Output file to save results')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Get comprehensive statistics')
    stats_parser.add_argument('--output', help='Output file to save results')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    fetcher = ComprehensiveDataFetcher()
    results = None
    
    try:
        if args.command == 'user':
            results = fetcher.fetch_user_data(args.user_id, args.data_types, args.max_results)
            
        elif args.command == 'search':
            results = fetcher.search_tweets(args.query, args.search_type, args.max_results)
            
        elif args.command == 'spaces':
            results = fetcher.fetch_spaces(args.query, args.max_results)
            
        elif args.command == 'dm':
            results = fetcher.fetch_direct_messages(args.participant_id, args.max_results)
            
        elif args.command == 'communities':
            results = fetcher.search_communities(args.query, args.max_results)
            
        elif args.command == 'trends':
            results = fetcher.fetch_trends(args.woeid)
            
        elif args.command == 'stats':
            results = fetcher.get_stats()
        
        # Print summary to console
        if results:
            if "error" in results:
                logger.error(f"Command failed: {results['error']}")
            else:
                print("\n" + "="*50)
                print("RESULTS SUMMARY")
                print("="*50)
                
                if args.command == 'user':
                    for data_type, result in results.items():
                        if "error" in result:
                            print(f"{data_type}: ERROR - {result['error']}")
                        else:
                            count = len(result.get("data", []))
                            print(f"{data_type}: {count} items")
                elif args.command == 'stats':
                    print(f"Cached data tables:")
                    for table, count in results.get("cached_data", {}).items():
                        print(f"  {table}: {count} records")
                
                print("="*50)
        
        # Save to file if requested
        if hasattr(args, 'output') and args.output and results:
            fetcher.save_results(results, args.output)
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 