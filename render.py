"""Render JD-evidence-based Beijing-first opportunities without deleting raw history."""
from collections import Counter
import html
import json
from pathlib import Path
import shutil
import re
from jd_match import classify

LABELS = {"new":"新发现开放","open":"仍在招聘","closed":"已关闭","unverified":"待核实"}
E = lambda v: html.escape(str(v if v is not None else "未说明"), quote=True)

def is_beijing(job):
    """Only explicitly listed work locations qualify as Beijing."""
    return bool(re.search(r"北京|\bbeijing\b|\bpeking\b", job.get("location",""), re.I))

def is_other_city(job):
    loc = job.get("location","")
    return not is_beijing(job) and bool(loc.strip()) and not re.search(r"待核实|未知|remote|中国\s*$|China\s*$",loc,re.I)

def enrich(job):
    result = dict(job)
    result.update(classify(result))
    return result

def card(j):
    status=j.get("status","unverified")
    ev=j.get("closure_evidence",{}) if status=="closed" else j.get("evidence",{})
    grade=j.get("match_grade","U")
    gaps="；".join(j.get("skill_gaps",[])) or "未发现已证实的关键冲突；具体能力仍须核实"
    skills="、".join(j.get("hard_skills",[])) or "未说明"
    first=(j.get("first_seen") or "")[:10] or "未说明"
    opened=(j.get("recommended_at") or "")[:10] or "未确认"
    lastopen=(j.get("last_confirmed_open") or "")[:10] or "未确认"
    checked=(j.get("last_checked") or ev.get("checked_at") or "")[:19].replace("T"," ")
    deadline=j.get("deadline") or "未说明"
    source=j.get("jd_source_url") or j.get("url","")
    href=E(j.get("url","#"))
    search=E(" ".join(str(j.get(k,"")) for k in ("title","company","location","conditions","reasons","industry","priority_direction","major_evidence")))
    city="北京" if is_beijing(j) else "其他城市"
    grade_label={"A":"A · 材料专业明确接受","B":"B · 相关理工科待确认","C":"C · 低匹配","U":"资格待核实"}.get(grade,"资格待核实")
    if status=="closed":
        dates=f'首次推荐 {E(opened)} · 最后确认开放 {E(lastopen)} · 关闭核实 {E((j.get("closed_at") or "")[:10])}'
    else:
        dates=f'首次发现 {E(first)} · 首次确认开放 {E(opened)}'
    return f'''<article class="job" data-status="{E(status)}" data-grade="{E(grade)}" data-industry="{E(j.get("industry","待核实"))}" data-city="{E(city)}" data-search="{search}">
    <div class="job-top"><span class="company">{E(j.get("company","待核实"))}</span><span class="badge {E(status)}">{E(LABELS.get(status,status))}</span></div>
    <h3><a href="{href}" target="_blank" rel="noopener noreferrer">{E(j.get("title","未说明"))} ↗</a></h3>
    <p class="location">⌖ {E(j.get("location","待核实"))} · {E(j.get("industry","待核实"))} · {E(j.get("priority_direction",""))}</p>
    <p class="fit-grade"><strong>{E(grade_label)}</strong>　{E(j.get("major_eligibility","未说明"))}</p>
    <div class="jd-fields"><p><b>学历</b> {E(j.get("degree_requirement","未说明"))}　<b>毕业届别</b> {E(j.get("graduation_requirement","未说明"))}</p>
    <p><b>实习/出勤</b> {E(j.get("attendance_requirement","未说明"))}　<b>语言</b> {E(j.get("language_requirement","未说明"))}</p>
    <p><b>JD技能关键词</b> {E(skills)}　<b>截止日</b> {E(deadline)}</p>
    <p><b>专业合格依据</b> {E(j.get("major_eligibility","待核实"))}</p>
    <p><b>技能匹配</b> {E(j.get("skill_fit","待核实"))}</p>
    <p><b>技能/硬性条件缺口</b> {E(gaps)}</p></div>
    <details class="evidence"><summary>JD专业要求原文及职位级证据 · {E(checked)}（北京时间）</summary>
    <p><b>JD原文摘录：</b>{E(j.get("major_evidence","未说明/待核实"))}</p>
    <p><b>JD来源说明：</b>{E(j.get("jd_source_note","职位级JD原文及来源见链接；未说明项不推定满足"))}</p>
     <p><b>状态证据：</b>{E(ev.get("excerpt","未取得职位级证据"))}</p>
    <a href="{E(source)}" target="_blank" rel="noopener noreferrer">JD原始职位链接 ↗</a> ·
    <a href="{E(ev.get("url",source))}" target="_blank" rel="noopener noreferrer">状态证据链接 ↗</a></details>
    <div class="job-foot"><span>{dates} · 核实 {E(checked)}</span><a href="{href}" target="_blank" rel="noopener noreferrer">查看/投递 →</a></div></article>'''

def build(root):
    data=root/"data";out=root/"docs";out.mkdir(exist_ok=True)
    latest=json.loads((data/"latest.json").read_text(encoding="utf-8"))
    all_jobs=[enrich(j) for j in latest["jobs"]]
    bj=[j for j in all_jobs if is_beijing(j)]
    primary=sorted((j for j in bj if j["match_grade"] in ("A","B")),key=lambda j:(j["priority_order"],j["match_grade"]!="A",-j.get("score",0)))
    unresolved=[j for j in bj if j["match_grade"]=="U"]
    low=[j for j in bj if j["match_grade"]=="C"]
    other=sorted((j for j in all_jobs if is_other_city(j) and j["match_grade"] in ("A","B") and j["status"] in ("new","open","unverified")),key=lambda j:(j["priority_order"],j["match_grade"]!="A"))[:8]
    counts=Counter(j["status"] for j in primary)
    statuses="".join(f'<button type="button" class="status-filter" data-filter="{s}" aria-pressed="false"><span class="dot {s}"></span>{label}<b>{counts[s]:02d}</b></button>' for s,label in LABELS.items())
    hints={"new":"首次被本系统确认开放，并不代表当天发布。","open":"本系统此前确认开放，本轮再次核实。","closed":"此前确认开放，后来取得具体职位关闭证据。","unverified":"专业适配A/B，但本轮开放状态未能确认。"}
    groups=""
    for status,label in LABELS.items():
        subset=[j for j in primary if j["status"]==status]
        groups+=f'<section class="job-section" data-group="{status}" id="{status}"><div class="section-title"><h2>{label} · A/B <span>{len(subset):02d}</span></h2><p>{hints[status]}</p></div><div class="job-grid">'+("".join(card(j) for j in subset) if subset else '<p class="empty">暂无符合A/B专业证据的岗位。</p>')+"</div></section>"
    groups+=f'<section class="job-section" id="pending-major"><div class="section-title"><h2>北京 · JD专业资格待核实 <span>{len(unresolved):02d}</span></h2><p>缺少JD任职/专业证据，不能自动认定A或B；原有职位状态不因此被判定关闭。</p></div><div class="job-grid">'+("".join(card(j) for j in unresolved) if unresolved else '<p class="empty">暂无。</p>')+"</div></section>"
    groups+=f'<section class="job-section" id="other-city"><div class="section-title"><h2>其他城市补充 · A/B <span>{len(other):02d}</span></h2><p>独立展示少量高匹配职位（包括待核实线索），不计入北京岗位数量；待核实不等于开放。</p></div><div class="job-grid">'+("".join(card(j) for j in other) if other else '<p class="empty">本轮暂无已确认开放的A/B其他城市补充。</p>')+"</div></section>"
    groups+=f'<details class="lowmatch"><summary>北京低匹配 C 类历史岗位（{len(low)} 条，不占主要推荐位）</summary><div class="job-grid">'+("".join(card(j) for j in low) if low else '<p class="empty">暂无。</p>')+"</div></details>"
    history="";days=sorted((data/"history").glob("*.json"),reverse=True)
    for path in days:
        day=json.loads(path.read_text(encoding="utf-8"));runs=day["runs"]
        snap=json.loads((data/"runs"/(runs[-1]+".json")).read_text(encoding="utf-8"))
        visible=[enrich(j) for j in snap["jobs"] if is_beijing(j)]
        c=Counter(j["status"] for j in visible if j["match_grade"] in ("A","B"))
        events=[]
        for j in visible:
            for ev in j.get("events",[]):
                if ev.get("at","")[:10]==day["date"] and ev.get("to") in ("new","closed"):
                    events.append((j,ev))
        changed="".join(f'<tr><td>{E(ev.get("at","")[:19])}</td><td>{E(LABELS.get(ev.get("to"),ev.get("to")))}</td><td>{E(j.get("company",""))} · <a href="{E(j.get("url","#"))}">{E(j.get("title",""))}</a></td></tr>' for j,ev in events)
        rows="".join(f'<tr><td><span class="badge {E(j["status"])}">{E(LABELS[j["status"]])}</span> / {E(j["match_grade"])}</td><td><a href="{E(j["url"])}" target="_blank" rel="noopener noreferrer">{E(j["title"])}</a><small>{E(j.get("company",""))}</small></td><td>{E(j.get("location","待核实"))}</td></tr>' for j in visible)
        runlinks="".join(f'<a href="data/runs/{E(r)}.json">{E(r.split("-")[0][9:11]+":"+r.split("-")[0][11:13])} 原始快照 ↗</a>' for r in reversed(runs))
        history+=f'<details class="history-day"><summary><span class="history-date">{E(day["date"])}</span><span>北京A/B：{" · ".join(f"{LABELS[s]} {c[s]}" for s in LABELS)}</span><span>{len(runs)} 次运行 <i>＋</i></span></summary><div class="history-content"><p>当日北京职位及A/B适配状态（历史分类按当前规则重新计算，原始快照不修改）。</p><h3>当日首次开放/确认关闭事件</h3><div class="table-wrap"><table><tbody>{changed or "<tr><td>无新增或关闭证据事件</td></tr>"}</tbody></table></div><h3>当日最后快照</h3><div class="table-wrap"><table><thead><tr><th>状态/专业</th><th>职位/公司</th><th>工作地点</th></tr></thead><tbody>{rows}</tbody></table></div><div class="runlinks">{runlinks}</div></div></details>'
    health="".join(f'<li><span class="health-dot {"ok" if h["ok"] else "fail"}"></span><div><a href="{E(h["url"])}" target="_blank" rel="noopener noreferrer">{E(h["source"])}</a><small>{E(h["message"])} · 扫描 {h["scanned"]} / 线索 {h["candidates"]}</small></div></li>' for h in latest["sources"])
    good=sum(h["ok"] for h in latest["sources"]);total=len(latest["sources"])
    state="检索已完成" if good==total else ("部分来源需核实" if good else "本轮来源访问异常")
    stamp=E(latest["generated_at"].replace("T"," ")[:19])
    page=(TEMPLATE.replace("@@STATUS@@",statuses).replace("@@GROUPS@@",groups).replace("@@HISTORY@@",history)
        .replace("@@HEALTH@@",health).replace("@@STAMP@@",stamp).replace("@@STATE@@",state)
        .replace("@@GOOD@@",str(good)).replace("@@TOTAL@@",str(total)).replace("@@DAYS@@",str(len(days)))
        .replace("@@COUNT@@",str(len(primary))))
    (out/"index.html").write_text(page,encoding="utf-8");(out/".nojekyll").touch()
    shutil.copytree(data,out/"data",dirs_exist_ok=True)
    print(f"Built docs/index.html: Beijing A/B {len(primary)}, other cities {len(other)}, pending JD {len(unresolved)}, C {len(low)}, history {len(days)} days.")
    
TEMPLATE='''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><meta name="description" content="北京半导体与汽车实习每日监测。面向材料工程硕士与能源动力本科，职位来源可查，历史按日归档。"><title>芯途 · 北京半导体与汽车实习监测</title>
<style>
:root{--ink:#17362e;--muted:#687d73;--line:#dae2d8;--paper:#f5f6ef;--green:#244f3e;--lime:#d3ee8c;--orange:#b35a2c}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;font-size:14px;line-height:1.6}a{color:inherit;text-decoration:none}a:hover{text-decoration:underline}button,input{font:inherit}button,a,input,summary{outline-offset:4px}header{border-bottom:1px solid var(--line)}.nav{max-width:1240px;margin:auto;padding:22px 32px;display:flex;justify-content:space-between;align-items:center;gap:20px}.logo{font-size:21px;font-weight:750;letter-spacing:1px;display:flex;gap:12px;align-items:center}.mark{width:30px;height:30px;display:grid;place-items:center;border:1px solid var(--ink);border-radius:8px;font-size:19px}.navlinks{display:flex;gap:24px;font-size:13px}.navlinks a:last-child{color:var(--muted)}main{max-width:1240px;margin:0 auto;padding:0 32px 72px}.hero{display:grid;grid-template-columns:1.45fr 1fr;gap:60px;padding:57px 0 36px;align-items:center}.eyebrow{font-size:11px;letter-spacing:2.4px;color:var(--muted);font-weight:600}.hero h1{font-size:clamp(30px,4.2vw,49px);line-height:1.3;letter-spacing:-1.5px;margin:18px 0 17px;font-weight:650}.hero h1 em{font-style:normal;border-bottom:5px solid var(--lime)}.intro{max-width:530px;color:var(--muted);font-size:14px;line-height:1.9}.focus{display:flex;gap:9px;margin-top:20px;flex-wrap:wrap}.focus span{border:1px solid #c8d4c1;border-radius:20px;padding:4px 12px;font-size:11px}.wafer{height:223px;position:relative;border-radius:16px;background:var(--green);overflow:hidden;display:flex;align-items:center;justify-content:center}.wafer svg{height:290px;position:absolute;right:-20px;top:-30px;width:290px;opacity:.7;transform:rotate(-20deg)}.wafer-label{position:absolute;bottom:23px;left:26px;color:#e1eccd;font-family:monospace;font-size:10px;letter-spacing:1px}.wafer-note{position:absolute;top:25px;left:26px;color:var(--lime);font-size:11px;line-height:1.9;letter-spacing:1px}.update{display:flex;justify-content:space-between;gap:20px;align-items:center;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:14px 0;margin-bottom:26px;font-size:12px;color:var(--muted)}.update strong{color:var(--green);font-weight:550}.live{display:inline-block;width:6px;height:6px;background:#6e9a46;border-radius:50%;margin-right:7px}.schedule{font-family:monospace;letter-spacing:.4px}.status-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:32px}.status-filter{background:#fffdf7;border:1px solid var(--line);border-radius:10px;padding:19px 20px;display:flex;align-items:center;gap:8px;color:var(--ink);text-align:left;cursor:pointer;transition:.2s}.status-filter b{font-weight:500;font-size:27px;margin-left:auto;font-family:monospace}.status-filter:hover,.status-filter[aria-pressed=true]{border-color:var(--green);box-shadow:0 0 0 1px var(--green)}.dot{width:7px;height:7px;border-radius:50%}.dot.new{background:#6a8e37}.dot.open{background:#368a71}.dot.closed{background:#939b95}.dot.unverified{background:#c78745}.workspace{display:flex;justify-content:space-between;align-items:center;gap:20px;margin:0 0 28px}.workspace h2{font-size:18px;margin:0;display:inline}.workspace small{color:var(--muted);margin-left:9px;font-size:11px}.filters{display:flex;gap:10px;align-items:center}.search{border:1px solid var(--line);background:transparent;border-radius:7px;padding:8px 12px;width:230px}.beijing{display:flex;gap:6px;font-size:12px;white-space:nowrap}.reset{background:var(--green);color:white;border:0;padding:9px 13px;border-radius:7px;cursor:pointer}.section-title{display:flex;align-items:baseline;gap:18px;margin:28px 0 13px}.section-title h2{font-size:15px;font-weight:600;margin:0;white-space:nowrap}.section-title h2 span{color:var(--muted);font-family:monospace;font-size:12px;margin-left:6px}.section-title p{margin:0;color:var(--muted);font-size:11px}.job-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.job{padding:23px;background:#fffef9;border:1px solid var(--line);border-radius:10px;min-width:0}.job-top{display:flex;align-items:center;justify-content:space-between;gap:12px}.company{font-size:11px;color:var(--muted);letter-spacing:.2px}.badge{font-size:10px;display:inline-block;padding:3px 8px;border-radius:4px;white-space:nowrap}.badge.new{background:#e9f1d9;color:#56772d}.badge.open{background:#e0eee6;color:#2f7054}.badge.closed{background:#eeefea;color:#7b847e}.badge.unverified{background:#f5eadb;color:#9a6b34}.job h3{font-size:18px;margin:14px 0 5px;line-height:1.5;font-weight:600}.job h3 span{font-size:14px;color:#83937b}.location{font-size:12px;color:var(--muted);margin:7px 0 13px}.tags{display:flex;flex-wrap:wrap;gap:5px}.tags span{padding:3px 7px;font-size:10px;background:#f0f2e9;color:#63734f;border-radius:3px}.conditions{font-size:12px;line-height:1.8;color:#69796c;margin:16px 0;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}.evidence{border-top:1px dashed var(--line);padding:12px 0;font-size:11px}.evidence summary{cursor:pointer;color:#65785f}.evidence summary span{float:right;font-size:9px;color:#8c9588}.evidence p{overflow-wrap:anywhere;color:var(--muted)}.evidence a{text-decoration:underline}.job-foot{display:flex;justify-content:space-between;gap:10px;font-size:9px;color:#8c968b;border-top:1px solid var(--line);padding-top:12px;margin-top:2px}.job-foot a{font-size:11px;color:var(--green);white-space:nowrap}.empty{grid-column:1/-1;border:1px dashed var(--line);border-radius:8px;padding:18px;color:var(--muted);font-size:12px;margin:0}.archive{margin-top:54px;border-top:1px solid var(--line);padding-top:32px}.archive-top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:18px}.archive-top h2{font-size:22px;font-weight:550;margin:0}.archive-top p{font-size:12px;color:var(--muted)}.history-day{border-bottom:1px solid var(--line)}.history-day>summary{cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:18px;padding:20px 0;list-style:none;font-size:11px;color:var(--muted)}.history-date{font-family:monospace;font-size:17px;color:var(--ink)}.history-day i{font-style:normal;margin-left:15px}.history-content{padding:0 0 20px}.history-content>p{font-size:11px;color:var(--muted)}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;text-align:left;font-size:12px}td,th{padding:12px 14px;border-bottom:1px solid var(--line)}th{font-size:10px;color:var(--muted);font-weight:400}td small{display:block;color:var(--muted);font-size:10px;margin-top:3px}.runlinks{display:flex;gap:15px;flex-wrap:wrap;margin-top:15px;font-size:11px;text-decoration:underline}.method{display:grid;grid-template-columns:1fr 1fr;gap:38px;margin-top:38px;padding:28px;background:#ecefe3;border-radius:10px}.method h2{font-size:14px;margin:0 0 12px}.method p{color:#65745d;font-size:12px;line-height:1.9}.health{margin:0;padding:0;list-style:none}.health li{display:flex;gap:8px;margin:10px 0}.health a{font-size:11px}.health small{display:block;font-size:10px;color:#839078;line-height:1.6}.health-dot{height:5px;width:5px;border-radius:50%;margin-top:7px;flex-shrink:0}.ok{background:#5b853b}.fail{background:#b78547}.source-health{margin:10px 0}.source-health>summary{cursor:pointer;font-size:12px}.footer{border-top:1px solid var(--line);padding:23px 0 0;margin-top:36px;display:flex;justify-content:space-between;gap:15px;font-size:10px;color:var(--muted)}[hidden]{display:none!important}.no-results{color:var(--muted);padding:18px;border:1px dashed var(--line);border-radius:8px}.freshness{font-size:12px;background:#fff0d5;border:1px solid #e7c689;padding:12px;border-radius:6px;margin-bottom:20px}.skip{position:absolute;left:-9999px}.skip:focus{left:10px;top:10px;z-index:2;background:white;padding:8px}
@media(max-width:850px){.hero{gap:30px}.wafer{height:210px}.status-grid{gap:8px}.status-filter{padding:14px 12px;font-size:12px}.status-filter b{font-size:22px}.workspace{align-items:flex-start;flex-direction:column}.filters{width:100%;flex-wrap:wrap}.search{flex:1}.job-grid{grid-template-columns:1fr}.method{grid-template-columns:1fr;gap:20px}.history-day>summary{flex-wrap:wrap}.section-title{align-items:flex-start;flex-direction:column;gap:5px}}@media(max-width:580px){.nav{padding:18px 20px}.navlinks{gap:14px;font-size:11px}.navlinks a:last-child{display:none}main{padding:0 20px 45px}.hero{display:block;padding-top:32px}.hero h1{font-size:35px}.wafer{display:none}.update{display:block;font-size:10px}.schedule{display:block;margin-top:6px}.status-grid{grid-template-columns:1fr 1fr}.workspace small{display:block;margin:4px 0 0}.job{padding:19px}.job h3{font-size:17px}.job-foot{flex-direction:column}.evidence summary span{float:none;display:block}.archive-top{display:block}.footer{flex-direction:column}.history-day>summary>span:nth-child(2){order:3;width:100%;font-size:10px}}
.fit-grade{background:#e9f2dc;border-left:3px solid #73985a;padding:9px 11px;font-size:12px}.jd-fields{font-size:12px;color:var(--muted);line-height:1.7}.jd-fields p{margin:5px 0}.jd-fields b{color:var(--ink)}.filters select{background:white;color:var(--ink);border:1px solid var(--line);padding:9px 7px;border-radius:7px;max-width:180px}.lowmatch{margin:32px 0;border:1px solid var(--line);border-radius:12px;padding:16px}.lowmatch>summary{cursor:pointer;font-weight:600}.lowmatch .job-grid{margin-top:15px}.job[hidden],.job-section[hidden],.lowmatch[hidden]{display:none!important}@media(max-width:850px){.filters select{max-width:100%;flex:1}}</style></head><body><a class="skip" href="#opportunities">跳到岗位</a><header><nav class="nav"><a class="logo" href="#"><span class="mark">▦</span>芯途 <span style="font-size:10px;font-weight:400;letter-spacing:1px;color:var(--muted)">INTERNSHIP TRACKER</span></a><div class="navlinks"><a href="#opportunities">实习机会</a><a href="#history">监测历史</a><a href="https://github.com/4ghan1m/semiconductor-internship-tracker" target="_blank" rel="noopener noreferrer">GitHub ↗</a></div></nav></header>
<main><section class="hero"><div><div class="eyebrow">BEIJING / SEMICONDUCTOR + AUTOMOTIVE</div><h1>下一站，<br>从<em>材料</em>走向芯片与汽车。</h1><p class="intro">持续发现半导体与汽车行业的北京实习机会，关注材料工程硕士与能源动力本科。让每一条推荐有据可查，让每一次状态变化留下记录。</p><div class="focus"><span>⌖ 北京优先 · 其他城市A/B补充</span><span>材料工程硕士</span><span>材料研发 · 工艺 · 热管理 · 电池 · 质量测试 · AI+材料</span></div></div><div class="wafer" aria-hidden="true"><span class="wafer-note">从研究室<br>到晶圆厂。</span><svg viewBox="0 0 300 300"><defs><pattern id="grid" width="22" height="28" patternUnits="userSpaceOnUse"><rect x="2" y="2" width="18" height="24" rx="1" fill="none" stroke="#b9d99b" stroke-width=".6"/></pattern><clipPath id="circle"><circle cx="150" cy="150" r="133"/></clipPath></defs><circle cx="150" cy="150" r="137" fill="none" stroke="#b9d99b" stroke-width=".7"/><circle cx="150" cy="150" r="133" fill="url(#grid)"/><path d="M141 283L150 273L159 283" stroke="#d3ee8c" fill="#244f3e"/></svg><span class="wafer-label">MATERIALS → PROCESS → POSSIBILITY</span></div></section>
<div class="update"><span><span class="live"></span><strong>@@STATE@@</strong> · 最后更新 @@STAMP@@（北京时间）</span><span class="schedule">每日 05:00 CST / @@GOOD@@ / @@TOTAL@@ 来源可用</span></div><div id="stale" class="freshness" role="status" hidden>页面已有超过 36 小时未更新，请查看 GitHub Actions 运行状态；历史推荐需重新核实。</div>
<div class="status-grid" aria-label="按岗位状态筛选">@@STATUS@@</div><div class="workspace" id="opportunities"><div><h2>今日岗位观察</h2><small>北京 A/B 优先 · 半导体材料/工艺 → 材料+AI → 相关工程 · @@COUNT@@ 条记录</small></div><div class="filters"><input class="search" id="search" type="search" placeholder="搜索岗位、公司或方向…" aria-label="搜索岗位、公司或方向"><select id="industry" aria-label="行业"><option value="all">全部行业</option><option value="半导体">半导体</option><option value="汽车">汽车</option></select><select id="city" aria-label="城市"><option value="all">全部城市</option><option value="北京">北京</option><option value="其他城市">其他城市补充</option></select><select id="grade" aria-label="专业匹配"><option value="all">全部专业等级</option><option value="A">A 明确材料</option><option value="B">B 相关理工</option><option value="U">资格待核实</option><option value="C">C 低匹配</option></select><button class="reset" id="reset" type="button">重置筛选</button></div></div><p id="no-results" class="no-results" hidden>当前筛选没有匹配岗位，试试其他关键词。</p>@@GROUPS@@
<section class="archive" id="history"><div class="archive-top"><h2>每一天，都有迹可循。</h2><p>@@DAYS@@ 个真实监测日期 · 日期倒序 · 同日运行独立保存</p></div>@@HISTORY@@</section>
<section class="method"><div><h2>推荐与状态，如何确认？</h2><p>“新发现开放”指本系统首次取得实时开放证据；后续复核仍开放，归为“仍在招聘”。匹配理由用于排序，具体专业、学历及出勤要求请以原职位为准。</p><p>“已关闭”只收录此前在本系统推荐且确认开放、后来取得明确关闭证据的岗位。搜索消失、404、登录墙和网络错误均转为待核实；从未推荐过的关闭岗位不入库。</p><p>每天北京时间 05:00 由 GitHub Actions 检索并更新此页面。平台调度可能延迟。所有快照保存到仓库，页面北京优先、另设其他城市A/B补充；各城市完整历史、证据及每次运行数据均保留。</p><a href="data/latest.json" style="font-size:11px;text-decoration:underline">下载本轮完整数据 ↗</a></div><div><h2>来源与本轮检索情况</h2><p>官方招聘库持续扫描，中文网页搜索补充北京半导体与汽车材料、工艺、热管理、电池、质量测试和 AI+材料线索。检索范围受公开来源和访问条件限制，不代表全网完整覆盖。</p><details class="source-health"><summary>查看 @@TOTAL@@ 个检索来源（@@GOOD@@ 个可用）</summary><ul class="health">@@HEALTH@@</ul></details><p>每条岗位卡片可展开核实依据。访问异常会如实记录，并保留既有岗位与历史。</p></div></section><footer class="footer"><span>芯途 · Beijing Semiconductor + Automotive Internship Tracker</span><a href="https://github.com/4ghan1m/semiconductor-internship-tracker/actions" target="_blank" rel="noopener noreferrer">查看自动更新状态 ↗</a><span>为材料工程的下一步，保留线索。</span></footer></main>
<script>
(()=>{let state='all';const q=document.getElementById('search'),industry=document.getElementById('industry'),city=document.getElementById('city'),grade=document.getElementById('grade'),buttons=[...document.querySelectorAll('[data-filter]')],jobs=[...document.querySelectorAll('.job')];function filter(){const term=q.value.trim().toLocaleLowerCase();let total=0;jobs.forEach(j=>{j.hidden=!((state==='all'||j.dataset.status===state)&&(industry.value==='all'||j.dataset.industry===industry.value)&&(city.value==='all'||j.dataset.city===city.value)&&(grade.value==='all'||j.dataset.grade===grade.value)&&j.dataset.search.toLocaleLowerCase().includes(term));if(!j.hidden)total++});document.querySelectorAll('.job-section').forEach(s=>{const any=[...s.querySelectorAll('.job')].some(j=>!j.hidden);s.hidden=!any&&!!(term||state!=='all'||industry.value!=='all'||city.value!=='all'||grade.value!=='all')});buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.filter===state)));document.getElementById('no-results').hidden=total>0}buttons.forEach(b=>b.addEventListener('click',()=>{state=state===b.dataset.filter?'all':b.dataset.filter;filter()}));[q,industry,city,grade].forEach(el=>el.addEventListener(el===q?'input':'change',filter));document.getElementById('reset').addEventListener('click',()=>{state='all';q.value='';industry.value='all';city.value='all';grade.value='all';filter()});if(Date.now()-new Date('@@STAMP@@'.replace(' ','T')+'+08:00').getTime()>36*3600000)document.getElementById('stale').hidden=false;})();
</script></body></html>'''

if __name__=='__main__':build(Path(__file__).resolve().parent)
