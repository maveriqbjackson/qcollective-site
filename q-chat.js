/* ============================================================================
   Q COLLECTIVE — FLOATING "ASK Q" CHAT WIDGET
   Drop-in: <script src="q-config.js"></script><script src="q-chat.js"></script>
   Shows a gold bubble bottom-right on every page. Click it to chat in a panel
   without leaving the page. Talks to your Cloudflare Worker (window.Q_WORKER_URL).
   If the Worker isn't connected yet, it shows a friendly "coming online" note.
============================================================================ */
(function () {
  if (window.__qChatLoaded) return;            // don't load twice
  window.__qChatLoaded = true;
  if (document.body && document.body.getAttribute("data-no-qchat") === "1") return;

  var CSS = "" +
  ".qc-bubble{position:fixed;right:20px;bottom:20px;z-index:2147483000;width:60px;height:60px;border-radius:50%;background:linear-gradient(135deg,#D4AF50,#B8962E);color:#122848;border:none;cursor:pointer;box-shadow:0 6px 20px rgba(18,40,72,.28);display:flex;align-items:center;justify-content:center;font-family:'Playfair Display',Georgia,serif;font-weight:900;font-size:26px;transition:transform .15s,box-shadow .15s}" +
  ".qc-bubble:hover{transform:translateY(-2px) scale(1.04);box-shadow:0 10px 26px rgba(18,40,72,.35)}" +
  ".qc-bubble .qc-x{font-family:'DM Sans',sans-serif;font-weight:400;font-size:26px;line-height:1}" +
  ".qc-tip{position:fixed;right:88px;bottom:34px;z-index:2147483000;background:#122848;color:#fff;font-family:'DM Sans',sans-serif;font-size:13px;padding:8px 13px;border-radius:8px;box-shadow:0 4px 14px rgba(18,40,72,.25);white-space:nowrap;opacity:0;transform:translateX(6px);transition:opacity .2s,transform .2s;pointer-events:none}" +
  ".qc-tip.show{opacity:1;transform:translateX(0)}" +
  ".qc-tip:after{content:'';position:absolute;right:-6px;bottom:12px;border:6px solid transparent;border-left-color:#122848}" +
  ".qc-panel{position:fixed;right:20px;bottom:92px;z-index:2147483000;width:380px;max-width:calc(100vw - 32px);height:560px;max-height:calc(100vh - 130px);background:#fff;border:1px solid #E0D5BE;border-radius:16px;box-shadow:0 16px 50px rgba(18,40,72,.30);display:none;flex-direction:column;overflow:hidden;font-family:'DM Sans',sans-serif}" +
  ".qc-panel.open{display:flex;animation:qcpop .18s ease}" +
  "@keyframes qcpop{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}" +
  ".qc-head{background:#122848;color:#fff;padding:15px 18px;position:relative;overflow:hidden}" +
  ".qc-head .qc-wm{position:absolute;right:-16px;top:-40px;font-family:'Playfair Display',Georgia,serif;font-weight:900;font-size:150px;color:rgba(255,255,255,.06);line-height:1;pointer-events:none}" +
  ".qc-head h4{margin:0;font-family:'Playfair Display',Georgia,serif;font-size:19px;position:relative}" +
  ".qc-head p{margin:2px 0 0;font-size:12px;color:rgba(255,255,255,.72);position:relative}" +
  ".qc-close{position:absolute;top:12px;right:14px;background:none;border:none;color:rgba(255,255,255,.8);font-size:22px;cursor:pointer;line-height:1}" +
  ".qc-log{flex:1;overflow-y:auto;padding:16px 15px;display:flex;flex-direction:column;gap:11px;background:#F9F6F0}" +
  ".qc-b{max-width:86%;padding:10px 13px;border-radius:13px;font-size:14px;line-height:1.55;white-space:pre-wrap;word-wrap:break-word}" +
  ".qc-b.a{align-self:flex-start;background:#fff;border:1px solid #E0D5BE;border-bottom-left-radius:4px;color:#1a1a1a}" +
  ".qc-b.a a{color:#1B3A6B;text-decoration:underline;font-weight:500}" +
  ".qc-b.u{align-self:flex-end;background:#1B3A6B;color:#fff;border-bottom-right-radius:4px}" +
  ".qc-b.a .qc-who{display:block;font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1.4px;text-transform:uppercase;color:#B8962E;margin-bottom:4px}" +
  ".qc-typing{align-self:flex-start;color:#5a5a5a;font-size:13px;font-style:italic;padding:2px 4px}" +
  ".qc-chips{display:flex;flex-wrap:wrap;gap:6px;padding:0 15px 10px;background:#F9F6F0}" +
  ".qc-chip{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:.4px;background:#fff;border:1px solid #E0D5BE;color:#1B3A6B;padding:6px 10px;border-radius:16px;cursor:pointer}" +
  ".qc-chip:hover{background:#B8962E;border-color:#B8962E;color:#122848}" +
  ".qc-chip.role{background:#122848;color:#fff;border-color:#122848}" +
  ".qc-chip.role:hover{background:#B8962E;border-color:#B8962E;color:#122848}" +
  ".qc-input{display:flex;gap:8px;padding:11px 12px;border-top:1px solid #E0D5BE;background:#fbf9f4}" +
  ".qc-input textarea{flex:1;resize:none;border:1px solid #E0D5BE;border-radius:8px;padding:9px 11px;font-family:'DM Sans',sans-serif;font-size:14px;line-height:1.4;color:#1a1a1a;min-height:40px;max-height:120px}" +
  ".qc-input textarea:focus{outline:none;border-color:#B8962E}" +
  ".qc-input button{border:none;cursor:pointer;padding:0 16px;border-radius:8px;font-family:'DM Mono',monospace;font-size:11px;letter-spacing:1px;text-transform:uppercase;background:#B8962E;color:#122848}" +
  ".qc-input button:disabled{opacity:.5;cursor:default}" +
  ".qc-disc{font-size:10px;color:#8a8a8a;text-align:center;padding:7px 14px 10px;background:#fbf9f4;line-height:1.5}" +
  "@media(max-width:460px){.qc-panel{right:8px;left:8px;width:auto;bottom:84px}.qc-tip{display:none}}";

  var s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s);

  var Q = "Q Assistant";
  var INTRO = "Hi \u2014 I'm the Q Assistant. Ask me anything, or paste a link and I'll weigh it against the seven pillars.<br><br><b>Quick links:</b> <a href='find-officials.html'>Find your reps</a> &middot; <a href='hub.html'>Q Scores</a> &middot; <a href='the-work.html'>The bills</a> &middot; <a href='support-a-bill.html'>Support a bill</a><br><br><b>Reach us:</b> <a href=\'contact.html\'>Contact</a> or <a href=\'work-with-us.html\'>Work with us</a>, or email team@theQcollective.org.<br><br><b>New here?</b> Tell me who you are below and I&rsquo;ll tailor this.";

  var wrap = document.createElement("div");
  wrap.innerHTML =
    '<div class="qc-tip" id="qcTip">Ask me anything</div>' +
    '<button class="qc-bubble" id="qcBubble" aria-label="Open the Q Assistant chat"><span class="qc-q">Q</span></button>' +
    '<div class="qc-panel" id="qcPanel" role="dialog" aria-label="Q Assistant chat">' +
      '<div class="qc-head"><div class="qc-wm">Q</div><button class="qc-close" id="qcClose" aria-label="Close">&times;</button>' +
        '<h4>Ask the Q Assistant</h4><p>Ask anything \u00b7 or paste a link to evaluate</p></div>' +
      '<div class="qc-log" id="qcLog"></div>' +
      '<div class="qc-chips" id="qcChips">' +
        '<span class="qc-chip role" data-q="I am a citizen. How can I find my representatives and their scores?">I\u2019m a citizen</span>' +
        '<span class="qc-chip role" data-official="1">Elected official</span>' +
        '<span class="qc-chip role" data-q="I am a member of the press. Where is your scoring methodology and how do I request comment?">Press</span>' +
        '<span class="qc-chip role" data-q="I am from another branch of government (executive or judicial). How does scoring apply to me?">Another branch</span>' +
        '<span class="qc-chip" data-q="What is the Colorado Economic Security Act, in plain language?">What is CESA?</span>' +
        '<span class="qc-chip" data-q="What are the seven pillars of life stability?">The seven pillars</span>' +
      '</div>' +
      '<div class="qc-input"><textarea id="qcBox" rows="1" placeholder="Ask a question, or paste a link\u2026"></textarea><button id="qcSend">Send</button></div>' +
      '<div class="qc-disc">AI can be wrong. Not legal advice. Confirm against source documents.</div>' +
    '</div>';
  document.body.appendChild(wrap);

  var bubble=document.getElementById("qcBubble"), panel=document.getElementById("qcPanel"),
      log=document.getElementById("qcLog"), box=document.getElementById("qcBox"),
      send=document.getElementById("qcSend"), chips=document.getElementById("qcChips"),
      tip=document.getElementById("qcTip"), bq=bubble.querySelector(".qc-q");
  var history=[], started=false, tipTimer;

  function esc(t){return String(t).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
  function linkify(t){t=esc(t);
    t=t.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+|[a-z0-9_\-]+\.html[^\s)]*)\)/gi,function(_,txt,url){var ext=/^https?:/i.test(url);return '<a href="'+url+'"'+(ext?' target="_blank" rel="noopener"':'')+'>'+txt+'</a>';});
    t=t.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g,function(m,pre,url){return pre+'<a href="'+url+'" target="_blank" rel="noopener">'+url+'</a>';});
    return t;}
  function bub(role,text){var d=document.createElement("div");d.className="qc-b "+(role==="user"?"u":"a");
    if(role!=="user"){d.innerHTML='<span class="qc-who">'+Q+'</span>'+linkify(text);}else{d.textContent=text;}
    log.appendChild(d);log.scrollTop=log.scrollHeight;return d;}
  function bubHTML(html){var d=document.createElement("div");d.className="qc-b a";d.innerHTML='<span class="qc-who">'+Q+'</span>'+html;log.appendChild(d);log.scrollTop=log.scrollHeight;return d;}
  function typing(){var d=document.createElement("div");d.className="qc-typing";d.textContent="Thinking\u2026";log.appendChild(d);log.scrollTop=log.scrollHeight;return d;}

  function open(){panel.classList.add("open");bubble.setAttribute("aria-expanded","true");bq.textContent="";bubble.querySelector(".qc-q").innerHTML='<span class="qc-x">&times;</span>';
    if(!started){started=true;bubHTML(INTRO);} setTimeout(function(){box.focus();},60); hideTip();}
  function close(){panel.classList.remove("open");bubble.setAttribute("aria-expanded","false");bubble.querySelector(".qc-q").textContent="Q";}
  function toggle(){panel.classList.contains("open")?close():open();}
  function hideTip(){tip.classList.remove("show");clearTimeout(tipTimer);}

  var awaitOfficial=false, rosterCache=null;
  function startOfficialLookup(){bubHTML('Sure \u2014 type your name as it appears on the ballot (for example, <b>Jane Smith</b>) and I\u2019ll pull up your Q Score and profile.');awaitOfficial=true;box.focus();}
  function lookupOfficial(name){var t=typing();function done(list){t.remove();matchOfficial(name,list);}
    if(rosterCache){done(rosterCache);return;}
    fetch('data/CO.json').then(function(r){return r.json();}).then(function(d){rosterCache=(d&&d.legislators)||[];done(rosterCache);}).catch(function(){t.remove();bub('assistant','I couldn\u2019t load the roster just now. You can find your profile via the Accountability Hub (hub.html) or Find Your Officials (find-officials.html).');});}
  function matchOfficial(name,list){var q=name.toLowerCase().replace(/\s+/g,' ').trim();var hit=null,hits=[];
    for(var i=0;i<list.length;i++){var n=(list[i].name||'').toLowerCase();if(n===q){hit=list[i];break;}
      var pa=n.split(' '),pb=q.split(' ');if(n.indexOf(q)>=0||q.indexOf(n)>=0||pa[pa.length-1]===pb[pb.length-1])hits.push(list[i]);}
    if(!hit&&hits.length===1)hit=hits[0];
    if(hit){var url='legislator.html?state=CO&id='+encodeURIComponent(hit.id);var lab=hit.label?(' \u2014 '+esc(hit.label)):'';
      bubHTML('Here you are, <b>'+esc(hit.name)+'</b> ('+esc(hit.role||'')+', District '+esc(String(hit.district||''))+'):<br><br>Your Q Score is <b>'+esc(String(hit.score))+'</b>'+lab+'.<br><br>See your full profile \u2014 every factor and the data behind it: <a href="'+url+'">Your profile &amp; record</a>. If anything needs context, you can submit an official response via <a href="contact.html">Contact</a>.');}
    else if(hits.length>1){var links=hits.slice(0,6).map(function(h){return '<a href="legislator.html?state=CO&id='+encodeURIComponent(h.id)+'">'+esc(h.name)+'</a>';}).join(' &middot; ');
      bubHTML('I found a few possible matches \u2014 which one is you? '+links);}
    else{bubHTML('I couldn\u2019t find that exact name in the Colorado roster. Double-check the spelling, or browse everyone at <a href="find-officials.html">Find Your Officials</a> or the <a href="hub.html">Accountability Hub</a>.');}}
  function ask(text){
    if(!text.trim())return;
    if(awaitOfficial){awaitOfficial=false;bub("user",text);box.value="";box.style.height="auto";lookupOfficial(text.trim());return;}
    bub("user",text);history.push({role:"user",content:text});
    box.value="";box.style.height="auto";send.disabled=true;
    var url=window.Q_WORKER_URL||"";
    if(!url){var t=typing();setTimeout(function(){t.remove();
      bub("assistant","The assistant is coming online soon \u2014 the live chat isn't connected on this page yet. In the meantime, everything I'd draw from is public on the site: try The Work, or the bill itself.");
      send.disabled=false;},450);return;}
    var t=typing();
    fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({messages:history})})
      .then(function(r){return r.json();})
      .then(function(d){t.remove();var reply=(d&&d.reply)||"Sorry \u2014 I couldn't answer that just now.";
        bub("assistant",reply);history.push({role:"assistant",content:reply});send.disabled=false;})
      .catch(function(){t.remove();bub("assistant","Something went wrong reaching me. Please try again, or email team@theQcollective.org.");send.disabled=false;});
  }

  bubble.addEventListener("click",toggle);
  document.getElementById("qcClose").addEventListener("click",close);
  send.addEventListener("click",function(){ask(box.value);});
  box.addEventListener("keydown",function(e){if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();ask(box.value);}});
  box.addEventListener("input",function(){box.style.height="auto";box.style.height=Math.min(box.scrollHeight,120)+"px";});
  chips.addEventListener("click",function(e){if(!e.target.classList.contains("qc-chip"))return;if(e.target.getAttribute("data-official")){startOfficialLookup();return;}ask(e.target.getAttribute("data-q"));});
  document.addEventListener("keydown",function(e){if(e.key==="Escape"&&panel.classList.contains("open"))close();});

  // gentle first-visit nudge
  tipTimer=setTimeout(function(){if(!panel.classList.contains("open")){tip.classList.add("show");setTimeout(hideTip,4200);}},1400);
})();
