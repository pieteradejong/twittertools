# Twitter(X) Tools

[![twittertools](https://github.com/pieteradejong/twittertools/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/pieteradejong/twittertools/actions/workflows/ci.yml)

## Goal: v0.1 Milestone
~~* :white_check_mark: make successful Twitter API call~~

## Todos
* [DONE] load all tweets from archive download
* [DONE] use open source "`zero-shot-classification`" classifier to detect given themes
* [WIP] save classifications to sqliteDB (they are expensive, deterministic, and I want to work with `sqlite`)
  * steps for performing an expensive operation like classification:
    * 1) before starting, load from db table all tweet_id's that already have a classification for the given topic
    * 2) classify all other tweets and append to in-memory list
    * 3) when all done, insert added classifications to db
* [PERHAPS] fetch own tweets with zero likes or zero replies or zero retweets

[DEPRECATED] ~~## Functional requirements~~
* show who I blocked and when, plus reminders to potentially unblock
* show who is not following me back
* show who I am not following back
* attempt to group tweeps I follow into lists that make sense
* attempt to classify and storify my favorites in ways that make sense
* when viewing another user's profile, recommend which if any of your lists that user would be a good fit for
* reply ranking
* for user: ratio replies/original
* for user: how often replies to replies?
* given tweet, find all instances of quoted tweet
* brief into qustionairre to get you started
