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
import insights
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

    def test_default_categories_seeded(self):
        names = [row["name"] for row in db.getCategories(self.pid)]
        self.assertEqual(names, ["Food", "Transport", "Shopping", "Bills", "Other"])

    def test_existing_expense_categories_are_adopted(self):
        db.save(self.pid, self.today.isoformat(), "Pets", 15, "Cat food")
        db.setup()
        names = [row["name"] for row in db.getCategories(self.pid)]
        self.assertIn("Pets", names)
        self.assertEqual(len(names), 6)

    def test_existing_expense_categories_match_case_insensitively(self):
        db.save(self.pid, self.today.isoformat(), "food", 9, "Snack")
        db.setup()
        names = [row["name"] for row in db.getCategories(self.pid)]
        self.assertEqual(names.count("Food"), 1)
        self.assertNotIn("food", names)
        rows = db.getPeriodExpenses(
            self.pid,
            self.today.replace(day=1).isoformat(),
            self.today.isoformat(),
        )
        snack = next(item for item in rows if item["description"] == "Snack")
        self.assertEqual(snack["category"], "Food")

    def test_category_crud(self):
        response = self.client.post(
            "/categories/add",
            data={
                "name": "Pets",
                "color": "accent",
                "budget": "120",
                "next": "/period/settings",
            },
            follow_redirects=True,
        )
        self.assertIn("Category added.", response.get_data(as_text=True))
        categories = {row["name"]: row for row in db.getCategories(self.pid)}
        self.assertEqual(categories["Pets"]["budget"], 120)
        self.assertEqual(categories["Pets"]["color"], "accent")

        duplicate = self.client.post(
            "/categories/add",
            data={
                "name": "food",
                "color": "accent",
                "budget": "",
                "next": "/period/settings",
            },
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("already exists", duplicate)
        self.assertEqual(len(db.getCategories(self.pid)), 6)

        category_id = categories["Pets"]["id"]
        saved = self.client.post(
            f"/categories/{category_id}/update",
            data={
                "name": "Pet care",
                "color": "ok",
                "budget": "150",
                "next": "/period/settings",
            },
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("Category saved.", saved)
        updated = db.getCategory(self.pid, category_id)
        self.assertEqual(updated["name"], "Pet care")
        self.assertEqual(updated["budget"], 150)
        self.assertEqual(updated["color"], "ok")

    def test_category_rename_updates_expenses(self):
        eid = self.add_expense(category="Food")
        category = {row["name"]: row for row in db.getCategories(self.pid)}["Food"]
        response = self.client.post(
            f"/categories/{category['id']}/update",
            data={
                "name": "Dining",
                "color": "cat-food",
                "budget": "",
                "next": "/period/settings",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.getExpense(self.pid, eid)["category"], "Dining")
        page = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn("Dining", page)

    def test_category_delete_rules(self):
        self.add_expense(category="Food")
        rows = {row["name"]: row for row in db.getCategories(self.pid)}
        used = self.client.post(
            f"/categories/{rows['Food']['id']}/delete",
            data={"next": "/period/settings"},
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("still has expenses", used)
        deleted = self.client.post(
            f"/categories/{rows['Shopping']['id']}/delete",
            data={"next": "/period/settings"},
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("Category deleted.", deleted)
        names = [row["name"] for row in db.getCategories(self.pid)]
        self.assertIn("Food", names)
        self.assertNotIn("Shopping", names)

        second = db.createProfile("Second")
        second_rows = db.getCategories(second)
        for row in second_rows[:-1]:
            self.assertEqual(db.deleteCategory(second, row["id"]), "ok")
        self.assertEqual(db.deleteCategory(second, second_rows[-1]["id"]), "last")

    def test_custom_category_on_expense(self):
        self.client.post(
            "/categories/add",
            data={
                "name": "Pets",
                "color": "cat-transport",
                "budget": "",
                "next": "/period/settings",
            },
        )
        self.client.post(
            "/expense/add",
            data={
                "date": self.today.isoformat(),
                "category": "Pets",
                "amount": "25",
                "description": "Cat food",
            },
        )
        self.client.post(
            "/expense/add",
            data={
                "date": self.today.isoformat(),
                "category": "Unknown",
                "amount": "5",
                "description": "Mystery",
            },
        )
        rows = db.getPeriodExpenses(
            self.pid,
            self.today.replace(day=1).isoformat(),
            self.today.isoformat(),
        )
        categories = [item["category"] for item in rows]
        self.assertIn("Pets", categories)
        self.assertIn("Other", categories)

    def test_category_budget_and_insights_render(self):
        category = {row["name"]: row for row in db.getCategories(self.pid)}["Food"]
        self.client.post(
            f"/categories/{category['id']}/update",
            data={
                "name": "Food",
                "color": "cat-food",
                "budget": "120",
                "next": "/period/settings",
            },
        )
        self.add_expense(category="Food", amount=96, description="Groceries")
        page = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn("By category", page)
        self.assertIn("Spending pace", page)
        self.assertIn("Safe to spend / day", page)
        self.assertIn("80% of", page)
        self.assertIn("donut-seg", page)
        self.assertIn("legend-item", page)

    def test_insights_pacing(self):
        start = date(2026, 1, 1)
        end = date(2026, 1, 10)
        today = date(2026, 1, 5)
        result = insights.pacing(start, end, 300, 1000, today)
        self.assertEqual(result["total_days"], 10)
        self.assertEqual(result["elapsed_days"], 5)
        self.assertEqual(result["days_left"], 5)
        self.assertEqual(result["safe_per_day"], 140)
        self.assertEqual(result["burn_rate"], 60)
        self.assertEqual(result["projected"], 600)
        self.assertEqual(result["expected"], 500)
        self.assertEqual(result["pace_delta"], -200)
        self.assertTrue(result["on_pace"])
        self.assertEqual(result["projection_status"], "ok")

        over = insights.pacing(start, end, 900, 1000, date(2026, 1, 3))
        self.assertEqual(over["days_left"], 7)
        self.assertEqual(over["burn_rate"], 300)
        self.assertEqual(over["projected"], 3000)
        self.assertEqual(over["pace_delta"], 600)
        self.assertFalse(over["on_pace"])
        self.assertEqual(over["projection_status"], "over")

        no_limit = insights.pacing(start, end, 50, None, today)
        self.assertIsNone(no_limit["safe_per_day"])
        self.assertIsNone(no_limit["remaining"])
        self.assertEqual(no_limit["projection_status"], "none")

    def test_insights_series_chart_and_donut(self):
        start = date(2026, 1, 1)
        end = date(2026, 1, 10)
        today = date(2026, 1, 5)
        expenses = [
            {"date": "2026-01-01", "amount": 10},
            {"date": "2026-01-03", "amount": 5},
            {"date": "2026-01-06", "amount": 99},
        ]
        series = insights.daily_series(expenses, start, end, today)
        self.assertEqual(series, [10, 10, 15, 15, 15])
        ideal = insights.ideal_series(1000, 10, 5)
        self.assertEqual(ideal, [100, 200, 300, 400, 500])
        geometry = insights.pace_geometry(series, ideal)
        self.assertEqual(len(geometry["grid"]), 3)
        self.assertTrue(geometry["actual"])
        self.assertTrue(geometry["area"])
        self.assertIsNotNone(geometry["last"])

        donut = insights.donut_geometry(
            [
                {"name": "Food", "value": 60, "css_color": "var(--cat-food)"},
                {"name": "Transport", "value": 40, "css_color": "var(--cat-transport)"},
            ]
        )
        self.assertEqual(len(donut["segments"]), 2)
        self.assertEqual(donut["segments"][0]["label"], "Food")
        self.assertEqual(donut["segments"][0]["color"], "var(--cat-food)")
        self.assertTrue(donut["segments"][0]["dasharray"])

    def test_category_breakdown_budgets(self):
        categories = [
            {
                "id": 1,
                "name": "Food",
                "color": "cat-food",
                "css_color": "var(--cat-food)",
                "budget": 100,
            },
            {
                "id": 2,
                "name": "Bills",
                "color": "cat-bills",
                "css_color": "var(--cat-bills)",
                "budget": None,
            },
        ]
        rows = insights.category_breakdown(
            categories, {"Food": 85, "Bills": 15}, 100, {"Food": 3, "Bills": 1}
        )
        food = next(row for row in rows if row["name"] == "Food")
        bills = next(row for row in rows if row["name"] == "Bills")
        self.assertEqual(food["status"], "warn")
        self.assertEqual(food["budget_percent"], 85)
        self.assertEqual(food["remaining"], 15)
        self.assertEqual(food["count"], 3)
        self.assertEqual(bills["status"], "none")
        self.assertIsNone(bills["budget_percent"])
        self.assertEqual(rows[0]["name"], "Food")
        self.assertEqual(
            [
                row["name"]
                for row in insights.category_breakdown(
                    list(reversed(categories)),
                    {"Food": 85, "Bills": 15},
                    100,
                    {},
                    sort_items=False,
                )
            ],
            ["Bills", "Food"],
        )

    def test_system_theme_option(self):
        page = self.client.get("/period/settings").get_data(as_text=True)
        self.assertIn('value="system"', page)
        self.assertIn('data-system-light="saas"', page)
        self.assertIn('data-system-dark="fintech"', page)
        self.assertIn("Follows your device light or dark preference.", page)
        self.assertEqual(app_module.theme_catalog.SYSTEM_LIGHT_THEME, "saas")
        self.assertEqual(app_module.theme_catalog.SYSTEM_DARK_THEME, "fintech")


if __name__ == "__main__":
    unittest.main()
