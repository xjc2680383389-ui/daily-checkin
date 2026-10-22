import json
import os
from pathlib import Path
import tempfile
import concurrent.futures
import unittest
from datetime import date
from unittest.mock import patch

import checkin


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / 'checkins.json'
        for name, value in [('DATA_DIR', self.temp.name), ('DATA_FILE', str(self.file))]:
            p = patch.object(checkin, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_failed_write_preserves_existing_data(self):
        self.file.write_text('{"2026-05-01": true}', encoding='utf-8')
        before = self.file.read_bytes()
        with patch.object(checkin.json, 'dump', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                checkin.save_data({'2026-05-02': True})
        self.assertEqual(self.file.read_bytes(), before)
        self.assertFalse(list(Path(self.temp.name).glob('*.tmp')))

    def test_invalid_data_is_reported_without_overwriting(self):
        for text in ['{broken', '[]', '{"not-a-date":true}', '{"2026-05-01":"yes"}']:
            with self.subTest(text=text):
                self.file.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    checkin.load_data()
                self.assertEqual(self.file.read_text(encoding='utf-8'), text)

    def test_round_trip_and_missing_file(self):
        self.assertEqual(checkin.load_data(), {})
        data = {'2026-05-01': True}
        checkin.save_data(data)
        self.assertEqual(checkin.load_data(), data)

    def test_replace_failure_preserves_existing_data(self):
        checkin.save_data({'2026-05-01': True})
        before = self.file.read_bytes()
        with patch.object(checkin.os, 'replace', side_effect=OSError('replace failed')):
            with self.assertRaises(OSError):
                checkin.save_data({'2026-05-02': True})
        self.assertEqual(self.file.read_bytes(), before)
        self.assertFalse(list(Path(self.temp.name).glob('*.tmp')))

    def test_concurrent_read_modify_write_keeps_all_dates(self):
        def record(day):
            with checkin.data_lock():
                data = checkin.load_data()
                data[f'2026-05-{day:02d}'] = True
                checkin.save_data(data)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(record, range(1, 5)))
        self.assertEqual(len(checkin.load_data()), 4)


class CalendarTests(StorageTests):
    def setUp(self):
        super().setUp()
        original = checkin.ctk.CTk
        def hidden_window():
            window = original()
            window.withdraw()
            return window
        with patch.object(checkin.ctk, 'CTk', side_effect=hidden_window):
            self.app = checkin.CheckinApp()
        self.addCleanup(self.destroy_window)
        self.app.today = date(2026, 7, 1)
        self.app.current_year = 2026
        self.app.current_month = 5

    def destroy_window(self):
        # CustomTkinter 自己的延迟回调也需在销毁测试窗口前取消。
        for callback in self.app.window.tk.call('after', 'info'):
            self.app.window.after_cancel(callback)
        self.app.window.destroy()

    def test_shorter_month_clears_unused_rows_and_commands(self):
        self.app._render_calendar()
        old = self.app.day_btns[5][0]
        self.assertEqual(old.cget('text'), '31')
        self.app.current_month = 6
        self.app._render_calendar()
        for button in self.app.day_btns[5]:
            self.assertEqual(button.cget('text'), '')
            self.assertEqual(button.cget('state'), 'disabled')
            button.invoke()
        self.assertEqual(self.app.data, {})

    def test_write_failure_does_not_change_ui_state(self):
        with patch.object(checkin, 'save_data', side_effect=OSError('disk full')):
            with patch('tkinter.messagebox.showerror') as error:
                self.app._toggle_day(date(2026, 5, 1))
        self.assertTrue(error.called)
        self.assertEqual(self.app.data, {})

    def test_another_window_records_are_preserved(self):
        checkin.save_data({'2026-05-02': True})
        self.app._toggle_day(date(2026, 5, 1))
        self.assertEqual(checkin.load_data(), {'2026-05-01': True, '2026-05-02': True})

    def test_corrupt_file_is_not_overwritten_by_toggle(self):
        self.file.write_text('{broken', encoding='utf-8')
        with patch('tkinter.messagebox.showerror') as error:
            self.app._toggle_day(date(2026, 5, 1))
        self.assertTrue(error.called)
        self.assertEqual(self.file.read_text(encoding='utf-8'), '{broken')
        self.assertEqual(self.app.data, {})

    def test_return_today_refreshes_the_actual_date(self):
        self.app.today = date(2026, 5, 31)
        self.app._go_today()
        self.assertEqual(self.app.today, date.today())
        self.assertEqual((self.app.current_year, self.app.current_month), (date.today().year, date.today().month))

    def test_midnight_refresh_follows_today_month(self):
        self.app.today = date(2026, 5, 31)
        self.app.current_year, self.app.current_month = 2026, 5
        class NextDay(date):
            @classmethod
            def today(cls):
                return date(2026, 6, 1)
        with patch.object(checkin, 'date', NextDay):
            self.app._refresh_today()
        self.assertEqual(self.app.today, date(2026, 6, 1))
        self.assertEqual((self.app.current_year, self.app.current_month), (2026, 6))


if __name__ == '__main__':
    unittest.main()
