from services.yolo_counter.centroid_track import CentroidTracker
from services.yolo_counter.line_count import LineCounter


def _run_belt(tracker, n_pills=8, spacing=40.0, step=30.0, w=640, h=200):
    """Fila de comprimidos andando da direita para a esquerda; retorna o total contado."""
    counter = LineCounter(direction="rtl", line_pos=0.5)
    total = 0
    xs = [w + 20 + i * spacing for i in range(n_pills)]
    for _ in range(80):
        centers = [(x, 100.0) for x in xs if 0 <= x <= w]
        total += counter.count_frame(tracker.update(centers), w, h)
        xs = [x - step for x in xs]
    return total


def test_fast_belt_counts_every_pill():
    t = CentroidTracker(max_dist=56, max_lost=25, direction="rtl")
    assert _run_belt(t) == 8


def test_fast_belt_with_missed_detections():
    t = CentroidTracker(max_dist=56, max_lost=25, direction="rtl")
    counter = LineCounter(direction="rtl", line_pos=0.5)
    w, h = 640, 200
    xs = [w + 20 + i * 60.0 for i in range(8)]
    total = 0
    for f in range(80):
        # cada comprimido some em 1 de cada 3 frames (reflexo)
        centers = [(x, 100.0) for i, x in enumerate(xs) if 0 <= x <= w and (f + i) % 3]
        total += counter.count_frame(t.update(centers), w, h)
        xs = [x - 30.0 for x in xs]
    assert total == 8


def test_stopped_belt_keeps_ids():
    t = CentroidTracker(max_dist=56, max_lost=25, direction="rtl")
    a = t.update([(300.0, 100.0), (340.0, 100.0)])
    b = t.update([(300.0, 100.0), (340.0, 100.0)])
    assert sorted((x.id, x.cx) for x in a) == sorted((x.id, x.cx) for x in b)


def test_long_lost_track_does_not_jump_onto_far_detection():
    t = CentroidTracker(max_dist=56, max_lost=25, direction="rtl")
    c = LineCounter(direction="rtl", line_pos=0.5)
    for x in (700.0, 650.0, 600.0):
        c.count_frame(t.update([(x, 100.0), (x + 120, 100.0)]), 640, 200)
    for _ in range(10):
        c.count_frame(t.update([]), 640, 200)
    # 11 passos depois a previsao do rastro cai em x=50, onde ha um objeto parado na borda
    out = t.update([(50.0, 100.0)])
    assert out[0].id not in (1, 2)
    assert c.count_frame(out, 640, 200) == 0


def test_recent_track_wins_over_long_lost_one():
    t = CentroidTracker(max_dist=56, max_lost=25, direction="rtl")
    t.update([(325.0, 100.0), (360.0, 100.0)])  # ids 1 e 2
    t.update([(305.0, 100.0), (340.0, 100.0)])  # esteira a -20 px/frame
    for x in (320.0, 300.0, 280.0, 260.0):
        t.update([(x, 100.0)])  # 1 some
    # tranco da camera: o comprimido 2 foge da previsao (240) e cai onde a previsao do 1 aponta (205)
    out = t.update([(205.0, 100.0)])
    assert out[0].id == 2


def test_irregular_dt_uses_velocity():
    t = CentroidTracker(max_dist=30, max_lost=25, direction="rtl")
    t.update([(500.0, 100.0)], dt=0.1)
    t.update([(480.0, 100.0)], dt=0.1)  # 200 px/s
    # quadro atrasado: 0.4 s depois o comprimido andou 80 px
    out = t.update([(400.0, 100.0)], dt=0.4)
    assert out[0].id == 1
