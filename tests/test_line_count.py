from services.yolo_counter.line_count import LineCounter, TrackBox


def test_ltr_counts_once_when_crossing():
    c = LineCounter(direction="ltr", line_pos=0.5)
    w, h = 200, 100
    d0 = c.count_frame([TrackBox(1, 80, 50)], w, h)
    assert d0 == 0
    d1 = c.count_frame([TrackBox(1, 110, 50)], w, h)
    assert d1 == 1
    d2 = c.count_frame([TrackBox(1, 150, 50)], w, h)
    assert d2 == 0


def test_reset_clears_counted_ids():
    c = LineCounter(direction="ltr", line_pos=0.5)
    c.count_frame([TrackBox(1, 80, 50)], 200, 100)
    c.count_frame([TrackBox(1, 110, 50)], 200, 100)
    c.reset()
    d = c.count_frame([TrackBox(1, 80, 50)], 200, 100)
    assert d == 0
    d = c.count_frame([TrackBox(1, 110, 50)], 200, 100)
    assert d == 1


def test_rtl_crossing():
    c = LineCounter(direction="rtl", line_pos=0.5)
    assert c.count_frame([TrackBox(2, 120, 40)], 200, 100) == 0
    assert c.count_frame([TrackBox(2, 90, 40)], 200, 100) == 1
