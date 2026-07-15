"""
Serial query/response for the pump controller, translated from the ESP8266
Arduino sketch (getParameters() / callback logic).

Protocol (as implemented on the device side):
  Query bytes sent:  STX 'M' '2' '0' '0' '0' '0' '0' 'C' '8' 'F' ETX '6' '5' CR CR
  Response frame(s):
    STX(1) + param#(2 ASCII digits) + value(7 bytes) + ETX(1) + checksum(2 ASCII hex)
  Multiple frames can be concatenated in one response buffer.
  Checksum = 8-bit sum of (STX + param# bytes + value bytes) minus the
             2 hex-ASCII checksum bytes; valid when the result == 0.

Adjust SERIAL_PORT and BAUD_RATE for your setup before running.
"""

import time
import serial  # pip install pyserial

SERIAL_PORT = "COM3"   # e.g. "COM3" on Windows, "/dev/ttyUSB0" on Linux
BAUD_RATE = 9600       # match the device's actual baud rate
RESPONSE_WAIT = 1.0    # seconds to wait for the ~256 byte reply (mirrors firmware's delay(1000))

# Raw query bytes, exactly as sent by the firmware
QUERY = bytes([0x02, 0x4d, 0x32, 0x30, 0x30, 0x30, 0x30, 0x30,
                0x30, 0x43, 0x38, 0x46, 0x03, 0x36, 0x35, 0x0d, 0x0d])

# Parameter index -> name, taken from the firmware's anaData[] array
PARAM_NAMES = [
    "Total running time",
    "BP power",
    "MP power",
    "BP motor speed",
    "MP motor speed",
    "BP current",
    "MP current",
    "BP casing temp",
    "MP casing temp",
    "Cooling water flow",
    "Pump N2 flow",
    "Back pressure 1",
    "Heater2",
    "Heater3",
    "Heater4",
]


def viewable_to_hex(v: int) -> int:
    """Convert an ASCII hex-digit byte to its numeric value (matches viewableToHex())."""
    if v > 0x40:
        return v - 0x41 + 10
    return v - 0x30


def parse_response(data: bytes) -> dict:
    """
    Walk a raw response buffer and extract every valid parameter frame,
    mirroring the byte-by-byte logic in the firmware's getParameters().
    """
    result = {}
    i = 0
    n = len(data)

    while i < n:
        if data[i] != 0x02:  # look for STX
            i += 1
            continue

        checksum = data[i]

        # discard non-numeric frames (next byte must be an ASCII digit, i.e. < 0x3A)
        if i + 1 >= n or data[i + 1] >= 0x3A:
            i += 1
            continue

        i += 1  # move onto first digit of param number
        if i + 1 >= n:
            break

        param_str = bytes([data[i], data[i + 1]])
        checksum = (checksum + data[i] + data[i + 1]) & 0xFF
        i += 1  # points at second digit; firmware moves i forward one, then +1 below

        try:
            para = int(param_str.decode())
        except ValueError:
            i += 1
            continue

        i += 1  # move onto first value byte

        if i + 7 > n:
            break

        raw = bytearray(data[i:i + 7])
        decimal_present = False
        for j in range(7):
            checksum = (checksum + raw[j]) & 0xFF
            if raw[j] == 0x20:       # space -> '0'
                raw[j] = 0x30
            if raw[j] == 0x2E:       # '.'
                decimal_present = True

        value_str = bytes(raw) + b"0"
        value_bytes = bytearray(value_str)
        if not decimal_present:
            value_bytes[7] = 0x2E    # no decimal point in payload -> append one

        try:
            value = float(value_bytes.decode())
        except ValueError:
            value = None

        i += 7   # advance past the 7 value bytes
        i += 1   # skip ETX

        if i + 1 >= n:
            break

        checksum = (checksum - ((viewable_to_hex(data[i]) << 4) + viewable_to_hex(data[i + 1]))) & 0xFF
        i += 2

        if checksum == 0 and value is not None and 0 <= para < len(PARAM_NAMES):
            result[PARAM_NAMES[para]] = value

    return result


def query_device(port: str = SERIAL_PORT, baud: int = BAUD_RATE, timeout: float = 2.0) -> dict:
    """Send the query and return a dict of {parameter_name: value} parsed from the reply."""
    with serial.Serial(port, baud, timeout=timeout) as ser:
        ser.reset_input_buffer()
        ser.write(QUERY)

        time.sleep(RESPONSE_WAIT)  # give the device time to send its full reply
        raw = ser.read(ser.in_waiting or 256)

        if not raw:
            print("No response received (timeout)")
            return {}

        return parse_response(raw)


if __name__ == "__main__":
    readings = query_device()
    if readings:
        for name, value in readings.items():
            print(f"{name}: {value}")
    else:
        print("No valid data parsed from response.")