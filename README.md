This script looks at a user's currently playing song and checks if
it is in a playlist called "Dislikes". If so it skips to the next song

if you want to use this, you need to create an app in Spotify's developer dashboard, and set the redirectUrl to: http://127.0.0.1:8888
replace 'clientID' on line 25 and 'YOUR_CLIENT_ID_HERE' on line 9 with your client id and set your client secret as an environment variable named:  SPOTIFY_CLIENT_SECRET

On the first run, you need to goto: ⬇
https://accounts.spotify.com/en/authorize?client_id=YOUR_CLIENT_ID_HERE&response_type=code&redirect_uri=http://127.0.0.1:8888&scope=user-read-private%20user-read-currently-playing%20user-modify-playback-state%20user-read-email%20playlist-read-private%20playlist-read-collaborative
and after authorizing the app, copy the code that comes after the 'code='  in the url you were redirected to.
set 'userCode' on line 49 to this code. This should be a one time stepup,  after  the file 'spotify_refresh.txt' in '~/Scripts/' has been automatically created, the next time you run this script it will use the code in the file
