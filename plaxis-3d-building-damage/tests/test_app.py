import unittest
from pathlib import Path

import numpy as np
import viktor as vkt
from munch import munchify
from viktor.testing import mock_PlaxisAnalysis, mock_Storage, mock_View

from app import Controller
from plaxis3d_app.damage import category, facade_damage
from plaxis3d_app.entities import derive

FIXTURE = Path(__file__).parent / "data" / "worker_output_fixture.json"   # recorded output of the PLAXIS worker
STORED = [vkt.File.from_path(FIXTURE) for _ in range(6)]


def params():
    return munchify({
        "conn": {"mode": "launch", "project_path": r"C:\x.p3dx", "plaxis_exe": "", "port": 10000, "password": "",
                 "recalculate": False},
        "bld": {"entity_filter": "Building", "height": 12, "stamp": 0},
        "assess": {"entity": "Building_raft", "stage": "Phase_5", "btype": "masonry", "exaggeration": 200,
                   "facade": "F"}})


class TestDamage(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(category(0.01)[0], 0)
        self.assertEqual(category(0.06)[0], 1)
        self.assertEqual(category(0.1)[0], 2)
        self.assertEqual(category(0.2)[0], 3)
        self.assertEqual(category(0.5)[0], 4)

    def test_flat_facade_is_negligible(self):
        s = np.linspace(0, 20, 9)
        r = facade_damage("flat", s, np.zeros(9), np.zeros(9), 10.0)
        self.assertEqual(r.category, 0)
        self.assertAlmostEqual(r.eps_governing, 0.0)

    def test_sagging_trough_gives_strain(self):
        s = np.linspace(0, 20, 9)
        uz = -30 * np.exp(-((s - 10) / 5) ** 2)               # 30 mm settlement bowl mid-span
        r = facade_damage("trough", s, uz, np.zeros(9), 10.0)
        self.assertEqual(r.mode, "sagging")
        self.assertGreater(r.eps_governing, 0.05)

    def test_derive_facades_from_entity(self):
        import json
        raw = json.loads(FIXTURE.read_text(encoding='utf-8'))
        d = derive(raw, "Building_raft", 12)
        b = d["building"]
        self.assertEqual(set(b["facades"]), {"F", "B", "W", "E"})
        self.assertGreater(len(b["facades"]["F"]["ids"]), 3)
        self.assertNotIn("Phase_1", d["disp"])             # building self-weight stage is dropped (displacement reset)
        self.assertEqual(b["front_edge"], "ymax")           # the raft edge nearest the pit
        self.assertTrue(all(p["bbox"][5] - p["bbox"][4] >= 1.0 for p in d["plates"]))   # walls only


class TestViews(unittest.TestCase):
    @mock_View(Controller)
    @mock_Storage(get=STORED)
    def test_scene(self):
        self.assertIsInstance(Controller().view_scene(params=params()), vkt.GeometryAndDataResult)

    @mock_View(Controller)
    @mock_Storage(get=STORED)
    def test_damage(self):
        self.assertIsInstance(Controller().view_damage(params=params()), vkt.DataResult)

    @mock_View(Controller)
    @mock_Storage(get=STORED)
    def test_table(self):
        self.assertIsInstance(Controller().view_table(params=params()), vkt.TableResult)

    @mock_View(Controller)
    @mock_Storage(get=STORED)
    def test_map(self):
        self.assertIsInstance(Controller().view_map(params=params()), vkt.PlotlyResult)

    @mock_View(Controller)
    @mock_Storage(get=STORED)
    def test_profile(self):
        self.assertIsInstance(Controller().view_profile(params=params()), vkt.PlotlyResult)

    @mock_View(Controller)
    @mock_Storage(get=STORED)
    def test_unknown_stage_falls_back(self):
        p = params()
        p.assess.stage = "nope"
        self.assertIsInstance(Controller().view_table(params=p), vkt.TableResult)

    @mock_Storage(get=STORED)
    def test_csv(self):
        self.assertIsInstance(Controller().download_csv(params=params()), vkt.DownloadResult)

    @mock_View(Controller)
    def test_no_results_is_user_error(self):
        with self.assertRaises(vkt.UserError):
            Controller().view_table(params=params())


class TestFetch(unittest.TestCase):
    @mock_Storage()
    @mock_PlaxisAnalysis(get_output_file={"output.json": vkt.File.from_path(FIXTURE)})
    def test_fetch(self):
        self.assertIsInstance(Controller().fetch_live(params=params()), vkt.SetParamsResult)

    def test_attach_needs_password(self):
        p = params()
        p.conn.mode = "attach"
        with self.assertRaises(vkt.UserError):
            Controller().fetch_live(params=p)
