import twitter
import env

api = twitter.Api(
 consumer_key=env.config['consumer_key'],
 consumer_secret=env.config['consumer_secret'],
 access_token_key=env.config['access_token_key'],
 access_token_secret=env.config['access_token_secret']
 )


search = api.GetSearch(term='technology', lang='en', result_type='recent', count=100, max_id='')
for t in search:
 print t.user.screen_name + ' (' + t.created_at + ')'
 #Add the .encode to force encoding
 print t.text.encode('utf-8')
 print ''
