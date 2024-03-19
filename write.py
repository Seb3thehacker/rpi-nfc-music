import board
import busio
from adafruit_pn532.i2c import PN532_I2C

# Create an I2C object
i2c = busio.I2C(board.SCL, board.SDA)

# Create the PN532 object
pn532 = PN532_I2C(i2c, debug=False)

# Configure PN532 to communicate with MiFare cards
pn532.SAM_configuration()

print("Place an NFC card to write...")

try:
    while True:
        # Check if a card is available to write
        uid = pn532.read_passive_target(timeout=0.5)

        # If a card is found, ask the user for data to write
        if uid is not None:
            print("Found card with UID:", [hex(i) for i in uid])

            # User input for data to write to the card
            data_to_write = input("Enter data to write to the card: ")

            # Convert the string to bytes (UTF-8 encoding)
            data_bytes = data_to_write.encode('utf-8')

            # Write data to the card, 4 bytes per block
            block_number = 4  # Start writing from block 4
            for start_index in range(0, len(data_bytes), 4):
                end_index = start_index + 4
                block_data = data_bytes[start_index:end_index]
                
                # Ensure the block_data is 4 bytes long by padding if necessary
                block_data += b'\0' * (4 - len(block_data))

                pn532.ntag2xx_write_block(block_number, block_data)
                block_number += 1

            print("Data written to the card:", data_to_write)
            break

except Exception as e:
    print(f"Error: {e}")

finally:
    # Explicitly close the I2C connection
    i2c.deinit()
