#!/usr/bin/env python3
"""
HZTZPrinter - ZJ-8360 Thermal Ticket Printer CLI

Unified command-line interface for the ZJ-8360 thermal ticket printer.
Supports printing from JSON templates, previewing output, generating
QR codes, listing USB devices, and running diagnostics.

Usage:
    python fool_printer.py print -j data.json -t event
    python fool_printer.py preview -j data.json -t receipt
    python fool_printer.py qr -d "https://example.com"
    python fool_printer.py list-usb
    python fool_printer.py test
    python fool_printer.py serve
    python fool_printer.py serve --port 9000
"""

import sys
import os
import json
import argparse
import logging
import textwrap
from typing import Dict, List, Union

# ---------------------------------------------------------------------------
# Path setup – ensure the src/ package is importable regardless of cwd
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# Load .env (if present) before anything else so HZTZ_* vars are available.
# Falls back silently if python-dotenv is not installed.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(_SCRIPT_DIR, ".env"))
except ImportError:
    pass  # python-dotenv not installed — set env vars manually if needed

from src.printer import ZJ8360Printer, list_usb_devices
from src.template_system import (
    TemplateBuilder,
    TicketTemplate,
    FieldReference,
    FieldSelector,
    ItemLayout,
    TemplateRow,
)
from src.ticket_renderer import TicketRenderer, TicketPrinter, PrinterConfig
from src.qrcode_generator import QRCodeGenerator

__version__ = "1.0.0"

TEMPLATE_TYPES: Dict[str, callable] = {
    "event": TemplateBuilder.create_event_template,
    "receipt": TemplateBuilder.create_receipt_template,
    "attendance": TemplateBuilder.create_attendance_template,
    "poisson": TemplateBuilder.create_poisson_template,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure root logging based on CLI flags."""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(level=level, format="%(levelname)-8s %(message)s")


def _load_json(path: str) -> Union[dict, list]:
    """Load and parse a JSON file, exit on error."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(f"  Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"  Error: invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)


def _resolve_path(path: str) -> str:
    """Resolve *path* relative to the script directory or templates/ folder."""
    if os.path.isabs(path) or os.path.exists(path):
        return path
    for prefix in (_SCRIPT_DIR, os.path.join(_SCRIPT_DIR, "templates")):
        candidate = os.path.join(prefix, path)
        if os.path.exists(candidate):
            return candidate
    return path  # let the caller fail with FileNotFoundError


def _get_template(name: str) -> TicketTemplate:
    """Return a built-in template by name."""
    factory = TEMPLATE_TYPES.get(name)
    if factory is None:
        print(f"  Error: unknown template '{name}'", file=sys.stderr)
        print(f"  Available: {', '.join(TEMPLATE_TYPES)}", file=sys.stderr)
        sys.exit(1)
    return factory(name)


def _normalize_tickets(data: Union[dict, list]) -> List[dict]:
    """Ensure data is always a list of ticket dicts."""
    return data if isinstance(data, list) else [data]


# Keys that unambiguously identify a template type
_TEMPLATE_SIGNATURES = {
    "attendance": {"student"},
    "receipt":    {"merchant", "order", "items", "totals"},
    "event":      {"event", "seat", "holder"},
    "poisson":    {"poisson"},
}


def _detect_template(data: Union[dict, list]) -> str:
    """Infer the best template name from the top-level keys of the first ticket."""
    sample = data[0] if isinstance(data, list) else data
    keys = set(sample.keys())
    for name, signature in _TEMPLATE_SIGNATURES.items():
        if keys & signature:   # any overlap → match
            return name
    return "event"             # safe fallback


# ---------------------------------------------------------------------------
# Subcommand: print
# ---------------------------------------------------------------------------


def cmd_print(args: argparse.Namespace) -> None:
    """Print ticket(s) from a JSON file to the thermal printer."""
    data = _load_json(_resolve_path(args.json))
    template_name = args.template or _detect_template(data)
    if not args.template:
        print(f"  Auto-detected template: {template_name}  (override with -t)")
    template = _get_template(template_name)
    tickets = _normalize_tickets(data)

    printer = ZJ8360Printer(paper_width=args.paper_width)
    if not printer.connect():
        print("  Error: could not connect to the printer.", file=sys.stderr)
        print("  Make sure it is plugged in and powered on.", file=sys.stderr)
        sys.exit(1)

    config = PrinterConfig(paper_width=args.paper_width)
    count = len(tickets)
    print(f"  Printing {count} ticket(s)  [template={template_name}, width={args.paper_width}]")

    try:
        for idx, ticket_data in enumerate(tickets, 1):
            print(f"  -> Ticket {idx}/{count} ... ", end="", flush=True)
            ticket_printer = TicketPrinter(printer, template, config)
            ok = ticket_printer.print_formatted_ticket(
                ticket_data,
                cut_paper=not args.no_cut,
                feed_lines=args.feed_lines,
            )
            print("OK" if ok else "FAILED")
            if not ok:
                sys.exit(1)
    finally:
        printer.disconnect()

    print("  Done.")


# ---------------------------------------------------------------------------
# Subcommand: preview
# ---------------------------------------------------------------------------


def cmd_preview(args: argparse.Namespace) -> None:
    """Preview ticket rendering in the terminal (no printer needed)."""
    data = _load_json(_resolve_path(args.json))
    template_name = args.template or _detect_template(data)
    if not args.template:
        print(f"  Auto-detected template: {template_name}  (override with -t)")
    template = _get_template(template_name)
    tickets = _normalize_tickets(data)
    config = PrinterConfig(paper_width=args.paper_width)
    separator = "=" * args.paper_width

    for idx, ticket_data in enumerate(tickets, 1):
        renderer = TicketRenderer(template, config)
        text = renderer.render_to_text(ticket_data, printer_safe=args.printer_safe)
        print()
        print(separator)
        print(f" PREVIEW  —  Ticket {idx}/{len(tickets)}"
              f"  [template={template_name}, width={args.paper_width}]")
        print(separator)
        print(text)
        print(separator)

    print()


# ---------------------------------------------------------------------------
# Subcommand: qr
# ---------------------------------------------------------------------------


def cmd_qr(args: argparse.Namespace) -> None:
    """Generate a QR code from text data or a JSON file's qr_code field."""
    # Determine data to encode
    if args.data:
        qr_data = args.data
    else:
        raw = _load_json(_resolve_path(args.json))
        tickets = _normalize_tickets(raw)
        if not tickets:
            print("  Error: JSON file contains no tickets.", file=sys.stderr)
            sys.exit(1)
        ticket = tickets[0]
        qr_data = (
            ticket.get("qr_code", {}).get("value")
            or ticket.get("barcode", {}).get("value")
            or ""
        )
        if not qr_data:
            print(
                "  Error: no QR/barcode value found in the first ticket.",
                file=sys.stderr,
            )
            sys.exit(1)

    qr_gen = QRCodeGenerator(error_correction=args.ec_level)

    # Output as PNG file
    if args.output:
        size_map = {
            "tiny": QRCodeGenerator.TINY,
            "small": QRCodeGenerator.SMALL,
            "medium": QRCodeGenerator.MEDIUM,
            "large": QRCodeGenerator.LARGE,
        }
        img_bytes = qr_gen.generate_image(
            qr_data, size=size_map.get(args.size, QRCodeGenerator.MEDIUM)
        )
        if img_bytes:
            with open(args.output, "wb") as fh:
                fh.write(img_bytes)
            print(f"  QR code saved to: {args.output}  ({len(img_bytes)} bytes)")
            print(f"  Data encoded: {qr_data}")
        else:
            print("  Error: failed to generate QR image.", file=sys.stderr)
            sys.exit(1)
        return

    # Output as ASCII art to terminal
    if args.format == "printer":
        art = qr_gen.generate_printer_safe_ascii(qr_data)
    else:
        art = qr_gen.generate_ascii_art(qr_data)

    print()
    print(f"  QR Code  —  data: {qr_data}")
    print(f"  EC level: {args.ec_level}  |  format: {args.format}")
    print()
    print(art)
    print()


# ---------------------------------------------------------------------------
# Subcommand: list-usb
# ---------------------------------------------------------------------------


def cmd_list_usb(_args: argparse.Namespace) -> None:
    """List all connected USB devices."""
    list_usb_devices()


# ---------------------------------------------------------------------------
# Subcommand: test
# ---------------------------------------------------------------------------


def cmd_test(_args: argparse.Namespace) -> None:
    """Run template system and QR code diagnostics (no printer needed)."""
    passed = 0
    failed = 0

    def _ok(label: str, detail: str = ""):
        nonlocal passed
        passed += 1
        suffix = f"  ({detail})" if detail else ""
        print(f"  PASS  {label}{suffix}")

    def _fail(label: str, detail: str = ""):
        nonlocal failed
        failed += 1
        suffix = f"  ({detail})" if detail else ""
        print(f"  FAIL  {label}{suffix}")

    print()
    print("=" * 60)
    print("  HZTZPrinter — Self-test suite")
    print("=" * 60)
    print()

    # 1 — imports (already done at module level, just confirm)
    try:
        assert TemplateBuilder and TicketRenderer and QRCodeGenerator
        _ok("Module imports")
    except Exception as exc:
        _fail("Module imports", str(exc))
        sys.exit(1)

    # 2 — event template creation
    try:
        tpl = TemplateBuilder.create_event_template("Test Event")
        assert tpl.name == "Test Event" and len(tpl.card_rows) > 0
        _ok("Event template creation", f"{len(tpl.card_rows)} card rows")
    except Exception as exc:
        _fail("Event template creation", str(exc))

    # 3 — receipt template creation
    try:
        tpl_r = TemplateBuilder.create_receipt_template("Test Receipt")
        assert tpl_r.title == "Receipt"
        _ok("Receipt template creation")
    except Exception as exc:
        _fail("Receipt template creation", str(exc))

    # 4 — field reference resolution
    try:
        ref = FieldReference(paths=["event.name"])
        result = ref.resolve({"event": {"name": "Summer Concert"}})
        assert result is not None and str(result.value) == "Summer Concert"
        _ok("Field reference resolution", f"value={result.value}")
    except Exception as exc:
        _fail("Field reference resolution", str(exc))

    # 5 — fallback field resolution
    try:
        ref = FieldReference(paths=["primary.missing", "backup.field"])
        result = ref.resolve({"backup": {"field": "Fallback Value"}})
        assert result is not None and str(result.value) == "Fallback Value"
        _ok("Fallback field resolution", f"value={result.value}")
    except Exception as exc:
        _fail("Fallback field resolution", str(exc))

    # 6 — row rendering
    try:
        row = TemplateRow(layout=ItemLayout.TWO_ITEMS)
        row.add_item(field_ref=FieldReference(paths=["date"]), label="DATE")
        row.add_item(field_ref=FieldReference(paths=["time"]), label="TIME")
        rendered = row.render({"date": "July 15, 2026", "time": "8:00 PM"})
        assert rendered and "July 15" in rendered and "8:00 PM" in rendered
        _ok("Row rendering", f"output={rendered!r}")
    except Exception as exc:
        _fail("Row rendering", str(exc))

    # 7 — empty field handling
    try:
        row = TemplateRow(layout=ItemLayout.THREE_ITEMS)
        row.add_item(field_ref=FieldReference(paths=["f1"]), label="A")
        row.add_item(field_ref=FieldReference(paths=["f2"]), label="B")
        row.add_item(field_ref=FieldReference(paths=["f3"]), label="C")
        rendered = row.render({"f2": "Value2"})
        assert rendered and "Value2" in rendered
        _ok("Empty field handling", f"output={rendered!r}")
    except Exception as exc:
        _fail("Empty field handling", str(exc))

    # 8 — full ticket rendering
    try:
        tpl = TemplateBuilder.create_event_template()
        event_data = {
            "event": {"name": "Concert", "date": "July 15, 2026", "time": "8:00 PM"},
            "venue": {"name": "Central Park", "address": "123 Central Park, NY"},
            "seat": {"section": "A", "row": "5", "seat": "12", "gate": "North"},
            "barcode": {"value": "EVT123456"},
            "holder": {"name": "John Doe"},
        }
        text = TicketRenderer(tpl).render_to_text(event_data)
        assert text and "Concert" in text and "July 15" in text
        _ok("Full ticket text rendering", f"{len(text)} chars")
    except Exception as exc:
        _fail("Full ticket text rendering", str(exc))

    # 9 — QR code ASCII generation
    try:
        art = QRCodeGenerator().generate_ascii_art("TEST-DATA-12345")
        assert art and len(art) > 0
        _ok("QR code ASCII generation", f"{len(art.splitlines())} lines")
    except Exception as exc:
        _fail("QR code ASCII generation", str(exc))

    # 10 — QR code printer-safe generation
    try:
        art = QRCodeGenerator().generate_printer_safe_ascii("TEST-DATA-12345")
        assert art and "#" in art
        _ok("QR code printer-safe generation")
    except Exception as exc:
        _fail("QR code printer-safe generation", str(exc))

    # 11 — QR native ESC Z command
    try:
        cmd = QRCodeGenerator().generate_native_qr_command(
            "EVT123456", version=0, ec_level="M"
        )
        assert cmd and cmd[:2] == b"\x1b\x5a"
        _ok("QR native ESC Z command", f"{len(cmd)} bytes")
    except Exception as exc:
        _fail("QR native ESC Z command", str(exc))

    # 12 — QR PNG image generation
    try:
        img = QRCodeGenerator().generate_image("EVT123456", size=QRCodeGenerator.MEDIUM)
        assert img and len(img) > 100
        _ok("QR PNG image generation", f"{len(img)} bytes")
    except Exception as exc:
        _fail("QR PNG image generation", str(exc))

    # 13 — sample JSON loading
    try:
        sample_path = os.path.join(_SCRIPT_DIR, "templates", "sample_event_ticket.json")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as fh:
                sample = json.load(fh)
            assert "event" in sample
            _ok("Sample JSON loading", f"keys={list(sample.keys())}")
        else:
            _ok("Sample JSON loading", "skipped — file not found")
    except Exception as exc:
        _fail("Sample JSON loading", str(exc))

    # Summary
    total = passed + failed
    print()
    print("-" * 60)
    print(f"  Results: {passed}/{total} passed, {failed}/{total} failed")
    print("-" * 60)
    print()
    if failed > 0:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Subcommand: serve
# ---------------------------------------------------------------------------


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the HTTP API server."""
    # Port precedence: --port flag > HZTZ_PORT env var > default 8360
    port = args.port if args.port is not None else int(os.environ.get("HZTZ_PORT", 8360))
    debug = args.debug or os.environ.get("HZTZ_DEBUG", "false").lower() in ("true", "1", "yes")

    try:
        from src.api_server import start_server
    except ImportError as exc:
        msg = str(exc).lower()
        if "flask" in msg or "flask_cors" in msg:
            print("  Error: Flask and flask-cors are required for server mode.", file=sys.stderr)
            print("  Install them with:  pip install flask flask-cors", file=sys.stderr)
        else:
            print(f"  Error: cannot import API server: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"  Starting HZTZPrinter API server on port {port} ...")
    if debug:
        print("  Debug mode enabled.")
    start_server(port=port, debug=debug)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _add_json_and_template_args(parser: argparse.ArgumentParser) -> None:
    """Add the shared --json / --template / --paper-width arguments."""
    parser.add_argument(
        "-j",
        "--json",
        required=True,
        metavar="FILE",
        help="path to JSON file with ticket data (single object or array)",
    )
    parser.add_argument(
        "-t",
        "--template",
        default=None,
        choices=list(TEMPLATE_TYPES),
        help="template to use: event, receipt (default: auto-detected from data)",
    )
    parser.add_argument(
        "--paper-width",
        type=int,
        default=48,
        choices=[32, 40, 48],
        metavar="WIDTH",
        help="paper width in characters: 32 (80mm), 40 (std), 48 (96mm) (default: 48)",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with all subcommands."""

    parser = argparse.ArgumentParser(
        prog="fool_printer",
        description=textwrap.dedent(f"""\
            HZTZPrinter — ZJ-8360 Thermal Ticket Printer CLI  (v{__version__})

            Control a ZJ-8360 thermal printer from the command line.
            Print tickets from JSON data, preview renders, generate QR
            codes, and run diagnostics.
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              %(prog)s preview -j templates/sample_event_ticket.json
              %(prog)s preview -j templates/sample_receipt.json -t receipt
              %(prog)s print   -j data.json -t event --paper-width 48
              %(prog)s qr      -d "https://example.com"
              %(prog)s qr      -d "TICKET-42" -o ticket_qr.png
              %(prog)s qr      -j templates/sample_qr.json
              %(prog)s list-usb
              %(prog)s test
              %(prog)s serve
              %(prog)s serve --port 9000
        """),
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="enable debug logging"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="suppress informational output"
    )

    sub = parser.add_subparsers(title="commands", dest="command", metavar="COMMAND")

    # -- print -------------------------------------------------------------
    p_print = sub.add_parser(
        "print",
        help="print ticket(s) from JSON data to the thermal printer",
        description="Send formatted tickets to the ZJ-8360 thermal printer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              %(prog)s -j templates/sample_event_ticket.json
              %(prog)s -j data.json -t receipt --paper-width 48
              %(prog)s -j tickets.json -t event --no-cut --feed-lines 5
        """),
    )
    _add_json_and_template_args(p_print)
    p_print.add_argument(
        "--no-cut", action="store_true", help="do not cut paper after printing"
    )
    p_print.add_argument(
        "--feed-lines",
        type=int,
        default=3,
        metavar="N",
        help="blank lines to feed before cutting (default: 3)",
    )
    p_print.set_defaults(func=cmd_print)

    # -- preview -----------------------------------------------------------
    p_preview = sub.add_parser(
        "preview",
        help="preview ticket rendering in the terminal (no printer needed)",
        description="Render tickets as text and display them in the terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              %(prog)s -j templates/sample_event_ticket.json
              %(prog)s -j templates/sample_receipt.json -t receipt
              %(prog)s -j data.json --paper-width 32 --printer-safe
        """),
    )
    _add_json_and_template_args(p_preview)
    p_preview.add_argument(
        "--printer-safe",
        action="store_true",
        help="use ASCII-safe characters (matches actual printer output)",
    )
    p_preview.set_defaults(func=cmd_preview)

    # -- qr ----------------------------------------------------------------
    p_qr = sub.add_parser(
        "qr",
        help="generate QR codes (ASCII art or PNG image)",
        description="Generate QR codes for display or export.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              %(prog)s -d "https://example.com"
              %(prog)s -d "TICKET-42" -o qr.png --size large
              %(prog)s -d "DATA" --format printer --ec-level H
              %(prog)s -j templates/sample_qr.json
        """),
    )
    qr_src = p_qr.add_mutually_exclusive_group(required=True)
    qr_src.add_argument("-d", "--data", metavar="TEXT", help="text/URL to encode")
    qr_src.add_argument(
        "-j",
        "--json",
        metavar="FILE",
        help="read QR data from the first ticket's qr_code.value or barcode.value",
    )
    p_qr.add_argument(
        "-o", "--output", metavar="FILE", help="save QR as PNG (omit for terminal art)"
    )
    p_qr.add_argument(
        "--format",
        default="ascii",
        choices=["ascii", "printer"],
        help="terminal format: 'ascii' (unicode) or 'printer' (# chars) (default: ascii)",
    )
    p_qr.add_argument(
        "--ec-level",
        default="M",
        choices=["L", "M", "Q", "H"],
        metavar="LEVEL",
        help="error correction: L (7%%), M (15%%), Q (25%%), H (30%%) (default: M)",
    )
    p_qr.add_argument(
        "--size",
        default="medium",
        choices=["tiny", "small", "medium", "large"],
        help="PNG image size (default: medium)",
    )
    p_qr.set_defaults(func=cmd_qr)

    # -- list-usb ----------------------------------------------------------
    p_usb = sub.add_parser(
        "list-usb",
        help="list all connected USB devices",
        description="Scan and display all USB devices. Useful to verify the printer is detected.",
    )
    p_usb.set_defaults(func=cmd_list_usb)

    # -- test --------------------------------------------------------------
    p_test = sub.add_parser(
        "test",
        help="run built-in self-tests (no printer needed)",
        description="Execute template, rendering, and QR code tests to verify the installation.",
    )
    p_test.set_defaults(func=cmd_test)

    # -- serve -------------------------------------------------------------
    p_serve = sub.add_parser(
        "serve",
        help="start the HTTP API server",
        description=textwrap.dedent("""\
            Start an HTTP REST API server that exposes all printer
            functionalities over HTTP.

            The server listens at:  http://localhost:{PORT}/api/

            PORT is resolved in this order:
              1. --port flag
              2. HZTZ_PORT variable in .env
              3. Default: 8360  (matches the ZJ-8360 printer model)
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            endpoints:
              GET  /api/health      — liveness probe
              GET  /api/templates   — list available templates
              POST /api/preview     — render ticket(s) to text (no printer needed)
              POST /api/print       — send ticket(s) to the thermal printer
              POST /api/qr          — generate a QR code (ASCII art or PNG)
              GET  /api/usb         — list connected USB devices
              GET  /api/test        — run self-test suite

            examples:
              %(prog)s                        # port from .env  (default: 8360)
              %(prog)s --port 9000
              %(prog)s --port 8080 --debug
        """),
    )
    p_serve.add_argument(
        "--port",
        type=int,
        default=None,
        metavar="PORT",
        help="TCP port to listen on (overrides HZTZ_PORT in .env, default: 8360)",
    )
    p_serve.add_argument(
        "--debug",
        action="store_true",
        help="enable Flask debug mode (auto-reload + verbose error pages)",
    )
    p_serve.set_defaults(func=cmd_serve)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    _setup_logging(
        verbose=getattr(args, "verbose", False),
        quiet=getattr(args, "quiet", False),
    )

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
