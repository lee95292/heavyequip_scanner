'use strict';
const crypto = require('node:crypto');
const {serviceKey:readServiceKey}=require('./construction-businesses-config.cjs');
const ENDPOINT = 'https://api.data.go.kr/openapi/tn_pubr_public_construction_equipment_operator_api';
const FIELDS = {
  name: 'BPLC_NM', road_address: 'LCTN_ROAD_NM_ADDR', lot_address: 'LCTN_LOTNO_ADDR',
  latitude: 'LAT', longitude: 'LOT', phone: 'RPRS_TELNO', business_type: 'BIZ_KND_NM',
  registration_type: 'REG_KND_SE_NM', registration_number: 'REG_NO', registered_date: 'REG_YMD',
  agency: 'MNG_INST_NM', agency_phone: 'MNG_INST_TELNO', reference_date: 'DATA_CRTR_YMD',
  provider_code: 'instt_code', provider: 'instt_nm'
};
const compact = value => String(value || '').replace(/_/g, '').toLowerCase();
function normalize(raw) {
  const source = Object.fromEntries(Object.entries(raw).map(([k,v]) => [compact(k),v]));
  const row = Object.fromEntries(Object.entries(FIELDS).map(([k,v]) => [k, String(source[compact(v)] ?? '').trim()]));
  if (!row.name) throw new Error('invalid_record_missing_business_name');
  const identity = row.registration_number
    ? [row.provider_code || row.provider || row.agency, row.business_type, row.registration_number]
    : [row.provider_code || row.provider || row.agency, row.name, row.business_type, row.registration_type, row.road_address || row.lot_address, row.registered_date];
  row.id = crypto.createHash('sha256').update(JSON.stringify(identity)).digest('hex');
  row.region = (row.road_address || row.lot_address).split(/\s+/)[0] || '';
  row.raw_json = JSON.stringify(raw);
  return row;
}
function parseResponse(payload) {
  if (payload.OpenAPI_ServiceResponse) throw new Error('upstream_auth_or_quota_error');
  const response = payload.response || payload;
  if (!response || !['00', '0'].includes(String(response.header?.resultCode))) throw new Error('upstream_api_error');
  const body = response.body;
  const total = Number(body?.totalCount);
  if (!Number.isSafeInteger(total) || total < 0) throw new Error('invalid_total_count');
  let items = body.items?.item ?? body.items;
  if (items === '' || items == null) items = [];
  if (!Array.isArray(items) && typeof items === 'object') items = [items];
  if (!Array.isArray(items) || items.some(x => !x || typeof x !== 'object')) throw new Error('invalid_items');
  return { total, items };
}
async function migrate(db) {
  const textColumns = Object.keys(FIELDS).map(k => `\`${k}\` TEXT NOT NULL`).join(',');
  await db.query(`CREATE TABLE IF NOT EXISTS construction_businesses (
    id CHAR(64) PRIMARY KEY, ${textColumns}, region VARCHAR(100) NOT NULL,
    raw_json JSON NOT NULL, collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX business_region(region), INDEX business_type_idx(business_type(100)),
    INDEX business_name_idx(name(100))) CHARACTER SET utf8mb4`);
  await db.query(`CREATE TABLE IF NOT EXISTS construction_business_sync (
    id INT PRIMARY KEY, status VARCHAR(20) NOT NULL, next_page INT NOT NULL DEFAULT 1,
    processed INT NOT NULL DEFAULT 0, total INT NULL, error VARCHAR(200) NULL,
    started_at DATETIME NULL, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL)`);
  await db.query("INSERT IGNORE INTO construction_business_sync(id,status,next_page) VALUES(1,'not_started',1)");
  await db.query(`CREATE TABLE IF NOT EXISTS construction_business_pages (
    page INT PRIMARY KEY, content_hash CHAR(64) NOT NULL, raw_json JSON NOT NULL,
    collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)`);
}
async function sync(db, { restart = false, serviceKey = readServiceKey(), fetcher = fetch, onStarted = async()=>{} } = {}) {
  if (!serviceKey) throw new Error('service_key_required');
  const connection = await db.getConnection();
  let locked = false;
  try {
    const [locks] = await connection.query("SELECT GET_LOCK('scan_construction_business_sync',0) AS acquired");
    if (!locks[0].acquired) throw new Error('sync_already_running');
    locked = true;
    const [[state]] = await connection.query('SELECT * FROM construction_business_sync WHERE id=1');
    if (state.status === 'complete' && !restart) return;
    if (restart) await connection.query("UPDATE construction_business_sync SET next_page=1,processed=0,total=NULL,completed_at=NULL,started_at=NOW() WHERE id=1");
    await connection.query("UPDATE construction_business_sync SET status='running',error=NULL,started_at=COALESCE(started_at,NOW()),updated_at=NOW() WHERE id=1");
    await onStarted();
    let page = restart ? 1 : Math.max(1,state.next_page);
    let processed = restart ? 0 : state.processed;
    let expectedTotal = restart ? null : state.total;
    while (true) {
      const url = new URL(ENDPOINT);
      let decoded = serviceKey;
      try { decoded = decodeURIComponent(serviceKey); } catch (_) { /* plain key */ }
      url.search = new URLSearchParams({serviceKey: decoded, pageNo:String(page),numOfRows:'1000',type:'json'});
      let response;
      try { response = await fetcher(url, {signal: AbortSignal.timeout(30000)}); }
      catch (_) { throw new Error('upstream_connection_failed'); }
      if (!response.ok) throw new Error(`upstream_http_${response.status}`);
      let payload;
      try { payload = await response.json(); } catch (_) { throw new Error('upstream_non_json_response'); }
      const {total, items} = parseResponse(payload);
      if (expectedTotal !== null && total !== expectedTotal) throw new Error('upstream_total_changed_restart_required');
      expectedTotal = total;
      if (!items.length && processed < total) throw new Error('unexpected_empty_page');
      if (processed + items.length > total) throw new Error('upstream_count_mismatch');
      const rows = items.map(normalize);
      const pageHash = crypto.createHash('sha256').update(JSON.stringify(items)).digest('hex');
      if (page > 1) {
        const [[previous]] = await connection.query('SELECT content_hash FROM construction_business_pages WHERE page=?',[page-1]);
        if (previous?.content_hash===pageHash && items.length) throw new Error('upstream_repeated_page');
      }
      await connection.beginTransaction();
      try {
        for (const row of rows) {
          const columns = Object.keys(row);
          await connection.query(`INSERT INTO construction_businesses (${columns.map(k=>`\`${k}\``).join(',')}) VALUES (${columns.map(()=>'?').join(',')})
            ON DUPLICATE KEY UPDATE ${columns.filter(k=>k!=='id').map(k=>`\`${k}\`=VALUES(\`${k}\`)`).join(',')},collected_at=NOW()`, Object.values(row));
        }
        processed += items.length;
        await connection.query('INSERT INTO construction_business_pages(page,content_hash,raw_json) VALUES(?,?,?) ON DUPLICATE KEY UPDATE content_hash=VALUES(content_hash),raw_json=VALUES(raw_json),collected_at=NOW()', [page,pageHash,JSON.stringify(payload)]);
        const complete = processed >= total;
        await connection.query(`UPDATE construction_business_sync SET status=?,next_page=?,processed=?,total=?,updated_at=NOW(),completed_at=IF(?,NOW(),NULL) WHERE id=1`,
          [complete ? 'complete' : 'running', page+1, processed, total, complete]);
        await connection.commit();
        if (complete) break;
      } catch (error) { await connection.rollback(); throw error; }
      page++;
      await new Promise(resolve => setTimeout(resolve, 250));
    }
  } catch (error) {
    if (locked) await connection.query("UPDATE construction_business_sync SET status='failed',error=?,updated_at=NOW() WHERE id=1", [/^[a-z_0-9]+$/i.test(error.message) ? error.message.slice(0,200) : 'database_write_failed']);
    throw error;
  } finally {
    if (locked) await connection.query("SELECT RELEASE_LOCK('scan_construction_business_sync')");
    connection.release();
  }
}
function filters(query) {
  const clauses = [], values = [];
  for (const key of ['region','business_type','registration_type']) {
    if (query[key]) {clauses.push(`\`${key}\`=?`); values.push(String(query[key]).slice(0,200));}
  }
  if (query.q) {
    const q = '%' + String(query.q).slice(0,100).replace(/[!%_]/g, c=>'!'+c) + '%';
    clauses.push("(name LIKE ? ESCAPE '!' OR road_address LIKE ? ESCAPE '!' OR lot_address LIKE ? ESCAPE '!' OR registration_number LIKE ? ESCAPE '!')");
    values.push(q,q,q,q);
  }
  return {where: clauses.length ? ' WHERE '+clauses.join(' AND ') : '',values};
}
function registerConstructionBusinesses(app, getPool) {
  let active = false;
  app.get('/api/construction-businesses', async (req,res) => {
    try {
      const db = getPool();
      const page = Math.max(1, Math.min(100000, parseInt(req.query.page,10)||1));
      const {where,values} = filters(req.query);
      const [[{total}]] = await db.query(`SELECT COUNT(*) AS total FROM construction_businesses${where}`,values);
      const [items] = await db.query(`SELECT id,${Object.keys(FIELDS).map(k=>`\`${k}\``).join(',')},region,collected_at FROM construction_businesses${where} ORDER BY name,id LIMIT 50 OFFSET ?`,[...values,(page-1)*50]);
      const options = {};
      for (const key of ['region','business_type','registration_type']) {
        const [rows] = await db.query(`SELECT DISTINCT \`${key}\` AS value FROM construction_businesses WHERE \`${key}\`<>'' ORDER BY \`${key}\``);
        options[key] = rows.map(r=>r.value);
      }
      const [[state]] = await db.query('SELECT * FROM construction_business_sync WHERE id=1');
      if (state?.status==='running') {
        const [[lock]] = await db.query("SELECT IS_USED_LOCK('scan_construction_business_sync') AS owner");
        if (!lock.owner) {state.status='failed';state.error='sync_interrupted_resume_available';}
      }
      res.setHeader('Cache-Control','no-store');
      let schedule=null;
      try {
        const [[weekly]]=await db.query('SELECT * FROM construction_business_schedule WHERE id=1');
        if(weekly){const {plan}=require('./construction-businesses-weekly.cjs');const next=plan(weekly);schedule={label:'매주 월요일 오전 5시 (한국시간)',nextRunAt:new Date(next.due?Date.now():next.next).toISOString(),lastSuccessAt:weekly.last_success_at?new Date(Number(weekly.last_success_at)).toISOString():null,healthy:Date.now()-Number(weekly.heartbeat_at)<180000,error:weekly.error};}
      }catch(error){if(error.code!=='ER_NO_SUCH_TABLE')throw error;}
      res.json({items,total:Number(total),page,pageSize:50,options,sync:state,schedule,serviceKeyConfigured:Boolean(readServiceKey())});
    } catch (error) {
      res.status(503).json({error:error.code==='ER_NO_SUCH_TABLE' ? '사업자 DB 초기화가 필요합니다.' : '사업자 데이터 조회에 실패했습니다.'});
    }
  });
  app.post('/api/construction-businesses/sync', async(req,res) => {
    if (!readServiceKey()) return res.status(422).json({error:'서버에 공공 API 인증키 설정이 필요합니다.'});
    if (active) return res.status(409).json({error:'수집이 진행 중입니다.'});
    active = true;
    sync(getPool(), {restart:req.body?.restart===true}).catch(()=>{}).finally(()=>{active=false;});
    res.status(202).json({status:'accepted'});
  });
}
module.exports = {ENDPOINT,FIELDS,normalize,parseResponse,migrate,sync,filters,registerConstructionBusinesses};
