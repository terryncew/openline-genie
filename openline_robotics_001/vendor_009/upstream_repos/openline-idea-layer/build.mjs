import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const read=f=>readFileSync(new URL(f,import.meta.url),'utf8');
const html=read('./index.template.html');
const engine=read('./engine.mjs').replaceAll(/\bexport (const|function)\b/g,'$1');
const app=read('./app.mjs').replace(/^import .*?;\s*/m,'');
const js=engine+'\n'+app;
const hash=createHash('sha256').update(js).digest('base64');
const out=html.replace('<script type="module" src="./app.mjs"></script>',()=>`<script>${js.replaceAll('</script','<\\/script')}</script>`)
              .replace('</head>',`<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-${hash}'; style-src 'unsafe-inline'; connect-src 'none'; img-src data:; object-src 'none'; base-uri 'none'; form-action 'none'"></head>`);
writeFileSync(new URL('./index.html',import.meta.url),out);
console.log('Built self-contained index.html, '+Buffer.byteLength(out)+' bytes');
