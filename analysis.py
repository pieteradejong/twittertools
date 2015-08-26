import twitter
import env

api = twitter.Api(
 consumer_key=env.config['consumer_key'],
 consumer_secret=env.config['consumer_secret'],
 access_token_key=env.config['access_token_key'],
 access_token_secret=env.config['access_token_secret']
 )

print "Verifying Twitter API Credentials.."
print api.VerifyCredentials()
print "(DONE) Twitter API Credentials Verified"


search = api.GetSearch(term='technology', lang='en', result_type='recent', count=100, max_id='')
for t in search:
 print t.user.screen_name + ' (' + t.created_at + ')'
 #Add the .encode to force encoding
 print t.text.encode('utf-8')
 print ''


print "Getting all followers' user names\n"
followers = api.GetFollowers()
for fol in followers:
  print fol.screen_name
print "(DONE) Getting all followers' user names\n\n\n"

print "Getting all followees' user names\n"
friends = api.GetFriends()
for friend in friends:
  print friend.screen_name
print "(DONE) Getting all followees' user names\n\n\n"


