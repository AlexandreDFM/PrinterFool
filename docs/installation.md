# Installation & Setup — HZTZPrinter

Step-by-step guide for getting HZTZPrinter running on your machine with the ZJ-8360 USB thermal ticket printer.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone & Set Up](#2-clone--set-up)
3. [Install Dependencies](#3-install-dependencies)
4. [Environment Configuration](#4-environment-configuration)
5. [USB Permissions on macOS](#5-usb-permissions-on-macos)
6. [USB Permissions on Linux](#6-usb-permissions-on-linux)
7. [Verify the Installation](#7-verify-the-installation)
8. [Upgrading](#8-upgrading)

---

## 1. Prerequisites

Make sure the following are in place before you start.

### Software

| Requirement | Minimum version | Check |
|---|---|---|
| Python | 3.9+ (3.11+ recommended) | `python3 --version` |
| pip | bundled with Python 3.9+ | `pip3 --version` |
| git | any recent version | `git --version` |

> **Note:** Python 3.9 is the minimum supported version. If your system ships an older Python, install a newer one via [python.org](https://www.python.org/downloads/) or your package manager before continuing.

### Hardware

- ZJ-8360 thermal printer **powered on**
- USB cable connecting the printer to your computer
- On **macOS**, the `libusb` system library must be present (installed via Homebrew):

```sh
brew install libusb
```

> **Note:** `libusb` is a C library that `pyusb` wraps. Without it, USB communication is not possible on macOS regardless of the Python packages installed.

---

## 2. Clone & Set Up

### Clone the repository

```sh
git clone https://github.com/your-org/HZTZPrinter.git
cd HZTZPrinter
```

### Create a virtual environment

Using a virtual environment keeps the project's dependencies isolated from your system Python.

```sh
python3 -m venv venv
```

### Activate the virtual environment

**macOS / Linux:**

```sh
source venv/bin/activate
```

**Windows (PowerShell):**

```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (cmd.exe):**

```cmd
venv\Scripts\activate.bat
```

Once activated, your shell prompt will be prefixed with `(venv)`. To leave the virtual environment at any time, run `deactivate`.

> **Note:** You must activate the virtual environment at the start of every new terminal session before running any `python` or `pip` commands for this project.

---

## 3. Install Dependencies

With the virtual environment active, install all required packages:

```sh
pip install -r requirements.txt
```

This installs the following packages:

| Package | Required version | Purpose |
|---|---|---|
| `pyusb` | ≥ 1.2.1 | Low-level USB communication with the printer |
| `qrcode` | ≥ 8.1 | QR code generation |
| `pillow` | ≥ 11.0 | Image processing for QR codes and graphics |
| `black` | ≥ 24.1.1 | Code formatter (development) |
| `flask` | ≥ 3.0 | HTTP server for the `serve` command |
| `flask-cors` | ≥ 4.0 | Cross-Origin Resource Sharing support for the server |
| `python-dotenv` | ≥ 1.0 | Loads configuration from the `.env` file |

> **Note:** `pip` will resolve and install the latest versions that satisfy the constraints above. If you are reproducing a known-good environment, consider pinning exact versions with `pip freeze > requirements.lock`.

---

## 4. Environment Configuration

The application reads runtime configuration from a `.env` file in the project root.

### Create your `.env` file

Copy the provided example file:

```sh
cp .env.example .env
```

### `.env` reference

The `.env.example` file contains the following defaults:

```ini
HZTZ_PORT=8360
HZTZ_DEBUG=false
```

| Variable | Default | Description |
|---|---|---|
| `HZTZ_PORT` | `8360` | TCP port the HTTP server listens on when running `serve` |
| `HZTZ_DEBUG` | `false` | Set to `true` to enable Flask debug mode (auto-reload, verbose errors). **Never enable in production.** |

> **Note:** The server always binds to `0.0.0.0` (all interfaces). Logging verbosity is controlled by the `--verbose` / `--quiet` CLI flags, not by an environment variable.

### Port resolution order for `serve`

When starting the HTTP server with `python fool_printer.py serve`, the port is resolved in this order — the first value found wins:

1. `--port` CLI flag passed directly to the command
2. `HZTZ_PORT` variable defined in `.env`
3. Hard-coded default: **`8360`**

Example — override the port at runtime without editing `.env`:

```sh
python fool_printer.py serve --port 9000
```

> **Note:** The `.env` file may contain secrets. It is listed in `.gitignore` by default and should **never** be committed to version control. Only `.env.example` (which contains no real secrets) should be committed.

---

## 5. USB Permissions on macOS

### How the driver is handled

The ZJ-8360 (USB Vendor ID `0x0416`, Product ID `0x5011`) uses a kernel driver that macOS attaches automatically. `pyusb` needs exclusive access to the device, so the printer code detaches the kernel driver on connection:

```python
device.detach_kernel_driver(0)
```

This happens automatically — you do not need to configure anything for this step.

### Running without `sudo`

On macOS, accessing raw USB devices may require elevated privileges the first time. If you see a `USBError: [Errno 13] Access denied` error, try:

```sh
sudo python fool_printer.py list-usb
```

For a permanent, non-`sudo` solution, you can create a macOS `launchd` rule or apply an **IOKit entitlement** to the Python binary. This is an advanced topic; for most development workflows, running with `sudo` once per session is sufficient.

> **Warning:** Do not run the HTTP server (`serve`) with `sudo` in a shared or production environment, as it would expose the process with root privileges. Use proper USB permissions or a dedicated system user instead.

### macOS USB checklist

- [ ] `libusb` is installed: `brew list libusb`
- [ ] Printer is on and USB cable is connected
- [ ] No other application (e.g., a system print driver) has claimed the device

---

## 6. USB Permissions on Linux

On Linux, the kernel grants USB access only to `root` by default. The recommended approach is a **udev rule** that grants read/write access to all users (or a specific group) for the ZJ-8360.

### Create the udev rule

Create a new rules file:

```sh
sudo nano /etc/udev/rules.d/99-zj8360.rules
```

Add the following single line:

```
SUBSYSTEM=="usb", ATTR{idVendor}=="0416", ATTR{idProduct}=="5011", MODE="0666"
```

Save the file, then reload and trigger udev:

```sh
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Unplug and reconnect the printer. You should now be able to communicate with it without `sudo`.

> **Note:** `MODE="0666"` grants read/write access to all users on the system. In a multi-user or shared environment, prefer `GROUP="plugdev", MODE="0660"` and add your user to the `plugdev` group (`sudo usermod -aG plugdev $USER`), then log out and back in for the group change to take effect.

> **Warning:** On some distributions (e.g., Fedora/RHEL with SELinux), udev rules alone may not be sufficient. Check `journalctl -xe` and SELinux audit logs if permission errors persist after adding the rule.

### Linux USB checklist

- [ ] udev rule file created at `/etc/udev/rules.d/99-zj8360.rules`
- [ ] `udevadm control --reload-rules` and `udevadm trigger` executed
- [ ] Printer unplugged and reconnected after applying the rule
- [ ] Current user is in the appropriate group (if using `GROUP=` in the rule)

---

## 7. Verify the Installation

### Step 1 — Run the self-test suite (no printer required)

```sh
python fool_printer.py test
```

This runs 13 built-in tests that cover module imports, template creation, field resolution, row rendering, QR code generation, and sample JSON loading — all entirely in software, with no USB device needed.

Expected output:

```
Results: 13/13 passed, 0/13 failed
```

> **Warning:** If any tests fail, check that all dependencies were installed correctly (`pip install -r requirements.txt`) and that the virtual environment is active. A `ModuleNotFoundError` almost always means the venv is not activated.

### Step 2 — Confirm USB printer detection

With the printer powered on and connected, run:

```sh
python fool_printer.py list-usb
```

The ZJ-8360 should appear in the output with its USB identifiers:

```
Found USB device: Vendor ID 0x0416 / Product ID 0x5011
```

If the printer is not listed:

- Verify the USB cable is firmly seated at both ends
- Try a different USB port
- On **macOS**: confirm `brew list libusb` succeeds
- On **Linux**: confirm the udev rule is in place (see [Section 6](#6-usb-permissions-on-linux))
- Run `python fool_printer.py list-usb` with `sudo` to rule out a permissions issue

---

## 8. Upgrading

To upgrade all dependencies to the latest versions that still satisfy the version constraints in `requirements.txt`, run:

```sh
pip install -r requirements.txt --upgrade
```

To also pull the latest code from the repository before upgrading:

```sh
git pull
pip install -r requirements.txt --upgrade
```

> **Note:** After a `git pull`, always re-run `pip install -r requirements.txt` (with or without `--upgrade`) to ensure any newly added dependencies are installed.