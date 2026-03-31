"""
Ticket Renderer for Thermal Printer

Renders template-based tickets to thermal printer output.
Integrates the template system with the ZJ8360Printer.
"""

from typing import Dict, Any, List, Optional
from .template_system import TicketTemplate
from .qrcode_generator import QRCodeGenerator
from dataclasses import dataclass
import logging
import time

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Unicode → ASCII replacement table for thermal printers
# ---------------------------------------------------------------------------

_PRINTER_SAFE_REPLACEMENTS = {
    "€": "$",
    "©": "(c)",
    "®": "(R)",
    "™": "(TM)",
    "•": "*",
    "–": "-",
    "—": "--",
    "…": "...",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
}


def make_printer_safe(text: str) -> str:
    """
    Convert special Unicode characters to printer-safe ASCII equivalents.

    Thermal printers often don't support full UTF-8 for typographic
    characters.  This function swaps them for ASCII-compatible alternatives.
    """
    if not isinstance(text, str):
        return str(text)
    for src, dst in _PRINTER_SAFE_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text


# ---------------------------------------------------------------------------
#  Configuration
# ---------------------------------------------------------------------------

@dataclass
class PrinterConfig:
    """Configuration for printer output."""

    paper_width: int = 40
    bold_titles: bool = True
    center_header: bool = True
    center_title: bool = True
    line_separator: str = "-"
    wrap_text: bool = True


# ---------------------------------------------------------------------------
#  Renderer (template → text)
# ---------------------------------------------------------------------------

class TicketRenderer:
    """
    Renders a TicketTemplate to formatted plain text that can be printed
    on a thermal printer or previewed in a terminal.
    """

    def __init__(
        self, template: TicketTemplate, config: Optional[PrinterConfig] = None
    ):
        self.template = template
        self.config = config or PrinterConfig()

    # -- public API --------------------------------------------------------

    def render_to_text(self, data: Dict[str, Any], printer_safe: bool = False) -> str:
        """
        Render ticket template to plain text.

        Args:
            data:          Ticket data dictionary.
            printer_safe:  If True, use ASCII-safe characters for QR codes
                           (matches actual printer output).  If False, use
                           Unicode block characters for terminal preview.

        Returns:
            Formatted text string.
        """
        return self._render(data, include_qr=True, printer_safe=printer_safe)

    # -- internal ----------------------------------------------------------

    def _render(
        self,
        data: Dict[str, Any],
        *,
        include_qr: bool = True,
        printer_safe: bool = False,
    ) -> str:
        """
        Core rendering logic shared by both the full-text renderer and the
        "without QR" variant used before sending a native QR command.
        """
        lines: List[str] = []
        rendered = self.template.render_full(data)
        w = self.config.paper_width

        # -- Title --
        if self.config.center_title and rendered.get("title"):
            lines.append("")
            if self.config.bold_titles:
                lines.append("=" * w)
            lines.append(self._center(rendered["title"]))
            if self.config.bold_titles:
                lines.append("=" * w)

        # -- Header --
        if rendered.get("header"):
            lines.append("")
            for item in rendered["header"]:
                if item:
                    if self.config.center_header:
                        lines.append(self._center(item))
                    else:
                        lines.append(self._wrap(item))

        # -- Card rows --
        if rendered.get("card"):
            lines.append("")
            lines.append(self.config.line_separator * w)
            for item in rendered["card"]:
                if item:
                    lines.append(self._wrap(item))
                    lines.append("")
            lines.append(self.config.line_separator * w)

        # -- Barcode / QR section --
        if include_qr and rendered.get("barcode"):
            self._append_barcode_section(lines, rendered["barcode"], printer_safe)

        # -- Details --
        if rendered.get("details"):
            lines.append("")
            for item in rendered["details"]:
                if item:
                    for line in item.split("\n"):
                        lines.append(self._wrap(line))

        # -- Footer spacing --
        lines.append("")
        lines.append("")

        output = "\n".join(lines)
        if printer_safe:
            output = make_printer_safe(output)
        return output

    def _render_ticket_without_qr(self, data: Dict[str, Any]) -> str:
        """Render ticket text *without* the QR/barcode section.

        Used by TicketPrinter so it can send the native ESC Z QR command
        separately after the text body.
        """
        return make_printer_safe(
            self._render(data, include_qr=False, printer_safe=False)
        )

    # -- barcode helper ----------------------------------------------------

    def _append_barcode_section(
        self,
        lines: List[str],
        barcode_info: Dict[str, Optional[str]],
        printer_safe: bool,
    ) -> None:
        lines.append("")

        if barcode_info.get("top"):
            lines.append(self._center(barcode_info["top"]))

        barcode = barcode_info.get("barcode")
        if barcode:
            label = barcode_info.get("label", "")
            try:
                qr_gen = QRCodeGenerator(paper_width=self.config.paper_width)
                if printer_safe:
                    qr_ascii = qr_gen.generate_printer_safe_ascii(barcode)
                else:
                    qr_ascii = qr_gen.generate_ascii_art(barcode)

                if qr_ascii:
                    if label:
                        lines.append(self._center(label))
                    lines.append("")
                    for qr_line in qr_ascii.split("\n"):
                        lines.append(self._center(qr_line))
                    lines.append("")
                else:
                    self._append_barcode_fallback(lines, label, barcode)
            except Exception as exc:
                logger.warning("QR generation failed: %s – falling back to text", exc)
                self._append_barcode_fallback(lines, label, barcode)

        if barcode_info.get("bottom"):
            lines.append(self._center(barcode_info["bottom"]))

    def _append_barcode_fallback(
        self, lines: List[str], label: str, barcode: str
    ) -> None:
        if label:
            lines.append(self._center(label))
        lines.append(self._center(barcode))

    # -- text helpers ------------------------------------------------------

    def _center(self, text: str) -> str:
        """Center *text* within the configured paper width."""
        text = str(text)[: self.config.paper_width]
        pad = (self.config.paper_width - len(text)) // 2
        return " " * pad + text

    def _wrap(self, text: str, indent: int = 0) -> str:
        """Word-wrap *text* to fit the paper width."""
        text = str(text)
        if not self.config.wrap_text or len(text) <= self.config.paper_width:
            return text

        words = text.split()
        result_lines: List[str] = []
        current = " " * indent

        for word in words:
            if len(current) + len(word) + 1 > self.config.paper_width:
                if current.strip():
                    result_lines.append(current)
                current = " " * indent + word
            else:
                current += (" " if current.strip() else "") + word

        if current.strip():
            result_lines.append(current)

        return "\n".join(result_lines)


# ---------------------------------------------------------------------------
#  Printer (renderer + USB hardware)
# ---------------------------------------------------------------------------

class TicketPrinter:
    """
    High-level interface for printing template-based tickets.

    Combines TicketTemplate, TicketRenderer and the ZJ8360Printer driver.
    """

    def __init__(
        self,
        printer: "ZJ8360Printer",
        template: TicketTemplate,
        config: Optional[PrinterConfig] = None,
    ):
        self.printer = printer
        self.template = template
        self.renderer = TicketRenderer(template, config)

    # -- simple print (text only, QR as ASCII art) -------------------------

    def print_ticket(
        self, data: Dict[str, Any], cut_paper: bool = True, feed_lines: int = 3
    ) -> bool:
        """Print a ticket as plain text (QR rendered as ASCII art)."""
        try:
            text = self.renderer.render_to_text(data)

            self.printer.set_alignment("left")
            self.printer.set_font_size(1, 1)
            self.printer.set_bold(False)

            if not self.printer.print_text(text):
                logger.error("Failed to print ticket text")
                return False

            if feed_lines > 0:
                self.printer.feed_paper(feed_lines)
            if cut_paper:
                self.printer.cut_paper()

            return True
        except Exception as exc:
            logger.error("Error printing ticket: %s", exc)
            return False

    # -- formatted print (native QR via ESC Z) -----------------------------

    def print_formatted_ticket(
        self, data: Dict[str, Any], cut_paper: bool = True, feed_lines: int = 3
    ) -> bool:
        """
        Print ticket with a scannable QR code using the printer's native
        ESC Z command.  The text body is sent first, then the QR command
        is written directly to the USB endpoint.
        """
        try:
            text_output = self.renderer._render_ticket_without_qr(data)

            self.printer.set_alignment("left")
            for line in text_output.split("\n"):
                self.printer.print_text(line)

            # Send native QR code if present
            barcode_data = data.get("qr_code", {}).get("value", "")
            if barcode_data:
                self._send_native_qr(data, barcode_data)

            # Footer / cut
            self.printer.set_alignment("center")
            if feed_lines > 0:
                self.printer.feed_paper(feed_lines)
            if cut_paper:
                self.printer.cut_paper()
                time.sleep(0.5)

            return True
        except Exception as exc:
            logger.error("Error printing formatted ticket: %s", exc)
            return False

    # -- QR code helpers ---------------------------------------------------

    def _send_native_qr(self, data: Dict[str, Any], barcode_data: str) -> None:
        """Send the native ESC Z QR command to the printer."""
        label = data.get("qr_code", {}).get("label", "QR Code")
        if label:
            self.printer.set_alignment("center")
            self.printer.print_text("")
            self.printer.print_text(label)
            self.printer.print_text("")

        try:
            qr_gen = QRCodeGenerator()
            escpos_cmd = qr_gen.generate_native_qr_command(
                barcode_data, version=0, ec_level="M"
            )
            if escpos_cmd:
                logger.info("Sending ESC Z QR command (%d bytes)", len(escpos_cmd))
                self.printer.device.write(self.printer.endpoint_out, escpos_cmd)
                self.printer.print_text("")
            else:
                logger.warning("Failed to generate ESC Z QR command")
        except Exception as exc:
            logger.error("Failed to print QR code: %s", exc)

    def _send_qr_with_fallback(self, data: str) -> bool:
        """
        Try the native ESC Z command first; fall back to a raster image
        if the native command fails.
        """
        qr_gen = QRCodeGenerator()

        # Attempt 1: native ESC Z
        try:
            cmd = qr_gen.generate_native_qr_command(data, version=0, ec_level="M")
            if cmd:
                self.printer.device.write(self.printer.endpoint_out, cmd)
                self.printer.print_text("")
                return True
        except Exception as exc:
            logger.debug("Native QR command failed: %s – trying raster", exc)

        # Attempt 2: raster image
        try:
            cmd = qr_gen.generate_escpos_image(data, size=QRCodeGenerator.TINY)
            if cmd:
                self.printer.device.write(self.printer.endpoint_out, cmd)
                self.printer.print_text("")
                return True
        except Exception as exc:
            logger.debug("Raster QR print failed: %s", exc)

        return False

    def print_qr_code(
        self, data: str, label: Optional[str] = None, centered: bool = True
    ) -> bool:
        """Print a standalone QR code (raster image) to the printer."""
        try:
            qr_gen = QRCodeGenerator()
            escpos_cmd = qr_gen.generate_escpos_image(data)
            if not escpos_cmd:
                logger.error("Failed to generate QR code")
                return False

            if label:
                if centered:
                    self.printer.set_alignment("center")
                self.printer.print_text(label)

            if centered:
                self.printer.set_alignment("center")

            self.printer.device.write(self.printer.endpoint_out, escpos_cmd)

            if centered:
                self.printer.set_alignment("left")

            return True
        except Exception as exc:
            logger.error("Error printing QR code: %s", exc)
            return False
