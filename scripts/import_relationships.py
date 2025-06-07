#!/usr/bin/env python3
"""
Import following and follower relationships from Twitter archive.
"""

import json
import sqlite3
import re
import sys
import os
from pathlib import Path
from datetime import datetime

# Add the src directory to the path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

def extract_js_data(file_path: str, variable_name: str):
    """Extract data from JavaScript files in Twitter archive format."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the variable assignment - more robust pattern
        pattern = rf'window\.YTD\.{variable_name}\.part0\s*=\s*(\[.*?\]);'
        match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
        
        if match:
            json_str = match.group(1)
            return json.loads(json_str)
        else:
            # Try alternative approach - find the start and end manually
            start_marker = f'window.YTD.{variable_name}.part0 = ['
            
            start_idx = content.find(start_marker)
            if start_idx != -1:
                start_idx += len(start_marker) - 1  # Include the opening bracket
                # Find the matching closing bracket at the end
                # The file typically ends with just ']' 
                json_str = content[start_idx:].strip()
                if json_str.endswith(']'):
                    return json.loads(json_str)
            
            print(f"Could not find {variable_name} data in {file_path}")
            return []
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

def import_account_data(db_path: str, archive_path: str):
    """Import account data from Twitter archive."""
    account_file = os.path.join(archive_path, 'data', 'account.js')
    if not os.path.exists(account_file):
        print(f"Account file not found: {account_file}")
        return None
    
    print(f"Importing account data from {account_file}")
    account_data = extract_js_data(account_file, 'account')
    
    if not account_data:
        print("No account data found")
        return None
    
    account_info = account_data[0]['account']
    
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO account 
            (account_id, username, display_name, email, created_at, created_via)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            account_info['accountId'],
            account_info['username'],
            account_info['accountDisplayName'],
            account_info['email'],
            account_info['createdAt'],
            account_info['createdVia']
        ))
        conn.commit()
    
    print(f"Imported account: {account_info['username']} ({account_info['accountId']})")
    return account_info['accountId']

def import_relationships(db_path: str, archive_path: str):
    """Import following and follower relationships from Twitter archive."""
    
    # Get current user ID from account table, or import it if missing
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT account_id FROM account LIMIT 1")
        row = cursor.fetchone()
        if not row:
            print("No user found in account table, importing account data...")
            user_id = import_account_data(db_path, archive_path)
            if not user_id:
                print("Error: Could not import account data")
                return
        else:
            user_id = row[0]
    
    print(f"Importing relationships for user ID: {user_id}")
    
    # Import following data
    following_file = os.path.join(archive_path, 'data', 'following.js')
    if os.path.exists(following_file):
        print(f"Importing following data from {following_file}")
        following_data = extract_js_data(following_file, 'following')
        
        with sqlite3.connect(db_path) as conn:
            # Clear existing following relationships for this user
            conn.execute("""
                DELETE FROM relationships 
                WHERE source_user_id = ? AND relationship_type = 'following'
            """, (user_id,))
            
            # Insert following relationships
            now = datetime.now().isoformat()
            for item in following_data:
                if 'following' in item and 'accountId' in item['following']:
                    target_user_id = item['following']['accountId']
                    relationship_id = f"{user_id}_{target_user_id}_following"
                    
                    conn.execute("""
                        INSERT OR REPLACE INTO relationships 
                        (id, source_user_id, target_user_id, relationship_type, 
                         created_at, cached_at, expires_at, data_source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        relationship_id,
                        user_id,
                        target_user_id,
                        'following',
                        now,
                        now,
                        None,  # No expiration for archive data
                        'archive'
                    ))
            
            conn.commit()
            print(f"Imported {len(following_data)} following relationships")
    else:
        print(f"Following file not found: {following_file}")
    
    # Import follower data
    follower_file = os.path.join(archive_path, 'data', 'follower.js')
    if os.path.exists(follower_file):
        print(f"Importing follower data from {follower_file}")
        follower_data = extract_js_data(follower_file, 'follower')
        
        with sqlite3.connect(db_path) as conn:
            # Clear existing follower relationships for this user
            conn.execute("""
                DELETE FROM relationships 
                WHERE target_user_id = ? AND relationship_type = 'follower'
            """, (user_id,))
            
            # Insert follower relationships
            now = datetime.now().isoformat()
            for item in follower_data:
                if 'follower' in item and 'accountId' in item['follower']:
                    source_user_id = item['follower']['accountId']
                    relationship_id = f"{source_user_id}_{user_id}_follower"
                    
                    conn.execute("""
                        INSERT OR REPLACE INTO relationships 
                        (id, source_user_id, target_user_id, relationship_type, 
                         created_at, cached_at, expires_at, data_source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        relationship_id,
                        source_user_id,
                        user_id,
                        'follower',
                        now,
                        now,
                        None,  # No expiration for archive data
                        'archive'
                    ))
            
            conn.commit()
            print(f"Imported {len(follower_data)} follower relationships")
    else:
        print(f"Follower file not found: {follower_file}")
    
    # Print summary
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("""
            SELECT relationship_type, COUNT(*) 
            FROM relationships 
            WHERE source_user_id = ? OR target_user_id = ?
            GROUP BY relationship_type
        """, (user_id, user_id))
        
        print("\nRelationship summary:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}")

def main():
    """Main function."""
    # Default paths
    db_path = "data/x_data.db"
    archive_path = "twitter-archive-2025-05-31"
    
    # Check if files exist
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    if not os.path.exists(archive_path):
        print(f"Archive directory not found: {archive_path}")
        return
    
    print("Starting relationship import...")
    import_relationships(db_path, archive_path)
    print("Import completed!")

if __name__ == "__main__":
    main() 