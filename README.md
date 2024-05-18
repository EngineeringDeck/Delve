# About

## What?

[Delve](http://rewire.hlmjr.com/delve.html) is a tool for finding streamers in a list of Twitch categories and listing them in a single, easy to see interface.

## Why?

I wrote Delve mainly as a tool for finding new people to raid. It compensates for Twitch's shortcomings in its followed channels listing, which has an upper limit and will not show all channels you follow. Twitch also provides no grouping and filtering options.

# Usage

## Getting Started

### Registration w/Twitch

Create a [developer account with Twitch](https://dev.twitch.tv/console) and create an app in your developer console. You will need the client ID from this page and will need to [generate an OAuth token using the implicit flow](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/).

### Settings

Open `delve.yaml` and fill out the necessary fields (and/or remove unnecessary ones). The most important fields are your authorization information and default list of categories you want to find streamers in. The YAML file is commented to help you find and understand these fields.

### Dependencies

Install the following Python dependencies:
- requests
- PyYAML

## Running

From a directory containing `delve.yaml` and `streams.html`, execute the following:

```
./delve.py
```

You can specify one of the groups in the `delve.yaml` file using the `--groups` or `-g` switch, for example:

```
./delve.py -g dev
```

When the script is finished running, it will create `streams.js` with the results in JSON format and open the results in `streams.html` in your default web browser.
