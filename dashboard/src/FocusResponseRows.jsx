import React from 'react';

const display=value=>(typeof value==='string'||(typeof value==='number'&&Number.isFinite(value)))&&String(value)!==''?String(value):'—';

export default function FocusResponseRows({rows,legacyNames}) {
  const values=Array.isArray(rows)?rows.filter(row=>row&&typeof row==='object'&&!Array.isArray(row)):[];
  const names=Array.isArray(legacyNames)?legacyNames.filter(name=>typeof name==='string').slice(0,5):[];
  if(values.length) return <details><summary>모델명 · 연식 · 가격 보기 ({values.length}건)</summary>
    <ul>{values.map((row,i)=><li key={i}>모델명: {display(row.model_name)} · 연식(원문): {display(row.manufactured_ym)} · 가격(원문): {display(row.price)}</li>)}</ul>
  </details>;
  if(names.length) return <details><summary>이전 기록: 매물 이름 예시 ({names.length}개)</summary><ul>{names.map((name,i)=><li key={i}>{name}</li>)}</ul></details>;
  return null;
}
