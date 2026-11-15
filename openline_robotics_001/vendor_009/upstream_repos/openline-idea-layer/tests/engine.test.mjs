import {test} from 'node:test';
import assert from 'node:assert/strict';
import {generate,brief,sectors,audiences,formats} from '../engine.mjs';

test('all catalog combinations render with bounded, complete output',()=>{
 let count=0;
 for(let sector=0;sector<sectors.length;sector++)for(const audience of audiences)for(const format of formats){
  const x=generate({sector,audience,format});
  const b=brief(x);
  assert.ok(x.offer&&x.firstTest&&x.risk&&x.stopRule&&x.formatPackaging);
  assert.match(b,/No paid APIs/);
  assert.match(b,/Hypothesis only/);
  assert.match(b,/Do not publish/);
  count++;
 }
 assert.equal(count,108);
});

test('repeatability and controlled variation across seed, audience, and format',()=>{
 assert.deepEqual(generate({sector:3,seed:1}),generate({sector:3,seed:1}));
 assert.notEqual(generate({sector:3,seed:1}).scope,generate({sector:3,seed:2}).scope);
 assert.notEqual(generate({sector:2,audience:'individuals',format:'service'}).formatPackaging,generate({sector:2,audience:'community groups',format:'toolkit'}).formatPackaging);
});

test('invalid inputs fail closed including blank strings, booleans, null, arrays, floats, and negative zero',()=>{
 const badInputs=[
  {sector:-1},{sector:12},{sector:1.5},{sector:''},{sector:'   '},{sector:null},{sector:false},{sector:true},{sector:[0]},{sector:-0},
  {audience:'<script>'},{audience:''},{audience:null},{audience:false},
  {format:'scam'},{format:''},{format:null},{format:true},
  {budget:-1},{budget:1000001},{budget:0.5},{budget:125.99},{budget:Infinity},{budget:NaN},{budget:'oops'},{budget:''},{budget:'   '},{budget:null},{budget:false},{budget:true},{budget:[125]},{budget:-0},
  {seed:-1},{seed:10000},{seed:1.5},{seed:''},{seed:'   '},{seed:null},{seed:false},{seed:true},{seed:[1]},{seed:-0}
 ];
 for(const opts of badInputs){
  assert.throws(()=>generate(opts), `Expected generate(${JSON.stringify(opts)}) to throw`);
 }
});

test('valid string integer inputs from DOM controls are accepted cleanly',()=>{
 const x=generate({sector:'2',audience:'community groups',format:'toolkit',budget:'125',seed:'3'});
 assert.equal(x.id,'IL-3-3');
 assert.match(x.budget,/\$125/);
});

test('zero budget never implies a paid dependency',()=>{
 assert.match(brief(generate()),/free local tools/);
 assert.match(brief(generate()),/No paid APIs/);
});

test('catalog does not assert verified demand',()=>{
 for(let i=0;i<sectors.length;i++){
  const x=generate({sector:i});
  assert.match(x.evidence,/No customer demand/);
  assert.match(x.limitations,/maturity/);
  assert.ok(!/guaranteed income/i.test(x.offer));
 }
});
