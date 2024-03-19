import board
import busio
from adafruit_pn532.i2c import PN532_I2C
from ndef import BluetoothEasyPairingRecord, NdefMessage

# Raspberry Pi's Bluetooth address (replace with your actual address)
bluetooth_address = "XX:XX:XX:XX:XX:XX"

# Initialize PN532
i2c = busio.I2C(board.SCL, board.SDA)
pn532 = PN532_I2C(i2c, debug=False)
pn532.SAM_configuration()

# Create an NDEF record with the Bluetooth pairing information
record = BluetoothEasyPairingRecord(bluetooth_address)
ndef_message = NdefMessage(record)

# Function to write the NDEF message to an NFC tag
def write_nfc_tag(ndef_message):
    try:
        pn532.write_ndef(ndef_message)
        print("NFC tag written with Bluetooth pairing info.")
    except Exception as e:
        print(f"Error writing to NFC tag: {e}")

# Write to the NFC tag
write_nfc_tag(ndef_message)
