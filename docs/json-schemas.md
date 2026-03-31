# JSON Data Schemas — HZTZPrinter

This page is the authoritative reference for every JSON field understood by the
template engine. It applies to:

- **CLI** — the `-j / --json` flag on `print`, `preview`, and `qr`
- **HTTP API** — the `data` body field on `POST /api/print`, `POST /api/preview`,
  and `POST /api/qr`

> **No server-side validation is performed.** Every field is optional from the
> engine's point of view. Missing optional fields are silently skipped and the
> corresponding section is simply omitted from the rendered output. Type errors
> (e.g. passing a string where a number is expected) are handled gracefully
> rather than raising an exception.

---

## Table of Contents

1. [Auto-detection](#auto-detection)
2. [Event Ticket schema](#event-ticket-schema)
3. [Receipt schema](#receipt-schema)
4. [Multiple tickets (array format)](#multiple-tickets-array-format)
5. [QR code field resolution](#qr-code-field-resolution)
6. [Sample files](#sample-files)

---

## Auto-detection

The engine inspects the **top-level keys** of the data object to pick a template
automatically. You never need to specify the template name explicitly — it is
inferred.

| Priority | Template selected | Trigger keys (ANY one is sufficient) |
|---|---|---|
| 1 | `receipt` | `merchant`, `order`, `items`, `totals` |
| 2 | `event` | `event`, `seat`, `holder` |
| fallback | `event` | _(no matching keys)_ |

Detection source — `_detect_template()` in `src/api_server.py`:

```python
_TEMPLATE_SIGNATURES = {
    "receipt": {"merchant", "order", "items", "totals"},
    "event":   {"event", "seat", "holder"},
}

def _detect_template(data):
    sample = data[0] if isinstance(data, list) else data
    keys   = set(sample.keys())
    for name, sig in _TEMPLATE_SIGNATURES.items():
        if keys & sig:          # intersection — ANY matching key triggers
            return name
    return "event"              # fallback
```

When the input is an array, the **first element** is used for detection.

---

## Event Ticket schema

### Annotated schema

```json
{
  "event": {
    "name": "Concert d'été 2026",      // displayed in the header and as the list title
    "date": "15 juillet 2026",         // card row — DATE
    "time": "20:00"                    // card row — TIME
  },
  "venue": {
    "name": "Amphithéâtre Central",    // displayed in the header (second line)
    "address": "123 Parc Central, NY 10001"  // details section
  },
  "seat": {
    "section": "A",     // card row — SECTION
    "row": "5",         // card row — ROW
    "seat": "12",       // card row — SEAT
    "gate": "Nord"      // card row — GATE
  },
  "barcode": {
    "value": "EVT00012345"    // printed as QR code (see resolution rules below)
  },
  "holder": {
    "name": "Jean Dupont"     // details section — ticket holder name
  }
}
```

### Card layout

The event card is rendered in two rows of three fields each:

```
┌──────────────────────────────────────────┐
│  DATE          TIME          SECTION     │
│  15 juil 2026  20:00         A           │
├──────────────────────────────────────────┤
│  ROW           SEAT          GATE        │
│  5             12            Nord        │
└──────────────────────────────────────────┘
```

### Field reference

| JSON path | Required | Rendered by | Notes |
|---|---|---|---|
| `event.name` | recommended | Header (line 1), list title | Event / show name |
| `event.date` | recommended | Card row — DATE | Any string format accepted |
| `event.time` | recommended | Card row — TIME | Any string format accepted |
| `venue.name` | optional | Header (line 2) | Venue or location name |
| `venue.address` | optional | Details section | Full street address |
| `seat.section` | optional | Card row — SECTION | e.g. `"A"`, `"Orchestra"` |
| `seat.row` | optional | Card row — ROW | e.g. `"5"`, `"K"` |
| `seat.seat` | optional | Card row — SEAT | e.g. `"12"`, `"22"` |
| `seat.gate` | optional | Card row — GATE | e.g. `"Nord"`, `"Main"` |
| `barcode.value` | optional | QR code | See [QR code field resolution](#qr-code-field-resolution) |
| `qr_code.value` | optional | QR code | Alternative path — takes priority over `barcode.value` |
| `holder.name` | optional | Details section | Ticket holder full name |

### Minimal working example

```json
{
  "event": { "name": "Summer Concert", "date": "July 15 2026", "time": "8:00 PM" },
  "barcode": { "value": "EVT00012345" }
}
```

### Full example (from `templates/sample_event_ticket.json`)

```json
{
  "event": {
    "name": "Concert d'été 2026",
    "date": "15 juillet 2026",
    "time": "20:00"
  },
  "venue": {
    "name": "Amphithéâtre Central",
    "address": "123 Parc Central, NY 10001"
  },
  "seat": {
    "section": "A",
    "row": "5",
    "seat": "12",
    "gate": "Nord"
  },
  "barcode": {
    "value": "EVT00012345"
  },
  "holder": {
    "name": "Jean Dupont"
  }
}
```

---

## Receipt schema

### Annotated schema

```json
{
  "merchant": {
    "name": "Coffee Shop Express",     // header — shop / company name
    "address": "42 Rue de la Paix",    // header — street address
    "postal_code": "75002",            // stored only, not rendered
    "city": "Paris",                   // stored only, not rendered
    "country": "France"                // stored only, not rendered
  },
  "order": {
    "commande_number": "CMD-2026-002156",  // card row — Commande
    "ticket_number":   "002156",           // card row — Ticket
    "caisse_number":   "02"                // card row — Caisse
  },
  "transaction": {
    "date": "2026-03-30",    // card row — Date
    "hour": "14:32",         // card row — Heure
    "type": "À emporter"     // card row — Type  (e.g. "Sur place", "À emporter")
  },
  "staff": {
    "seller": "Thomas Lefevre"   // card row — Vendeur
  },
  "items": [
    {
      "quantity":    1,                   // details — multiplier shown as "1x"
      "designation": "Cappuccino Moyen",  // details — item name / description
      "unit_price":  4.50,                // stored only, not rendered
      "total_price": 4.50,                // details — displayed as "4.50€"
      "tva":         0.72                 // stored only, not rendered
    }
  ],
  "totals": {
    "total_ht":   4.50,   // details totals — "Total HT  : 4.50€"
    "tva_amount": 0.72,   // details totals — "TVA       : 0.72€"
    "total_ttc":  5.22    // details totals — "Total TTC : 5.22€"
  },
  "qr_code": {
    "value": "CMD-2026-002156",                                    // printed as QR code
    "url":   "https://receipt.example.com/verify?ref=CMD-2026-002156"  // stored only, not rendered
  },
  "footer": {
    "message": "Merci !",              // details section — printed at the bottom
    "contact": "contact@example.com"   // stored only, not rendered
  }
}
```

### Card layout

The receipt card is rendered in three rows:

```
┌──────────────────────────────────────────┐
│  Commande                  Ticket        │
│  CMD-2026-002156           002156        │
├──────────────────────────────────────────┤
│  Date          Heure       Type          │
│  2026-03-30    14:32       À emporter    │
├──────────────────────────────────────────┤
│  Caisse                    Vendeur       │
│  02                        Thomas L.     │
└──────────────────────────────────────────┘
```

### Details / items section format

The items list and totals block are rendered as plain text in the details section:

```
Items:
  1x Cappuccino Moyen: 4.50€
  2x Croissant Jambon Fromage: 11.00€
  1x Pain au Chocolat: 3.00€

-
Total HT  : 18.50€
TVA       : 2.96€
Total TTC : 21.46€
-
```

### Field reference

| JSON path | Required | Rendered by | Notes |
|---|---|---|---|
| `merchant.name` | recommended | Header (line 1) | Shop or company name |
| `merchant.address` | optional | Header (line 2) | Street address |
| `merchant.postal_code` | optional | Not rendered | Stored only |
| `merchant.city` | optional | Not rendered | Stored only |
| `merchant.country` | optional | Not rendered | Stored only |
| `order.commande_number` | optional | Card row — Commande | Full order reference |
| `order.ticket_number` | optional | Card row — Ticket | Short ticket / receipt number |
| `order.caisse_number` | optional | Card row — Caisse | Register / till number |
| `transaction.date` | optional | Card row — Date | Date string, any format |
| `transaction.hour` | optional | Card row — Heure | Time string, any format |
| `transaction.type` | optional | Card row — Type | e.g. `"Sur place"`, `"À emporter"` |
| `staff.seller` | optional | Card row — Vendeur | Seller / cashier name |
| `items[]` | optional | Details — items list | Array of item objects (see below) |
| `items[].quantity` | — | Details | Integer; displayed as `Nx` prefix |
| `items[].designation` | — | Details | Item name or description |
| `items[].unit_price` | — | Not rendered | Stored only |
| `items[].total_price` | — | Details | Displayed as `X.XX€` |
| `items[].tva` | — | Not rendered | Stored only (per-item VAT) |
| `totals.total_ht` | optional | Details — totals block | Displayed as `X.XX€` |
| `totals.tva_amount` | optional | Details — totals block | Displayed as `X.XX€` |
| `totals.total_ttc` | optional | Details — totals block | Displayed as `X.XX€` |
| `qr_code.value` | optional | QR code | See [QR code field resolution](#qr-code-field-resolution) |
| `qr_code.url` | optional | Not rendered | Stored only |
| `footer.message` | optional | Details section | Printed at the very bottom |
| `footer.contact` | optional | Not rendered | Stored only |

### Minimal working example

```json
{
  "merchant": { "name": "My Shop" },
  "items": [
    { "quantity": 1, "designation": "Coffee", "total_price": 2.50 }
  ],
  "totals": { "total_ttc": 2.50 }
}
```

### Full example (from `templates/sample_receipt.json`)

```json
{
  "merchant": {
    "name": "Coffee Shop Express",
    "address": "42 Rue de la Paix",
    "postal_code": "75002",
    "city": "Paris",
    "country": "France"
  },
  "order": {
    "commande_number": "CMD-2026-002156",
    "ticket_number": "002156",
    "caisse_number": "02"
  },
  "transaction": {
    "date": "2026-03-30",
    "hour": "14:32",
    "type": "À emporter"
  },
  "staff": {
    "seller": "Thomas Lefevre"
  },
  "items": [
    {
      "quantity": 1,
      "designation": "Cappuccino Moyen",
      "unit_price": 4.50,
      "total_price": 4.50,
      "tva": 0.72
    },
    {
      "quantity": 2,
      "designation": "Croissant Jambon Fromage",
      "unit_price": 5.50,
      "total_price": 11.00,
      "tva": 1.76
    },
    {
      "quantity": 1,
      "designation": "Pain au Chocolat",
      "unit_price": 3.00,
      "total_price": 3.00,
      "tva": 0.48
    }
  ],
  "totals": {
    "total_ht": 18.50,
    "tva_amount": 2.96,
    "total_ttc": 21.46
  },
  "qr_code": {
    "value": "CMD-2026-002156-CAFE",
    "url": "https://receipt.cafe-express.fr/verify?ref=CMD-2026-002156"
  },
  "footer": {
    "message": "À bientôt !",
    "contact": "contact@cafe-express.fr"
  }
}
```

---

## Multiple tickets (array format)

Any endpoint or CLI flag that accepts `data` also accepts a **JSON array**. The
engine will render and print every element in order.

```json
[
  {
    "event": { "name": "Broadway Show", "date": "March 30, 2026", "time": "7:30 PM" },
    "venue": { "name": "Theatre Royal", "address": "321 Main Street, NY" },
    "seat":  { "section": "Orchestra", "row": "K", "seat": "15", "gate": "Main" },
    "barcode": { "value": "TH2026033001" },
    "holder": { "name": "Marie Martin" }
  },
  {
    "event": { "name": "Broadway Show", "date": "March 30, 2026", "time": "7:30 PM" },
    "venue": { "name": "Theatre Royal", "address": "321 Main Street, NY" },
    "seat":  { "section": "Balcony", "row": "A", "seat": "8", "gate": "Side" },
    "barcode": { "value": "TH2026033002" },
    "holder": { "name": "Pierre Laurent" }
  },
  {
    "event": { "name": "Broadway Show", "date": "March 30, 2026", "time": "7:30 PM" },
    "venue": { "name": "Theatre Royal", "address": "321 Main Street, NY" },
    "seat":  { "section": "Mezzanine", "row": "C", "seat": "22", "gate": "Main" },
    "barcode": { "value": "TH2026033003" },
    "holder": { "name": "Sophie Leclerc" }
  }
]
```

### Rules

- **Template detection** uses the first element of the array only. All tickets in
  the array are assumed to be of the same type.
- **Rendering order** matches the array order — element `0` is printed first.
- **API response** — the `count` / `printed` field in the response reflects the
  total number of individual tickets processed.
- A single-element array `[{...}]` is valid and behaves identically to a plain
  object `{...}`.

---

## QR code field resolution

The engine uses a **fallback chain** when looking up the QR code value. The first
path that resolves to a non-empty string wins:

| Priority | Path | Used by |
|---|---|---|
| 1st | `qr_code.value` | Receipt template (primary), event ticket (alternative) |
| 2nd | `barcode.value` | Event ticket template (primary) |

If neither path resolves, the QR code section is omitted entirely — no error is
raised.

**Practical guidance:**

- For **event tickets**, prefer `barcode.value`; the event template reads it
  first and it keeps the data consistent with physical ticket conventions.
- For **receipts**, use `qr_code.value`; the receipt template reads only that
  path.
- If you supply both fields, `qr_code.value` takes priority regardless of
  template.

```json
// Event ticket — recommended style
{ "barcode": { "value": "EVT00012345" } }

// Receipt — recommended style
{ "qr_code": { "value": "CMD-2026-002156" } }

// Works for both templates — qr_code.value wins
{ "qr_code": { "value": "SHARED-REF-001" }, "barcode": { "value": "IGNORED" } }
```

---

## QR-only payload (`qr` command / `POST /api/qr`)

The `qr` CLI command (with `-j`) reads `qr_code.value` or `barcode.value` from
the first ticket in the JSON file. The `POST /api/qr` endpoint takes the string
directly in its `data` field and does **not** read from a nested `qr_code` object.

```json
{
  "qr_code": {
    "value": "https://example.com/verify?ref=XYZ"
  }
}
```

> **`label` field:** The `qr_code.label` field exists in some sample files but
> is **only** used by `TicketPrinter._send_native_qr()` when printing a full
> ticket to hardware. Neither the `qr` CLI command nor `POST /api/qr` reads it.
> It has no effect on standalone QR generation.

> The `qr` command ignores all fields other than `qr_code.value` and
> `barcode.value`. No template is applied.

---

## Sample files

Ready-to-use sample files are provided in the `templates/` directory:

| File | Template | Format | Notes |
|---|---|---|---|
| `sample_event_ticket.json` | `event` | Single object | Basic event ticket — all seat fields populated |
| `sample_multiple_tickets.json` | `event` | Array of 3 | Three seats at the same show, different holders |
| `sample_receipt.json` | `receipt` | Single object | Full receipt — items with `tva`, QR code, footer |
| `sample_student_attendence_1.json` | `receipt` | Array of 1 | Receipt without per-item `tva`; `qr_code.url` omitted |
| `sample_student_attendence_2.json` | `receipt` | Single object | Full receipt including `postal_code`, `city`, `country`, per-item `tva`, and `footer.contact` |
| `sample_qr.json` | — | Single object | QR-only payload; use with the `qr` command |

Use any of these files to test a command quickly:

```sh
# Terminal preview (no printer required)
python fool_printer.py preview -j templates/sample_event_ticket.json
python fool_printer.py preview -j templates/sample_receipt.json
python fool_printer.py preview -j templates/sample_multiple_tickets.json

# QR code to terminal
python fool_printer.py qr -j templates/sample_qr.json

# Print to hardware
python fool_printer.py print -j templates/sample_receipt.json
```

---

## Field naming conventions

| Convention | Meaning |
|---|---|
| `object.key` | Dot notation — nested object field |
| `array[]` | The value is a JSON array; individual item fields listed as `array[].field` |
| `—` | Field belongs to an array element; "required" applies within each element |
| _recommended_ | The field is technically optional but the output is significantly degraded without it |
| _optional_ | Field may be omitted; its section is silently skipped |
| _not rendered_ | Field is parsed and stored but has no visual output in the current template |

---

*See also: [templates.md](templates.md) — template system internals and how to build custom templates.*