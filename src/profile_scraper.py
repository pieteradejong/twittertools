import requests
import re
import json
import time
import logging
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
import sqlite3
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ProfileData:
    user_id: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    verified: bool = False
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    tweet_count: Optional[int] = None
    joined_date: Optional[str] = None
    scrape_source: str = "web_scraping"

class TwitterProfileScraper:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.session = requests.Session()
        # Use headers that look like a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })
    
    def extract_user_id_from_intent_url(self, intent_url: str) -> Optional[str]:
        """Extract user ID from Twitter intent URL."""
        try:
            parsed = urlparse(intent_url)
            if 'user_id' in parsed.query:
                params = parse_qs(parsed.query)
                return params.get('user_id', [None])[0]
        except Exception as e:
            logger.error(f"Error extracting user ID from {intent_url}: {e}")
        return None
    
    def scrape_profile_by_user_id(self, user_id: str, delay: float = 2.0) -> Optional[ProfileData]:
        """Scrape profile data using user ID. Since we can't directly access by ID, 
        we'll need to use the intent URL and follow redirects."""
        intent_url = f"https://twitter.com/intent/user?user_id={user_id}"
        
        # Try intent URL first
        profile = self.scrape_profile_from_intent_url(intent_url, user_id, delay)
        
        # If that fails, try alternative approaches
        if not profile:
            logger.info(f"Intent URL failed for {user_id}, trying alternative methods...")
            
            # For now, just return None. In the future we could try:
            # 1. Checking if we have a cached username from somewhere
            # 2. Using search APIs
            # 3. Other discovery methods
            logger.warning(f"No alternative methods available for user {user_id}")
        
        return profile
    
    def scrape_profile_from_intent_url(self, intent_url: str, user_id: str, delay: float = 2.0) -> Optional[ProfileData]:
        """Scrape profile data from Twitter intent URL."""
        try:
            time.sleep(delay)  # Rate limiting
            
            logger.info(f"Scraping profile for user ID: {user_id}")
            
            # First, try to get the actual profile URL by following the intent URL
            response = self.session.get(intent_url, allow_redirects=True, timeout=30)
            
            if response.status_code != 200:
                logger.warning(f"Failed to access intent URL {intent_url}: {response.status_code}")
                return None
            
            # Check if we were redirected to an actual profile
            final_url = response.url
            logger.info(f"Final URL after redirect: {final_url}")
            
            if 'twitter.com/' in final_url and '/intent/' not in final_url:
                # We got redirected to the actual profile
                return self.scrape_profile_from_url(final_url, user_id, delay=0)  # No additional delay
            else:
                # Intent URL didn't redirect, try to extract info from the intent page itself
                logger.info(f"Intent URL didn't redirect, trying to extract from intent page")
                return self.scrape_profile_from_intent_page(response.text, user_id)
                
        except Exception as e:
            logger.error(f"Error scraping profile from intent URL {intent_url}: {e}")
            return None
    
    def scrape_profile_from_intent_page(self, html_content: str, user_id: str) -> Optional[ProfileData]:
        """Try to extract profile data from the intent page itself."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Initialize profile data
            profile = ProfileData(user_id=user_id)
            
            # Look for any profile information in the intent page
            # Sometimes Twitter includes basic info even on intent pages
            
            # Check for Open Graph meta tags
            self._extract_meta_data(soup, profile)
            
            # Look for any embedded profile data
            # Intent pages sometimes contain JavaScript with profile data
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'screen_name' in script.string:
                    # Try to extract username from script content
                    import re
                    username_match = re.search(r'"screen_name"\s*:\s*"([^"]+)"', script.string)
                    if username_match:
                        profile.username = username_match.group(1)
                        logger.info(f"Found username in script: {profile.username}")
                        
                    name_match = re.search(r'"name"\s*:\s*"([^"]+)"', script.string)
                    if name_match:
                        profile.display_name = name_match.group(1)
                        logger.info(f"Found display name in script: {profile.display_name}")
            
            # If we found some data, return it
            if profile.username or profile.display_name:
                return profile
            else:
                logger.warning(f"No profile data found in intent page for user {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting profile from intent page: {e}")
            return None
    
    def scrape_profile_from_url(self, profile_url: str, user_id: str, delay: float = 2.0) -> Optional[ProfileData]:
        """Scrape profile data from direct Twitter profile URL."""
        try:
            if delay > 0:
                time.sleep(delay)
            
            response = self.session.get(profile_url, timeout=30)
            
            if response.status_code != 200:
                logger.warning(f"Failed to access profile URL {profile_url}: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract username from URL
            username = None
            if '/intent/' not in profile_url:
                # Extract username from URL like https://twitter.com/username
                url_parts = profile_url.rstrip('/').split('/')
                if len(url_parts) > 0:
                    username = url_parts[-1]
            
            # Initialize profile data
            profile = ProfileData(user_id=user_id, username=username)
            
            # Try to extract data from meta tags (Open Graph and Twitter Card)
            self._extract_meta_data(soup, profile)
            
            # Try to extract data from JSON-LD structured data
            self._extract_json_ld_data(soup, profile)
            
            # Try to extract data from page content
            self._extract_page_content(soup, profile)
            
            logger.info(f"Successfully scraped profile for {username or user_id}: {profile.display_name}")
            return profile
            
        except Exception as e:
            logger.error(f"Error scraping profile from URL {profile_url}: {e}")
            return None
    
    def _extract_meta_data(self, soup: BeautifulSoup, profile: ProfileData):
        """Extract data from meta tags."""
        try:
            # Open Graph tags
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                profile.display_name = og_title['content']
            
            og_description = soup.find('meta', property='og:description') 
            if og_description and og_description.get('content'):
                profile.bio = og_description['content']
            
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                profile.avatar_url = og_image['content']
            
            # Twitter Card tags
            twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
            if twitter_title and twitter_title.get('content') and not profile.display_name:
                profile.display_name = twitter_title['content']
            
            twitter_description = soup.find('meta', attrs={'name': 'twitter:description'})
            if twitter_description and twitter_description.get('content') and not profile.bio:
                profile.bio = twitter_description['content']
            
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content') and not profile.avatar_url:
                profile.avatar_url = twitter_image['content']
                
        except Exception as e:
            logger.error(f"Error extracting meta data: {e}")
    
    def _extract_json_ld_data(self, soup: BeautifulSoup, profile: ProfileData):
        """Extract data from JSON-LD structured data."""
        try:
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Person':
                        if not profile.display_name and data.get('name'):
                            profile.display_name = data['name']
                        if not profile.bio and data.get('description'):
                            profile.bio = data['description']
                        if not profile.avatar_url and data.get('image'):
                            profile.avatar_url = data['image']
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.error(f"Error extracting JSON-LD data: {e}")
    
    def _extract_page_content(self, soup: BeautifulSoup, profile: ProfileData):
        """Extract data from page content using various selectors."""
        try:
            # Try to find profile information in the page content
            # This is more fragile as Twitter's structure changes frequently
            
            # Look for display name in various possible locations
            if not profile.display_name:
                display_name_selectors = [
                    'h1[data-testid="UserName"]',
                    '[data-testid="UserName"] span',
                    'h1',
                    '.ProfileHeaderCard-name',
                ]
                for selector in display_name_selectors:
                    element = soup.select_one(selector)
                    if element and element.get_text(strip=True):
                        profile.display_name = element.get_text(strip=True)
                        break
            
            # Look for bio/description
            if not profile.bio:
                bio_selectors = [
                    '[data-testid="UserDescription"]',
                    '.ProfileHeaderCard-bio',
                    '[role="presentation"] div[dir="auto"]',
                ]
                for selector in bio_selectors:
                    element = soup.select_one(selector)
                    if element and element.get_text(strip=True):
                        profile.bio = element.get_text(strip=True)
                        break
            
            # Look for follower/following counts
            stats_elements = soup.find_all('a', href=True)
            for element in stats_elements:
                href = element.get('href', '')
                text = element.get_text(strip=True)
                
                if '/followers' in href and 'follower' in text.lower():
                    # Extract follower count
                    count_match = re.search(r'([\d,]+)', text)
                    if count_match:
                        try:
                            profile.follower_count = int(count_match.group(1).replace(',', ''))
                        except ValueError:
                            pass
                
                elif '/following' in href and 'following' in text.lower():
                    # Extract following count
                    count_match = re.search(r'([\d,]+)', text)
                    if count_match:
                        try:
                            profile.following_count = int(count_match.group(1).replace(',', ''))
                        except ValueError:
                            pass
            
        except Exception as e:
            logger.error(f"Error extracting page content: {e}")
    
    def save_profile_to_db(self, profile: ProfileData) -> bool:
        """Save scraped profile data to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Update the users table with scraped data
                conn.execute("""
                    UPDATE users 
                    SET username = COALESCE(?, username),
                        display_name = COALESCE(?, display_name),
                        bio = COALESCE(?, bio),
                        avatar_url = COALESCE(?, avatar_url),
                        verified = COALESCE(?, verified),
                        follower_count = COALESCE(?, follower_count),
                        following_count = COALESCE(?, following_count),
                        tweet_count = COALESCE(?, tweet_count),
                        location = COALESCE(?, location),
                        website = COALESCE(?, website),
                        profile_source = ?
                    WHERE id = ?
                """, (
                    profile.username,
                    profile.display_name,
                    profile.bio,
                    profile.avatar_url,
                    profile.verified,
                    profile.follower_count,
                    profile.following_count,
                    profile.tweet_count,
                    profile.location,
                    profile.website,
                    profile.scrape_source,
                    profile.user_id
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving profile to database: {e}")
            return False
    
    def scrape_profiles_batch(self, user_ids: list, delay: float = 2.0, max_profiles: int = 50) -> Dict[str, Any]:
        """Scrape multiple profiles in batch."""
        results = {
            'total_requested': len(user_ids),
            'successfully_scraped': 0,
            'failed_scrapes': 0,
            'profiles_updated': 0,
            'errors': []
        }
        
        # Limit the number of profiles to scrape
        limited_user_ids = user_ids[:max_profiles]
        
        for i, user_id in enumerate(limited_user_ids):
            try:
                logger.info(f"Scraping profile {i+1}/{len(limited_user_ids)}: {user_id}")
                
                profile = self.scrape_profile_by_user_id(user_id, delay)
                
                if profile:
                    if self.save_profile_to_db(profile):
                        results['successfully_scraped'] += 1
                        results['profiles_updated'] += 1
                    else:
                        results['failed_scrapes'] += 1
                        results['errors'].append(f"Failed to save profile for user {user_id}")
                else:
                    results['failed_scrapes'] += 1
                    results['errors'].append(f"Failed to scrape profile for user {user_id}")
                    
            except Exception as e:
                results['failed_scrapes'] += 1
                results['errors'].append(f"Error processing user {user_id}: {str(e)}")
                logger.error(f"Error processing user {user_id}: {e}")
        
        return results
    
    def get_users_needing_scraping(self, limit: int = 50) -> list:
        """Get list of user IDs that need profile scraping."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT id FROM users 
                    WHERE (username IS NULL OR avatar_url IS NULL) 
                    AND profile_source != 'web_scraping'
                    ORDER BY id 
                    LIMIT ?
                """, (limit,))
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting users needing scraping: {e}")
            return []

    def scrape_profile_by_username(self, username: str, user_id: str = None, delay: float = 2.0) -> Optional[ProfileData]:
        """Scrape profile data using a known username."""
        try:
            # Construct the profile URL
            profile_url = f"https://twitter.com/{username}"
            
            # Try the main domain first
            profile = self.scrape_profile_from_url(profile_url, user_id or username, delay)
            
            if not profile:
                # Try x.com domain
                profile_url = f"https://x.com/{username}"
                profile = self.scrape_profile_from_url(profile_url, user_id or username, delay)
            
            return profile
            
        except Exception as e:
            logger.error(f"Error scraping profile by username {username}: {e}")
            return None

    def get_users_with_usernames_needing_enrichment(self, limit: int = 50) -> list:
        """Get users who have usernames but are missing other profile data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT id, username FROM users 
                    WHERE username IS NOT NULL 
                    AND username NOT LIKE 'user_%'
                    AND username != ''
                    AND (avatar_url IS NULL OR bio IS NULL OR display_name IS NULL)
                    AND (profile_source IS NULL OR profile_source != 'web_scraping')
                    ORDER BY id 
                    LIMIT ?
                """, (limit,))
                return [(row[0], row[1]) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting users with usernames needing enrichment: {e}")
            return []

    def scrape_profiles_with_usernames_batch(self, limit: int = 20, delay: float = 2.0) -> Dict[str, Any]:
        """Scrape profiles for users who have usernames but missing other data."""
        results = {
            'total_requested': 0,
            'successfully_scraped': 0,
            'failed_scrapes': 0,
            'profiles_updated': 0,
            'errors': []
        }
        
        # Get users with usernames who need enrichment
        users_with_usernames = self.get_users_with_usernames_needing_enrichment(limit)
        results['total_requested'] = len(users_with_usernames)
        
        if not users_with_usernames:
            return results
        
        for i, (user_id, username) in enumerate(users_with_usernames):
            try:
                logger.info(f"Scraping profile {i+1}/{len(users_with_usernames)}: @{username} ({user_id})")
                
                profile = self.scrape_profile_by_username(username, user_id, delay)
                
                if profile:
                    if self.save_profile_to_db(profile):
                        results['successfully_scraped'] += 1
                        results['profiles_updated'] += 1
                    else:
                        results['failed_scrapes'] += 1
                        results['errors'].append(f"Failed to save profile for user @{username} ({user_id})")
                else:
                    results['failed_scrapes'] += 1
                    results['errors'].append(f"Failed to scrape profile for user @{username} ({user_id})")
                    
            except Exception as e:
                results['failed_scrapes'] += 1
                results['errors'].append(f"Error processing user @{username} ({user_id}): {str(e)}")
                logger.error(f"Error processing user @{username} ({user_id}): {e}")
        
        return results 