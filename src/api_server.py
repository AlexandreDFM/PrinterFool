"""
HZTZPrinter — HTTP API Server

Exposes all CLI functionalities as a RESTful JSON API.
Launch via:  python fool_printer.py serve

Endpoints
---------
GET  /api/health       — liveness probe
GET  /api/templates    — list available templates and paper widths
POST /api/preview      — render ticket(s) to text  (no printer required)
POST /api/print        — send ticket(s) to the thermal printer
POST /api/qr           — generate a QR code (ASCII art or PNG image)
GET  /api/usb          — enumerate connected USB devices
GET  /api/test         — run built-in self-test suite
POST /api/test         — run built-in self-test suite (POST convenience)

All JSON endpoints return:
  { "ok": true,  ...payload... }          on success
  { "ok": false, "error": "<message>" }   on failure
"""

import os
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from .printer import ZJ8360Printer
from .template_system import (
    TemplateBuilder,
    TicketTemplate,
    FieldReference,
    ItemLayout,
    TemplateRow,
)
from .ticket_renderer import TicketRenderer, TicketPrinter, PrinterConfig
from .qrcode_generator import QRCodeGenerator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template registry  (mirrors fool_printer.py)
# ---------------------------------------------------------------------------

TEMPLATE_TYPES: Dict[str, Any] = {
    "event":   TemplateBuilder.create_event_template,
    "receipt": TemplateBuilder.create_receipt_template,
}

_TEMPLATE_SIGNATURES: Dict[str, set] = {
    "receipt": {"merchant", "order", "items", "totals"},
    "event":   {"event", "seat", "holder"},
}

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _normalize_tickets(data: Union[dict, list]) -> List[dict]:
    """Ensure *data* is always a list of ticket dicts."""
    return data if isinstance(data, list) else [data]


def _detect_template(data: Union[dict, list]) -> str:
    """Infer the best template name from the top-level keys of the first ticket."""
    sample = data[0] if isinstance(data, list) else data
    keys = set(sample.keys())
    for name, sig in _TEMPLATE_SIGNATURES.items():
        if keys & sig:
            return name
    return "event"


def _get_template(name: str) -> Optional[TicketTemplate]:
    """Return a built-in template by name, or None if unknown."""
    factory = TEMPLATE_TYPES.get(name)
    return factory(name) if factory else None


# ---------------------------------------------------------------------------
# Self-test runner  (programmatic — returns a dict instead of printing)
# ---------------------------------------------------------------------------

def run_tests() -> Dict[str, Any]:
    """
    Run the full self-test suite and return structured results.

    Returns
    -------
    dict with keys:
        passed   int
        failed   int
        total    int
        results  list of {"name": str, "status": "pass"|"fail", "detail": str}
    """
    results: List[Dict[str, str]] = []
    passed = 0
    failed = 0

    def _ok(name: str, detail: str = "") -> None:
        nonlocal passed
        passed += 1
        results.append({"name": name, "status": "pass", "detail": detail})

    def _fail(name: str, detail: str = "") -> None:
        nonlocal failed
        failed += 1
        results.append({"name": name, "status": "fail", "detail": detail})

    # 1 — Module imports
    try:
        assert TemplateBuilder and TicketRenderer and QRCodeGenerator
        _ok("Module imports")
    except Exception as exc:
        _fail("Module imports", str(exc))

    # 2 — Event template creation
    try:
        tpl = TemplateBuilder.create_event_template("Test Event")
        assert tpl.name == "Test Event" and len(tpl.card_rows) > 0
        _ok("Event template creation", f"{len(tpl.card_rows)} card rows")
    except Exception as exc:
        _fail("Event template creation", str(exc))

    # 3 — Receipt template creation
    try:
        tpl_r = TemplateBuilder.create_receipt_template("Test Receipt")
        assert tpl_r.title == "Receipt"
        _ok("Receipt template creation")
    except Exception as exc:
        _fail("Receipt template creation", str(exc))

    # 4 — Field reference resolution
    try:
        ref = FieldReference(paths=["event.name"])
        result = ref.resolve({"event": {"name": "Summer Concert"}})
        assert result is not None and str(result.value) == "Summer Concert"
        _ok("Field reference resolution", f"value={result.value}")
    except Exception as exc:
        _fail("Field reference resolution", str(exc))

    # 5 — Fallback field resolution
    try:
        ref = FieldReference(paths=["primary.missing", "backup.field"])
        result = ref.resolve({"backup": {"field": "Fallback Value"}})
        assert result is not None and str(result.value) == "Fallback Value"
        _ok("Fallback field resolution", f"value={result.value}")
    except Exception as exc:
        _fail("Fallback field resolution", str(exc))

    # 6 — Row rendering
    try:
        row = TemplateRow(layout=ItemLayout.TWO_ITEMS)
        row.add_item(field_ref=FieldReference(paths=["date"]), label="DATE")
        row.add_item(field_ref=FieldReference(paths=["time"]), label="TIME")
        rendered = row.render({"date": "July 15, 2026", "time": "8:00 PM"})
        assert rendered and "July 15" in rendered and "8:00 PM" in rendered
        _ok("Row rendering", f"output={rendered!r}")
    except Exception as exc:
        _fail("Row rendering", str(exc))

    # 7 — Empty field handling
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

    # 8 — Full ticket text rendering
    try:
        tpl = TemplateBuilder.create_event_template()
        event_data = {
            "event":  {"name": "Concert", "date": "July 15, 2026", "time": "8:00 PM"},
            "venue":  {"name": "Central Park", "address": "123 Central Park, NY"},
            "seat":   {"section": "A", "row": "5", "seat": "12", "gate": "North"},
            "barcode":{"value": "EVT123456"},
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

    # 13 — Sample JSON loading
    try:
        import json as _json
        _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sample_path = os.path.join(_base, "templates", "sample_event_ticket.json")
        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as fh:
                sample = _json.load(fh)
            assert "event" in sample
            _ok("Sample JSON loading", f"keys={list(sample.keys())}")
        else:
            _ok("Sample JSON loading", "skipped — file not found")
    except Exception as exc:
        _fail("Sample JSON loading", str(exc))

    return {
        "passed":  passed,
        "failed":  failed,
        "total":   passed + failed,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Flask application factory
# ---------------------------------------------------------------------------

def create_app() -> "Flask":  # noqa: F821  (Flask typed as string to allow lazy import)
    """
    Create and configure the Flask API application.

    Raises
    ------
    ImportError
        If Flask or flask-cors are not installed.
    """
    try:
        from flask import Flask, Response, jsonify, request
        from flask_cors import CORS
    except ImportError as exc:
        raise ImportError(
            f"Flask and flask-cors are required for server mode: {exc}\n"
            "Install them with:  pip install flask flask-cors"
        ) from exc

    app = Flask(__name__)
    CORS(app)

    # ── internal helpers ─────────────────────────────────────────────────────

    def _ok(payload: dict, status: int = 200) -> Tuple[Response, int]:
        return jsonify({"ok": True, **payload}), status

    def _err(message: str, status: int = 400) -> Tuple[Response, int]:
        return jsonify({"ok": False, "error": message}), status

    def _parse_body() -> Tuple[Optional[dict], Any]:
        """Parse the JSON request body; return (body, None) or (None, error_response)."""
        if not request.is_json:
            return None, _err("Content-Type must be application/json")
        body = request.get_json(silent=True)
        if body is None:
            return None, _err("Invalid or empty JSON body")
        return body, None

    def _parse_paper_width(body: dict) -> Tuple[Optional[int], Any]:
        """Validate and return paper_width; return (None, error_response) on failure."""
        try:
            pw = int(body.get("paper_width", 48))
        except (TypeError, ValueError):
            return None, _err("paper_width must be an integer")
        if pw not in (32, 40, 48):
            return None, _err("paper_width must be 32, 40, or 48")
        return pw, None

    # =========================================================================
    # GET /api/health
    # =========================================================================

    @app.get("/api/health")
    def health():
        """Liveness probe — always returns 200 if the server is up."""
        return _ok({
            "status":  "ok",
            "version": "1.0.0",
            "printer": {
                "vendor_id":  hex(ZJ8360Printer.VENDOR_ID),
                "product_id": hex(ZJ8360Printer.PRODUCT_ID),
            },
        })

    # =========================================================================
    # GET /api/templates
    # =========================================================================

    @app.get("/api/templates")
    def templates():
        """List available template names and accepted paper widths."""
        return _ok({
            "templates":    list(TEMPLATE_TYPES.keys()),
            "paper_widths": [32, 40, 48],
            "ec_levels":    ["L", "M", "Q", "H"],
            "qr_formats":   ["ascii", "printer", "png"],
            "qr_sizes":     ["tiny", "small", "medium", "large"],
        })

    # =========================================================================
    # POST /api/preview
    # =========================================================================
    #
    # Body (JSON):
    #   {
    #     "data":         { ... } | [ ... ],         REQUIRED
    #     "template":     "event" | "receipt",        optional (auto-detected)
    #     "paper_width":  32 | 40 | 48,               optional (default: 48)
    #     "printer_safe": true | false                 optional (default: false)
    #   }
    #
    # Response:
    #   {
    #     "ok":           true,
    #     "template":     "event",
    #     "paper_width":  48,
    #     "printer_safe": false,
    #     "count":        1,
    #     "previews":     [ "<rendered text>", ... ]
    #   }

    @app.post("/api/preview")
    def preview():
        """Render ticket(s) to plain text without connecting to the printer."""
        body, err = _parse_body()
        if err is not None:
            return err

        raw_data = body.get("data")
        if raw_data is None:
            return _err("Missing required field: 'data'")

        paper_width, err = _parse_paper_width(body)
        if err is not None:
            return err

        template_name = body.get("template") or _detect_template(raw_data)
        template = _get_template(template_name)
        if template is None:
            return _err(
                f"Unknown template '{template_name}'. "
                f"Available: {list(TEMPLATE_TYPES)}"
            )

        printer_safe = bool(body.get("printer_safe", False))
        tickets      = _normalize_tickets(raw_data)
        config       = PrinterConfig(paper_width=paper_width)

        previews: List[str] = []
        for ticket_data in tickets:
            renderer = TicketRenderer(template, config)
            previews.append(renderer.render_to_text(ticket_data, printer_safe=printer_safe))

        return _ok({
            "template":     template_name,
            "paper_width":  paper_width,
            "printer_safe": printer_safe,
            "count":        len(previews),
            "previews":     previews,
        })

    # =========================================================================
    # POST /api/print
    # =========================================================================
    #
    # Body (JSON):
    #   {
    #     "data":        { ... } | [ ... ],          REQUIRED
    #     "template":    "event" | "receipt",         optional (auto-detected)
    #     "paper_width": 32 | 40 | 48,                optional (default: 48)
    #     "no_cut":      true | false,                 optional (default: false)
    #     "feed_lines":  3                             optional (default: 3)
    #   }
    #
    # Response:
    #   {
    #     "ok":          true,
    #     "printed":     1,
    #     "template":    "event",
    #     "paper_width": 48
    #   }
    #
    # Errors:
    #   503  — printer not connected
    #   500  — one or more tickets failed to print

    @app.post("/api/print")
    def print_tickets():
        """Send ticket(s) to the ZJ-8360 thermal printer."""
        body, err = _parse_body()
        if err is not None:
            return err

        raw_data = body.get("data")
        if raw_data is None:
            return _err("Missing required field: 'data'")

        paper_width, err = _parse_paper_width(body)
        if err is not None:
            return err

        try:
            feed_lines = int(body.get("feed_lines", 3))
        except (TypeError, ValueError):
            return _err("feed_lines must be an integer")

        no_cut        = bool(body.get("no_cut", False))
        template_name = body.get("template") or _detect_template(raw_data)
        template      = _get_template(template_name)
        if template is None:
            return _err(
                f"Unknown template '{template_name}'. "
                f"Available: {list(TEMPLATE_TYPES)}"
            )

        tickets = _normalize_tickets(raw_data)
        printer = ZJ8360Printer(paper_width=paper_width)

        if not printer.connect():
            return _err(
                "Could not connect to the printer. "
                "Make sure it is plugged in and powered on.",
                503,
            )

        config  = PrinterConfig(paper_width=paper_width)
        printed = 0
        errors: List[str] = []

        try:
            for idx, ticket_data in enumerate(tickets):
                tp = TicketPrinter(printer, template, config)
                ok = tp.print_formatted_ticket(
                    ticket_data,
                    cut_paper=not no_cut,
                    feed_lines=feed_lines,
                )
                if ok:
                    printed += 1
                else:
                    errors.append(f"ticket {idx + 1} failed")
        finally:
            printer.disconnect()

        if errors:
            return _err(
                f"{len(errors)}/{len(tickets)} ticket(s) failed: {'; '.join(errors)}",
                500,
            )

        return _ok({
            "printed":     printed,
            "template":    template_name,
            "paper_width": paper_width,
        })

    # =========================================================================
    # POST /api/qr
    # =========================================================================
    #
    # Body (JSON):
    #   {
    #     "data":     "https://example.com",           REQUIRED
    #     "format":   "ascii" | "printer" | "png",     optional (default: "ascii")
    #     "ec_level": "L" | "M" | "Q" | "H",           optional (default: "M")
    #     "size":     "tiny"|"small"|"medium"|"large"   optional (default: "medium")
    #   }
    #
    # Response (ascii / printer):
    #   {
    #     "ok":       true,
    #     "data":     "https://example.com",
    #     "format":   "ascii",
    #     "ec_level": "M",
    #     "lines":    25,
    #     "art":      "..."
    #   }
    #
    # Response (png):
    #   Binary PNG image  (Content-Type: image/png)

    @app.post("/api/qr")
    def qr():
        """Generate a QR code as ASCII art (ascii/printer) or PNG image."""
        body, err = _parse_body()
        if err is not None:
            return err

        qr_data = body.get("data")
        if not qr_data:
            return _err("Missing required field: 'data'")

        fmt      = body.get("format",   "ascii")
        ec_level = body.get("ec_level", "M")
        size_key = body.get("size",     "medium")

        if fmt not in ("ascii", "printer", "png"):
            return _err("format must be one of: ascii, printer, png")
        if ec_level not in ("L", "M", "Q", "H"):
            return _err("ec_level must be one of: L, M, Q, H")
        if size_key not in ("tiny", "small", "medium", "large"):
            return _err("size must be one of: tiny, small, medium, large")

        qr_gen = QRCodeGenerator(error_correction=ec_level)

        # ── PNG branch ───────────────────────────────────────────────────────
        if fmt == "png":
            size_map = {
                "tiny":   QRCodeGenerator.TINY,
                "small":  QRCodeGenerator.SMALL,
                "medium": QRCodeGenerator.MEDIUM,
                "large":  QRCodeGenerator.LARGE,
            }
            img_bytes = qr_gen.generate_image(qr_data, size=size_map[size_key])
            if not img_bytes:
                return _err("Failed to generate QR code image", 500)
            return Response(
                img_bytes,
                mimetype="image/png",
                headers={"Content-Disposition": 'inline; filename="qr.png"'},
            )

        # ── ASCII / printer branch ────────────────────────────────────────────
        art = (
            qr_gen.generate_printer_safe_ascii(qr_data)
            if fmt == "printer"
            else qr_gen.generate_ascii_art(qr_data)
        )
        if not art:
            return _err("Failed to generate QR code", 500)

        return _ok({
            "data":     qr_data,
            "format":   fmt,
            "ec_level": ec_level,
            "lines":    len(art.splitlines()),
            "art":      art,
        })

    # =========================================================================
    # GET /api/usb
    # =========================================================================
    #
    # Response:
    #   {
    #     "ok":               true,
    #     "count":            3,
    #     "printer_detected": true,
    #     "devices": [
    #       {
    #         "vendor_id":    "0x416",
    #         "product_id":   "0x5011",
    #         "manufacturer": "Zjiang",
    #         "is_printer":   true
    #       }, ...
    #     ]
    #   }

    @app.get("/api/usb")
    def usb_devices():
        """Enumerate all connected USB devices and flag the ZJ-8360 printer."""
        try:
            import usb.core
            import usb.util as usb_util
        except ImportError:
            return _err("pyusb is not installed on this server", 500)

        found   = usb.core.find(find_all=True) or []
        devices: List[dict] = []

        for dev in found:
            manufacturer = None
            try:
                manufacturer = usb_util.get_string(dev, dev.iManufacturer) or None
            except Exception:
                pass

            is_printer = (
                dev.idVendor  == ZJ8360Printer.VENDOR_ID
                and dev.idProduct == ZJ8360Printer.PRODUCT_ID
            )
            devices.append({
                "vendor_id":    hex(dev.idVendor),
                "product_id":   hex(dev.idProduct),
                "manufacturer": manufacturer,
                "is_printer":   is_printer,
            })

        printer_detected = any(d["is_printer"] for d in devices)
        return _ok({
            "count":            len(devices),
            "printer_detected": printer_detected,
            "devices":          devices,
        })

    # =========================================================================
    # GET /api/test   &   POST /api/test
    # =========================================================================
    #
    # Response:
    #   {
    #     "ok":      true,
    #     "passed":  12,
    #     "failed":  0,
    #     "total":   13,
    #     "results": [
    #       { "name": "Module imports", "status": "pass", "detail": "" },
    #       ...
    #     ]
    #   }
    #
    # HTTP status: 200 when all tests pass, 207 (Multi-Status) when some fail.

    def _run_tests_handler():
        test_results = run_tests()
        status = 200 if test_results["failed"] == 0 else 207
        return _ok(test_results, status)

    @app.get("/api/test")
    def test_get():
        """Run the built-in self-test suite (GET convenience)."""
        return _run_tests_handler()

    @app.post("/api/test")
    def test_post():
        """Run the built-in self-test suite."""
        return _run_tests_handler()

    # ── generic error handlers ───────────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(_exc):
        return _err(
            "Endpoint not found. Available routes: "
            "GET /api/health, GET /api/templates, "
            "POST /api/preview, POST /api/print, POST /api/qr, "
            "GET /api/usb, GET /api/test",
            404,
        )

    @app.errorhandler(405)
    def method_not_allowed(_exc):
        return _err(
            f"Method not allowed: {request.method} {request.path}",
            405,
        )

    @app.errorhandler(500)
    def internal_error(exc):
        logger.exception("Unhandled server error: %s", exc)
        return _err(f"Internal server error: {exc}", 500)

    return app


# ---------------------------------------------------------------------------
# Standalone launcher (used by fool_printer.py's `serve` command)
# ---------------------------------------------------------------------------

def start_server(port: int = 8360, debug: bool = False) -> None:
    """
    Create the Flask app and start the development server.

    Parameters
    ----------
    port:
        TCP port to listen on (default: 8360, matching the ZJ-8360 model).
    debug:
        Enable Flask's reloader and debugger.
    """
    app = create_app()

    print(f"  HZTZPrinter API server  —  http://localhost:{port}/api/")
    print()
    print("  Endpoints:")
    print(f"    GET  http://localhost:{port}/api/health")
    print(f"    GET  http://localhost:{port}/api/templates")
    print(f"    POST http://localhost:{port}/api/preview")
    print(f"    POST http://localhost:{port}/api/print")
    print(f"    POST http://localhost:{port}/api/qr")
    print(f"    GET  http://localhost:{port}/api/usb")
    print(f"    GET  http://localhost:{port}/api/test")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    app.run(host="0.0.0.0", port=port, debug=debug)
