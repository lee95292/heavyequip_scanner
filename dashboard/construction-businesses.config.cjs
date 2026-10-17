const path=require('node:path');
module.exports={apps:[{name:'heavyequip-public-business-weekly',cwd:path.resolve(__dirname,'..'),
  script:'dashboard/server/construction-businesses-weekly.cjs',instances:1,autorestart:true,
  restart_delay:10000,kill_timeout:45000,max_memory_restart:'256M',time:true,
  env:{TZ:'Asia/Seoul',NODE_ENV:'production'}}]};
