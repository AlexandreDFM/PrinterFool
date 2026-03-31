"""
QR Code Generator for Thermal Printer

Generates QR codes that can be printed on thermal printers in ESC/POS format.
Integrates seamlessly with the ZJ-8360 printer and template system.
"""

import qrcode
from io import BytesIO
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class QRCodeGenerator:
    """Generate and format QR codes for thermal printer output."""

    # QR code sizes optimized for thermal printer
    # These are in pixels for image generation
    TINY = (32, 32)  # Very small - fits comfortably (16 chars with ██)
    SMALL = (48, 48)  # Small - fits with margins (24 chars with ██)
    MEDIUM = (96, 96)  # Medium - for wider displays
    LARGE = (144, 144)  # Large - for special displays

    def __init__(self, error_correction: str = "M", paper_width: int = 40):
        """
        Initialize QR code generator.

        Args:
            error_correction: Error correction level ('L', 'M', 'Q', 'H')
            paper_width: Paper width in characters (32 for 80mm, 40 for default, 48 for 96mm)
        """
        # Map string to qrcode constant
        ec_map = {
            "L": qrcode.constants.ERROR_CORRECT_L,
            "M": qrcode.constants.ERROR_CORRECT_M,
            "Q": qrcode.constants.ERROR_CORRECT_Q,
            "H": qrcode.constants.ERROR_CORRECT_H,
        }
        self.error_correction = ec_map.get(
            error_correction, qrcode.constants.ERROR_CORRECT_M
        )
        self.paper_width = paper_width  # Support 32 or 48 character widths

    def generate_ascii_art(self, data: str) -> str:
        """
        Generate QR code as Unicode block art for terminal preview.

        Each module is rendered as one '█' character — no sampling, so the
        output is geometrically accurate and can actually be scanned from the
        screen.

        Args:
            data: Data to encode

        Returns:
            Unicode block art representation of QR code
        """
        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=self.error_correction,
                box_size=1,
                border=2,
            )
            qr.add_data(data)
            qr.make(fit=True)

            matrix = qr.get_matrix()
            lines = ["".join("█" if cell else " " for cell in row) for row in matrix]
            return "\n".join(lines)

        except Exception as e:
            logger.error("Error generating ASCII QR code: %s", e)
            return ""

    def generate_printer_safe_ascii(self, data: str) -> str:
        """
        Generate QR code as printer-safe ASCII art using '#' characters.

        Pure ASCII format that works on all devices. For actual printing, use native
        ESC Z command which properly handles QR code data without corruption.

        Args:
            data: Data to encode

        Returns:
            Printer-safe ASCII art representation of QR code (preview only)
        """
        try:
            qr = qrcode.QRCode(
                version=None,  # Auto version
                error_correction=self.error_correction,
                box_size=1,
                border=1,  # Minimal border
            )
            qr.add_data(data)
            qr.make(fit=True)

            # Get the modules (matrix)
            matrix = qr.get_matrix()

            # For ASCII preview: use single-character width
            # Sampling corrupts QR code data, so we don't sample for preview
            # Actual printing uses native ESC Z command for proper rendering

            # Convert to ASCII art
            lines = []

            for row in matrix:
                line = ""
                for cell in row:
                    # Use # if black, space if white
                    line += "#" if cell else " "

                lines.append(line)

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Error generating printer-safe ASCII QR code: {e}")
            return ""

    def generate_image(
        self, data: str, size: Tuple[int, int] = MEDIUM
    ) -> Optional[bytes]:
        """
        Generate QR code as PNG image bytes.

        Args:
            data: Data to encode
            size: Target size (width, height)

        Returns:
            PNG image bytes or None on error
        """
        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=self.error_correction,
                box_size=4,
                border=2,
            )
            qr.add_data(data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            # Resize to target size for better printing
            img = img.resize(size, qrcode.image.pil.Image.Resampling.LANCZOS)

            # Convert to bytes
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Error generating QR code image: {e}")
            return None

    def generate_escpos_image(
        self, data: str, size: Tuple[int, int] = MEDIUM
    ) -> Optional[bytes]:
        """
        Generate QR code as ESC/POS image command sequence.

        Args:
            data: Data to encode
            size: Target size (width, height)

        Returns:
            ESC/POS command bytes or None on error
        """
        try:
            from PIL import Image

            # Generate PNG image
            qr_image_bytes = self.generate_image(data, size)
            if not qr_image_bytes:
                return None

            # Load image
            img = Image.open(BytesIO(qr_image_bytes))

            # Convert to 1-bit monochrome (required for printer)
            img = img.convert("1")

            # Get image dimensions
            width, height = img.size

            # Convert to image data format expected by printer
            # ESC/POS image format: monochrome bitmap
            pixels = img.load()
            image_data = bytearray()

            # Process each row
            for y in range(height):
                # Each row is padded to byte boundary
                for x in range(0, width, 8):
                    byte_val = 0
                    for bit in range(8):
                        if x + bit < width:
                            # Get pixel (1 for black, 0 for white in monochrome)
                            if pixels[x + bit, y] == 0:  # Black pixel
                                byte_val |= 1 << (7 - bit)
                    image_data.append(byte_val)

            # ESC/POS command: GS v 0 (print raster image)
            # Format: GS v 0 m xL xH yL yH [image data]
            xL = width % 256
            xH = width // 256
            yL = height % 256
            yH = height // 256

            escpos_cmd = b"\x1d\x76\x30\x00"  # GS v 0 (image command)
            escpos_cmd += bytes([xL, xH, yL, yH])
            escpos_cmd += bytes(image_data)

            return escpos_cmd

        except Exception as e:
            logger.error(f"Error generating ESC/POS QR code command: {e}")
            return None

    def generate_native_qr_command(
        self, data: str, version: int = 0, ec_level: str = "M", component: int = 8
    ) -> Optional[bytes]:
        """
        Generate native ESC Z QR code command for thermal printer.

        Uses the printer's native QR code support via ESC Z command (from manual).
        This is more reliable than converting to raster images.

        Args:
            data: Data to encode in QR code
            version: QR version (1-40, 0=auto)
            ec_level: Error correction ('L'=0, 'M'=1, 'Q'=2, 'H'=3)
            component: Component type (1-8, default 3 for standard)

        Returns:
            ESC/POS command bytes for native QR printing
        """
        try:
            # Convert EC level to numeric value
            ec_map = {"L": 0, "M": 1, "Q": 2, "H": 3}
            ec_num = ec_map.get(ec_level, 1)

            # Encode data
            data_bytes = data.encode("utf-8")
            data_len = len(data_bytes)

            # Data length in low byte, high byte format
            dL = data_len % 256
            dH = data_len // 256

            # ESC Z m n k dL dH d1...dn
            # Format: 1B 5A m n k dL dH [data]
            escpos_cmd = b"\x1b\x5a"  # ESC Z
            escpos_cmd += bytes([version, ec_num, component, dL, dH])
            escpos_cmd += data_bytes

            return escpos_cmd

        except Exception as e:
            logger.error(f"Error generating native ESC Z QR command: {e}")
            return None


def get_qr_code_ascii(data: str) -> str:
    """
    Quick helper to get QR code as ASCII art.

    Args:
        data: Data to encode in QR code

    Returns:
        ASCII art string
    """
    generator = QRCodeGenerator()
    return generator.generate_ascii_art(data)


def get_qr_code_image(data: str) -> Optional[bytes]:
    """
    Quick helper to get QR code as PNG image bytes.

    Args:
        data: Data to encode in QR code

    Returns:
        PNG image bytes or None
    """
    generator = QRCodeGenerator()
    return generator.generate_image(data)


def get_qr_code_escpos(data: str) -> Optional[bytes]:
    """
    Quick helper to get QR code as ESC/POS command bytes.

    Args:
        data: Data to encode in QR code

    Returns:
        ESC/POS command bytes or None
    """
    generator = QRCodeGenerator()
    return generator.generate_escpos_image(data)
