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
POST /api/attendance   — generate personalised student attendance ticket
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
import random
import hashlib
from datetime import datetime
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
    "event":      TemplateBuilder.create_event_template,
    "receipt":    TemplateBuilder.create_receipt_template,
    "attendance": TemplateBuilder.create_attendance_template,
}

_TEMPLATE_SIGNATURES: Dict[str, set] = {
    "attendance": {"student"},
    "receipt":    {"merchant", "order", "items", "totals"},
    "event":      {"event", "seat", "holder"},
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
    # POST /api/attendance
    # =========================================================================
    #
    # Body (JSON):
    #   {
    #     "student_email":  "prenom.nom@epitech.eu",       REQUIRED
    #     "student_name":   "Prenom Nom",                   optional (derived from email)
    #     "scanned_by":     "Staff Name",                   optional
    #     "paper_width":    32 | 40 | 48,                   optional (default: 48)
    #     "print":          true | false,                   optional (default: false)
    #     "no_cut":         true | false,                   optional (default: false)
    #     "feed_lines":     3,                              optional (default: 3)
    #     "extend":         { ... }                         optional — deep-merge overrides
    #   }
    #
    # The "extend" object lets callers override ANY auto-generated field.
    # It is deep-merged on top of the generated ticket_data, so you only
    # need to specify the keys you want to change.
    #
    # Customisable fields via "extend":
    # ┌─────────────────────────────────────────────────────────────────┐
    # │ merchant.name          — school / org name (default: EPITECH)  │
    # │ merchant.address       — address line                          │
    # │ order.commande_number  — override generated CMD-xxxx           │
    # │ order.ticket_number    — override generated ticket number      │
    # │ order.caisse_number    — cash register number                  │
    # │ transaction.date       — override date  (default: today)       │
    # │ transaction.hour       — override time  (default: now)         │
    # │ transaction.type       — "Sur place" / "A emporter" / custom   │
    # │ staff.seller           — override random funny seller name     │
    # │ student.name           — override derived student name         │
    # │ student.email          — override email on ticket              │
    # │ items                  — full replacement of the items array   │
    # │ totals.total_ht        — override HT total                    │
    # │ totals.tva_amount      — override TVA                         │
    # │ totals.total_ttc       — override TTC total                   │
    # │ qr_code.value          — override QR code URL / data          │
    # │ fun.motto              — override funny motto line             │
    # │ fun.warning            — override warning line                 │
    # │ footer.message         — override footer text                  │
    # └─────────────────────────────────────────────────────────────────┘
    #
    # Example with extend:
    #   {
    #     "student_email": "jean.dupont@epitech.eu",
    #     "extend": {
    #       "merchant": { "name": "EPITECH LYON" },
    #       "staff":    { "seller": "Le Pion Officiel" },
    #       "fun":      { "motto": "Tu croyais echapper au scan ?" },
    #       "qr_code":  { "value": "https://my-custom-url.com/verify" },
    #       "items": [
    #         { "quantity": 1, "designation": "Retard injustifie", "unit_price": 42, "total_price": 42 }
    #       ],
    #       "totals":   { "total_ht": 42, "tva_amount": 8.4, "total_ttc": 50.4 }
    #     }
    #   }
    #
    # Response:
    #   {
    #     "ok":           true,
    #     "student":      { "name": "...", "email": "..." },
    #     "ticket_number": "001842",
    #     "template":     "attendance",
    #     "paper_width":  48,
    #     "printed":      false,
    #     "preview":      "<rendered text>",
    #     "ticket_data":  { ... }
    #   }

    # -- Deep-merge helper -------------------------------------------------

    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge *override* into *base* (returns a new dict).

        - Dict values are merged recursively.
        - Lists and scalars in *override* fully replace the base value.
        - Keys present only in *base* are kept as-is.
        """
        merged = base.copy()
        for key, val in override.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(val, dict)
            ):
                merged[key] = _deep_merge(merged[key], val)
            else:
                merged[key] = val
        return merged

    # -- Funny data pools for randomisation --------------------------------

    _FUNNY_SELLERS = [
        "Jean-Michel Bricoleur",
        "Mme Krabappel",
        "Gordon Ramsay",
        "Le Stagiaire du Mardi",
        "ChatGPT (en greve)",
        "Un pigeon savant",
        "Mister Robot",
        "Gandalf le Gris",
        "Julien Calenge",
        "Marvin",
        "Gildas Vinson",
        "Le fantome du Hub",
        "Master Yoda",
        "Un Bocal en furie",
        "La souris du serveur",
        "Luigi",
        "Patrick l'Etoile de mer",
    ]

    _FUNNY_ITEMS_POOL = [
        ("Air frais d'Epitech (edition limitee)", 42.00),
        ("Licence StackOverflow Premium", 199.99),
        ("1h de WiFi stable", 89.90),
        ("Douche de lumiere naturelle", 15.50),
        ("Cours de cuisine par Moulinex", 35.00),
        ("Cafe qui marche vraiment", 999.99),
        ("Place de parking imaginaire", 75.00),
        ("Excuse valide pour retard", 12.50),
        ("Ticket de bus invisible", 1.90),
        ("Motivation (en rupture)", 0.01),
        ("Compilation sans erreur", 404.00),
        ("Bug gratuit (offert)", 0.00),
        ("Nuit blanche tout compris", 23.59),
        ("Segfault artisanal", 11.11),
        ("Variable bien nommee", 3.14),
        ("Code qui marche du 1er coup", 777.77),
        ("Push force sur main", 666.66),
        ("Merge conflict resolution", 50.00),
        ("README.md a jour", 100.00),
        ("Norminette satisfaite", 42.42),
        ("Sommeil (8h, bio)", 88.88),
        ("Chaise ergonomique (reve)", 599.00),
        ("Diplome en papier recycle", 9999.99),
        ("Croissant quantique", 7.77),
        ("Sandwich au malloc", 13.37),
        ("Cookie (pas HTTP)", 2.50),
        ("Tasse de the nullptr", 4.04),
        ("Salade de pointeurs", 8.08),
        ("Baguette de debug", 5.55),
        ("Eau source de bugs", 1.00),
    ]

    _FUNNY_MOTTOS = [
        "La presence est obligatoire, le fun est optionnel",
        "Code, mange, dors... ah non, juste code",
        "Epitech : ou le cafe est un groupe alimentaire",
        "Aujourd'hui est un bon jour pour un segfault",
        "La cantine n'existe pas, et toi non plus",
        "malloc(happiness) returned NULL",
        "git commit -m 'je suis la'",
        "while(alive) { code(); }",
        "404 : Motivation Not Found",
        "Ton futur employeur regarde ce ticket",
        "Ce ticket s'autodetruira dans 5... 4...",
        "Tu viens de mass print un ticket de caisse",
        "C'est pas un bug, c'est une feature",
    ]

    _FUNNY_WARNINGS = [
        "Ce ticket est a presenter EN PERSONNE a 17h30",
        "Ticket non echangeable, non remboursable, non negociable",
        "Conservation: garder loin du cafe et des larmes",
        "Toute ressemblance avec un vrai ticket est fortuite",
        "Ingredients: papier, encre, desespoir, humour",
        "Si tu perds ce ticket, recommence ta journee",
        "Ce ticket a ete imprime par une imprimante heureuse",
        "Ne pas plier, ne pas froisser, ne pas manger",
        "Validite: aujourd'hui uniquement (pas demain, JAMAIS)",
    ]

    _FUNNY_FOOTERS = [
        "Merci de votre visite dans notre etablissement fictif !",
        "A bientot ! (vous n'avez pas le choix)",
        "Bonne journee ! Ou pas. On est pas vos parents.",
        "Conservez ce ticket, il vaut de l'or (non)",
        "Merci d'avoir scan ta carte, champion !",
        "Ce ticket a ete fabrique avec amour et segfaults",
        "Revenez demain pour un autre ticket inutile !",
        ">>> print('Merci et a bientot !')",
        "return 0; // tout s'est bien passe (ou pas)",
    ]

    _TROLL_URLS = [
        # --- Rickroll classics ---
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",   # Never Gonna Give You Up
        "https://www.youtube.com/watch?v=xvFZjo5PgG0",   # Rickroll variante (redirect)
        "https://www.youtube.com/watch?v=iik25wqIuFo",   # Rickroll HD remaster
        # --- Earworm musicaux ---
        #DEAD "https://www.youtube.com/watch?v=gy1B3agGNxw",   # Epic Sax Guy (10h dans ta tete)
        #DEAD  "https://www.youtube.com/watch?v=QH2-TGUlwu4",   # Nyan Cat (10h de chat arc-en-ciel)
        #DEAD "https://www.youtube.com/watch?v=feA64wXhbJU",   # Shooting Stars meme
        #DEAD "https://www.youtube.com/watch?v=KmtzQCSh6xk",   # Numa Numa (Dragostea Din Tei)
        "https://www.youtube.com/watch?v=oavMtUWDBTM",   # Trololo (Eduard Khil)
        "https://www.youtube.com/watch?v=k85mRPqvMbE",   # Crazy Frog - Axel F
        #DEAD "https://www.youtube.com/watch?v=zvq9rSmFAb0",   # Caramelldansen
        "https://www.youtube.com/watch?v=y6120QOlsfU",   # Darude - Sandstorm
        "https://www.youtube.com/watch?v=G1IbRujko-A",   # Gandalf Sax Guy 10h
        #DEAD "https://www.youtube.com/watch?v=XCiDuy4mrWU",   # Running in the 90s
        "https://www.youtube.com/watch?v=dv13gl0a-FA",   # Deja Vu (Initial D)
        #DEAD "https://www.youtube.com/watch?v=vTIIMJ9tUc8",   # Tunak Tunak Tun
        #DEAD "https://www.youtube.com/watch?v=1wnE4vF9CQ4",   # Leek Spin (Ievan Polkka)
        # --- Anthems memesques ---
        "https://www.youtube.com/watch?v=L_jWHffIx5E",   # All Star - Smash Mouth (Shrek)
        "https://www.youtube.com/watch?v=LDU_Txk06tM",   # Crab Rave
        "https://www.youtube.com/watch?v=ZZ5LpwO-An4",   # He-Man HEYYEYAAEYAA
        "https://www.youtube.com/watch?v=PfYnvDL0Qcw",   # We Are Number One (Lazy Town)
        "https://www.youtube.com/watch?v=9bZkp7q19f0",   # Gangnam Style
        "https://www.youtube.com/watch?v=jofNR_WkoCE",   # What Does The Fox Say
        "https://www.youtube.com/watch?v=kfVsfOSbJY0",   # Friday - Rebecca Black
        "https://www.youtube.com/watch?v=EwTZ2xpQwpA",   # Chocolate Rain
        "https://www.youtube.com/watch?v=Ct6BUPvE2sM",   # PPAP (Pen Pineapple Apple Pen)
        "https://www.youtube.com/watch?v=XqZsoesa55w",   # Baby Shark
        "https://www.youtube.com/watch?v=j9V78UbdzWI",   # Coffin Dance (Astronomia)
        # --- Animaux legendaires ---
        "https://www.youtube.com/watch?v=MtN1YnoL46Q",   # Duck Song ("got any grapes?")
        "https://www.youtube.com/watch?v=J---aiyznGQ",   # Keyboard Cat
        #DEAD "https://www.youtube.com/watch?v=Awf45u6zrP0",   # Sail Cat (AWOLNATION)
        "https://www.youtube.com/watch?v=EIyixC9NsLI",   # Badger Badger Badger
        "https://www.youtube.com/watch?v=p3G5IXn0K7A",   # Hamster Dance
        #DEAD "https://www.youtube.com/watch?v=a1Y73sPHKxw",   # Dramatic Chipmunk
        "https://www.youtube.com/watch?v=CMNry4PE93Y",   # I Like Turtles
        # --- Prank / jumpscare wholesome ---
        "https://www.youtube.com/watch?v=6n3pFFPSlW4",   # Gnome ("you've been gnomed")
        "https://www.youtube.com/watch?v=fC7oUOUEEi4",   # Get Stick Bugged lol
        "https://www.youtube.com/watch?v=Wl959QnD3lM",   # Wide Putin Walking
        "https://www.youtube.com/watch?v=wRRsXxE1KVY",   # John Cena Prank Call
        "https://www.youtube.com/watch?v=ZXsQAXx_ao0",   # Shia LaBeouf "JUST DO IT"
        "https://www.youtube.com/watch?v=QkWS9PiXekE",   # THIS IS SPARTA
        # --- Rires contagieux ---
        "https://www.youtube.com/watch?v=WDiB4rtp1qw",   # El Risitas (Spanish Laughing Guy)
        "https://www.youtube.com/watch?v=OQSNhk5ICTI",   # Double Rainbow
        "https://www.youtube.com/watch?v=mLyOj_QD4a4",   # Leeroy Jenkins
        # --- Nostalgie 2000s ---
        "https://www.youtube.com/watch?v=s8MDNFaGfT4",   # Peanut Butter Jelly Time
        "https://www.youtube.com/watch?v=CsGYh8AacgY",   # Charlie the Unicorn
        "https://www.youtube.com/watch?v=ETfiUYij5UE",   # Thomas the Tank Engine remix
        # --- Bonus chaos ---
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=43s",  # Rickroll mais skip l'intro
        #DEAD "https://www.youtube.com/watch?v=o-YBDTqX_ZU",   # Rickroll 4K 60fps
        # Not good "https://www.youtube.com/watch?v=2Z4m4lnjxkY",   # Benny Hill Theme (Yakety Sax)
        # Not good "https://www.youtube.com/watch?v=hB8S6oKjiw8",   # Oh No Oh No Oh No No No
    ]

    @app.post("/api/attendance")
    def attendance():
        """Generate (and optionally print) a personalised student attendance ticket."""
        body, err = _parse_body()
        if err is not None:
            return err

        student_email = body.get("student_email", "").strip()
        if not student_email:
            return _err("Missing required field: 'student_email'")

        # --- Derive student name from email if not provided ---------------
        student_name = body.get("student_name", "").strip()
        if not student_name:
            local_part = student_email.split("@")[0]
            parts = local_part.replace(".", " ").replace("-", " ").split()
            # Handle numbered names like "prenom1.nom" -> "Prenom Nom"
            cleaned = []
            for p in parts:
                import re
                cleaned.append(re.sub(r'\d+', '', p).capitalize())
            student_name = " ".join(cleaned) if cleaned else local_part

        # --- Deterministic seed from email for consistent tickets ---------
        seed = int(hashlib.md5(student_email.encode()).hexdigest(), 16)
        rng = random.Random(seed)

        # --- Generate unique ticket number from email hash ----------------
        ticket_num = str(seed % 999999).zfill(6)
        commande_num = f"CMD-2025-{ticket_num}"

        # --- Pick random funny items (3-6 items) -------------------------
        now = datetime.now()
        nb_items = rng.randint(3, 6)
        chosen_items = rng.sample(
            _FUNNY_ITEMS_POOL, min(nb_items, len(_FUNNY_ITEMS_POOL))
        )

        items = []
        total_ht = 0.0
        for designation, price in chosen_items:
            qty = rng.randint(1, 3)
            total = round(price * qty, 2)
            total_ht += total
            items.append({
                "quantity": qty,
                "designation": designation,
                "unit_price": price,
                "total_price": total,
            })

        tva = round(total_ht * 0.20, 2)
        total_ttc = round(total_ht + tva, 2)

        # --- Pick random funny elements ----------------------------------
        seller = body.get("scanned_by", "").strip() or rng.choice(_FUNNY_SELLERS)
        motto = rng.choice(_FUNNY_MOTTOS)
        warning = rng.choice(_FUNNY_WARNINGS)
        footer = rng.choice(_FUNNY_FOOTERS)
        rickroll = rng.choice(_TROLL_URLS)

        # --- Build QR code URL with student identifier --------------------
        qr_value = f"{rickroll}?student={student_email}&ticket={ticket_num}"

        # --- Assemble the full ticket data --------------------------------
        ticket_data = {
            "merchant": {
                "name": "EPITECH",
                "address": "2 Rue du Professeur Charles Appleton",
            },
            "order": {
                "commande_number": commande_num,
                "ticket_number": ticket_num,
                "caisse_number": str(rng.randint(1, 42)).zfill(2),
            },
            "transaction": {
                "date": now.strftime("%Y-%m-%d"),
                "hour": now.strftime("%H:%M"),
                "type": "Sur place",
            },
            "staff": {
                "seller": seller,
            },
            "student": {
                "name": student_name,
                "email": student_email,
            },
            "items": items,
            "totals": {
                "total_ht": total_ht,
                "tva_amount": tva,
                "total_ttc": total_ttc,
            },
            "qr_code": {
                "value": qr_value,
            },
            "fun": {
                "motto": motto,
                "warning": warning,
            },
            "footer": {
                "message": footer,
            },
        }

        # --- Apply extend overrides (deep merge) -------------------------
        extend = body.get("extend")
        if extend is not None:
            if not isinstance(extend, dict):
                return _err("'extend' must be a JSON object")
            ticket_data = _deep_merge(ticket_data, extend)
            # Re-sync student info from the (possibly overridden) ticket_data
            student_name = ticket_data.get("student", {}).get("name", student_name)
            student_email = ticket_data.get("student", {}).get("email", student_email)
            ticket_num = ticket_data.get("order", {}).get("ticket_number", ticket_num)

        # --- Paper width --------------------------------------------------
        paper_width, err = _parse_paper_width(body)
        if err is not None:
            return err

        # --- Render preview -----------------------------------------------
        template = TemplateBuilder.create_attendance_template("attendance")
        config = PrinterConfig(paper_width=paper_width)
        renderer = TicketRenderer(template, config)
        preview = renderer.render_to_text(ticket_data, printer_safe=False)

        # --- Optionally print ---------------------------------------------
        printed = False
        if body.get("print", False):
            try:
                feed_lines = int(body.get("feed_lines", 3))
            except (TypeError, ValueError):
                return _err("feed_lines must be an integer")

            no_cut = bool(body.get("no_cut", False))
            printer = ZJ8360Printer(paper_width=paper_width)

            if not printer.connect():
                return _err(
                    "Could not connect to the printer. "
                    "Make sure it is plugged in and powered on.",
                    503,
                )

            try:
                tp = TicketPrinter(printer, template, config)
                ok = tp.print_formatted_ticket(
                    ticket_data,
                    cut_paper=not no_cut,
                    feed_lines=feed_lines,
                )
                printed = ok
                if not ok:
                    return _err("Failed to print the attendance ticket", 500)
            finally:
                printer.disconnect()

        return _ok({
            "student": {
                "name": student_name,
                "email": student_email,
            },
            "ticket_number": ticket_num,
            "template": "attendance",
            "paper_width": paper_width,
            "printed": printed,
            "preview": preview,
            "ticket_data": ticket_data,
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
            "POST /api/preview, POST /api/print, POST /api/attendance, POST /api/qr, "
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
    print(f"    POST http://localhost:{port}/api/attendance")
    print(f"    POST http://localhost:{port}/api/qr")
    print(f"    GET  http://localhost:{port}/api/usb")
    print(f"    GET  http://localhost:{port}/api/test")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    app.run(host="0.0.0.0", port=port, debug=debug)
