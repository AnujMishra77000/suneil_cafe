#!/usr/bin/env python3
"""Locust load/stress test suite for Thathwamasi ecommerce.

Examples:
  locust -f scripts/locustfile.py --host https://your-domain.com
  LOCUST_USE_SHAPE=true locust -f scripts/locustfile.py --headless --host https://your-domain.com

Environment variables:
  LOAD_TEST_PINCODE=560001
  LOAD_TEST_ADDRESS='Main Road, Bengaluru'
  LOAD_TEST_PHONE_PREFIX=9
  LOAD_BROWSING_WEIGHT=7
  LOAD_BUYER_WEIGHT=3
  LOAD_MIN_WAIT_SECONDS=0.4
  LOAD_MAX_WAIT_SECONDS=2.0
  LOAD_POST_ORDER_HISTORY_PROB=0.5
  LOAD_POST_ORDER_NOTIFICATION_PROB=0.5
  LOCUST_USE_SHAPE=true
  LOCUST_STAGES_JSON='[{"duration":300,"users":300,"spawn_rate":60},{"duration":900,"users":1200,"spawn_rate":90},{"duration":1200,"users":2000,"spawn_rate":120}]'
"""

from __future__ import annotations

import json
import os
import random
import threading
from typing import Dict, List

from locust import HttpUser, LoadTestShape, between, task


CATEGORY_SECTIONS = ("snacks", "bakery")
DEFAULT_STAGE_JSON = json.dumps(
    [
        {"duration": 300, "users": 300, "spawn_rate": 60},
        {"duration": 600, "users": 700, "spawn_rate": 80},
        {"duration": 900, "users": 1200, "spawn_rate": 100},
        {"duration": 1200, "users": 2000, "spawn_rate": 120},
    ]
)


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    raw = str(os.getenv(name, str(default)) or "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(min_value, value)


def _env_float(name: str, default: float, min_value: float = 0.0) -> float:
    raw = str(os.getenv(name, str(default)) or "").strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default
    return max(min_value, value)


def _clamp_probability(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalize_phone_prefix(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return (digits or "9")[:1]


def _load_stage_profile() -> List[Dict[str, int]]:
    raw = os.getenv("LOCUST_STAGES_JSON", DEFAULT_STAGE_JSON)
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        rows = json.loads(DEFAULT_STAGE_JSON)

    parsed = []
    for row in rows:
        try:
            duration = int(row.get("duration", 0))
            users = int(row.get("users", 1))
            spawn_rate = int(row.get("spawn_rate", 1))
        except (TypeError, ValueError, AttributeError):
            continue
        if duration <= 0 or users <= 0 or spawn_rate <= 0:
            continue
        parsed.append({"duration": duration, "users": users, "spawn_rate": spawn_rate})

    return parsed or json.loads(DEFAULT_STAGE_JSON)


BROWSING_WEIGHT = _env_int("LOAD_BROWSING_WEIGHT", 7)
BUYER_WEIGHT = _env_int("LOAD_BUYER_WEIGHT", 3)
MIN_WAIT_SECONDS = _env_float("LOAD_MIN_WAIT_SECONDS", 0.4, min_value=0.0)
MAX_WAIT_SECONDS = _env_float("LOAD_MAX_WAIT_SECONDS", 2.0, min_value=MIN_WAIT_SECONDS or 0.001)
POST_ORDER_HISTORY_PROB = _clamp_probability(_env_float("LOAD_POST_ORDER_HISTORY_PROB", 0.5, min_value=0.0))
POST_ORDER_NOTIFICATION_PROB = _clamp_probability(
    _env_float("LOAD_POST_ORDER_NOTIFICATION_PROB", 0.5, min_value=0.0)
)


class SharedCatalog:
    """Thread-safe cache of categories/products/pincodes for virtual users."""

    lock = threading.Lock()
    bootstrapped = False
    category_ids: List[int] = []
    product_ids: List[int] = []
    pincode_codes: List[str] = []
    _phone_seq = random.randint(100_000_000, 899_000_000)
    phone_prefix = _normalize_phone_prefix(os.getenv("LOAD_TEST_PHONE_PREFIX", "9"))

    @classmethod
    def next_phone(cls) -> str:
        with cls.lock:
            cls._phone_seq += 1
            suffix = f"{cls._phone_seq % 1_000_000_000:09d}"
            return f"{cls.phone_prefix}{suffix}"

    @classmethod
    def bootstrap(cls, user: "BaseStoreUser") -> None:
        if cls.bootstrapped:
            return

        with cls.lock:
            if cls.bootstrapped:
                return

            category_ids: List[int] = []
            product_ids: List[int] = []
            pincode_codes: List[str] = []

            for section in CATEGORY_SECTIONS:
                resp = user.client.get(
                    f"/api/products/category-cards/?section={section}",
                    name="/api/products/category-cards/",
                )
                if resp.status_code != 200:
                    continue
                try:
                    rows = resp.json() or []
                except ValueError:
                    rows = []
                for row in rows:
                    cid = row.get("id")
                    if isinstance(cid, int):
                        category_ids.append(cid)

            random.shuffle(category_ids)
            category_ids = category_ids[:40]

            for category_id in category_ids:
                resp = user.client.get(
                    f"/api/products/categories/{category_id}/products/",
                    name="/api/products/categories/[id]/products/",
                )
                if resp.status_code != 200:
                    continue
                try:
                    rows = resp.json() or []
                except ValueError:
                    rows = []
                for row in rows:
                    pid = row.get("id")
                    is_available = bool(row.get("is_available", True))
                    stock_qty = int(row.get("stock_qty") or 0)
                    if isinstance(pid, int) and is_available and stock_qty > 0:
                        product_ids.append(pid)

            pincode_resp = user.client.get(
                "/api/orders/serviceable-pincodes/",
                name="/api/orders/serviceable-pincodes/",
            )
            if pincode_resp.status_code == 200:
                try:
                    pincode_rows = (pincode_resp.json() or {}).get("pincodes") or []
                except ValueError:
                    pincode_rows = []
                for row in pincode_rows:
                    code = str(row.get("code") or "").strip()
                    if code.isdigit() and len(code) == 6:
                        pincode_codes.append(code)

            fallback_pincode = (os.getenv("LOAD_TEST_PINCODE", "") or "").strip()
            if fallback_pincode.isdigit() and len(fallback_pincode) == 6:
                pincode_codes.append(fallback_pincode)

            cls.category_ids = list(dict.fromkeys(category_ids))
            cls.product_ids = list(dict.fromkeys(product_ids))
            cls.pincode_codes = list(dict.fromkeys(pincode_codes))
            cls.bootstrapped = True


class BaseStoreUser(HttpUser):
    abstract = True
    wait_time = between(MIN_WAIT_SECONDS, MAX_WAIT_SECONDS)

    def on_start(self):
        SharedCatalog.bootstrap(self)
        self.phone = SharedCatalog.next_phone()
        self.customer_name = f"LoadUser-{self.phone[-4:]}"
        self.address = os.getenv(
            "LOAD_TEST_ADDRESS",
            "Shop No 11, MG Road, Bengaluru",
        )

    @staticmethod
    def _looks_like_expected_business_rejection(body_text: str) -> bool:
        normalized = (body_text or "").lower()
        markers = (
            "out of stock",
            "cart is empty",
            "do not deliver",
            "pincode",
            "not found",
            "only",
        )
        return any(marker in normalized for marker in markers)

    def _pick_product_id(self) -> int | None:
        if not SharedCatalog.product_ids:
            return None
        return random.choice(SharedCatalog.product_ids)

    def _pick_pincode(self) -> str:
        if SharedCatalog.pincode_codes:
            return random.choice(SharedCatalog.pincode_codes)
        return ""

    def _run_post_order_followups(self):
        if random.random() <= POST_ORDER_HISTORY_PROB:
            self.client.get(
                f"/api/orders/history-by-phone/?phone={self.phone}",
                name="/api/orders/history-by-phone/",
            )

        if random.random() <= POST_ORDER_NOTIFICATION_PROB:
            self.client.get(
                (
                    "/api/notifications/unread-count/?recipient_type=USER"
                    f"&recipient_identifier={self.phone}"
                ),
                name="/api/notifications/unread-count/",
            )
            self.client.get(
                (
                    "/api/notifications/feed/?recipient_type=USER"
                    f"&recipient_identifier={self.phone}&limit=10"
                ),
                name="/api/notifications/feed/",
            )


class BrowsingUser(BaseStoreUser):
    weight = BROWSING_WEIGHT

    @task(3)
    def view_home(self):
        self.client.get("/", name="/")

    @task(2)
    def view_section_page(self):
        section_path = random.choice(["/bakery/", "/snacks/"])
        self.client.get(section_path, name="/section-page/")

    @task(3)
    def browse_categories(self):
        section = random.choice(CATEGORY_SECTIONS)
        self.client.get(
            f"/api/products/category-cards/?section={section}",
            name="/api/products/category-cards/",
        )

    @task(3)
    def browse_products(self):
        if not SharedCatalog.category_ids:
            return
        category_id = random.choice(SharedCatalog.category_ids)
        self.client.get(
            f"/api/products/categories/{category_id}/products/",
            name="/api/products/categories/[id]/products/",
        )

    @task(2)
    def search_products(self):
        query = random.choice(["cake", "bread", "snack", "khari", "dosa"])
        self.client.get(
            f"/api/products/search/?q={query}",
            name="/api/products/search/",
        )

    @task(1)
    def view_cart(self):
        self.client.get(
            f"/api/cart/view/?phone={self.phone}",
            name="/api/cart/view/",
        )


class BuyerUser(BaseStoreUser):
    weight = BUYER_WEIGHT

    @task
    def add_to_cart_and_checkout(self):
        product_id = self._pick_product_id()
        if not product_id:
            return

        add_payload = {
            "phone": self.phone,
            "customer_name": self.customer_name,
            "whatsapp_no": self.phone,
            "product_id": product_id,
            "quantity": random.randint(1, 2),
        }
        with self.client.post(
            "/api/cart/add/",
            json=add_payload,
            name="/api/cart/add/",
            catch_response=True,
        ) as add_resp:
            if add_resp.status_code == 200:
                add_resp.success()
            else:
                add_resp.failure(f"Unexpected status {add_resp.status_code}")
                return

        self.client.get(
            f"/api/cart/view/?phone={self.phone}",
            name="/api/cart/view/",
        )

        pincode = self._pick_pincode()
        if not pincode:
            return

        place_payload = {
            "phone": self.phone,
            "customer_name": self.customer_name,
            "whatsapp_no": self.phone,
            "address": f"{self.address}, {pincode}",
            "pincode": pincode,
            "cart_phone": self.phone,
        }
        with self.client.post(
            "/api/cart/place/",
            json=place_payload,
            name="/api/cart/place/",
            catch_response=True,
        ) as place_resp:
            if place_resp.status_code == 200:
                place_resp.success()
                self._run_post_order_followups()
                return

            body_text = place_resp.text or ""
            if place_resp.status_code == 400 and self._looks_like_expected_business_rejection(body_text):
                # Business-level rejections are expected under high contention and should
                # not be treated as transport/platform instability.
                place_resp.success()
                return

            place_resp.failure(f"Unexpected status {place_resp.status_code}")


if os.getenv("LOCUST_USE_SHAPE", "false").strip().lower() in {"1", "true", "yes", "on"}:

    class StagedLoadShape(LoadTestShape):
        stages = _load_stage_profile()

        def tick(self):
            run_time = int(self.get_run_time())
            for stage in self.stages:
                if run_time < stage["duration"]:
                    return stage["users"], stage["spawn_rate"]
            return None
