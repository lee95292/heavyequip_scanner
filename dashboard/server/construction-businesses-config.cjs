'use strict';
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
function serviceKey() {
  if(process.env.DATA_GO_KR_SERVICE_KEY) return process.env.DATA_GO_KR_SERVICE_KEY.trim();
  const file=process.env.DATA_GO_KR_KEY_FILE || path.join(os.homedir(),'.config/heavyequip-public-api/service-key');
  try {return fs.readFileSync(file,'utf8').trim();}
  catch(error) {if(error.code==='ENOENT')return '';throw new Error('service_key_file_unreadable');}
}
function createPool() {
  const mysql=require('mysql2/promise');
  const raw=JSON.parse(fs.readFileSync(process.env.CRAWL_CONFIG_PATH||path.resolve(__dirname,'../../crawl/config.json'),'utf8'));
  const s=raw.mysql||raw;
  return mysql.createPool({host:s.host,port:s.port||3306,user:s.user,password:s.password,database:s.database,charset:'utf8mb4',connectionLimit:3,connectTimeout:10000});
}
module.exports={serviceKey,createPool};
