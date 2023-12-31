#!/usr/bin/env python3

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
arguments.add_argument("-g","--group",default="default",help="Category group")
arguments.add_argument("-o","--output",help="Output file")
arguments.add_argument("-f","--follows",action='store_true',help="Search followed channels rather than games")
arguments.add_argument("-v","--variety",action='store_true',help="Search for variety streamers rather than games")
for attribute, value in vars(arguments.parse_args()).items():
	options[attribute]=value

def blacklisted(tags):
	for word in options['tags']['filters']:
		for tag in tags:
			if word in tag:
				return True
	return False

def reject(name,reason):
	print("Rejecting: "+name+" ("+str(reason)+")")

def write(filename,data):
	with open(os.path.join(os.environ['DELVE_OUTPUT_PATH'],filename),'w') as output:
		output.write(data)

headers={
	"Authorization": "Bearer "+options['token'],
	"Client-Id": options['clientID']
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
		while (cursor):
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
if 'output' in options:
	write(options['output'],output)
else:
	write("streams.js",output)
	webbrowser.open("streams.html")

