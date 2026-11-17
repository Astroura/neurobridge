import unittest,tempfile,sys,os,json,threading,urllib.request,urllib.error,csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'neurobridge'))
import numpy as np
from analysis import analyze
from reports import generate
from runtime import ensure,worker

class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.csv=self.root/'signal.csv';t=np.arange(2560)/256
        data=np.column_stack([t]+[20*np.sin(2*np.pi*10*t)]*4)
        np.savetxt(self.csv,data,delimiter=',',header='timestamps,TP9,AF7,AF8,TP10',comments='')
    def tearDown(self):self.temp.cleanup()
    def test_spectral_peak_and_exact_numpy_export(self):
        a=analyze(self.csv)
        self.assertEqual(a['samples'],2560);self.assertEqual(a['gaps'],0)
        spectrum=np.array(a['channels'][0]['spectrum']);self.assertAlmostEqual(spectrum[np.argmax(spectrum[:,1]),0],10,delta=.25)
        before=self.csv.read_bytes();dest=generate(self.csv,self.root/'reports')
        d=np.load(dest/'recording.npz',allow_pickle=False)
        self.assertEqual(d['eeg'].shape,(2560,4));self.assertEqual(list(d['channel_names']),['TP9','AF7','AF8','TP10'])
        self.assertTrue((dest/'signals.png').read_bytes().startswith(b'\x89PNG'))
        self.assertTrue((dest/'signals.pdf').read_bytes().startswith(b'%PDF'))
        self.assertEqual(before,self.csv.read_bytes())
    def test_reject_bad_csv(self):
        self.csv.write_text('wrong,columns\n1,2\n')
        with self.assertRaises(ValueError):analyze(self.csv)
    def test_paths_and_dispatch(self):
        chosen=ensure(self.root/'folder with spaces');self.assertTrue((chosen/'sessions').is_dir())
        cmd=worker('record',chosen/'raw/x.csv',60)
        self.assertIn('--worker',cmd);self.assertEqual(cmd[-1],'60')

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();os.environ['NEUROBRIDGE_DATA_DIR']=cls.temp.name
        import server
        cls.s=server;server.ROOT=ensure(cls.temp.name);server.RAW=server.ROOT/'raw'
        from http.server import ThreadingHTTPServer
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);server.PORT=cls.http.server_address[1]
        cls.base='http://127.0.0.1:'+str(server.PORT)
        threading.Thread(target=cls.http.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.temp.cleanup()
    def request(self,path,data,token=True):
        headers={'Content-Type':'application/json'}
        if token:headers['X-NeuroBridge']=self.s.TOKEN
        return urllib.request.urlopen(urllib.request.Request(self.base+path,data=json.dumps(data).encode(),headers=headers))
    def test_pages_and_persistent_setup(self):
        for path in ['/','/experiment','/storage.js','/api/storage']:
            with urllib.request.urlopen(self.base+path) as r:self.assertEqual(r.status,200)
        with self.request('/api/setup',{'participant':'P01','clips':[]}):pass
        with urllib.request.urlopen(self.base+'/api/setup') as r:self.assertEqual(json.load(r)['participant'],'P01')
    def test_reject_csrf_and_invalid_sessions(self):
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/connect',{},token=False)
        self.assertEqual(e.exception.code,403)
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/session/start',{'participant':'../invalid'})
        self.assertEqual(e.exception.code,400)
    def test_traversal(self):
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(self.base+'/api/download?file=../settings.json')

if __name__=='__main__':unittest.main()
