"""
Base App

"""
import logging
from dotenv import load_dotenv
import json



def init():
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.info("Initializing applicaiton...")
    logging.info("Loaded environment variables")


def fetchData():
    with open('twitter-personal-archive/tweets.json', 'r') as file:
        data = json.load(file)
    return data


def _any_reply_field_populated():
    pass

def extractReplies(tweets: list):
    """
    fields relevant to replies: 
        'in_reply_to_user_id_str', 
        'in_reply_to_status_id_str', 
        'in_reply_to_user_id', 
        'in_reply_to_status_id', (most relevant bc it's the actual tweet)
        'in_reply_to_screen_name'
    """ 
    pass

def main():
    logging.info("Running application..")
    tweets_data = fetchData()
    tweets: list = tweets_data['tweets']
    print(f'Number of tweets: {len(tweets)}')
    print(tweets_data['tweets'][:2])

    logging.info("Finished running application..")


if __name__ == "__main__":
    init()
    main()
