from spotdl.download import DownloadManager
from spotdl.parsers import parse_query
from spotdl.search import SpotifyClient, SongObject, from_spotify_url
from spotdl.providers import metadata_provider
from spotdl.utils.song_name_utils import format_name

import sqlite3
import os
import shutil

# Initialize spotify client id & secret is provided by spotdl no need to keep secret
SpotifyClient.init(
    client_id="5f573c9620494bae87890c0f08a60293",
    client_secret="212476d9b0f3472eaa762d90b19b0ba8",
    user_auth=False,
)

def search_query(query: str):
    """
    THIS FUNCTION TAKES search query AS INPUT AND RETURN
    a `list<SongObject>`.
    """ 
    songs = [] # This list contains searchSongObject for each song
    list_song_urls = []
    # get a spotify client
    spotify_client = SpotifyClient()

    # Use spotify search
    search_results = spotify_client.search(query, type="track")

    number_of_search_results = len(search_results.get("tracks", {}).get("items", []))

    # return first result link or if no matches are found, raise Exception
    if search_results is None or number_of_search_results == 0:
        raise Exception("No song matches found on Spotify")

    # Adds each song url to list_song_urls
    for i in range(0, number_of_search_results):
        # Get the Song Metadata
        song_url = "http://open.spotify.com/track/" + search_results["tracks"]["items"][i]["id"]
        raw_track_meta, raw_artist_meta, raw_album_meta = metadata_provider.from_url(song_url)

        # for searchSongObject
        song_name = search_results["tracks"]["items"][i]["name"]
        cover_url = search_results["tracks"]["items"][i]["album"]["images"][0]["url"]
        contributing_artists = [artist["name"] for artist in raw_track_meta["artists"]]   
        duration = search_results["tracks"]["items"][i]["duration_ms"] / 1000 # convert to seconds

        list_song_urls.append(song_url)
        # create SongObject and append to songs[]
        song = searchSongObject(song_url, contributing_artists, song_name, duration, cover_url)
        songs.append(song)

    return songs

# This is to display in /search because creating SongObject would mean you have to use youtube API, which takes too long
class searchSongObject:
    def __init__(self,
        spotify_url: str,
        contributing_artists: list,
        song_name: str,
        duration: float, 
        album_cover_url: str) -> None:

        self._spotify_url = spotify_url
        self._contributing_artists = contributing_artists
        self._song_name = song_name
        self._duration = duration
        self._album_cover_url = album_cover_url
    
    @property
    def spotify_url(self):
        return self._spotify_url
    
    @property
    def contributing_artists(self):
        return self._contributing_artists
    
    @property
    def song_name(self):
        return self._song_name
    
    @property
    def duration(self):
        return self._duration
    
    @property
    def album_cover_url(self):
        return self._album_cover_url

    @property
    def file_name(self):
        return self.create_file_name(self._song_name, self._contributing_artists)

    @staticmethod
    def create_file_name(song_name: str, song_artists: list[str]) -> str:
        # build file name of converted file
        # the main artist is always included
        artist_string = song_artists[0]

        # ! we eliminate contributing artist names that are also in the song name, else we
        # ! would end up with things like 'Jetta, Mastubs - I'd love to change the world
        # ! (Mastubs REMIX).mp3' which is kinda an odd file name.
        for artist in song_artists[1:]:
            if artist.lower() not in song_name.lower():
                artist_string += ", " + artist

        converted_file_name = artist_string + " - " + song_name

        return format_name(converted_file_name)

class ManageDownloads:
    """
        Download songs as .oggs files by using Spotify search API on title and artist
        name in track_metadata.db & spotdl and saves it in a folder
    """
    def __init__(self):
        # track_metadata.db has one table called songs
        # Establish connection and init cursor to database    
        self.connection = sqlite3.connect("track_metadata.db")
        self.cursor = self.connection.cursor()
        print("Successfully connected to db\n")
    def download_songs_using_track_metadata_db(self):
        ret = []
        self.cursor.execute("SELECT title, artist_name FROM songs LIMIT 20")
        data = self.cursor.fetchall()

        if os.path.isdir("./songs"):
            pass
        else:
            os.makedirs("./songs")

        for row in range(len(data)):
            # data[row][0] = title # of song
            # data[row][1] = artist_name # of song
            if data[row][0] == '' or data[row][1] == '':
                continue
            # title, artist_name
            search_param = f"{data[row][0]}, {data[row][1]}"
            print(f"Searching '{search_param}' using Spotify search API...")
            spotify_url = ""
            try:            
                spotify_url = search_query(search_param)[0].spotify_url
            except:
                print(f"failed to find match on Spotify\n")
                continue

            print(f"{spotify_url}\n")
            spotdl_opts = {
                "query": [spotify_url],
                "output_format": "ogg",
                "download_threads": 1,                  
                "path_template": None,
                "use_youtube": False,
                "generate_m3u": False,
                "search_threads": 1, 
            }
            # song_obj is a SongObject from spotdl.search.SongObject
            song_obj = parse_query(
                spotdl_opts["query"],
                spotdl_opts["output_format"],
                spotdl_opts["download_threads"],
                spotdl_opts["path_template"],
                spotdl_opts["use_youtube"],
                spotdl_opts["generate_m3u"],
                spotdl_opts["search_threads"],
            )
            if os.path.isfile(f"./{song_obj[0].file_name}.ogg") or os.path.isfile(f"./songs/{song_obj[0].file_name}.ogg"):
                # change download status by changing downloaded column in db
                self.cursor.execute("UPDATE songs SET downloaded=? WHERE title=? AND artist_name=?", [1, data[row][0], data[row][1]])
                self.connection.commit()
                # if file name already exists skip download
                print(f"{song_obj[0].file_name}.ogg already downloaded")
                continue    
            try:
                DownloadManager(spotdl_opts).download_single_song(song_obj[0])
                # Move to ./songs directory)
                shutil.move(f"{song_obj[0].file_name}.ogg", './songs/')
                # change download status by changing downloaded column in db
                self.cursor.execute("UPDATE songs SET downloaded=? WHERE title=? AND artist_name=?", [1, data[row][0], data[row][1]])
                self.connection.commit()
            except OSError:
                continue
            
        #print(bytes(data[17][0], 'utf-8').decode('unicode_escape'))
            
def main():
    data = ManageDownloads()
    data.download_songs_using_track_metadata_db()

if __name__ == '__main__':
    main()



