"""Conservative, offline screening and filtering; never edits the source recording."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import scipy
from scipy.signal import butter, sosfiltfilt, iirnotch, tf2sos, welch
from analysis import CHANNELS

FS = 256
VERSION = '1.0'
BANDS = {'theta': (4, 8), 'alpha': (8, 13), 'beta': (13, 30)}

def runs(mask):
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))

def spectral(x, boundaries):
    """Welch over complete 2 s windows, weighted by window count, never across gaps."""
    total = None; count = 0; freq = np.fft.rfftfreq(512, 1 / FS)
    for a, b in zip(boundaries[:-1], boundaries[1:]):
        for lo, hi in runs(np.isfinite(x[a:b])):
            segment = x[a + lo:a + hi]
            if len(segment) < 512: continue
            f, p = welch(segment, fs=FS, nperseg=512, noverlap=256, detrend='constant')
            windows = 1 + (len(segment) - 512) // 256
            total = p * windows if total is None else total + p * windows
            count += windows
    return freq, total / count if count else None, count

def powers(freq, psd):
    if psd is None: return {name: None for name in BANDS}
    return {name: float(np.trapz(psd[(freq >= lo) & (freq <= hi)], freq[(freq >= lo) & (freq <= hi)]))
            for name, (lo, hi) in BANDS.items()}

def preview(t, x, boundaries):
    """Chronological min/max bins with explicit breaks at missing data and gaps."""
    points = []; step = max(1, int(np.ceil(len(t) / 1800)))
    for a, b in zip(boundaries[:-1], boundaries[1:]):
        if points: points.append([float(t[a]), None])
        for lo, hi in runs(np.isfinite(x[a:b])):
            lo += a; hi += a
            points.append([float(t[lo]), None])
            for start in range(lo, hi, step):
                end = min(start + step, hi); values = x[start:end]
                ids = sorted(set([start + int(np.argmin(values)), start + int(np.argmax(values))]))
                points.extend([[float(t[i]), float(x[i])] for i in ids])
            points.append([float(t[hi - 1]), None])
    return points

def clean(path, destination, options=None, session_folder=None):
    path = Path(path); destination = Path(destination); options = options or {}
    threshold = float(options.get('amplitude_uv', 200))
    notch = int(options.get('notch_hz', 0))
    if not np.isfinite(threshold) or not 100 <= threshold <= 1000: raise ValueError('Amplitude threshold must be 100–1000 µV peak-to-peak.')
    if notch not in [0, 50, 60]: raise ValueError('Choose no notch, 50 Hz, or 60 Hz.')
    manual = options.get('exclusions', [])
    if not isinstance(manual, list) or len(manual) > 100: raise ValueError('Use at most 100 manual exclusions.')
    values = np.genfromtxt(path, delimiter=',', names=True)
    if not values.dtype.names or not all(c in values.dtype.names for c in ['timestamps'] + CHANNELS): raise ValueError('Use a Muse CSV with timestamps and TP9, AF7, AF8, TP10.')
    t = np.atleast_1d(values['timestamps']); x = np.column_stack([np.atleast_1d(values[c]) for c in CHANNELS])
    if len(t) < FS * 4 or not np.isfinite(t).all(): raise ValueError('Need at least 4 seconds of samples and finite timestamps.')
    dt = np.diff(t)
    if np.any(dt <= 0): raise ValueError('Timestamps repeat or run backward. Repair their provenance before cleaning; samples were not reordered.')
    if not .003 <= float(np.median(dt)) <= .005: raise ValueError('This workflow requires Muse EEG sampled at approximately 256 Hz.')
    elapsed = t - t[0]
    boundaries = np.r_[0, np.flatnonzero(dt > .020) + 1, len(t)]
    reasons = np.zeros(x.shape, dtype=np.uint16)
    # Bit mask permits overlapping reasons without silently replacing them.
    reason_names = {1:'missing/nonfinite', 2:'near rail (|raw| ≥ 995 µV)', 4:'large 2 s peak-to-peak', 8:'flat 2 s window (SD < 0.1 µV)', 16:'manual exclusion', 32:'0.25 s artifact margin', 64:'filter edge / short clean segment'}
    reasons[~np.isfinite(x)] |= 1
    reasons[np.abs(x) >= 995] |= 2
    for a, b in zip(boundaries[:-1], boundaries[1:]):
        for start in range(a, b, FS * 2):
            end = min(start + FS * 2, b)
            if end - start < FS // 2: continue
            for ch in range(4):
                v = x[start:end, ch]
                if not np.isfinite(v).all(): continue
                if np.ptp(v) > threshold: reasons[start:end, ch] |= 4
                if np.std(v) < .1: reasons[start:end, ch] |= 8
    normalized_manual = []
    for item in manual:
        lo = float(item['start']); hi = float(item['end']); label = str(item.get('reason', 'manual'))[:120]
        if not np.isfinite([lo, hi]).all() or not 0 <= lo < hi <= elapsed[-1] + 1 / FS: raise ValueError('Manual exclusions must fall inside the recording, with end after start.')
        reasons[(elapsed >= lo) & (elapsed < hi), :] |= 16
        normalized_manual.append(dict(start=lo, end=hi, reason=label))
    # Margins stay within each continuous timestamp segment.
    for a, b in zip(boundaries[:-1], boundaries[1:]):
        for ch in range(4):
            for lo, hi in runs(reasons[a:b, ch] != 0):
                reasons[max(a, a + lo - 64):min(b, a + hi + 64), ch] |= 32
    sos = butter(4, [1, 40], btype='bandpass', fs=FS, output='sos')
    if notch:
        nb, na = iirnotch(notch, 30, fs=FS); sos = np.vstack([tf2sos(nb, na), sos])
    filtered = np.full_like(x, np.nan)
    for a, b in zip(boundaries[:-1], boundaries[1:]):
        for ch in range(4):
            for lo, hi in runs(reasons[a:b, ch] == 0):
                start = a + lo; end = a + hi
                if end - start < FS * 3:
                    reasons[start:end, ch] |= 64; continue
                y = sosfiltfilt(sos, x[start:end, ch])
                # A fixed 1 s guard is conservative screening, not proof all transients vanish.
                filtered[start + FS:end - FS, ch] = y[FS:-FS]
                reasons[start:start + FS, ch] |= 64; reasons[end - FS:end, ch] |= 64
    usable_channel = np.isfinite(filtered); usable = usable_channel.all(axis=1)
    common = filtered.copy(); common[~usable, :] = np.nan
    intervals = []
    for ch, name in enumerate(CHANNELS):
        # Split whenever the reason combination changes, including timestamp boundaries.
        breaks = np.unique(np.r_[boundaries, np.flatnonzero(np.diff(reasons[:, ch]) != 0) + 1])
        for a, b in zip(breaks[:-1], breaks[1:]):
            bits = int(reasons[a, ch])
            if bits: intervals.append(dict(channel=name, start=float(elapsed[a]), end=float(elapsed[b-1] + 1/FS), reason='; '.join(text for bit,text in reason_names.items() if bits & bit), reason_bits=bits))
    channels = []
    for ch, name in enumerate(CHANNELS):
        f, psd, count = spectral(common[:, ch], boundaries)
        raw_f, raw_psd, _ = spectral(x[:, ch], boundaries)
        channels.append(dict(name=name, usable_percent=float(usable_channel[:, ch].mean()*100), raw=preview(elapsed,x[:,ch],boundaries), filtered=preview(elapsed,filtered[:,ch],boundaries), raw_spectrum=[] if raw_psd is None else [[float(a),float(b)] for a,b in zip(raw_f,raw_psd) if a <= 80], spectrum=[] if psd is None else [[float(a),float(b)] for a,b in zip(f,psd) if a <= 80], bandpower_uv2=powers(f,psd), spectral_windows=count))
    trial_rows = []
    if session_folder and (Path(session_folder)/'events.csv').is_file():
        pending = {}
        with (Path(session_folder)/'events.csv').open() as stream:
            for event in csv.DictReader(stream):
                name = event['event']; key = event['trial_id']
                if name in ['AUDIO_PLAY_REQUEST','LIVE_SPEECH_START_REQUEST']: pending[key] = event
                elif name in ['AUDIO_PLAYBACK_RETURNED','LIVE_SPEECH_END_REQUEST'] and key in pending:
                    start = pending.pop(key); lo=float(start['lsl_timestamp']); hi=float(event['lsl_timestamp'])
                    inside = (t >= lo) & (t < hi)
                    for ch, channel in enumerate(CHANNELS):
                        v = np.full(len(t), np.nan); v[inside] = common[inside,ch]
                        f,p,n = spectral(v,boundaries)
                        trial_rows.append(dict(trial_id=key,clip_id=event['clip_id'],mode='live' if name.startswith('LIVE') else 'audio',channel=channel,marked_seconds=max(0,hi-lo),recorded_seconds=float(inside.sum()/FS),usable_seconds=float((inside & usable).sum()/FS),recorded_samples=int(inside.sum()),usable_samples=int((inside & usable).sum()),usable_percent=float(usable[inside].mean()*100) if inside.any() else None, spectral_windows=n,**powers(f,p)))
    settings = dict(pipeline_version=VERSION,sample_rate_hz=FS,bandpass_hz=[1,40],butterworth_design_N=4,bandpass_order=8,forward_backward_bandpass_order=16,implementation='SciPy butter SOS + sosfiltfilt, forward/backward; optional notch Q=30 before band-pass',notch_hz=notch,amplitude_uv=threshold,artifact_window_seconds=2,flat_sd_uv=.1,rail_uv=995,artifact_margin_seconds=.25,edge_guard_seconds=1,min_filter_segment_seconds=3,gap_threshold_seconds=.020,welch_window_seconds=2,welch_overlap_percent=50,manual_exclusions=normalized_manual,numpy_version=np.__version__,scipy_version=scipy.__version__)
    warnings = ['Screening heuristics may miss blinks, muscle activity and contact artifacts; inspect the traces. Retained does not mean validated.', '1–40 Hz filtering removes slow activity; this preset is for exploratory band-power, not ERP/slow-potential analysis.', 'No ICA, channel interpolation, rereferencing, resampling, gap filling, or EEG comprehension prediction. Filtered values are NaN where rejected.', 'Band powers use only common retained intervals across all four channels; at least 2 continuous seconds are needed. Raw and retained spectra may cover different intervals.', 'Retained seconds count samples / 256; gaps are absent data. Percentages refer to recorded samples, not elapsed wall time.']
    if len(boundaries)>2: warnings.append('Timestamp gaps were split before filtering and spectral analysis; missing EEG was not reconstructed.')
    if not usable.any(): warnings.append('No samples passed the common four-channel screen. No band powers can be estimated; consider re-recording.')
    report = dict(file=path.name,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),duration_seconds=float(elapsed[-1]),recorded_seconds=len(t)/FS,samples=len(t),gaps=len(boundaries)-2,gap_seconds=float(np.sum(dt[dt>.020]-1/FS)),usable_percent=float(usable.mean()*100),usable_seconds=float(usable.sum()/FS),rejected_percent=float((~usable).mean()*100),settings=settings,warnings=warnings,channels=channels,intervals=intervals,trials=trial_rows)
    destination.mkdir(parents=True,exist_ok=False)
    with (destination/'cleaned.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['timestamps']+CHANNELS+['usable_all_channels']+['usable_'+c for c in CHANNELS])
        for i in range(len(t)):writer.writerow([f'{t[i]:.9f}']+[f'{v:.9g}' if np.isfinite(v) else '' for v in filtered[i]]+[int(usable[i])]+usable_channel[i].astype(int).tolist())
    np.savez_compressed(destination/'cleaned.npz',timestamps=t,eeg=filtered,usable=usable,usable_channel=usable_channel,reason_bits=reasons,channel_names=np.array(CHANNELS),sample_rate_hz=np.array(FS))
    for filename,rows,fields in [('rejected_intervals.csv',intervals,['channel','start','end','reason','reason_bits']),('trial_analysis.csv',trial_rows,['trial_id','clip_id','mode','channel','marked_seconds','recorded_seconds','usable_seconds','recorded_samples','usable_samples','usable_percent','spectral_windows','theta','alpha','beta'])]:
        with (destination/filename).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    (destination/'analysis.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    (destination/'PROCESSING.txt').write_text('NeuroBridge Review & clean\n\n'+json.dumps(settings,indent=2)+'\n\n'+'\n'.join(warnings)+'\n\ncleaned.csv and cleaned.npz preserve original timestamps and sample count. CSV blanks / NPZ NaNs mark rejected channel samples. usable is the common four-channel mask used for band powers; usable_channel is per-channel availability. Interval times are seconds from the first EEG timestamp. Manual exclusions apply to all channels. Trial boundaries, when available, are operator/playback request markers, not measured acoustic onsets. Theta 4–8, alpha 8–13, beta 13–30 Hz powers are absolute µV² after filtering. They do not measure comprehension. No source CSV is changed. The source SHA-256 is in analysis.json.\n')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig=Figure(figsize=(15,10),layout='constrained');FigureCanvasAgg(fig);axes=fig.subplots(4,3)
    for ch,c in enumerate(channels):
        for ax,signal,title in [(axes[ch,0],x[:,ch],'Raw EEG'),(axes[ch,1],filtered[:,ch],'Filtered / rejected gaps')]:
            for a,b in zip(boundaries[:-1],boundaries[1:]):ax.plot(elapsed[a:b],signal[a:b],lw=.35,color='#75618e')
            if title=='Raw EEG':
                for a,b in runs(~usable_channel[:,ch]):ax.axvspan(elapsed[a],elapsed[b-1]+1/FS,color='#c79495',alpha=.25,lw=0)
            ax.set_ylabel(c['name']+' · µV');ax.set_title(title if ch==0 else '');ax.set_xlabel('Seconds');ax.grid(alpha=.15)
        for values,color,label in [(c['raw_spectrum'],'#aaa4b0','Raw'),(c['spectrum'],'#75618e','Retained')]:
            if values:
                v=np.array(values);axes[ch,2].semilogy(v[:,0],v[:,1],color=color,label=label)
        axes[ch,2].set(xlim=(0,80),xlabel='Hz',ylabel='µV²/Hz');axes[ch,2].grid(alpha=.15)
    axes[0,2].set_title('Welch PSD · different retained coverage')
    if axes[0,2].lines:axes[0,2].legend()
    fig.suptitle(f'{path.name} · {report["usable_percent"]:.1f}% retained across all four channels · heuristic screen',fontsize=11)
    fig.savefig(destination/'comparison.png',dpi=150);fig.savefig(destination/'comparison.pdf')
    return report
