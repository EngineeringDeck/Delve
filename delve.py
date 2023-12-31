#!/usr/bin/env python3

import argparse
import json
import requests
import urllib.parse
import webbrowser
import yaml

with open("delve.yaml",'r') as input:
	options=yaml.load(input.read(),Loader=yaml.Loader)

arguments=argparse.ArgumentParser()
arguments.add_argument("-g","--group",default="default",help="Category group")
arguments.add_argument("-o","--output",help="Output file")
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
	with open(filename,'w') as output:
		output.write(data)

games=options['categories'][options['group']]

headers={
	"Authorization": "Bearer "+options['token'],
	"Client-Id": options['clientID']
}

streams=[]
maxChunkSize=100
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

