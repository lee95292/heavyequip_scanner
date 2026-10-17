#!/usr/bin/env python3
"""Run on the deployment host after a reviewed fast-forward. Stage and test before activation."""
import datetime,hashlib,json,os,pathlib,shutil,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[1]
def run(*cmd,**kwargs):
 print('RUN',*cmd[:4],flush=True);return subprocess.run(cmd,cwd=root,check=True,**kwargs)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
version='20261018-catalog-v4';catalog=root/'dashboard/data/specifications';original='20261018T1735-local-820'
config=root/'crawl/config.json';config_hash=sha(config);old_pointer=(catalog/'current.json').read_bytes()
assert json.loads(old_pointer)['snapshot_id']==original,'Unexpected current catalog: review before deployment'
backup=root/'work/deploy-backups'/('specifications-v2-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));backup.mkdir(parents=True)
(backup/'current-before.json').write_bytes(old_pointer)
run('git','status','--short',stdout=(backup/'status-before.txt').open('w'))
run('git','diff','--binary',stdout=(backup/'changes-before.patch').open('w'))
run('git','rev-parse','HEAD',stdout=(backup/'head.txt').open('w'))
stage=backup/'catalog-stage';stage.mkdir();shutil.copytree(catalog/original,stage/original);(stage/'current.json').write_bytes(old_pointer)
run('python3','scripts/extend-specifications.py',str(stage),version,'data/specifications/official-additions-20261018.json')
run('python3','scripts/install-specifications.py',str(stage),version)
run('python3','scripts/test-specifications-import.py')
env={**os.environ,'SPECIFICATIONS_TEST_ROOT':str(stage)}
run('bash','-lc','node --test dashboard/server/*.test.cjs',env=env,stdout=(backup/'node-tests.log').open('w'),stderr=subprocess.STDOUT)
new_dist=backup/'dist-new';run('npm','--prefix','dashboard','run','build','--','--outDir',str(new_dist))
assert sha(config)==config_hash
assert not (catalog/version).exists()
shutil.move(str(stage/version),str(catalog/version));old_dist=backup/'dist-before';dist=root/'dashboard/dist'
shutil.copytree(dist,old_dist)
try:
 run('python3','scripts/install-specifications.py',str(catalog),version)
 retired=backup/'dist-old-swap';assert not retired.exists();dist.rename(retired);new_dist.rename(dist)
 run('pm2','restart','heavyequip-dashboard')
 print('DEPLOY_COMPLETE',subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),flush=True)
 print('CONFIG_PRESERVED',sha(config)==config_hash,'BACKUP',backup,flush=True)
except BaseException:
 (catalog/'current.json').write_bytes(old_pointer)
 if (backup/'dist-old-swap').exists():
  if dist.exists():shutil.move(str(dist),str(backup/'dist-failed'))
  (backup/'dist-old-swap').rename(dist)
 run('pm2','restart','heavyequip-dashboard');raise
