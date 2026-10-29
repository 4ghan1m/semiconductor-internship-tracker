"""JD-evidence-based fit. Keep major eligibility separate from skills and job availability."""
import re

MATERIAL = re.compile(r"材料(?:科学(?:与工程)?|工程|学|类|相关|物理|化学|成型)?|冶金|金属材料|高分子|无机非金属|\bmaterials?\b|\bmetallurg\w*|\bpolymer\b", re.I)
RELATED = re.compile(r"能源与动力|热能工程|动力工程|流体机械|制冷|机械|物理|化学|理工科|工程类|相关工科|专业不限|不限专业|\bmechanical engineering\b|\bchemical engineering\b|\bthermal engineering\b|\bmanufacturing engineering\b|\bphysics\b|\bchemistry\b|\bSTEM\b", re.I)
SOFTWARE = re.compile(r"计算机|软件工程|电气工程|电子工程|\bcomputer science\b|\bsoftware engineering\b|\belectrical engineering\b", re.I)
HARD_LOWLEVEL = re.compile(r"CUDA|GPU|编译器|固件|底层开发|\bcompiler\b|\bfirmware\b|\bC\+\+\b|\bC/C\+\+\b", re.I)
FIELD = re.compile(r"材料|薄膜|沉积|刻蚀|光刻|CMP|封装|表征|失效|工艺|制程|良率|可靠性|设备|电池|热管理|制造|质量|测试|金属|仿真|\bmaterial\b|\bprocess\b|\betch(?:ing)?\b|deposition|wafer|thermal|battery|quality|metrology|manufactur", re.I)
SECTION = re.compile(r"专业要求\s*[:：]|任职资格\s*[:：]|任职要求\s*[:：]|岗位要求\s*[:：]|招聘对象\s*[:：]|\b(?:Minimum|Basic|Required|Preferred)\s+Qualifications\b|\bQualifications\b|\bRequirements\b|\bKey\s+Qualifications\b|\bEducation\s*[:：]?", re.I)
MAJOR_SECTION = re.compile(r"(?:专业要求|专业背景|所学专业|专业方向|\bMajor\b)\s*[:：]\s*(.{0,240})", re.I)
DEGREE = re.compile(r"硕士(?:及以上|研究生)?|本科(?:及以上)?|博士(?:及以上)?|\bmaster'?s?\b|\bPh\.?D\.?\b|\bbachelor'?s?\b|\bgraduate student\b", re.I)
GRAD = re.compile(r"20(?:2[6-9]|3[0-5])\s*届|20(?:2[6-9]|3[0-5])\s*(?:graduates?|graduation)", re.I)
ATTEND = re.compile(r"(?:[2-7]\s*[-~至到]\s*[2-7]\s*days\s*/\s*week)|(?:[2-9]\s*months)|暑期须全勤|(?:每周|一周|week(?:ly)?)[^。；;\n]{0,28}?(?:[2-7]\s*[-~至到]\s*[2-7]\s*天|[2-7]\s*天|[2-7]\s*days?)|(?:实习|internship)[^。；;\n]{0,24}?(?:[2-9]\s*个月|[2-9]\s*months?|半年)", re.I)
LANG = re.compile(r"英语|英文|\bEnglish\b|\bCET[- ]?[46]\b", re.I)
TECH = re.compile(r"Python|机器学习|数据分析|\bSQL\b|\bExcel\b|\bOffice\b|\bCUDA\b|C\+\+|\bMATLAB\b|\bCOMSOL\b|\bANSYS\b|\bAbaqus\b|\bEBSD\b|\bSEM\b|\bXRD\b|\bCAD\b", re.I)
AUTO = re.compile(r"汽车|整车|车辆|新能源车|动力电池|锂离子电池|电芯|电池研发|动力系统|奔驰|理想汽车|小米汽车|座舱|热管理|\bautomotive\b|\bvehicle\b", re.I)
SEMI = re.compile(r"半导体|晶圆|芯片|制程|光刻|刻蚀|CMP|\bsemiconductor\b|\bwafer\b|\bPIE\b", re.I)

def first(pattern, value):
    m = pattern.search(value or "")
    return m.group(0).strip() if m else "未说明"

def qualifications(description):
    value = re.sub(r"\s+", " ", description or "").strip()
    marks = list(SECTION.finditer(value))
    if not marks:
        return ""
    return value[marks[0].start():][:2400]

def classify(job):
    title = job.get("title", "")
    description = job.get("description", "")
    req = qualifications(description)
    major_match = MAJOR_SECTION.search(req)
    major_clause = major_match.group(1) if major_match else ""
    if major_clause:
        major_clause = re.split(r"任职资格|岗位职责|技能要求|工作内容|任职要求", major_clause)[0][:200]
    explicit_material = bool(MATERIAL.search(major_clause)) or bool(re.search(r"(?:专业|major|degree)[^。；;]{0,80}(?:材料|冶金|materials?\s+(?:science|engineering)|metallurg)", req, re.I))
    explicit_related = bool(RELATED.search(major_clause)) or bool(re.search(r"(?:专业|major|degree)[^。；;]{0,80}(?:机械|热能|能源动力|物理|化学|理工|机械工程|机械制造|mechanical engineering|chemical engineering|thermal engineering|manufacturing engineering|physics|chemistry)", req, re.I))
    software_only = bool(SOFTWARE.search(req)) and not explicit_material and not explicit_related and (bool(SOFTWARE.search(major_clause)) or bool(re.search(r"software|compiler|firmware|GPU|CUDA|DFT|verification|编译器|固件",title,re.I)) or bool(re.search(r"(?:major|degree|专业要求)[^.;。；]{0,140}(?:computer science|electrical engineering|software engineering|电子工程|电气工程|计算机)",req,re.I)))
    lowlevel = bool(HARD_LOWLEVEL.search(title)) or bool(re.search(r"(?:必须|精通|required|proficien(?:t|cy)|strong experience)[^。；;]{0,75}(?:CUDA|C\+\+|GPU|编译器|固件)", req, re.I))
    phd_only = bool(re.search(r"仅限博士|必须博士|Ph\.?D\.?\s+(?:required|only)", req, re.I))
    related_work = bool(FIELD.search(title + " " + description[:2000]))
    if not req:
        grade, major = "U", "未获取可核验的JD任职/专业要求；专业资格待核实"
    elif phd_only or lowlevel or software_only:
        grade, major = "C", "JD存在专业或核心技能门槛冲突，不能直接视为材料专业可投"
    elif explicit_material:
        grade, major = "A", "JD专业要求明确包含材料/冶金相关专业"
    elif explicit_related and related_work:
        grade, major = "B", "JD包含相关理工科专业且职责相关；材料硕士资格需HR确认"
    elif major_clause and re.search(r"专业不限|不限专业|理工科|相关专业",major_clause) and related_work:
        grade, major = "B", "JD未限定具体材料专业且职责相关；需HR确认"
    else:
        grade, major = "U", "JD未明确证明材料专业合格或相关理工科资格；待核实"
    sector = title + " " + job.get("company", "")
    industry = ("汽车" if AUTO.search(sector) and not SEMI.search(title) else
                "半导体" if SEMI.search(sector) or job.get("source") in {"amat","kla","intel","nxp","focuslight"} else
                "汽车" if AUTO.search(description[:700]) and not SEMI.search(description[:700]) else "待核实")
    if industry == "半导体" and re.search(r"材料|薄膜|沉积|刻蚀|光刻|CMP|封装|失效|可靠性|工艺|制程|良率|表征|\bprocess\b|\bmaterials?\b",title,re.I):
        priority, rank = "半导体材料/工艺", 0
    elif re.search(r"材料.?AI|AI.?材料|机器学习|工艺优化|数据分析|machine learning|materials informatics",title,re.I):
        priority, rank = "材料+AI/工艺数据", 1
    else:
        priority, rank = "设备/汽车工程或其他", 2
    skills = list(dict.fromkeys(m.group(0) for m in TECH.finditer(req)))[:12]
    gap = []
    if lowlevel: gap.append("CUDA/GPU/C++底层能力缺乏证明")
    if phd_only: gap.append("JD要求博士")
    if GRAD.search(req + " " + title): gap.append("毕业届别未知，须核实")
    if ATTEND.search(description): gap.append("到岗要求需本人确认")
    return {
        "match_grade":grade, "major_eligibility":major,
        "major_evidence":(major_clause or req[:850]) if req else "未说明/待核实",
        "jd_source_url":job.get("jd_source_url") or job.get("url",""), "degree_requirement":first(DEGREE,req),
        "graduation_requirement":first(GRAD,req+" "+title),
        "attendance_requirement":first(ATTEND,description),
        "language_requirement":first(LANG,req),
        "hard_skills":skills,
        "skill_fit":("Python/机器学习/材料实验经历可作为基础；JD其他技能仍须逐项核实" if related_work else "未证明核心技能匹配"),
        "skill_gaps":gap,
        "industry":industry, "priority_direction":priority, "priority_order":rank,
        "jd_verified":bool(req),
    }
