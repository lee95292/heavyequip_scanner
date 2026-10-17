'use strict';
const {createPool}=require('./construction-businesses-config.cjs');
const {migrate,sync}=require('./construction-businesses.cjs');
const WEEK=7*86400000, HOUR=3600000;
// Monday 05:00 Asia/Seoul == Sunday 20:00 UTC. No dependency on server TZ.
function slotAt(now=Date.now()) {
  const local=new Date(now+9*HOUR);
  const offset=(local.getUTCDay()+6)%7;
  let slot=Date.UTC(local.getUTCFullYear(),local.getUTCMonth(),local.getUTCDate()-offset,5)-9*HOUR;
  if(slot>now)slot-=WEEK;
  return slot;
}
function plan(state,now=Date.now()) {
  const slot=slotAt(now);
  if(Number(state.success_slot)>=slot)return {due:false,slot,next:slot+WEEK};
  if(Number(state.retry_at)>now)return {due:false,slot,next:Number(state.retry_at)};
  return {due:true,slot,restart:Number(state.attempt_slot)!==slot};
}
async function migrateSchedule(db) {
  await db.query(`CREATE TABLE IF NOT EXISTS construction_business_schedule (
    id INT PRIMARY KEY,success_slot BIGINT NULL,attempt_slot BIGINT NULL,retry_at BIGINT NULL,
    heartbeat_at BIGINT NULL,last_success_at BIGINT NULL,error VARCHAR(120) NULL)`);
  await db.query('INSERT IGNORE INTO construction_business_schedule(id) VALUES(1)');
}
async function tick(db,now=Date.now(),synchronize=sync) {
  const connection=await db.getConnection();
  let locked=false;
  try {
    const [[lock]]=await connection.query("SELECT GET_LOCK('scan_construction_weekly_scheduler',0) AS acquired");
    if(!lock.acquired)return;
    locked=true;
    await connection.query('UPDATE construction_business_schedule SET heartbeat_at=? WHERE id=1',[now]);
    const [[state]]=await connection.query('SELECT * FROM construction_business_schedule WHERE id=1');
    const job=plan(state,now);
    if(!job.due)return;
    const [[current]]=await connection.query('SELECT status,error FROM construction_business_sync WHERE id=1');
    const restart=job.restart||current?.error==='upstream_total_changed_restart_required';
    // Persist a new cycle before starting. On process death prior to sync, its prior
    // completed state must not be mistaken for this cycle's successful completion.
    await connection.query('UPDATE construction_business_schedule SET attempt_slot=?,retry_at=NULL,error=? WHERE id=1',[job.slot,restart?'starting_new_cycle':state.error]);
    let started=false;
    const needsRestart=restart||state.error==='starting_new_cycle';
    try {
      await synchronize(db,{restart:needsRestart,
        onStarted:async()=>{await connection.query('UPDATE construction_business_schedule SET error=NULL WHERE id=1');started=true;}});
      const [[done]]=await connection.query('SELECT status,processed,total FROM construction_business_sync WHERE id=1');
      if(done.status!=='complete'||Number(done.processed)!==Number(done.total))throw new Error('sync_not_complete');
      await connection.query('UPDATE construction_business_schedule SET success_slot=?,last_success_at=?,retry_at=NULL,error=NULL WHERE id=1',[job.slot,Date.now()]);
      console.log('[business-weekly] completed',new Date(job.slot).toISOString(),done.processed);
    }catch(error) {
      const code=/^[a-z_0-9]+$/i.test(error.message)?error.message.slice(0,120):'sync_failed';
      await connection.query('UPDATE construction_business_schedule SET retry_at=?,error=? WHERE id=1',[now+HOUR,needsRestart&&!started?'starting_new_cycle':code]);
      console.error('[business-weekly]',code,'retry_after_one_hour');
    }
  }finally {
    if(locked)await connection.query("SELECT RELEASE_LOCK('scan_construction_weekly_scheduler')");
    connection.release();
  }
}
async function main() {
  const db=createPool();
  await migrate(db);await migrateSchedule(db);
  let busy=false,stopping=false;
  const run=async()=>{if(busy||stopping)return;busy=true;try{await tick(db);}catch(_){console.error('[business-weekly] scheduler_database_unavailable');}finally{busy=false;}};
  await run();
  const timer=setInterval(run,60000);
  async function stop(){stopping=true;clearInterval(timer);while(busy)await new Promise(resolve=>setTimeout(resolve,100));await db.end();}
  process.once('SIGINT',stop);process.once('SIGTERM',stop);
  console.log('[business-weekly] Monday 05:00 Asia/Seoul; next slot',new Date(slotAt()+WEEK).toISOString());
}
if(require.main===module)main().catch(()=>{console.error('[business-weekly] startup_failed');process.exitCode=1;});
module.exports={slotAt,plan,tick,migrateSchedule};
