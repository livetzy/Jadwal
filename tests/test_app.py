import json
import os
import tempfile
import unittest
from io import BytesIO

import app


class ScheduleTrackingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database = app.DATABASE
        app.DATABASE = os.path.join(self.temp_dir.name, 'test.db')
        app.app.config['TESTING'] = True
        app.init_db()
        self.client = app.app.test_client()

        with app.app.app_context():
            db = app.get_db()
            cursor = db.execute('''
                INSERT INTO schedules
                    (title, date, start_time, end_time, is_recurring, recurring_days)
                VALUES (?, ?, ?, ?, 1, ?)
            ''', ('Olahraga', '2026-10-26', '08:00', '09:00', 'monday,tuesday'))
            self.schedule_id = cursor.lastrowid
            db.commit()

    def tearDown(self):
        app.DATABASE = self.original_database
        self.temp_dir.cleanup()

    def test_recurring_completion_is_per_occurrence(self):
        response = self.client.post(
            f'/api/toggle/{self.schedule_id}?date=2026-10-26'
        )
        self.assertEqual(response.status_code, 200)

        monday = self.client.get('/api/schedules?date=2026-10-26').get_json()
        tuesday = self.client.get('/api/schedules?date=2026-10-27').get_json()
        self.assertEqual(monday['schedules'][0]['is_completed'], 1)
        self.assertEqual(tuesday['schedules'][0]['is_completed'], 0)

        response = self.client.post(
            f'/api/toggle/{self.schedule_id}?date=2026-10-27'
        )
        self.assertEqual(response.status_code, 200)
        tuesday = self.client.get('/api/schedules?date=2026-10-27').get_json()
        self.assertEqual(tuesday['schedules'][0]['is_completed'], 1)

    def test_toggle_rejects_a_date_without_a_recurring_schedule(self):
        response = self.client.post(
            f'/api/toggle/{self.schedule_id}?date=2026-10-28'
        )
        self.assertEqual(response.status_code, 409)

    def test_weekly_and_daily_pages_render_occurrence_statuses(self):
        self.client.post(f'/api/toggle/{self.schedule_id}?date=2026-10-26')
        daily = self.client.get('/?date=2026-10-26')
        weekly = self.client.get('/weekly?date=2026-10-26')

        self.assertEqual(daily.status_code, 200)
        daily_html = daily.get_data(as_text=True)
        self.assertIn('checked', daily_html)
        self.assertIn('data-view="daily"', daily_html)
        self.assertEqual(weekly.status_code, 200)
        weekly_html = weekly.get_data(as_text=True)
        self.assertIn('1/1', weekly_html)
        self.assertIn('0/1', weekly_html)
        self.assertIn('data-view="weekly"', weekly_html)
        self.assertIn('Minggu Lalu', weekly_html)
        self.assertIn('Minggu Depan', weekly_html)
        self.assertNotIn('Kemarin', weekly_html)

    def test_legacy_template_completion_does_not_mark_every_occurrence_done(self):
        with app.app.app_context():
            db = app.get_db()
            db.execute(
                'UPDATE schedules SET is_completed = 1 WHERE id = ?',
                (self.schedule_id,),
            )
            db.commit()
            self.assertEqual(
                app.get_schedules_for_date('2026-10-26')[0]['is_completed'], 0
            )
            self.assertEqual(
                app.get_schedules_for_date('2026-10-27')[0]['is_completed'], 0
            )

    def test_recurring_completion_survives_export_and_import(self):
        self.client.post(f'/api/toggle/{self.schedule_id}?date=2026-10-26')
        exported = self.client.get('/api/export').get_json()
        self.assertEqual(exported['schedules'][0]['completed_dates'], ['2026-10-26'])

        response = self.client.post(
            '/api/import',
            data={'file': (BytesIO(json.dumps(exported).encode()), 'backup.json')},
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['imported'], 1)

        with app.app.app_context():
            schedules = app.get_schedules_for_date('2026-10-26')
            self.assertEqual([s['is_completed'] for s in schedules], [1, 1])
            schedules = app.get_schedules_for_date('2026-10-27')
            self.assertEqual([s['is_completed'] for s in schedules], [0, 0])

    def test_csv_export_and_import_preserve_recurring_completion(self):
        self.client.post(f'/api/toggle/{self.schedule_id}?date=2026-10-26')
        exported = self.client.get('/api/export?format=csv')
        self.assertIn(b'completed_dates', exported.data)

        response = self.client.post(
            '/api/import',
            data={'file': (BytesIO(exported.data), 'backup.csv')},
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 200)
        with app.app.app_context():
            schedules = app.get_schedules_for_date('2026-10-26')
            self.assertEqual([s['is_completed'] for s in schedules], [1, 1])

    def test_recurring_form_requires_at_least_one_day(self):
        response = self.client.post('/add', data={
            'title': 'Belajar',
            'date': '2026-10-26',
            'start_time': '10:00',
            'end_time': '11:00',
            'is_recurring': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'Pilih setidaknya satu hari untuk jadwal berulang.',
            response.get_data(as_text=True),
        )
        with app.app.app_context():
            count = app.get_db().execute(
                'SELECT COUNT(*) FROM schedules'
            ).fetchone()[0]
            self.assertEqual(count, 1)


if __name__ == '__main__':
    unittest.main()
