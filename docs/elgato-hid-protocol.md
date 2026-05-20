# Elgato Stream Deck HID Protocol Reference

Local reference compiled from the official Elgato HID API documentation.
Source: <https://docs.elgato.com/streamdeck/hid/intro>

This document covers the **Main Protocol** only. The legacy Stream Deck Mini
protocol is not documented here and is not supported by DeUX.

---

## Supported Devices

| Device | Model | VID | PID | Matrix | Key Size | LCD Size | Rotation | Window | Encoders |
|---|---|---|---|---|---|---|---|---|---|
| SD 15-Key Module | 20GBA9901 | 0x0FD9 | 0x00B9 | 5x3 | 72x72 | 480x272 | 180 deg | - | - |
| SD 2019 | 20GAA9902 | 0x0FD9 | 0x006D | 5x3 | 72x72 | 480x272 | 180 deg | - | - |
| SD Mk.2 | 20GBA9901 | 0x0FD9 | 0x0080 | 5x3 | 72x72 | 480x272 | 180 deg | - | - |
| SD Mk.2 (Scissor) | 20GBL9901 | 0x0FD9 | 0x00A5 | 5x3 | 72x72 | 480x272 | 180 deg | - | - |
| SD XL | 20GAT9901 | 0x0FD9 | 0x006C | 8x4 | 96x96 | 1024x600 | 180 deg | - | - |
| SD XL 2022 | 20GAT9902 | 0x0FD9 | 0x008F | 8x4 | 96x96 | 1024x600 | 180 deg | - | - |
| SD Module 32 | 20GAT9902 | 0x0FD9 | 0x00BA | 8x4 | 96x96 | 1024x600 | 180 deg | - | - |
| SD Neo | 20GBJ9901 | 0x0FD9 | 0x009A | 4x2 | 96x96 | 480x320 | 180 deg | 248x58 | - |
| SD + | 20GBD9901 | 0x0FD9 | 0x0084 | 4x2 | 120x120 | 800x480 | none | 800x100 | 4 |
| SD + XL | 20GBD9901 | 0x0FD9 | 0x00C6 | 9x4 | 112x112 | 1280x800 | 90 deg CCW | 1200x100 | 6 |

**Notes:**

- All Classic family devices (PIDs 0x006D, 0x0080, 0x00A5, 0x00B9) share the
  same command set.
- All XL family devices (PIDs 0x006C, 0x008F, 0x00BA) share the same command
  set.
- The Stream Deck with PID 0x0060 is the original 2017 model and uses a
  different legacy protocol. It is **not supported**.
- Neo has 2 capacitive touch sensors mapped as extra buttons appended after
  the keypad buttons in the input report.
- All images are JPEG format.
- "Rotation" is the rotation applied to the image **before** upload.

---

## Data Types

| Type | Description |
|---|---|
| UINT8 / BYTE | Unsigned 8-bit integer |
| INT8 / CHAR | Signed 8-bit integer / ASCII |
| UINT16 | Little-endian unsigned 16-bit integer |
| INT16 | Little-endian signed 16-bit integer |
| UINT32 | Little-endian unsigned 32-bit integer |
| INT32 | Little-endian signed 32-bit integer |
| RGB Triplet | 3 bytes: R (0x00), G (0x01), B (0x02) |

All multi-byte integers are **little-endian**.

---

## Report Structures

### Input Report (Device -> Host)

Max size: **512 bytes**. Obtained by polling with HID READ (non-blocking,
recommended 50ms interval). TIMEOUT indicates no pending event.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x01` |
| 0x01 | UINT8 | Command |
| 0x02 | UINT16 | Payload data length |
| 0x04 | BYTE[] | Payload |

### Output Report (Host -> Device)

Max size: **1024 bytes**. Sent via HID WRITE. Pad remaining bytes with zeroes
to 1024.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x02` |
| 0x01 | UINT8 | Command |
| 0x02 | BYTE[] | Payload |

### Feature Report (Bidirectional)

Max size: **32 bytes**. Sent via HID SEND FEATURE REPORT / HID GET FEATURE
REPORT. Pad remaining bytes with zeroes to 32.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID |
| 0x01 | UINT8 | Command (ignored for some getter reports) |
| 0x02 | BYTE[] | Payload |

---

## Input Reports (Report ID: 0x01)

### Key / Button Press State Change (Command: 0x00)

All devices. Event generated on every change of key/button state.

| Offset | Type | Description |
|---|---|---|
| 0x00 | | Report ID: `0x01`, Command: `0x00` |
| 0x02 | UINT16 | Payload length = number of keys/buttons |
| 0x04 | UINT8[] | Per-key state: `0x00` = depressed, `0x01` = pressed |

**Neo note:** The 2 capacitive touch sensors are appended as extra buttons
after the 8 keypad buttons (total payload length = 10).

### Touch Screen Activity (Command: 0x02)

Plus and Plus XL only. Event reported after interaction completes (touch and
release are not separate events).

#### TAP (contents type: 0x01)

| Offset | Type | Description |
|---|---|---|
| 0x00 | | Report ID: `0x01`, Command: `0x02` |
| 0x02 | UINT16 | Payload length: `0x0A` |
| 0x04 | UINT8 | Contents type: `0x01` (TAP) |
| 0x05 | UINT8 | Number of fingers: N/A |
| 0x06 | UINT16 | Touch X-coordinate |
| 0x08 | UINT16 | Touch Y-coordinate |

#### PRESS (contents type: 0x02)

| Offset | Type | Description |
|---|---|---|
| 0x00 | | Report ID: `0x01`, Command: `0x02` |
| 0x02 | UINT16 | Payload length: `0x0A` |
| 0x04 | UINT8 | Contents type: `0x02` (PRESS) |
| 0x05 | UINT8 | Number of fingers: N/A |
| 0x06 | UINT16 | Touch X-coordinate |
| 0x08 | UINT16 | Touch Y-coordinate |

#### FLICK (contents type: 0x03)

| Offset | Type | Description |
|---|---|---|
| 0x00 | | Report ID: `0x01`, Command: `0x02` |
| 0x02 | UINT16 | Payload length: `0x0E` |
| 0x04 | UINT8 | Contents type: `0x03` (FLICK) |
| 0x05 | UINT8 | Reserved |
| 0x06 | UINT16 | Start X-coordinate |
| 0x08 | UINT16 | Start Y-coordinate |
| 0x0A | UINT16 | End X-coordinate |
| 0x0C | UINT16 | End Y-coordinate |

### Encoder State Change (Command: 0x03)

Plus and Plus XL only.

#### BTN (contents type: 0x00)

One or more encoder buttons changed press state.

| Offset | Type | Description |
|---|---|---|
| 0x00 | | Report ID: `0x01`, Command: `0x03` |
| 0x02 | UINT16 | Payload length = number of encoders + 1 |
| 0x04 | UINT8 | Contents type: `0x00` (BTN) |
| 0x05 | UINT8[] | Per-encoder: `0x00` = depressed, `0x01` = pressed |

#### ROTATE (contents type: 0x01)

One or more encoders were rotated.

| Offset | Type | Description |
|---|---|---|
| 0x00 | | Report ID: `0x01`, Command: `0x03` |
| 0x02 | UINT16 | Payload length = number of encoders + 1 |
| 0x04 | UINT8 | Contents type: `0x01` (ROTATE) |
| 0x05 | INT8[] | Per-encoder: positive = CW, negative = CCW |

---

## Output Reports (Report ID: 0x02)

All output image commands use chunked transfers. The JPEG payload is split
into chunks that fit within 1024-byte reports. Each chunk includes a header
followed by chunk data. The last chunk sets the "Transfer is Done" flag to
`0x01`.

### Update Key / Button Image (Command: 0x07)

All devices. Uploads a JPEG image for a specific key.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x02` |
| 0x01 | UINT8 | Command: `0x07` |
| 0x02 | UINT8 | Key/Button index |
| 0x03 | UINT8 | Transfer is Done flag (`0x01` = last chunk) |
| 0x04 | UINT16 | Chunk contents size |
| 0x06 | UINT16 | Chunk index (zero-based) |
| 0x08 | UINT8[] | Chunk data |

Header size: 8 bytes. Max chunk data per report: 1024 - 8 = **1016 bytes**.

### Update Full Screen Image (Command: 0x08)

All devices. Uploads a JPEG image covering the entire LCD.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x02` |
| 0x01 | UINT8 | Command: `0x08` |
| 0x02 | UINT8 | Reserved |
| 0x03 | UINT8 | Transfer is Done flag (`0x01` = last chunk) |
| 0x04 | UINT16 | Chunk contents size |
| 0x06 | UINT16 | Chunk index (zero-based) |
| 0x08 | UINT8[] | Chunk data |

Header size: 8 bytes. Max chunk data per report: 1024 - 8 = **1016 bytes**.

LCD sizes per device:

| Device | Full Screen Size |
|---|---|
| Classic family | 480x272 (rotate 180 deg) |
| XL family | 1024x600 (rotate 180 deg) |
| Neo | 480x320 (rotate 180 deg) |
| Plus | 800x480 (no rotation) |
| Plus XL | 1280x800 (rotate 90 deg CCW) |

### Update Window Image (Command: 0x0B)

Neo, Plus, Plus XL. Uploads a JPEG image for the full touchscreen/info window
strip.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x02` |
| 0x01 | UINT8 | Command: `0x0B` |
| 0x02 | UINT8 | Reserved |
| 0x03 | UINT8 | Transfer is Done flag (`0x01` = last chunk) |
| 0x04 | UINT16 | Chunk contents size |
| 0x06 | UINT16 | Chunk index (zero-based) |
| 0x08 | UINT8[] | Chunk data |

Header size: 8 bytes. Max chunk data per report: 1024 - 8 = **1016 bytes**.

Window sizes:

| Device | Window Size |
|---|---|
| Neo | 248x58 |
| Plus | 800x100 |
| Plus XL | 1200x100 |

### Update Partial Window Image (Command: 0x0C)

Neo, Plus, Plus XL. Uploads a JPEG image into a rectangular region of the
window.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x02` |
| 0x01 | UINT8 | Command: `0x0C` |
| 0x02 | UINT16 | X-coordinate |
| 0x04 | UINT16 | Y-coordinate |
| 0x06 | UINT16 | Image width |
| 0x08 | UINT16 | Image height |
| 0x0A | UINT8 | Transfer is Done flag (`0x01` = last chunk) |
| 0x0B | UINT16 | Chunk index (zero-based) |
| 0x0D | UINT16 | Chunk contents size |
| 0x0F | UINT8 | Reserved |
| 0x10 | UINT8[] | Chunk data |

Header size: 16 bytes. Max chunk data per report: 1024 - 16 = **1008 bytes**.

**Note:** Use logical coordinates, without accounting for image rotation.

### Update Background (Command: 0x0D)

Classic and XL families only. Uploads a JPEG image to be stored as a
background at a given index.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x02` |
| 0x01 | UINT8 | Command: `0x0D` |
| 0x02 | UINT8 | Background index |
| 0x03 | UINT8 | Transfer is Done flag (`0x01` = last chunk) |
| 0x04 | UINT16 | Chunk index (zero-based) |
| 0x06 | UINT16 | Chunk contents size |
| 0x08 | UINT8[] | Chunk data |

**Note:** Chunk index and chunk contents size fields are swapped compared to
the other output commands.

---

## Setter Feature Reports (Report ID: 0x03)

### Show Logo (Command: 0x02)

All devices. Forcibly triggers the display of the boot logo.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x03` |
| 0x01 | UINT8 | Command: `0x02` |

### Fill LCD with Color (Command: 0x05)

All devices. Fills the entire LCD with a given RGB color.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x03` |
| 0x01 | UINT8 | Command: `0x05` |
| 0x02 | RGB Triplet | Color (R, G, B) |

### Fill Key / Button with Color (Command: 0x06)

All devices. Fills a single key/button with a given RGB color.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x03` |
| 0x01 | UINT8 | Command: `0x06` |
| 0x02 | UINT8 | Key/Button index |
| 0x03 | RGB Triplet | Color (R, G, B) |

### Set Backlight Brightness (Command: 0x08)

All devices. Sets the LCD backlight brightness level.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x03` |
| 0x01 | UINT8 | Command: `0x08` |
| 0x02 | UINT8 | Brightness: `0x00` to `0x64` (0-100%) |

### Set Sleep Mode Duration (Command: 0x0D)

All devices. Sets idle duration in seconds before sleep mode.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x03` |
| 0x01 | UINT8 | Command: `0x0D` |
| 0x02 | INT32 | Duration in seconds (0 = disabled) |

### Show Background by Index (Command: 0x13)

XL family only. Displays a previously stored background by its index.

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x03` |
| 0x01 | UINT8 | Command: `0x13` |
| 0x02 | UINT8 | Background index |

---

## Getter Feature Reports

Each getter uses a dedicated Report ID. Send the report ID to request, then
read the response.

### Get Firmware Version

Three firmware components, each with its own report ID:

| Report ID | Firmware |
|---|---|
| `0x04` | LD |
| `0x05` | AP2 (primary firmware) |
| `0x07` | AP1 |

**Request:** Send feature report with the report ID (payload ignored).

**Response:**

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID |
| 0x01 | UINT8 | Data length: `0x0C` |
| 0x02 | UINT32 | Checksum |
| 0x06 | UINT8[8] | Version string (ASCII) |

### Get Unit Serial Number (Report ID: 0x06)

**Request:** Send feature report with report ID `0x06`.

**Response:**

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x06` |
| 0x01 | UINT8 | Data length: `0x0C` or `0x0E` |
| 0x02 | UINT8[N] | Serial number string (ASCII) |

### Get Unit Information (Report ID: 0x08)

**Request:** Send feature report with report ID `0x08`.

**Response:**

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x08` |
| 0x01 | UINT8 | Keypad matrix rows |
| 0x02 | UINT8 | Keypad matrix columns |
| 0x03 | UINT16 | Key/Button width (pixels) |
| 0x05 | UINT16 | Key/Button height (pixels) |
| 0x07 | UINT16 | LCD width (pixels) |
| 0x09 | UINT16 | LCD height (pixels) |
| 0x0B | UINT8 | Image BPP |
| 0x0C | UINT8 | Image color scheme |
| 0x0D | UINT8 | Number of key/button images in gallery |
| 0x0E | UINT8 | Number of LCD images in gallery |
| 0x0F | UINT8 | Number of frames for DEMO |
| 0x10 | UINT8 | Reserved |

**Note:** The response format may vary across firmware versions. Window-capable
devices may extend this response.

### Get Sleep Mode Duration (Report ID: 0x0A)

**Request:** Send feature report with report ID `0x0A`.

**Response:**

| Offset | Type | Description |
|---|---|---|
| 0x00 | UINT8 | Report ID: `0x0A` |
| 0x01 | UINT8 | Data length |
| 0x02 | INT32 | Duration in seconds |

---

## Image Upload Chunking

All image output commands split JPEG payloads across multiple 1024-byte HID
output reports. The procedure:

1. Encode the image as JPEG bytes.
2. Apply required rotation (per device) **before** JPEG encoding.
3. Split the JPEG bytes into chunks. Max chunk data size depends on the
   command header size (see each command above).
4. For each chunk, build a 1024-byte report:
   - Write the command header with the chunk index and chunk data size.
   - Set "Transfer is Done" flag to `0x01` on the **last** chunk only.
   - Copy chunk data after the header.
   - Pad the remainder of the 1024-byte report with `0x00`.
5. Send each report via HID WRITE.

---

## Input Polling

The host polls the device for input reports using HID READ with a timeout.
Recommended polling interval: **50ms**. A timeout return indicates no event
is pending. When an event is pending, a 512-byte input report is returned.

The command byte at offset 0x01 determines the event type:

| Command | Event | Devices |
|---|---|---|
| `0x00` | Key/Button press state change | All |
| `0x02` | Touch screen activity | Plus, Plus XL |
| `0x03` | Encoder state change | Plus, Plus XL |

---

## Device Lifecycle

1. **Enumerate** — List HID devices with VID `0x0FD9` and a known PID.
2. **Open** — Open the HID device by path.
3. **Identify** — Read serial number (report `0x06`) and unit information
   (report `0x08`).
4. **Configure** — Set brightness, sleep duration, etc.
5. **Operate** — Poll for input events, send images.
6. **Close** — Optionally show logo (report `0x03` cmd `0x02`), then close
   the HID handle.
