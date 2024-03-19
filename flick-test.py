import flicklib
import pyautogui

# VLC keyboard shortcuts
PLAY_PAUSE_KEY = ' '
NEXT_TRACK_KEY = 'n'
PREVIOUS_TRACK_KEY = 'p'

@flicklib.flick()
def on_flick(start, finish):
    delta = finish - start
    if delta > 0:
        next_track()
    else:
        previous_track()

@flicklib.airwheel()
def on_airwheel(delta):
    if delta > 0:
        next_track()
    else:
        previous_track()

def play_pause():
    pyautogui.press(PLAY_PAUSE_KEY)

def next_track():
    pyautogui.press(NEXT_TRACK_KEY)

def previous_track():
    pyautogui.press(PREVIOUS_TRACK_KEY)

try:
    while True:
        pass
except KeyboardInterrupt:
    flicklib.stop()
