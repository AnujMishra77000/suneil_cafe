from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from orders.models import Bill, BillItem, BillPrintJob, Order
from users.models import Customer


User = get_user_model()


@override_settings(PRINT_AGENT_TOKEN="print-agent-test-token")
class PrintAgentFlowTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staffagent",
            email="staffagent@example.com",
            password="SecurePass12345",
            is_staff=True,
        )
        self.customer = Customer.objects.create(
            name="Walkin Customer",
            phone="9876543210",
            whatsapp_no="9876543210",
            address="Main Road, Pune",
        )
        self.order = Order.objects.create(
            customer=self.customer,
            customer_name="Walkin Customer",
            phone="9876543210",
            shipping_address="Main Road, Pune",
            total_price=Decimal("240.00"),
            subtotal_price=Decimal("240.00"),
            status="Placed",
        )
        self.bill = Bill.objects.create(
            order=self.order,
            recipient_type="ADMIN",
            bill_number="BILL-AGENT-001",
            customer_name="Walkin Customer",
            phone="9876543210",
            shipping_address="Main Road, Pune",
            subtotal_amount=Decimal("240.00"),
            total_amount=Decimal("240.00"),
        )
        BillItem.objects.create(
            bill=self.bill,
            product_name="Test Bread",
            quantity=2,
            unit_price=Decimal("120.00"),
        )

    def test_staff_can_queue_print_job(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("admin-bill-queue-print-job", kwargs={"bill_id": self.bill.id}),
            {"next": reverse("admin-bill-thermal-print", kwargs={"bill_id": self.bill.id})},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("print_job=queued", response["Location"])
        self.assertEqual(BillPrintJob.objects.count(), 1)
        self.assertEqual(BillPrintJob.objects.first().status, BillPrintJob.STATUS_PENDING)

    def test_queue_dedupes_when_pending_exists(self):
        BillPrintJob.objects.create(bill=self.bill, status=BillPrintJob.STATUS_PENDING)
        self.client.force_login(self.staff_user)
        response = self.client.post(reverse("admin-bill-queue-print-job", kwargs={"bill_id": self.bill.id}))
        self.assertEqual(response.status_code, 302)
        self.assertIn("print_job=exists", response["Location"])
        self.assertEqual(BillPrintJob.objects.count(), 1)

    def test_print_agent_claim_and_complete_success(self):
        job = BillPrintJob.objects.create(bill=self.bill, status=BillPrintJob.STATUS_PENDING)

        claim = self.client.get(
            "/api/orders/print-agent/jobs/next/?agent_id=mac-pos-1",
            HTTP_X_PRINT_AGENT_TOKEN="print-agent-test-token",
            HTTP_X_PRINT_AGENT_ID="mac-pos-1",
        )
        self.assertEqual(claim.status_code, 200)
        payload = claim.json()["job"]
        self.assertEqual(payload["id"], job.id)
        self.assertTrue(payload["escpos_payload_b64"])

        job.refresh_from_db()
        self.assertEqual(job.status, BillPrintJob.STATUS_CLAIMED)
        self.assertEqual(job.agent_id, "mac-pos-1")
        self.assertEqual(job.attempts, 1)

        complete = self.client.post(
            f"/api/orders/print-agent/jobs/{job.id}/complete/",
            data='{"success": true, "agent_id": "mac-pos-1"}',
            content_type="application/json",
            HTTP_X_PRINT_AGENT_TOKEN="print-agent-test-token",
            HTTP_X_PRINT_AGENT_ID="mac-pos-1",
        )
        self.assertEqual(complete.status_code, 200)

        job.refresh_from_db()
        self.assertEqual(job.status, BillPrintJob.STATUS_PRINTED)
        self.assertTrue(job.completed_at is not None)
        self.assertEqual(job.last_error, "")

    def test_print_agent_complete_failure_marks_failed(self):
        job = BillPrintJob.objects.create(
            bill=self.bill,
            status=BillPrintJob.STATUS_CLAIMED,
            claimed_at=timezone.now(),
            agent_id="mac-pos-1",
            attempts=1,
        )

        complete = self.client.post(
            f"/api/orders/print-agent/jobs/{job.id}/complete/",
            data='{"success": false, "error": "usb timeout"}',
            content_type="application/json",
            HTTP_X_PRINT_AGENT_TOKEN="print-agent-test-token",
            HTTP_X_PRINT_AGENT_ID="mac-pos-1",
        )
        self.assertEqual(complete.status_code, 200)

        job.refresh_from_db()
        self.assertEqual(job.status, BillPrintJob.STATUS_FAILED)
        self.assertIn("usb timeout", job.last_error)

    def test_print_agent_next_rejects_missing_token(self):
        BillPrintJob.objects.create(bill=self.bill, status=BillPrintJob.STATUS_PENDING)
        response = self.client.get("/api/orders/print-agent/jobs/next/")
        self.assertEqual(response.status_code, 403)
