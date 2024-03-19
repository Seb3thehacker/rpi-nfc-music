from gtts import gTTS
import os

def text_to_speech(text, lang='en'):
    tts = gTTS(text=text, lang=lang)
    filename = "/tmp/temp.mp3"
    tts.save(filename)
    os.system(f"mpg123 {filename}")

# Example usage
text = "Shuffling NOEASY. Now playing liked songs. Lets start with, God`s Menu by Stray Kids. You'll like this one: CHEESE by Stray Kids."
text_to_speech(text)
