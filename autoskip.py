"""
This script looks at a user's currently playing song and checks if
it is in a playlist called "Dislikes". If so it skips to the next song

if you want to use this, you need to create an app in Spotify's developer dashboard, and set the redirectUrl to: http://127.0.0.1:8888
replace 'clientID' on line 25 and 'YOUR_CLIENT_ID_HERE' on line 9 with your client id and set your client secret as an environment variable named:  SPOTIFY_CLIENT_SECRET

On the first run, you need to goto: ⬇
https://accounts.spotify.com/en/authorize?client_id=YOUR_CLIENT_ID_HERE&response_type=code&redirect_uri=http://127.0.0.1:8888&scope=user-read-private%20user-read-currently-playing%20user-modify-playback-state%20user-read-email%20playlist-read-private%20playlist-read-collaborative
and after authorizing the app, copy the code that comes after the 'code='  in the url you were redirected to.
set 'userCode' on line 49 to this code. This should be a one time stepup,  after  the file 'spotify_refresh.txt' in '~/Scripts/' has been automatically created, the next time you run this script it will use the code in the file
"""

import requests

import asyncio
import threading
import time
import base64
import json
import os

activeToken = ""
refreshToken = ""
clientID = "732ea1b7d28d4e19a44233e44df2fdb2"
clientSecret = os.getenv('SPOTIFY_CLIENT_SECRET',None)
dislikedPlaylistId=""
currentlyPlaying = (None,None)
file_path = "~/Scripts/spotify_refresh.txt"
last_error_type = ""

if clientSecret is None:
    print("Error: SPOTIFY_CLIENT_SECRET environment variable must be set.")
    exit(-3)

#This function runs async and periodically updates the global activeToken
async def getCode():
    global activeToken
    global refreshToken
    url = "https://accounts.spotify.com/api/token"
    authString = clientID + ":" + clientSecret
    b64_auth_string = base64.b64encode(authString.encode()).decode()

    #tries to read refreshToken from a file. If it is found then uses that, if not it generates one(need manual userCode), and saves to file
    #this will only be run if there is no spotify_refresh.txt file.
    if not getRefreshTokenFromFile():
        # To get this,  goto:  https://accounts.spotify.com/en/authorize?client_id=732ea1b7d28d4e19a44233e44df2fdb2&response_type=code&redirect_uri=http://127.0.0.1:8888&scope=user-read-private%20user-read-currently-playing%20user-modify-playback-state%20user-read-email%20playlist-read-private%20playlist-read-collaborative
        # and copy the 'code='  in the url once redirected
        userCode = "FILL_CODE_HERE"

        payload = {
            "grant_type": "authorization_code",
            "code": userCode,
            "redirect_uri": "http://127.0.0.1:8888",
            "client_id": clientID,
            "client_secret": clientSecret
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        response = requests.post(url, data=payload, headers=headers)
        if response.status_code == 200:
            activeToken = response.json()["access_token"]
            refreshToken = response.json()["refresh_token"]
            with open(os.path.expanduser(file_path), "w") as f:
                f.write(refreshToken)
            #print("Initial user access token: " + activeToken)
            #print("Initial user refresh token: " + refreshToken)
        else:
            print("unable to get initial access token, exiting")
            print(response)
            await asyncio.sleep(10)
            exit(-1)

    while True:
        #uses the refresh token to get a new user access token without manual interaction
        #print("Refreshing token")
        refresh_payload = {
            "grant_type": "refresh_token",
            "refresh_token":  refreshToken,
            "client_id": clientID,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic " + b64_auth_string
        }
        try:
            refresh_response = requests.post(url, data=refresh_payload, headers=headers)
            data = json.loads(refresh_response.text.strip())
            activeToken = data["access_token"]
            #print("New access token: " + activeToken)
            print("Refreshed access token")
        except (TypeError, KeyError) as e:
            print("Error: Scope: getCode: refresh-token: " + e)
            exit(-4)
        await asyncio.sleep(3590)

#finds the 'Disliked' playlist id and sets a global variable
def findDislikedPlaylist():
    global dislikedPlaylistId
    ##Gets current user's id
    url = "https://api.spotify.com/v1/me"
    headers = {
        "Authorization": "Bearer " + activeToken
    }
    user_data_unformatted = requests.get(url=url, headers=headers)
    user_data = json.loads(user_data_unformatted.text.strip())
    user_id = user_data["id"]
    ##Gets user playlist from user_id
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    headers = {
        "Authorization": "Bearer " + activeToken,
        "limit": "50",
        "offset": "0"
    }
    playlists_unformatted = requests.get(url=url, headers=headers)
    playlists = json.loads(playlists_unformatted.text.strip())["items"]
    for playlist in playlists:
        if playlist["name"] == "Disliked":
            dislikedPlaylistId = playlist["id"]
            print("'Disliked' playlist id is: " + dislikedPlaylistId)
            return
    print("User has no 'Disliked' playlist, exiting.")
    exit(-2)

#sends a get request to get the currently playing song,
#and filters for the artist and song in a tuple
def getCurrentlyPlaying():
    global last_error_type

    url = "https://api.spotify.com/v1/me/player/currently-playing"
    headers = {
        "Authorization": "Bearer " + activeToken,
    }
    currently_playing_unformatted_fetch = requests.get(url=url, headers=headers)
    if currently_playing_unformatted_fetch.text == "":
        return None
    try:
        currently_playing_unformatted = json.loads(currently_playing_unformatted_fetch.text.strip())["item"]
        artist = currently_playing_unformatted["album"]["artists"][0]["name"]
        song_name = currently_playing_unformatted["name"]
    except (TypeError, KeyError) as e:
        if last_error_type is  not type(e):
            print("Error: Scope: getCurrentlyPlaying - One of the JSON keys is not valid, mostly happens when DJ talks")
            last_error_type = type(e)
        return None
    last_error_type = ""
    return artist,song_name

#sends a post request to skip the currently playing song
def skipSong():
    url = "https://api.spotify.com/v1/me/player/next"
    headers = {
        "Authorization": "Bearer " + activeToken
    }
    requests.post(url=url, headers=headers)
    print("Skipped a song")

#creates a list of (artist, song) tuples from the "Dislikes" playlist
#and checks if the currently playing song is in said list. If so, skips
def checkSong():
    global currentlyPlaying
    playing = getCurrentlyPlaying()
    if playing is None:
        if currentlyPlaying is not None:
            currentlyPlaying = None
            print("Nothing is playing.")
        return
    if currentlyPlaying == playing: #if the current song is the same as the last one checked
        return
    currentlyPlaying = playing
    print("Playing: " + playing[1] + " by " + playing[0])

    ##check "Dislikes" playlist to see if current song is in it, if so, skip
    url = f"https://api.spotify.com/v1/playlists/{dislikedPlaylistId}/tracks"
    headers = {
        "Authorization": "Bearer " + activeToken,
    }
    playlist_songs_unformatted_fetch = requests.get(url=url, headers=headers)
    playlist_songs_unformatted = json.loads(playlist_songs_unformatted_fetch.text.strip())["items"]
    artist_song_list = []
    for song_metadata in playlist_songs_unformatted:
        artist = song_metadata["track"]["album"]["artists"][0]["name"]
        song = song_metadata["track"] ["name"]
        artist_song_list.append((artist,song))
    if playing in artist_song_list:
        skipSong()

#init thread to keep access token up to date in the background
def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()
loop = asyncio.new_event_loop()
threading.Thread(target=start_background_loop, args=(loop,), daemon=True).start()

def getRefreshTokenFromFile():
    global refreshToken

    if not os.path.exists(os.path.expanduser(file_path)) or os.stat(os.path.expanduser(file_path)).st_size == 0:
        print("Spotify refresh token file is missing or empty!")
        return False
    with open(os.path.expanduser(file_path)) as f:
        refreshToken= f.read().strip()
        print("Reading refresh token from file: " + os.path.expanduser(file_path))
        return True

asyncio.run_coroutine_threadsafe(getCode(), loop)
#

if __name__ == '__main__':
    time.sleep(3)
    findDislikedPlaylist()
    while True:
        time.sleep(1)
        checkSong()
