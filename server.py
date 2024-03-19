import board
import busio
from adafruit_pn532.i2c import PN532_I2C
from flask import Flask, render_template, request

app = Flask(__name__)

# Create an I2C object
i2c = busio.I2C(board.SCL, board.SDA)

# Create the PN532 object
pn532 = PN532_I2C(i2c, debug=False)

# Configure PN532 to communicate with MiFare cards
pn532.SAM_configuration()

last_scanned_uid = None  # Variable to store the last scanned UID

@app.route('/')
def index():
    return render_template('index.html', last_scanned_uid=last_scanned_uid)

@app.route('/scan', methods=['POST'])
def scan():
    try:
        global last_scanned_uid

        # Check if a card is available to read
        uid = pn532.read_passive_target(timeout=0.5)

        if uid is not None:
            print("Found card with UID:", [hex(i) for i in uid])
            last_scanned_uid = uid

            return render_template('index.html', last_scanned_uid=last_scanned_uid)

        else:
            error_message = "Error: No NFC card found. Please try again."
            print(error_message)
            return render_template('error.html', error_message=error_message)

    except Exception as e:
        error_message = f"Error: {e}"
        print(error_message)
        return render_template('error.html', error_message=error_message)

@app.route('/write', methods=['POST'])
def write():
    try:
        global last_scanned_uid

        if last_scanned_uid is not None:
            # Get data from the web form
            data_to_write = request.form['data_to_write']

            # Convert the string to bytes (UTF-8 encoding)
            data_bytes = data_to_write.encode('utf-8')

            # Write data to the last scanned card, 4 bytes per block
            block_number = 4  # Start writing from block 4
            for start_index in range(0, len(data_bytes), 4):
                end_index = start_index + 4
                block_data = data_bytes[start_index:end_index]

                # Ensure the block_data is 4 bytes long by padding if necessary
                block_data += b'\0' * (4 - len(block_data))

                pn532.ntag2xx_write_block(block_number, block_data)
                block_number += 1

            print("Data written to the last scanned card:", data_to_write)

            return render_template('success.html', data_written=data_to_write)

        else:
            error_message = "Error: No NFC card scanned. Please scan an NFC card first."
            print(error_message)
            return render_template('error.html', error_message=error_message)

    except Exception as e:
        error_message = f"Error: {e}"
        print(error_message)
        return render_template('error.html', error_message=error_message)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
