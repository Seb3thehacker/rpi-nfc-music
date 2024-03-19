import board
import busio
from adafruit_pn532.i2c import PN532_I2C
import time

# Create an I2C object
i2c = busio.I2C(board.SCL, board.SDA)

# Create the PN532 object
pn532 = PN532_I2C(i2c, debug=False)

# Configure PN532 to communicate with MiFare cards
pn532.SAM_configuration()

print("Waiting for an NFC card...")

try:
    while True:
        # Check if a card is available to read
        uid = pn532.read_passive_target(timeout=0.5)

        # If a card is found, read data from it
        if uid is not None:
            print("Found card with UID:", [hex(i) for i in uid])

            # Read data from the card (assuming 4-byte data)
            data_read = pn532.ntag2xx_read_block(4)

            print("Data read from the card:", data_read.decode('utf-8'))

except Exception as e:
    print(f"Error: {e}")

finally:
    # Explicitly close the I2C connection
    i2c.deinit()
