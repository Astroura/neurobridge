"""Release checks for offline assets and the approved design contract."""
import collections
import json
from pathlib import Path
import re
import unittest

STATIC=Path(__file__).resolve().parents[1]/'neurobridge/static'

class DesignTests(unittest.TestCase):
    def test_forms_have_unique_ids(self):
        for p in STATIC.glob('*.html'):
            ids=collections.Counter(re.findall(r'id="([^"]+)"',p.read_text()))
            self.assertFalse([name for name,count in ids.items() if count>1],p.name)
    def test_component_palettes_are_tokenized(self):
        tokens=json.loads((STATIC/'theme.json').read_text())
        self.assertNotEqual(tokens['action'],tokens['annotation'])
        for pattern in ['*.css','*.js','*.html']:
            for p in STATIC.glob(pattern):
                self.assertIsNone(re.search(r'#[0-9a-fA-F]{3,8}\b',p.read_text()),p.name)
                self.assertNotRegex(p.read_text(),r'font-family:[^;}]*\b(?:Inter|Roboto|Arial|system-ui|-apple-system)\b',p.name)
    def test_local_fonts_include_arabic_and_scientific_glyphs(self):
        from fontTools.ttLib import TTFont
        for filename,text in [('IBMPlexSans-400.ttf','µ±αβθ'),('IBMPlexSansArabic-Regular.ttf','أين توقفت الحافلة؟')]:
            font=TTFont(STATIC/'fonts'/filename)
            cmap=font.getBestCmap()
            self.assertTrue(all(ord(c) in cmap for c in text),filename)
            font.close()
        self.assertTrue((STATIC/'fonts/ibmplexsans-OFL.txt').is_file())
        self.assertTrue((STATIC/'lucide-LICENSE.txt').is_file())

