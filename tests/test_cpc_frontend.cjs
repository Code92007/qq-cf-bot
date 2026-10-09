const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.join(__dirname,'..');
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{value:'2024',checked:false,textContent:'',innerHTML:''});return elements.get(id);}
const context={document:{getElementById:element,addEventListener(){}},Date};
vm.createContext(context);
const wall=process.env.CPC_WALL_CHECKOUT||path.join(root,'../oj-submission-wall');
vm.runInContext(fs.readFileSync(path.join(wall,'web/regionals.js'),'utf8'),context);
vm.runInContext(`cpcData={roster_checked:0,unmapped_count:0,contests:[{year:2024,name:'测试 <站>',problems:['A','B','C','D','E'].map(id=>({id,index:id,name:id}))}],problems:{A:{personal:true,onsite:true},B:{team:true},C:{onsite:true}}};cpcWall();`,context);
assert.match(element('cpcSummary').textContent,/2\/5/);
assert.match(element('cpcRows').innerHTML,/测试 &lt;站&gt;/);
element('cpcTeams').checked=true;vm.runInContext('cpcWall()',context);
assert.match(element('cpcSummary').textContent,/3\/5/);
const botContext={document:{addEventListener(){}}};vm.createContext(botContext);
vm.runInContext(fs.readFileSync(path.join(root,'src/qq_cf_bot/web/regionals.js'),'utf8'),botContext);
assert.equal(vm.runInContext(`model.view='union';completed({oral:false,code:false,onsite:true})`,botContext),true);
assert.equal(vm.runInContext(`model.view='oral';completed({oral:false,code:false,onsite:true})`,botContext),false);
assert.equal(vm.runInContext(`model.view='code';completed({oral:false,code:false,onsite:true})`,botContext),false);
console.log('CPC frontend: default/team coverage, deduplication, escaping and isolated oral/code views passed');
