# HZTZPrinter — HTTP API Reference

> **Version 1.0.0** · ZJ-8360 Thermal Ticket Printer · Flask server mode

This document covers every HTTP endpoint exposed by `python fool_printer.py serve`.  
For the **Python library API** see [python-api.md](python-api.md).  
For **CLI usage** see [cli.md](cli.md).

---

## Contents

- [Starting the server](#starting-the-server)
- [Base URL](#base-url)
- [CORS](#cors)
- [Response envelope](#response-envelope)
- [Endpoints](#endpoints)
  - [GET /api/health](#get-apihealth)
  - [GET /api/templates](#get-apitemplates)
  - [POST /api/preview](#post-apipreview)
  - [POST /api/print](#post-apiprint)
  - [POST /api/qr](#post-apiqr)
  - [GET /api/usb](#get-apiusb)
  - [GET /api/test](#get-apitest)
- [Error reference](#error-reference)
- [Code examples](#code-examples)

---

## Starting the server

```sh
# Default port — reads HZTZ_PORT from .env, falls back to 8360
python fool_printer.py serve

# Explicit port
python fool_printer.py serve --port 9000

# Enable Flask debug mode (auto-reload + verbose error pages)
python fool_printer.py serve --debug
```

**Port resolution order:**

1. `--port` CLI flag
2. `HZTZ_PORT` variable in `.env`
3. Hardcoded default: **`8360`** (matches the ZJ-8360 model number)

Press **Ctrl+C** to stop the server.

---

## Base URL

```
http://localhost:{PORT}/api/
```

Example with the default port: `http://localhost:8360/api/`

---

## CORS

`flask-cors` is applied globally to the Flask application — **all origins are
accepted** (`Access-Control-Allow-Origin: *`). No preflight configuration is
required for browser clients.

---

## Response envelope

Every endpoint — success or failure — returns JSON with the following outermost
shape.

**Success:**

```json
{ "ok": true, "...payload fields...": "..." }
```

**Error:**

```json
{ "ok": false, "error": "human-readable message" }
```

The `ok` field is always a boolean. Additional payload fields are merged at the
top level (not nested inside a separate `data` key). The HTTP status code always
reflects the outcome independently of `ok`.

---

## Endpoints

---

## GET /api/health

Liveness probe. Returns `200` as long as the server process is running. Does
**not** require the printer to be connected or detected.

**Request:** none

**Response `200`:**

```json
{
  "ok": true,
  "status": "ok",
  "version": "1.0.0",
  "printer": {
    "vendor_id": "0x416",
    "product_id": "0x5011"
  }
}
```

---

## GET /api/templates

Returns the names of all available templates and every accepted option value
that can be passed to other endpoints. Use this to discover valid inputs without
consulting the documentation.

**Request:** none

**Response `200`:**

```json
{
  "ok": true,
  "templates": ["event", "receipt"],
  "paper_widths": [32, 40, 48],
  "ec_levels": ["L", "M", "Q", "H"],
  "qr_formats": ["ascii", "printer", "png"],
  "qr_sizes": ["tiny", "small", "medium", "large"]
}
```

---

## POST /api/preview

Renders one or more tickets to plain text **without connecting to the printer**.
Useful for validating ticket data, debugging layouts, and building web UIs that
show a live preview before printing.

**Content-Type:** `application/json`

**Request body:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `data` | object or array | ✅ | — | Single ticket object or array of ticket objects |
| `template` | string | — | auto-detected | `"event"` or `"receipt"` |
| `paper_width` | integer | — | `48` | Characters per line: `32`, `40`, or `48` |
| `printer_safe` | boolean | — | `false` | Replace Unicode characters (e.g. `█`, `—`, `©`) with ASCII equivalents to match actual printer output |

> **Template auto-detection:** the server inspects the top-level keys of the
> first ticket. If any of `merchant`, `order`, `items`, or `totals` are present
> it selects `"receipt"`; otherwise it falls back to `"event"`.

**Response `200`:**

```json
{
  "ok": true,
  "template": "event",
  "paper_width": 48,
  "printer_safe": false,
  "count": 1,
  "previews": [
    "...rendered text for ticket 1...",
    "...rendered text for ticket 2..."
  ]
}
```

`previews` is always an array, even when a single ticket object was submitted.
`count` equals `previews.length`.

**Errors:**

- `400` — `data` field is missing from the request body
- `400` — `template` value is not `"event"` or `"receipt"`
- `400` — `paper_width` value is not `32`, `40`, or `48`

---

## POST /api/print

Sends one or more tickets to the ZJ-8360 thermal printer over USB.

**Content-Type:** `application/json`

**Request body:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `data` | object or array | ✅ | — | Single ticket object or array of ticket objects |
| `template` | string | — | auto-detected | `"event"` or `"receipt"` |
| `paper_width` | integer | — | `48` | Characters per line: `32`, `40`, or `48` |
| `no_cut` | boolean | — | `false` | Skip the automatic paper cut after each ticket |
| `feed_lines` | integer | — | `3` | Number of blank lines to feed before the cut |

**Response `200`:**

```json
{
  "ok": true,
  "printed": 3,
  "template": "event",
  "paper_width": 48
}
```

`printed` is the count of tickets that were successfully sent to the printer. On
partial success the endpoint returns `500` (see below) instead of `200`.

**Errors:**

- `400` — `data` field is missing from the request body
- `400` — `template` value is not `"event"` or `"receipt"`
- `400` — `paper_width` value is not `32`, `40`, or `48`
- `400` — `feed_lines` is not a valid integer
- `503` — printer not found or not connected via USB
- `500` — one or more tickets failed to print; the `error` string includes a
  `failed/total` summary (e.g. `"2/3 ticket(s) failed: ticket 2 failed; ticket 3 failed"`)

---

## POST /api/qr

Generates a QR code. Returns JSON containing ASCII art for `ascii` and `printer`
formats, or a raw PNG binary for the `png` format.

**Content-Type:** `application/json`

**Request body:**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `data` | string | ✅ | — | Text or URL to encode |
| `format` | string | — | `"ascii"` | `"ascii"` (Unicode █ blocks, scannable from screen), `"printer"` (`#` characters, preview-only), or `"png"` |
| `ec_level` | string | — | `"M"` | Error-correction level: `"L"` (7%), `"M"` (15%), `"Q"` (25%), `"H"` (30%) |
| `size` | string | — | `"medium"` | PNG output size — ignored for `ascii`/`printer` formats |

**PNG sizes:**

| Value | Pixels |
|---|---|
| `"tiny"` | 32 × 32 |
| `"small"` | 48 × 48 |
| `"medium"` | 96 × 96 |
| `"large"` | 144 × 144 |

**Response `200` — `ascii` or `printer` format:**

```json
{
  "ok": true,
  "data": "https://example.com",
  "format": "ascii",
  "ec_level": "M",
  "lines": 25,
  "art": "...multiline QR art string..."
}
```

`lines` is the number of newline-separated rows in `art`.

**Response `200` — `png` format:**

Binary PNG image. `Content-Type: image/png`.  
Use `--output qr.png` in curl, or write `response.content` to a file in Python.
The JSON envelope is **not** present — the body is raw image bytes.

**Errors:**

- `400` — `data` field is missing or empty
- `400` — `format` is not `"ascii"`, `"printer"`, or `"png"`
- `400` — `ec_level` is not `"L"`, `"M"`, `"Q"`, or `"H"`
- `400` — `size` is not `"tiny"`, `"small"`, `"medium"`, or `"large"`
- `500` — QR generation failed internally

---

## GET /api/usb

Enumerates all connected USB devices and flags the ZJ-8360 printer among them.
Requires `pyusb` to be installed on the server.

**Request:** none

**Response `200`:**

```json
{
  "ok": true,
  "count": 8,
  "printer_detected": true,
  "devices": [
    {
      "vendor_id": "0x416",
      "product_id": "0x5011",
      "manufacturer": "Zjiang",
      "is_printer": true
    },
    {
      "vendor_id": "0x5ac",
      "product_id": "0x8289",
      "manufacturer": "Apple Inc.",
      "is_printer": false
    }
  ]
}
```

`count` is the total number of USB devices found.  
`printer_detected` is `true` when at least one device matches vendor `0x0416` /
product `0x5011`.  
`is_printer` is `true` only for the device matching those IDs.  
`manufacturer` may be `null` if the device does not expose a manufacturer string.

**Errors:**

- `500` — `pyusb` is not installed on the server

---

## GET /api/test

Runs 13 built-in self-tests and returns structured results. **No printer
required.** All tests exercise the template engine, renderer, and QR generator
in memory.

Also callable as `POST /api/test` for convenience (the body is ignored).

**Request:** none

**Response `200` — all tests pass:**

```json
{
  "ok": true,
  "passed": 13,
  "failed": 0,
  "total": 13,
  "results": [
    { "name": "Module imports",                    "status": "pass", "detail": "" },
    { "name": "Event template creation",           "status": "pass", "detail": "2 card rows" },
    { "name": "Receipt template creation",         "status": "pass", "detail": "" },
    { "name": "Field reference resolution",        "status": "pass", "detail": "value=Summer Concert" },
    { "name": "Fallback field resolution",         "status": "pass", "detail": "value=Fallback Value" },
    { "name": "Row rendering",                     "status": "pass", "detail": "..." },
    { "name": "Empty field handling",              "status": "pass", "detail": "..." },
    { "name": "Full ticket text rendering",        "status": "pass", "detail": "512 chars" },
    { "name": "QR code ASCII generation",          "status": "pass", "detail": "25 lines" },
    { "name": "QR code printer-safe generation",   "status": "pass", "detail": "" },
    { "name": "QR native ESC Z command",           "status": "pass", "detail": "18 bytes" },
    { "name": "QR PNG image generation",           "status": "pass", "detail": "1234 bytes" },
    { "name": "Sample JSON loading",               "status": "pass", "detail": "keys=[...]" }
  ]
}
```

**Response `207 Multi-Status` — one or more tests fail:**

Same shape as above, but `failed > 0` and the failing entries have
`"status": "fail"`. The `ok` field remains `true` — `207` signals partial
success, not an API-level failure.

**HTTP status codes:**

| Code | Condition |
|---|---|
| `200` | All 13 tests passed |
| `207` | At least one test failed (`failed > 0`) |

---

## Error reference

| HTTP | Meaning |
|---|---|
| `200` | Success |
| `207` | Multi-Status — test endpoint only: some self-tests failed |
| `400` | Bad request — missing or invalid parameters |
| `404` | Endpoint not found |
| `405` | Method not allowed |
| `500` | Server error or internal failure |
| `503` | Printer not connected |

`404` and `405` responses include a list of all valid routes in the `error`
string. All error responses follow the standard envelope:

```json
{ "ok": false, "error": "human-readable message" }
```

---

## Code examples

All examples target the default port `8360`. Substitute your port if you started
the server with `--port`.

### Sample event ticket

The following ticket object is used in the preview and print examples below.

```json
{
  "event":   { "name": "Summer Concert", "date": "July 15, 2026", "time": "8:00 PM" },
  "venue":   { "name": "Central Park", "address": "123 Central Park, NY" },
  "seat":    { "section": "A", "row": "5", "seat": "12", "gate": "North" },
  "barcode": { "value": "EVT00012345" },
  "holder":  { "name": "Jane Doe" }
}
```

---

### GET /api/health

<details>
<summary>curl</summary>

```sh
curl http://localhost:8360/api/health
```

</details>

<details>
<summary>Python (requests)</summary>

```python
import requests

resp = requests.get("http://localhost:8360/api/health")
body = resp.json()
print(body["status"])   # "ok"
print(body["version"])  # "1.0.0"
```

</details>

<details>
<summary>JavaScript (fetch)</summary>

```js
const resp = await fetch("http://localhost:8360/api/health");
const body = await resp.json();
console.log(body.status);   // "ok"
console.log(body.version);  // "1.0.0"
```

</details>

---

### POST /api/preview

<details>
<summary>curl</summary>

```sh
curl -X POST http://localhost:8360/api/preview \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "event":   { "name": "Summer Concert", "date": "July 15, 2026", "time": "8:00 PM" },
      "venue":   { "name": "Central Park", "address": "123 Central Park, NY" },
      "seat":    { "section": "A", "row": "5", "seat": "12", "gate": "North" },
      "barcode": { "value": "EVT00012345" },
      "holder":  { "name": "Jane Doe" }
    },
    "paper_width": 48
  }'
```

</details>

<details>
<summary>Python (requests)</summary>

```python
import requests

ticket = {
    "event":   {"name": "Summer Concert", "date": "July 15, 2026", "time": "8:00 PM"},
    "venue":   {"name": "Central Park", "address": "123 Central Park, NY"},
    "seat":    {"section": "A", "row": "5", "seat": "12", "gate": "North"},
    "barcode": {"value": "EVT00012345"},
    "holder":  {"name": "Jane Doe"},
}

resp = requests.post(
    "http://localhost:8360/api/preview",
    json={"data": ticket, "paper_width": 48},
)
body = resp.json()
if body["ok"]:
    print(body["previews"][0])
else:
    print(f"Error: {body['error']}")
```

</details>

<details>
<summary>JavaScript (fetch)</summary>

```js
const ticket = {
  event:   { name: "Summer Concert", date: "July 15, 2026", time: "8:00 PM" },
  venue:   { name: "Central Park", address: "123 Central Park, NY" },
  seat:    { section: "A", row: "5", seat: "12", gate: "North" },
  barcode: { value: "EVT00012345" },
  holder:  { name: "Jane Doe" },
};

const resp = await fetch("http://localhost:8360/api/preview", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ data: ticket, paper_width: 48 }),
});
const body = await resp.json();
if (body.ok) {
  console.log(body.previews[0]);
} else {
  console.error(`Error: ${body.error}`);
}
```

</details>

---

### POST /api/print

<details>
<summary>curl</summary>

```sh
curl -X POST http://localhost:8360/api/print \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "event":   { "name": "Summer Concert", "date": "July 15, 2026", "time": "8:00 PM" },
      "venue":   { "name": "Central Park", "address": "123 Central Park, NY" },
      "seat":    { "section": "A", "row": "5", "seat": "12", "gate": "North" },
      "barcode": { "value": "EVT00012345" },
      "holder":  { "name": "Jane Doe" }
    }
  }'
```

</details>

<details>
<summary>Python (requests)</summary>

```python
import requests

ticket = {
    "event":   {"name": "Summer Concert", "date": "July 15, 2026", "time": "8:00 PM"},
    "venue":   {"name": "Central Park", "address": "123 Central Park, NY"},
    "seat":    {"section": "A", "row": "5", "seat": "12", "gate": "North"},
    "barcode": {"value": "EVT00012345"},
    "holder":  {"name": "Jane Doe"},
}

resp = requests.post(
    "http://localhost:8360/api/print",
    json={"data": ticket},
)
body = resp.json()
if body["ok"]:
    print(f"Printed {body['printed']} ticket(s)")
else:
    print(f"Error ({resp.status_code}): {body['error']}")
```

</details>

<details>
<summary>JavaScript (fetch)</summary>

```js
const ticket = {
  event:   { name: "Summer Concert", date: "July 15, 2026", time: "8:00 PM" },
  venue:   { name: "Central Park", address: "123 Central Park, NY" },
  seat:    { section: "A", row: "5", seat: "12", gate: "North" },
  barcode: { value: "EVT00012345" },
  holder:  { name: "Jane Doe" },
};

const resp = await fetch("http://localhost:8360/api/print", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ data: ticket }),
});
const body = await resp.json();
if (body.ok) {
  console.log(`Printed ${body.printed} ticket(s)`);
} else {
  console.error(`Error ${resp.status}: ${body.error}`);
}
```

</details>

---

### POST /api/qr — ASCII art

<details>
<summary>curl</summary>

```sh
curl -X POST http://localhost:8360/api/qr \
  -H "Content-Type: application/json" \
  -d '{"data": "https://example.com", "format": "ascii", "ec_level": "M"}'
```

</details>

<details>
<summary>Python (requests)</summary>

```python
import requests

resp = requests.post(
    "http://localhost:8360/api/qr",
    json={"data": "https://example.com", "format": "ascii", "ec_level": "M"},
)
body = resp.json()
if body["ok"]:
    print(f"QR code ({body['lines']} lines):")
    print(body["art"])
else:
    print(f"Error: {body['error']}")
```

</details>

<details>
<summary>JavaScript (fetch)</summary>

```js
const resp = await fetch("http://localhost:8360/api/qr", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    data: "https://example.com",
    format: "ascii",
    ec_level: "M",
  }),
});
const body = await resp.json();
if (body.ok) {
  console.log(`QR code (${body.lines} lines):`);
  console.log(body.art);
} else {
  console.error(`Error: ${body.error}`);
}
```

</details>

---

### POST /api/qr — PNG image

<details>
<summary>curl</summary>

```sh
curl -X POST http://localhost:8360/api/qr \
  -H "Content-Type: application/json" \
  -d '{"data": "https://example.com", "format": "png", "size": "medium"}' \
  --output qr.png
```

</details>

<details>
<summary>Python (requests)</summary>

```python
import requests

resp = requests.post(
    "http://localhost:8360/api/qr",
    json={"data": "https://example.com", "format": "png", "size": "medium"},
)
if resp.status_code == 200 and resp.headers["Content-Type"] == "image/png":
    with open("qr.png", "wb") as f:
        f.write(resp.content)
    print(f"Saved qr.png ({len(resp.content)} bytes)")
else:
    print(f"Error: {resp.json()['error']}")
```

</details>

<details>
<summary>JavaScript (fetch) — browser, save as download</summary>

```js
const resp = await fetch("http://localhost:8360/api/qr", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    data: "https://example.com",
    format: "png",
    size: "medium",
  }),
});

if (resp.ok) {
  const blob = await resp.blob();                   // image/png
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = "qr.png";
  a.click();
  URL.revokeObjectURL(url);
} else {
  const body = await resp.json();
  console.error(`Error: ${body.error}`);
}
```

</details>

<details>
<summary>JavaScript (fetch) — Node.js, write to disk</summary>

```js
import { writeFileSync } from "fs";

const resp = await fetch("http://localhost:8360/api/qr", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    data: "https://example.com",
    format: "png",
    size: "medium",
  }),
});

if (resp.ok) {
  const buffer = Buffer.from(await resp.arrayBuffer());
  writeFileSync("qr.png", buffer);
  console.log(`Saved qr.png (${buffer.length} bytes)`);
} else {
  const body = await resp.json();
  console.error(`Error: ${body.error}`);
}
```

</details>