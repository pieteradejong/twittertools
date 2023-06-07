import private
import tweepy

def main():
    print('Hello Tweepy')
    
    client = tweepy.Client(
        bearer_token=private.Bearer_Token,
        access_token=private.Access_Token,
        access_token_secret=private.Access_Token_Secret,
        consumer_secret=private.API_Secret_Key
    )
    
    response = client.get_users(ids=private.USER_ID)
    print(response.data)
    
    response = client.get_users_tweets(private.USER_ID)
    for tweet in response.data:
        print(tweet.id)
        print(tweet.text)



if __name__ == "__main__":
    main()
