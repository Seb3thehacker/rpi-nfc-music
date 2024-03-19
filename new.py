import RPi.GPIO as GPIO
import threading
import subprocess
import json
import os
import board
import logging
import busio
import time
import vlc
from adafruit_pn532.i2c import PN532_I2C

# Initialize GPIO and PN532
GPIO.setwarnings(False)

# Create an I2C object
i2c = busio.I2C(board.SCL, board.SDA)

# Create the PN532 object
pn532 = PN532_I2C(i2c, debug=True)

# Configure PN532 to communicate with MiFare cards
pn532.SAM_configuration()

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

class AudioPlayerThread(threading.Thread):
    def __init__(self, file_paths, lock):
        threading.Thread.__init__(self)
        self.file_paths = file_paths
        self.lock = lock

    def run(self):
        with self.lock:
            for file_path in self.file_paths:
                play_audio(file_path)

def is_process_running(process_name):
    try:
        subprocess.check_output(["pidof", process_name])
        return True
    except subprocess.CalledProcessError:
        return False

def play_audio(file_path):
    # Check if VLC process is already running
    if not is_process_running("vlc"):
        subprocess.Popen(["cvlc", "--no-xlib", "--quiet", file_path])

def load_tag_mappings():
    with open("tags_config.json", "r") as file:
        return json.load(file)["tags"]

def play_all_songs_in_order(folder):
    songs = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.flac')]

    # Extract track numbers from file names or use default of 99 if not found
    track_numbers = [int(f.split('.')[0]) if f.split('.')[0].isdigit() else 99 for f in songs]

    # Sort songs based on track numbers
    sorted_songs = [song for _, song in sorted(zip(track_numbers, songs))]

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
    lock = threading.Lock()

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
            # Pause for 1 second after a tag is scanned
            time.sleep(1)

            # Parse album information from the text on the tag
            album_info = text.strip()

            # Check Bluetooth status
            bluetooth_powered_on = check_bluetooth_status()

            # Turn off Bluetooth if powered on
            if bluetooth_powered_on:
                log("Bluetooth is powered on. Turning off...")
                toggle_bluetooth(False)
                #time.sleep(5)  # Wait for Bluetooth to turn off

            # Stop the currently playing audio
            subprocess.Popen(["pkill", "vlc"])

            # Check if the album_info is in the mapping
            if album_info and album_info in tag_audio_mapping:
                tag_info = tag_audio_mapping[album_info]
                folder = os.path.join(audio_folder, tag_info["folder"])
                
                # Play all songs immediately in order from the album folder
                log(f"Playing all songs in order from folder: {folder}")
                sorted_songs = play_all_songs_in_order(folder)
                audio_thread = AudioPlayerThread(sorted_songs, lock)
                audio_thread.start()

                # After playing all songs, shuffle play the entire folder if Bluetooth is off
                if not bluetooth_powered_on:
                    log(f"Finished playing album {album_info}. Playing global folder in order.")
                    sorted_global_songs = play_all_songs_in_order(audio_folder)
                    audio_thread = AudioPlayerThread(sorted_global_songs, lock)
                    audio_thread.start()

                # Turn Bluetooth back on if it was turned off
                if not bluetooth_powered_on:
                    log("Turning Bluetooth back on...")
                    toggle_bluetooth(True)

            last_scanned_tag = album_info

except KeyboardInterrupt:
    log("Program terminated by user.")
    # Turn Bluetooth back on if it was turned off
    if not check_bluetooth_status():
        log("Turning Bluetooth back on...")
        toggle_bluetooth(True)
    GPIO.cleanup()
