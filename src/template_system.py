"""
Event Ticket Template System

A flexible templating system for thermal printer tickets based on
Google Wallet event ticket template structure.

Reference: https://developers.google.com/wallet/tickets/events/resources/template
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ItemLayout(Enum):
    """Template row layout options."""

    ONE_ITEM = "oneItem"
    TWO_ITEMS = "twoItems"
    THREE_ITEMS = "threeItems"


@dataclass
class Field:
    """Field value with optional label."""

    value: Any
    label: Optional[str] = None

    def is_empty(self) -> bool:
        """Check if field is empty."""
        return self.value is None or self.value == ""


@dataclass
class FieldReference:
    """Field reference for templating with fallback logic."""

    paths: List[str] = field(default_factory=list)  # Fallback field paths

    def resolve(self, data: Dict[str, Any]) -> Optional[Field]:
        """
        Resolve field by trying paths in order (fallback logic).

        Args:
            data: Data dictionary to resolve from

        Returns:
            Field object or None if not resolved
        """
        for path in self.paths:
            value = self._get_nested(data, path)
            if value is not None and value != "":
                return Field(value=value)
        return None

    def _get_nested(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value from dict using dot/bracket notation."""
        try:
            # Handle bracket notation like field['id']
            path = path.replace("['", ".").replace("']", "")
            # Handle array indices
            path = path.replace("[", ".").replace("]", "")

            current = data
            for part in path.split("."):
                if part and current is not None:
                    if isinstance(current, dict):
                        current = current.get(part)
                    elif isinstance(current, list):
                        try:
                            current = current[int(part)]
                        except (ValueError, IndexError):
                            return None
                    else:
                        return None
            return current
        except Exception as e:
            logger.debug(f"Error resolving path '{path}': {e}")
            return None


@dataclass
class TemplateItem:
    """Single item in a template row."""

    field_reference: Optional[FieldReference] = None
    predefined_item: Optional[Callable[[Dict[str, Any]], str]] = None
    label: Optional[str] = None

    def render(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Render item to string.

        Args:
            data: Data dictionary

        Returns:
            Rendered string or None if empty
        """
        if self.predefined_item:
            return self.predefined_item(data)

        if self.field_reference:
            field = self.field_reference.resolve(data)
            if field and not field.is_empty():
                if self.label:
                    return f"{self.label}: {field.value}"
                return str(field.value)

        return None


@dataclass
class TemplateRow:
    """Row in the card template with configurable layout."""

    layout: ItemLayout = ItemLayout.ONE_ITEM
    items: List[TemplateItem] = field(default_factory=list)
    separator: str = " / "

    def add_item(
        self,
        field_ref: Optional[FieldReference] = None,
        predefined: Optional[Callable] = None,
        label: Optional[str] = None,
    ) -> None:
        """Add item to row."""
        self.items.append(
            TemplateItem(
                field_reference=field_ref, predefined_item=predefined, label=label
            )
        )

    def render(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Render row to string.

        Args:
            data: Data dictionary

        Returns:
            Rendered row or None if all items empty
        """
        rendered_items = []
        for item in self.items:
            rendered = item.render(data)
            if rendered and rendered.strip():
                rendered_items.append(rendered)

        if not rendered_items:
            return None

        return self.separator.join(rendered_items)


@dataclass
class FieldSelector:
    """Selector for structured data fields."""

    fields: List[FieldReference] = field(default_factory=list)

    def render(self, data: Dict[str, Any]) -> Optional[str]:
        """Render with fallback logic."""
        for field_ref in self.fields:
            result = field_ref.resolve(data)
            if result and not result.is_empty():
                return str(result.value)
        return None


@dataclass
class DetailItem:
    """Item in details template section."""

    field_selector: Optional[FieldSelector] = None
    predefined_item: Optional[Callable] = None

    def render(self, data: Dict[str, Any]) -> Optional[str]:
        """Render detail item."""
        if self.predefined_item:
            return self.predefined_item(data)

        if self.field_selector:
            return self.field_selector.render(data)

        return None


@dataclass
class BarcodeSection:
    """Barcode section template with optional details."""

    barcode_value: Optional[FieldReference] = None
    barcode_label: Optional[str] = None
    top_detail: Optional[FieldSelector] = None
    bottom_detail: Optional[FieldSelector] = None

    def render(self, data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """
        Render barcode section.

        Returns:
            Dict with barcode and optional top/bottom details
        """
        result = {
            "barcode": None,
            "top": None,
            "bottom": None,
            "label": self.barcode_label,
        }

        if self.barcode_value:
            barcode = self.barcode_value.resolve(data)
            if barcode:
                result["barcode"] = str(barcode.value)

        if self.top_detail:
            result["top"] = self.top_detail.render(data)

        if self.bottom_detail:
            result["bottom"] = self.bottom_detail.render(data)

        return result


class TicketTemplate:
    """
    Main template for event tickets.

    Defines the structure and rendering logic for tickets with:
    - Card template (main display rows)
    - Barcode section
    - Details section
    - List template
    """

    def __init__(self, name: str = "Default"):
        """Initialize template."""
        self.name = name
        self.title: Optional[str] = None
        self.header_fields: List[FieldReference] = []  # Logo, issuer, event, venue

        # Card template sections
        self.card_rows: List[TemplateRow] = []

        # Barcode section
        self.barcode_section: Optional[BarcodeSection] = None

        # Details section
        self.details_items: List[DetailItem] = []

        # List template (for pass list view)
        self.list_title_field: Optional[FieldReference] = None
        self.list_subtitle_field: Optional[FieldReference] = None

    def add_card_row(self, layout: ItemLayout = ItemLayout.ONE_ITEM) -> TemplateRow:
        """Add a row to the card template."""
        row = TemplateRow(layout=layout)
        self.card_rows.append(row)
        return row

    def add_detail_item(
        self,
        field_selector: Optional[FieldSelector] = None,
        predefined: Optional[Callable] = None,
    ) -> DetailItem:
        """Add item to details section."""
        item = DetailItem(field_selector=field_selector, predefined_item=predefined)
        self.details_items.append(item)
        return item

    def set_barcode_section(
        self,
        barcode_value: Optional[FieldReference] = None,
        barcode_label: Optional[str] = None,
        top_detail: Optional[FieldSelector] = None,
        bottom_detail: Optional[FieldSelector] = None,
    ) -> BarcodeSection:
        """Set barcode section."""
        self.barcode_section = BarcodeSection(
            barcode_value=barcode_value,
            barcode_label=barcode_label,
            top_detail=top_detail,
            bottom_detail=bottom_detail,
        )
        return self.barcode_section

    def render_header(self, data: Dict[str, Any]) -> List[Optional[str]]:
        """
        Render title/header section.

        Returns:
            List of rendered header fields
        """
        header = []
        for field_ref in self.header_fields:
            field = field_ref.resolve(data)
            if field:
                header.append(str(field.value))
        return header

    def render_card(self, data: Dict[str, Any]) -> List[Optional[str]]:
        """
        Render card template rows.

        Returns:
            List of rendered rows
        """
        rows = []
        for row in self.card_rows:
            rendered = row.render(data)
            if rendered:
                rows.append(rendered)
        return rows

    def render_barcode(
        self, data: Dict[str, Any]
    ) -> Optional[Dict[str, Optional[str]]]:
        """Render barcode section."""
        if self.barcode_section:
            return self.barcode_section.render(data)
        return None

    def render_details(self, data: Dict[str, Any]) -> List[Optional[str]]:
        """
        Render details section.

        Returns:
            List of rendered detail items
        """
        details = []
        for item in self.details_items:
            rendered = item.render(data)
            if rendered:
                details.append(rendered)
        return details

    def render_list(self, data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """
        Render list template (for pass list view).

        Returns:
            Dict with title and subtitle for list view
        """
        result = {"title": None, "subtitle": None}

        if self.list_title_field:
            field = self.list_title_field.resolve(data)
            if field:
                result["title"] = str(field.value)

        if self.list_subtitle_field:
            field = self.list_subtitle_field.resolve(data)
            if field:
                result["subtitle"] = str(field.value)

        return result

    def render_full(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render complete ticket structure.

        Args:
            data: Ticket data dictionary

        Returns:
            Dictionary with all rendered sections
        """
        return {
            "title": self.title,
            "header": self.render_header(data),
            "card": self.render_card(data),
            "barcode": self.render_barcode(data),
            "details": self.render_details(data),
            "list": self.render_list(data),
        }


class TemplateBuilder:
    """Builder utility for creating templates."""

    @staticmethod
    def create_event_template(name: str = "Event Ticket") -> TicketTemplate:
        """Create a default event ticket template."""
        template = TicketTemplate(name=name)

        # Title
        template.title = "Event Ticket"

        # Header with logo, issuer, event, venue
        template.header_fields = [
            FieldReference(paths=["event.name"]),  # Event name
            FieldReference(paths=["venue.name"]),  # Venue name
        ]

        # Card rows - example configuration
        row1 = template.add_card_row(layout=ItemLayout.THREE_ITEMS)
        row1.add_item(field_ref=FieldReference(paths=["event.date"]), label="DATE")
        row1.add_item(field_ref=FieldReference(paths=["event.time"]), label="TIME")
        row1.add_item(field_ref=FieldReference(paths=["seat.section"]), label="SECTION")

        row2 = template.add_card_row(layout=ItemLayout.THREE_ITEMS)
        row2.add_item(field_ref=FieldReference(paths=["seat.row"]), label="ROW")
        row2.add_item(field_ref=FieldReference(paths=["seat.seat"]), label="SEAT")
        row2.add_item(field_ref=FieldReference(paths=["seat.gate"]), label="GATE")

        # Barcode
        template.set_barcode_section(
            barcode_value=FieldReference(paths=["barcode.value"]),
            barcode_label="TICKET #",
        )

        # Details
        template.add_detail_item(
            field_selector=FieldSelector(
                fields=[
                    FieldReference(paths=["holder.name"]),
                ]
            )
        )
        template.add_detail_item(
            field_selector=FieldSelector(
                fields=[
                    FieldReference(paths=["venue.address"]),
                ]
            )
        )

        # List template
        template.list_title_field = FieldReference(paths=["event.name"])
        template.list_subtitle_field = FieldReference(paths=["event.date"])

        return template

    @staticmethod
    def create_receipt_template(name: str = "Receipt") -> TicketTemplate:
        """Create a receipt template."""
        template = TicketTemplate(name=name)
        template.title = "Receipt"

        # Header with merchant info
        template.header_fields = [
            FieldReference(paths=["merchant.name"]),
            FieldReference(paths=["merchant.address"]),
        ]

        # Row 1: Order and Ticket info
        row1 = template.add_card_row(layout=ItemLayout.TWO_ITEMS)
        row1.add_item(
            field_ref=FieldReference(paths=["order.commande_number"]), label="Commande"
        )
        row1.add_item(
            field_ref=FieldReference(paths=["order.ticket_number"]), label="Ticket"
        )

        # Row 2: Date, Time, Type
        row2 = template.add_card_row(layout=ItemLayout.THREE_ITEMS)
        row2.add_item(
            field_ref=FieldReference(paths=["transaction.date"]), label="Date"
        )
        row2.add_item(
            field_ref=FieldReference(paths=["transaction.hour"]), label="Heure"
        )
        row2.add_item(
            field_ref=FieldReference(paths=["transaction.type"]), label="Type"
        )

        # Row 3: Cash register and Seller
        row3 = template.add_card_row(layout=ItemLayout.TWO_ITEMS)
        row3.add_item(
            field_ref=FieldReference(paths=["order.caisse_number"]), label="Caisse"
        )
        row3.add_item(field_ref=FieldReference(paths=["staff.seller"]), label="Vendeur")

        # Items details - handled as multi-line detail
        template.add_detail_item(
            predefined=lambda data: TemplateBuilder._format_receipt_items(data)
        )

        # Totals section with labels
        template.add_detail_item(
            predefined=lambda data: TemplateBuilder._format_receipt_totals(data)
        )

        # Barcode
        template.set_barcode_section(
            barcode_value=FieldReference(paths=["qr_code.value"]),
            barcode_label="QR Code",
        )

        # Footer
        template.add_detail_item(
            field_selector=FieldSelector(
                fields=[
                    FieldReference(paths=["footer.message"]),
                ]
            )
        )

        # List template
        template.list_title_field = FieldReference(paths=["merchant.name"])
        template.list_subtitle_field = FieldReference(paths=["transaction.date"])

        return template

    @staticmethod
    def _format_receipt_items(data: Dict[str, Any]) -> Optional[str]:
        """Format receipt items into a nicely displayed list."""
        items = data.get("items", [])
        if not items:
            return None

        lines = ["Items:"]
        for item in items:
            if isinstance(item, dict):
                qty = item.get("quantity", 1)
                desc = item.get("designation", "Item")
                total = item.get("total_price", 0)
                lines.append(f"  {qty}x {desc}: {total:.2f}€")

        return "\n".join(lines)

    @staticmethod
    def _format_receipt_totals(data: Dict[str, Any]) -> Optional[str]:
        """Format receipt totals with labels."""
        totals = data.get("totals", {})
        if not totals:
            return None

        lines = [""]
        ht = totals.get("total_ht", 0)
        tva = totals.get("tva_amount", 0)
        ttc = totals.get("total_ttc", 0)

        lines.append("-" * 40)
        lines.append(f"Total HT  : {ht:.2f}€")
        lines.append(f"TVA       : {tva:.2f}€")
        lines.append(f"Total TTC : {ttc:.2f}€")
        lines.append("-" * 40)

        return "\n".join(lines)

    @staticmethod
    def create_attendance_template(name: str = "Attendance") -> "TicketTemplate":
        """Create a student attendance receipt template (April Fools edition).

        This template renders a fake restaurant receipt that serves as a
        student attendance proof.  Each ticket is personalised with the
        student's name/email and contains randomised funny items.

        Expected JSON structure::

            {
              "merchant": { "name": "EPITECH", "address": "..." },
              "order":    { "commande_number": "...", "ticket_number": "...", "caisse_number": "..." },
              "transaction": { "date": "...", "hour": "...", "type": "Sur place" },
              "staff":    { "seller": "..." },
              "student":  { "name": "...", "email": "..." },
              "items":    [ { "quantity": 1, "designation": "...", "unit_price": 0, "total_price": 0 } ],
              "totals":   { "total_ht": 0, "tva_amount": 0, "total_ttc": 0 },
              "qr_code":  { "value": "..." },
              "footer":   { "message": "..." },
              "fun":      { "motto": "...", "warning": "..." }
            }
        """
        template = TicketTemplate(name=name)
        template.title = "EPITECH CANTINE"

        # Header with merchant info
        template.header_fields = [
            FieldReference(paths=["merchant.name"]),
            FieldReference(paths=["merchant.address"]),
        ]

        # Row 1: Order and Ticket info
        row1 = template.add_card_row(layout=ItemLayout.TWO_ITEMS)
        row1.add_item(
            field_ref=FieldReference(paths=["order.commande_number"]), label="Commande"
        )
        row1.add_item(
            field_ref=FieldReference(paths=["order.ticket_number"]), label="Ticket"
        )

        # Row 2: Date, Time, Type
        row2 = template.add_card_row(layout=ItemLayout.THREE_ITEMS)
        row2.add_item(
            field_ref=FieldReference(paths=["transaction.date"]), label="Date"
        )
        row2.add_item(
            field_ref=FieldReference(paths=["transaction.hour"]), label="Heure"
        )
        row2.add_item(
            field_ref=FieldReference(paths=["transaction.type"]), label="Type"
        )

        # Row 3: Cash register and Seller
        row3 = template.add_card_row(layout=ItemLayout.TWO_ITEMS)
        row3.add_item(
            field_ref=FieldReference(paths=["order.caisse_number"]), label="Caisse"
        )
        row3.add_item(field_ref=FieldReference(paths=["staff.seller"]), label="Vendeur")

        # Row 4: Student info
        row4 = template.add_card_row(layout=ItemLayout.ONE_ITEM)
        row4.add_item(
            field_ref=FieldReference(paths=["student.name"]), label="Etudiant"
        )

        # Items details
        template.add_detail_item(
            predefined=lambda data: TemplateBuilder._format_receipt_items(data)
        )

        # Totals section
        template.add_detail_item(
            predefined=lambda data: TemplateBuilder._format_receipt_totals(data)
        )

        # Fun motto / warning
        template.add_detail_item(
            predefined=lambda data: TemplateBuilder._format_attendance_fun(data)
        )

        # Barcode (QR Code)
        template.set_barcode_section(
            barcode_value=FieldReference(paths=["qr_code.value"]),
            barcode_label="SCAN POUR VALIDER",
        )

        # Footer
        template.add_detail_item(
            field_selector=FieldSelector(
                fields=[
                    FieldReference(paths=["footer.message"]),
                ]
            )
        )

        # List template
        template.list_title_field = FieldReference(paths=["student.name"])
        template.list_subtitle_field = FieldReference(paths=["transaction.date"])

        return template

    @staticmethod
    def _format_attendance_fun(data: Dict[str, Any]) -> Optional[str]:
        """Format the fun section of the attendance ticket."""
        fun = data.get("fun", {})
        motto = fun.get("motto", "")
        warning = fun.get("warning", "")

        if not motto and not warning:
            return None

        lines = [""]
        if motto:
            lines.append(f">> {motto} <<")
        if warning:
            lines.append("")
            lines.append(f"/!\\ {warning} /!\\")
        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Poisson d'Avril ASCII art collection
    # Sourced & adapted from https://www.asciiart.eu/animals/fish
    # ------------------------------------------------------------------

    _POISSON_DESIGNS = {
        # Clean outline fish (default)
        "classic": [
            "       _..._",
            "     ,'     `.",
            "    / O       \\",
            "---<           >----->",
            "    \\         /",
            "     `._____.'",
        ],
        # Wider outline fish – fills the paper nicely
        "big": [
            "      _________________",
            "    ,'                 `.",
            "   /    O                \\",
            "--<                       >====>",
            "   \\                     /",
            "    `._________________.'",
        ],
        # Skeleton fish – by unknown
        "skeleton": [
            "|\\    \\ \\ \\ \\ \\ \\ \\      __",
            "|  \\    \\ \\ \\ \\ \\ \\ \\   | O~-_",
            "|   >----|-|-|-|-|-|-|--|  __/",
            "|  /    / / / / / / /   |__\\",
            "|/     / / / / / / /",
        ],
        # Fish blowing bubbles – by unknown
        "bubbles": [
            "|\\   \\\\__     o",
            "| \\_/    o \\    o",
            "> _   (( <_  oo",
            "| / \\__+___/",
            "|/     |/",
        ],
        # Whale with waves – by Riitta Rasimus
        "whale": [
            "       .",
            '       ":"',
            '     ___:____     |"\\/"|',
            "   ,'        `.    \\  /",
            "   |  O        \\___/  |",
            "~^~^~^~^~^~^~^~^~^~^~^~^~",
        ],
        # School of fishes – by Linda Ball
        "school": [
            "             O  o",
            "         _\\_   o",
            ">('>   \\\\/  o\\ .",
            "      //\\___=",
            "         ''",
        ],
        # Shark – by unknown
        "shark": [
            "      .",
            " \\_____)\\____",
            "_/--v____ __`<",
            "         )/",
            "         '",
        ],
        # Jellyfish – by unknown
        "jellyfish": [
            "      _______",
            "  ,-~~~       ~~~-,",
            " (                 )",
            "  \\_-, , , , , ,-_/",
            "     / / | | \\ \\",
            "     | | | | | |",
            "     | | | | | |",
            "    / / /   \\ \\ \\",
            "    | | |   | | |",
        ],
        # Sea horse – by H P Barmario (Morfina)
        "seahorse": [
            "    \\/)/)  ",
            "   _'  oo(_.-.",
            "  /'.     .---'",
            "/'-./    ( )",
            "   ; __\\",
            "\\_.'\\ : __|",
            "    )  _/",
            "   (  (,.",
            "    '-.-'",
        ],
        # Simple trio of text fish
        "simple": [
            "    ><(((((((o>",
            "<o)))))))><",
            "         ><(((o>",
        ],
    }

    @staticmethod
    def create_poisson_template(name: str = "Poisson d'Avril") -> "TicketTemplate":
        """Create a Poisson d'Avril (April Fools fish) template.

        Expected JSON structure::

            {
              "poisson": {
                "design":   "classic",
                "subtitle": "Regarde dans ton dos !",
                "message":  "Tu t'es fait avoir !",
                "from":     "Ton collegue le plus malicieux",
                "date":     "1er Avril 2025"
              }
            }

        Available designs: classic, big, skeleton, bubbles, whale,
        school, shark, jellyfish, seahorse, simple.
        """
        template = TicketTemplate(name=name)
        template.title = "POISSON D'AVRIL !"

        # Optional centered subtitle (e.g. "Regarde dans ton dos !")
        template.header_fields = [
            FieldReference(paths=["poisson.subtitle"]),
        ]

        # ASCII fish art block (design selectable via poisson.design)
        template.add_detail_item(
            predefined=lambda data: TemplateBuilder._format_poisson_art(data)
        )

        # Personalised message, author and date
        template.add_detail_item(
            predefined=lambda data: TemplateBuilder._format_poisson_message(data)
        )

        # Decorative fish parade footer
        template.add_detail_item(
            predefined=lambda data: TemplateBuilder._format_poisson_footer(data)
        )

        # For list / multi-ticket view
        template.list_title_field = FieldReference(paths=["poisson.from"])
        template.list_subtitle_field = FieldReference(paths=["poisson.date"])

        return template

    @staticmethod
    def _format_poisson_art(data: Dict[str, Any]) -> str:
        """Return the selected ASCII-art fish centred for 40-char thermal paper.

        The design is chosen via ``data["poisson"]["design"]``.  Falls back
        to ``"classic"`` when the key is missing or unknown.
        """
        W = 40
        designs = TemplateBuilder._POISSON_DESIGNS
        choice = data.get("poisson", {}).get("design", "classic")
        if choice not in designs:
            available = ", ".join(sorted(designs))
            logger.warning(
                "Unknown poisson design '%s' - using 'classic'. "
                "Available: %s",
                choice,
                available,
            )
            choice = "classic"

        fish_lines = designs[choice]
        parts = [""]
        for line in fish_lines:
            parts.append(line.center(W) if line.strip() else "")
        parts.append("")
        parts.append("!! TU T'ES FAIT AVOIR !!".center(W))
        parts.append("")
        return "\n".join(parts)

    @staticmethod
    def _format_poisson_message(data: Dict[str, Any]) -> Optional[str]:
        """Format the personalised Poisson d'Avril message block."""
        poisson = data.get("poisson", {})
        msg   = poisson.get("message", "Bonne fete du poisson !")
        from_ = poisson.get("from", "")
        date  = poisson.get("date", "1er Avril")

        lines = ["", msg, ""]
        if from_:
            lines.append(f"De la part de : {from_}")
        lines.append(f"Le             : {date}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _format_poisson_footer(_data: Dict[str, Any]) -> str:
        """Return a decorative row of small fish for the bottom of the ticket."""
        W = 40
        decoration = "><(o>  <o)><  ><(o>  <o)><"
        return "\n" + decoration.center(W) + "\n"
