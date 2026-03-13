#!/usr/bin/env python3
"""
Local POS print agent for 58mm ESC/POS printers.

Flow:
1) Poll Django API for pending print jobs
2) Receive base64 ESC/POS payload
3) Send bytes directly to USB printer (no browser / no CUPS HTML printing)
4) Mark print job success/failure back to server
"""

import argparse
import base64
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def parse_int(value):
    text = str(value or "").strip()
    if not text:
        return None
    return int(text, 0)


def build_url(base_url, path):
    base = (base_url or "").rstrip("/")
    return f"{base}{path}"


def http_json_request(method, url, headers=None, payload=None, timeout=12.0, insecure=False):
    body = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    context = None
    if insecure:
        import ssl

        context = ssl._create_unverified_context()

    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        raw = response.read().decode("utf-8")
        if not raw.strip():
            return {}
        return json.loads(raw)


def find_usb_printer(vendor_id=None, product_id=None):
    try:
        import usb.core
        import usb.util
    except Exception as exc:
        raise RuntimeError("Missing pyusb/libusb. Install pyusb and libusb first.") from exc

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
        raise RuntimeError("USB ESC/POS printer not found.")
    return device, usb


def find_out_endpoint(device, usb):
    try:
        device.set_configuration()
    except usb.core.USBError:
        pass

    cfg = device.get_active_configuration()
    for interface in cfg:
        endpoint = usb.util.find_descriptor(
            interface,
            custom_match=lambda ep: usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT,
        )
        if endpoint is not None:
            return endpoint
    raise RuntimeError("No writable USB endpoint found.")


def write_escpos_payload(payload, vendor_id=None, product_id=None):
    device, usb = find_usb_printer(vendor_id=vendor_id, product_id=product_id)
    endpoint = find_out_endpoint(device, usb)

    max_packet = int(getattr(endpoint, "wMaxPacketSize", 64) or 64)
    packet_size = max(32, min(max_packet, 4096))

    try:
        for i in range(0, len(payload), packet_size):
            endpoint.write(payload[i : i + packet_size], timeout=5000)
    finally:
        try:
            usb.util.dispose_resources(device)
        except Exception:
            pass

    return f"{int(device.idVendor):04x}:{int(device.idProduct):04x}"


def get_next_job(base_url, token, agent_id, timeout=12.0, insecure=False):
    endpoint = build_url(
        base_url,
        f"/api/orders/print-agent/jobs/next/?agent_id={urllib.parse.quote(agent_id)}",
    )
    headers = {
        "X-Print-Agent-Token": token,
        "X-Print-Agent-Id": agent_id,
    }
    return http_json_request("GET", endpoint, headers=headers, timeout=timeout, insecure=insecure)


def complete_job(base_url, token, agent_id, job_id, success, error_message="", timeout=12.0, insecure=False):
    endpoint = build_url(base_url, f"/api/orders/print-agent/jobs/{job_id}/complete/")
    headers = {
        "X-Print-Agent-Token": token,
        "X-Print-Agent-Id": agent_id,
    }
    payload = {
        "success": bool(success),
        "error": str(error_message or ""),
        "agent_id": agent_id,
    }
    return http_json_request(
        "POST",
        endpoint,
        headers=headers,
        payload=payload,
        timeout=timeout,
        insecure=insecure,
    )


def run_agent(args):
    base_url = (args.base_url or "").strip().rstrip("/")
    token = (args.token or "").strip()
    agent_id = (args.agent_id or "").strip() or socket.gethostname()
    interval = max(float(args.interval), 0.5)
    timeout = max(float(args.timeout), 3.0)

    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        raise RuntimeError("base-url must start with http:// or https://")
    if not token:
        raise RuntimeError("token is required (or set PRINT_AGENT_TOKEN)")

    vendor_id = parse_int(args.vendor_id)
    product_id = parse_int(args.product_id)

    print(f"[print-agent] started | base={base_url} | agent={agent_id}")
    if vendor_id is not None and product_id is not None:
        print(f"[print-agent] printer target usb={vendor_id:04x}:{product_id:04x}")
    else:
        print("[print-agent] printer target usb=auto-detect")

    while True:
        try:
            response = get_next_job(
                base_url=base_url,
                token=token,
                agent_id=agent_id,
                timeout=timeout,
                insecure=args.insecure,
            )
            job = (response or {}).get("job")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "ignore")
            print(f"[print-agent] poll HTTP error {exc.code}: {body[:240]}")
            if args.once:
                return 1
            time.sleep(interval)
            continue
        except Exception as exc:
            print(f"[print-agent] poll error: {exc}")
            if args.once:
                return 1
            time.sleep(interval)
            continue

        if not job:
            if args.once:
                print("[print-agent] no pending print jobs")
                return 0
            time.sleep(interval)
            continue

        job_id = job.get("id")
        bill_no = job.get("bill_number")
        payload_b64 = job.get("escpos_payload_b64") or ""
        print(f"[print-agent] claimed job #{job_id} bill={bill_no}")

        if not payload_b64:
            error = "Missing escpos_payload_b64"
            print(f"[print-agent] job #{job_id} failed: {error}")
            try:
                complete_job(base_url, token, agent_id, job_id, False, error, timeout=timeout, insecure=args.insecure)
            except Exception as ack_exc:
                print(f"[print-agent] ack error for job #{job_id}: {ack_exc}")
            if args.once:
                return 1
            time.sleep(interval)
            continue

        try:
            payload = base64.b64decode(payload_b64.encode("ascii"))
            printed_on = write_escpos_payload(payload, vendor_id=vendor_id, product_id=product_id)
            complete_job(base_url, token, agent_id, job_id, True, "", timeout=timeout, insecure=args.insecure)
            print(f"[print-agent] job #{job_id} printed successfully on {printed_on}")
        except Exception as exc:
            error_text = str(exc)
            print(f"[print-agent] job #{job_id} failed: {error_text}")
            try:
                complete_job(base_url, token, agent_id, job_id, False, error_text, timeout=timeout, insecure=args.insecure)
            except Exception as ack_exc:
                print(f"[print-agent] ack error for job #{job_id}: {ack_exc}")
            if args.once:
                return 1

        if args.once:
            return 0

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Local ESC/POS print agent for Thathwamasi.")
    parser.add_argument("--base-url", default=os.getenv("PRINT_AGENT_BASE_URL", ""), help="Example: https://www.thathwamasibakery.com")
    parser.add_argument("--token", default=os.getenv("PRINT_AGENT_TOKEN", ""), help="Must match server PRINT_AGENT_TOKEN")
    parser.add_argument("--agent-id", default=os.getenv("PRINT_AGENT_ID", socket.gethostname()))
    parser.add_argument("--interval", default=os.getenv("PRINT_AGENT_POLL_INTERVAL", "2.0"), help="Polling interval in seconds")
    parser.add_argument("--timeout", default=os.getenv("PRINT_AGENT_HTTP_TIMEOUT", "12.0"), help="HTTP timeout in seconds")
    parser.add_argument("--vendor-id", default=os.getenv("PRINT_AGENT_USB_VENDOR_ID") or os.getenv("ESC_POS_USB_VENDOR_ID", ""))
    parser.add_argument("--product-id", default=os.getenv("PRINT_AGENT_USB_PRODUCT_ID") or os.getenv("ESC_POS_USB_PRODUCT_ID", ""))
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    args = parser.parse_args()

    try:
        return run_agent(args)
    except Exception as exc:
        print(f"[print-agent] fatal: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
