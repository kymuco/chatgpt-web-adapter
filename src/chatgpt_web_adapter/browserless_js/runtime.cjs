// Research harness: no credentials or network APIs are exposed to the VM.
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const bytes = fs.readFileSync(input.modulePath);
if (crypto.createHash('sha256').update(bytes).digest('hex') !== '21a5313fc55570e213891f3f6daef5a596130a8a5cd12b8d90a94e37944321ed') {
  throw new Error('Unreviewed integrity module: hash mismatch');
}
let source = bytes.toString('utf8').slice(4);
source = source.replace('let t=g(),n=p(await e(t))', 'let t=INPUT.prepareInput,n=p(INPUT.requirements)');
source = source.replace('let a=r.get(t),i=a[String(r.get(n))];', "let a=r.get(t),key=String(r.get(n));if(!a||typeof a[key]!=='function')throw Error('Missing method '+key);let i=a[key];");
source = source.replace('let a=r.get(t);r.set(e,a[String(r.get(n))])', "let a=r.get(t),key=String(r.get(n));trace.push(key);if(a==null)throw Error('Missing object for '+key);r.set(e,a[key])");
const context = vm.createContext({}, {codeGeneration: {strings: false, wasm: false}});
const bootstrap = `
const INPUT = ${JSON.stringify(input)};
const trace=[];
const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
function btoa(s) { let out=''; for(let i=0;i<s.length;i+=3) { let a=s.charCodeAt(i), b=s.charCodeAt(i+1), c=s.charCodeAt(i+2); out+=alphabet[a>>2]+alphabet[((a&3)<<4)|((b||0)>>4)]+(i+1<s.length?alphabet[((b&15)<<2)|((c||0)>>6)]:'=')+(i+2<s.length?alphabet[c&63]:'='); } return out; }
function atob(s) { let bits=0,value=0,out=''; for(const c of s.replace(/=+$/,'')){ const n=alphabet.indexOf(c);if(n<0)continue;value=(value<<6)|n;bits+=6;if(bits>=8){bits-=8;out+=String.fromCharCode((value>>bits)&255);} } return out; }
class TextEncoder { encode(s) { return Uint8Array.from(unescape(encodeURIComponent(s)), c=>c.charCodeAt(0)); } }
const performance = {timeOrigin:Date.now(), now:()=>Date.now()-performance.timeOrigin};
const screen = {width:0,height:0};
const navigator = {userAgent:INPUT.userAgent,language:'en-US',languages:['en-US'],hardwareConcurrency:1};
const elements=[];
function createElement(tag) {
  const node={tagName:String(tag).toUpperCase(),style:{},children:[],attributes:{},
    setAttribute(k,v){this.attributes[k]=String(v);},getAttribute(k){return this.attributes[k]??null;},
    appendChild(n){this.children.push(n);return n;},remove(){},
    getContext(){return null;},getBoundingClientRect(){return {x:0,y:0,width:0,height:0,top:0,bottom:0,left:0,right:0};},addEventListener(){},removeEventListener(){}};
  elements.push(String(tag));return node;
}
const document = {scripts:[],createElement,documentElement:{getAttribute:()=>null},body:{appendChild(n){return n;},removeChild(n){return n;}}};
const window = globalThis;
const storage = {length:0,getItem(){return null;},setItem(){},removeItem(){},key(){return null;}};
Object.assign(window, {
  location: {search:'',href:'https://chatgpt.com/',origin:'https://chatgpt.com'},
  history: {length:1},
  localStorage: storage,
  sessionStorage: storage,
});
class URLSearchParams { keys(){return [][Symbol.iterator]();} }
Object.assign(window,{performance,screen,navigator,document,TextEncoder,URLSearchParams});
const timers=[];
function setTimeout(fn) {timers.push(fn);return timers.length;}
function clearTimeout() {}
const exports={};
const req=(id)=>{if(id!=='DD')throw Error('unsupported import');return {a:()=>INPUT.uuid};};
Object.assign(req, {d:(target, defs)=>{for(const [k,v] of Object.entries(defs))Object.defineProperty(target,k,{get:v});}});
(${source})({},exports,req);
let result;
if(INPUT.mode==='prepare') result={prepareInput:exports.d()};
else exports.f().then(v=>{result={proofToken:v.proofToken,turnstileToken:v.turnstileToken,trace:trace.slice(-20),elements};}).catch(e=>{result={error:String(e)};});
`;
vm.runInContext(bootstrap, context, {timeout:3000});
setImmediate(()=>{
  vm.runInContext('for (const fn of timers) if (!result) fn();', context, {timeout:1000});
  setImmediate(()=>{
    const output=vm.runInContext('JSON.stringify(result ?? {error:"unfinished"})', context, {timeout:1000});
    process.stdout.write(output);
  });
});
