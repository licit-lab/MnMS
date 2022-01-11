import unittest
from decimal import Decimal

from mnms.tools.time import Time, TimeTable, Dt


class TestTime(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_time(self):
        t = Time("07:34:23.67")
        self.assertEqual(7, t._hours)
        self.assertEqual(34, t._minutes)
        self.assertAlmostEqual(23.67, t.seconds)

    def test_time_from_seconds(self):
        t = Time.fromSeconds(12345)
        self.assertEqual(3, t.hours)
        self.assertEqual(25, t.minutes)
        self.assertAlmostEqual(45, t.seconds)

    def test_time_operator(self):
        t1 = Time("07:34:23.67")
        t2 = Time("07:34:23.69")

        self.assertTrue(t1 < t2)
        self.assertTrue(t1 <= t2)
        self.assertTrue(t2 > t1)
        self.assertTrue(t2 >= t1)

        self.assertTrue(t1 < t2)
        self.assertTrue(t2 > t1)

        t2 = Time("07:34:23.67")
        self.assertTrue(t1 >= t2)
        self.assertTrue(t1 <= t2)


class TestDt(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_dt(self):
        dt = Dt(12, 35, 13.45)

        self.assertEqual(12, dt._hours)
        self.assertEqual(35, dt._minutes)
        self.assertAlmostEqual(Decimal(13.45), dt._seconds)

        dt = Dt(12, 135, 73.45)

        self.assertEqual(14, dt._hours)
        self.assertEqual(16, dt._minutes)
        self.assertAlmostEqual(Decimal(13.45), dt._seconds)

        dt.__repr__()

    def test_to_sec(self):
        dt = Dt(12, 35, 13.45)
        self.assertAlmostEqual(12*3600+35*60+13.45, dt.to_seconds())

    def test_mul_dt(self):
        dt = Dt(12, 35, 13.45)*2
        self.assertEqual(25, dt._hours)
        self.assertEqual(10, dt._minutes)
        self.assertAlmostEqual(Decimal(13.45*2), dt._seconds)