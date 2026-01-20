import sys
import os
import unittest
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from track_availability import should_run
except ImportError:
    should_run = None

class TestScheduler(unittest.TestCase):
    def test_should_run(self):
        if should_run is None:
            self.fail("should_run function not found in track_availability module")

        # Targets: 55, 10, 25, 40

        # Case 1: Just ran (5 mins ago). Not target.
        # Last: 10:00 (Not target, maybe recovery). Now: 10:05.
        # Elapsed: 5. Target: No (05).
        last = datetime(2023, 1, 1, 10, 0, 0)
        now = datetime(2023, 1, 1, 10, 5, 0)
        self.assertFalse(should_run(last, now), "Should skip: only 5 mins elapsed, not target")

        # Case 2: Standard schedule.
        # Last: 10:10. Now: 10:25.
        # Elapsed: 15. Target: Yes (25).
        last = datetime(2023, 1, 1, 10, 10, 0)
        now = datetime(2023, 1, 1, 10, 25, 0)
        self.assertTrue(should_run(last, now), "Should run: 15 mins elapsed, at target")

        # Case 3: Alignment (e.g. previous run was off-schedule recovery).
        # Last: 10:13. Now: 10:25.
        # Elapsed: 12. Target: Yes (25).
        last = datetime(2023, 1, 1, 10, 13, 0)
        now = datetime(2023, 1, 1, 10, 25, 0)
        self.assertTrue(should_run(last, now), "Should run: 12 mins elapsed (>10), at target")

        # Case 4: Too soon for alignment.
        # Last: 10:18. Now: 10:25.
        # Elapsed: 7. Target: Yes.
        last = datetime(2023, 1, 1, 10, 18, 0)
        now = datetime(2023, 1, 1, 10, 25, 0)
        self.assertFalse(should_run(last, now), "Should skip: only 7 mins elapsed (<10), even if at target")

        # Case 5: Missed schedule (Recovery).
        # Last: 10:10. Now: 10:26 (e.g. 10:25 was missed/busy).
        # Elapsed: 16. Target: No (26).
        last = datetime(2023, 1, 1, 10, 10, 0)
        now = datetime(2023, 1, 1, 10, 26, 0)
        self.assertTrue(should_run(last, now), "Should run: 16 mins elapsed (>15)")

        # Case 6: Off-schedule but recently ran.
        # Last: 10:10. Now: 10:15.
        # Elapsed: 5. Target: No.
        last = datetime(2023, 1, 1, 10, 10, 0)
        now = datetime(2023, 1, 1, 10, 15, 0)
        self.assertFalse(should_run(last, now), "Should skip: 5 mins elapsed")

        # Case 7: First run (No last run).
        self.assertTrue(should_run(None, now), "Should run if last_run is None")

        # Case 8: Target minute boundary check (55)
        # Last: 09:40. Now: 09:55.
        last = datetime(2023, 1, 1, 9, 40, 0)
        now = datetime(2023, 1, 1, 9, 55, 0)
        self.assertTrue(should_run(last, now), "Should run at 55 target")

if __name__ == '__main__':
    unittest.main()
