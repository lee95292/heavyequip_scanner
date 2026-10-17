import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('builder',Path(__file__).with_name('build-specifications.py'));b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
class Facets(unittest.TestCase):
 def fact(self,**changes):return dict(attribute='Operating Weight',unit='kg',value='20,000',category='Weights',verification='reviewed',original_fact={},**changes)
 def test_numbers(self):
  for v,w in [('20,000',[20000,20000]),('20 000',[20000,20000]),('18.2–19.3',[18.2,19.3]),('4.5',[4.5,4.5])]:self.assertEqual(b.numeric_range(v),w)
  for v in ['',None,'unknown','N/A','2 / 4','>10','20,5','220.550','-3','not stated (blank)'] :self.assertIsNone(b.numeric_range(v))
 def test_reference_and_conflict(self):
  f=self.fact();self.assertIsNotNone(b.numeric_facet(f));f['applicable_to_record_model']=False;self.assertIsNone(b.numeric_facet(f));f.pop('applicable_to_record_model');f['original_fact']['conflict_ids']=['C1'];self.assertIsNone(b.numeric_facet(f));f['original_fact']={};f['verification']='source_unit_conflict';self.assertIsNone(b.numeric_facet(f))
 def test_exclusions(self):
  for attr in ['Shipping weight','Axle operating weight','Change in Operating Weight','Tipping Load at Operating Weight','Operating weight increment']:
   f=self.fact();f['attribute']=attr;self.assertIsNone(b.numeric_facet(f))
  self.assertIsNone(b.numeric_facet(self.fact(),assembly=True))
 def test_power(self):
  f=self.fact();f.update(attribute='Net Power ISO 9249',unit='kW',value='120',category='Engine');self.assertEqual(b.numeric_facet(f)[1]['power_type'],'net');f['attribute']='Hydraulic pump power';self.assertIsNone(b.numeric_facet(f))
 def test_new_dimensions_and_capacity(self):
  for attr,unit,value,key,expected in [('Overall width','in',100,'overall_width_mm',2540),('Bucket digging force','kN',100,'bucket_digging_force_kn',100),('Rated operating capacity','lb',1000,'rated_operating_capacity_kg',453.59237),('Drum width','mm',2130,'drum_width_mm',2130)]:
   f=self.fact();f.update(attribute=attr,unit=unit,value=value);k,v=b.numeric_facet(f);self.assertEqual(k,key);self.assertAlmostEqual(v['min'],expected)
  for attr in ['Change in Overall Width','Bucket width','Overall width of fork carriage']:
   f=self.fact();f.update(attribute=attr,unit='mm');self.assertIsNone(b.numeric_facet(f))
 def test_attachment_dimension_is_not_machine_width(self):
  f=self.fact();f.update(attribute='Overall width',unit='mm',category='Attachment: PALLET FORKS');self.assertIsNone(b.numeric_facet(f))
 def test_safe_urls(self):
  for s in ['javascript:alert(1)','data:text/html,x','file:///etc/passwd','https://name:password@example.com']:self.assertIsNone(b.safe_url(s))
  self.assertEqual(b.safe_url('https://www.cat.com/a'),'https://www.cat.com/a')
if __name__=='__main__':unittest.main()
