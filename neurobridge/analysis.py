"""Read-only checks for Muse CSV recordings. Thresholds flag artifacts, not validity."""
import csv
from pathlib import Path
import numpy as np
from scipy.signal import welch

CHANNELS = ['TP9', 'AF7', 'AF8', 'TP10']

def analyze(path):
    with Path(path).open() as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if 'timestamps' not in fields or not all(c in fields for c in CHANNELS):
            raise ValueError('CSV must contain timestamps, TP9, AF7, AF8, TP10.')
        rows = list(reader)
    if len(rows) < 2:
        raise ValueError('Recording needs at least two samples.')
    t = np.array([float(r['timestamps']) for r in rows])
    if not np.isfinite(t).all():
        raise ValueError('Timestamps contain missing or invalid values.')
    dt = np.diff(t)
    duration = float(t[-1] - t[0])
    positive = dt[dt > 0]
    # Muse timestamps are rounded to milliseconds in legacy files; use the known rate.
    fs = 256
    elapsed = t - t[0]
    boundaries = np.r_[0, np.flatnonzero((dt > .020) | (dt <= 0)) + 1, len(t)]
    segments = [(int(a), int(b)) for a, b in zip(boundaries[:-1], boundaries[1:])]
    spec_start, spec_end = max(segments, key=lambda ab: ab[1]-ab[0])
    channels = []
    warnings = []
    if (dt <= 0).any(): warnings.append('Duplicate or backward timestamps detected.')
    gaps = int((dt > .020).sum())
    if gaps: warnings.append(f'{gaps} timestamp gaps exceed 20 ms.')
    # Preserve spikes for plotting: two chronological extrema per bin, not averaging.
    bin_size = max(1, int(np.ceil(len(t) / 2400)))
    for c in CHANNELS:
        x = np.array([float(r[c]) if r.get(c) else np.nan for r in rows])
        valid = np.isfinite(x)
        clean = x[valid]
        if not len(clean): raise ValueError(f'{c} has no finite data.')
        large = float(np.mean(np.abs(clean) > 500) * 100)
        rail = float(np.mean(np.abs(clean) >= 995) * 100)
        flags = []
        if not valid.all(): flags.append('Missing values')
        if np.std(clean) == 0: flags.append('Flat signal')
        if rail > .1: flags.append('Possible clipping')
        if large > 5: flags.append('Large amplitudes')
        if flags: warnings.append(f'{c}: {", ".join(flags).lower()}.')
        points = []
        for start in range(0, len(x), bin_size):
            end = min(start + bin_size, len(x))
            ids = np.arange(start, end)[valid[start:end]]
            if not len(ids):
                points.append([float(elapsed[start]), None]); continue
            extrema = sorted(set([int(ids[np.argmin(x[ids])]), int(ids[np.argmax(x[ids])])]))
            points.extend([[float(elapsed[j]), float(x[j])] for j in extrema])
        # Spectra use the longest continuous segment and never join missing samples.
        segment = x[spec_start:spec_end]
        spectrum = []
        if len(segment) >= 32 and np.isfinite(segment).all():
            f, power = welch(segment, fs=fs, nperseg=min(1024, len(segment)))
            spectrum = [[float(a), float(b)] for a, b in zip(f, power) if a <= 100]
        # Insert graph breaks around recorded timestamp gaps.
        for boundary in boundaries[1:-1]:
            at = float(elapsed[boundary])
            idx = next((i for i, point in enumerate(points) if point[0] >= at), len(points))
            points.insert(idx, [at, None])
        channels.append(dict(name=c, std=float(np.std(clean)), missing=int((~valid).sum()),
            large_percent=large, rail_percent=rail, flags=flags, points=points, spectrum=spectrum))
    return dict(file=Path(path).name, samples=len(t), duration=duration,
        sample_rate=(len(t)-1)/duration if duration > 0 else 0,
        gaps=gaps, nonincreasing=int((dt <= 0).sum()), max_gap=float(np.max(dt)),
        warnings=warnings, channels=channels, assumed_spectral_rate=fs,
        spectrum_segment_seconds=float(t[spec_end-1]-t[spec_start]))
