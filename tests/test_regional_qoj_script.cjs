const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../src/qq_cf_bot/web/regional-qoj-sync.user.js'),'utf8');
const context={URL};vm.createContext(context);
vm.runInContext(source.replace("  const panel = document.createElement('div');","  globalThis.parseUsername = submissionUsername; return;\n  const panel = document.createElement('div');"),context);
function cell(text,urls=[],controls=[]){
  return {textContent:text,querySelectorAll:()=>urls.map(href=>({getAttribute:()=>href})),cloneNode:()=>{
    let output=text;return {get textContent(){return output},querySelectorAll:()=>controls.map(label=>({textContent:label,remove(){output=output.replace(label,'')}}))};
  }};
}
const parse=context.parseUsername;
assert.equal(parse(cell('Team display #',['/submissions?submitter=ucup-team123'])),'ucup-team123');
assert.equal(parse(cell('Team display',['/user/profile/ucup-team123'])),'ucup-team123');
assert.equal(parse(cell('ucup-team123 #',[],['#'])),'ucup-team123');
assert.equal(parse(cell('ucup-team123＃',[],['＃'])),'ucup-team123');
assert.equal(parse(cell('alice')),'alice');
assert.equal(parse(cell('ucup-team123 extra')),'');
assert.equal(parse(cell('alice',['https://evil.example/user/profile/bob'])),'alice');
assert.throws(()=>parse(cell('alice bob',['/user/profile/alice','/submissions?submitter=bob'])));
assert.equal(parse(cell('Team',['/user/profile/alice','/submissions?submitter=alice'])),'alice');
console.log('QOJ 1.0.2 username parsing: team filter links, profile links, # controls, ambiguity and foreign origins passed');
