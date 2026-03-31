# HZTZPrinter CLI Reference

> **Version 1.0.0** · ZJ-8360 Thermal Ticket Printer

---

## Entry Point

```sh
python fool_printer.py [GLOBAL_FLAGS] COMMAND [ARGS]
```

Or via the executable wrapper:

```sh
./fool_printer COMMAND [ARGS]
```

---

## Global Flags

These flags must appear **before** the command name.

| Flag | Description |
|---|---|
| `-V, --version` | Show version (`1.0.0`) and exit |
| `-v, --verbose` | Enable DEBUG logging |
| `-q, --quiet` | Suppress INFO output — only WARNING and above are shown |
| `-h, --help` | Show help and exit |

---

## Commands

### `print`

Send ticket(s) from a JSON file to the thermal printer.

```sh
python fool_printer.py print -j FILE [OPTIONS]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `-j, --json FILE` | `path` | *(required)* | Path to JSON file containing ticket data (single object or array) |
| `-t, --template` | `{event,receipt}` | auto-detected | Template to use; inferred from data keys when omitted |
| `--paper-width` | `{32,40,48}` | `48` | Paper width in characters: `32` = 80 mm, `40` = std, `48` = 96 mm |
| `--no-cut` | flag | `false` | Do not cut paper after printing |
| `--feed-lines N` | `int` | `3` | Blank lines to feed before cutting |

**Exit codes:** `0` on success · `1` if the printer connection fails or any ticket fails to print.

**Examples:**

```sh
python fool_printer.py print -j templates/sample_event_ticket.json
python fool_printer.py print -j data.json -t receipt --paper-width 48
python fool_printer.py print -j tickets.json -t event --no-cut --feed-lines 5
```

---

### `preview`

Render ticket(s) as formatted text in the terminal. No printer required.

```sh
python fool_printer.py preview -j FILE [OPTIONS]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `-j, --json FILE` | `path` | *(required)* | Path to JSON file (single object or array) |
| `-t, --template` | `{event,receipt}` | auto-detected | Template override; inferred from data keys when omitted |
| `--paper-width` | `{32,40,48}` | `48` | Paper width in characters |
| `--printer-safe` | flag | `false` | Use ASCII-safe characters to match actual printer output (e.g. `€` → `$`, `—` → `--`) |

**Examples:**

```sh
python fool_printer.py preview -j templates/sample_event_ticket.json
python fool_printer.py preview -j templates/sample_receipt.json -t receipt
python fool_printer.py preview -j data.json --paper-width 32 --printer-safe
```

---

### `qr`

Generate a QR code from inline text or from the `qr_code.value` / `barcode.value`
field of a JSON file. Outputs ASCII art to the terminal or saves a PNG file.

```sh
python fool_printer.py qr (-d TEXT | -j FILE) [OPTIONS]
```

`-d / --data` and `-j / --json` are **mutually exclusive**; exactly one is required.

#### Source flags

| Flag | Type | Default | Description |
|---|---|---|---|
| `-d, --data TEXT` | `string` | — | Text or URL to encode directly |
| `-j, --json FILE` | `path` | — | Read QR data from the first ticket's `qr_code.value` or `barcode.value` |

#### Output flags

| Flag | Type | Default | Description |
|---|---|---|---|
| `-o, --output FILE` | `path` | — | Save QR code as PNG; omit to display ASCII art in the terminal |
| `--format` | `{ascii,printer}` | `ascii` | Terminal art style: `ascii` uses Unicode █ blocks, `printer` uses `#` characters |
| `--ec-level` | `{L,M,Q,H}` | `M` | Error-correction level: `L` = 7 %, `M` = 15 %, `Q` = 25 %, `H` = 30 % |
| `--size` | `{tiny,small,medium,large}` | `medium` | PNG output size (only relevant with `-o`) |

#### PNG sizes

| Value | Pixels |
|---|---|
| `tiny` | 32 × 32 |
| `small` | 48 × 48 |
| `medium` | 96 × 96 |
| `large` | 144 × 144 |

**Examples:**

```sh
python fool_printer.py qr -d "https://example.com"
python fool_printer.py qr -d "TICKET-42" -o qr.png --size large
python fool_printer.py qr -d "DATA" --format printer --ec-level H
python fool_printer.py qr -j templates/sample_qr.json
```

---

### `list-usb`

Print a table of all connected USB devices. Useful for verifying the printer is
detected and for obtaining its vendor and product IDs.

```sh
python fool_printer.py list-usb
```

No additional flags.

Expected output line for the ZJ-8360:

```
Vendor: 0x416  | Product: 0x5011 | Manufacturer: Zjiang
```

---

### `test`

Run 13 built-in self-tests. No printer required.

```sh
python fool_printer.py test
```

No additional flags.

**Tests covered:**

| # | Test |
|---|---|
| 1 | Module imports |
| 2 | Event template creation |
| 3 | Receipt template creation |
| 4 | Field reference resolution |
| 5 | Fallback resolution |
| 6 | Row rendering |
| 7 | Empty field handling |
| 8 | Full ticket rendering |
| 9 | QR ASCII generation |
| 10 | QR printer-safe generation |
| 11 | QR native ESC Z command |
| 12 | QR PNG generation |
| 13 | Sample JSON loading |

**Exit codes:** `0` if all tests pass · `1` if any test fails.

---

### `serve` *(new)*

Start the HTTP REST API server that exposes all printer functionalities over HTTP.

```sh
python fool_printer.py serve [OPTIONS]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--port PORT` | `int` | `8360` | TCP port to listen on (overrides `HZTZ_PORT` in `.env`) |
| `--debug` | flag | `false` | Enable Flask debug mode (auto-reload, verbose error pages) |

#### Port resolution order

1. `--port` CLI flag
2. `HZTZ_PORT` variable in `.env`
3. Hardcoded default: **`8360`**

Once started, the API is available at:

```
http://localhost:{PORT}/api/
```

Press **Ctrl+C** to stop the server.

**Examples:**

```sh
python fool_printer.py serve
python fool_printer.py serve --port 9000
python fool_printer.py serve --port 8080 --debug
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Error — invalid arguments, printer failure, or test failure |
