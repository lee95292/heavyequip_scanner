'use strict';
// Similarity is descriptive only: published ranges may represent different configurations.
const WEIGHTS={operating_weight_kg:3,engine_power_kw:2,bucket_capacity_m3:2,rated_payload_kg:3,rated_operating_capacity_kg:3,max_digging_depth_mm:2,max_reach_mm:1,overall_width_mm:1,overall_height_mm:1,overall_length_mm:1,bucket_digging_force_kn:1,blade_width_mm:2,drum_width_mm:2,travel_speed_kmh:0.5};
function family(m){const s=`${m.model_name} ${m.original_category}`.toLowerCase();if(m.category==='굴착기')return /wheel|\b[a-z]*w[-\s]?\d|zx\d+w/.test(s)?'wheeled':/long.?reach|demolition|frontless|shovel|dragline/.test(s)?'special':'crawler';if(m.category==='스키드·컴팩트 트랙 로더')return /compact track|track loader/.test(s)?'track':/skid.?steer/.test(s)?'skid':'unknown';return m.category;}
function comparable(values,key){return (values||[]).filter(v=>Number.isFinite(v.min)&&Number.isFinite(v.max)&&v.min>0&&v.max>=v.min&&v.max/v.min<=2).map(v=>({...v,mid:(v.min+v.max)/2}));}
function rankSimilar(base,models,facets,limit=6){
 if(base.is_assembly||base.record_kind!=='individual_model'||/기타|구성품/.test(base.category))return [];
 const candidates=[];
 for(const m of models){if(m.id===base.id||m.is_assembly||m.record_kind!=='individual_model'||m.category!==base.category||family(m)!==family(base)||m.model_name===base.model_name&&m.manufacturer===base.manufacturer)continue;
 const comparisons=[];
 for(const [key,weight] of Object.entries(WEIGHTS)){
  const a=comparable(base.facets[key],key),b=comparable(m.facets[key],key);if(!a.length||!b.length)continue;
  // Use median of unique alternatives, not whichever configuration happens to be closest.
  let types=key==='engine_power_kw'?['net','gross','rated','unspecified'].filter(t=>a.some(x=>x.power_type===t)&&b.some(x=>x.power_type===t)):[null];if(!types.length)continue;
  const type=types[0],pick=xs=>{const v=xs.filter(x=>!type||x.power_type===type).sort((x,y)=>x.mid-y.mid);return v[Math.floor(v.length/2)];};const av=pick(a),bv=pick(b);const delta=Math.abs(Math.log(bv.mid/av.mid));
  comparisons.push({key,label:facets[key]?.label||key,unit:facets[key]?.unit||'',base:{min:av.min,max:av.max},candidate:{min:bv.min,max:bv.max},difference_percent:Math.round((bv.mid/av.mid-1)*1000)/10,power_type:type,weight,distance:delta});
 }
 if(comparisons.length<2||!comparisons.some(c=>['operating_weight_kg','rated_payload_kg','rated_operating_capacity_kg','engine_power_kw'].includes(c.key)))continue;
 if(comparisons.some(c=>c.key==='operating_weight_kg'&&c.distance>Math.log(1.8)))continue;
 const distance=comparisons.reduce((s,c)=>s+c.distance*c.weight,0)/comparisons.reduce((s,c)=>s+c.weight,0);if(distance>Math.log(1.65))continue;
 const coverage=Math.min(1,comparisons.length/4),score=Math.round(100*Math.exp(-2*distance)*(0.7+0.3*coverage));
 candidates.push({id:m.id,model_name:m.model_name,manufacturer:m.manufacturer,category:m.category,score,compared_count:comparisons.length,comparisons:comparisons.map(({weight,distance,...c})=>c)});
 }
 return candidates.sort((a,b)=>b.score-a.score||b.compared_count-a.compared_count||a.id.localeCompare(b.id)).slice(0,limit);
}
module.exports={rankSimilar,family};
