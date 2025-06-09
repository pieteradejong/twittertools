#!/usr/bin/env python3
"""
Test script to demonstrate profile link generation logic
This mirrors the TypeScript logic for generating Twitter profile URLs
"""

def generate_profile_url(user_data):
    """
    Generate a Twitter profile URL for a user
    Priority order:
    1. Use existing user_link if available
    2. Use username to create twitter.com/username link
    3. Fall back to Twitter intent URL with user ID
    """
    user_id = user_data.get('id')
    username = user_data.get('username')
    user_link = user_data.get('user_link')
    
    # First priority: use existing user_link
    if user_link:
        return user_link
    
    # Second priority: use username for clean URL
    if username:
        return f"https://twitter.com/{username}"
    
    # Fallback: use Twitter intent URL with user ID
    return f"https://twitter.com/intent/user?user_id={user_id}"

def generate_profile_link_options(user_data):
    """Generate multiple profile link options for a user"""
    user_id = user_data.get('id')
    username = user_data.get('username')
    
    options = {
        'primary': generate_profile_url(user_data),
        'intent': f"https://twitter.com/intent/user?user_id={user_id}"
    }
    
    # Add username-based links if available
    if username:
        options.update({
            'username': f"https://twitter.com/{username}",
            'x_domain': f"https://x.com/{username}"
        })
    
    return options

def test_profile_links():
    """Test profile link generation with different data scenarios"""
    
    # Test cases representing different data scenarios
    test_users = [
        {
            'id': '12345',
            'username': 'elonmusk',
            'user_link': 'https://twitter.com/elonmusk',
            'display_name': 'Elon Musk'
        },
        {
            'id': '67890',
            'username': 'jack',
            'user_link': None,
            'display_name': 'Jack Dorsey'
        },
        {
            'id': '11111',
            'username': None,
            'user_link': 'https://twitter.com/someuser',
            'display_name': 'User with custom link'
        },
        {
            'id': '22222',
            'username': None,
            'user_link': None,
            'display_name': 'User with only ID'
        }
    ]
    
    print("Profile Link Generation Test")
    print("=" * 50)
    
    for i, user in enumerate(test_users, 1):
        print(f"\nTest Case {i}: {user['display_name']}")
        print(f"  ID: {user['id']}")
        print(f"  Username: {user['username']}")
        print(f"  User Link: {user['user_link']}")
        
        # Generate primary URL
        primary_url = generate_profile_url(user)
        print(f"  Generated URL: {primary_url}")
        
        # Generate all options
        options = generate_profile_link_options(user)
        print("  All Options:")
        for key, url in options.items():
            print(f"    {key}: {url}")
        
        print("-" * 40)

def test_batch_generation():
    """Test batch profile URL generation"""
    users = [
        {'id': '1', 'username': 'user1', 'user_link': None},
        {'id': '2', 'username': 'user2', 'user_link': 'https://twitter.com/custom'},
        {'id': '3', 'username': None, 'user_link': None},
    ]
    
    print("\nBatch Profile URL Generation")
    print("=" * 50)
    
    url_map = {}
    for user in users:
        url_map[user['id']] = generate_profile_url(user)
    
    for user_id, url in url_map.items():
        print(f"User {user_id}: {url}")

def validate_profile_link(url):
    """Check if a profile link is valid/accessible"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        valid_domains = ['twitter.com', 'x.com']
        return parsed.hostname in valid_domains
    except:
        return False

def extract_username_from_url(url):
    """Extract username from a Twitter URL"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.hostname in ['twitter.com', 'x.com']:
            path_parts = [p for p in parsed.path.split('/') if p]
            if path_parts and not path_parts[0].startswith('intent'):
                return path_parts[0]
    except:
        pass
    return None

def test_utilities():
    """Test utility functions"""
    print("\nUtility Functions Test")
    print("=" * 50)
    
    test_urls = [
        'https://twitter.com/jack',
        'https://x.com/elonmusk',
        'https://twitter.com/intent/user?user_id=12345',
        'https://facebook.com/invalid',
        'invalid-url'
    ]
    
    for url in test_urls:
        is_valid = validate_profile_link(url)
        username = extract_username_from_url(url)
        print(f"URL: {url}")
        print(f"  Valid: {is_valid}")
        print(f"  Username: {username}")
        print()

if __name__ == "__main__":
    test_profile_links()
    test_batch_generation()
    test_utilities()
    
    print("\n" + "=" * 50)
    print("Profile Link System Summary:")
    print("- Handles users with complete data (username + user_link)")
    print("- Handles users with username only")
    print("- Handles users with custom link only")
    print("- Handles users with ID only (fallback to intent URL)")
    print("- Provides multiple link options (Twitter.com, X.com, Intent)")
    print("- Includes validation and utility functions")
    print("- Compatible with existing Following/Followers data") 