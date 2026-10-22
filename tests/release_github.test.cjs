const {test} = require('node:test');
const assert = require('node:assert/strict');
const {createDraft, publishDraft} = require('../scripts/release_github.cjs');

function fixture(overrides = {}) {
  Object.assign(process.env, {RELEASE_TAG:'v1.0.0', RELEASE_SHA:'abc123', RELEASE_ID:'123', RELEASE_PRERELEASE:'false'});
  const writes = [];
  const release = {id:123, tag_name:'v1.0.0', draft:true, body:'<!-- release-sha: abc123 -->', ...overrides};
  const repositories = {
    getReleaseByTag: async()=>({data:release}), getRelease: async()=>({data:release}),
    createRelease: async args=>{writes.push(args); return {data:release};},
    updateRelease: async args=>{writes.push(args);}, listReleaseAssets: ()=>{},
  };
  return {writes, github:{rest:{git:{getRef:async()=>({data:{object:{type:'commit',sha:'abc123'}}})}, repos:repositories},
    paginate:async()=>[{name:'latest.json',size:100},{name:'SHA256SUMS',size:200}]},
    context:{repo:{owner:'owner',repo:'repo'}}, core:{setOutput:()=>{}}};
}

test('published release cannot be overwritten', async()=>{
  const f=fixture({draft:false});
  await assert.rejects(createDraft(f),/already published/);
  assert.equal(f.writes.length,0);
});
test('a moved tag cannot be published', async()=>{
  const f=fixture();
  f.github.rest.git.getRef=async()=>({data:{object:{type:'commit',sha:'changed'}}});
  await assert.rejects(publishDraft(f),/tag moved/);
  assert.equal(f.writes.length,0);
});
test('missing manifest keeps the release a draft', async()=>{
  const f=fixture(); f.github.paginate=async()=>[{name:'SHA256SUMS',size:200}];
  await assert.rejects(publishDraft(f),/manifest is missing/);
  assert.equal(f.writes.length,0);
});
test('missing SHA256SUMS keeps the release a draft', async()=>{
  const f=fixture(); f.github.paginate=async()=>[{name:'latest.json',size:100}];
  await assert.rejects(publishDraft(f),/checksums file is missing/);
  assert.equal(f.writes.length,0);
});
test('draft for another commit is rejected', async()=>{
  const f=fixture({body:'<!-- release-sha: changed -->'});
  await assert.rejects(createDraft(f),/different commit/);
  assert.equal(f.writes.length,0);
});
test('verified stable release is published with latest-version policy', async()=>{
  const f=fixture(); await publishDraft(f);
  assert.equal(f.writes.length,1);
  assert.equal(f.writes[0].draft,false);
  assert.equal(f.writes[0].make_latest,'legacy');
});
test('new drafts are created for the exact validated commit', async()=>{
  const f=fixture(); f.github.rest.repos.getReleaseByTag=async()=>{throw Object.assign(new Error('not found'),{status:404});};
  await createDraft(f);
  assert.equal(f.writes[0].target_commitish,'abc123');
  assert.equal(f.writes[0].draft,true);
});
