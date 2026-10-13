import test from 'node:test';
import assert from 'node:assert/strict';
import {safeLink, approvedInquiry, inquiryUrl, selectCandidates, assertCatalog} from '../docs/beta/model.mjs';
const record=(id,price='10')=>({id,synthetic:false,version:'1',name:id,tasks:['extract'],price:{amount:price,currency:'USD',basis:'task'},evidence_summary:{label:'SELF_REPORTED',missing:[]},publication:{reviewed:true},inquiry:{accepts_inquiries:true,url:'https://github.com/terryncew/openline-bureau/issues/new'}});
const catalog=(capabilities,evaluations=[])=>({format:'openline.catalog.v1',synthetic:false,policy:{inquiries_enabled:true},capabilities,evaluations,workers:[]});
const criteria={task:'extract',budget:'15',currency:'USD',basis:'task',minEvaluations:1};
const evaluation=(id,method='frozen fixtures')=>({capability_id:id,capability_version:'1',task:'extract',method,environment:'python 3.12',sample:{total:4,passed:3,failed:1},independence:'SEPARATE_REVIEWED_CONTRIBUTOR',outcome_verification:'MAINTAINER_REPRODUCED'});
test('URL policy rejects credential, scheme, private host and redirect-ish inquiry paths',()=>{
 for(const value of ['javascript:alert(1)','http://github.com/a/b','https://user:password@github.com/a/b','https://127.0.0.1/a','https://github.com.evil.test/a'])assert.equal(safeLink(value),null);
 const c=record('real');assert.equal(approvedInquiry(c,false),c.inquiry.url);
 for(const url of ['https://github.com/evil/repo/issues/new','https://github.com/terryncew/openline-bureau/issues/new?body=forged','https://github.com/terryncew/openline-bureau/issues/new#payload','https://github.com/terryncew/openline-bureau/issues/1'])assert.equal(approvedInquiry({...c,inquiry:{accepts_inquiries:true,url}},false),null);
 assert.equal(approvedInquiry(c,true),null);assert.equal(approvedInquiry({...c,publication:{reviewed:false}},false),null);assert.equal(approvedInquiry({...c,inquiry:{url:c.inquiry.url}},false),null);
});
test('inquiry URL preserves literal public draft without code interpolation',()=>{const body='Generic & scoped task\n<script>alert("x")</script>';const url=new URL(inquiryUrl(record('real').inquiry.url,'Task #1',body));assert.equal(url.searchParams.get('body'),body);assert.equal(url.searchParams.get('title'),'Task #1');});
test('catalog display fails closed mislabeled synthetic records and unreviewed records',()=>{assert.equal(assertCatalog(catalog([]),false).capabilities.length,0);assert.throws(()=>assertCatalog({...catalog([]),synthetic:true},false));assert.throws(()=>assertCatalog(catalog([{...record('a'),publication:{reviewed:false}}]),false));assert.throws(()=>assertCatalog(catalog([{...record('a'),evidence_summary:{label:'SYNTHETIC',missing:[]}}]),false));});
test('cheapest baseline respects exact task currency pricing unit budget',()=>{
 const cheap=record('cheap','5'),supported=record('supported','12'),over=record('over','50'),different={...record('other','1'),price:{amount:'1',currency:'EUR',basis:'task'}};
 const result=selectCandidates(catalog([cheap,supported,over,different],[evaluation('supported')]),criteria);
 assert.equal(result.baseline.id,'cheap');assert.deepEqual(result.eligible.map(c=>c.id),['supported']);assert.equal(result.recommendation,null);
});
test('missing or incompatible reproduced evidence abstains instead of merging scores',()=>{
 const a=record('a'),b=record('b','12');const incomplete=selectCandidates(catalog([a],[{...evaluation('a'),outcome_verification:'EVALUATOR_REPORTED'}]),criteria);assert.match(incomplete.abstention,/maintainer-reproduced/);
 const incompatible=selectCandidates(catalog([a,b],[evaluation('a'),evaluation('b','different benchmark')]),criteria);assert.match(incompatible.abstention,/methods.*differ/);
 assert.match(selectCandidates(catalog([a],[evaluation('a')]),{...criteria,basis:''}).abstention,/pricing unit/);
 assert.match(selectCandidates({...catalog([a],[evaluation('a')]),synthetic:true},criteria).abstention,/synthetic/);
});

test('same sample size with different dataset or selection remains incomparable',()=>{
 const a=record('a'),b=record('b','12');
 for(const field of ['dataset','selection']){
  const first={...evaluation('a'),sample:{...evaluation('a').sample,dataset:'frozen A',selection:'preregistered'}};
  const second={...evaluation('b'),sample:{...evaluation('b').sample,dataset:'frozen A',selection:'preregistered',[field]:'different'}};
  assert.match(selectCandidates(catalog([a,b],[first,second]),criteria).abstention,/differ/);
 }
});
test('worker execution reports never substitute for capability evaluations',()=>{
 const a=record('a');
 const workerEval={...evaluation('a'),scope:'WORKER_EXECUTION',worker_id:'worker-a'};
 const result=selectCandidates(catalog([a],[workerEval]),criteria);
 assert.equal(result.eligible.length,0);assert.match(result.abstention,/independent evaluation requirement/);
});

test('equal offered prices use deterministic ordinal id and version tie breaks',()=>{
 const punctuation=selectCandidates(catalog([record('alpha_a'),record('alpha-a')]),{...criteria,minEvaluations:0});
 assert.equal(punctuation.baseline.id,'alpha-a');
 const versions=selectCandidates(catalog([{...record('same'),version:'1.1.0'},{...record('same'),version:'1.0.0'}]),{...criteria,minEvaluations:0});
 assert.equal(versions.baseline.version,'1.0.0');
});
