"""Evidence-based internship discovery. No API keys or LLM required."""
import argparse
import concurrent.futures as cf
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urljoin, urlunparse, parse_qsl, urlencode
import uuid
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
CST = timezone(timedelta(hours=8))
LABELS = {"new":"新发现开放", "open":"仍在招聘", "closed":"已关闭", "unverified":"待核实"}
INTERN = re.compile(r"\bintern(?:ship)?s?\b|实习", re.I)
NONTECH = re.compile(r"finance|accountant|purchasing|human.resources|\bHR\b|legal|strategy|财务|会计|采购|人力|法务|战略",re.I)
MATERIAL = re.compile(r"材料|薄膜|刻蚀|沉积|表征|封装|失效分析|工艺|制程|化学|物理|晶圆|\bmaterials?\b|thin.film|\betch\w*|deposition|characteri[sz]|packaging|failure.analysis|\bprocess\b|chemistry|physics|wafer|metrology", re.I)
CHINA = re.compile(r"China|\bCHN\b|中国|北京|上海|天津|无锡|苏州|西安|成都|深圳|杭州|武汉|合肥|大连|Beijing|Shanghai|Tianjin|Wuxi|Suzhou|Xi.an|Chengdu|Shenzhen|Hangzhou|Wuhan|Hefei|Dalian", re.I)
SEMI = re.compile(r"半导体|芯片|晶圆|集成电路|semiconductor|wafer|microelectronic|自旋电子|MRAM|薄膜|刻蚀", re.I)
CLOSED = re.compile(r"职位[已]?关闭|招聘[已]?结束|停止招聘|已下线|该职位已结束|不再接受[申请投递]|no longer (?:available|accepting applications)|job (?:has been|is) (?:filled|closed)|position (?:has been|is) (?:filled|closed)", re.I)


def session():
    s = requests.Session()
    s.headers.update({"User-Agent":"Mozilla/5.0 (compatible; SemiconductorInternshipTracker/1.0; +https://github.com/4ghan1m/semiconductor-internship-tracker)", "Accept-Language":"zh-CN,zh;q=0.9,en;q=0.8"})
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1, status_forcelist=[429,500,502,503,504])))
    return s


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else copy.deepcopy(default)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def text(html):
    soup = BeautifulSoup(html or "", "html.parser")
    for node in soup(["script","style","nav","footer"]):
        node.decompose()
    return " ".join(soup.stripped_strings)


def evidence(state, url, excerpt, method, at):
    return {"state":state,"url":url,"excerpt":excerpt[:700],"method":method,"checked_at":at}


def fit(title, description, location):
    # Match requirements separately: boilerplate company introductions must not imply degree eligibility.
    reasons = []
    score = 0
    req = qualification_excerpt(description)
    if re.search(r"北京|Beijing", location, re.I):
        score += 50; reasons.append("北京岗位")
    hits = sorted(set(m.group(0).lower() for m in MATERIAL.finditer(title)))
    if hits:
        score += 35; reasons.append("岗位方向：" + " / ".join(hits[:4]))
    elif re.search(r"材料|\bmaterials?\b|\bphysics\b|\bchemistry\b",req,re.I):
        score += 15; reasons.append("任职条件涉及材料 / 物理 / 化学相关方向")
    if re.search(r"硕士|master|graduate student|postgraduate", req, re.I):
        score += 15; reasons.append("任职条件提及硕士 / 研究生")
    if re.search(r"ph\.?d.{0,30}(?:required|only)|博士.{0,10}(?:仅限|必须)", req, re.I):
        score -= 50; reasons.append("可能要求博士，需核实学历")
    if re.search(r"software|compiler|GPU|firmware|AI Application|软件",title,re.I) and not hits:
        score -= 25; reasons.append("偏软件 / 芯片设计，材料专业需核对技能门槛")
    return score, reasons or ["半导体行业实习，专业资格需逐项核对"]


def workday_url(source, path):
    return f"https://{source['host']}/en-US/{source['board']}{path}"


def wd_observe(source, posting, at):
    base = f"https://{source['host']}/wday/cxs/{source['tenant']}/{source['board']}"
    path = posting["externalPath"]
    url = workday_url(source, path)
    jid = posting.get("bulletFields", [path])[-1]
    job = {"id":f"{source['id']}:{jid}","source":source["id"],"company":source["company"],"title":posting["title"],"location":posting.get("locationsText","待核实"),"url":url,"path":path,"requisition":jid}
    try:
        r = session().get(base + path, timeout=25)
        if r.status_code != 200:
            job["evidence"] = evidence("unverified", base+path, f"职位接口 HTTP {r.status_code}；不能据此认定关闭", "workday-detail", at)
            return job
        info = r.json().get("jobPostingInfo", {})
        desc = text(info.get("jobDescription", ""))
        job["location"] = info.get("location",job["location"])
        if info.get("country",{}).get("descriptor")=="China" and not CHINA.search(job["location"]):
            job["location"] += "（中国）"
        job.update({"title":info.get("title",job["title"]),"description":desc[:14000],"posted":info.get("startDate",""),"conditions":qualification_excerpt(desc)})
        # Require matching job ID, detailed description and a live application URL.
        apply = info.get("externalUrl", "")
        match_id = str(info.get("jobReqId",info.get("jobRequisitionId",""))) == str(jid)
        if match_id and desc and apply and info.get("canApply") is True and info.get("posted") is True:
            job["evidence"] = evidence("open",base+path,f"官方职位接口返回 requisition={jid}；存在申请入口。"+qualification_excerpt(desc),"workday-live-detail",at)
        elif match_id and desc and info.get("canApply") is False and info.get("posted") is False:
            job["evidence"] = evidence("closed",base+path,f"官方职位接口返回 requisition={jid}，canApply=false 且 posted=false。","workday-explicit-closed",at)
        else:
            job["evidence"] = evidence("unverified",base+path,"官方接口返回内容不足，未同时确认职位编号、详情与申请入口", "workday-detail",at)
    except Exception as exc:
        job["evidence"] = evidence("unverified",url,type(exc).__name__+"：实时详情读取失败", "workday-detail",at)
    return job


def qualification_excerpt(desc):
    match = re.search(r"Minimum Qualifications|Qualifications|Requirements|任职资格|任职要求|Education", desc, re.I)
    start = match.start() if match else 0
    return desc[start:start+650]


def collect_workday(source, at):
    s = session()
    api = f"https://{source['host']}/wday/cxs/{source['tenant']}/{source['board']}/jobs"
    found = {}
    scanned = 0
    try:
        def page(offset, facets):
            r = s.post(api,json={"appliedFacets":facets,"limit":20,"offset":offset,"searchText":""}, timeout=30)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data.get("jobPostings"),list) or not isinstance(data.get("total"),int):
                raise ValueError("招聘接口格式变化")
            return data
        first = page(0,{})
        facets = {}
        for f in first.get("facets",[]):
            values = [v["id"] for v in f.get("values",[]) if v.get("descriptor", "").lower() == "china"]
            if values:
                facets = {f["facetParameter"]:values}; break
        if facets:
            first = page(0, facets)
        total = first["total"]
        if total > 2000 and not facets:
            raise ValueError(f"未发现中国地区筛选，全球职位达 {total} 条；停止截断检索，报告来源异常")
        pages = [first]
        for offset in range(20,total,20):
            pages.append(page(offset,facets))
        for p in pages:
            for j in p["jobPostings"]:
                scanned += 1
                if j.get("externalPath") and INTERN.search(j.get("title","")) and not NONTECH.search(j.get("title","")) and (CHINA.search(j.get("locationsText","")) or re.search(r"\d+ Locations",j.get("locationsText",""))):
                    found[j["externalPath"]] = j
        with cf.ThreadPoolExecutor(max_workers=4) as pool:
            jobs = list(pool.map(lambda j:wd_observe(source,j,at),found.values()))
        jobs = [j for j in jobs if CHINA.search(j.get("location",""))]
        return jobs,{"source":source["company"],"id":source["id"],"url":workday_url(source,""),"ok":True,"scanned":scanned,"candidates":len(jobs),"message":"实时扫描官方招聘库；中国地区实习按详情核实"}
    except Exception as exc:
        return [],{"source":source["company"],"id":source["id"],"url":workday_url(source,""),"ok":False,"scanned":scanned,"candidates":0,"message":type(exc).__name__+": "+str(exc)[:180]}


def canonical(url):
    p = urlparse(url)
    query = urlencode([(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith("utm_") and k.lower() not in {"pcm","from","source","ref"}])
    return urlunparse((p.scheme,p.netloc.lower(),p.path.rstrip("/"),"",query,""))


def permitted(url, config):
    host = urlparse(url).hostname or ""
    return url.startswith("https://") and any(host == d or host.endswith("."+d) for d in config["official_domains"]+config["search_domains"])


def web_observe(job, config, at):
    job = copy.deepcopy(job)
    url = job["url"]
    official = any((urlparse(url).hostname or "").endswith(d) for d in config["official_domains"])
    try:
        r = session().get(url,timeout=25)
        # Single 404/410, login walls, robots denials and disappearing search hits are all uncertainty.
        if r.status_code != 200:
            job["evidence"] = evidence("unverified",url,f"HTTP {r.status_code}：无法实时核实", "web-detail",at)
            return job
        soup = BeautifulSoup(r.content,"html.parser")
        body = text(str(soup))
        # Page-specific structured JobPosting is the strongest general-web signal.
        structured = []
        for script in soup.find_all("script",type="application/ld+json"):
            try:
                value = json.loads(script.string or "")
                nodes = value if isinstance(value,list) else value.get("@graph",[value])
                structured.extend(n for n in nodes if isinstance(n,dict) and n.get("@type")=="JobPosting")
            except (ValueError,TypeError,AttributeError):
                pass
        if len(structured)==1:
            p = structured[0]
            job["title"] = p.get("title",job["title"])
            desc = text(p.get("description",""))
            org = p.get("hiringOrganization",{})
            if isinstance(org,dict): job["company"] = org.get("name",job["company"])
            loc = p.get("jobLocation",{})
            if isinstance(loc,list):loc = loc[0] if loc else {}
            if isinstance(loc,dict):
                addr = loc.get("address",{})
                if isinstance(addr,dict):job["location"] = " ".join(str(addr.get(k,"")) for k in ["addressRegion","addressLocality"]).strip() or job.get("location","待核实")
            expiry = str(p.get("validThrough",""))[:10]
            job["description"] = desc[:14000]
            job["conditions"] = qualification_excerpt(desc)
            if expiry and re.fullmatch(r"\d{4}-\d\d-\d\d",expiry) and expiry < at[:10]:
                job["evidence"] = evidence("closed",url,"职位 JobPosting 的截止日期为 "+expiry,"jobposting-expiry",at)
                return job
            apply = any(re.search(r"投递简历|立即投递|Apply(?: now)?|申请职位",a.get_text(" ",strip=True),re.I) for a in soup.find_all(["a","button"]))
            if (official or "shixiseng.com" in url) and apply and desc and INTERN.search(job["title"]) and expiry >= at[:10]:
                job["evidence"] = evidence("open",url,"职位详情、有效截止日期 "+expiry+" 与投递入口同时存在。"+qualification_excerpt(desc),"jobposting-live",at)
                return job
        # Avoid classifying a list page by a closed label belonging to a different job.
        headings = [h.get_text(' ',strip=True) for h in soup.find_all('h1')]
        title_ok = job["title"].split("实习招聘")[0] in headings
        match = CLOSED.search(body)
        if official and title_ok and match and (structured or soup.find("h1")):
            job["evidence"] = evidence("closed",url,body[max(0,match.start()-70):match.end()+100],"explicit-closed-detail",at)
        else:
            job["evidence"] = evidence("unverified",url,"页面可读，但未取得足以确认开放 / 关闭的职位级证据；搜索摘要不算开放证明。","web-detail",at)
    except Exception as exc:
        job["evidence"] = evidence("unverified",url,type(exc).__name__+"：详情读取失败","web-detail",at)
    return job


def collect_search(config, at):
    def query(q):
        try:
            r = session().get("https://www.bing.com/search",params={"format":"rss","q":q},timeout=25)
            r.raise_for_status(); root = ET.fromstring(r.content)
            if root.tag != "rss":raise ValueError("搜索未返回 RSS")
            jobs=[]
            for item in root.findall("./channel/item"):
                title = item.findtext("title",""); url = canonical(item.findtext("link","")); desc = item.findtext("description","")
                if permitted(url,config) and INTERN.search(title) and SEMI.search(title+" "+desc):
                    jobs.append({"id":"web:"+hashlib.sha256(url.encode()).hexdigest()[:16],"source":"web","company":"待核实招聘单位","title":title,"location":"待核实（搜索线索）","url":url,"discovery_query":q})
            return jobs,{"source":"网页搜索 · "+q,"id":"search","url":r.url,"ok":True,"scanned":len(root.findall('./channel/item')),"candidates":len(jobs),"message":"仅发现线索；逐条访问原始职位详情核实"}
        except Exception as exc:
            return [],{"source":"网页搜索 · "+q,"id":"search","url":"https://www.bing.com/search","ok":False,"scanned":0,"candidates":0,"message":type(exc).__name__+"：搜索源不可用，保留既有岗位"}
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(query,config["search_queries"]))
    unique = {j["url"]:j for jobs,_ in results for j in jobs}
    for j in config.get("watch_links",[]):
        seed = dict(j,source="web",id="web:"+hashlib.sha256(canonical(j["url"]).encode()).hexdigest()[:16])
        unique[canonical(j["url"])] = seed
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        jobs = list(pool.map(lambda j:web_observe(j,config,at),unique.values()))
    return jobs,[health for _,health in results]


def transition(registry, observations, at):
    """Never admit a newly discovered closed job to the registry."""
    jobs = copy.deepcopy(registry.get("jobs",{}))
    for obs in observations:
        key = obs["id"]; ev = obs["evidence"]; old = jobs.get(key)
        if ev["state"] == "closed" and not (old and old.get("recommended_at")):
            continue
        if not old:
            old = {"id":key,"first_seen":at,"events":[]}
        for name,value in obs.items():
            if name != "evidence":old[name] = value
        previous = old.get("status")
        if ev["state"] == "open":
            old.setdefault("recommended_at",at)
            old["last_confirmed_open"] = at
            old["status"] = "new" if old["recommended_at"][:10] == at[:10] else "open"
        elif ev["state"] == "closed":
            old["status"] = "closed"
            old["closed_at"] = at
            old["closure_evidence"] = copy.deepcopy(ev)
        elif old.get("status") != "closed":
            old["status"] = "unverified"
        old["evidence"] = ev
        old["last_checked"] = at
        old["score"],old["reasons"] = fit(old["title"],old.get("description",""),old.get("location",""))
        if previous != old["status"]:
            old["events"].append({"at":at,"from":previous,"to":old["status"],"evidence":copy.deepcopy(ev)})
        jobs[key] = old
    for key,job in jobs.items():
        if key not in {o["id"] for o in observations} and job["status"] != "closed":
            job["status"] = "unverified"
            job["evidence"] = evidence("unverified",job["url"],"本轮未取得职位详情；未出现于检索结果不代表已关闭", "not-observed",at)
            job["last_checked"] = at
    return {"schema_version":1,"updated_at":at,"jobs":jobs}


def persist_run(root, registry, health, at, run_id):
    data = root / "data"
    path = data / "runs" / (run_id+".json")
    if path.exists():
        raise FileExistsError("不可覆盖已有运行快照："+run_id)
    snapshot = {"schema_version":1,"id":run_id,"date":at[:10],"generated_at":at,"jobs":sorted(registry["jobs"].values(),key=lambda j:(-j.get("score",0),j["id"])),"sources":health}
    write_json(path,snapshot)
    day_path = data / "history" / (at[:10]+".json")
    day = read_json(day_path,{"date":at[:10],"runs":[]})
    day["runs"].append(run_id)
    write_json(day_path,day)
    write_json(data / "registry.json",registry)
    write_json(data / "latest.json",snapshot)
    return snapshot


def collect(root=ROOT):
    at = datetime.now(CST).isoformat(timespec="seconds")
    run_id = datetime.now(CST).strftime("%Y%m%dT%H%M%S%f")+"-"+str(os.getenv("GITHUB_RUN_ID") or uuid.uuid4().hex[:8])+"-"+os.getenv("GITHUB_RUN_ATTEMPT","1")
    config = read_json(root/"config.json",{})
    registry = read_json(root/"data/registry.json",{"jobs":{}})
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda s:collect_workday(s,at),config["workday"]))
    observations = [j for jobs,_ in results for j in jobs]
    health = [h for _,h in results]
    extra, search_health = collect_search(config,at)
    observations.extend(extra); health.extend(search_health)
    seen = {j["id"] for j in observations}
    source_map = {s["id"]:s for s in config["workday"]}
    # Recheck every previously recommended job, including ones omitted by discovery.
    # Workday 404 is intentionally uncertainty, never closure evidence.
    for job in registry["jobs"].values():
        if job["id"] in seen or job["status"] == "closed":continue
        if job["source"] in source_map:
            observations.append(wd_observe(source_map[job["source"]],{"externalPath":job["path"],"title":job["title"],"locationsText":job["location"],"bulletFields":[job["requisition"]]},at))
        elif permitted(job["url"],config):
            observations.append(web_observe(job,config,at))
    registry = transition(registry,observations,at)
    snapshot = persist_run(root,registry,health,at,run_id)
    counts = {s:sum(j["status"]==s for j in snapshot["jobs"]) for s in LABELS}
    print(json.dumps({"run":run_id,"counts":counts,"healthy_sources":sum(h["ok"] for h in health),"sources":len(health)},ensure_ascii=False))
    return snapshot


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--render-only",action="store_true"); args=parser.parse_args()
    if not args.render_only:collect()
    from render import build
    build(ROOT)
