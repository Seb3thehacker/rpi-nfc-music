import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import vlc
import time
import json
import os
import logging
import subprocess

# Initialize GPIO and RFID reader
GPIO.setwarnings(False)
reader = SimpleMFRC522()

# Load global configuration
with open("tags_config.json", "r") as config_file:
    config_data = json.load(config_file)
    global_config = config_data.get("global_config", {})
    audio_folder = global_config.get("audio_folder", "/path/to/audio/folder")
    shuffle_play = global_config.get("shuffle_play", False)
    enable_logging = global_config.get("enable_logging", False)

# Configure logging
if enable_logging:
    logging.basicConfig(filename='rfid_audio_player.log', level=logging.INFO)

def log(message):
    if enable_logging:
        logging.info(message)
    print(message)

def play_audio(file_path):
    instance = vlc.Instance("--no-xlib --quiet")
    player = instance.media_player_new()
    media = instance.media_new(file_path)
    media.get_mrl()
    player.set_media(media)
    player.play()
    while player.get_state() != vlc.State.Ended:
        time.sleep(1)

def load_tag_mappings():
    with open("tags_config.json", "r") as file:
        return json.load(file)["tags"]

def play_all_songs_in_order(folder):
    songs = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.flac')]
    songs.sort()  # Sort by filename
    
    for song in songs:
        log(f"Playing: {song}")
        play_audio(song)

def check_bluetooth_status():
    try:
        result = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True, timeout=5)
        return "Powered: yes" in result.stdout
    except subprocess.TimeoutExpired:
        log("Timeout while checking Bluetooth status. Assuming Bluetooth is powered on.")
        return True

def toggle_bluetooth(enable):
    if enable:
        subprocess.run(["bluetoothctl", "power", "on"])
        print("Bluetooth turned ON")
    else:
        subprocess.run(["bluetoothctl", "power", "off"])
        print("Bluetooth turned OFF")

try:
    tag_audio_mapping = load_tag_mappings()

    while True:
        # Scan for NFC tags
        log("Hold an NFC tag near the reader...")
        
        # Initialize id and text to handle potential errors
        id = None
        text = None
        
        try:
            id, text = reader.read()
        except Exception as e:
            log(f"Error during NFC tag scan: {e}")
        
        # Continue only if a successful scan occurred
        if id is not None and text is not None:
            # Parse album information from the text on the tag
            album_info = text.strip()

            # Check Bluetooth status
            bluetooth_powered_on = check_bluetooth_status()

            # Turn off Bluetooth if powered on
            if bluetooth_powered_on:
                log("Bluetooth is powered on. Turning off...")
                toggle_bluetooth(False)
                time.sleep(5)  # Wait for Bluetooth to turn off

            # Check if the album_info is in the mapping
            if album_info and album_info in tag_audio_mapping:
                tag_info = tag_audio_mapping[album_info]
                folder = os.path.join(audio_folder, tag_info["folder"])

                # Play all songs in order from the album folder
                log(f"Playing all songs in order from folder: {folder}")
                play_all_songs_in_order(folder)

                # After playing all songs, shuffle play the entire folder if Bluetooth is off
                if shuffle_play and not bluetooth_powered_on:
                    log(f"Finished playing album {album_info}. Shuffle playing folder {folder}.")
                    play_all_songs_in_order(folder)

                # Turn Bluetooth back on if it was turned off
                if not bluetooth_powered_on:
                    log("Turning Bluetooth back on...")
                    toggle_bluetooth(True)
        
except KeyboardInterrupt:
    log("Program terminated by user.")
    # Turn Bluetooth back on if it was turned off
    if not check_bluetooth_status():
        log("Turning Bluetooth back on...")
        toggle_bluetooth(True)
    GPIO.cleanup()
