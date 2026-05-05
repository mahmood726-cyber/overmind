import sys, os, io, json
import contextlib
# detect_events_from_km has emoji prints at module import time. Redirect
# stdout to /dev/null during import so the JSON we emit is the only line.
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, ".")
_real_stdout = sys.stdout
with contextlib.redirect_stdout(io.StringIO()):
    from detect_events_from_km import (
        detect_steps_in_km_curve, calculate_events_from_steps, infer_nrisk_times,
    )
sys.stdout = _real_stdout

# Fixed KM curve points: 5 vertical drops at known times
points = [
    (0.0, 1.00),
    (1.5, 1.00), (1.5, 0.95),
    (3.0, 0.95), (3.0, 0.85),
    (4.5, 0.85), (4.5, 0.75),
    (6.0, 0.75), (6.0, 0.60),
    (7.5, 0.60), (7.5, 0.50),
]
steps = detect_steps_in_km_curve(points, step_threshold=0.01)

# nrisk inference on a fixed sequence — 4 numbers across 8-month max
nrisk_times = infer_nrisk_times([100, 80, 60, 40], x_max=8.0)

# Event calculation with fixed initial nrisk
events = calculate_events_from_steps(steps, nrisk_times=[0.0, 4.0, 8.0], nrisk_values=[100, 80, 60])

print(json.dumps({
    "n_curve_points":  len(points),
    "n_steps_detected": len(steps),
    "first_step_time":  round(float(steps[0]["time"]), 6) if steps else None,
    "first_drop_mag":   round(float(steps[0]["drop_magnitude"]), 6) if steps else None,
    "total_drop":       round(float(sum(s["drop_magnitude"] for s in steps)), 6),
    "n_nrisk_times":    len(nrisk_times),
    "nrisk_t0":         round(float(nrisk_times[0]), 6) if nrisk_times else None,
    "nrisk_t_last":     round(float(nrisk_times[-1]), 6) if nrisk_times else None,
    "n_events":         len(events) if events else 0,
}))