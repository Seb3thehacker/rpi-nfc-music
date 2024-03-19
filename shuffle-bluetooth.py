import time
import json
import vlc
import os
import board
import busio
from adafruit_pn532.i2c import PN532_I2C
import logging
import threading
import random
import RPi.GPIO as GPIO  # Import the GPIO library

last_scanned_tag = None
consecutive_scans = 0
scan_delay = 2  # Delay in seconds after a tag is scanned

# Load configuration
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

audio_folder = config['global_config']['audio_folder']

# Logging
logging.basicConfig(filename='app.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

logging.info('Program started')

# Create a VLC instance with ALSA audio output
vlc_instance = vlc.Instance('--aout=alsa')

# Use this instance to create the media player
player = vlc_instance.media_list_player_new()

# Initialize NFC reader
i2c = busio.I2C(board.SCL, board.SDA)
pn532 = PN532_I2C(i2c, debug=False)
pn532.SAM_configuration()

# Set up GPIO pin for the physical switch
switch_pin = 22  # Change this to the GPIO pin you are using
GPIO.setmode(GPIO.BCM)
GPIO.setup(switch_pin, GPIO.IN)

# Bluetooth control functions
def turn_on_bluetooth():
    os.system("bluetoothctl power on")

def turn_off_bluetooth():
    os.system("bluetoothctl power off")

def check_switch_state():
    return GPIO.input(switch_pin)  # Returns 1 if the switch is ON, 0 if OFF

def play_all_songs_randomly():
    try:
        media_list = vlc_instance.media_list_new()
        songs = sorted(os.listdir(audio_folder))
        random.shuffle(songs)
        for song in songs:
            if song.endswith('.flac'):
                media_list.add_media(vlc_instance.media_new(os.path.join(audio_folder, song)))
        player.set_media_list(media_list)
        player.play()
        logging.info(f"Started playing all songs randomly")
    except Exception as e:
        logging.error(f'Error playing all songs randomly: {e}')

def play_album(folder, shuffle=False):
    try:
        media_list = vlc_instance.media_list_new()
        album_path = os.path.join(audio_folder, folder)
        songs = sorted(os.listdir(album_path))
        if shuffle:
            random.shuffle(songs)
        for song in songs:
            if song.endswith('.flac'):
                media_list.add_media(vlc_instance.media_new(os.path.join(album_path, song)))
        player.set_media_list(media_list)
        player.play()
        logging.info(f"Started playing album: {folder} {'shuffled' if shuffle else 'in order'}")
    except Exception as e:
        logging.error(f'Error playing album {folder}: {e}')

def handle_new_tag(tag_data):
    global last_scanned_tag, consecutive_scans
    shuffle = False

    if tag_data == last_scanned_tag:
        consecutive_scans += 1
        if consecutive_scans == 2:
            shuffle = True
        else:
            consecutive_scans = 1
    else:
        play_all_songs_randomly()

    if player.is_playing():
        player.stop()

    if tag_data in config['tags']:
        play_album(config['tags'][tag_data]['folder'], shuffle)
    else:
        play_all_songs_randomly()

    last_scanned_tag = tag_data  # Update the last scanned tag
    time.sleep(scan_delay)  # Delay to prevent immediate re-scanning

def scan_tag():
    try:
        uid = pn532.read_passive_target(timeout=0.5)
        if uid is not None:
            data_read = pn532.ntag2xx_read_block(4)
            tag_data = data_read.decode('utf-8').strip()
            tag_data = tag_data.replace('\x00', '').strip()
            logging.info(f'Tag scanned: {tag_data}')
            return tag_data
        else:
            logging.debug('No tag found')
    except Exception as e:
        logging.error(f'Error reading tag: {e}')
    return None

def tag_scanning_loop():
    while True:
        tag_data = scan_tag()
        if tag_data:
            handle_new_tag(tag_data)
        time.sleep(0.1)

# Start the tag scanning in a separate thread
tag_scanning_thread = threading.Thread(target=tag_scanning_loop)
tag_scanning_thread.daemon = True
tag_scanning_thread.start()

try:
    while True:
        time.sleep(1)

        # Check if the player has finished playing the current item
        if not player.is_playing() and last_scanned_tag is not None:
            play_all_songs_randomly()  # Play all songs randomly after an album is done

        # Check switch state and control Bluetooth accordingly
        switch_state = check_switch_state()
        if switch_state:
            turn_on_bluetooth()
        else:
            turn_off_bluetooth()

except KeyboardInterrupt:
    print("Program terminated by user")
finally:
    i2c.deinit()
    GPIO.cleanup()  # Clean up GPIO resources
