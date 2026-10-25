"""把登录层样式从「赛博朋克」换成「暮色山河」：暖金 + 湖青 + 衬线，去掉网格/扫描线/故障字。"""
from pathlib import Path

P = Path(r"D:\文旅助手\web\css\style.css")
css = P.read_text(encoding="utf-8")

NEW = r"""/* ---------- 登录层 · 暮色山河 ---------- */
:root{--gd:#e0a86a;--gw:#6fc0b3;--gr:#d07a86;
  --serif:"Songti SC","STSong","Noto Serif SC","SimSun",Georgia,"Times New Roman",serif}

.auth-layer{position:fixed;inset:0;z-index:200;display:grid;grid-template-columns:1.05fr .95fr;
  background:#0a0b10;overflow:hidden}
.auth-layer.hidden{display:none}

/* 氛围层：暖光 / 浮尘 / 远山 */
.auth-glow{position:absolute;inset:0;z-index:0;pointer-events:none;
  background:
    radial-gradient(900px 620px at 8% 6%,rgba(224,168,106,.13),transparent 62%),
    radial-gradient(820px 600px at 94% 92%,rgba(111,192,179,.10),transparent 62%),
    radial-gradient(620px 460px at 62% 16%,rgba(208,122,134,.055),transparent 66%)}
.auth-ridges{position:absolute;left:0;right:0;bottom:0;width:100%;height:46%;z-index:1;pointer-events:none}
.auth-dust{position:absolute;inset:0;z-index:2;pointer-events:none;overflow:hidden}
.auth-dust i{position:absolute;width:3px;height:3px;border-radius:50%;
  background:rgba(244,214,168,.75);box-shadow:0 0 9px rgba(244,214,168,.7);
  animation:floatDust linear infinite}
@keyframes floatDust{
  0%{transform:translate3d(0,0,0);opacity:0}
  18%{opacity:.6}
  80%{opacity:.35}
  100%{transform:translate3d(26px,-150px,0);opacity:0}}

/* 左侧品牌区 */
.auth-visual{position:relative;overflow:hidden;display:flex;align-items:center;z-index:3}
.auth-slides{position:absolute;inset:0}
.auth-slide{position:absolute;inset:0;background-size:cover;background-position:center;opacity:0;
  transition:opacity 1.6s ease;transform:scale(1.06);filter:saturate(1.06) contrast(1.02) sepia(.14)}
.auth-slide.on{opacity:.42;transform:scale(1);transition:opacity 1.6s ease,transform 12s linear}
.auth-visual::after{content:"";position:absolute;inset:0;
  background:linear-gradient(90deg,rgba(10,11,16,.22),rgba(10,11,16,.84) 58%,rgba(10,11,16,.96)),
             linear-gradient(180deg,rgba(10,11,16,.3),rgba(10,11,16,.9))}
.auth-visual.no-photo::after{background:linear-gradient(90deg,rgba(10,11,16,.2),rgba(10,11,16,.72) 58%,rgba(10,11,16,.94))}
.auth-visual-inner{position:relative;z-index:2;padding:0 clamp(30px,4.5vw,72px);max-width:560px}
.auth-logo{width:58px;height:58px;border-radius:16px;display:grid;place-items:center;font-size:25px;
  color:#f0cf9a;background:linear-gradient(140deg,rgba(224,168,106,.2),rgba(111,192,179,.1));
  border:1px solid rgba(224,168,106,.4);margin-bottom:24px;
  box-shadow:0 0 34px -10px rgba(224,168,106,.65),inset 0 0 22px -12px rgba(224,168,106,.8)}
.auth-brandline{display:flex;align-items:baseline;gap:14px;margin-bottom:14px}
.auth-brandline .brk{font-family:var(--serif);font-size:34px;font-weight:600;letter-spacing:10px;color:#f7ecdd;
  text-shadow:0 2px 34px rgba(224,168,106,.4)}
.auth-brandline em{font-style:normal;font-size:12px;letter-spacing:4px;color:rgba(111,192,179,.92)}
.auth-visual-inner h2{font-family:var(--serif);font-size:clamp(30px,3.1vw,44px);font-weight:600;
  letter-spacing:5px;line-height:1.42;margin-bottom:30px;color:#f4e6d3;
  text-shadow:0 2px 40px rgba(224,168,106,.22)}
.auth-points{list-style:none;display:flex;flex-direction:column;gap:14px;margin-bottom:32px}
.auth-points li{display:flex;align-items:center;gap:12px;font-size:13px;color:#b3a795;letter-spacing:.6px}
.auth-points i{width:6px;height:6px;border-radius:1px;background:var(--gd);flex:none;transform:rotate(45deg);
  box-shadow:0 0 12px rgba(224,168,106,.85)}
.auth-stats{display:flex;gap:36px;padding-top:24px;border-top:1px solid rgba(224,168,106,.16)}
.auth-stats div{display:flex;flex-direction:column}
.auth-stats b{font-family:var(--serif);font-size:25px;font-weight:600;color:#f6e9d7;letter-spacing:1px}
.auth-stats span{font-size:10.5px;letter-spacing:2.6px;color:#7d7466;margin-top:3px}
.auth-credit{position:absolute;bottom:-64px;font-size:9.5px;color:rgba(255,255,255,.2);letter-spacing:1px}

/* 右侧卡片 */
.auth-panel{display:flex;align-items:center;justify-content:center;padding:34px 26px;overflow-y:auto;z-index:3;
  background:linear-gradient(180deg,rgba(10,11,16,.5),rgba(10,11,16,.86))}
.auth-card{width:100%;max-width:412px;position:relative;padding:32px 34px 26px;border-radius:20px;
  background:linear-gradient(165deg,rgba(30,26,23,.84),rgba(17,16,19,.78));
  border:1px solid rgba(224,168,106,.2);
  backdrop-filter:blur(20px) saturate(130%);
  box-shadow:0 0 0 1px rgba(255,255,255,.035) inset,0 40px 90px -40px #000,0 0 70px -36px rgba(224,168,106,.5)}
.auth-card::before{content:"";position:absolute;left:15%;right:15%;top:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(240,207,154,.6),transparent)}
.auth-corner{position:absolute;width:14px;height:14px;border:1px solid rgba(224,168,106,.6)}
.auth-corner.tl{left:-1px;top:-1px;border-right:0;border-bottom:0}
.auth-corner.tr{right:-1px;top:-1px;border-left:0;border-bottom:0}
.auth-corner.bl{left:-1px;bottom:-1px;border-right:0;border-top:0}
.auth-corner.br{right:-1px;bottom:-1px;border-left:0;border-top:0}
.auth-kicker{font-size:10.5px;letter-spacing:5px;color:rgba(224,168,106,.78);margin-bottom:10px}
.auth-head h3{font-family:var(--serif);font-size:31px;font-weight:600;letter-spacing:4px;color:#f6ead9}
.auth-head p{font-size:12px;color:#8f8474;margin-top:8px;margin-bottom:22px;letter-spacing:.6px}

/* 页签：下划线式 */
.auth-tabs{display:flex;gap:26px;padding:0;margin-bottom:24px;background:none;border:0;
  border-bottom:1px solid rgba(255,255,255,.08);border-radius:0}
.auth-tabs button{position:relative;background:none;border:0;padding:10px 2px 13px;color:#8b8073;
  font-family:var(--serif);font-size:16px;letter-spacing:4px;cursor:pointer;transition:.25s}
.auth-tabs button:hover{color:#dcc6a4}
.auth-tabs button.on{background:none;color:#f2d5a8;box-shadow:none}
.auth-tabs button.on::after{content:"";position:absolute;left:-4px;right:-4px;bottom:-1px;height:2px;
  background:linear-gradient(90deg,transparent,var(--gd),transparent)}

/* 表单 */
.auth-form{display:flex;flex-direction:column;gap:15px}
.fld{display:flex;flex-direction:column;gap:7px;position:relative}
.fld>span{font-size:11.5px;letter-spacing:2.4px;color:#9b8f7c}
.fld input,.fld select{width:100%;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.09);
  border-radius:10px;padding:12px 14px;color:#f2e9dc;font-family:inherit;font-size:13.5px;outline:0;
  transition:.25s;color-scheme:dark;caret-color:var(--gd)}
.fld input::placeholder{color:#4f4a44}
.fld select option{background:#14161d;color:#f2e9dc}
.fld select option:checked{background:var(--gd);color:#221a10}
.fld input:focus,.fld select:focus{border-color:rgba(224,168,106,.55);background:rgba(224,168,106,.05);
  box-shadow:0 0 0 3px rgba(224,168,106,.10),0 0 26px -12px rgba(224,168,106,.55)}
.mail-input,.pwd-input{display:flex;align-items:center;background:rgba(255,255,255,.035);
  border:1px solid rgba(255,255,255,.09);border-radius:10px;overflow:hidden;transition:.25s}
.mail-input:focus-within,.pwd-input:focus-within{border-color:rgba(224,168,106,.55);background:rgba(224,168,106,.05);
  box-shadow:0 0 0 3px rgba(224,168,106,.10),0 0 26px -12px rgba(224,168,106,.5)}
.mail-input input,.pwd-input input{border:0;background:none;border-radius:0;box-shadow:none!important}
.mail-input em{font-style:normal;font-size:12.5px;color:#e8c48a;padding:0 14px;line-height:44px;
  border-left:1px solid rgba(255,255,255,.08);background:rgba(224,168,106,.08);white-space:nowrap}
.pwd-eye{flex:none;width:42px;height:44px;border:0;background:none;color:#6f6659;cursor:pointer;
  font-size:13px;transition:.2s}
.pwd-eye:hover,.pwd-eye.on{color:var(--gd);text-shadow:0 0 12px rgba(224,168,106,.85)}
.code-input,.city-input{display:flex;gap:9px}
.code-input input{flex:1}
.code-input button{flex:none;padding:0 15px;border-radius:10px;border:1px solid rgba(224,168,106,.4);
  background:rgba(224,168,106,.09);color:#eec891;font-family:inherit;font-size:12.5px;cursor:pointer;
  transition:.22s;white-space:nowrap}
.code-input button:hover:not(:disabled){background:rgba(224,168,106,.18);box-shadow:0 0 18px -6px rgba(224,168,106,.8)}
.code-input button:disabled{opacity:.45;cursor:not-allowed;color:#6f6659;border-color:rgba(255,255,255,.08);background:rgba(255,255,255,.03)}
.city-input select{flex:1}
.city-input button{flex:none;padding:0 14px;border-radius:10px;border:1px solid rgba(255,255,255,.1);
  background:rgba(255,255,255,.04);color:#a89b86;font-family:inherit;font-size:12.5px;cursor:pointer;transition:.2s}
.city-input button:hover{color:var(--gd);border-color:rgba(224,168,106,.5);box-shadow:0 0 16px -6px rgba(224,168,106,.7)}
.fld-hint{font-size:10.5px;color:#6f6659}
.auth-err{font-size:12px;color:#e08a93;min-height:16px;margin:-2px 0 0}

/* 记住我 / 忘记密码 */
.auth-row{display:flex;align-items:center;justify-content:space-between;margin-top:-2px}
.ck{display:flex;align-items:center;gap:9px;cursor:pointer;font-size:12px;color:#8f8474;user-select:none}
.ck input{position:absolute;opacity:0;width:0;height:0}
.ck i{width:15px;height:15px;border:1px solid rgba(224,168,106,.45);border-radius:4px;position:relative;
  transition:.2s;flex:none}
.ck:hover i{border-color:var(--gd);box-shadow:0 0 12px -3px rgba(224,168,106,.85)}
.ck input:checked + i{background:rgba(224,168,106,.2);border-color:var(--gd);box-shadow:0 0 14px -3px rgba(224,168,106,.9)}
.ck input:checked + i::after{content:"";position:absolute;left:5px;top:2px;width:4px;height:8px;
  border:solid #f0cf9a;border-width:0 2px 2px 0;transform:rotate(45deg)}
.link-btn{background:none;border:0;color:#a3906f;font-family:inherit;font-size:12px;cursor:pointer;
  padding:0;opacity:.9;transition:.2s}
.link-btn:hover{color:var(--gd);opacity:1}

/* 主按钮：深底烫金，hover 时填金 */
.auth-submit{position:relative;display:flex;align-items:center;justify-content:center;gap:10px;
  margin-top:6px;padding:14px 20px;border:1px solid rgba(224,168,106,.5);border-radius:10px;cursor:pointer;
  font-family:inherit;font-size:13.5px;font-weight:600;letter-spacing:6px;color:#f2d5a8;
  background:linear-gradient(120deg,rgba(224,168,106,.16),rgba(224,168,106,.05));
  overflow:hidden;transition:color .25s,background .25s,box-shadow .25s,transform .16s}
.auth-submit::after{content:"";position:absolute;top:0;bottom:0;width:36%;left:-45%;
  background:linear-gradient(100deg,transparent,rgba(255,238,210,.3),transparent);
  transform:skewX(-18deg);transition:left .65s ease}
.auth-submit:hover{color:#241a0e;border-color:rgba(240,207,154,.92);
  background:linear-gradient(120deg,#eec891,#d59b58);box-shadow:0 14px 34px -16px rgba(224,168,106,.9)}
.auth-submit:hover::after{left:112%}
.auth-submit:active{transform:translateY(1px) scale(.995)}
.auth-submit .btn-arrow{font-style:normal;font-size:14px;transition:transform .2s}
.auth-submit:hover .btn-arrow{transform:translateX(4px)}
.auth-submit.loading{pointer-events:none;filter:saturate(.6) brightness(.92)}
.auth-submit.loading .btn-arrow{animation:cySpin .9s linear infinite}
@keyframes cySpin{to{transform:rotate(360deg)}}

/* 第三方入口 */
.auth-providers{display:flex;align-items:center;gap:9px;margin-top:4px}
.ap-line{font-size:10.5px;letter-spacing:2.4px;color:#6f6659;flex:none}
.ap-btn{flex:1;padding:8px;border-radius:9px;border:1px solid rgba(255,255,255,.09);background:rgba(255,255,255,.03);
  color:#8b8073;font-family:inherit;font-size:11.5px;cursor:pointer;transition:.2s}
.ap-btn:hover{color:#eec891;border-color:rgba(224,168,106,.5);background:rgba(224,168,106,.1);
  box-shadow:0 0 18px -8px rgba(224,168,106,.8)}

.auth-legal{font-size:10px;color:#6f6659;line-height:1.8;text-align:center;margin-top:4px}
.auth-skip{margin-top:18px;width:100%;background:none;border:0;color:#6f6659;font-family:inherit;
  font-size:12px;cursor:pointer;padding:8px;transition:.2s}
.auth-skip:hover{color:#eec891}
.dev-code{margin-top:6px;padding:9px 12px;border-radius:8px;font-size:11.5px;color:#f0cf9a;
  background:rgba(224,168,106,.1);border:1px solid rgba(224,168,106,.28)}
.dev-code b{letter-spacing:2px;font-size:14px}
"""

start = css.index("/* ---------- 登录层 · 赛博朋克 ---------- */")
end_marker = ".dev-code b{letter-spacing:2px;font-size:14px}\n"
end = css.index(end_marker) + len(end_marker)
css = css[:start] + NEW + css[end:]

# 媒体查询里的 auth 部分同步（字号随新风格微调）
css = css.replace("  .auth-panel{padding:24px 18px}\n  .auth-card{max-width:430px;margin:0 auto}",
                  "  .auth-panel{padding:24px 18px}\n  .auth-card{max-width:420px;margin:0 auto}")
css = css.replace("  .auth-card{padding:24px 20px 20px}\n  .auth-head h3{font-size:21px}",
                  "  .auth-card{padding:24px 20px 20px}\n  .auth-head h3{font-size:25px}")

P.write_text(css, encoding="utf-8")
print(f"OK  css={len(css)} bytes")
