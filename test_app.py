import unittest
from pathlib import Path
from unittest.mock import patch

import app


class AppTests(unittest.TestCase):
    def test_get_max_conversions_per_scan_defaults_to_20(self) -> None:
        with patch.dict(app.os.environ, {}, clear=True):
            self.assertEqual(app.get_max_conversions_per_scan(), 20)

    def test_get_max_conversions_per_scan_reads_env(self) -> None:
        with patch.dict(app.os.environ, {"MAX_CONVERSIONS_PER_SCAN": "7"}, clear=True):
            self.assertEqual(app.get_max_conversions_per_scan(), 7)

    def test_process_file_batch_limits_number_of_conversions(self) -> None:
        files = [Path(f"track-{index}.m4a") for index in range(5)]
        with patch("app.convert_m4a_to_flac", side_effect=[True, True, False]) as convert:
            results = app.process_file_batch(files, 3)

        self.assertEqual(list(results.keys()), files[:3])
        self.assertEqual(results, {files[0]: True, files[1]: True, files[2]: False})
        self.assertEqual(convert.call_count, 3)


if __name__ == "__main__":
    unittest.main()
