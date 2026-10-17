import React from 'react';

const contactState={
  missing:'매물 상세페이지에 연락처가 없습니다',
  fetch_failed:'상세 조회 실패로 연락처를 확인하지 못했습니다',
  unavailable:'연락처를 확인할 수 없습니다',
  not_collected:'연락처를 수집하지 않았습니다',
};
const fields=[['model_name','모델명'],['manufacturer','제작사'],['price','가격'],['manufactured_ym','제작년월'],['location','위치'],['seller','판매자'],['status','상태'],['category_name','분류'],['category_code','분류 코드'],['posted_at','매물 등록일']];
const text=value=>typeof value==='string'&&value.trim()?value:null;

export default function MailListingSnapshot({snapshot}){
  if(!snapshot||typeof snapshot!=='object'||Array.isArray(snapshot)||snapshot.version!==1){
    return <p>이전 기록: 상세정보·연락처 스냅샷이 없습니다</p>;
  }
  return <div className="mail-listing-snapshot">
    <p><strong>연락처:</strong> {text(snapshot.contact)||(Object.hasOwn(contactState,snapshot.contact_status)?contactState[snapshot.contact_status]:contactState.unavailable)}</p>
    <details><summary>발송 당시 매물 주요정보</summary>
      <p>수집 시각: {text(snapshot.captured_at)||'정보 없음'} · 원문에 있던 정보를 보관한 기록입니다</p>
      <dl>{fields.map(([key,label])=><React.Fragment key={key}><dt>{label}</dt><dd>{text(snapshot[key])||'정보 없음'}</dd></React.Fragment>)}</dl>
      {text(snapshot.description)&&<p className="mail-listing-description">{snapshot.description}</p>}
    </details>
  </div>;
}
