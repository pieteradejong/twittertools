import private
import tweepy


def get_followers(client: tweepy.Client, user_id: int) -> list:
    response = client.get_users_followers(user_id, user_fields=["profile_image_url"])
    return response.data

def get_user_tweets(client: tweepy.Client, user_id: int) -> list:
    response = client.get_users_tweets(user_id)
    return response.data

def main():
    print('Hello Tweepy')
    
    client = tweepy.Client(
        bearer_token=private.Bearer_Token,
        access_token=private.Access_Token,
        access_token_secret=private.Access_Token_Secret,
        consumer_secret=private.API_Secret_Key
    )
    
    user_tweets = get_user_tweets(client, private.TWITTER_USER_ID)
    for tweet in user_tweets:
        print(tweet.id)
        print(tweet.text)



if __name__ == "__main__":
    main()
