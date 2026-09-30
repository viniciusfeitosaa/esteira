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


def test_counts_crossing_hidden_by_short_gap():
    c = LineCounter(direction="rtl", line_pos=0.5, keep_lost=5)
    assert c.count_frame([TrackBox(3, 110, 40)], 200, 100) == 0
    for _ in range(3):
        assert c.count_frame([], 200, 100) == 0
    assert c.count_frame([TrackBox(3, 85, 40)], 200, 100) == 1


def test_forgets_after_long_gap():
    c = LineCounter(direction="rtl", line_pos=0.5, keep_lost=2)
    c.count_frame([TrackBox(4, 110, 40)], 200, 100)
    for _ in range(3):
        c.count_frame([], 200, 100)
    assert c.count_frame([TrackBox(4, 85, 40)], 200, 100) == 0
