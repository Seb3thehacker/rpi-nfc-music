import time
import json
import vlc
import os
import board
import busio
import RPi.GPIO as GPIO
import subprocess
from adafruit_pn532.i2c import PN532_I2C
import logging
import threading
import random

last_scanned_tag = None
consecutive_scans = 0
scan_delay = 2 # Delay in seconds after a tag is scanned

# Define GPIO pins for the external switches
switch_pin_1 = 25 # Pin 25 for Bluetooth
switch_pin_2 = 22 # Pin 22 for NFC tag scanning control

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(switch_pin_1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(switch_pin_2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

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

def find_flac_files(directory):
  flac_files = []
  for root, dirs, files in os.walk(directory):
     for file in files:
        if file.endswith('.flac'):
           flac_files.append(os.path.join(root, file))
  return flac_files

def play_all_songs_randomly():
  try:
     media_list = vlc_instance.media_list_new()
     flac_files = find_flac_files(audio_folder)
     random.shuffle(flac_files)
     for flac_file in flac_files:
        media_list.add_media(vlc_instance.media_new(flac_file))
     player.set_media_list(media_list)
     player.play()
     logging.info(f"Started playing all songs randomly")
  except Exception as e:
     logging.error(f'Error playing all songs randomly: {e}')

def play_album(folder, shuffle=False):
  try:
     media_list = vlc_instance.media_list_new()
     album_path = os.path.join(audio_folder, folder)
     flac_files = find_flac_files(album_path)
     if shuffle:
        random.shuffle(flac_files)
     for flac_file in flac_files:
        media_list.add_media(vlc_instance.media_new(flac_file))
     player.set_media_list(media_list)
     player.play()
     logging.info(f"Started playing album: {folder} {'shuffled' if shuffle else 'in order'}")
  except Exception as e:
     logging.error(f'Error playing album {folder}: {e}')

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

  last_scanned_tag = tag_data # Update the last scanned tag
  time.sleep(scan_delay) # Delay to prevent immediate re-scanning

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

def check_bluetooth_state():
  result = subprocess.run(['bluetoothctl', 'show'], capture_output=True, text=True)
  return 'Powered: yes' in result.stdout

def set_bluetooth_power(state):
  if state:
     subprocess.run(['bluetoothctl', 'power', 'on'])
  else:
     subprocess.run(['bluetoothctl', 'power', 'off'])

def tag_scanning_loop():
  while True:
     # Check if NFC tag scanning is allowed (based on switch_pin_2 state)
     switch_2_state = GPIO.input(switch_pin_2)
     if switch_2_state == GPIO.LOW:
        time.sleep(1) # Add a delay to avoid rapid checking when the switch is off
        continue # Skip NFC tag scanning and handling

     tag_data = scan_tag()
     if tag_data:
        handle_new_tag(tag_data)
     time.sleep(0.1)

# Start the tag scanning in a separate thread
tag_scanning_thread = threading.Thread(target=tag_scanning_loop)
tag_scanning_thread.daemon = True
tag_scanning_thread.start()

try:
  # Check initial switch states and set Bluetooth accordingly
  initial_switch_1_state = GPIO.input(switch_pin_1)
  initial_switch_2_state = GPIO.input(switch_pin_2)
  initial_bluetooth_state = check_bluetooth_state()

  if initial_switch_1_state == GPIO.LOW and initial_bluetooth_state:
     set_bluetooth_power(False)
  elif initial_switch_1_state == GPIO.HIGH and not initial_bluetooth_state:
     set_bluetooth_power(True)

  while True:
     time.sleep(1)
     # Check if the player has finished playing the current item
     if not player.is_playing() and last_scanned_tag is not None:
        play_all_songs_randomly() # Play all songs randomly after an album is done

     # Check the state of the external switches
     switch_1_state = GPIO.input(switch_pin_1)
     switch_2_state = GPIO.input(switch_pin_2)
     bluetooth_state = check_bluetooth_state()

     if switch_1_state == GPIO.LOW and bluetooth_state:
        # Switch 1 is off and Bluetooth is on, turn off Bluetooth
        set_bluetooth_power(False)
        time.sleep(1) # Add a delay to avoid rapid switching

     elif switch_1_state == GPIO.HIGH and not bluetooth_state:
        # Switch 1 is on and Bluetooth is off, turn on Bluetooth
        set_bluetooth_power(True)
        time.sleep(1) # Add a delay to avoid rapid switching

     # Check if NFC tag scanning is allowed (based on switch_2_state)
     if switch_2_state == GPIO.LOW:
        player.stop() # Stop player activity when switch 2 is off
        last_scanned_tag = None # Reset last scanned tag
        continue # Skip NFC tag scanning and handling

except KeyboardInterrupt:
  print("Program terminated by user")
finally:
  i2c.deinit()
  GPIO.cleanup() # Clean up GPIO resources
