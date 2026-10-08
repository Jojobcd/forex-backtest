"""Construit « Journal Forex.html » (version locale, sans claude.ai) à partir de journal.html.
Les idées et analyses viennent de donnees.js ; les trades de l'utilisateur sont gardés dans le navigateur
(localStorage) avec export / import d'une sauvegarde JSON."""
from pathlib import Path
H = Path(__file__).parent
src = (H / "journal.html").read_text(encoding="utf-8")


def rep(s, old, new):
    assert old in s, f"motif introuvable : {old[:60]}"
    return s.replace(old, new, 1)


s = src
s = rep(s, '<p class="lead">Ce journal suit',
        '<p class="lead">Ce journal suit')
s = rep(s, "  <details>\n    <summary>Comment lire ce journal (lexique)</summary>",
        """  <section aria-labelledby="h-save">
    <h2 id="h-save">Sauvegarde</h2>
    <p class="lead">Les trades sont enregistrés dans ce navigateur, sur cet ordinateur. Si l'historique du navigateur est effacé, ils disparaissent. Faites une sauvegarde après chaque modification importante et rangez le fichier dans le dossier <b>journal</b> : Claude pourra alors le lire.</p>
    <div class="actions">
      <button class="primary" type="button" id="b-export">Télécharger une sauvegarde</button>
      <label class="small" style="flex-direction:row;align-items:center;gap:8px"><span>Restaurer une sauvegarde :</span><input type="file" id="b-import" accept=".json,application/json"></label>
    </div>
    <p id="save-msg" class="small"></p>
  </section>

  <details>
    <summary>Comment lire ce journal (lexique)</summary>""")
s = rep(s, "<script>\nconst NOMS=", '<script src="donnees.js"></script>\n<script>\nconst NOMS=')
s = rep(s, "let db=null, canWrite=true,", "const KEY=\"journal-forex-g10\"; let store={trades:{},deleted:{}}; let db=null, canWrite=true,")
s = rep(s, """async function save(id,patch){
  try{await db.doc("trades/"+id).update(patch)}catch(e){showErr(e)}
}""", """function persist(){
  try{localStorage.setItem(KEY,JSON.stringify(store))}catch(e){const st=$("status");st.hidden=false;st.textContent="Ce navigateur refuse d'enregistrer les données. Les changements seront perdus à la fermeture : téléchargez une sauvegarde."}
  rebuild();render();
}
function rebuild(){
  const D=window.JOURNAL_DATA||{analyses:[],idees:[]}; const out={};
  (D.idees||[]).forEach(t=>{if(!store.deleted[t.id]) out[t.id]={...t}});
  Object.entries(store.trades).forEach(([id,t])=>{if(!store.deleted[id]) out[id]={...(out[id]||{}),...t,id}});
  trades=Object.values(out);
  const A=[...(D.analyses||[])].sort((a,b)=>String(b.date).localeCompare(String(a.date))); analyse=A[0]||null;
}
async function save(id,patch){
  const cur=trades.find(t=>t.id===id)||{}; store.trades[id]={...cur,...patch}; persist();
}""")
s = rep(s, 'try{await db.doc("trades/"+id).delete()}catch(err){showErr(err)}',
        "store.deleted[id]=true; delete store.trades[id]; persist();")
s = rep(s, 'try{await db.collection("trades").add(doc);f.reset();msg.textContent="Trade ajouté."}catch(err){showErr(err)}finally{$("a-submit").disabled=false}',
        'const nid="perso-"+Date.now(); store.trades[nid]={...doc,id:nid}; persist(); f.reset(); msg.textContent="Trade ajouté."; $("a-submit").disabled=false;')
start = s.index("(async()=>{\n  const s=$(\"status\");")
end = s.index("})();", start) + len("})();")
s = s[:start] + """(function init(){
  try{const raw=localStorage.getItem(KEY); if(raw){const p=JSON.parse(raw); store={trades:p.trades||{},deleted:p.deleted||{}}}}catch(_){}
  if(!window.JOURNAL_DATA){const st=$("status");st.hidden=false;st.textContent="Le fichier donnees.js est introuvable : gardez-le dans le même dossier que cette page."}
  rebuild(); render();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change",render);
  addEventListener("resize",()=>{clearTimeout(window.__rz);window.__rz=setTimeout(renderBilan,150)});
  $("b-export").addEventListener("click",()=>{
    const blob=new Blob([JSON.stringify({format:"journal-forex-g10",version:1,exporte_le:new Date().toISOString(),trades:store.trades,deleted:store.deleted},null,1)],{type:"application/json"});
    const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download="journal_forex_sauvegarde_"+new Date().toISOString().slice(0,10)+".json";
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(a.href),2000);
    $("save-msg").textContent="Sauvegarde téléchargée. Rangez-la dans le dossier journal.";
  });
  $("b-import").addEventListener("change",async e=>{
    const f=e.target.files[0]; if(!f) return;
    try{const p=JSON.parse(await f.text()); if(p.format!=="journal-forex-g10") throw 0;
      store={trades:{...store.trades,...(p.trades||{})},deleted:{...store.deleted,...(p.deleted||{})}}; persist();
      $("save-msg").textContent="Sauvegarde restaurée : "+Object.keys(p.trades||{}).length+" trade(s) importé(s).";
    }catch(_){$("save-msg").textContent="Ce fichier n'est pas une sauvegarde du journal."}
    e.target.value="";
  });
})();""" + s[end:]
page = ('<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n</head>\n<body>\n' + s + "\n</body>\n</html>\n")
(H / "Journal Forex.html").write_text(page, encoding="utf-8")
print("OK", H / "Journal Forex.html")
