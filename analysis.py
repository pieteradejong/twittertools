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
print [f.name for f in followers]
print "(DONE) Getting all followers' user names\n\n\n"


print "Getting all followees' user names\n"
friends = api.GetFriends()
print [f.name for f in friends]
print "(DONE) Getting all followees' user names\n\n\n"

followers_set = set(followers)
followees_set = set(followees)
not_following_me_back = [x for x in followees if x not in followers_set]
Im_not_following_back = [x for x in followers if x not in followees_set]
