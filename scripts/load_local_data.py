import os
import json
from pathlib import Path
import sqlite3

data_dir = Path(__file__).parent.parent / 'twitter-archive-2025-05-31' / 'data'
db_path = Path(__file__).parent.parent / 'data' / 'x_data.db'

# List of relevant data files
DATA_FILES = [
    'tweets.js', 'like.js', 'block.js', 'mute.js', 'lists-created.js', 'lists-member.js', 'lists-subscribed.js',
    'follower.js', 'following.js', 'direct-messages.js', 'direct-messages-group.js', 'deleted-tweets.js',
    'profile.js', 'account.js', 'tweet-headers.js', 'tweetdeck.js'
]
MEDIA_FOLDERS = [
    'moments_media', 'tweets_media', 'profile_media', 'direct_messages_media', 'direct_messages_group_media',
    'deleted_tweets_media', 'community_tweet_media', 'moments_tweets_media', 'grok_chat_media'
]

def load_json_js(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        if content.startswith('window.YTD'):
            json_start = content.find('=') + 1
            content = content[json_start:].strip().rstrip(';')
        return json.loads(content)

def create_tables(conn):
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tweets (
        id TEXT PRIMARY KEY, -- tweet.id_str or tweet.id
        text TEXT, -- tweet.full_text or tweet.text
        created_at TEXT, -- tweet.created_at
        conversation_id TEXT, -- tweet.conversation_id
        author_id TEXT, -- tweet.user_id_str or tweet.author_id
        in_reply_to_status_id TEXT, -- tweet.in_reply_to_status_id
        in_reply_to_user_id TEXT, -- tweet.in_reply_to_user_id
        in_reply_to_screen_name TEXT, -- tweet.in_reply_to_screen_name
        favorite_count INTEGER, -- tweet.favorite_count
        retweet_count INTEGER, -- tweet.retweet_count
        lang TEXT, -- tweet.lang
        deleted_at TEXT, -- deleted_tweets.deleted_at
        status TEXT DEFAULT 'published' -- 'published' or 'deleted'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS likes (
        tweet_id TEXT PRIMARY KEY, -- like.tweetId
        full_text TEXT, -- like.fullText
        expanded_url TEXT, -- like.expandedUrl
        liked_at TEXT, -- (not present, but for future API)
        author_id TEXT, -- extracted from URL or API
        author_username TEXT -- extracted from URL or API
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS blocks (
        user_id TEXT PRIMARY KEY, -- blocking.accountId
        user_link TEXT -- blocking.userLink
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS mutes (
        user_id TEXT PRIMARY KEY, -- muting.accountId
        user_link TEXT -- muting.userLink
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS lists (
        id TEXT PRIMARY KEY, -- list.id or url
        name TEXT, -- list.name (future API)
        url TEXT, -- userListInfo.url
        type TEXT -- created/member/subscribed
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, -- user.accountId or id
        username TEXT, -- user.screenName or username
        display_name TEXT, -- user.name or displayName
        user_link TEXT -- user.userLink
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS media (
        media_id TEXT PRIMARY KEY, -- media id
        tweet_id TEXT, -- tweet id
        type TEXT, -- media type
        url TEXT -- media url
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS account (
        account_id TEXT PRIMARY KEY, -- account.accountId
        username TEXT, -- account.username
        display_name TEXT, -- account.accountDisplayName
        email TEXT, -- account.email
        created_at TEXT, -- account.createdAt
        created_via TEXT -- account.createdVia
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS profile (
        account_id TEXT PRIMARY KEY, -- account.accountId
        bio TEXT, -- profile.description.bio
        website TEXT, -- profile.description.website
        location TEXT, -- profile.description.location
        avatar_url TEXT, -- profile.avatarMediaUrl
        header_url TEXT -- profile.headerMediaUrl
    )''')
    conn.commit()

def get_account_id(account_js_path):
    with open(account_js_path) as f:
        js = f.read()
        # Remove JS variable assignment if present
        js = js.split('=', 1)[1].strip()
        account_json = json.loads(js)
        return account_json[0]['account']['accountId']

def insert_tweets(conn, tweets, account_id):
    c = conn.cursor()
    count = 0
    for entry in tweets:
        tweet = entry.get('tweet') or entry
        c.execute('''INSERT OR IGNORE INTO tweets (id, text, created_at, conversation_id, author_id, in_reply_to_status_id, in_reply_to_user_id, in_reply_to_screen_name, favorite_count, retweet_count, lang, deleted_at, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (tweet.get('id_str') or tweet.get('id'),
                   tweet.get('full_text') or tweet.get('text'),
                   tweet.get('created_at'),
                   tweet.get('conversation_id'),
                   account_id,  # Set author_id to your account ID
                   tweet.get('in_reply_to_status_id'),
                   tweet.get('in_reply_to_user_id'),
                   tweet.get('in_reply_to_screen_name'),
                   int(tweet.get('favorite_count') or 0),
                   int(tweet.get('retweet_count') or 0),
                   tweet.get('lang'),
                   tweet.get('deleted_at'),
                   'published'))
        count += 1
    conn.commit()
    return count

def extract_author_from_url(expanded_url):
    """Extract username from Twitter URL like https://twitter.com/username/status/123"""
    if not expanded_url:
        return None, None
    
    import re
    # Match Twitter URLs: twitter.com/username/status/id or x.com/username/status/id
    pattern = r'(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)'
    match = re.search(pattern, expanded_url)
    
    if match:
        username = match.group(1)
        # Filter out invalid usernames (Twitter usernames can't contain certain chars)
        if username and not any(char in username for char in ['?', '&', '=', '#']):
            return None, username  # We don't have author_id from URL, only username
    
    return None, None

def insert_likes(conn, likes):
    c = conn.cursor()
    count = 0
    for entry in likes:
        like = entry.get('like') or entry
        
        # Try to extract author info from URL
        author_id, author_username = extract_author_from_url(like.get('expandedUrl'))
        
        # Use any existing author info from the like data (if available)
        author_id = like.get('authorId') or author_id
        author_username = like.get('authorUsername') or author_username
        
        c.execute('''INSERT OR IGNORE INTO likes (tweet_id, full_text, expanded_url, liked_at, author_id, author_username) VALUES (?, ?, ?, ?, ?, ?)''',
                  (like.get('tweetId'), like.get('fullText'), like.get('expandedUrl'), like.get('createdAt'), author_id, author_username))
        count += 1
    conn.commit()
    return count

def insert_blocks(conn, blocks):
    c = conn.cursor()
    count = 0
    for entry in blocks:
        block = entry.get('blocking') or entry
        c.execute('''INSERT OR IGNORE INTO blocks (user_id, user_link) VALUES (?, ?)''',
                  (block.get('accountId'), block.get('userLink')))
        count += 1
    conn.commit()
    return count

def insert_mutes(conn, mutes):
    c = conn.cursor()
    count = 0
    for entry in mutes:
        mute = entry.get('muting') or entry
        c.execute('''INSERT OR IGNORE INTO mutes (user_id, user_link) VALUES (?, ?)''',
                  (mute.get('accountId'), mute.get('userLink')))
        count += 1
    conn.commit()
    return count

def extract_list_info_from_url(url):
    """Extract list ID and name from Twitter list URL"""
    if not url:
        return None, None
    
    import re
    # Match Twitter list URLs: twitter.com/username/lists/id_or_name
    pattern = r'(?:twitter\.com|x\.com)/[^/]+/lists/(.+)$'
    match = re.search(pattern, url)
    
    if match:
        list_identifier = match.group(1)
        
        # If it's all digits, it's a numeric ID
        if list_identifier.isdigit():
            return list_identifier, None
        else:
            # It's a name-based identifier, use it as both ID and name
            # Clean up the name for display (replace hyphens with spaces, etc.)
            display_name = list_identifier.replace('-', ' ').replace('_', ' ').title()
            return list_identifier, display_name
    
    return None, None

def insert_lists(conn, lists_data, list_type):
    c = conn.cursor()
    count = 0
    for entry in lists_data:
        info = entry.get('userListInfo') or entry.get('list') or entry
        url = info.get('url')
        
        # Extract ID and name from URL
        list_id, list_name = extract_list_info_from_url(url)
        
        # Use extracted info or fallback to original data
        final_id = info.get('id') or list_id
        final_name = info.get('name') or list_name
        
        c.execute('''INSERT OR IGNORE INTO lists (id, name, url, type) VALUES (?, ?, ?, ?)''',
                  (final_id, final_name, url, list_type))
        count += 1
    conn.commit()
    return count

def insert_users(conn, users_data):
    c = conn.cursor()
    count = 0
    for entry in users_data:
        user = entry.get('follower') or entry.get('following') or entry.get('user') or entry
        c.execute('''INSERT OR IGNORE INTO users (id, username, display_name, user_link) VALUES (?, ?, ?, ?)''',
                  (user.get('accountId') or user.get('id'), user.get('screenName') or user.get('username'), user.get('name') or user.get('displayName'), user.get('userLink')))
        count += 1
    conn.commit()
    return count

def main():
    db_path.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(db_path)
    create_tables(conn)
    summary = {}

    # Load account ID from account.js
    account_js_path = data_dir / 'account.js'
    account_id = get_account_id(account_js_path)

    # Tweets
    tweets_path = data_dir / 'tweets.js'
    if tweets_path.exists():
        tweets_data = load_json_js(tweets_path)
        summary['tweets'] = insert_tweets(conn, tweets_data, account_id)
    else:
        summary['tweets'] = 0
    # Likes
    likes_path = data_dir / 'like.js'
    if likes_path.exists():
        likes_data = load_json_js(likes_path)
        summary['likes'] = insert_likes(conn, likes_data)
    else:
        summary['likes'] = 0
    # Blocks
    blocks_path = data_dir / 'block.js'
    if blocks_path.exists():
        blocks_data = load_json_js(blocks_path)
        summary['blocks'] = insert_blocks(conn, blocks_data)
    else:
        summary['blocks'] = 0
    # Mutes
    mutes_path = data_dir / 'mute.js'
    if mutes_path.exists():
        mutes_data = load_json_js(mutes_path)
        summary['mutes'] = insert_mutes(conn, mutes_data)
    else:
        summary['mutes'] = 0
    # Lists
    for fname, ltype in [('lists-created.js', 'created'), ('lists-member.js', 'member'), ('lists-subscribed.js', 'subscribed')]:
        path = data_dir / fname
        if path.exists():
            lists_data = load_json_js(path)
            summary[f'lists_{ltype}'] = insert_lists(conn, lists_data, ltype)
        else:
            summary[f'lists_{ltype}'] = 0
    # Users (followers and following)
    for fname, utype in [('follower.js', 'follower'), ('following.js', 'following')]:
        path = data_dir / fname
        if path.exists():
            users_data = load_json_js(path)
            summary[utype] = insert_users(conn, users_data)
        else:
            summary[utype] = 0
    # Profile
    profile_path = data_dir / 'profile.js'
    if profile_path.exists():
        profile_data = load_json_js(profile_path)
        if profile_data and 'profile' in profile_data[0]:
            p = profile_data[0]['profile']
            avatar_url = p.get('avatarMediaUrl')
            header_url = p.get('headerMediaUrl')
            bio = p.get('description', {}).get('bio', '')
            website = p.get('description', {}).get('website', '')
            location = p.get('description', {}).get('location', '')
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO profile (account_id, bio, website, location, avatar_url, header_url) VALUES (?, ?, ?, ?, ?, ?)''',
                      (account_id, bio, website, location, avatar_url, header_url))
            conn.commit()
            summary['profile'] = 1
        else:
            summary['profile'] = 0
    else:
        summary['profile'] = 0
    print("Summary of records inserted:")
    for k, v in summary.items():
        print(f"{k}: {v}")
    conn.close()

if __name__ == "__main__":
    main() 