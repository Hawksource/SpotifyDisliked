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

from datetime import datetime

from requests import JSONDecodeError
from urllib3.exceptions import NameResolutionError

activeToken = ""
refreshToken = ""
clientID = "732ea1b7d28d4e19a44233e44df2fdb2"
clientSecret = os.getenv('SPOTIFY_CLIENT_SECRET',None)
dislikedPlaylistId=""
currentlyPlaying = (None,None)
file_path = "~/Scripts/spotify_refresh.txt"
error_file_path = "~/Scripts/spotify_error_logs.txt"
last_error_type = ""

if clientSecret is None:
    print("Error: SPOTIFY_CLIENT_SECRET environment variable must be set.")
    exit(-3)


def apiCall(url, headers=None, payload=None, method="GET", first_filter="items"):
    request_response = None
    global last_error_type
    try:
        if method.upper() == "GET":
            request_response = requests.get(url=url, headers=headers, data=payload)
        elif method.upper() == "POST":
            request_response = requests.post(url=url, headers=headers, data=payload)
        else:
            print(f"Error: Scope: apiCall - Illegal method: '{method}'")
            return "_error"
    except (ConnectionError, ConnectionResetError, NameResolutionError) as e:
        if last_error_type is not type(e):
            last_error_type = type(e)
            print("Error: Connection Error: You are most likely disconnected from the internet")
            return "_error"
    except Exception as e:
        if last_error_type is not type(e):
            last_error_type = type(e)
            if type(e) is requests.exceptions.ConnectionError:
                print("Error: Connection Error: You are most likely disconnected from the internet")
            else:
                print(f"There was an unexpected error, it has been logged at: {error_file_path}")
                with open(os.path.expanduser(error_file_path), "a") as f:
                    f.write(f"{datetime.now()}  ::  {type(e)}  ::  {str(e)}\n\n")
        return "_error"
    if request_response.status_code != 200:
        if last_error_type != "non200":
            print(f"Error: request did not return 200 to {url}")
            last_error_type = "non200"
        return "_error"
    if first_filter == "_nodata":
        return "_nodata"
    if first_filter is None:
        return json.loads(request_response.text.strip())
    try:
        unformatted = json.loads(request_response.text.strip())[first_filter]
    except (KeyError, JSONDecodeError, TypeError) as e:
        if last_error_type is not type(e):
            print("Error: Scope: apiCall json filter- One of the JSON keys is not valid, mostly happens when DJ talks")
            last_error_type = type(e)
        return "_error"
    except Exception as e:
        print(f"There was an unexpected error, it has been logged at: {error_file_path}")
        if last_error_type is not type(e):
            last_error_type = type(e)
            with open(os.path.expanduser(error_file_path), "a") as f:
                f.write(f"{datetime.now()}  ::  {str(e)}")
        return "_error"
    return unformatted


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

        response = apiCall(url=url,headers=headers,payload=payload,method="POST",first_filter=None)
        if response.status_code == 200:
            activeToken = response.json()["access_token"]
            refreshToken = response.json()["refresh_token"]
            with open(os.path.expanduser(file_path), "w") as f:
                f.write(refreshToken)
        else:
            print("Error: unable to get initial access token, exiting")
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
        data = apiCall(url=url,headers=headers,payload=refresh_payload,method="POST",first_filter="access_token")
        if data == "_error": #recall get code if failed
            getCode()
        else:
            activeToken = data
            print("Refreshed access token")
            await asyncio.sleep(3590)

#finds the 'Disliked' playlist id and sets a global variable
def findDislikedPlaylist():
    global dislikedPlaylistId
    ##Gets current user's id
    url = "https://api.spotify.com/v1/me"
    headers = {
        "Authorization": "Bearer " + activeToken
    }
    user_id = apiCall(url=url, headers=headers,method="GET",first_filter="id")
    if user_id == "_error":
        exit(-5)
    ##Gets user playlist from user_id
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    headers = {
        "Authorization": "Bearer " + activeToken,
        "limit": "50",
        "offset": "0"
    }
    playlists = apiCall(url=url,headers=headers,method="GET")
    if playlists == "_error":
        exit(-6)
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

    currently_playing_unformatted_fetch = apiCall(url=url,headers=headers,method="GET",first_filter=None)
    if currently_playing_unformatted_fetch == "_error" or currently_playing_unformatted_fetch["is_playing"] == False or currently_playing_unformatted_fetch == "":
        return None
    try:
        currently_playing_unformatted = currently_playing_unformatted_fetch["item"]
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
    apiCall(url=url,headers=headers,method="POST",first_filter="_nodata")
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
    playlist_songs_unformatted = apiCall(url=url,headers=headers,method="GET")
    if playlist_songs_unformatted == "_error":
        exit(-7)
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
        time.sleep(.5)
        checkSong()
