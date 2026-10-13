// Pure, local catalog operations; no code execution, network fetch, score, or payment.
export const APPROVED_CONTACT_REPOSITORIES = Object.freeze(['terryncew/openline-bureau']);
const ordinal = (a,b) => a < b ? -1 : a > b ? 1 : 0;
const LINK_HOSTS = new Set(['github.com', 'raw.githubusercontent.com', 'terryncew.github.io']);
export function safeLink(value) {
  if (typeof value !== 'string' || value.length > 2048) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.port || !LINK_HOSTS.has(url.hostname)) return null;
    return url.href;
  } catch { return null; }
}
export function approvedInquiry(capability, synthetic) {
  if (synthetic || capability.synthetic !== false || capability.publication?.reviewed !== true || capability.inquiry?.accepts_inquiries !== true) return null;
  const safe = safeLink(capability.inquiry.url);
  if (!safe) return null;
  const url = new URL(safe);
  if (url.hostname !== 'github.com' || url.search || url.hash) return null;
  const approved = APPROVED_CONTACT_REPOSITORIES.some(repo => url.pathname === `/${repo}/issues/new`);
  return approved ? url.href : null;
}
export function inquiryUrl(base, title, body) {
  const url = new URL(base);
  url.search = new URLSearchParams({title: String(title).slice(0, 180), body: String(body).slice(0, 5000)}).toString();
  return url.href;
}
export function evaluationsFor(catalog, capability, task = null, includeWorker = false) {
  return (catalog.evaluations || []).filter(item => item.capability_id === capability.id && item.capability_version === capability.version && (!task || item.task === task) && (includeWorker || (item.scope !== 'WORKER_EXECUTION' && !item.worker_id)));
}
export function priceLabel(price) {
  return price ? `${price.amount} ${price.currency} / ${price.basis}` : 'Price not offered';
}
export function selectCandidates(catalog, criteria) {
  const minEvaluations = Math.max(0, Number(criteria.minEvaluations ?? 1));
  const budget = criteria.budget === '' || criteria.budget === null || criteria.budget === undefined ? null : Number(criteria.budget);
  const taskMatches = catalog.capabilities.filter(c => c.tasks.includes(criteria.task));
  if (!criteria.task) return {baseline:null, eligible:[], recommendation:null, abstention:'Choose one documented task. Select does not generalize evidence to other tasks.'};
  if (!criteria.basis) return {baseline:null, eligible:[], recommendation:null, abstention:'Choose one pricing unit so offered prices can be compared fairly.'};
  const offered = taskMatches.filter(c => c.price && c.price.currency === criteria.currency && c.price.basis === criteria.basis && Number.isFinite(Number(c.price.amount)) && Number(c.price.amount) >= 0 && (budget === null || (Number.isFinite(budget) && Number(c.price.amount) <= budget))).sort((a,b) => Number(a.price.amount)-Number(b.price.amount) || ordinal(a.id,b.id) || ordinal(a.version,b.version));
  const baseline = offered[0] || null;
  const eligible = offered.filter(c => evaluationsFor(catalog,c,criteria.task).filter(e => e.independence === 'SEPARATE_REVIEWED_CONTRIBUTOR').length >= minEvaluations);
  if (!baseline) return {baseline,eligible,recommendation:null,abstention:'No offered price matches this task, currency, pricing unit and budget. Unpriced capabilities can still be explored in the catalog.'};
  if (!eligible.length) return {baseline,eligible,recommendation:null,abstention:'No candidate meets the independent evaluation requirement for this exact task. The cheapest offer alone is not an evidence recommendation.'};
  const reproduced = eligible.map(c => ({capability:c,evaluations:evaluationsFor(catalog,c,criteria.task).filter(e => e.independence === 'SEPARATE_REVIEWED_CONTRIBUTOR' && e.outcome_verification === 'MAINTAINER_REPRODUCED')}));
  if (reproduced.some(row => !row.evaluations.length) || catalog.synthetic) return {baseline,eligible,recommendation:null,abstention:catalog.synthetic?'These are synthetic examples. No real outcome or economic benefit has been demonstrated.':'Abstaining: each shortlisted candidate needs maintainer-reproduced evidence for this exact task before an evidence recommendation is supportable.'};
  const conditions = new Set(reproduced.flatMap(row => row.evaluations.map(e => JSON.stringify([e.task,e.method,e.environment,e.sample?.total,e.sample?.dataset,e.sample?.selection]))));
  if (conditions.size !== 1) return {baseline,eligible,recommendation:null,abstention:'Abstaining: evaluation methods, environments, datasets, sampling or sample sizes differ. Inspect the evidence without combining incompatible results.'};
  // Select never ranks outcomes using a universal score; comparable evidence is a shortlist for human review.
  return {baseline,eligible,recommendation:null,abstention:'Comparable reproduced evidence is available for human review. Select does not infer future outcomes or automatically authorize a purchase.'};
}
export function assertCatalog(catalog, expectedSynthetic) {
  if (!catalog || catalog.format !== 'openline.catalog.v1' || catalog.synthetic !== expectedSynthetic || !Array.isArray(catalog.capabilities) || !Array.isArray(catalog.workers) || !Array.isArray(catalog.evaluations)) throw new Error('Unsupported or mislabeled catalog. No records were displayed.');
  if ([catalog.capabilities,catalog.workers,catalog.evaluations].some(rows => rows.length > 500)) throw new Error('Catalog exceeds this beta’s display limit.');
  for (const rows of [catalog.capabilities, catalog.workers, catalog.evaluations]) for (const row of rows) {
    if (row.publication?.reviewed !== true) throw new Error('Catalog contains an unreviewed record.');
    if (row.synthetic !== expectedSynthetic) throw new Error('Catalog record crosses the synthetic boundary.');
  }
  for (const c of catalog.capabilities) {
    if (typeof c.id !== 'string' || typeof c.version !== 'string' || typeof c.name !== 'string' || !Array.isArray(c.tasks) || !c.evidence_summary || !Array.isArray(c.evidence_summary.missing) || c.publication?.reviewed !== true) throw new Error('Catalog records are not reviewed compiled records.');
    if (!expectedSynthetic && c.evidence_summary.label === 'SYNTHETIC') throw new Error('Synthetic records cannot appear in the reviewed public catalog.');
  }
  if (!expectedSynthetic && catalog.policy?.inquiries_enabled !== true && [...catalog.capabilities, ...catalog.workers].some(row => row.inquiry?.accepts_inquiries === true)) throw new Error('Catalog inquiry policy is disabled.');
  return catalog;
}
