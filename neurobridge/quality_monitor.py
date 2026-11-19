"""Read-only live LSL preview worker. No EEG is saved by this worker."""
import json,signal,time
from pylsl import StreamInlet,resolve_byprop,local_clock
from quality import LiveQuality,CHANNELS

stopping=False
def stop(*_):
    global stopping
    stopping=True
signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
def emit(value):print(json.dumps(value,allow_nan=False),flush=True)
def main():
    while not stopping:
        streams=resolve_byprop('type','EEG',timeout=1)
        if len(streams)!=1:
            emit(dict(ready=False,good_seconds=0,status='No EEG stream' if not streams else 'Multiple EEG streams; close extra streamers',channels=[],traces=[]));continue
        inlet=StreamInlet(streams[0],max_buflen=15)
        try:
            inlet.open_stream(timeout=4);info=inlet.info(timeout=4);node=info.desc().child('channels').first_child();labels=[]
            for _ in range(info.channel_count()):labels.append(node.child_value('label'));node=node.next_sibling()
            if not all(c in labels for c in CHANNELS) or abs(info.nominal_srate()-256)>1:raise ValueError('Expected four Muse channels at 256 Hz')
            indices=[labels.index(c) for c in CHANNELS];buffer=LiveQuality();reported=0;correction=inlet.time_correction(timeout=4)
            while not stopping:
                samples,times=inlet.pull_chunk(timeout=.25,max_samples=256)
                if times:
                    corrected=[t+correction for t in times]
                    if abs(corrected[-1]-local_clock())>1.5:raise ValueError('EEG timestamps are stale or use an incompatible clock. Restart the streamer with --lsltime.')
                    buffer.push(corrected,[[row[i] for i in indices] for row in samples])
                if time.monotonic()-reported>=.5:emit(buffer.snapshot());reported=time.monotonic()
        except Exception as exc:emit(dict(ready=False,good_seconds=0,status=str(exc),channels=[],traces=[]))
        finally:inlet.close_stream()
if __name__=='__main__':main()
