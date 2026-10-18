'use strict';
function displayModelName(m) {
 const name=String(m.model_name||'');
 return m.manufacturer==='Caterpillar' && /^\d/.test(name) ? 'CAT'+name : name;
}
function modelSearchText(m) {
 const name=String(m.model_name||'');
 const aliases=m.manufacturer==='Caterpillar' ? `CAT${name} CAT ${name} 캐터필러 ${name}` : '';
 return `${m.manufacturer} ${name} ${m.base_model||''} ${aliases}`.toLocaleLowerCase();
}
module.exports={displayModelName,modelSearchText};
