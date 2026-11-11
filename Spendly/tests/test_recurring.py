import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_BOOTSTRAP = tempfile.TemporaryDirectory()
os.environ["SPENDLY_DATA_DIR"] = _BOOTSTRAP.name

import app as app_module
import cycles
import db
import recurrence
import recurring
import settings


class RecurringTests(unittest.TestCase):
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

    def add_rule(
        self,
        amount=25.0,
        category="Bills",
        description="Internet",
        cadence="monthly",
        start=None,
        end=None,
        next_due=None,
        auto_post=False,
    ):
        start = start or self.today
        next_due = next_due or start
        return db.addRecurring(
            self.pid,
            amount,
            category,
            description,
            cadence,
            start.isoformat(),
            end.isoformat() if end else None,
            next_due.isoformat(),
            auto_post,
        )

    def expenses(self):
        conn = db.connect()
        rows = conn.execute(
            "SELECT id, date, category, amount, description FROM expenses "
            "WHERE profile_id = ? ORDER BY id",
            (self.pid,),
        ).fetchall()
        conn.close()
        return rows

    def test_monthly_and_yearly_dates_do_not_drift(self):
        anchor = date(2023, 1, 31)
        due = recurrence.next_date(anchor, "monthly", anchor)
        self.assertEqual(due, date(2023, 2, 28))
        due = recurrence.next_date(due, "monthly", anchor)
        self.assertEqual(due, date(2023, 3, 31))

        anchor = date(2024, 2, 29)
        due = recurrence.next_date(anchor, "yearly", anchor)
        self.assertEqual(due, date(2025, 2, 28))
        due = recurrence.next_date(due, "yearly", anchor)
        self.assertEqual(due, date(2026, 2, 28))
        due = recurrence.next_date(due, "yearly", anchor)
        self.assertEqual(due, date(2027, 2, 28))
        due = recurrence.next_date(due, "yearly", anchor)
        self.assertEqual(due, date(2028, 2, 29))

        anchor = date(2026, 12, 28)
        self.assertEqual(
            recurrence.next_date(anchor, "weekly", anchor),
            date(2027, 1, 4),
        )

    def test_schema_version_and_pre_migration_backup(self):
        legacy = Path(self.temp.name) / "legacy.db"
        conn = sqlite3.connect(legacy)
        conn.execute(
            "CREATE TABLE profiles(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)"
        )
        conn.execute(
            "CREATE TABLE expenses(id INTEGER PRIMARY KEY, profile_id INTEGER, "
            "date TEXT, category TEXT, amount REAL, description TEXT)"
        )
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        conn.close()

        db.DB = str(legacy)
        db.setup()
        conn = db.connect()
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        conn.close()

        self.assertEqual(version, db.SCHEMA_VERSION)
        self.assertIn("recurring", tables)
        self.assertIn("recurring_occurrences", tables)
        self.assertIn("templates", tables)
        backups = list((Path(self.temp.name) / "backups").glob("pre-migration-v1-*.db"))
        self.assertEqual(len(backups), 1)

    def test_post_posts_once_and_advances_due_date(self):
        due = self.today - timedelta(days=1)
        rule_id = self.add_rule(start=due, next_due=due)

        ok, message = recurring.post(self.pid, rule_id, due.isoformat(), self.today)
        self.assertTrue(ok)
        self.assertIn("Posted", message)
        rows = self.expenses()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], due.isoformat())
        self.assertEqual(rows[0]["amount"], 25)
        self.assertEqual(rows[0]["category"], "Bills")

        occurrence = db.getRecurringOccurrence(rule_id, due.isoformat())
        self.assertEqual(occurrence["status"], "posted")
        self.assertEqual(occurrence["expense_id"], rows[0]["id"])
        rule = db.getRecurringRule(self.pid, rule_id)
        self.assertEqual(rule["next_due"], recurrence.next_date(due, "monthly", due).isoformat())

        ok, message = recurring.post(self.pid, rule_id, due.isoformat(), self.today)
        self.assertFalse(ok)
        self.assertIn("already handled", message)
        self.assertEqual(len(self.expenses()), 1)

    def test_edit_single_occurrence_and_skip(self):
        due = self.today
        rule_id = self.add_rule(amount=30, category="Bills", description="Power")
        values = {
            "date": self.today,
            "category": "Transport",
            "amount": 19.5,
            "description": "Edited occurrence",
        }
        ok, _message = recurring.post(
            self.pid, rule_id, due.isoformat(), self.today, values
        )
        self.assertTrue(ok)
        rows = self.expenses()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "Transport")
        self.assertEqual(rows[0]["amount"], 19.5)
        self.assertEqual(rows[0]["description"], "Edited occurrence")
        rule = db.getRecurringRule(self.pid, rule_id)
        self.assertEqual(rule["category"], "Bills")
        self.assertEqual(rule["amount"], 30)

        skip_id = self.add_rule(description="Water")
        ok, message = recurring.skip(self.pid, skip_id, self.today.isoformat(), self.today)
        self.assertTrue(ok)
        self.assertIn("will not be posted", message)
        self.assertEqual(len(self.expenses()), 1)
        skipped = db.getRecurringOccurrence(skip_id, self.today.isoformat())
        self.assertEqual(skipped["status"], "skipped")
        skipped_rule = db.getRecurringRule(self.pid, skip_id)
        self.assertGreater(skipped_rule["next_due"], self.today.isoformat())

    def test_auto_post_is_opt_in_and_idempotent(self):
        start = self.today - timedelta(days=14)
        rule_id = self.add_rule(
            cadence="weekly",
            start=start,
            next_due=start,
            auto_post=True,
        )
        self.assertEqual(recurring.auto_post(self.pid, self.today), 3)
        self.assertEqual(len(self.expenses()), 3)
        self.assertEqual(recurring.auto_post(self.pid, self.today), 0)
        self.assertEqual(len(self.expenses()), 3)
        rule = db.getRecurringRule(self.pid, rule_id)
        self.assertEqual(rule["next_due"], (self.today + timedelta(days=7)).isoformat())

    def test_auto_post_runs_on_dashboard(self):
        yesterday = self.today - timedelta(days=1)
        rule_id = self.add_rule(
            cadence="weekly",
            start=yesterday,
            next_due=yesterday,
            auto_post=True,
        )
        page = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn("Dashboard", page)
        self.assertEqual(len(self.expenses()), 1)
        rule = db.getRecurringRule(self.pid, rule_id)
        self.assertEqual(rule["next_due"], (yesterday + timedelta(days=7)).isoformat())

    def test_deleting_rule_keeps_posted_expenses(self):
        rule_id = self.add_rule()
        ok, _message = recurring.post(
            self.pid, rule_id, self.today.isoformat(), self.today
        )
        self.assertTrue(ok)
        self.assertIsNotNone(db.deleteRecurring(self.pid, rule_id))
        self.assertEqual(len(self.expenses()), 1)
        self.assertIsNone(db.getRecurringRule(self.pid, rule_id))
        self.assertIsNone(
            db.getRecurringOccurrence(rule_id, self.today.isoformat())
        )

    def test_upcoming_card_and_post_skip_routes(self):
        rule_id = self.add_rule(description="Rent", amount=700)
        page = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn("Upcoming", page)
        self.assertIn("Rent", page)
        self.assertIn("Due today", page)
        self.assertIn("Post", page)
        self.assertIn("Skip", page)
        self.assertIn("Edit", page)

        response = self.client.post(
            f"/recurring/{rule_id}/post",
            data={"due": self.today.isoformat(), "next": "/dashboard"},
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("Posted Bills for", response)
        self.assertEqual(len(self.expenses()), 1)

        skip_id = self.add_rule(description="Gym")
        response = self.client.post(
            f"/recurring/{skip_id}/skip",
            data={"due": self.today.isoformat(), "next": "/dashboard"},
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("will not be posted", response)
        self.assertEqual(len(self.expenses()), 1)

    def test_recurring_settings_add_edit_delete(self):
        page = self.client.post(
            "/recurring/add",
            data={
                "description": "Internet",
                "amount": "45",
                "category": "Bills",
                "cadence": "monthly",
                "start": self.today.isoformat(),
                "end": "",
                "next_due": self.today.isoformat(),
                "auto_post": "on",
                "next": "/period/settings#recurring",
            },
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("Recurring rule added.", page)
        rules = db.getRecurringRules(self.pid)
        self.assertEqual(len(rules), 1)
        rule = rules[0]
        self.assertEqual(rule["auto_post"], 1)
        self.assertEqual(rule["description"], "Internet")

        response = self.client.post(
            f"/recurring/{rule['id']}/edit",
            data={
                "description": "Home internet",
                "amount": "50",
                "category": "Bills",
                "cadence": "monthly",
                "start": self.today.isoformat(),
                "end": "",
                "next_due": self.today.isoformat(),
                "next": "/period/settings",
            },
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("Recurring rule saved.", response)
        updated = db.getRecurringRule(self.pid, rule["id"])
        self.assertEqual(updated["description"], "Home internet")
        self.assertEqual(updated["amount"], 50)
        self.assertEqual(updated["auto_post"], 0)

        response = self.client.post(
            f"/recurring/{rule['id']}/delete",
            data={"next": "/period/settings"},
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("Expenses already posted were kept.", response)
        self.assertEqual(db.getRecurringRules(self.pid), [])

    def test_category_reorder_persists(self):
        rows = {row["name"]: row for row in db.getCategories(self.pid)}
        response = self.client.post(
            f"/categories/{rows['Bills']['id']}/move?direction=up",
            data={"next": "/period/settings"},
        )
        self.assertEqual(response.status_code, 302)
        names = [row["name"] for row in db.getCategories(self.pid)]
        self.assertEqual(names, ["Food", "Transport", "Bills", "Shopping", "Other"])

        db.setup()
        names = [row["name"] for row in db.getCategories(self.pid)]
        self.assertEqual(names, ["Food", "Transport", "Bills", "Shopping", "Other"])

    def test_templates_quick_add_and_delete(self):
        response = self.client.post(
            "/templates/add",
            data={
                "name": "Morning coffee",
                "category": "Food",
                "amount": "4.50",
                "description": "Flat white",
                "next": "/period/settings",
            },
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("Template added.", response)
        templates = db.getTemplates(self.pid)
        self.assertEqual(len(templates), 1)

        page = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn("Templates", page)
        self.assertIn("Morning coffee", page)

        response = self.client.post(
            f"/templates/{templates[0]['id']}/use",
            data={"next": "/dashboard"},
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("Added &#34;Morning coffee&#34; for today.", response)
        rows = self.expenses()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount"], 4.5)
        self.assertEqual(rows[0]["description"], "Flat white")

        self.client.post(
            f"/templates/{templates[0]['id']}/delete",
            data={"next": "/period/settings"},
        )
        self.assertEqual(db.getTemplates(self.pid), [])

    def test_duplicate_expense_uses_today(self):
        original = self.today - timedelta(days=1)
        eid = db.save(
            self.pid,
            original.isoformat(),
            "Food",
            12.5,
            "Lunch",
        )
        response = self.client.post(
            f"/expense/{eid}/duplicate",
            data={"next": "/dashboard"},
        )
        self.assertEqual(response.status_code, 302)
        rows = self.expenses()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["date"], self.today.isoformat())
        self.assertEqual(rows[1]["amount"], 12.5)
        self.assertEqual(rows[1]["description"], "Lunch")

    def test_category_use_updates_and_blocks_deletion(self):
        rule_id = self.add_rule(category="Bills", description="Power")
        template_id = db.addTemplate(self.pid, "Power bill", "Bills", 55, "Electricity")
        rows = {row["name"]: row for row in db.getCategories(self.pid)}
        response = self.client.post(
            f"/categories/{rows['Bills']['id']}/update",
            data={
                "name": "Utilities",
                "color": "cat-bills",
                "budget": "",
                "next": "/period/settings",
            },
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("Category saved.", response)
        self.assertEqual(
            db.getRecurringRule(self.pid, rule_id)["category"], "Utilities"
        )
        self.assertEqual(db.getTemplate(self.pid, template_id)["category"], "Utilities")

        page = self.client.post(
            f"/categories/{rows['Bills']['id']}/delete",
            data={"next": "/period/settings"},
            follow_redirects=True,
        ).get_data(as_text=True)
        self.assertIn("recurring rules", page)
        self.assertIsNotNone(db.getCategory(self.pid, rows["Bills"]["id"]))

    def test_future_rules_show_in_later_section(self):
        future = self.today + timedelta(days=5)
        self.add_rule(description="Insurance", start=future, next_due=future)
        page = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn("No bills due right now", page)
        self.assertIn("Insurance", page)
        self.assertIn("Later", page)
        self.assertNotIn("data-post-recurring", page)

    def test_end_date_stops_generation(self):
        start = self.today - timedelta(days=21)
        end = self.today - timedelta(days=8)
        self.add_rule(
            cadence="weekly",
            start=start,
            end=end,
            next_due=start,
            auto_post=True,
        )
        self.assertEqual(recurring.auto_post(self.pid, self.today), 2)
        rule = db.getRecurringRules(self.pid)[0]
        self.assertGreater(rule["next_due"], end.isoformat())


if __name__ == "__main__":
    unittest.main()
