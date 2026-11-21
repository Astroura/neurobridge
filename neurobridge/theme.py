"""Single presentation token source for browser UI and scientific reports."""
import json
from pathlib import Path
from functools import wraps
from runtime import CODE

TOKENS=json.loads((CODE/'static/theme.json').read_text(encoding='utf-8'))

def css():
    return ':root{'+''.join('--'+key+':'+str(value)+';' for key,value in TOKENS.items())+'}'

def report_theme(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        import matplotlib as mpl
        from matplotlib import font_manager
        for name in ['IBMPlexSans-400.ttf','IBMPlexSerif-Regular.ttf']:
            font_manager.fontManager.addfont(CODE/'static/fonts'/name)
        def size(name):return float(TOKENS[name].removesuffix('px'))*.75
        with mpl.rc_context({'font.family':TOKENS['font-ui-name'],'mathtext.fontset':'custom','mathtext.rm':TOKENS['font-ui-name'],'mathtext.it':TOKENS['font-ui-name'],'mathtext.bf':TOKENS['font-ui-name'],'mathtext.sf':TOKENS['font-ui-name'],'mathtext.tt':TOKENS['font-ui-name'],'mathtext.cal':TOKENS['font-ui-name'],'mathtext.fallback':None,'font.size':size('type-body'),
            'axes.titlesize':size('type-body'),'axes.labelsize':size('type-caption'),
            'xtick.labelsize':size('type-caption'),'ytick.labelsize':size('type-caption'),
            'figure.titlesize':size('type-section'),'figure.facecolor':TOKENS['canvas'],
            'axes.facecolor':TOKENS['surface'],'text.color':TOKENS['text'],
            'axes.labelcolor':TOKENS['text-secondary'],'axes.edgecolor':TOKENS['border-control'],
            'xtick.color':TOKENS['signal-axis'],'ytick.color':TOKENS['signal-axis'],
            'grid.color':TOKENS['signal-grid'],'pdf.fonttype':42}):
            return function(*args,**kwargs)
    return wrapped
