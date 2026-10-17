const fs = require('node:fs');
const path = require('node:path');
const mysql = require('mysql2/promise');
const {migrate,sync} = require('./construction-businesses.cjs');
async function main() {
  if(process.argv.includes('--key-stdin')) process.env.DATA_GO_KR_SERVICE_KEY=fs.readFileSync(0,'utf8').trim();
  const raw = JSON.parse(fs.readFileSync(process.env.CRAWL_CONFIG_PATH || path.resolve(__dirname,'../../crawl/config.json'),'utf8'));
  const s = raw.mysql || raw;
  const db = mysql.createPool({host:s.host,port:s.port||3306,user:s.user,password:s.password,database:s.database,charset:'utf8mb4',connectionLimit:2});
  try {
    await migrate(db);
    if (process.argv.includes('--sync')) await sync(db,{restart:process.argv.includes('--restart')});
    const [[state]] = await db.query('SELECT * FROM construction_business_sync WHERE id=1');
    const [[counts]] = await db.query('SELECT COUNT(*) AS saved FROM construction_businesses');
    console.log(JSON.stringify({state,...counts}));
  } finally {await db.end();}
}
main().catch(error=>{console.error(error.code || error.message);process.exitCode=1;});
