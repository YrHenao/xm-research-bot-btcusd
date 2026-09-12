import unittest
from bot.native_replay import NativeSignal


class NativeReplayTests(unittest.TestCase):
    def test_select_only_closed_bars(self):
        frames={15:[(i*900,100+i) for i in range(30)]}
        s=NativeSignal(frames); cfg={'trend_period':20,'trend_frames':[15]}
        selected=s.select(21*900,cfg)[15]
        self.assertEqual(len(selected),21)
        self.assertEqual(selected[-1].time,20*900)
        self.assertEqual(s.select(21*900+899,cfg)[15][-1].time,20*900)

    def test_future_prices_cannot_change_past_selection(self):
        frames={15:[(i*900,100+i) for i in range(30)]}; cfg={'trend_period':20,'trend_frames':[15]}
        before=NativeSignal(frames).select(21*900,cfg)
        frames[15][21:]=[(i*900,999999) for i in range(21,30)]
        self.assertEqual(before,NativeSignal(frames).select(21*900,cfg))

    def test_missing_and_stale_native_history_block(self):
        s=NativeSignal({15:[(i*900,100+i) for i in range(21)]}); cfg={'trend_period':20,'trend_frames':[15]}
        with self.assertRaisesRegex(ValueError,'insuficiente'): s.select(20*900,cfg)
        with self.assertRaisesRegex(ValueError,'atrasado'): s.select(24*900,cfg)
