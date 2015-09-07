import twitter
import env

api = twitter.Api(
 consumer_key=env.config['consumer_key'],
 consumer_secret=env.config['consumer_secret'],
 access_token_key=env.config['access_token_key'],
 access_token_secret=env.config['access_token_secret']
 )

# Friends = who am I following
# Followers = who is following me

print "Verifying Twitter API Credentials.."
print api.VerifyCredentials()
print "(DONE) Twitter API Credentials Verified"

# this was just for testing, we don't need it now
# search = api.GetSearch(term='technology', lang='en', result_type='recent', count=100, max_id='')
# with open("followers.txt", "w") as text_file:
#   for t in search:
#     screen_name = t.user.screen_name
#     print t.user.screen_name + ' (' + t.created_at + ')'
#     #Add the .encode to force encoding
#     print t.text.encode('utf-8')
#     text_file.write(screen_name)
#     text_file.write("\n")
#     print ''


#  commented out because we already have followers
# print "Getting all followers' user names\n"
# followers = api.GetFollowers()
# with open("followers2.txt", "w") as text_file:
#   for f in followers:
#     text_file.write(f.name.encode('utf8'))  
#     text_file.write("\t")
#     text_file.write(f.screen_name.encode('utf8'))  
#     text_file.write("\n")
#     print f.name
# print "(DONE) Getting all followers' user names\n\n\n"


print "Getting all friends' user names\n"
friends = api.GetFriends()
with open("friends2.txt", "w") as text_file:
  for f in followers:
    text_file.write(f.name.encode('utf8'))
    text_file.write("\t")
    text_file.write(f.screen_name.encode('utf8'))
    text_file.write("\n")
    print f.name, "\t", f.screen_name
print "(DONE) Getting all friends' user names\n\n\n"

# followers_set = set(followers)
# followees_set = set(followees)
# not_following_me_back = [x for x in followees if x not in followers_set]
# Im_not_following_back = [x for x in followers if x not in followees_set]

def get_followers():
  followers = set()
  with open("followers.txt", "r") as text_file:
    for line in text_file:
      user = line.split()
      user_username = user[0]
      user_screen_name = user[1]
      followers.add(user_screen_name)
  return followers

def get_friends():
  friends = set()
  with open("friends.txt", "r") as text_file:
    for line in text_file:
      user = line.split()
      user_username = user[0]
      user_screen_name = user[1]
      friends.add(user_screen_name)
  return friends

# friends that are not following me back
def write_non_followers():
  followers = get_followers()
  friends = get_friends()
  non_follow_back = [x for x in friends if x not in followers]
  with open("friends_non_followers.txt", "w") as f:
    for user in non_follow_back:
      f.write(user + "\n")

# followers that I am not following back
def write_non_friends():
  followers = get_followers()
  friends = get_friends()
  non_following_back = [x for x in followers if x not in friends]
  with open("followers_non_following_back.txt", "w") as f:
    for user in non_following_back:
      f.write(user + "\n")



