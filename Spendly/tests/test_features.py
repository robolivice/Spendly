import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_BOOTSTRAP = tempfile.TemporaryDirectory()
os.environ["SPENDLY_DATA_DIR"] = _BOOTSTRAP.name

import app as app_module
import currency
import cycles
import db
import settings


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.environ["SPENDLY_DATA_DIR"] = self.temp.name
        db.DB = str(Path(self.temp.name) / "spendly.db")
        db.setup()
        settings._cache = None
        self.pid = db.createProfile("Tester")
        self.today = date.today()
        start = self.today.replace(day=1)
        end = cycles.month_end(self.today.year, self.today.month, 31)
        db.setupCycle(
            self.pid,
            cycles.end_day_for(end),
            1000,
            start=start,
            end=end,
        )
        db.ensurePeriods(self.pid, self.today)
        self.client = app_module.app.test_client()
        with self.client.session_transaction() as session:
            session["pid"] = self.pid

    def tearDown(self):
        settings._cache = None
        self.temp.cleanup()

    def add_expense(self, on_date=None, category="Food", amount=12.5, description="Lunch"):
        return db.save(
            self.pid,
            (on_date or self.today).isoformat(),
            category,
            amount,
            description,
        )

    def test_currency_formatting(self):
        self.assertEqual(currency.format_amount(1234.5, "INR"), "₹1,234.50")
        self.assertEqual(currency.format_amount(1234.5, "USD"), "$1,234.50")
        self.assertEqual(currency.format_amount(1234.5, "EUR"), "1.234,50 €")
        self.assertEqual(currency.format_amount(1234.5, "GBP"), "£1,234.50")
        self.assertEqual(currency.format_amount(12345678, "INR"), "₹1,23,45,678.00")
        self.assertEqual(currency.format_amount(-12.5, "USD"), "-$12.50")
        self.assertEqual(currency.format_amount("bad", "USD"), "$0.00")
        self.assertEqual(currency.normalize("eur"), "EUR")
        self.assertEqual(currency.normalize("AUD"), "INR")

    def test_currency_preference_updates_pages(self):
        response = self.client.post(
            "/settings/preferences",
            data={"currency": "EUR", "next": "/period/settings"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(settings.get("currency"), "EUR")
        page = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn("€", page)
        self.assertNotIn("₹", page)

    def test_invalid_currency_falls_back(self):
        self.client.post("/settings/preferences", data={"currency": "AUD"})
        self.assertEqual(settings.get("currency"), "INR")

    def test_settings_page_lists_preferences(self):
        page = self.client.get("/period/settings").get_data(as_text=True)
        self.assertIn("Preferences", page)
        self.assertIn("Save preferences", page)
        self.assertIn("INR (₹)", page)

    def test_edit_expense(self):
        eid = self.add_expense()
        response = self.client.post(
            f"/expense/{eid}/edit",
            data={
                "date": self.today.isoformat(),
                "category": "Transport",
                "amount": "24.75",
                "description": "Train",
                "next": "/dashboard",
            },
        )
        self.assertEqual(response.status_code, 302)
        row = db.getExpense(self.pid, eid)
        self.assertEqual(row["category"], "Transport")
        self.assertEqual(row["amount"], 24.75)
        self.assertEqual(row["description"], "Train")

    def test_edit_rejects_future_date(self):
        eid = self.add_expense()
        response = self.client.post(
            f"/expense/{eid}/edit",
            data={
                "date": (self.today + timedelta(days=1)).isoformat(),
                "category": "Food",
                "amount": "99",
                "description": "Later",
                "next": "/dashboard",
            },
            follow_redirects=True,
        )
        self.assertIn("future", response.get_data(as_text=True))
        row = db.getExpense(self.pid, eid)
        self.assertEqual(row["description"], "Lunch")
        self.assertEqual(row["amount"], 12.5)

    def test_delete_and_undo(self):
        eid = self.add_expense(description="Coffee beans")
        response = self.client.post(
            f"/expense/delete/{eid}", data={"next": "/dashboard"}
        )
        self.assertEqual(response.status_code, 302)
        target = response.headers["Location"]
        action_id = int(parse_qs(urlsplit(target).query)["undo"][0])
        self.assertIsNone(db.getExpense(self.pid, eid))
        action = db.getPendingAction(self.pid, action_id)
        self.assertEqual(action["message"], "Expense deleted.")

        page = self.client.get(target).get_data(as_text=True)
        self.assertIn("Expense deleted.", page)
        self.assertIn(f"/expense/undo/{action_id}", page)

        restored = self.client.post(
            f"/expense/undo/{action_id}",
            data={"next": "/dashboard"},
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("Expense restored.", restored)
        row = db.getExpense(self.pid, eid)
        self.assertEqual(row["description"], "Coffee beans")
        self.assertIsNone(db.getPendingAction(self.pid, action_id))

        self.client.post(f"/expense/undo/{action_id}", data={"next": "/dashboard"})
        rows = db.getPeriodExpenses(
            self.pid,
            self.today.replace(day=1).isoformat(),
            self.today.isoformat(),
        )
        self.assertEqual(len([item for item in rows if item["id"] == eid]), 1)

    def test_search_current_period_and_all_time(self):
        self.add_expense(description="Coffee beans")
        old_date = self.today - timedelta(days=40)
        self.add_expense(
            on_date=old_date,
            category="Transport",
            amount=20,
            description="Bus pass",
        )

        all_time = self.client.get("/search?q=coffee&scope=all").get_data(as_text=True)
        self.assertIn("Coffee beans", all_time)
        self.assertNotIn("Bus pass", all_time)

        current = self.client.get("/search?q=bus&scope=current").get_data(as_text=True)
        self.assertNotIn("Bus pass", current)

        all_time = self.client.get("/search?q=bus&scope=all").get_data(as_text=True)
        self.assertIn("Bus pass", all_time)

        amount = self.client.get("/search?q=12.50&scope=all").get_data(as_text=True)
        self.assertIn("Coffee beans", amount)

    def test_search_delete_returns_to_results(self):
        eid = self.add_expense(description="Coffee beans")
        target = "/search?q=coffee&scope=all"
        response = self.client.post(
            f"/expense/delete/{eid}", data={"next": target}
        )
        location = response.headers["Location"]
        self.assertTrue(location.startswith(target))
        self.assertIn("undo=", location)
        page = self.client.get(location).get_data(as_text=True)
        self.assertIn("Search", page)
        self.assertIn("Expense deleted.", page)


if __name__ == "__main__":
    unittest.main()
