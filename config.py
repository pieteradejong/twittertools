import json

class Config(object):

	def __init__(self):
		with open("twitter_credentials.json", "r") as file:
			twitter_credentials = json.load(file)

		print(twitter_credentials)

		twitter_credentials['CONSUMER_KEY'] 	= twitter_credentials['API_key']
		twitter_credentials['CONSUMER_SECRET'] 	= twitter_credentials['API_Secret_Key']
		twitter_credentials['ACCESS_TOKEN'] 	= twitter_credentials['Access_Token']
		twitter_credentials['ACCESS_SECRET'] 	= twitter_credentials['Access_Token_Secret']

		print(twitter_credentials)
