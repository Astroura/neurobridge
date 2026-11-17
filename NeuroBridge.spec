from PyInstaller.utils.hooks import collect_all,collect_dynamic_libs
from pathlib import Path
base=Path(SPECPATH)
data=[(str(base/'neurobridge/static'),'neurobridge/static')]
binaries=[];hidden=['server','runtime','reports','analysis','recorder','experiment','protocol','packs','webview.platforms.cocoa','muselsl.cli','muselsl.backends','bleak.backends.corebluetooth']
for package in ['pylsl','webview']:
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
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='NeuroBridge',console=True,disable_windowed_traceback=False,target_arch=None,codesign_identity=None)
coll=COLLECT(exe,a.binaries,a.datas,name='NeuroBridge')
app=BUNDLE(coll,name='NeuroBridge.app',bundle_identifier='org.neurobridge.research',info_plist={
 'CFBundleName':'NeuroBridge','CFBundleShortVersionString':'0.2.0','CFBundleVersion':'2',
 'NSBluetoothAlwaysUsageDescription':'NeuroBridge connects to your Muse headset to record EEG for your local research sessions.',
 'NSBluetoothPeripheralUsageDescription':'Connect to your Muse EEG headset.',
 'NSDocumentsFolderUsageDescription':'Save recordings and scientific reports in the folder you choose.',
 'NSDownloadsFolderUsageDescription':'Export recording archives to the folder you choose.',
 'NSHighResolutionCapable':True,'LSMinimumSystemVersion':'12.0'})
