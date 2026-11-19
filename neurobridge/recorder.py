"""Dedicated LSL recording process; stdout is a small JSON status protocol."""
import csv
import json
import signal
import sys
import time
from pathlib import Path
from pylsl import StreamInlet, resolve_byprop, local_clock

stopping = False

def stop(*_):
    global stopping
    stopping = True

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

def emit(**data):
    print(json.dumps(data), flush=True)

def main():
    path, duration = Path(sys.argv[1]), int(sys.argv[2])
    emit(phase='searching', message='Looking for a Muse EEG stream…')
    streams = resolve_byprop('type', 'EEG', timeout=8)
    if stopping: return
    if not streams: raise RuntimeError('No EEG stream found. Connect the Muse first, then record.')
    if len(streams) != 1: raise RuntimeError('Multiple EEG streams found. Close extra streamers before recording.')
    inlet = StreamInlet(streams[0], max_buflen=30)
    try:
        inlet.open_stream(timeout=8)
        info = inlet.info(timeout=5)
        count = info.channel_count()
        node = info.desc().child('channels').first_child()
        labels = []
        for i in range(count):
            labels.append(node.child_value('label') or f'Channel {i+1}')
            node = node.next_sibling()
        if not all(c in labels for c in ['TP9','AF7','AF8','TP10']):
            raise RuntimeError('Selected stream does not contain the four expected Muse EEG channels.')
        correction = inlet.time_correction(timeout=5)
        # Flush buffered data. Record from the first new sample, not stream discovery time.
        inlet.pull_chunk(timeout=0, max_samples=100000)
        total, first, last, last_received, report = 0, None, None, time.monotonic(), 0
        with path.open('x', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamps'] + labels)
            emit(phase='waiting', message='Connected. Waiting for EEG samples…')
            while not stopping:
                samples, stamps = inlet.pull_chunk(timeout=.25, max_samples=256)
                now = time.monotonic()
                if stamps:
                    if 'quality-v1' in sys.argv:
                        from quality import CHANNELS
                        indices=[labels.index(c) for c in CHANNELS]
                        emit(quality_samples={'timestamps':[s+correction for s in stamps],'samples':[[row[i] for i in indices] for row in samples]})
                    if len(sys.argv) > 3 and abs(stamps[-1]+correction-local_clock()) > 60:
                        raise RuntimeError("EEG stream uses an incompatible clock. Close the old streaming terminal, then reconnect from the dashboard.")
                    last_received = now
                    if first is None:
                        first = stamps[0]
                        emit(phase='recording', message='Recording EEG samples')
                    for sample, stamp in zip(samples, stamps):
                        if stamp - first > duration: break
                        writer.writerow([f'{stamp+correction:.6f}'] + sample)
                        total += 1
                        last = stamp
                    f.flush()
                if now - report > .5:
                    emit(samples=total, elapsed=0 if last is None else last-first)
                    report = now
                if first is not None and stamps and stamps[-1]-first >= duration: break
                if now-last_received > 10:
                    raise RuntimeError('No EEG samples for 10 seconds. Check Bluetooth and headset power. Any partial CSV has been kept.')
        if not total:
            path.unlink(missing_ok=True)
            emit(phase='cancelled', message='Stopped before EEG samples arrived.')
        else:
            emit(phase='complete', file=path.name, samples=total,
                 elapsed=last-first, message='Recording saved' if not stopping else 'Stopped early; partial recording saved')
    finally:
        inlet.close_stream()

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        emit(phase='error', message=str(exc))
        sys.exit(1)
