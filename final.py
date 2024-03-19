import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import subprocess
import json
import os
import logging
import time
import vlc
import threading
import random

# Initialize GPIO and RFID reader
GPIO.setwarnings(False)
reader = SimpleMFRC522()

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
    def __init__(self, file_paths, shuffle=False):
        threading.Thread.__init__(self)
        self.file_paths = file_paths
        self.shuffle = shuffle

    def run(self):
        if self.shuffle:
            self.shuffle_play()
        else:
            self.play_in_order()

    def play_in_order(self):
        for file_path in self.file_paths:
            play_audio(file_path)

    def shuffle_play(self):
        shuffled_paths = self.file_paths.copy()
        random.shuffle(shuffled_paths)
        for file_path in shuffled_paths:
            play_audio(file_path)

def is_process_running(process_name):
    try:
        subprocess.check_output(["pidof", process_name])
        return True
    except subprocess.CalledProcessError:
        return False

def play_audio(file_path):
    Sound(file_path)

def stop_audio():
    subprocess.Popen(["pkill", "vlc"]).wait()

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

def Sound(sound):
    vlc_instance = vlc.Instance()
    player = vlc_instance.media_player_new()
    media = vlc_instance.media_new(sound)
    player.set_media(media)
    player.play()
    time.sleep(1.5)
    duration = player.get_length() / 1000
    time.sleep(duration)

try:
    tag_audio_mapping = load_tag_mappings()
    last_scanned_tag = None
    last_scan_time = None
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
                time.sleep(5)  # Wait for Bluetooth to turn off

            # Stop the currently playing audio
            stop_audio()

            # Check if the album_info is in the mapping
            if album_info and album_info in tag_audio_mapping:
                tag_info = tag_audio_mapping[album_info]
                folder = os.path.join(audio_folder, tag_info["folder"])
                
                # Play all songs immediately in order from the album folder on the first scan
                # If the same tag is scanned within 30 seconds, shuffle play the songs
                shuffle = last_scanned_tag == album_info and last_scan_time and time.time() - last_scan_time <= 30
                log(f"Playing songs{' (shuffled)' if shuffle else ''} from folder: {folder}")
                sorted_songs = play_all_songs_in_order(folder)
                audio_thread = AudioPlayerThread(sorted_songs, shuffle)
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
            last_scan_time = time.time()

except KeyboardInterrupt:
    log("Program terminated by user.")
    # Turn Bluetooth back on if it was turned off
    if not check_bluetooth_status():
        log("Turning Bluetooth back on...")
        toggle_bluetooth(True)
    GPIO.cleanup()
