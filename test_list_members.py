#!/usr/bin/env python3
"""
Test script for List Members functionality

Demonstrates how to use the ListMembersFetcher to get members from Twitter lists.
"""

import os
import sys
import sqlite3
from datetime import datetime

# Add src directory to path for imports
sys.path.append('src')

def create_sample_list_data(db_path: str = "data/x_data.db"):
    """Create sample list and member data for testing"""
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    with sqlite3.connect(db_path) as conn:
        # Create tables if they don't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS twitter_lists (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                member_count INTEGER DEFAULT 0,
                follower_count INTEGER DEFAULT 0,
                private BOOLEAN DEFAULT 0,
                owner_id TEXT,
                created_at TEXT,
                fetched_at TEXT,
                last_updated TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS list_members (
                list_id TEXT,
                user_id TEXT,
                username TEXT,
                name TEXT,
                description TEXT,
                profile_image_url TEXT,
                verified BOOLEAN DEFAULT 0,
                protected BOOLEAN DEFAULT 0,
                follower_count INTEGER,
                following_count INTEGER,
                tweet_count INTEGER,
                created_at TEXT,
                location TEXT,
                url TEXT,
                fetched_at TEXT,
                PRIMARY KEY (list_id, user_id)
            )
        """)
        
        now = datetime.now().isoformat()
        
        # Sample lists
        sample_lists = [
            {
                'id': 'list_tech_leaders',
                'name': 'Tech Leaders',
                'description': 'Influential people in technology and startups',
                'member_count': 3,
                'follower_count': 1250,
                'private': False,
                'owner_id': 'user_123',
                'created_at': '2023-01-15T10:30:00.000Z',
                'fetched_at': now,
                'last_updated': now
            },
            {
                'id': 'list_ai_researchers',
                'name': 'AI Researchers',
                'description': 'Leading researchers in artificial intelligence',
                'member_count': 2,
                'follower_count': 890,
                'private': False,
                'owner_id': 'user_456',
                'created_at': '2023-03-20T14:15:00.000Z',
                'fetched_at': now,
                'last_updated': now
            }
        ]
        
        # Sample members
        sample_members = [
            # Tech Leaders list members
            {
                'list_id': 'list_tech_leaders',
                'user_id': '12345',
                'username': 'elonmusk',
                'name': 'Elon Musk',
                'description': 'CEO of Tesla, SpaceX, and other companies',
                'profile_image_url': 'https://pbs.twimg.com/profile_images/1590968738358079488/IY9Gx6Ok_400x400.jpg',
                'verified': True,
                'protected': False,
                'follower_count': 150000000,
                'following_count': 200,
                'tweet_count': 25000,
                'created_at': '2009-06-02T20:12:29.000Z',
                'location': 'Austin, Texas',
                'url': 'https://twitter.com/elonmusk',
                'fetched_at': now
            },
            {
                'list_id': 'list_tech_leaders',
                'user_id': '67890',
                'username': 'sundarpichai',
                'name': 'Sundar Pichai',
                'description': 'CEO of Google and Alphabet',
                'profile_image_url': 'https://pbs.twimg.com/profile_images/864282616597405701/M-FEJMZ0_400x400.jpg',
                'verified': True,
                'protected': False,
                'follower_count': 5000000,
                'following_count': 150,
                'tweet_count': 1200,
                'created_at': '2011-03-15T08:45:00.000Z',
                'location': 'Mountain View, CA',
                'url': 'https://twitter.com/sundarpichai',
                'fetched_at': now
            },
            {
                'list_id': 'list_tech_leaders',
                'user_id': '11111',
                'username': 'satyanadella',
                'name': 'Satya Nadella',
                'description': 'Chairman and CEO, Microsoft',
                'profile_image_url': 'https://pbs.twimg.com/profile_images/1221837516816306177/_Ld4un5A_400x400.jpg',
                'verified': True,
                'protected': False,
                'follower_count': 3000000,
                'following_count': 300,
                'tweet_count': 800,
                'created_at': '2010-05-20T12:30:00.000Z',
                'location': 'Redmond, WA',
                'url': 'https://twitter.com/satyanadella',
                'fetched_at': now
            },
            # AI Researchers list members
            {
                'list_id': 'list_ai_researchers',
                'user_id': '22222',
                'username': 'ylecun',
                'name': 'Yann LeCun',
                'description': 'Chief AI Scientist at Meta, Professor at NYU',
                'profile_image_url': 'https://pbs.twimg.com/profile_images/1552946811751657472/rqWIoJCK_400x400.jpg',
                'verified': True,
                'protected': False,
                'follower_count': 800000,
                'following_count': 1000,
                'tweet_count': 15000,
                'created_at': '2010-02-10T16:20:00.000Z',
                'location': 'New York, NY',
                'url': 'https://twitter.com/ylecun',
                'fetched_at': now
            },
            {
                'list_id': 'list_ai_researchers',
                'user_id': '33333',
                'username': 'AndrewYNg',
                'name': 'Andrew Ng',
                'description': 'Co-founder of Coursera, Founder of Landing AI',
                'profile_image_url': 'https://pbs.twimg.com/profile_images/1506060664867057664/8_bKSKWX_400x400.jpg',
                'verified': True,
                'protected': False,
                'follower_count': 1200000,
                'following_count': 500,
                'tweet_count': 8000,
                'created_at': '2009-12-05T09:15:00.000Z',
                'location': 'Stanford, CA',
                'url': 'https://twitter.com/AndrewYNg',
                'fetched_at': now
            }
        ]
        
        # Insert sample data
        for list_data in sample_lists:
            conn.execute("""
                INSERT OR REPLACE INTO twitter_lists 
                (id, name, description, member_count, follower_count, private, owner_id, created_at, fetched_at, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                list_data['id'], list_data['name'], list_data['description'],
                list_data['member_count'], list_data['follower_count'], list_data['private'],
                list_data['owner_id'], list_data['created_at'], list_data['fetched_at'], list_data['last_updated']
            ))
        
        for member in sample_members:
            conn.execute("""
                INSERT OR REPLACE INTO list_members 
                (list_id, user_id, username, name, description, profile_image_url, 
                 verified, protected, follower_count, following_count, tweet_count,
                 created_at, location, url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                member['list_id'], member['user_id'], member['username'], member['name'],
                member['description'], member['profile_image_url'], member['verified'],
                member['protected'], member['follower_count'], member['following_count'], 
                member['tweet_count'], member['created_at'], member['location'], 
                member['url'], member['fetched_at']
            ))
        
        conn.commit()
        print(f"✅ Created sample data with {len(sample_lists)} lists and {len(sample_members)} members")

def test_list_queries(db_path: str = "data/x_data.db"):
    """Test querying list data"""
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        
        print("\n📋 Available Lists:")
        print("-" * 50)
        
        cursor = conn.execute("""
            SELECT id, name, description, member_count, follower_count
            FROM twitter_lists 
            ORDER BY name
        """)
        
        lists = cursor.fetchall()
        for list_row in lists:
            print(f"ID: {list_row['id']}")
            print(f"Name: {list_row['name']}")
            print(f"Description: {list_row['description']}")
            print(f"Members: {list_row['member_count']}")
            print(f"Followers: {list_row['follower_count']}")
            print()
        
        # Test members for each list
        for list_row in lists:
            list_id = list_row['id']
            list_name = list_row['name']
            
            print(f"👥 Members of '{list_name}':")
            print("-" * 50)
            
            cursor = conn.execute("""
                SELECT user_id, username, name, description, verified, follower_count
                FROM list_members 
                WHERE list_id = ?
                ORDER BY name
            """, (list_id,))
            
            members = cursor.fetchall()
            for member in members:
                verified_badge = "✓" if member['verified'] else ""
                followers = f"{member['follower_count']:,}" if member['follower_count'] else "N/A"
                
                print(f"  @{member['username']} {verified_badge}")
                print(f"    Name: {member['name']}")
                print(f"    Bio: {member['description'][:80]}..." if member['description'] and len(member['description']) > 80 else f"    Bio: {member['description']}")
                print(f"    Followers: {followers}")
                print()

def test_api_endpoints():
    """Test the API endpoints (requires server to be running)"""
    try:
        import requests
        
        base_url = "http://localhost:8000"
        
        print("\n🌐 Testing API Endpoints:")
        print("-" * 50)
        
        # Test lists endpoint
        try:
            response = requests.get(f"{base_url}/api/lists", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ GET /api/lists - Found {len(data.get('lists', []))} lists")
            else:
                print(f"❌ GET /api/lists - Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ GET /api/lists - Connection error: {e}")
        
        # Test list members endpoint
        try:
            response = requests.get(f"{base_url}/api/lists/list_tech_leaders/members", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ GET /api/lists/list_tech_leaders/members - Found {len(data.get('members', []))} members")
            else:
                print(f"❌ GET /api/lists/list_tech_leaders/members - Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ GET /api/lists/list_tech_leaders/members - Connection error: {e}")
            
    except ImportError:
        print("❌ requests library not available for API testing")

def main():
    """Main test function"""
    print("🧪 Testing List Members Functionality")
    print("=" * 50)
    
    # Create sample data
    create_sample_list_data()
    
    # Test database queries
    test_list_queries()
    
    # Test API endpoints (if server is running)
    test_api_endpoints()
    
    print("\n📝 Next Steps:")
    print("1. Start your server: ./run.sh")
    print("2. Visit http://localhost:3000 to see the frontend")
    print("3. Use the ListMembersList component to display list members")
    print("4. To fetch real data, configure TWITTER_BEARER_TOKEN and use ListMembersFetcher")
    
    print("\n💡 Example API Usage:")
    print("GET http://localhost:8000/api/lists")
    print("GET http://localhost:8000/api/lists/list_tech_leaders/members")

if __name__ == "__main__":
    main() 