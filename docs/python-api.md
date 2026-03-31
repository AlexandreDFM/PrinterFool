# HZTZPrinter — Python Library API Reference

Python 3.9+ required. Add the project root to `sys.path`, then import from `src.*`.

## 1. Import

```python
import sys
sys.path.insert(0, "/path/to/HZTZPrinter")

from src.printer import ZJ8360Printer, list_usb_devices
from src.template_system import TemplateBuilder, TicketTemplate, FieldReference, FieldSelector, ItemLayout
from src.ticket_renderer import TicketRenderer, TicketPrinter, PrinterConfig
from src.qrcode_generator import QRCodeGenerator
```

## 2. `ZJ8360Printer`

Low-level USB driver. All methods return `bool` (True = success).

```python
printer = ZJ8360Printer(vendor_id=0x0416, product_id=0x5011, paper_width=48)
# paper_width: 32 / 40 / 48 characters

printer.connect()                                    # -> bool
printer.disconnect()                                 # -> None  (always call in finally)
printer.print_text(text: str)                        # -> bool
printer.print_line(char="-", width=None)             # -> bool
printer.print_centered(text: str)                    # -> bool
printer.set_bold(enable: bool)                       # -> bool
printer.set_font_size(height: int, width: int)       # -> bool  (1–8 each)
printer.set_alignment("left" | "center" | "right")  # -> bool
printer.feed_paper(lines: int)                       # -> bool
printer.cut_paper()                                  # -> bool
```

> Always wrap usage in `try/finally` to guarantee `disconnect()` is called.

## 3. `PrinterConfig`

```python
config = PrinterConfig(
    paper_width=40,      # characters per line (default: 40)
    bold_titles=True,    # surround title with "===" lines
    center_header=True,  # center header lines
    center_title=True,   # center title line
    line_separator="-",  # character used for rule lines
    wrap_text=True,      # word-wrap long lines
)
```

## 4. `TicketRenderer`

Renders a `TicketTemplate` to a plain-text string. No hardware required.

```python
renderer = TicketRenderer(template, config=PrinterConfig())

text: str = renderer.render_to_text(data, printer_safe=False)
# printer_safe=False  Unicode block art QR — accurate, scannable on screen (default)
# printer_safe=True   ASCII-safe output — replaces €, ©, smart quotes, etc.
```

## 5. `TicketPrinter`

High-level wrapper: renders a template and writes it to hardware.

```python
tp = TicketPrinter(printer, template, config=PrinterConfig())

tp.print_formatted_ticket(data, cut_paper=True, feed_lines=3)  # -> bool
# Sends text body first, then the native ESC Z QR command when
# data["qr_code"]["value"] is present.

tp.print_ticket(data, cut_paper=True, feed_lines=3)            # -> bool
# Text-only variant — QR rendered inline as ASCII art.
```

## 6. `QRCodeGenerator`

```python
qr = QRCodeGenerator(error_correction="M", paper_width=40)
# error_correction: "L" | "M" | "Q" | "H"

qr.generate_ascii_art(data: str)            -> str          # Unicode █ art, scannable from screen
qr.generate_printer_safe_ascii(data: str)   -> str          # "#" art, preview only
qr.generate_image(data, size=MEDIUM)        -> bytes | None # PNG image bytes
qr.generate_escpos_image(data, size=MEDIUM) -> bytes | None # ESC/POS raster command
qr.generate_native_qr_command(data, version=0, ec_level="M", component=8) -> bytes | None
# component=8 (default) → larger printed modules; ESC Z native command

# Size constants (pixels)
QRCodeGenerator.TINY   = (32,  32)
QRCodeGenerator.SMALL  = (48,  48)
QRCodeGenerator.MEDIUM = (96,  96)
QRCodeGenerator.LARGE  = (144, 144)
```

## 7. `TemplateBuilder`

```python
template = TemplateBuilder.create_event_template(name="Event Ticket")
template = TemplateBuilder.create_receipt_template(name="Receipt")
```

**Event template** data keys:
`event.name`, `event.date`, `event.time`, `venue.name`, `venue.address`,
`seat.section`, `seat.row`, `seat.seat`, `seat.gate`, `barcode.value`, `holder.name`

**Receipt template** data keys:
`merchant.name`, `merchant.address`, `order.commande_number`, `order.ticket_number`,
`transaction.date`, `transaction.hour`, `transaction.type`, `order.caisse_number`,
`staff.seller`, `items[]`, `totals{}`, `qr_code.value`, `footer.message`

### Template selection heuristic

```python
def detect_template(data):
    sample = data[0] if isinstance(data, list) else data
    if {"merchant", "order", "items", "totals"} & set(sample):
        return "receipt"
    return "event"
```

## 8. Example: Terminal Preview

```python
from src.template_system import TemplateBuilder
from src.ticket_renderer import TicketRenderer, PrinterConfig

template = TemplateBuilder.create_event_template()
renderer = TicketRenderer(template, PrinterConfig(paper_width=48))

data = {
    "event":   {"name": "Summer Concert", "date": "July 15, 2026", "time": "8:00 PM"},
    "venue":   {"name": "Central Park", "address": "123 Central Park, NY"},
    "seat":    {"section": "A", "row": "5", "seat": "12", "gate": "North"},
    "barcode": {"value": "EVT00012345"},
    "holder":  {"name": "John Doe"},
}
print(renderer.render_to_text(data))
```

## 9. Example: Print to Hardware

```python
from src.printer import ZJ8360Printer
from src.template_system import TemplateBuilder
from src.ticket_renderer import TicketPrinter, PrinterConfig

template = TemplateBuilder.create_receipt_template()
printer  = ZJ8360Printer(paper_width=48)

if not printer.connect():
    raise RuntimeError("Printer not found")

try:
    tp = TicketPrinter(printer, template, PrinterConfig(paper_width=48))
    tp.print_formatted_ticket(receipt_data)
finally:
    printer.disconnect()
```

## 10. Example: Batch Printing

```python
printer = ZJ8360Printer()
if not printer.connect():
    raise RuntimeError("Printer not found")

try:
    tp = TicketPrinter(printer, template, config)
    for ticket in tickets:
        tp.print_formatted_ticket(ticket, cut_paper=True)
finally:
    printer.disconnect()
```

## 11. `list_usb_devices`

Prints a table of all connected USB devices to stdout. Use this to find
the correct `vendor_id` and `product_id` for your hardware.

```python
from src.printer import list_usb_devices
list_usb_devices()
```