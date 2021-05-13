# import twitter
# import env

# api = twitter.Api(
#  consumer_key=env.config['consumer_key'],
#  consumer_secret=env.config['consumer_secret'],
#  access_token_key=env.config['access_token_key'],
#  access_token_secret=env.config['access_token_secret']
#  )


# followers = api.GetFollowers()
# # print [unicode(f.name) , "\n" for f in followers]
# for f in followers:
#   print f.screen_name

# test whether i can write a few strings to a file:

# with open("test.txt", "w") as text_file:
#   text_file.write("fmdlsflk")
#   text_file.write("this is a test")
#   text_file.write("\n")
#   text_file.write("this is a test")
#   text_file.write("this is a test")
#   text_file.write("\n")
#   text_file.write("this is a test")



# testing whether i can cal a function before it is defined:



def double(number):
  return 2 * number

print double(1)

