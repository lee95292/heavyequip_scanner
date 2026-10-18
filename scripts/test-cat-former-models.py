#!/usr/bin/env python3
import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build-specifications.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
class LegacyCatalogTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rows=json.loads((ROOT/'data/specifications/cat-former-models-20261018.json').read_text());cls.models={ (m['model_name'],m['category']):m for m in cls.rows }
 def test_target_models_and_source_facts(self):
  for name,power in [('D6H','165'),('D9N','370'),('D8N','285')]:
   m=self.models[(name,'도저')];self.assertTrue(any(f['attribute']=='Net engine power (flywheel)' and f['value']==power for f in m['facts']));self.assertTrue(all(f.get('source_pdf_page') and f.get('configuration') for f in m['facts']))
 def test_ambiguous_dozer_power_pairs_are_held(self):
  fs=self.models[('D6H','도저')]['facts'];f=next(f for f in fs if f.get('source_cell')=='123/165');self.assertEqual(f['value'],'123/165');self.assertIsNone(b.numeric_facet(f));self.assertEqual(f['verification'],'source_unit_conflict')
 def test_unique_identities_and_nonempty_evidence(self):
  self.assertEqual(len(self.rows),len(self.models))
  for m in self.rows:
   self.assertGreaterEqual(len(m['facts']),2);self.assertEqual(len(m['source_sha256']),64)
 def test_source_conflict_is_not_a_filter_value(self):
  m=self.models[('D9N','도저')];f=next(f for f in m['facts'] if f['attribute']=='Overall width');self.assertEqual(f['verification'],'source_unit_conflict');self.assertIsNone(b.numeric_facet(f))
 def test_approximate_and_shipping_weights_are_not_operating_weights(self):
  for attr in ['Approximate machine weight','Shipping weight']:
   self.assertIsNone(b.numeric_facet(dict(attribute=attr,value='20000',unit='kg')))
 def test_power_units_and_categories(self):
  m=self.models[('583R','파이프레이어')];f=next(f for f in m['facts'] if 'power' in f['attribute']);self.assertEqual(f['unit'],'kW');self.assertEqual(f['value'],'228')
  self.assertGreaterEqual(len({m['category'] for m in self.rows}),14)
if __name__=='__main__':unittest.main()
