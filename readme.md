# Pump Controller Serial Query

Python script that queries a pump controller over a serial link and parses
its response, translated from the ESP8266 Arduino firmware's
`getParameters()` logic (STX/ETX framing with an 8-bit checksum).

## Requirements

- Python 3.7+
- [pyserial](https://pypi.org/project/pyserial/)

```bash
pip install pyserial
```

## Configuration

Edit the constants at the top of `serial_query.py` before running:

| Constant | Description | Default |
|---|---|---|
| `SERIAL_PORT` | Serial port name (e.g. `COM3` on Windows, `/dev/ttyUSB0` on Linux) | `COM3` |
| `BAUD_RATE` | Must match the controller's configured baud rate | `9600` |
| `RESPONSE_WAIT` | Seconds to wait for the full reply before reading | `1.0` |

## Usage

```bash
python serial_query.py
```

On success, prints each parsed parameter and its value, e.g.:

```
Total running time: 1234.0
BP power: 45.2
MP power: 38.7
...
```

If nothing is printed, either no response was received (timeout — check
port/baud/wiring) or no frame in the response passed its checksum.

## Protocol notes

- **Query**: a fixed byte sequence (`STX 'M200000C8F' ETX '65' CR CR`) is
  sent to request a reading.
- **Response**: one or more frames of the form
  `STX + 2-digit param# + 7-byte value + ETX + 2-char hex checksum`,
  possibly concatenated in a single buffer.
- **Checksum**: 8-bit sum of the STX, param#, and value bytes; a frame is
  valid only when subtracting the trailing hex checksum bytes yields 0.
- **Value decoding**: spaces (`0x20`) in the 7-byte value field are treated
  as `'0'`; if no decimal point (`.`) appears in those 7 bytes, one is
  appended after them before parsing as a float.
- Parameter numbers are mapped to names via `PARAM_NAMES`, taken from the
  firmware's `anaData[]` array — update this list if your controller uses
  different parameter indices.

## Using the parsed data

`query_device()` returns a plain `dict` of `{parameter_name: value}`, so it
can be dropped into an MQTT publish, logged to a file/database, or polled on
a loop for continuous monitoring — mirroring what the original firmware does
over MQTT.