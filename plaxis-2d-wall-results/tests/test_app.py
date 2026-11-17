import unittest
from pathlib import Path

import viktor as vkt
from munch import munchify
from viktor.testing import mock_PlaxisAnalysis, mock_Storage, mock_View

from app import Controller

# Recorded output.json of the PLAXIS worker (used as a mocked worker result in tests only)
FIXTURE = Path(__file__).parent / "data" / "worker_output_fixture.json"
STORED = [vkt.File.from_path(FIXTURE) for _ in range(4)]


def params():
    return munchify({
        "live": {"mode": "launch", "project_path": r"C:\x.p2dx", "plaxis_exe": "", "recalculate": False, "stamp": 0, "port": 10000, "password": ""},
        "sel": {"plate": "Secant wall - G-Gate N-S", "stage": "Phase_11",
                "compare": ["Phase_5", "Phase_8", "Phase_11"], "quantities": ["m", "q"], "envelope": True}})


class TestViews(unittest.TestCase):
    @mock_View(Controller)
    @mock_Storage(get=STORED)
    def test_stage_view(self):
        self.assertIsInstance(Controller().view_stage(params=params()), vkt.PlotlyResult)

    @mock_View(Controller)
    @mock_Storage(get=STORED)
    def test_unknown_stage_falls_back(self):
        p = params()
        p.sel.stage = "does-not-exist"
        self.assertIsInstance(Controller().view_stage(params=p), vkt.PlotlyResult)

    @mock_View(Controller)
    @mock_Storage(get=STORED)
    def test_compare_view(self):
        self.assertIsInstance(Controller().view_compare(params=params()), vkt.PlotlyResult)

    @mock_View(Controller)
    @mock_Storage(get=STORED)
    def test_summary_table(self):
        self.assertIsInstance(Controller().view_summary(params=params()), vkt.TableResult)

    @mock_Storage(get=STORED)
    def test_csv(self):
        self.assertIsInstance(Controller().download_csv(params=params()), vkt.DownloadResult)

    @mock_View(Controller)
    def test_no_results_is_user_error(self):
        with self.assertRaises(vkt.UserError):
            Controller().view_stage(params=params())


class TestFetch(unittest.TestCase):
    @mock_Storage()
    @mock_PlaxisAnalysis(get_output_file={"output.json": vkt.File.from_path(FIXTURE)})
    def test_fetch_live(self):
        self.assertIsInstance(Controller().fetch_live(params=params()), vkt.SetParamsResult)

    def test_launch_requires_path(self):
        p = params()
        p.live.project_path = ""
        with self.assertRaises(vkt.UserError):
            Controller().fetch_live(params=p)
