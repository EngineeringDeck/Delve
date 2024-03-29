#!/usr/bin/env python3

import ahocorasick
import argparse
from datetime import datetime,timedelta
import json
import os
import requests
import urllib.parse
import webbrowser
import yaml

with open(os.environ['DELVE_OPTIONS_PATH'],'r') as input:
	options=yaml.load(input.read(),Loader=yaml.Loader)

arguments=argparse.ArgumentParser()
arguments.add_argument("-o","--output",help="Output file")
operation=arguments.add_mutually_exclusive_group(required=True)
operation.add_argument("-g","--group",default="default",help="Category group")
operation.add_argument("-t","--type",default=None,help="Type (genre) of game")
operation.add_argument("-f","--follows",action='store_true',help="Search followed channels rather than games")
operation.add_argument("-v","--variety",action='store_true',help="Search for variety streamers rather than games")
for attribute, value in vars(arguments.parse_args()).items():
	options[attribute]=value

blacklist=ahocorasick.Automaton()
for index,key in enumerate(options['tags']['filters']):
	blacklist.add_word(key,(index,key))
blacklist.make_automaton()

def blacklisted(tags):
	return len([match for match in blacklist.iter(" ".join(tags))]) > 0

def reject(name,reason):
	print("Rejecting: "+name+" ("+str(reason)+")")

def write(filename,data):
	with open(os.path.join(os.environ['DELVE_OUTPUT_PATH'],filename),'w') as output:
		output.write(data)

headers={
	"Authorization": "Bearer "+options['token'],
	"Client-Id": options['clientID'],
	"Accept": "application/json"
}

streams=[]
maxChunkSize=100
if options['follows']:
	channels=options['channels']
	for chunk in [channels[index:index+maxChunkSize] for index in range(0,len(channels),maxChunkSize)]:
		request=requests.get("https://api.twitch.tv/helix/streams?language=en&type=live&first="+str(maxChunkSize)+"&"+"&".join([f"user_login={entry}" for entry in chunk]),headers=headers)
		streamData=json.loads(request.text)
		streams.extend(streamData['data'])
elif options['variety']:
	thresholds=options['clips']
	cursor="*"
	startTime=datetime.now()
	while cursor and datetime.now() < startTime+timedelta(minutes=options['runtime']):
		request=requests.get("https://api.twitch.tv/helix/streams?language=en&type=live&first="+str(maxChunkSize)+("&after="+cursor if cursor != "*" and cursor != "" else ""),headers=headers)
		streamData=json.loads(request.text)
		chunk=streamData['data']
		ids={entry['user_id']: entry for entry in chunk}
		if len(ids) > 0:
			request=requests.get("https://api.twitch.tv/helix/users?"+"&".join([f"id={id}" for id in ids.keys()]),headers=headers)
			userData=json.loads(request.text)
			for entry in userData['data']:
				id=entry['id']
				if "variety" in entry['description'].lower():
					streams.append(ids[id])
				else:
					request=requests.get("https://api.twitch.tv/helix/clips?broadcaster_id="+id+"&first="+str(maxChunkSize),headers=headers)
					clipData=json.loads(request.text)
					games={clipID for clip in clipData['data'] if (creationDate:=datetime.fromisoformat(clip['created_at'])) > datetime.now(creationDate.tzinfo)-timedelta(days=thresholds['age']) if len(clipID:=clip['game_id']) > 0}
					if len(games) > thresholds['games']:
						streams.append(ids[id])
		if 'pagination' in streamData:
			if 'cursor' in streamData['pagination']:
				cursor=streamData['pagination']['cursor']
elif "type" in options and (genre:=options['type']) is not None:
	genre=genre.capitalize()
	chunkOffset=0
	request=requests.post("https://api.igdb.com/v4/genres",data=f"fields name; where name=\"{genre}\";",headers=headers)
	genreData=json.loads(request.text)
	genreID=genreData[0]['id']
	while (len(gameData:=json.loads(requests.post("https://api.igdb.com/v4/games",data=f"fields name; where genres=[{genreID}]; offset {chunkOffset}; limit {maxChunkSize};",headers=headers).text)) > 0):
		request=requests.get("https://api.twitch.tv/helix/games?"+"&".join([f"igdb_id={game['id']}" for game in gameData]),headers=headers)
		games=json.loads(request.text)['data']
		cursor="*"
		while cursor:
			request=requests.get("https://api.twitch.tv/helix/streams?language=en&type=live&first="+str(maxChunkSize)+("&after="+cursor+"&" if cursor != "*" and cursor != "" else "&")+"&".join({f"game_id={entry['id']}" for entry in games}),headers=headers)
			streamData=json.loads(request.text)
			streams.extend(streamData['data'])
			cursor=""
			if 'pagination' in streamData:
				if 'cursor' in streamData['pagination']:
					cursor=streamData['pagination']['cursor']
		chunkOffset+=maxChunkSize
else:
	games=options['categories'][options['group']]
	for chunk in [games[index:index+maxChunkSize] for index in range(0,len(games),maxChunkSize)]:
		request=requests.get("https://api.twitch.tv/helix/games?"+"&".join([f"name={urllib.parse.quote(name)}" for name in chunk]),headers=headers)
		gameData=json.loads(request.text)
		validGames=[]
		for game in gameData['data']:
			validGames.append(game['name'])
		for game in chunk:
			if not game in validGames:
				print("Game not found: "+game)
		cursor="*"
		while cursor:
			request=requests.get("https://api.twitch.tv/helix/streams?language=en&type=live&first="+str(maxChunkSize)+("&after="+cursor+"&" if cursor != "*" and cursor != "" else "&")+"&".join([f"game_id={entry['id']}" for entry in gameData['data']]),headers=headers)
			streamData=json.loads(request.text)
			streams.extend(streamData['data'])
			cursor=""
			if 'pagination' in streamData:
				if 'cursor' in streamData['pagination']:
					cursor=streamData['pagination']['cursor']

results=[]
weights={}
for entry in streams:
	streamer=entry['user_name']
	tags=entry['tags']
	if tags and "tags" in options and "filters" in options['tags']:
		if blacklisted([tag.lower() for tag in tags]):
			reject(streamer,", ".join(tags))
			continue
	viewers=int(entry['viewer_count']);
	if "viewers" in options and "min" in options['viewers'] and "max" in options['viewers']:
		if viewers < options['viewers']['min'] or viewers > options['viewers']['max']:
			reject(streamer,str(viewers)+" viewers")
			continue
	request=requests.get("https://api.twitch.tv/helix/chat/settings?broadcaster_id="+entry['user_id'],headers=headers)
	streamerData=json.loads(request.text)['data'][0]
	if (streamerData['follower_mode']):
		reject(streamer,"Follower-Only Chat")
		continue
	if (streamerData['subscriber_mode']):
		reject(streamer,"Subscriber-Only Chat")
		continue
	name=entry['game_name']
	results.append({
		"streamer": streamer,
		"title": entry['title'],
		"viewers": viewers,
		"game": name,
		"tags": tags if tags else [],
		"thumbnail": entry['thumbnail_url'].format(width=440,height=248)
	})
	if name in weights:
		weights[name]+=1
	else:
		weights[name]=1

output="var streams="+json.dumps(sorted(results,key=lambda value:(weights[value['game']],value['viewers'])))+";"
path=options['output']
if path is not None:
	write(path,output)
else:
	write("streams.js",output)
	webbrowser.open("streams.html")

