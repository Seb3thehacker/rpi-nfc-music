import RPi.GPIO as GPIO
import board
import busio
from adafruit_pn532.i2c import PN532_I2C
import vlc
import time
import json
import os
import logging
import subprocess
import multiprocessing

# Initialize GPIO and RFID reader
GPIO.setwarnings(False)
i2c = busio.I2C(board.SCL, board.SDA)
pn532 = PN532_I2C(i2c, debug=False)
#pn532.SAM_configuration()

def log(message):
    if enable_logging:
        logging.info(message)
    print(message)

def play_audio(file_path):
    instance = vlc.Instance("--quiet", "--no-xlib", "--aout=alsa")
    player = instance.media_player_new()
    media = instance.media_new(file_path)
    media.get_mrl()
    player.set_media(media)
    player.play()
    player.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached, lambda x: player.stop())
    player.event_manager().event_attach(vlc.EventType.MediaPlayerStopped, lambda x: player.release())
    player.set_fullscreen(True)
    player.set_pause(0)  # Start playing

def play_audio_process(file_path):
    play_audio(file_path)

def load_tag_mappings():
    with open("tags_config.json", "r") as file:
        return json.load(file)["tags"]

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

def stop_all_vlc_processes():
    try:
        subprocess.run(["pkill", "vlc"])
    except Exception as e:
        log(f"Error stopping VLC processes: {e}")

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

try:
    tag_audio_mapping = load_tag_mappings()

    while True:
        log("Hold an NFC tag near the reader...")

        uid = pn532.read_passive_target(timeout=0.5)

        if uid is not None:
            id = str(uid.hex())
            text = None

            try:
                text = tag_audio_mapping[id]
            except KeyError:
                log(f"Tag {id} not found in mappings.")
            
            if text is not None:
                album_info = text.strip()

                stop_all_vlc_processes()

                bluetooth_powered_on = check_bluetooth_status()

                if bluetooth_powered_on:
                    log("Bluetooth is powered on. Turning off...")
                    toggle_bluetooth(False)
                    time.sleep(5)

                if album_info and album_info in tag_audio_mapping:
                    tag_info = tag_audio_mapping[album_info]
                    folder = os.path.join(audio_folder, tag_info["folder"])

                    log(f"Playing all songs in order from folder: {folder}")

                    # Start a new process to play audio
                    play_process = multiprocessing.Process(target=play_audio_process, args=(folder,))
                    play_process.start()
                    play_process.join()  # Wait for the process to finish

                    if shuffle_play and not bluetooth_powered_on:
                        log(f"Finished playing album {album_info}. Shuffle playing folder {folder}.")

                        # Start a new process to shuffle play audio
                        shuffle_process = multiprocessing.Process(target=play_audio_process, args=(folder,))
                        shuffle_process.start()
                        shuffle_process.join()  # Wait for the process to finish

                    if not bluetooth_powered_on:
                        log("Turning Bluetooth back on...")
                        toggle_bluetooth(True)

except KeyboardInterrupt:
    log("Program terminated by user.")

    if not check_bluetooth_status():
        log("Turning Bluetooth back on...")
        toggle_bluetooth(True)
    GPIO.cleanup()
