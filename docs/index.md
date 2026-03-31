# HZTZPrinter

Python interface for the **ZJ-8360** USB thermal ticket printer.  
Version 1.0.0 · Python 3 · USB (Vendor `0x0416` / Product `0x5011`)

---

## Overview

HZTZPrinter provides two ways to drive the ZJ-8360 printer:

| Mode | How to use | Entry point |
|---|---|---|
| **CLI** | Direct commands from the terminal | `fool_printer.py` / `fool_printer` |
| **API Server** | HTTP server (Flask) for remote/programmatic access | `serve` command → `http://localhost:8360/api/` |

Both modes share the same template engine, renderer, and USB driver underneath.

---

## ⚡ Quick Start

| Goal | Command |
|---|---|
| Preview a ticket in the terminal | `python fool_printer.py preview -j templates/sample_event_ticket.json` |
| Print a ticket to the printer | `python fool_printer.py print -j templates/sample_event_ticket.json` |
| Start the API server | `python fool_printer.py serve` |

No printer is required for `preview`, `qr` (ASCII output), `test`, or API server dry-runs.

---

## CLI Commands

| Command | Description |
|---|---|
| `print` | Print ticket(s) from a JSON file to the thermal printer |
| `preview` | Render ticket(s) as formatted text in the terminal |
| `qr` | Generate QR codes (ASCII art or PNG) |
| `list-usb` | Enumerate all connected USB devices |
| `test` | Run the self-test suite (13 tests, no printer needed) |
| `serve` | Start the Flask HTTP API server |

→ Full reference: [cli.md](cli.md)

---

## 🌐 API Server

The server reads its port from `.env`:

```ini
HZTZ_PORT=8360   # default — matches the printer model number
```

**Base URL:** `http://localhost:8360/api/`

Available endpoints:

| Endpoint | Purpose |
|---|---|
| `GET  /api/health` | Health check |
| `GET  /api/templates` | List available templates |
| `POST /api/preview` | Render ticket(s) as text |
| `POST /api/print` | Send ticket(s) to the printer |
| `POST /api/qr` | Generate a QR code |
| `GET  /api/usb` | List connected USB devices |
| `GET  /api/test` | Run the self-test suite |

→ Full reference: [api.md](api.md)

---

## Project Layout

```
HZTZPrinter/
├── fool_printer.py          # Main CLI entry point
├── fool_printer              # Executable wrapper script
├── requirements.txt
├── .env                      # Port & debug config (not committed)
├── .env.example              # Template for .env
├── templates/
│   ├── sample_event_ticket.json
│   ├── sample_multiple_tickets.json
│   ├── sample_receipt.json
│   ├── sample_student_attendence_1.json
│   ├── sample_student_attendence_2.json
│   ├── sample_qr.json
│   └── ticket-design.txt
├── src/
│   ├── __init__.py
│   ├── printer.py            # ZJ8360Printer USB driver
│   ├── template_system.py    # TicketTemplate, TemplateBuilder, etc.
│   ├── ticket_renderer.py    # TicketRenderer, TicketPrinter, PrinterConfig
│   ├── qrcode_generator.py   # QRCodeGenerator
│   └── api_server.py         # Flask API server (create_app, run_tests)
└── docs/
    ├── index.md              ← you are here
    ├── installation.md
    ├── cli.md
    ├── api.md
    ├── python-api.md
    ├── templates.md
    └── json-schemas.md
```

---

## Hardware

| Property | Value |
|---|---|
| Model | ZJ-8360 |
| Interface | USB |
| Vendor ID | `0x0416` |
| Product ID | `0x5011` |

---

## 📚 Documentation

| Page | Contents |
|---|---|
| [installation.md](installation.md) | Setup, virtual environment, USB permissions, `.env` configuration |
| [cli.md](cli.md) | All CLI commands, flags, and usage examples |
| [api.md](api.md) | HTTP API reference — endpoints, request/response schemas, examples |
| [python-api.md](python-api.md) | Python library API — classes, methods, and usage examples |
| [templates.md](templates.md) | Template system, built-in templates, creating custom templates |
| [json-schemas.md](json-schemas.md) | JSON data schemas for event tickets and receipts |