"""
Base App

"""
import logging
from dotenv import load_dotenv
import json
from transformers import pipeline
import sqlite3
import os
from enum import Enum

class Theme(Enum):
    POLITICS = 'politics'
    RELIGION = 'religion'
    ENTERTAINMENT = 'entertainment'
    MIAMI = 'Miami'
    TECHNOLOGY = 'technology'
    GEOPOLITICS = 'geopolitics'
    EUROPE = 'Europe'
    SPACEFLIGHT = 'spaceflight'

THRESHOLD_CLASSIFICATION_DEFAULT = 0.7  # initial guess; adjust as needed

def init():
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger_data = logging.getLogger('data_warnings')
    handler = logging.FileHandler('logs/data_warnings.log')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger_data.addHandler(handler)
    logger_data.setLevel(logging.WARNING)
    
    logging.info("Initializing application")
    logging.info("Configured logging.")
    logging.info("Set environment variables.")

    conn = sqlite3.connect("theme_classifications.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scores (
            tweet_id TEXT PRIMARY KEY,
            full_text TEXT NOT NULL,
            theme TEXT NOT NULL,
            score REAL NOT NULL
        )
        """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tweet_id ON scores (tweet_id)")
    # fetch already-classified's by theme: don't perform duplicate work
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_theme ON scores (theme)")

    conn.commit()
    logging.info(
        "Initialized SQLite database and created necessary table and index(es)."
    )
    return conn

def terminate(conn: sqlite3.Connection) -> None:
    """
    Clean up resources and gracefully terminate the application.
    """
    if conn:
        conn.close()
        logging.info("Database connection closed.")
    logging.info("Application terminated.")

def display_db(conn: sqlite3):
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    for table_name in tables:
        table_name = table_name[0]
        logging.info(f"Table: {table_name}")

        # Retrieve column information
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        logging.info(f"Columns: {column_names}")

        # Count the rows in the table
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        logging.info(f"Row count: {count}\n")


def fetchTweets():
    """
    Returns: [{
      "tweet" : {
        "edit_info" : {},
        "favorite_count": int,
        "id_str": str,
        "retweet_count": int,
        "full_text": str,
        "in_reply_to_user_id_str": str,
        ...
        },
    ]
    """
    with open("twitter-personal-archive/tweets.json", "r") as file:
        tweets = json.load(file)
    return tweets["tweets"]


# def filter_are_replies(tweets: list) -> list:
#     are_replies = []
#     for tw in tweets:
#         data = tw["tweet"]
#         if data.get("in_reply_to_status_id", "") != "":
#             are_replies.append(tw)

#     return are_replies


# def extract_replies(tweets: list):
#     """
#     fields relevant to replies:
#         'in_reply_to_user_id_str',
#         'in_reply_to_status_id_str',
#         'in_reply_to_user_id',
#         'in_reply_to_status_id', (most relevant bc it's the actual tweet)
#         'in_reply_to_screen_name'
#     """
#     pass


def fetch_classified_tweet_ids(conn: sqlite3, theme: str) -> set:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT tweet_id FROM scores WHERE theme = ?", (theme,))
        existing_ids = set(row[0] for row in cursor.fetchall())
        return existing_ids
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return set()


def classify_tweets(tweets: list, theme: str) -> list:
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    classified_tweets = []

    logging.info(f"Classifying {len(tweets)} tweets for theme '{theme}'")
    count = 0
    for tw_obj in tweets:
        count += 1
        if count % 100 == 0:
            logging.info(f"Classified {count} out of {len(tweets)} tweets.")
        tweet = tw_obj.get("tweet", "")
        if not tweet:
            logger_data.warn('object found with no tweet')
            continue
        full_text = tweet.get("full_text", "")
        tweet_id = tweet.get("id", "")
        if not tweet_id:
            logger_data.warn('tweet found with no id')
            continue
        if not full_text:
            logger_data.warn(f'tweet has no full_text [(id{tweet_id})]')
            continue
        classification = classifier(full_text, theme)
        # print(f'\033[95mClassified tweet full text {full_text} for theme {theme}: {classification}\033[0m')
        scores_by_theme = dict(zip(classification["labels"], classification["scores"]))
        classification_score = scores_by_theme.get(theme, 0)
        if not classification_score:
            logger_data.warn(f'no score found for theme {theme} after classification (tweet_id [{tweet_id}])')
            continue
        classified = {
            "tweet_id": tweet_id,
            "tweet_full_text": full_text,
            "theme_measured": theme,
            "classification_score": classification_score,
        }
        classified_tweets.append(classified)
    return classified_tweets

def insert_classified_tweets(conn: sqlite3.Connection, classified_tweets: list) -> int:
    cursor = conn.cursor()
    rows_affected = 0
    for tweet in classified_tweets:
        try:
            cursor.execute(
                "INSERT INTO scores (tweet_id, full_text, theme, score) VALUES (?, ?, ?, ?)",
                (
                    tweet["tweet_id"],
                    tweet["tweet_full_text"],
                    tweet["theme_measured"],
                    tweet["classification_score"],
                ),
            )
            rows_affected += cursor.rowcount
            logging.info(f"Successfully inserted tweet_id: {tweet['tweet_id']} into the database.")
        except sqlite3.Error as e:
            logging.error(f"Failed to insert tweet_id: {tweet['tweet_id']} into the database. Error: {e}")
    conn.commit()
    return rows_affected

def classify_and_save(conn: sqlite3, tweets: list, theme: str) -> int:
    existing_ids: set = fetch_classified_tweet_ids(conn, theme)
    # logging.info(f"Number of existing scored tweets IDs: {len(existing_ids)}")
    
    # logging.info(f'Number of existing IDs: {len(existing_ids)}')
    tweets_not_yet_classified = [t for t in tweets if t['tweet'].get('id', '') not in existing_ids]
    # logging.info(f'\033[94mNumber of tweets not yet clasified: {len(tweets_not_yet_classified)}\033[0m')
    classified_tweets: list = classify_tweets(tweets_not_yet_classified, theme)
    
    rows_inserted = insert_classified_tweets(conn, classified_tweets)
    logging.info(f'Number of classified tweets inserted into database: [{rows_inserted}]')
    
    return rows_inserted

# def generate_url_from_tweet_id(tweet_id):
#     twitter_username = os.getenv('TWITTER_USERNAME')
#     return f"https://twitter.com/{twitter_username}/status/{tweet_id}"

def main():
    conn = init()
    tweets = fetchTweets()
    print(f"Number of tweets: {len(tweets)}")

    # section: classify by topic
    # classify_topic(tweets)
    # political = get_tweets_for_theme(conn, tweets, "political")
    tweets_classified_and_inserted = classify_and_save(conn, tweets, Theme.ENTERTAINMENT.value)
    logging.info(f'Number of tweets classified and inserted: {tweets_classified_and_inserted}')
    # print(f"Length of political tweets: {len(political)}")
    # print("First 5 political tweets:", political[:5])

    # section: get favorites / retweets
    # engagement = {}
    # for t in tweets:
    #     fav_count = int(t['tweet']['favorite_count'])
    #     rt_count = int(t['tweet']['retweet_count'])
    #     tw_id = t['tweet']['id_str']
    #     if fav_count > 0 or rt_count > 0:
    #         engagement[tw_id] = {
                
    #         }
        # if int(fav_count) > 0:
        #     print(f'fav count: {t['tweet']['favorite_count']}')
        #     print(generate_url_from_id(tw_id))
        # if int(rt_count) > 0:
        #     print(f'rt count: {t['tweet']['retweet_count']}')
        #     print(generate_url_from_id(tw_id))

    # display_db(conn)

    terminate(conn)


if __name__ == "__main__":
    init()
    main()
