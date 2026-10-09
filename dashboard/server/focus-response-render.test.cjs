const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const {createRequire}=require('node:module'),React=require('react'),{renderToStaticMarkup}=require('react-dom/server'),{transformSync}=require('esbuild');
const file=path.resolve(__dirname,'../src/FocusResponseRows.jsx');
const compiled=transformSync(fs.readFileSync(file,'utf8'),{loader:'jsx',jsx:'automatic',format:'cjs'}).code;
const context={exports:{}};vm.runInNewContext(compiled,{module:context,exports:context.exports,require:createRequire(file)});
const Rows=context.exports.default,render=props=>renderToStaticMarkup(React.createElement(Rows,props));
test('all response rows render with source units and escaped text',()=>{
 const rows=Array.from({length:9},(_,i)=>({model_name:'장비'+i,manufactured_ym:'20.05',price:'3,000만원'}));
 rows[0].model_name='<script>unsafe</script>';
 const html=render({rows});assert.match(html,/9건/);assert.match(html,/장비8/);assert.match(html,/연식\(원문\): 20.05/);assert.match(html,/3,000만원/);
 assert.match(html,/&lt;script&gt;/);assert.ok(!html.includes('<script>'));
});
test('legacy names render separately',()=>{const html=render({legacyNames:['DX','EW']});assert.match(html,/이전 기록/);assert.match(html,/DX/);assert.ok(!html.includes('연식'));});
test('empty malformed and nullable payloads render safely',()=>{
 for(const rows of [null,{},'bad',[],[null,[],true]]) assert.equal(render({rows}),'');
 const html=render({rows:[{model_name:{},manufactured_ym:null,price:0}]});assert.match(html,/모델명: —/);assert.match(html,/가격\(원문\): 0/);
});
