"""Full-resolution NumPy export and static Matplotlib figures; original CSV untouched."""
import csv,json
from pathlib import Path
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_pdf import FigureCanvasPdf
from analysis import analyze,CHANNELS

from theme import TOKENS, report_theme

@report_theme
def generate(path,destination):
    path=Path(path);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    result=analyze(path)
    values=np.genfromtxt(path,delimiter=',',names=True)
    timestamps=np.atleast_1d(values['timestamps'])
    eeg=np.column_stack([np.atleast_1d(values[c]) for c in CHANNELS])
    np.savez_compressed(destination/'recording.npz',timestamps=timestamps,eeg=eeg,channel_names=np.array(CHANNELS),nominal_sample_rate=np.array(256))
    (destination/'quality.json').write_text(json.dumps({k:v for k,v in result.items() if k!='channels'},indent=2))
    fig=Figure(figsize=(float(TOKENS['plot-report-width']),float(TOKENS['plot-report-height'])),layout='constrained');FigureCanvasAgg(fig)
    axes=fig.subplots(4,2)
    for i,c in enumerate(result['channels']):
        ax,ps=axes[i]
        ax.plot(timestamps-timestamps[0],eeg[:,i],lw=float(TOKENS['plot-line-width']),color=TOKENS['signal-raw'])
        ax.set_ylabel(c['name']+' (µV)');ax.grid(alpha=float(TOKENS['plot-grid-alpha']))
        spectrum=np.asarray(c['spectrum'])
        if len(spectrum):ps.semilogy(spectrum[:,0],spectrum[:,1],color=TOKENS['signal-3'],lw=float(TOKENS['chart-stroke-raw']))
        ps.set_xlim(0,100);ps.set_ylabel('PSD (µV²/Hz)');ps.grid(alpha=float(TOKENS['plot-grid-alpha']))
    axes[0,0].set_title('Raw EEG · full resolution');axes[0,1].set_title('Welch spectrum · longest continuous segment, 256 Hz')
    axes[-1,0].set_xlabel('Seconds');axes[-1,1].set_xlabel('Hz')
    fig.suptitle(path.name,fontsize=float(TOKENS['type-section'].removesuffix('px'))*.75,fontfamily=TOKENS['font-display-name'])
    fig.savefig(destination/'signals.png',dpi=int(TOKENS['plot-report-dpi']));fig.savefig(destination/'signals.pdf')
    return destination
