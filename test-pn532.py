from adafruit_pn532.i2c import PN532_I2C
from pydub import AudioSegment
from pydub.playback import play
import subprocess
import json
import os
import board
import logging
import busio
import time
import threading
import random
import RPi.GPIO as GPIO

i2c = busio.I2C(board.SCL, board.SDA)  
  
# Create the PN532 object  
pn532 = PN532_I2C(i2c, debug=False)  

# Load global configuration
with open("tags_config.json", "r") as config_file:
    config_data = json.load(config_file)
    global_config = config_data.get("global_config", {})
    audio_folder = global_config.get("audio_folder", "/path/to/audio/folder")
    enable_logging = global_config.get("enable_logging", False)

# Configure logging
if enable_logging:
    logging.basicConfig(filename='rfid_audio_player.log', level=logging.INFO)

def log(message):
    if enable_logging:
        logging.info(message)
    print(message)

def play_audio(file_path):
    stop_all_audio()  # Stop all pydub audio before playing a new one
    audio = AudioSegment.from_file(file_path, format="flac")
    play(audio)

def stop_all_audio():
    # Stop all pydub playback
    subprocess.run(["pkill", "pydub"])

def load_tag_mappings():
    with open("tags_config.json", "r") as file:
        return json.load(file)["tags"]

def play_all_songs_in_order(folder):
    songs = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.flac')]

    # Sort songs based on filenames
    sorted_songs = sorted(songs)

    return sorted_songs

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
    last_scanned_tag = None
    last_scan_time = None

    while True:
        # Scan for NFC tags
        log("Hold an NFC tag near the reader...")

        uid = pn532.read_passive_target(timeout=0.5)
        
        if uid is not None:
            time.sleep(1)

            album_info = str(uid.hex())
            bluetooth_powered_on = check_bluetooth_status()

            if bluetooth_powered_on:
                log("Bluetooth is powered on. Turning off...")
                toggle_bluetooth(False)
                time.sleep(5)

            stop_all_audio()

            if album_info and album_info in tag_audio_mapping:
                tag_info = tag_audio_mapping[album_info]
                folder = os.path.join(audio_folder, tag_info["folder"])

                log(f"Playing songs from folder: {folder}")
                sorted_songs = play_all_songs_in_order(folder)
                play_audio(sorted_songs[0])  # Play the first song in the sorted list

                if not bluetooth_powered_on:
                    log(f"Finished playing album {album_info}. Playing global folder in order.")
                    sorted_global_songs = play_all_songs_in_order(audio_folder)
                    play_audio(sorted_global_songs[0])  # Play the first song in the sorted global list

                if not check_bluetooth_status():
                    log("Turning Bluetooth back on...")
                    toggle_bluetooth(True)

            last_scanned_tag = album_info
            last_scan_time = time.time()

except KeyboardInterrupt:
    log("Program terminated by user.")
    if not check_bluetooth_status():
        log("Turning Bluetooth back on...")
        toggle_bluetooth(True)
    GPIO.cleanup()
