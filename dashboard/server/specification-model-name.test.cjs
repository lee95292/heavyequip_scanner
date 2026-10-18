const test=require('node:test');const assert=require('node:assert/strict');
const {displayModelName,modelSearchText}=require('./specification-model-name.cjs');
const {matchModel,parseQuery}=require('./specifications.cjs');
test('CAT numeric display preserves original identity and other makers',()=>{
 for(const name of ['265','320 GC','301.5','966H']){const m={manufacturer:'Caterpillar',model_name:name};assert.equal(displayModelName(m),'CAT'+name);assert.equal(m.model_name,name);}
 for(const name of ['D6H','D9N','CAT265'])assert.equal(displayModelName({manufacturer:'Caterpillar',model_name:name}),name);
 assert.equal(displayModelName({manufacturer:'Bobcat',model_name:'265'}),'265');
});
test('raw, spaced and compact CAT aliases match the same source model',()=>{
 const m={manufacturer:'Caterpillar',model_name:'265',facets:{}};
 for(const q of ['265','CAT265','CAT 265','캐터필러 265'])assert.ok(matchModel(m,parseQuery({q})));
 assert.ok(!matchModel({...m,manufacturer:'Bobcat'},parseQuery({q:'CAT265'})));
});
