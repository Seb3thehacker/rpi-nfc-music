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

# GPIO setup
switch_pin = 17  # GPIO 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(switch_pin, GPIO.IN)

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

# Function to turn Bluetooth on/off
def toggle_bluetooth(is_on):
    bluetooth_cmd = "bluetoothctl power {}".format("on" if is_on else "off")
    os.system(bluetooth_cmd)

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

def check_external_switch():
    while True:
        switch_state = GPIO.input(switch_pin)
        if switch_state == GPIO.LOW:  # Switch is off
            toggle_bluetooth(False)  # Turn off Bluetooth
        else:  # Switch is on
            toggle_bluetooth(True)  # Turn on Bluetooth
        time.sleep(1)

# Start the external switch monitoring in a separate thread
switch_thread = threading.Thread(target=check_external_switch)
switch_thread.daemon = True
switch_thread.start()


# Keep the main program running
try:
    while True:
        time.sleep(1)
        # Check if the player has finished playing the current item
        if not player.is_playing():
            play_all_songs_randomly()  # Play all songs randomly when an album is done
except KeyboardInterrupt:
    print("Program terminated by user")
finally:
    i2c.deinit()
