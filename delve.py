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
for attribute, value in vars(arguments.parse_args()).items():
	options[attribute]=value

def blacklisted(tags):
	for word in options['tags']['filters']:
		for tag in tags:
			if word in tag:
				return True
	return False

games=options['categories'][options['group']]

headers={
	"Authorization": "Bearer "+options['token'],
	"Client-Id": options['clientID']
}

streams=[]
for chunk in games:
	request=requests.get("https://api.twitch.tv/helix/games?"+"&".join([f"name={urllib.parse.quote(name)}" for name in chunk]), headers=headers)
	gameData=json.loads(request.text)
	validGames=[]
	for game in gameData['data']:
		validGames.append(game['name']);
	for game in chunk:
		if not game in validGames:
			print("Game not found: "+game);

	cursor="*"
	while (cursor):
		request=requests.get("https://api.twitch.tv/helix/streams?language=en&type=live&first=100"+("&after="+cursor+"&" if cursor != "*" and cursor != "" else "&")+"&".join([f"game_id={entry['id']}" for entry in gameData['data']]), headers=headers)
		streamData=json.loads(request.text)
		streams.extend(streamData['data'])
		cursor=""
		if 'pagination' in streamData:
			if 'cursor' in streamData['pagination']:
				cursor=streamData['pagination']['cursor']

results=[]
weights={}
for entry in streams:
	tags=entry['tags'];
	if tags and "tags" in options and "filters" in options['tags']:
		if blacklisted([tag.lower() for tag in tags]):
			continue
	viewers=int(entry['viewer_count']);
	if "viewers" in options and "min" in options['viewers'] and "max" in options['viewers']:
		if viewers < options['viewers']['min'] or viewers > options['viewers']['max']:
			continue;
	name=entry['game_name']
	results.append({
		"streamer": entry['user_name'],
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

with open("streams.js",'w') as output:
	output.write("var streams="+json.dumps(sorted(results,key=lambda value:(weights[value['game']],value['viewers'])))+";")

webbrowser.open("streams.html");
