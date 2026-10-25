"""把登录层样式整体替换为赛博朋克版本。"""
import io
import re
from pathlib import Path

P = Path(r"D:\文旅助手\web\css\style.css")
css = P.read_text(encoding="utf-8")

NEW = r"""/* ---------- 登录层 · 赛博朋克 ---------- */
:root{--cy:#00e5ff;--mg:#ff2d95;--mono:"Cascadia Mono","Cascadia Code",ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",Menlo,monospace}

.auth-layer{position:fixed;inset:0;z-index:200;display:grid;grid-template-columns:1.05fr .95fr;
  background:#04060c;overflow:hidden;font-family:var(--mono)}
.auth-layer.hidden{display:none}

/* 背景装饰：透视网格 / 扫描线 / 扫描光束 / 双色光晕 */
.auth-grid-bg{position:absolute;inset:-40%;pointer-events:none;z-index:0;
  background:
    repeating-linear-gradient(0deg,rgba(0,229,255,.055) 0 1px,transparent 1px 46px),
    repeating-linear-gradient(90deg,rgba(0,229,255,.05) 0 1px,transparent 1px 46px);
  transform:perspective(560px) rotateX(64deg) translateY(-10%);
  animation:cyGrid 12s linear infinite;
  -webkit-mask-image:linear-gradient(180deg,transparent,#000 28%,#000 72%,transparent);
  mask-image:linear-gradient(180deg,transparent,#000 28%,#000 72%,transparent)}
@keyframes cyGrid{to{background-position:0 46px,0 0}}
.auth-scanlines{position:absolute;inset:0;pointer-events:none;z-index:4;opacity:.5;
  background:repeating-linear-gradient(180deg,rgba(255,255,255,.028) 0 1px,transparent 1px 3px)}
.auth-scanbeam{position:absolute;left:0;right:0;height:220px;pointer-events:none;z-index:5;
  background:linear-gradient(180deg,transparent,rgba(0,229,255,.06) 42%,rgba(255,45,149,.045) 58%,transparent);
  animation:cyBeam 8s linear infinite}
@keyframes cyBeam{0%{top:-25%}100%{top:110%}}
.auth-layer::before{content:"";position:absolute;z-index:1;width:820px;height:820px;left:-200px;top:-220px;
  border-radius:50%;background:radial-gradient(circle,rgba(0,229,255,.15),transparent 62%);filter:blur(40px)}
.auth-layer::after{content:"";position:absolute;z-index:1;width:720px;height:720px;right:-180px;bottom:-200px;
  border-radius:50%;background:radial-gradient(circle,rgba(255,45,149,.13),transparent 62%);filter:blur(40px)}

/* 左侧品牌区 */
.auth-visual{position:relative;overflow:hidden;display:flex;align-items:center;z-index:2}
.auth-slides{position:absolute;inset:0}
.auth-slide{position:absolute;inset:0;background-size:cover;background-position:center;opacity:0;
  transition:opacity 1.4s ease;transform:scale(1.08);filter:saturate(1.15) contrast(1.06)}
.auth-slide.on{opacity:.34;transform:scale(1);transition:opacity 1.4s ease,transform 10s linear}
.auth-visual::after{content:"";position:absolute;inset:0;
  background:linear-gradient(90deg,rgba(4,6,12,.18),rgba(4,6,12,.84) 62%,rgba(4,6,12,.96)),
             linear-gradient(180deg,rgba(4,6,12,.35),rgba(4,6,12,.88))}
.auth-visual.no-photo::after{background:linear-gradient(90deg,rgba(4,6,12,.2),rgba(4,6,12,.72) 62%,rgba(4,6,12,.94))}
.auth-visual-inner{position:relative;z-index:2;padding:0 clamp(30px,4.5vw,72px);max-width:560px}
.auth-logo{width:60px;height:60px;border-radius:14px;display:grid;place-items:center;font-size:26px;
  color:var(--cy);background:linear-gradient(140deg,rgba(0,229,255,.14),rgba(255,45,149,.12));
  border:1px solid rgba(0,229,255,.45);margin-bottom:22px;
  box-shadow:0 0 34px -6px rgba(0,229,255,.7),inset 0 0 22px -10px rgba(0,229,255,.9)}
.auth-brandline{display:flex;align-items:baseline;gap:12px;margin-bottom:10px}
.auth-brandline .brk{font-size:30px;font-weight:800;letter-spacing:8px;color:#fff;
  text-shadow:0 0 18px rgba(0,229,255,.65),0 0 44px rgba(0,229,255,.35)}
.auth-brandline em{font-style:normal;font-size:11px;letter-spacing:4px;color:var(--mg);
  text-shadow:0 0 14px rgba(255,45,149,.6)}
.auth-visual-inner h2{font-size:clamp(23px,2.3vw,33px);font-weight:700;letter-spacing:1px;margin-bottom:26px;
  line-height:1.55;color:#dce8f7}
.auth-points{list-style:none;display:flex;flex-direction:column;gap:13px;margin-bottom:30px}
.auth-points li{display:flex;align-items:center;gap:11px;font-size:12.5px;color:#9fb4cd;letter-spacing:.4px}
.auth-points li b{color:var(--cy);font-weight:600;text-shadow:0 0 12px rgba(0,229,255,.45)}
.auth-points i{width:6px;height:6px;border-radius:1px;background:var(--mg);flex:none;
  box-shadow:0 0 10px rgba(255,45,149,.9);transform:rotate(45deg)}
.auth-stats{display:flex;gap:34px;padding-top:22px;border-top:1px solid rgba(0,229,255,.14)}
.auth-stats div{display:flex;flex-direction:column}
.auth-stats b{font-size:22px;font-weight:800;color:#fff;letter-spacing:-.5px;
  text-shadow:0 0 16px rgba(0,229,255,.55)}
.auth-stats span{font-size:9.5px;letter-spacing:2px;color:#5d7594;margin-top:2px}
.auth-credit{position:absolute;bottom:-70px;font-size:9px;color:rgba(255,255,255,.2);letter-spacing:1px}

/* 右侧表单 */
.auth-panel{display:flex;align-items:center;justify-content:center;padding:34px 26px;overflow-y:auto;z-index:2;
  background:linear-gradient(180deg,rgba(4,6,12,.7),rgba(4,6,12,.9))}
.auth-card{width:100%;max-width:414px;position:relative;padding:30px 32px 26px;border-radius:16px;
  background:linear-gradient(160deg,rgba(9,17,31,.84),rgba(5,9,18,.74));
  border:1px solid rgba(0,229,255,.2);
  backdrop-filter:blur(22px) saturate(150%);
  box-shadow:0 0 0 1px rgba(255,45,149,.12) inset,0 34px 90px -34px #000,0 0 70px -34px rgba(0,229,255,.7)}
.auth-corner{position:absolute;width:15px;height:15px;border:1px solid var(--cy);opacity:.9;
  filter:drop-shadow(0 0 6px rgba(0,229,255,.8))}
.auth-corner.tl{left:-1px;top:-1px;border-right:0;border-bottom:0}
.auth-corner.tr{right:-1px;top:-1px;border-left:0;border-bottom:0}
.auth-corner.bl{left:-1px;bottom:-1px;border-right:0;border-top:0}
.auth-corner.br{right:-1px;bottom:-1px;border-left:0;border-top:0}
.auth-id{font-size:9.5px;letter-spacing:3px;color:#3f6b8f;margin-bottom:9px}
.auth-head h3{font-size:25px;font-weight:700;letter-spacing:1px;color:#fff}
.auth-head p{font-size:11.5px;color:#7d93ad;margin-top:7px;margin-bottom:20px;letter-spacing:.4px}

/* 故障字 */
.glitch{position:relative;display:inline-block}
.glitch::before,.glitch::after{content:attr(data-text);position:absolute;inset:0;pointer-events:none;opacity:.75}
.glitch::before{color:var(--mg);clip-path:inset(0 0 58% 0);animation:glitchA 3.4s infinite steps(2)}
.glitch::after{color:var(--cy);clip-path:inset(56% 0 0 0);animation:glitchB 2.9s infinite steps(2)}
@keyframes glitchA{0%,86%,100%{transform:translate(0,0)}88%{transform:translate(-3px,1px)}92%{transform:translate(2px,-1px)}}
@keyframes glitchB{0%,88%,100%{transform:translate(0,0)}90%{transform:translate(3px,-1px)}94%{transform:translate(-2px,1px)}}

/* 页签 */
.auth-tabs{display:flex;gap:3px;padding:3px;border-radius:6px;background:rgba(4,12,22,.7);
  border:1px solid rgba(0,229,255,.16);margin-bottom:22px}
.auth-tabs button{flex:1;padding:9px;border:0;border-radius:3px;background:none;color:#6f88a5;
  font-family:var(--mono);font-size:12px;letter-spacing:2px;cursor:pointer;transition:.2s}
.auth-tabs button:hover{color:#cfe6ff}
.auth-tabs button.on{background:linear-gradient(120deg,var(--cy),#26a6ff);color:#031018;font-weight:700;
  box-shadow:0 0 20px -4px rgba(0,229,255,.9)}

/* 表单 */
.auth-form{display:flex;flex-direction:column;gap:13px}
.fld{display:flex;flex-direction:column;gap:6px;position:relative}
.fld>span{font-size:9.5px;letter-spacing:2.4px;color:#4e6d8d;text-transform:uppercase}
.fld::after{content:"";position:absolute;left:0;right:0;top:0;height:1px;opacity:0;pointer-events:none;
  background:linear-gradient(90deg,transparent,var(--cy),transparent)}
.fld:focus-within::after{animation:cyScan 1.8s ease-in-out infinite}
@keyframes cyScan{0%,100%{opacity:0;transform:translateY(0)}45%{opacity:.95;transform:translateY(30px)}}
.fld input,.fld select{width:100%;background:rgba(3,9,18,.78);border:1px solid rgba(0,229,255,.16);
  border-radius:4px;padding:11px 13px;color:#dff2ff;font-family:var(--mono);font-size:13px;outline:0;
  transition:.22s;color-scheme:dark;caret-color:var(--cy)}
.fld input::placeholder{color:#3c5570}
.fld select option{background:#071120;color:#dff2ff}
.fld select option:checked{background:var(--cy);color:#031018}
.fld input:focus,.fld select:focus{border-color:rgba(0,229,255,.75);background:rgba(0,229,255,.05);
  box-shadow:0 0 0 1px rgba(0,229,255,.35),0 0 22px -4px rgba(0,229,255,.6),inset 0 0 24px -14px rgba(0,229,255,.9)}
.mail-input,.pwd-input{display:flex;align-items:center;background:rgba(3,9,18,.78);
  border:1px solid rgba(0,229,255,.16);border-radius:4px;overflow:hidden;transition:.22s}
.mail-input:focus-within,.pwd-input:focus-within{border-color:rgba(0,229,255,.75);background:rgba(0,229,255,.05);
  box-shadow:0 0 0 1px rgba(0,229,255,.35),0 0 22px -4px rgba(0,229,255,.6)}
.mail-input input,.pwd-input input{border:0;background:none;border-radius:0;box-shadow:none!important}
.mail-input em{font-style:normal;font-size:12px;color:var(--cy);padding:0 13px;line-height:42px;
  border-left:1px solid rgba(0,229,255,.18);background:rgba(0,229,255,.07);white-space:nowrap;
  text-shadow:0 0 10px rgba(0,229,255,.5)}
.pwd-eye{flex:none;width:40px;height:40px;border:0;background:none;color:#4e6d8d;cursor:pointer;
  font-size:13px;transition:.2s}
.pwd-eye:hover,.pwd-eye.on{color:var(--cy);text-shadow:0 0 10px rgba(0,229,255,.9)}
.code-input,.city-input{display:flex;gap:8px}
.code-input input{flex:1}
.code-input button{flex:none;padding:0 14px;border-radius:4px;border:1px solid rgba(0,229,255,.4);
  background:rgba(0,229,255,.09);color:var(--cy);font-family:var(--mono);font-size:11.5px;cursor:pointer;
  transition:.2s;white-space:nowrap;letter-spacing:1px}
.code-input button:hover:not(:disabled){background:rgba(0,229,255,.2);box-shadow:0 0 16px -4px rgba(0,229,255,.9)}
.code-input button:disabled{opacity:.45;cursor:not-allowed;color:#4e6d8d;border-color:rgba(0,229,255,.14);background:rgba(0,229,255,.03)}
.city-input select{flex:1}
.city-input button{flex:none;padding:0 13px;border-radius:4px;border:1px solid rgba(0,229,255,.2);
  background:rgba(0,229,255,.05);color:#8fb2d4;font-family:var(--mono);font-size:11.5px;cursor:pointer;transition:.2s}
.city-input button:hover{color:var(--cy);border-color:rgba(0,229,255,.55);box-shadow:0 0 14px -4px rgba(0,229,255,.8)}
.fld-hint{font-size:10px;color:#4e6d8d;letter-spacing:.4px}
.auth-err{font-size:11.5px;color:#ff6b9d;min-height:16px;margin:-2px 0 0;letter-spacing:.4px;
  text-shadow:0 0 12px rgba(255,45,149,.5)}

/* 记住我 / 忘记密码 */
.auth-row{display:flex;align-items:center;justify-content:space-between;margin-top:-2px}
.ck{display:flex;align-items:center;gap:8px;cursor:pointer;font-size:11.5px;color:#7d93ad;user-select:none}
.ck input{position:absolute;opacity:0;width:0;height:0}
.ck i{width:14px;height:14px;border:1px solid rgba(0,229,255,.45);border-radius:2px;position:relative;
  transition:.2s;flex:none}
.ck:hover i{border-color:var(--cy);box-shadow:0 0 10px -2px rgba(0,229,255,.8)}
.ck input:checked + i{background:rgba(0,229,255,.18);border-color:var(--cy);box-shadow:0 0 12px -2px rgba(0,229,255,.9)}
.ck input:checked + i::after{content:"";position:absolute;left:4px;top:1px;width:4px;height:8px;
  border:solid var(--cy);border-width:0 2px 2px 0;transform:rotate(45deg);
  filter:drop-shadow(0 0 4px rgba(0,229,255,.9))}
.link-btn{background:none;border:0;color:#5f8fbd;font-family:var(--mono);font-size:11px;
  cursor:pointer;padding:0;opacity:.9;letter-spacing:.6px;transition:.2s}
.link-btn:hover{color:var(--cy);opacity:1;text-shadow:0 0 10px rgba(0,229,255,.8)}

/* 主按钮 */
.auth-submit{position:relative;display:flex;align-items:center;justify-content:center;gap:10px;
  margin-top:4px;padding:13px 20px;border:0;border-radius:4px;cursor:pointer;
  font-family:var(--mono);font-size:13px;font-weight:700;letter-spacing:4px;color:#031018;
  background:linear-gradient(110deg,var(--cy),#2a9dff 55%,#7ad7ff);
  clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px);
  box-shadow:0 0 26px -6px rgba(0,229,255,.85);
  transition:transform .16s,box-shadow .16s,filter .16s}
.auth-submit:hover{transform:translateY(-1px);box-shadow:0 0 38px -4px rgba(0,229,255,1);filter:brightness(1.08)}
.auth-submit:active{transform:translateY(1px) scale(.995);box-shadow:0 0 18px -6px rgba(0,229,255,.7)}
.auth-submit .btn-arrow{font-style:normal;font-size:14px;transition:transform .2s}
.auth-submit:hover .btn-arrow{transform:translateX(4px)}
.auth-submit.loading{pointer-events:none;filter:saturate(.5) brightness(.85)}
.auth-submit.loading .btn-arrow{animation:cySpin .9s linear infinite}
@keyframes cySpin{to{transform:rotate(360deg)}}

/* 第三方入口 */
.auth-providers{display:flex;align-items:center;gap:8px;margin-top:2px}
.ap-line{font-size:10px;letter-spacing:2px;color:#3f6b8f;flex:none}
.ap-btn{flex:1;padding:7px;border-radius:3px;border:1px solid rgba(0,229,255,.18);background:rgba(0,229,255,.04);
  color:#6f88a5;font-family:var(--mono);font-size:11px;cursor:pointer;transition:.2s;letter-spacing:1px}
.ap-btn:hover{color:var(--cy);border-color:rgba(0,229,255,.6);background:rgba(0,229,255,.12);
  box-shadow:0 0 16px -6px rgba(0,229,255,.9)}

.auth-legal{font-size:9.5px;color:#3f6b8f;line-height:1.8;text-align:center;margin-top:2px;letter-spacing:.3px}
.auth-skip{margin-top:16px;width:100%;background:none;border:0;color:#3f6b8f;font-family:var(--mono);
  font-size:11px;cursor:pointer;padding:8px;transition:.2s;letter-spacing:1px}
.auth-skip:hover{color:var(--cy);text-shadow:0 0 12px rgba(0,229,255,.8)}
.dev-code{margin-top:6px;padding:9px 12px;border-radius:4px;font-size:11px;color:#fcd34d;
  background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.25);font-family:var(--mono)}
.dev-code b{letter-spacing:2px;font-size:14px}
"""

# 1) 替换「登录层」整块（从标记到 dev-code 结束）
start = css.index("/* ---------- 登录层 ---------- */")
end_marker = ".dev-code b{letter-spacing:2px;font-size:14px}\n"
end = css.index(end_marker) + len(end_marker)
css = css[:start] + NEW + css[end:]

# 2) 删掉后面重复的 .auth-row / .link-btn 旧规则（已并入新块）
old_row = (".auth-row{display:flex;justify-content:flex-end;margin-top:-4px}\n"
           ".link-btn{background:none;border:0;color:var(--teal);font-family:inherit;font-size:11.5px;\n"
           "  cursor:pointer;padding:0;opacity:.85}\n"
           ".link-btn:hover{opacity:1;text-decoration:underline}\n")
if old_row in css:
    css = css.replace(old_row, "")
else:
    print("!! 未找到旧 .auth-row/.link-btn 规则")

# 3) 媒体查询里的登录层部分同步
old_mq = """@media(max-width:1080px){
  .auth-layer{grid-template-columns:1fr}
  .auth-visual{display:none}
  .auth-panel{padding:24px 20px}
  .auth-card{max-width:420px;margin:0 auto}
}"""
new_mq = """@media(max-width:1080px){
  .auth-layer{grid-template-columns:1fr}
  .auth-visual{display:none}
  .auth-panel{padding:24px 18px}
  .auth-card{max-width:430px;margin:0 auto}
}"""
if old_mq in css:
    css = css.replace(old_mq, new_mq)
else:
    print("!! 未找到 1080 媒体查询块")

# 4) 去掉旧的 .auth-visual-inner h2 字号覆盖
css = css.replace("  .auth-visual-inner h2{font-size:30px}\n", "")

P.write_text(css, encoding="utf-8")
print(f"OK  css={len(css)} bytes  剩余 auth-layer 规则数={css.count('.auth-layer{')}")
