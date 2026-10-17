const test=require('node:test'),assert=require('node:assert/strict');
const {slotAt,plan,tick}=require('./construction-businesses-weekly.cjs');
test('KST Monday 05 boundary, independent of host timezone',()=>{
 assert.equal(new Date(slotAt(Date.parse('2026-10-11T19:59:59Z'))).toISOString(),'2026-10-04T20:00:00.000Z');
 assert.equal(new Date(slotAt(Date.parse('2026-10-11T20:00:00Z'))).toISOString(),'2026-10-11T20:00:00.000Z');
 assert.equal(new Date(slotAt(Date.parse('2026-12-31T23:00:00Z'))).toISOString(),'2026-12-27T20:00:00.000Z');
});
test('one run per week, new weeks restart, failures resume, retry delay',()=>{
 const now=Date.parse('2026-10-12T00:00:00Z'),slot=slotAt(now);
 assert.equal(plan({success_slot:slot},now).due,false);
 assert.equal(plan({success_slot:slot-7*864e5,attempt_slot:slot-7*864e5},now).restart,true);
 assert.equal(plan({attempt_slot:slot},now).restart,false);
 assert.equal(plan({attempt_slot:slot,retry_at:now+1000},now).due,false);
});
function fake(state={},current={status:'complete',processed:2057,total:2057}) {
 const connection={release(){},async query(sql,params=[]){
  if(sql.includes('GET_LOCK'))return [[{acquired:1}]];
  if(sql.includes('SELECT * FROM construction_business_schedule'))return [[{...state}]];
  if(sql.includes('SELECT status'))return [[current]];
  if(sql.includes('SET attempt_slot')){state.attempt_slot=params[0];state.error=params[1];}
  if(sql.includes('SET error=NULL'))state.error=null;
  if(sql.includes('SET success_slot')){state.success_slot=params[0];state.error=null;}
  if(sql.includes('SET retry_at')){state.retry_at=params[0];state.error=params[1];}
  return [[]];
 }};return {getConnection:async()=>connection};
}
test('successful tick persists weekly completion and does not repeat',async()=>{
 const state={},db=fake(state),now=Date.parse('2026-10-12T00:00:00Z');let calls=0;
 const run=async(_,o)=>{calls++;assert.equal(o.restart,true);await o.onStarted();};
 await tick(db,now,run);await tick(db,now,run);assert.equal(calls,1);assert.equal(state.success_slot,slotAt(now));
});
test('failed run records retry without declaring success',async()=>{
 const state={},db=fake(state),now=Date.parse('2026-10-12T00:00:00Z');
 await tick(db,now,async(_,o)=>{await o.onStarted();throw Error('upstream_connection_failed');});
 assert.equal(state.retry_at,now+3600000);assert.equal(state.success_slot,undefined);
});
test('interrupted page resumes; new-cycle interruption safely restarts',async()=>{
 const now=Date.parse('2026-10-12T00:00:00Z');
 for(const error of [null,'starting_new_cycle']){
  const state={attempt_slot:slotAt(now),error};let restart;
  await tick(fake(state),now,async(_,o)=>{restart=o.restart;await o.onStarted();});
  assert.equal(restart,error==='starting_new_cycle');
 }
});
test('busy manual sync retains restart intent for the next retry',async()=>{
 const state={},db=fake(state),now=Date.parse('2026-10-12T00:00:00Z');
 await tick(db,now,async()=>{throw Error('sync_already_running');});
 assert.equal(state.error,'starting_new_cycle');assert.equal(state.success_slot,undefined);
 await tick(db,now+3600000,async(_,o)=>{assert.equal(o.restart,true);await o.onStarted();});
 assert.equal(state.success_slot,slotAt(now));
});
