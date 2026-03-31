"""
HZTZPrinter - ZJ-8360 Thermal Ticket Printer Python Interface

A complete toolkit for controlling the ZJ-8360 thermal ticket printer
via USB, with template-based ticket rendering and QR code support.
"""

from .printer import ZJ8360Printer, list_usb_devices
from .template_system import (
    TicketTemplate,
    TemplateBuilder,
    TemplateRow,
    ItemLayout,
    Field,
    FieldReference,
    FieldSelector,
    DetailItem,
    BarcodeSection,
)
from .ticket_renderer import (
    TicketRenderer,
    TicketPrinter,
    PrinterConfig,
    make_printer_safe,
)
from .qrcode_generator import (
    QRCodeGenerator,
    get_qr_code_ascii,
    get_qr_code_image,
    get_qr_code_escpos,
)
from .api_server import create_app, run_tests

__version__ = "1.0.0"

# API server

__all__ = [
    # Printer
    "ZJ8360Printer",
    "list_usb_devices",
    # Templates
    "TicketTemplate",
    "TemplateBuilder",
    "TemplateRow",
    "ItemLayout",
    "Field",
    "FieldReference",
    "FieldSelector",
    "DetailItem",
    "BarcodeSection",
    # Rendering
    "TicketRenderer",
    "TicketPrinter",
    "PrinterConfig",
    "make_printer_safe",
    # QR Codes
    "QRCodeGenerator",
    "get_qr_code_ascii",
    "get_qr_code_image",
    "get_qr_code_escpos",
    # API Server
    "create_app",
    "run_tests",
]
