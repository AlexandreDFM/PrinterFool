"""
ZJ-8360 Thermal Ticket Printer Python Interface

Module pour communiquer avec l'imprimante à tickets thermique ZJ-8360.
Supporte l'envoi de texte, formatage, images et commandes ESC/POS.

Vendor ID: 0x0416
Product ID: 0x5011
"""

import usb.core
import usb.util
from typing import Optional, List, Tuple
import logging
import time

logger = logging.getLogger(__name__)


class ZJ8360Printer:
    """
    Interface pour l'imprimante thermique ZJ-8360.

    Gère la connexion USB, l'envoi de commandes et l'impression de texte.
    """

    # Identifiants USB
    VENDOR_ID = 0x0416
    PRODUCT_ID = 0x5011

    # Paramètres de communication
    TIMEOUT = 5000  # millisecondes

    # Commandes ESC/POS
    ESC = b"\x1b"
    GS = b"\x1d"

    # Paramètres d'initialisation
    INIT = b"\x1b\x40"  # ESC @ - Initialiser

    def __init__(
        self,
        vendor_id: int = VENDOR_ID,
        product_id: int = PRODUCT_ID,
        paper_width: int = 48,
    ):
        """
        Initialiser la connexion avec l'imprimante.

        Args:
            vendor_id: ID du vendeur USB
            product_id: ID du produit USB
            paper_width: Largeur du papier en caractères (32 pour 80mm, 40 pour défaut, 48 pour 96mm)
        """
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.paper_width = paper_width  # Support 32, 40, or 48 character widths
        self.device = None
        self.endpoint_out = None
        self.endpoint_in = None

    def connect(self) -> bool:
        """
        Établir la connexion avec l'imprimante.

        Returns:
            True si la connexion est établie, False sinon
        """
        try:
            # Chercher l'imprimante
            self.device = usb.core.find(
                idVendor=self.vendor_id, idProduct=self.product_id
            )

            if self.device is None:
                logger.error(
                    f"Imprimante non trouvée (Vendor: {hex(self.vendor_id)}, Product: {hex(self.product_id)})"
                )
                return False

            logger.info("Imprimante détectée")

            # Sur macOS, détacher le driver s'il existe
            try:
                if self.device.is_kernel_driver_active(0):
                    self.device.detach_kernel_driver(0)
                    logger.info("Driver kernel détaché")
            except usb.core.USBError:
                pass

            # Configurer le device
            self.device.set_configuration()
            logger.info("Device configuré")

            # Obtenir les endpoints
            cfg = self.device.get_active_configuration()
            intf = cfg[(0, 0)]

            self.endpoint_out = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
                == usb.util.ENDPOINT_OUT,
            )

            self.endpoint_in = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
                == usb.util.ENDPOINT_IN,
            )

            if self.endpoint_out is None:
                logger.error("Endpoint OUT non trouvé")
                return False

            logger.info("Endpoints configurés avec succès")

            # Initialiser l'imprimante
            self._initialize()

            return True

        except usb.core.USBError as e:
            logger.error(f"Erreur USB: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur de connexion: {e}")
            return False

    def disconnect(self):
        """Fermer la connexion avec l'imprimante."""
        if self.device:
            try:
                # Small delay to ensure all pending commands are processed
                time.sleep(0.2)
                # Release the USB interface
                usb.util.release_interface(self.device, 0)
            except Exception:
                pass  # Interface may not have been claimed
            finally:
                self.device = None
                logger.info("Déconnecté de l'imprimante")

    def _send_command(self, data: bytes) -> bool:
        """
        Envoyer une commande à l'imprimante.

        Args:
            data: Données à envoyer (bytes)

        Returns:
            True si succès, False sinon
        """
        if self.device is None or self.endpoint_out is None:
            logger.error("Imprimante non connectée")
            return False

        try:
            self.endpoint_out.write(data, self.TIMEOUT)
            return True
        except usb.core.USBError as e:
            logger.error(f"Erreur lors de l'envoi: {e}")
            return False

    def _initialize(self):
        """Initialiser l'imprimante."""
        self._send_command(self.INIT)

    def print_text(self, text: str, encoding: str = "utf-8") -> bool:
        """
        Imprimer du texte simple.

        Args:
            text: Texte à imprimer
            encoding: Encodage du texte (par défaut utf-8)

        Returns:
            True si succès, False sinon
        """
        try:
            data = text.encode(encoding) + b"\n"
            return self._send_command(data)
        except Exception as e:
            logger.error(f"Erreur lors de l'impression: {e}")
            return False

    def print_line(self, char: str = "-", width: int = None) -> bool:
        """
        Imprimer une ligne de séparation.

        Args:
            char: Caractère à utiliser
            width: Largeur (par défaut la largeur du papier)

        Returns:
            True si succès, False sinon
        """
        if width is None:
            width = self.paper_width
        return self.print_text(char * width)

    def print_centered(self, text: str) -> bool:
        """
        Imprimer du texte centré.

        Args:
            text: Texte à centrer

        Returns:
            True si succès, False sinon
        """
        padding = (self.paper_width - len(text)) // 2
        centered_text = " " * padding + text
        return self.print_text(centered_text)

    def set_bold(self, enable: bool = True) -> bool:
        """
        Activer/désactiver le mode gras.

        Args:
            enable: True pour activer, False pour désactiver

        Returns:
            True si succès, False sinon
        """
        if enable:
            command = self.ESC + b"\x45\x01"  # ESC E 1
        else:
            command = self.ESC + b"\x45\x00"  # ESC E 0
        return self._send_command(command)

    def set_font_size(self, height: int = 1, width: int = 1) -> bool:
        """
        Définir la taille de la police.

        Args:
            height: Hauteur (1-8)
            width: Largeur (1-8)

        Returns:
            True si succès, False sinon
        """
        if not (1 <= height <= 8 and 1 <= width <= 8):
            logger.error("Taille invalide (doit être entre 1 et 8)")
            return False

        size = ((height - 1) << 4) | (width - 1)
        command = self.GS + b"\x21" + bytes([size])
        return self._send_command(command)

    def set_alignment(self, alignment: str = "left") -> bool:
        """
        Définir l'alignement du texte.

        Args:
            alignment: 'left', 'center', ou 'right'

        Returns:
            True si succès, False sinon
        """
        alignment_map = {
            "left": b"\x1b\x61\x00",  # ESC a 0
            "center": b"\x1b\x61\x01",  # ESC a 1
            "right": b"\x1b\x61\x02",  # ESC a 2
        }

        if alignment not in alignment_map:
            logger.error(f"Alignement invalide: {alignment}")
            return False

        return self._send_command(alignment_map[alignment])

    def feed_paper(self, lines: int = 3) -> bool:
        """
        Avancer le papier.

        Args:
            lines: Nombre de lignes à avancer

        Returns:
            True si succès, False sinon
        """
        for _ in range(lines):
            if not self._send_command(b"\n"):
                return False
        return True

    def cut_paper(self) -> bool:
        """
        Couper le papier.

        Returns:
            True si succès, False sinon
        """
        command = self.GS + b"\x56\x00"  # GS V 0
        return self._send_command(command)

    def print_receipt(
        self, items: List[Tuple[str, str]], title: str = "REÇU", total: str = None
    ) -> bool:
        """
        Imprimer un reçu formaté.

        Args:
            items: Liste de tuples (nom, prix)
            title: Titre du reçu
            total: Montant total (optionnel)

        Returns:
            True si succès, False sinon
        """
        try:
            # En-tête
            self.set_alignment("center")
            self.print_text("")
            self.set_font_size(2, 2)
            self.print_centered(title)
            self.set_font_size(1, 1)
            self.set_alignment("left")

            # Séparation
            self.print_line()

            # Articles
            for name, price in items:
                # Formater la ligne
                name_part = name[:20]  # Limiter le nom
                price_part = price.rjust(10)
                line = f"{name_part:<20}{price_part}"
                self.print_text(line[: self.paper_width])

            # Séparation
            self.print_line()

            # Total
            if total:
                total_line = f"{'TOTAL':<20}{total.rjust(10)}"
                self.set_bold(True)
                self.print_text(total_line[: self.paper_width])
                self.set_bold(False)

            # Pied de page
            self.set_alignment("center")
            self.print_text("")
            self.print_centered("Merci!")
            self.set_alignment("left")

            # Avancer et couper
            self.feed_paper(3)
            self.cut_paper()

            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'impression du reçu: {e}")
            return False

def list_usb_devices():
    """
    Lister tous les appareils USB disponibles.
    Utile pour le débogage.
    """
    devices = usb.core.find(find_all=True)

    if devices is None:
        print("Aucun appareil USB trouvé")
        return

    print("Appareils USB détectés:")
    print("-" * 50)

    for device in devices:
        try:
            print(
                f"Vendor: {hex(device.idVendor):>6} | Product: {hex(device.idProduct):>6} | "
                f"Manufacturer: {usb.util.get_string(device, device.iManufacturer) or 'N/A':>20}"
            )
        except Exception as e:
            print(f"Erreur lors de la lecture de l'appareil: {e}")

    print("-" * 50)
