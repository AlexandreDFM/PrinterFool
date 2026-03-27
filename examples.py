"""
Exemples d'utilisation de l'imprimante ZJ-8360

Démonstrations de différentes fonctionnalités.
"""

from printer import ZJ8360Printer
import logging

logging.basicConfig(level=logging.INFO)


def example_simple_text():
    """Exemple 1: Imprimer du texte simple"""
    printer = ZJ8360Printer()

    if not printer.connect():
        print("Impossible de se connecter à l'imprimante")
        return

    try:
        printer.print_text("Bonjour! Ceci est un test simple.")
        printer.feed_paper(2)
        print("✓ Texte simple imprimé")
    finally:
        printer.disconnect()


def example_formatted_text():
    """Exemple 2: Imprimer du texte formaté"""
    printer = ZJ8360Printer()

    if not printer.connect():
        print("Impossible de se connecter à l'imprimante")
        return

    try:
        # En-tête centré et gras
        printer.set_alignment('center')
        printer.set_font_size(2, 2)
        printer.set_bold(True)
        printer.print_centered("MAGASIN ABC")
        printer.set_bold(False)
        printer.set_font_size(1, 1)

        # Infos
        printer.set_alignment('center')
        printer.print_text("123 Rue de la Paix")
        printer.print_text("Tél: 01 23 45 67 89")

        printer.print_line("=")

        # Contenu centré à gauche
        printer.set_alignment('left')
        printer.print_text("Produit: Café expresso")
        printer.print_text("Quantité: 1")
        printer.print_text("Prix: 2,50 €")

        printer.print_line()

        # Total
        printer.set_bold(True)
        printer.print_text("TOTAL: 2,50 €")
        printer.set_bold(False)

        # Pied
        printer.set_alignment('center')
        printer.print_text("Merci de votre visite!")

        printer.feed_paper(3)
        print("✓ Texte formaté imprimé")
    finally:
        printer.disconnect()


def example_receipt():
    """Exemple 3: Imprimer un reçu complet"""
    printer = ZJ8360Printer()

    if not printer.connect():
        print("Impossible de se connecter à l'imprimante")
        return

    try:
        # Données du reçu
        items = [
            ("Café expresso", "2,50 €"),
            ("Croissant", "1,50 €"),
            ("Jus d'orange", "2,00 €"),
            ("Sandwich", "5,80 €"),
        ]

        # Imprimer le reçu
        printer.print_receipt(
            items=items,
            title="FACTURE",
            total="11,80 €"
        )

        print("✓ Reçu imprimé et papier coupé")
    finally:
        printer.disconnect()


def example_multiple_sizes():
    """Exemple 4: Différentes tailles de texte"""
    printer = ZJ8360Printer()

    if not printer.connect():
        print("Impossible de se connecter à l'imprimante")
        return

    try:
        printer.set_alignment('center')

        for size in range(1, 5):
            printer.set_font_size(size, size)
            printer.print_centered(f"Taille {size}x{size}")

        printer.set_font_size(1, 1)
        printer.feed_paper(2)
        print("✓ Différentes tailles imprimées")
    finally:
        printer.disconnect()


def example_advanced_layout():
    """Exemple 5: Mise en page avancée"""
    printer = ZJ8360Printer()

    if not printer.connect():
        print("Impossible de se connecter à l'imprimante")
        return

    try:
        # En-tête
        printer.set_alignment('center')
        printer.print_text("")
        printer.set_bold(True)
        printer.print_centered("═" * 30)
        printer.print_centered("COMMANDE #12345")
        printer.print_centered("═" * 30)
        printer.set_bold(False)

        printer.set_alignment('left')
        printer.print_text(f"Date: 27/03/2026")
        printer.print_text(f"Heure: 14:30:45")

        printer.print_line("─")

        # Tableau
        printer.print_text(f"{'Article':<20} {'Qty':>4} {'Prix':>6}")
        printer.print_line("─")

        articles = [
            ("Pizza Margherita", "2", "12,00"),
            ("Coca cola", "3", "4,50"),
            ("Salade", "1", "6,50"),
        ]

        for article, qty, price in articles:
            line = f"{article:<20} {qty:>4} {price:>6}"
            printer.print_text(line[:32])

        printer.print_line("─")

        # Total
        printer.set_bold(True)
        total_line = f"{'TOTAL':<20} {'':>4} {'23,00':>6}"
        printer.print_text(total_line[:32])
        printer.set_bold(False)

        # Footer
        printer.set_alignment('center')
        printer.print_text("")
        printer.print_centered("Merci et à bientôt!")
        printer.print_text("")

        printer.feed_paper(3)
        printer.cut_paper()
        print("✓ Mise en page avancée imprimée et coupée")
    finally:
        printer.disconnect()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        example_num = sys.argv[1]

        examples = {
            "1": example_simple_text,
            "2": example_formatted_text,
            "3": example_receipt,
            "4": example_multiple_sizes,
            "5": example_advanced_layout,
        }

        if example_num in examples:
            examples[example_num]()
        else:
            print("Exemple invalide. Utilisez 1-5")
    else:
        print("Exemples disponibles:")
        print("  python examples.py 1  - Texte simple")
        print("  python examples.py 2  - Texte formaté")
        print("  python examples.py 3  - Reçu complet")
        print("  python examples.py 4  - Différentes tailles")
        print("  python examples.py 5  - Mise en page avancée")
