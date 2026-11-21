from PyInstaller.utils.hooks import collect_all,collect_dynamic_libs,collect_submodules
from pathlib import Path
import sys
base=Path(SPECPATH)
data=[(str(base/'neurobridge/static'),'neurobridge/static'),(str(base/'QUALITY-PROTOCOL.md'),'neurobridge/static')]
binaries=[];hidden=['server','runtime','reports','theme','cleaning','analysis','recorder','experiment','protocol','packs','quality','quality_monitor','terminal_muse','platform_support','audio_player','webview.platforms.cocoa','muselsl.cli','muselsl.backends','bleak.backends.corebluetooth']
windows=sys.platform=='win32'
if windows:
    hidden=[h for h in hidden if h not in ['webview.platforms.cocoa','bleak.backends.corebluetooth']]
    hidden+=['webview.platforms.winforms','webview.platforms.edgechromium','bleak.backends.winrt','bleak.backends.winrt.client','bleak.backends.winrt.scanner','winsound','msvcrt','clr_loader','pythonnet']
    hidden+=collect_submodules('winrt')
for package in ['pylsl','webview','bitstring']+(['imageio_ffmpeg','clr_loader','pythonnet'] if windows else []):
    d,b,h=collect_all(package);data+=d;binaries+=b;hidden+=h
# Include original third-party license files from wheel metadata.
import importlib.metadata as metadata
for dist in metadata.distributions():
    for file in dist.files or []:
        if any(key in str(file).lower() for key in ['license','copying','notice']) and '.dist-info/' in str(file):
            p=Path(dist.locate_file(file))
            if p.is_file():data.append((str(p),'third_party_licenses/'+dist.metadata['Name']))
a=Analysis([str(base/'app.py')],pathex=[str(base/'neurobridge')],binaries=binaries,datas=data,hiddenimports=hidden,excludes=['PyQt5','PyQt6','PySide2','PySide6','tkinter','IPython','pytest','notebook'],noarchive=False)
pyz=PYZ(a.pure)
if not windows:exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='NeuroBridge',console=True,disable_windowed_traceback=False,target_arch=None,codesign_identity=None)
if windows:
    # Keep the UI window free of a console, but give workers real stdout/stdin.
    gui=EXE(pyz,a.scripts,[],exclude_binaries=True,name='NeuroBridge',console=False)
    # The existing console EXE gets a distinct name on Windows.
    console_worker=EXE(pyz,a.scripts,[],exclude_binaries=True,name='NeuroBridge-Worker',console=True)
    coll=COLLECT(gui,console_worker,a.binaries,a.datas,name='NeuroBridge')
else:
    coll=COLLECT(exe,a.binaries,a.datas,name='NeuroBridge')
if not windows:
    app=BUNDLE(coll,name='NeuroBridge.app',bundle_identifier='org.neurobridge.research',info_plist={
     'CFBundleName':'NeuroBridge','CFBundleShortVersionString':'0.7.0','CFBundleVersion':'8',
     'NSBluetoothAlwaysUsageDescription':'NeuroBridge connects to your Muse headset to record EEG for your local research sessions.',
     'NSBluetoothPeripheralUsageDescription':'Connect to your Muse EEG headset.',
     'NSDocumentsFolderUsageDescription':'Save recordings and scientific reports in the folder you choose.',
     'NSDownloadsFolderUsageDescription':'Export recording archives to the folder you choose.',
     'NSHighResolutionCapable':True,'LSMinimumSystemVersion':'12.0'})
