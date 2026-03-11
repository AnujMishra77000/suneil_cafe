from decimal import Decimal
import os


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


def _build_payload(bill):
    width = 32
    item_width = 22
    amount_width = 10

    chunks = [b"\x1b@", b"\x1ba\x01", b"\x1bE\x01"]  # init, center, bold on
    chunks.append("Thathwamasi Bakery Cafe\n".encode("ascii", "replace"))
    chunks.append(b"\x1bE\x00")  # bold off
    chunks.append(f"Bill: {bill.bill_number}\n".encode("ascii", "replace"))
    chunks.append(f"{bill.created_at.strftime('%Y-%m-%d %H:%M')}\n".encode("ascii", "replace"))
    chunks.append(b"\x1ba\x00")  # left
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
    chunks.append(b"\x1bE\x01")
    chunks.append(f"Total: {_money(bill.total_amount)}\n".encode("ascii", "replace"))
    chunks.append(b"\x1bE\x00")
    chunks.append(("-" * width + "\n").encode("ascii"))
    chunks.append("Thank you!\n".encode("ascii"))
    chunks.append(b"\n\n\n\x1dV\x00")  # feed and cut
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
