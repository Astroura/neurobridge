import hashlib,json,re,unicodedata,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'stimulus-materials/collections'
class CatalogTests(unittest.TestCase):
 def test_source_hashes_answer_evidence_and_translation_pairs(self):
  catalog=json.loads((ROOT/'catalog.json').read_text());self.assertEqual(len(catalog),20)
  normalize=lambda s:re.sub('[\u064b-\u065f\u0670]','',unicodedata.normalize('NFC',s))
  keys=set();paired={}
  for c in catalog:
   self.assertNotIn(c['key'],keys);keys.add(c['key'])
   self.assertEqual(hashlib.sha256((ROOT/c['file']).read_bytes()).hexdigest(),c['sha256'])
   self.assertLess(c['processed_peak'],.999)
   if c['questions']:
    self.assertEqual(len(c['questions']),2)
    for q in c['questions']:
     self.assertEqual(len(set(q['options'])),3);self.assertIn(q['correct'],range(3));self.assertIn(normalize(q['evidence']),normalize(c['transcript']))
   else:paired.setdefault(c['source_id'],set()).add(c['language_config'])
  self.assertEqual(len(paired),4)
  for languages in paired.values():self.assertEqual(languages,{'hi_in','en_us'})
