import private
import tweepy


def get_user_follows(client: tweepy.Client, user_id: int) -> list:
    pass

def get_user_followers(client: tweepy.Client, user_id: int) -> list:
    # response = client.get_users_followers(user_id, user_fields=["profile_image_url"])
    response = client.get_users_followers(user_id)
    return response.data

def get_follow_followed_overlap():
    pass

def get_user_tweets(client: tweepy.Client, user_id: int) -> list:
    response = client.get_users_tweets(user_id, user_fields=["created_at", "description"])
    return response.data

def get_client_methods(client: tweepy.Client) -> list:
    return dir(client)

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

    # user_followers = get_user_followers(client, private.TWITTER_USER_ID)
    # for f in user_followers:
    #     print(f)

    # client_methods = get_client_methods(client)
    # print(*client_methods, sep="\n")


if __name__ == "__main__":
    main()
