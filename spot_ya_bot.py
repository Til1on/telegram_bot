#!/usr/bin/env python3

import logging
import re
import requests
from bs4 import BeautifulSoup
import telebot
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# instantiate logging to log-file and console
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler('spot_ya_bot_log.log'),  # write to log-file
                        logging.StreamHandler()  # log to console
                    ])

logger = logging.getLogger(__name__)

# Spotify API credentials to app 'links_to_spotify_ya_music'
SPOTIFY_CLIENT_ID = 'xxxxxxxxxxxxxxxxxxxxx'
SPOTIFY_CLIENT_SECRET = 'xxxxxxxxxxxxxxxxxxxxxxxxxx'

# Spotify API
sp = spotipy.Spotify(
    client_credentials_manager = SpotifyClientCredentials(
        client_id = SPOTIFY_CLIENT_ID, client_secret = SPOTIFY_CLIENT_SECRET)
        )

# Telegram bot 'spot_ya_bot' token
bot = telebot.TeleBot('xxxxxxxxxxxxxxxxxxxxxxxxxxx')

# Using bs4 module on Yandex Music to find song/album by their titles and return hyperlink
def find_on_yandex_music(query):
    search_url = f'https://music.yandex.ru/search?text={query.replace(' ', '+')}'
    response = requests.get(search_url)
    soup = BeautifulSoup(response.content, 'html.parser') # using bs4 module to scrape yandex search page using html-parser

    # Using BeautifulSoup find_all method to find all links
    track_link = None
    for link in soup.find_all('a', href=True): # serch all <a> anchor tags, which has `href` attribute = hyperlinks
        if '/track/' in link['href'] or '/album/' in link['href']: # link['href'] = URL or path that the hyperlink points to
            track_link = f'https://music.yandex.ru{link['href']}' # construct full link to track or album
            break

    return track_link if track_link else "нет этого дерьма на яндекс музике"

# Function to extract track|album and artist name details from link to Yandex Music
def extract_yandex_music_details(url):
    # instantiate regex pattern. tag <meta property='og:description'> = artist variable contains:
    # artist name (central) dot word `Трек` (central) dot and year of the song
    # using regex pattern to get rid of dots, `Трек`|`Альбом`|`Сингл` and year
    pattern_track = r'[^Трек^0-9•]+' # regular expression for track name
    pattern_album = r'[^Альбом^Сингл^0-9•]+' # regular expression for album name
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract track|album title and artist name
    track = 'track'
    album = 'album'
    if '/track/' in soup.find('meta', {'property': 'og:url', 'content': True})['content']:
        try:
            title_track = soup.find('meta', property='og:title')['content']
            artist_year = soup.find('meta', property='og:description')['content']
            artist = re.findall(pattern_track, artist_year)[0].strip() # using regex to get rid of useless info
            return track, title_track, artist
        except (TypeError, KeyError) as e:
            logger.error(f'Failed to extract Yandex Music details (title_track or artist) from link: {e}')
            return f'Failed to extract Yandex Music details (title_track or artist) from link: {url}'
    elif '/album/' in soup.find('meta', {'property': 'og:url', 'content': True})['content']:
        try:
            title_album = soup.find('meta', property='og:title')['content']
            artist_year = soup.find('meta', property='og:description')['content']
            artist = re.findall(pattern_album, artist_year)[0].strip() # using regex to get rid of useless info
            return album, title_album, artist
        except (TypeError, KeyError) as e:
            logger.error(f'Failed to extract Yandex Music details (title_album or artist) from link: {e}')
            return f'Failed to extract Yandex Music details (title_album or artist) from link: {url}'

# Using Spotify API to find exact match for song/album and artist titles and return hyperlink
def find_on_spotify(track_album_indication, query_title, query_artist):
    # Check for `track_album_indication` that points out to tack or album
    if track_album_indication == 'track':
        try:
            # Search Spotify for track
            result = sp.search(f"{query_artist} {query_title}", type='track', limit=10)

            # Check tracks
            for track in result['tracks']['items']:
                track_name = track['name'].lower()
                track_artists = [artist['name'].lower() for artist in track['artists']]

                # Check if both the track name and artist name match exactly (ignoring case)
                if query_title.lower() == track_name and query_artist.lower() in ", ".join(track_artists): #unpacking list of artist to a string for proper comparison
                    return f'https://open.spotify.com/track/{track['id']}'
            
            # If no exact match is found, return a not found message
            return f'Exact match for song: `{query_title}` and artist: `{query_artist}` not found on Spotify'

        except Exception as e:
            logger.error(f'Error searching Spotify: {e}')
            return 'Error searching Spotify'

    elif track_album_indication == 'album':
        try:
            # Search Spotify for album
            result = sp.search(f'{query_artist} {query_title}', type='album', limit=10)
            # Check albums
            for album in result['albums']['items']:
                album_name = album['name'].lower()
                album_artists = [artist['name'].lower() for artist in album['artists']]

                # Check if both the album name and artist name match exactly (ignoring case)
                if query_title.lower() == album_name and query_artist.lower() in album_artists:
                    return f'https://open.spotify.com/album/{album['id']}'

            # If no exact match is found, return a not found message
            return f'Exact match for album: `{query_title}` and artist: `{query_artist}` not found on Spotify'

        except Exception as e:
            logger.error(f'Error searching Spotify: {e}')
            return 'Error searching Spotify'
    else:
        logger.error(f'Error searching Spotify: bad query')
        return 'Error searching Spotify: bad query'

# Command to start the bot
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 'хеллоу, ссылки на музыку направляешь - ссылки получаешь')

# Function to handle messages and check for Spotify or Yandex links
@bot.message_handler(func=lambda message: True)
def handle_message(message):
        text = message.text
        
        # Check if the message contains a Spotify link
        spotify_match = re.search(r'https://open.spotify.com/(track|album)/([a-zA-Z0-9]+)', text)
        if spotify_match:
            link_type = spotify_match.group(1)  # track or album
            spotify_id = spotify_match.group(2)  # the track or album ID

            # Get track or album info from Spotify
            if link_type == 'track':
                track_info = sp.track(spotify_id)
                track_name = track_info['name']
                artist_name = track_info['artists'][0]['name']
                query = f'{artist_name} {track_name}'
                yandex_link = find_on_yandex_music(query)
                bot.reply_to(message, f'яндекс музик link: {yandex_link}')

            elif link_type == 'album':
                album_info = sp.album(spotify_id)
                album_name = album_info['name']
                artist_name = album_info['artists'][0]['name']
                query = f"{artist_name} {album_name}"
                yandex_link = find_on_yandex_music(query)
                bot.reply_to(message, f'яндекс музик link: {yandex_link}')

        # Check if the message contains a Yandex Music link
        #yandex_match = re.search(r'https://music.yandex.(ru|com)/album/([a-zA-Z0-9/]+)', text)
        yandex_match = re.search(r'(https:\/\/music\.yandex)', text)
        if yandex_match:
            #yandex_url = yandex_match.group(0)
            try:
                # Extract the song/album details from Yandex Music
                track_album_indication, title, artist = extract_yandex_music_details(text)
                if title and artist:
                    #query = f"{artist} {title}"
                    spotify_link = find_on_spotify(track_album_indication, title, artist)
                    bot.reply_to(message, f'спотифу link: {spotify_link}')
                else:
                    bot.reply_to(message, 'Failed to retrieve Yandex Music details.')
            except Exception as e:
                logger.error(f'Error extracting Yandex music details: {e}')
                return 'Error extracting Yandex music details'
# Polling to keep the bot running and listening for messages
bot.polling()