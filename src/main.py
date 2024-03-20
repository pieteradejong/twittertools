"""
Base App

"""
import logging
from dotenv import load_dotenv
import json
from transformers import pipeline
import sqlite3


def init():
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.info("Initializing applicaiton...")
    logging.info("Loaded environment variables")

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
    # conn.close()
    logging.info(
        "Initialized SQLite database and created necessary table and index(es)."
    )
    return conn


def display_db(conn: sqlite3, database_path: str):
    # conn = sqlite3.connect(database_path)
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

    conn.close()


def fetchTweets():
    with open("twitter-personal-archive/tweets.json", "r") as file:
        tweets = json.load(file)
    return tweets["tweets"]


def filter_are_replies(tweets: list) -> list:
    are_replies = []
    for tw in tweets:
        data = tw["tweet"]
        if data.get("in_reply_to_status_id", "") != "":
            are_replies.append(tw)

    return are_replies


def extract_replies(tweets: list):
    """
    fields relevant to replies:
        'in_reply_to_user_id_str',
        'in_reply_to_status_id_str',
        'in_reply_to_user_id',
        'in_reply_to_status_id', (most relevant bc it's the actual tweet)
        'in_reply_to_screen_name'
    """
    pass


def classify_topic(tweets: list):
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    categories = [
        "politics",
        "religion",
        "entertainment",
        "Miami",
        "technology",
        "geopolitics",
        "Europe",
        "spaceflight",
    ]
    for tweet in tweets[:5]:
        full_text = tweet["tweet"].get("full_text", "")
        if full_text:
            result = classifier(full_text, categories)
            for k, v in result.items():
                print(f"{k}: {v}")
            # print(f"\nTweet: {full_text}\nClassification topic result: {result}\n")


def get_tweets_for_theme(conn: sqlite3, tweets: list, theme: str) -> list:
    # conn = sqlite3.connect('theme_classifications.db')
    cursor = conn.cursor()
    cursor.execute("SELECT tweet_id FROM scores WHERE theme = ?", (theme,))
    existing_ids = set(row[0] for row in cursor.fetchall())

    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    political_classified = []
    THRESHOLD = 0.7
    for t in tweets[:100]:
        full_text = t["tweet"].get("full_text", "")
        if full_text and t["tweet"]["id"] not in existing_ids:
            classification = classifier(full_text, theme)
            scores_by_theme = dict(
                zip(classification["labels"], classification["scores"])
            )
            if scores_by_theme.get(theme, 0) > THRESHOLD:
                classified = {
                    "tweet_id": t["tweet"]["id"],
                    "tweet_full_text": full_text,
                    "theme_measured": theme,
                    "classification_score": scores_by_theme.get(theme, 0),
                }
                political_classified.append(classified)

                cursor.execute(
                    "INSERT INTO scores (tweet_id, full_text, theme, score) VALUES (?, ?, ?, ?)",
                    (
                        t["tweet"]["id_str"],
                        full_text,
                        theme,
                        scores_by_theme.get(theme, 0),
                    ),
                )

    conn.commit()
    # conn.close()
    return political_classified


def main():
    logging.info("Running application..")
    conn = init()
    tweets = fetchTweets()
    logging.info(f"\033[96mNumber of tweets: {len(tweets)}\033[0m")

    # are_replies = filter_are_replies(tweets=tweets)
    # logging.info(f'\033[96mNumber of tweets that are replies: {len(are_replies)}\033[0m')
    # classify_topic(tweets)
    political = get_tweets_for_theme(conn, tweets, "political")
    print(f"Length of political tweets: {len(political)}")
    print("First 5 political tweets:", political[:5])

    display_db(conn, "theme_classifications.db")

    conn.close()
    logging.info("Database connection closed.")
    logging.info("Finished running application..")


if __name__ == "__main__":
    init()
    main()
