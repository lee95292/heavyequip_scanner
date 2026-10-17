const fs = require('fs');
const path = require('path');

function validateRule(body = {}) {
  const errors = {}, value = {};
  value.model_contains = typeof body.model_contains === 'string' ? body.model_contains.trim() : '';
  value.email = typeof body.email === 'string' ? body.email.trim() : '';
  if (!value.model_contains || value.model_contains.length > 120) errors.model_contains = '모델명 포함 조건을 1~120자로 입력하세요.';
  if (value.email.length > 254 || !/^[^\s@<>,;:"()[\]\\]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(value.email)) errors.email = '수신 이메일 주소 하나를 입력하세요.';
  for (const field of ['price_min_manwon','price_max_manwon','year_min','year_max']) {
    const input = body[field];
    value[field] = input === '' || input == null ? null : Number(input);
    const year = field.startsWith('year'), interval = field === 'interval_minutes';
    const min = interval ? 1 : year ? 1900 : 0, max = interval ? 1440 : year ? new Date().getFullYear()+1 : 100000000;
    if ((interval && value[field] === null) || (value[field] !== null && (typeof input === 'boolean' || !Number.isSafeInteger(value[field]) || value[field] < min || value[field] > max))) errors[field] = `${min}~${max} 범위의 정수를 입력하세요.`;
  }
  for (const [min,max] of [['price_min_manwon','price_max_manwon'],['year_min','year_max']]) {
    if (value[min] !== null && value[max] !== null && value[min] > value[max]) errors[max] = '최댓값은 최솟값 이상이어야 합니다.';
  }
  value.enabled = body.enabled === true;
  if (typeof body.enabled !== 'boolean') errors.enabled = '활성화 여부가 올바르지 않습니다.';
  return {value,errors};
}

function validateScan(body = {}) {
  const errors={}, value={enabled:body.enabled===true,interval_minutes:Number(body.interval_minutes),request_delay_seconds:Number(body.request_delay_seconds??2),categories:Array.isArray(body.categories)?[...new Set(body.categories)]:[]};
  if(typeof body.enabled!=='boolean') errors.enabled='활성화 여부가 올바르지 않습니다.';
  if(typeof body.interval_minutes==='boolean'||!Number.isSafeInteger(value.interval_minutes)||value.interval_minutes<1||value.interval_minutes>1440) errors.interval_minutes='1~1440분 범위의 정수를 입력하세요.';
  if(typeof body.request_delay_seconds==='boolean'||!Number.isSafeInteger(value.request_delay_seconds)||value.request_delay_seconds<1||value.request_delay_seconds>30) errors.request_delay_seconds='1~30초 범위의 정수를 입력하세요.';
  if((value.enabled&&!value.categories.length)||value.categories.length>15||value.categories.some(v=>typeof v!=='string'||!/^\d{6}$/.test(v))) errors.categories='카테고리를 최대 15개 선택하세요. 시작하려면 1개 이상 필요합니다.';
  return {value,errors};
}

function logPayload(value) {
  let rows=value;
  if(typeof rows==='string') {try {rows=JSON.parse(rows)} catch (_) {rows=[]}}
  if(!Array.isArray(rows)) rows=[];
  const text=value=>typeof value==='string'||(typeof value==='number'&&Number.isFinite(value))?String(value):null;
  return {
    response_rows:rows.filter(row=>row&&typeof row==='object'&&!Array.isArray(row)).map(row=>({
      model_name:text(row.model_name),manufactured_ym:text(row.manufactured_ym),price:text(row.price)
    })),
    sample_names:rows.filter(row=>typeof row==='string').slice(0,5)
  };
}

const snapshotFields=['listing_name','model_name','manufacturer','price','manufactured_ym','location','seller','status','category_code','category_name','posted_at','detail_url','contact','description'];
function mailSnapshot(value) {
  let snapshot=value;
  if(typeof snapshot==='string'){try{snapshot=JSON.parse(snapshot)}catch{return null}}
  if(!snapshot||typeof snapshot!=='object'||Array.isArray(snapshot)||snapshot.version!==1)return null;
  const text=value=>typeof value==='string'?value:null;
  return {version:1,captured_at:text(snapshot.captured_at),
    contact_status:['available','missing','fetch_failed','unavailable','not_collected'].includes(snapshot.contact_status)?snapshot.contact_status:'unavailable',
    ...Object.fromEntries(snapshotFields.map(key=>[key,text(snapshot[key])]))};
}

async function ensureMailSnapshotColumn(pool) {
  const [columns]=await pool.query("SHOW COLUMNS FROM focus_mail_history LIKE 'listing_snapshot_json'");
  if(columns.length)return;
  try {await pool.query('ALTER TABLE focus_mail_history ADD COLUMN listing_snapshot_json JSON NULL')}
  catch(error){if(error.code!=='ER_DUP_FIELDNAME'&&error.errno!==1060)throw error}
}

function registerFocusScan(app, getPool) {
  let ready;
  async function db() {
    const pool = getPool();
    if (!ready) ready = (async()=>{
      const schema=fs.readFileSync(path.join(__dirname,'../../crawl/focus_schema.sql'),'utf8');
      for (const sql of schema.split(';').filter(s=>s.trim())) await pool.query(sql);
      await ensureMailSnapshotColumn(pool);
      const [tables]=await pool.query("SHOW TABLES LIKE 'listing_alert_rules'");
      const [imported]=await pool.query("SELECT name FROM focus_migrations WHERE name='legacy-rules-imported'");
      if (tables.length&&!imported.length) {
        await pool.query(`INSERT IGNORE INTO focus_rules
        (legacy_id,model_contains,email,price_min_manwon,price_max_manwon,year_min,year_max,categories_json,enabled,last_summary)
        SELECT id,model_contains,email,price_min_manwon,price_max_manwon,year_min,year_max,JSON_ARRAY(),0,
        '이전 알림 조건 · 카테고리 선택 후 시작하세요' FROM listing_alert_rules`);
        await pool.query("INSERT IGNORE INTO focus_migrations(name) VALUES('legacy-rules-imported')");
      }
    })().catch(e=>{ready=null;throw e});
    await ready; return pool;
  }
  const handler=fn=>async(req,res)=>{
    res.set('Cache-Control','no-store');
    try {await fn(req,res)} catch (_) {res.status(503).json({error:'집중탐색 정보를 처리하지 못했습니다. 잠시 후 다시 시도하세요.'})}
  };
  async function categories(pool) {
    const [rows]=await pool.query(`SELECT category_code code,MAX(category_name) name FROM crawl_tasks
      WHERE site_slug='green_heavy' AND category_code REGEXP '^[0-9]{6}$'
      GROUP BY category_code ORDER BY category_code`);
    return rows;
  }
  app.get('/api/focus-scan',handler(async(_req,res)=>{
    const pool=await db();
    const [rules]=await pool.query('SELECT id,legacy_id,model_contains,email,price_min_manwon,price_max_manwon,year_min,year_max,enabled,revision FROM focus_rules ORDER BY id DESC LIMIT 100');
    const [[scan]]=await pool.query('SELECT * FROM focus_scan_config WHERE id=1');
    const [logs]=await pool.query('SELECT l.*,s.names_json FROM focus_logs l LEFT JOIN focus_log_samples s ON s.log_id=l.id WHERE l.created_at>=NOW()-INTERVAL 7 DAY ORDER BY l.id DESC LIMIT 100');
    const [state]=await pool.query('SELECT *, TIMESTAMPDIFF(SECOND,heartbeat_at,NOW()) heartbeat_age FROM focus_service_state WHERE id=1');
    res.json({categories:await categories(pool),rules,scan:{...scan,categories:typeof scan.categories_json==='string'?JSON.parse(scan.categories_json):scan.categories_json,categories_json:undefined},logs:logs.map(l=>({...l,...logPayload(l.names_json),names_json:undefined})),service:state[0]||null});
  }));
  app.put('/api/focus-scan/config',handler(async(req,res)=>{
    const {value,errors}=validateScan(req.body);
    if(Object.keys(errors).length)return res.status(400).json({error:'공통 크롤링 설정을 확인하세요.',errors});
    const pool=await db(),valid=new Set((await categories(pool)).map(c=>c.code));
    if(value.categories.some(c=>!valid.has(c)))return res.status(400).json({error:'지원하지 않는 카테고리입니다.',errors:{categories:'카테고리를 다시 선택하세요.'}});
    const [[old]]=await pool.query('SELECT * FROM focus_scan_config WHERE id=1');
    const prior=typeof old.categories_json==='string'?JSON.parse(old.categories_json):old.categories_json;
    const changed=JSON.stringify([...prior].sort())!==JSON.stringify([...value.categories].sort());
    const resumed=!old.enabled&&value.enabled;
    // Interval edits retain the identity boundary. Category edits/restarts baseline safely.
    await pool.query(`UPDATE focus_scan_config SET categories_json=?,interval_minutes=?,request_delay_seconds=?,enabled=?,revision=revision+?,
      next_run_at=IF(? OR interval_minutes<>?,NOW(),next_run_at),last_status=?,last_summary=? WHERE id=1`,
      [JSON.stringify(value.categories),value.interval_minutes,value.request_delay_seconds,value.enabled,changed||resumed?1:0,changed||resumed||Number(old.interval_minutes)!==value.interval_minutes,value.interval_minutes,value.enabled?'waiting':'paused',changed||resumed?'공통 기준점 등록 후 다음 주기부터 알림':'공통 크롤링 설정 저장']);
    res.json({ok:true});
  }));
  async function save(req,res) {
    const id=req.params.id == null ? null : Number(req.params.id);
    if (id!==null && (!Number.isSafeInteger(id)||id<=0)) return res.status(400).json({error:'설정 ID가 올바르지 않습니다.'});
    const {value,errors}=validateRule(req.body);
    if (Object.keys(errors).length) return res.status(400).json({error:'입력값을 확인하세요.',errors});
    const pool=await db();
    const fields=['model_contains','email','price_min_manwon','price_max_manwon','year_min','year_max','enabled'];
    const params=fields.map(f=>value[f]);
    if (id===null) {
      const [[count]]=await pool.query('SELECT COUNT(*) n FROM focus_rules');
      if(count.n>=100) return res.status(400).json({error:'집중탐색은 최대 100개까지 등록할 수 있습니다.'});
      const [result]=await pool.query(`INSERT INTO focus_rules (${fields.join(',')},categories_json,last_status)
        VALUES (${params.map(()=>'?').join(',')},JSON_ARRAY(),?)`,[...params,value.enabled?'waiting':'paused']);
      return res.status(201).json({id:result.insertId});
    }
    const [result]=await pool.query(`UPDATE focus_rules SET ${fields.map(f=>f+'=?').join(',')},
      revision=revision+1,last_status=?,last_summary='알림 조건 변경 · 공통 크롤링 기준점 유지'
      WHERE id=?`,[...params,value.enabled?'waiting':'paused',id]);
    if(!result.affectedRows) return res.status(404).json({error:'설정을 찾지 못했습니다.'});
    res.json({ok:true});
  }
  app.post('/api/focus-scan',handler(save));
  app.put('/api/focus-scan/:id',handler(save));
  app.delete('/api/focus-scan/:id',handler(async(req,res)=>{
    const id=Number(req.params.id);
    if(!Number.isSafeInteger(id)||id<=0)return res.status(400).json({error:'알림 ID가 올바르지 않습니다.'});
    const pool=await db();
    const [result]=await pool.query('DELETE FROM focus_rules WHERE id=?',[id]);
    if(!result.affectedRows)return res.status(404).json({error:'알림 조건을 찾지 못했습니다.'});
    // No cascading deletion: historical receipts and dedupe claims survive.
    res.json({ok:true});
  }));
  app.get('/api/focus-mail-history',handler(async(req,res)=>{
    const page=Math.max(1,Math.min(100000,Math.floor(Number(req.query.page)||1))),limit=50;
    const q=String(req.query.q||'').trim().slice(0,120),pool=await db();
    const pattern='%'+q.replace(/[\\%_]/g,'\\$&')+'%';
    const where="status='sent'"+(q?' AND (listing_name LIKE ? OR recipient LIKE ?)':'');
    const args=q?[pattern,pattern]:[];
    const [[count]]=await pool.query('SELECT COUNT(*) total FROM focus_mail_history WHERE '+where,args);
    const [rows]=await pool.query('SELECT id,rule_id,recipient,listing_name,price_text,manufactured_ym,detail_url,category_code,condition_json,listing_snapshot_json,sent_at FROM focus_mail_history WHERE '+where+' ORDER BY sent_at DESC,id DESC LIMIT ? OFFSET ?',[...args,limit,(page-1)*limit]);
    res.json({total:count.total,page,limit,rows:rows.map(r=>({...r,condition:typeof r.condition_json==='string'?JSON.parse(r.condition_json):r.condition_json,condition_json:undefined,listing_snapshot:mailSnapshot(r.listing_snapshot_json),listing_snapshot_json:undefined}))});
  }));
  app.patch('/api/focus-scan/:id',handler(async(req,res)=>{
    const id=Number(req.params.id);
    if(!Number.isSafeInteger(id)||id<=0||typeof req.body.enabled!=='boolean') return res.status(400).json({error:'요청을 확인하세요.'});
    const pool=await db();
    const [[rule]]=await pool.query('SELECT * FROM focus_rules WHERE id=?',[id]);
    if(!rule) return res.status(404).json({error:'설정을 찾지 못했습니다.'});
    if(Boolean(rule.enabled)!==req.body.enabled) await pool.query(`UPDATE focus_rules SET enabled=?,revision=revision+1,
      last_status=?,last_summary=? WHERE id=?`,[req.body.enabled,req.body.enabled?'waiting':'paused',req.body.enabled?'다음 공통 크롤링부터 조건 적용':'사용자가 알림을 중지함',id]);
    res.json({ok:true});
  }));
}
module.exports={registerFocusScan,validateRule,validateScan,logPayload,mailSnapshot,ensureMailSnapshotColumn};

