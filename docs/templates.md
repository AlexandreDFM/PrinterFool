# Template System Reference

> **Source files:** `src/template_system.py` · `src/ticket_renderer.py`  
> For CLI flags see [`cli.md`](cli.md); for REST endpoints see [`api.md`](api.md).

---

## Table of Contents

1. [Auto-Detection](#1-auto-detection)
2. [Built-in Templates](#2-built-in-templates)
   - [event template](#event-template)
   - [receipt template](#receipt-template)
3. [Rendering Pipeline](#3-rendering-pipeline)
4. [Field References](#4-field-references)
5. [Card Row Layouts — `ItemLayout`](#5-card-row-layouts--itemlayout)
6. [`PrinterConfig`](#6-printerconfig)
7. [Paper Widths](#7-paper-widths)
8. [Unicode → ASCII (`printer_safe` mode)](#8-unicode--ascii-printer_safe-mode)
9. [Custom Templates](#9-custom-templates)

---

## 1. Auto-Detection

When `-t` is omitted (CLI) or the `"template"` field is absent (API), the engine
inspects the **top-level keys** of the first ticket object and matches them
against known signatures **in priority order**:

| Priority | Template | Trigger keys — any single key is enough to match |
|:--------:|----------|--------------------------------------------------|
| 1 | `receipt` | `merchant`, `order`, `items`, `totals` |
| 2 | `event` | `event`, `seat`, `holder` |
| — | `event` | *(fallback — no keys matched)* |

The same logic is used in both `fool_printer.py` and `src/api_server.py`:

```/dev/null/detect_template.py#L1-13
_TEMPLATE_SIGNATURES = {
    "receipt": {"merchant", "order", "items", "totals"},
    "event":   {"event", "seat", "holder"},
}

def _detect_template(data):
    sample = data[0] if isinstance(data, list) else data
    keys   = set(sample.keys())
    for name, sig in _TEMPLATE_SIGNATURES.items():
        if keys & sig:   # any overlap -> match
            return name
    return "event"       # safe fallback
```

> **Ordering note:** signatures are checked in insertion order — `receipt` first,
> then `event`. A payload whose keys overlap both groups resolves to `receipt`.

---

## 2. Built-in Templates

Two templates are registered under `"event"` and `"receipt"`.
Both are produced by factory methods on `TemplateBuilder` in `src/template_system.py`.

---

### `event` template

**Factory:** `TemplateBuilder.create_event_template(name="Event Ticket")`  
**Title string:** `"Event Ticket"`

#### Header fields

| Order | Data path |
|:-----:|-----------|
| 1 | `event.name` |
| 2 | `venue.name` |

#### Card rows

| Row | Layout | Item 1 | Item 2 | Item 3 |
|:---:|--------|--------|--------|--------|
| 1 | `THREE_ITEMS` | `event.date` · label **DATE** | `event.time` · label **TIME** | `seat.section` · label **SECTION** |
| 2 | `THREE_ITEMS` | `seat.row` · label **ROW** | `seat.seat` · label **SEAT** | `seat.gate` · label **GATE** |

#### Barcode section

| Attribute | Value |
|-----------|-------|
| `barcode_value` | `barcode.value` |
| `barcode_label` | `"TICKET #"` |

#### Detail items

| Order | Data path |
|:-----:|-----------|
| 1 | `holder.name` |
| 2 | `venue.address` |

#### List view

| Field | Data path |
|-------|-----------|
| Title | `event.name` |
| Subtitle | `event.date` |

#### Minimal JSON

```/dev/null/event_minimal.json#L1-7
{
  "event":   { "name": "Summer Concert 2026", "date": "15 Jul 2026", "time": "20:00" },
  "venue":   { "name": "Central Park Arena",  "address": "1 Park Ave, NY 10001" },
  "seat":    { "section": "A", "row": "5", "seat": "12", "gate": "North" },
  "barcode": { "value": "EVT-00012345" },
  "holder":  { "name": "Jane Doe" }
}
```

---

### `receipt` template

**Factory:** `TemplateBuilder.create_receipt_template(name="Receipt")`  
**Title string:** `"Receipt"`

#### Header fields

| Order | Data path |
|:-----:|-----------|
| 1 | `merchant.name` |
| 2 | `merchant.address` |

#### Card rows

| Row | Layout | Item 1 | Item 2 | Item 3 |
|:---:|--------|--------|--------|--------|
| 1 | `TWO_ITEMS` | `order.commande_number` · label **Commande** | `order.ticket_number` · label **Ticket** | — |
| 2 | `THREE_ITEMS` | `transaction.date` · label **Date** | `transaction.hour` · label **Heure** | `transaction.type` · label **Type** |
| 3 | `TWO_ITEMS` | `order.caisse_number` · label **Caisse** | `staff.seller` · label **Vendeur** | — |

#### Detail items (predefined)

| Order | Content |
|:-----:|----------|
| 1 | **Items list** — each item formatted as `{qty}x {designation}: {total_price:.2f}€` (from `items[]`) |
| 2 | **Totals** — `Total HT`, `TVA`, `Total TTC` (from `totals.total_ht`, `totals.tva_amount`, `totals.total_ttc`) |
| 3 | `footer.message` |

#### Barcode section

| Attribute | Value |
|-----------|-------|
| `barcode_value` | `qr_code.value` |
| `barcode_label` | `"QR Code"` |

#### List view

| Field | Data path |
|-------|-----------|
| Title | `merchant.name` |
| Subtitle | `transaction.date` |

#### Minimal JSON

```/dev/null/receipt_minimal.json#L1-12
{
  "merchant":    { "name": "Coffee Shop Express", "address": "42 Rue de la Paix" },
  "order":       { "commande_number": "CMD-001", "ticket_number": "001", "caisse_number": "02" },
  "transaction": { "date": "2026-03-30", "hour": "14:32", "type": "A emporter" },
  "staff":       { "seller": "Alice Martin" },
  "items": [
    { "quantity": 2, "designation": "Croissant", "total_price": 5.00 }
  ],
  "totals":  { "total_ht": 4.17, "tva_amount": 0.83, "total_ttc": 5.00 },
  "qr_code": { "value": "CMD-001-VERIFY" },
  "footer":  { "message": "Thank you!" }
}
```

---

## 3. Rendering Pipeline

Sections are rendered **top-to-bottom** in this fixed order:

```/dev/null/ticket-layout.txt#L1-32
 paper edge
 ┌──────────────────────────────────────────────┐
 │  ===========================================================================  │  1. Title border (= x paper_width)
 │                     Event Ticket                     │     centered; only when bold_titles=True
 │  ===========================================================================  │
 │                                                       │
 │            Summer Concert 2026                        │  2. Header field 1 (centered)
 │             Central Park Arena                        │     Header field 2 (centered)
 │                                                       │
 │  -----------------------------------------------------------------------  │  3. Card row border (line_separator x paper_width)
 │  DATE: 15 Jul / TIME: 20:00 / SECTION: A              │     Card Row 1  (THREE_ITEMS, joined with " / ")
 │                                                       │
 │  ROW: 5 / SEAT: 12 / GATE: North                      │     Card Row 2  (THREE_ITEMS)
 │                                                       │
 │  -----------------------------------------------------------------------  │     Card row border
 │                                                       │
 │               TICKET #                                │  4. Barcode label (centered)
 │                                                       │
 │         ▀▀▀▀▀▀▀ ▀ ▀▀▀▀▀▀▀                          │     QR code art (centered)
 │         ▀     ▀ ▀ ▀     ▀                          │     Unicode blocks in preview;
 │         ▀ ▀▀▀ ▀   ▀ ▀▀▀ ▀                          │     # chars in printer_safe;
 │         ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀                          │     native ESC/POS on hardware
 │                                                       │
 │  Jane Doe                                             │  5. Detail item 1 (left-aligned)
 │  1 Park Ave, NY 10001                                 │     Detail item 2 (multi-line ok)
 │                                                       │
 └──────────────────────────────────────────────┘
 paper edge
```

| # | Section | `TicketTemplate` attribute | Notes |
|:-:|---------|-------------------------------|-------|
| 1 | **Title** | `template.title` | Centered; bordered by `=` lines when `bold_titles=True` |
| 2 | **Header** | `template.header_fields` | Centered; one line per `FieldReference` |
| 3 | **Card rows** | `template.card_rows` | Delimited by `line_separator` chars; items joined with `" / "` |
| 4 | **Barcode / QR** | `template.barcode_section` | ASCII art in preview; native ESC/POS QR command on hardware |
| 5 | **Details** | `template.details_items` | Left-aligned; supports `\n` within a single item |

---

## 4. Field References

`FieldReference` resolves a value from the data dict at render time.
When **multiple paths** are given the first non-empty result wins (fallback chain).
If every path returns `None` or `""` the field is silently omitted from the output.

### Path syntax

| Notation | Example | Equivalent Python |
|----------|---------|-------------------|
| Dot notation | `"event.name"` | `data["event"]["name"]` |
| Bracket notation | `"event['name']"` | `data["event"]["name"]` (converted internally) |
| Array index | `"items.0.designation"` | `data["items"][0]["designation"]` |

Bracket notation is normalised by stripping `['` / `']` before the path is split,
so all three forms reach the same resolver.

### Fallback chain

```/dev/null/fallback_example.py#L1-2
# Try barcode.value first; fall back to qr_code.value
FieldReference(paths=["barcode.value", "qr_code.value"])
```

### Resolution algorithm

```/dev/null/resolve.py#L1-19
def resolve(self, data):
    for path in self.paths:
        value = self._get_nested(data, path)
        if value is not None and value != "":
            return Field(value=value)
    return None

def _get_nested(self, data, path):
    # Normalise bracket notation -> dot notation
    path = path.replace("['", ".").replace("']", "")
    path = path.replace("[", ".").replace("]", "")
    current = data
    for part in path.split("."):
        if part and current is not None:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                current = current[int(part)]  # array index
            else:
                return None
    return current
```

---

## 5. Card Row Layouts — `ItemLayout`

```/dev/null/example.py#L1
from src.template_system import ItemLayout
```

| Enum value | Internal key | Rendered output |
|------------|-------------|------------------|
| `ItemLayout.ONE_ITEM` | `"oneItem"` | `LABEL: value` |
| `ItemLayout.TWO_ITEMS` | `"twoItems"` | `LABEL1: v1 / LABEL2: v2` |
| `ItemLayout.THREE_ITEMS` | `"threeItems"` | `LABEL1: v1 / LABEL2: v2 / LABEL3: v3` |

Items are joined with `" / "` (the `TemplateRow.separator` default).
Override the separator per row:

```/dev/null/separator_example.py#L1-4
row = template.add_card_row(layout=ItemLayout.TWO_ITEMS)
row.separator = " | "    # custom separator for this row only
row.add_item(field_ref=FieldReference(paths=["order.number"]), label="ORDER")
row.add_item(field_ref=FieldReference(paths=["order.date"]),   label="DATE")
```

Empty items are dropped automatically. A row where **all** items resolve to empty
is omitted entirely from the output.

---

## 6. `PrinterConfig`

Defined as a `dataclass` in `src/ticket_renderer.py`. Controls all text formatting.

```/dev/null/printer_config_example.py#L1-11
from src.ticket_renderer import PrinterConfig

config = PrinterConfig(
    paper_width    = 40,    # characters per line
    bold_titles    = True,  # wrap title in = separator lines
    center_header  = True,  # center header field values
    center_title   = True,  # center the title string
    line_separator = "-",   # char repeated paper_width times for card borders
    wrap_text      = True,  # word-wrap lines that exceed paper_width
)
```

| Field | Type | Default | Description |
|-------|------|:-------:|-------------|
| `paper_width` | `int` | `40` | Characters per line — must match the physical paper |
| `bold_titles` | `bool` | `True` | Wrap the title in `=` separator lines |
| `center_header` | `bool` | `True` | Center each header field value |
| `center_title` | `bool` | `True` | Center the title string |
| `line_separator` | `str` | `"-"` | Character repeated `paper_width` times to form card-row borders |
| `wrap_text` | `bool` | `True` | Word-wrap any line longer than `paper_width` |

---

## 7. Paper Widths

| `paper_width` value | Physical paper width | CLI / API flag |
|:-------------------:|---------------------|:--------------:|
| `32` | ~80 mm | `--paper-width 32` |
| `40` | Standard | `--paper-width 40` |
| `48` | ~96 mm | `--paper-width 48` *(CLI default)* |

Pass `--paper-width` on the CLI or include `"paper_width"` in the API request body.

---

## 8. Unicode → ASCII (`printer_safe` mode)

Thermal printers often lack full UTF-8 coverage for typographic characters.
When `printer_safe=True` is passed to `render_to_text()` (or `--printer-safe` on the
CLI), the following substitutions are applied to the entire output **after** rendering.

```HZTZPrinter/src/ticket_renderer.py#L22-35
_PRINTER_SAFE_REPLACEMENTS = {
    "€":  "$",
    "©":  "(c)",
    "®":  "(R)",
    "™":  "(TM)",
    "•":  "*",
    "–":  "-",
    "—": "--",
    "…":  "...",
    "‘": "'",   # ‘
    "’": "'",   # ’
    "“": """,  # “
    "”": """,  # ”
}
```

| Unicode character | Replacement |
|:-----------------:|:-----------:|
| `€` | `$` |
| `©` | `(c)` |
| `®` | `(R)` |
| `™` | `(TM)` |
| `•` | `*` |
| `–` en dash | `-` |
| `—` em dash | `--` |
| `…` | `...` |
| `‘` `’` curly single quotes | `'` |
| `“` `”` curly double quotes | `"` |

> **Hardware note:** `TicketPrinter.print_formatted_ticket()` calls
> `make_printer_safe()` automatically before sending text to the USB endpoint,
> so you do not need to set `printer_safe=True` manually for hardware prints.

---

## 9. Custom Templates

### Building a template

```/dev/null/custom_template_example.py#L1-17
from src.template_system import (
    TicketTemplate, TemplateBuilder,
    FieldReference, FieldSelector, ItemLayout,
)

tpl = TicketTemplate(name="Parking Pass")
tpl.title = "PARKING PASS"
tpl.header_fields = [FieldReference(paths=["lot.name"])]

row = tpl.add_card_row(layout=ItemLayout.TWO_ITEMS)
row.add_item(field_ref=FieldReference(paths=["vehicle.plate"]), label="PLATE")
row.add_item(field_ref=FieldReference(paths=["permit.zone"]),   label="ZONE")

tpl.set_barcode_section(
    barcode_value=FieldReference(paths=["permit.code"]),
    barcode_label="SCAN TO VERIFY",
)
```

### Rendering to text

```/dev/null/render_example.py#L1-16
from src.ticket_renderer import TicketRenderer, PrinterConfig

config   = PrinterConfig(paper_width=48)
renderer = TicketRenderer(tpl, config)

data = {
    "lot":     {"name": "Lot B"},
    "vehicle": {"plate": "ABC-123"},
    "permit":  {"zone": "B2", "code": "PKG-456"},
}

# Unicode block art — for terminal preview
print(renderer.render_to_text(data, printer_safe=False))

# ASCII-safe output — matches what the physical printer produces
print(renderer.render_to_text(data, printer_safe=True))
```

### Predefined (computed) items

For values that cannot be expressed as a simple path — e.g. computed totals or
formatted time spans — pass a `predefined` callable. It receives the full data dict
and must return a `str` or `None` to silently skip the item.

```/dev/null/predefined_example.py#L1-11
def render_slot(data):
    start = data.get("slot", {}).get("start", "")
    end   = data.get("slot", {}).get("end",   "")
    return f"{start} -> {end}" if start and end else None

# In a card row
row = tpl.add_card_row(layout=ItemLayout.ONE_ITEM)
row.add_item(predefined=render_slot)

# In the details section
tpl.add_detail_item(predefined=render_slot)
```

### Adding detail items

Detail items render below the QR code as full-width, left-aligned text.
Multi-line strings (containing `\n`) are split and rendered line-by-line.

```/dev/null/detail_item_example.py#L1-11
# Path-based
tpl.add_detail_item(
    field_selector=FieldSelector(
        fields=[FieldReference(paths=["holder.note"])]
    )
)

# Inline lambda
tpl.add_detail_item(
    predefined=lambda data: "Issued: " + data.get("meta", {}).get("issued_at", "")
)
```

### Example output

Given the parking-pass template above and the sample data, `render_to_text()` produces:

```/dev/null/parking-pass-preview.txt#L1-18
================================================
             PARKING PASS
================================================

                  Lot B

------------------------------------------------
PLATE: ABC-123 / ZONE: B2

------------------------------------------------

           SCAN TO VERIFY

    ▀▀▀▀▀▀▀ ▀▀  ▀▀▀▀▀▀▀
    ▀     ▀  ▀  ▀     ▀
    ▀ ▀▀▀ ▀ ▀▀  ▀ ▀▀▀ ▀
    ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀

```

---

*This reference covers `src/template_system.py` and `src/ticket_renderer.py`.
For CLI flags see [cli.md](cli.md); for REST endpoints see [api.md](api.md).*
