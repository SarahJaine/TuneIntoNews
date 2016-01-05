import requests
from textblob import TextBlob
from random import randint
import tweepy
import os, site, sys

from TuneIntoNews_credentials import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_KEY, ACCESS_SECRET, NPR_KEY

###################
### Virtual Env ###
###################

## Tell wsgi to add the Python site-packages to its path
site.addsitedir('/Users/sz/Documents/TuneIntoNews/TuneIntoNews/lib/python2.7/site-packages')

## Activate my virtual environment
activate_this = os.path.expanduser('/Users/sz/Documents/TuneIntoNews/TuneIntoNews/bin/activate_this.py')
execfile(activate_this, dict(__file__=activate_this))

## Calculate the path based on the location of the WSGI script
project = '/Users/sz/Documents/TuneIntoNews/TuneIntoNews'
workspace = os.path.dirname(project)
sys.path.append(workspace)

###################
##### NPR API #####
###################

## Request NPR top stories
url_npr='http://api.npr.org/query?id=1001&fields=title,titles&date=current&dateType=story&output=JSON&numResults=20&apiKey={0}'.format(NPR_KEY)
response=requests.get(url_npr)
stories=response.json()

## Output single story at random
story_picker=randint(0,len(stories['list']['story'])-1)
story_title= stories['list']['story'][story_picker]['title']['$text']
story_url= stories['list']['story'][story_picker]['link'][2]['$text']
story_title_low =story_title.lower()

## Pull out nouns, pl nouns, and adjectives (all must be at least 3 char length)
news_nouns=[]
story_title_blob = TextBlob(story_title_low)
for text_and_tag in story_title_blob.tags:
	if (text_and_tag[1]=='NN' or text_and_tag[1]=='JJ' or text_and_tag[1]=='NNS') and len(text_and_tag[0])>2:
		if text_and_tag[0]!="watch" and text_and_tag[0]!="listen":
			news_nouns.append(text_and_tag[0].replace("'",""))

###################
### Spotify API ###
###################

def most_popular(x):
	pop_rate=max(x)
	x.remove(max(x))
	return pop_rate

## Request tracks, assign needed song details to simplified dictionary
track_details={}
for search_term in news_nouns:
	url_spotify='https://api.spotify.com/v1/search?q=track:{0}+NOT+christmas&type=track&market=US&limit=5'.format(search_term)
	response=requests.get(url_spotify)
	tracks=response.json()
	try:
		returns= tracks['tracks']['items']
	except KeyError:
		pass
	else:
		for result in returns:
			## Exclude songs with populatity =<1 and explicit songs
			if result['popularity']>1 and result['explicit']==False:
				## Exclude songs with same title and songs already added to dictionary
				if track_details.get(result['name']) is None:
					## Excude songs with featured artist matching a search_term
					if (result['name'].lower().find('feat.')==-1 or result['name'].lower().find(search_term)<result['name'].lower().find('feat.')) \
					and (result['name'].lower().find('(feat')==-1 or result['name'].lower().find(search_term)<result['name'].lower().find('(feat')):
						track_details[result['name']]= {
								'track_title':result['name'],
								'track_artist':result['artists'][0]['name'],
								'track_url':result['external_urls']['spotify'],
								'track_popularity':result['popularity'],
								'track_explicit':result['explicit'],
								'image':result['album']['images'][1]['url'],
								'return_song':False,}

## Multiply popularity rating by number of search_terms in song name 
for track in track_details.keys():
	news_nouns_included=0
	news_nouns_total=0
	for search_term in news_nouns:
		news_nouns_included=track.lower().count(search_term)
		news_nouns_total+=news_nouns_included
	if news_nouns_total>1:
		track_details[track]['track_popularity']=track_details[track]['track_popularity']*news_nouns_total

## Find 2 highest popularity ratings
popularity_all=[]
for track in track_details.keys():
	popularity_all.append(track_details[track]['track_popularity'])
pop_rate_1 = most_popular(popularity_all)
if len(popularity_all)>0:
	pop_rate_2 = most_popular(popularity_all)

## Output 2 songs that match one of 2 highest popularity ratings
return_song_counter=1
for track in track_details.keys():
	if return_song_counter<=2:
		if track_details[track]['track_popularity']==pop_rate_1 or track_details[track]['track_popularity']==pop_rate_2:
			try:
				track_details[track]['return_song']=True
				return_song_counter+=1
			except UnicodeEncodeError:
				track_details.pop(track, None)
				pass
	## Remove all other songs from the dictionary
	if track_details[track]['return_song'] == False:
		track_details.pop(track)

###################
### Twitter API ###
###################

auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_KEY, ACCESS_SECRET)
api = tweepy.API(auth)

## Loop through all tweets @fTuneIntoNews has tweeted, store the status IDs as a list
statuses = []
for status in api.user_timeline():
    statuses.append(status.id)

## Create a variable to hold @TuneIntoNews most recent tweet's status ID
most_recent = statuses[0]

## Check for @ mentions since most recent status ID (aka the last time the bot tweeted)
if most_recent:
    mentions = api.mentions_timeline(since_id=most_recent)
else:
    mentions = ()
for mention in mentions:
    request = mention.text
    requester = mention.user.screen_name
    ## Mention must contain word "play"
    if "play" in request.lower():
    	## Find length of tweet without urls, set trim if tweet is longer than 140 char
    	tweet_wo_url=""".@{0}_"{1}"_url_pairs_well_with_url""".format(requester, story_title)
    	trim=140-23-23-len(tweet_wo_url)+3+3
    	ellipsis=""
    	if trim<0:
    		trim-=3
    		ellipsis="..."
    	else:
    		trim=len(story_title)
    		ellipsis=""
    	api.update_status(status=""".@{0} "{1}{2}" {3} pairs well with {4}""".format(requester, story_title[:trim].strip(), ellipsis, story_url, track_details.values()[0]['track_url']))
