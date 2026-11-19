import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'neurobridge'))
from cleaning import clean, spectral, FS

class CleaningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.t=np.arange(FS*24)/FS+1000
        self.x=20*np.sin(2*np.pi*10*(self.t-1000))+10*np.sin(2*np.pi*70*(self.t-1000))+30*np.sin(2*np.pi*.2*(self.t-1000))
        self.path=self.root/'raw.csv'
    def tearDown(self):self.temp.cleanup()
    def save(self,x=None,t=None):
        x=self.x if x is None else x;t=self.t if t is None else t
        if x.ndim==1:x=np.tile(x[:,None],(1,4))
        np.savetxt(self.path,np.column_stack([t,x]),delimiter=',',header='timestamps,TP9,AF7,AF8,TP10',comments='')
    def test_filter_frequency_response_and_source_preservation(self):
        self.save();before=self.path.read_bytes();report=clean(self.path,self.root/'out')
        self.assertEqual(before,self.path.read_bytes());data=np.load(self.root/'out/cleaned.npz',allow_pickle=False)
        self.assertEqual(data['eeg'].shape,(len(self.t),4));np.testing.assert_array_equal(data['timestamps'],self.t)
        valid=data['usable'];self.assertFalse(valid[:FS].any());self.assertFalse(valid[-FS:].any())
        f,p,n=spectral(data['eeg'][:,0],[0,len(self.t)])
        self.assertAlmostEqual(f[np.argmax(p)],10,delta=.5)
        self.assertLess(p[np.argmin(abs(f-70))],p[np.argmin(abs(f-10))]*.001)
        # A 20 µV sine has 200 µV² power; broad tolerance allows finite-window filtering.
        self.assertAlmostEqual(report['channels'][0]['bandpower_uv2']['alpha'],200,delta=20)
        for name in ['cleaned.csv','cleaned.npz','analysis.json','rejected_intervals.csv','trial_analysis.csv','comparison.png','comparison.pdf','PROCESSING.txt']:self.assertTrue((self.root/'out'/name).is_file())
    def test_artifacts_manual_masks_gaps_and_trial_coverage(self):
        t=self.t.copy();t[FS*12:]+=3;x=np.tile(self.x[:,None],(1,4));x[FS*4:FS*6,0]=1000
        x[FS*8:FS*10,1]=0;x[FS*14,2]=np.nan
        self.save(x,t);session=self.root/'session';session.mkdir()
        with (session/'events.csv').open('w',newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=['event','trial_id','clip_id','lsl_timestamp']);w.writeheader()
            for event,stamp in [('AUDIO_PLAY_REQUEST',1000),('AUDIO_PLAYBACK_RETURNED',1030)]:w.writerow(dict(event=event,trial_id='T01',clip_id='EN01',lsl_timestamp=stamp))
        report=clean(self.path,self.root/'out',{'exclusions':[dict(start=18,end=20,reason='Subject speech')]},session)
        d=np.load(self.root/'out/cleaned.npz',allow_pickle=False);self.assertEqual(report['gaps'],1)
        self.assertTrue(np.isnan(d['eeg'][FS*4:FS*6,0]).all());self.assertTrue(np.isnan(d['eeg'][FS*8:FS*10,1]).all())
        self.assertFalse(d['usable'][np.logical_and(t-1000>=18,t-1000<20)].any())
        self.assertTrue(np.isnan(d['eeg'][FS*12-FS:FS*12+FS]).all())
        self.assertEqual(len(report['trials']),4);self.assertLess(report['trials'][0]['usable_percent'],100)
        self.assertGreater(d['usable_channel'][:,3].sum(),d['usable'].sum())
        self.assertTrue(any(i['reason_bits'] & 16 for i in report['intervals']))
        self.assertEqual(json.loads((self.root/'out/analysis.json').read_text())['settings']['manual_exclusions'][0]['reason'],'Subject speech')
    def test_completely_bad_data_has_no_fabricated_power(self):
        self.save(np.zeros(len(self.t)));r=clean(self.path,self.root/'out')
        self.assertEqual(r['usable_percent'],0);self.assertIsNone(r['channels'][0]['bandpower_uv2']['alpha'])
        self.assertEqual(r['channels'][0]['spectrum'],[])
    def test_reject_backward_timestamps_and_invalid_settings(self):
        t=self.t.copy();t[300]=t[299];self.save(t=t)
        with self.assertRaisesRegex(ValueError,'backward'):clean(self.path,self.root/'out')
        self.save()
        for opts in [{'amplitude_uv':float('nan')},{'notch_hz':30},{'exclusions':[dict(start=-1,end=3)]}]:
            with self.assertRaises(ValueError):clean(self.path,self.root/'out',opts)

if __name__=='__main__':unittest.main()
