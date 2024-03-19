from flask import Flask, request, render_template
import board
import busio
from adafruit_pn532.i2c import PN532_I2C

app = Flask(__name__)

# Initialize I2C bus and PN532 module
i2c = busio.I2C(board.SCL, board.SDA)
pn532 = PN532_I2C(i2c, address=0x24)

# Initialize Flask web server
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/write', methods=['POST'])
def write_to_tag():
    if request.method == 'POST':
        data = request.form['data']
        if data:
            # Configure PN532 to read NTAG215 tags
            pn532.SAM_configuration()

            # Wait for a tag to be present
            print('Waiting for NFC/RFID tag...')
            uid = pn532.read_passive_target(timeout=0.5)
            if uid:
                # Ensure data is padded with null bytes to fill the block
                data_bytes = data.encode('utf-8')
                data_blocks = [data_bytes[i:i+4].ljust(4, b'\x00') for i in range(0, len(data_bytes), 4)]

                # Write data to the tag block by block
                success = True
                for block_number, block_data in enumerate(data_blocks):
                    success = pn532.ntag2xx_write_block(block_number, block_data)
                    if not success:
                        break

                if success:
                    return f'Data "{data}" has been successfully written to tag with UID: {uid.hex()}'
                else:
                    return 'Failed to write data to tag. Make sure the tag is not locked.'
            else:
                return 'Failed to detect tag. Please try again.'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
