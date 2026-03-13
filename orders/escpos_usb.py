from datetime import datetime
from decimal import Decimal
import os
from pathlib import Path


class EscPosPrintError(RuntimeError):
    pass


def _parse_int(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text, 0)
    except ValueError as exc:
        raise EscPosPrintError(f"Invalid USB id value: {text}") from exc


def _find_usb_device():
    try:
        import usb.core
        import usb.util
    except Exception as exc:
        raise EscPosPrintError(
            "pyusb is not installed. Install with: pip install pyusb (and libusb on macOS)."
        ) from exc

    vendor_id = _parse_int(os.getenv("ESC_POS_USB_VENDOR_ID"))
    product_id = _parse_int(os.getenv("ESC_POS_USB_PRODUCT_ID"))

    device = None
    if vendor_id is not None and product_id is not None:
        device = usb.core.find(idVendor=vendor_id, idProduct=product_id)
    else:
        for candidate in usb.core.find(find_all=True) or []:
            try:
                for cfg in candidate:
                    for interface in cfg:
                        if int(getattr(interface, "bInterfaceClass", -1)) in {7, 255}:
                            device = candidate
                            break
                    if device:
                        break
            except Exception:
                continue
            if device:
                break

    if device is None:
        raise EscPosPrintError(
            "USB ESC/POS printer not found. Set ESC_POS_USB_VENDOR_ID and ESC_POS_USB_PRODUCT_ID."
        )
    return device, usb


def _find_out_endpoint(device, usb):
    try:
        device.set_configuration()
    except usb.core.USBError:
        # Usually safe to continue if already configured.
        pass

    cfg = device.get_active_configuration()
    for interface in cfg:
        endpoint = usb.util.find_descriptor(
            interface,
            custom_match=lambda ep: usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT,
        )
        if endpoint is not None:
            return endpoint
    raise EscPosPrintError("No writable USB endpoint found for ESC/POS printer.")


def _money(value):
    amount = Decimal(str(value or "0.00")).quantize(Decimal("0.01"))
    return f"{amount:.2f}"


def _line(text, width=32):
    text = str(text or "")
    if len(text) <= width:
        return [text]
    parts = []
    while text:
        parts.append(text[:width])
        text = text[width:]
    return parts


def _resolve_logo_path_candidates():
    configured_path = (os.getenv("ESC_POS_LOGO_PATH") or "").strip()
    candidates = []
    if configured_path:
        candidates.append(Path(configured_path))

    try:
        from django.conf import settings

        base_dir = Path(settings.BASE_DIR)
        candidates.extend(
            [
                base_dir / "products" / "static" / "products" / "images" / "thathwamasi-logo-mono.png",
                base_dir / "products" / "static" / "products" / "images" / "thathwamasi-logo.png",
                base_dir / "products" / "static" / "products" / "images" / "thathwamasi-logo.jpg",
                base_dir / "staticfiles" / "products" / "images" / "thathwamasi-logo-mono.png",
                base_dir / "staticfiles" / "products" / "images" / "thathwamasi-logo.png",
                base_dir / "staticfiles" / "products" / "images" / "thathwamasi-logo.jpg",
            ]
        )
    except Exception:
        # Safe fallback for non-Django script usage.
        pass

    return candidates


def _logo_print_enabled():
    return (os.getenv("ESC_POS_PRINT_LOGO", "true") or "").strip().lower() in {"1", "true", "yes", "on"}


def _logo_max_width():
    raw = (os.getenv("ESC_POS_LOGO_MAX_WIDTH", "192") or "").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 192
    return max(64, min(value, 384))


def _build_raster_logo_command(path, max_width):
    try:
        from PIL import Image
    except Exception:
        return b""

    try:
        with Image.open(path) as image:
            image = image.convert("L")
            if image.width > max_width:
                new_height = max(1, int(image.height * (max_width / float(image.width))))
                image = image.resize((max_width, new_height))

            width = image.width
            if width % 8 != 0:
                padded_width = ((width + 7) // 8) * 8
                padded = Image.new("L", (padded_width, image.height), 255)
                padded.paste(image, (0, 0))
                image = padded

            threshold_raw = (os.getenv("ESC_POS_LOGO_THRESHOLD", "172") or "").strip()
            try:
                threshold = int(threshold_raw)
            except ValueError:
                threshold = 172
            threshold = max(1, min(threshold, 254))

            bw = image.point(lambda px: 0 if px < threshold else 255, mode="1")
            bytes_per_row = bw.width // 8
            data = bytearray()
            pixels = bw.load()

            for y in range(bw.height):
                for x_byte in range(bytes_per_row):
                    byte_val = 0
                    for bit in range(8):
                        x = x_byte * 8 + bit
                        if pixels[x, y] == 0:
                            byte_val |= 1 << (7 - bit)
                    data.append(byte_val)

            x_l = bytes_per_row & 0xFF
            x_h = (bytes_per_row >> 8) & 0xFF
            y_l = bw.height & 0xFF
            y_h = (bw.height >> 8) & 0xFF
            return b"\x1d\x76\x30\x00" + bytes([x_l, x_h, y_l, y_h]) + bytes(data)
    except Exception:
        return b""


def _build_logo_command():
    if not _logo_print_enabled():
        return b""

    max_width = _logo_max_width()
    for path in _resolve_logo_path_candidates():
        if not path.exists() or not path.is_file():
            continue
        command = _build_raster_logo_command(path, max_width=max_width)
        if command:
            return command
    return b""


def _delivery_charge(bill):
    subtotal = Decimal(str(getattr(bill, "subtotal_amount", "0.00") or "0.00"))
    discount = Decimal(str(getattr(bill, "discount_amount", "0.00") or "0.00"))
    total = Decimal(str(getattr(bill, "total_amount", "0.00") or "0.00"))
    subtotal_after_discount = max(subtotal - discount, Decimal("0.00"))
    charge = total - subtotal_after_discount
    if charge <= Decimal("0.00"):
        return Decimal("0.00")
    return charge.quantize(Decimal("0.01"))


def _enable_cut():
    return (os.getenv("ESC_POS_ENABLE_CUT", "false") or "").strip().lower() in {"1", "true", "yes", "on"}


def _build_payload(bill):
    width = 32
    item_width = 22
    amount_width = 10

    total_qty = sum(int(getattr(item, "quantity", 0) or 0) for item in bill.items.all())
    status_text = str(getattr(getattr(bill, "order", None), "status", "Placed") or "Placed")
    coupon_code = str(getattr(bill, "coupon_code", "") or "").strip()
    discount_percent = int(getattr(bill, "discount_percent", 0) or 0)
    printed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    chunks = [b"\x1b@", b"\x1b\x32"]  # init + default line spacing

    logo_command = _build_logo_command()
    if logo_command:
        chunks.append(b"\x1ba\x01")  # center
        chunks.append(logo_command)
        chunks.append(b"\n")

    chunks.append(b"\x1ba\x01")  # center
    chunks.append(b"\x1bE\x01")  # bold on
    chunks.append("THATHWAMASI BAKERY CAFE\n".encode("ascii", "replace"))
    chunks.append(b"\x1bE\x00")  # bold off
    chunks.append("Fresh - Handmade - Pure\n".encode("ascii", "replace"))
    chunks.append(("-" * width + "\n").encode("ascii"))

    chunks.append(b"\x1ba\x00")  # left
    chunks.append(f"Bill No: {bill.bill_number}\n".encode("ascii", "replace"))
    chunks.append(f"Date: {bill.created_at.strftime('%Y-%m-%d %H:%M')}\n".encode("ascii", "replace"))
    chunks.append(f"Status: {status_text}\n".encode("ascii", "replace"))
    chunks.append(f"Qty Total: {total_qty}\n".encode("ascii", "replace"))
    if coupon_code:
        chunks.append(f"Coupon: {coupon_code} (-{discount_percent}%)\n".encode("ascii", "replace"))

    chunks.append(("-" * width + "\n").encode("ascii"))

    chunks.append(f"Customer: {bill.customer_name}\n".encode("ascii", "replace"))
    chunks.append(f"Phone: {bill.phone}\n".encode("ascii", "replace"))
    for address_part in _line(f"Addr: {bill.shipping_address}", width):
        chunks.append((address_part + "\n").encode("ascii", "replace"))

    chunks.append(("-" * width + "\n").encode("ascii"))
    for item in bill.items.all():
        for product_line in _line(item.product_name, width):
            chunks.append((product_line + "\n").encode("ascii", "replace"))
        qty_part = f"{item.quantity} x {_money(item.unit_price)}"
        amt_part = _money(Decimal(str(item.unit_price)) * Decimal(str(item.quantity)))
        line = qty_part[:item_width].ljust(item_width) + amt_part.rjust(amount_width)
        chunks.append((line + "\n").encode("ascii", "replace"))

    chunks.append(("-" * width + "\n").encode("ascii"))
    chunks.append(f"Subtotal: {_money(bill.subtotal_amount)}\n".encode("ascii", "replace"))
    if getattr(bill, "discount_amount", Decimal("0.00")) > 0:
        chunks.append(
            f"Discount: -{_money(bill.discount_amount)}\n".encode("ascii", "replace")
        )
    delivery_charge = _delivery_charge(bill)
    if delivery_charge > Decimal("0.00"):
        chunks.append(f"Delivery: {_money(delivery_charge)}\n".encode("ascii", "replace"))

    chunks.append(b"\x1bE\x01")
    chunks.append(f"Grand Total: {_money(bill.total_amount)}\n".encode("ascii", "replace"))
    chunks.append(b"\x1bE\x00")
    chunks.append(("-" * width + "\n").encode("ascii"))
    chunks.append(f"Printed: {printed_at}\n".encode("ascii", "replace"))
    chunks.append("Thank you for serving with care!\n".encode("ascii", "replace"))
    chunks.append(b"\n\n\n")
    if _enable_cut():
        chunks.append(b"\x1dV\x00")
    return b"".join(chunks)


def print_bill_via_escpos_usb(bill):
    device, usb = _find_usb_device()
    endpoint = _find_out_endpoint(device, usb)
    payload = _build_payload(bill)

    max_packet = int(getattr(endpoint, "wMaxPacketSize", 64) or 64)
    packet_size = max(32, min(max_packet, 4096))

    try:
        for index in range(0, len(payload), packet_size):
            packet = payload[index : index + packet_size]
            endpoint.write(packet, timeout=5000)
    except usb.core.USBError as exc:
        raise EscPosPrintError(f"USB print failed: {exc}") from exc
    finally:
        try:
            usb.util.dispose_resources(device)
        except Exception:
            pass

    vendor = f"{int(device.idVendor):04x}"
    product = f"{int(device.idProduct):04x}"
    return f"USB {vendor}:{product}"
