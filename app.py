import streamlit as st
import pandas as pd
import numpy as np
import random,json,io,uuid,base64
from copy import deepcopy

st.set_page_config(page_title="LHA / MLH League Manager v2.5",page_icon="🏒",layout="wide")

LHA_DIV={
"East":["Boston Titans","D.C. Daggers","Toronto Stars","New York Chiefs","Ottawa Capitals","Philadelphia Liberty"],
"West":["Seattle Wildcats","Vancouver Pilots","Los Angeles Jets","Colorado Knights","Detroit Flames","Chicago Railers"]}
MLH_TEAMS=["Anchorage Bush Pilots","Bellingham Blades","Erie Thunderbirds","Kingston Corsairs","Rapid City Scouts","Syracuse IceHawks"]
MLH_ALIASES={
"Anchorage":"Anchorage Bush Pilots","Bellingham":"Bellingham Blades","Erie":"Erie Thunderbirds",
"Kingston":"Kingston Corsairs","Rapid City":"Rapid City Scouts","Syracuse":"Syracuse IceHawks"}
AFFILIATES={
"Anchorage Bush Pilots":["Seattle Wildcats","Vancouver Pilots"],
"Bellingham Blades":["Colorado Knights","Los Angeles Jets"],
"Erie Thunderbirds":["Philadelphia Liberty","Toronto Stars"],
"Kingston Corsairs":["Boston Titans","Ottawa Capitals"],
"Rapid City Scouts":["Chicago Railers","Detroit Flames"],
"Syracuse IceHawks":["D.C. Daggers","New York Chiefs"]}
ARENAS={
"Boston Titans":"Commonwealth Garden","D.C. Daggers":"Capital Forum","Toronto Stars":"CN Arena",
"New York Chiefs":"Empire Center","Ottawa Capitals":"National Arena","Philadelphia Liberty":"Liberty Center",
"Seattle Wildcats":"Sound Arena","Vancouver Pilots":"Sky Dome","Los Angeles Jets":"Pacific Forum",
"Colorado Knights":"Front Range Arena","Detroit Flames":"Detroit Garden","Chicago Railers":"Lakefront Arena"}
SET={"assist_probs":[.08,.27,.65],"learning":.20,"win_pts":2,"otl_pts":1}
ROSTER_COLS=["PlayerID","League","Team","Player","Position","Line","Scoring","Playmaking","Active"]
SCHEDULE_COLS=["League","Week","Away","Home","Date","GameID"]

def fresh():
    return {"version":"2.5","rosters":[],"schedule":[],"games":[],"transactions":[],"selections":[],
            "team_info":{},"overrides":{"team":{},"status":{},"seed":{}},
            "playoffs":{"LHA":{"generated":False,"series":[],"champion":None},
                        "MLH":{"generated":False,"series":[],"champion":None}},
            "settings":deepcopy(SET)}

if "L" not in st.session_state: st.session_state.L=fresh()
L=st.session_state.L
for k,v in fresh().items():
    if k not in L:L[k]=deepcopy(v)

# v2.3 migration
if isinstance(L.get("playoffs"),dict) and "generated" in L["playoffs"]:
    old=L["playoffs"];L["playoffs"]={"LHA":old,"MLH":{"generated":False,"series":[],"champion":None}}
for rec in L.get("rosters",[]):
    rec.setdefault("PlayerID","P-"+uuid.uuid4().hex[:10].upper())
    old=rec.pop("Level",None)
    rec.setdefault("League","MLH" if old in ["Minor League","MLH"] else "LHA")
for rec in L.get("schedule",[]):
    rec.setdefault("League","MLH" if rec.get("Away") in MLH_TEAMS else "LHA")
for g in L.get("games",[]):
    g.setdefault("League","MLH" if g.get("Away") in MLH_TEAMS else "LHA")
# Canonicalize old city-only MLH data from early v2.4 builds.
def canon_team(t):
    return MLH_ALIASES.get(str(t).strip(),str(t).strip())

for rec in L.get("rosters",[]):
    rec["Team"]=canon_team(rec.get("Team",""))
    if rec["Team"] in MLH_TEAMS: rec["League"]="MLH"
for rec in L.get("schedule",[]):
    rec["Away"]=canon_team(rec.get("Away","")); rec["Home"]=canon_team(rec.get("Home",""))
    if rec["Away"] in MLH_TEAMS or rec["Home"] in MLH_TEAMS: rec["League"]="MLH"
for g in L.get("games",[]):
    g["Away"]=canon_team(g.get("Away","")); g["Home"]=canon_team(g.get("Home",""))
    if g["Away"] in MLH_TEAMS or g["Home"] in MLH_TEAMS: g["League"]="MLH"
    for e in g.get("Events",[]): e["Team"]=canon_team(e.get("Team",""))
    for q in g.get("Goalies",[]): q["Team"]=canon_team(q.get("Team",""))
for rec in L.get("transactions",[]):
    if "FromTeam" in rec: rec["FromTeam"]=canon_team(rec["FromTeam"])
    if "ToTeam" in rec: rec["ToTeam"]=canon_team(rec["ToTeam"])
for rec in L.get("selections",[]):
    if "Team" in rec: rec["Team"]=canon_team(rec["Team"])
for lg in ["LHA","MLH"]:
    for s in L.get("playoffs",{}).get(lg,{}).get("series",[]):
        s["Team1"]=canon_team(s.get("Team1","")); s["Team2"]=canon_team(s.get("Team2",""))
    ch=L.get("playoffs",{}).get(lg,{}).get("champion")
    if ch: L["playoffs"][lg]["champion"]=canon_team(ch)
for old,new in MLH_ALIASES.items():
    if old in L["team_info"] and new not in L["team_info"]:
        L["team_info"][new]=L["team_info"].pop(old)
    elif old in L["team_info"]:
        L["team_info"].pop(old,None)

INFO_DEFAULT={"Coach":"","GM":"","Arena":"","Notes":"","LogoData":"","LogoType":"",
              "Championships":"","DivisionTitles":"","RetiredNumbers":"","TeamHonors":""}
for t in sum(LHA_DIV.values(),[]):
    base=deepcopy(INFO_DEFAULT); base["Arena"]=ARENAS.get(t,"")
    cur=L["team_info"].setdefault(t,base)
    for k,v in base.items(): cur.setdefault(k,v)
for t in MLH_TEAMS:
    base=deepcopy(INFO_DEFAULT); base["Affiliates"]=", ".join(AFFILIATES[t])
    cur=L["team_info"].setdefault(t,base)
    for k,v in base.items(): cur.setdefault(k,v)

def teams(league):
    return sum(LHA_DIV.values(),[]) if league=="LHA" else MLH_TEAMS
def division(team):
    if team in LHA_DIV["East"]:return "East"
    if team in LHA_DIV["West"]:return "West"
    return "MLH"
def df(k):
    rows=L.get(k,[])
    cols=ROSTER_COLS if k=="rosters" else SCHEDULE_COLS if k=="schedule" else None
    if cols:return pd.DataFrame(rows,columns=cols) if not rows else pd.DataFrame(rows).reindex(columns=cols)
    return pd.DataFrame(rows)
def P(x):return str(x).strip().upper()
def upload(u):
    raw=u.getvalue()
    if u.name.lower().endswith(".csv"):
        for enc in ["utf-8-sig","utf-8","cp1252","latin1"]:
            try:
                return pd.read_csv(io.BytesIO(raw),encoding=enc)
            except UnicodeDecodeError:
                pass
        raise ValueError("CSV encoding could not be read.")
    return pd.read_excel(io.BytesIO(raw))
def roster_import(d,default_league):
    a={str(c).strip().lower():c for c in d.columns}
    miss=[x for x in ["team","player","position","line"] if x not in a]
    if miss:raise ValueError("Missing: "+", ".join(miss))
    o=pd.DataFrame({"Team":d[a["team"]].astype(str).str.strip().map(canon_team),"Player":d[a["player"]].astype(str).str.strip(),
                    "Position":d[a["position"]].astype(str).str.strip(),
                    "Line":pd.to_numeric(d[a["line"]],errors="coerce").fillna(3).clip(1,4).astype(int)})
    o["League"]=d[a["league"]].astype(str).str.upper().str.strip() if "league" in a else default_league
    for c in ["Scoring","Playmaking"]:
        o[c]=pd.to_numeric(d[a[c.lower()]],errors="coerce").fillna(70).clip(1,99) if c.lower() in a else 70
    o["Active"]=d[a["active"]].astype(str).str.lower().isin(["true","1","yes","y"]) if "active" in a else True
    if "playerid" in a:o["PlayerID"]=d[a["playerid"]].astype(str)
    else:o["PlayerID"]=["P-"+uuid.uuid4().hex[:10].upper() for _ in range(len(o))]
    return o[ROSTER_COLS]
def schedule_import(d,league):
    a={str(c).strip().lower():c for c in d.columns}
    miss=[x for x in ["week","away","home"] if x not in a]
    if miss:raise ValueError("Missing: "+", ".join(miss))
    o=pd.DataFrame({"League":league,"Week":pd.to_numeric(d[a["week"]],errors="coerce").fillna(1).astype(int),
                    "Away":d[a["away"]].astype(str).str.strip().map(canon_team),"Home":d[a["home"]].astype(str).str.strip().map(canon_team)})
    o["Date"]=d[a["date"]].astype(str) if "date" in a else ""
    o["GameID"]=[f"{league}-REG-W{w:02d}-{i+1:03d}" for i,w in enumerate(o.Week)]
    return o[SCHEDULE_COLS]
def roster(team,goalie=False):
    r=df("rosters")
    if r.empty:return pd.DataFrame(columns=ROSTER_COLS)
    active=r.Active.fillna(True).astype(str).str.lower().isin(["true","1","yes","y"]) if r.Active.dtype==object else r.Active.fillna(True).astype(bool)
    m=r.Team.eq(team)&active
    isg=r.Position.map(P).eq("G")
    m&=isg if goalie else ~isg
    return r[m].drop_duplicates("PlayerID").reset_index(drop=True)
def games(league=None,kind=None):
    z=L["games"]
    if league:z=[g for g in z if g.get("League","LHA")==league]
    if kind=="Regular":z=[g for g in z if g.get("SeasonType","Regular")=="Regular"]
    if kind=="Playoffs":z=[g for g in z if g.get("SeasonType")=="Playoffs"]
    return z
def remaining(team,league):
    s=df("schedule");s=s[s.League.eq(league)]
    total=((s.Away==team)|(s.Home==team)).sum()
    played=sum(team in [g["Away"],g["Home"]] for g in games(league,"Regular"))
    return max(0,int(total-played))
def standings(league):
    base={t:{"Team":t,"Division":division(t),"GP":0,"W":0,"L":0,"OTL":0,"GF":0,"GA":0,"PTS":0} for t in teams(league)}
    for g in games(league,"Regular"):
        a,h=g["Away"],g["Home"];ag,hg=g["AwayGoals"],g["HomeGoals"]
        if a not in base or h not in base:continue
        for t,gf,ga in [(a,ag,hg),(h,hg,ag)]:
            base[t]["GP"]+=1;base[t]["GF"]+=gf;base[t]["GA"]+=ga
        w,l=(a,h) if ag>hg else (h,a);base[w]["W"]+=1;base[w]["PTS"]+=2
        if g["OT"]:base[l]["OTL"]+=1;base[l]["PTS"]+=1
        else:base[l]["L"]+=1
    for t,x in L["overrides"]["team"].items():
        if t in base:
            for k,v in x.items():
                if k in base[t]:base[t][k]+=int(v)
    d=pd.DataFrame(base.values());d["DIFF"]=d.GF-d.GA;d["GR"]=[remaining(t,league) for t in d.Team]
    return d
def rank(league,div=None):
    d=standings(league)
    if div:d=d[d.Division.eq(div)]
    return d.sort_values(["PTS","W","DIFF","GF"],ascending=False).reset_index(drop=True)
def stat_games(league,kind):
    if kind=="Combined":return games(league)
    return games(league,kind)
def skaters(league,kind="Combined"):
    r=df("rosters");chosen=stat_games(league,kind);gp={};go={};ast={}
    for g in chosen:
        participants=set()
        for e in g.get("Events",[]):
            for idkey,namekey in [("ScorerID","Scorer"),("Assist1ID","Assist1"),("Assist2ID","Assist2")]:
                nm=e.get(namekey,"")
                if nm:
                    row=r[(r.Team.eq(e["Team"]))&(r.Player.eq(nm))]
                    pid=e.get(idkey) or (row.iloc[0].PlayerID if not row.empty else e["Team"]+"|"+nm)
                    participants.add(pid)
            row=r[(r.Team.eq(e["Team"]))&(r.Player.eq(e.get("Scorer","")))]
            k=e.get("ScorerID") or (row.iloc[0].PlayerID if not row.empty else e["Team"]+"|"+e.get("Scorer",""))
            go[k]=go.get(k,0)+1
            for idkey,namekey in [("Assist1ID","Assist1"),("Assist2ID","Assist2")]:
                nm=e.get(namekey,"")
                if nm:
                    row=r[(r.Team.eq(e["Team"]))&(r.Player.eq(nm))]
                    k=e.get(idkey) or (row.iloc[0].PlayerID if not row.empty else e["Team"]+"|"+nm)
                    ast[k]=ast.get(k,0)+1
        for t in [g["Away"],g["Home"]]:
            for pid in r[(r.Team.eq(t))&(r.League.eq(league))&(~r.Position.map(P).eq("G"))].PlayerID:
                gp[pid]=gp.get(pid,0)+1
    out=[]
    for _,p in r[(r.League.eq(league))&(~r.Position.map(P).eq("G"))].iterrows():
        if gp.get(p.PlayerID,0) or go.get(p.PlayerID,0) or ast.get(p.PlayerID,0):
            out.append({"PlayerID":p.PlayerID,"Player":p.Player,"Team":p.Team,"GP":gp.get(p.PlayerID,0),"G":go.get(p.PlayerID,0),"A":ast.get(p.PlayerID,0),"PTS":go.get(p.PlayerID,0)+ast.get(p.PlayerID,0)})
    return pd.DataFrame(out)
def goalies(league,kind="Combined"):
    rows=[q for g in stat_games(league,kind) for q in g.get("Goalies",[])]
    if not rows:return pd.DataFrame()
    d=pd.DataFrame(rows);out=[]
    for (t,p),x in d.groupby(["Team","Goalie"]):
        sa=x.SA.sum();sv=x.SV.sum();ga=x.GA.sum();gp=len(x)
        out.append({"Team":t,"Goalie":p,"GP":gp,"W":int((x.Result=="W").sum()),"L":int((x.Result=="L").sum()),
                    "OTL":int((x.Result=="OTL").sum()),"SA":sa,"SV":sv,"GA":ga,"SO":int((x.GA==0).sum()),
                    "SV%":round(sv/sa,3) if sa else 0,"GAA":round(ga/gp,2)})
    return pd.DataFrame(out)
def pick(team,kind,exclude=[]):
    p=roster(team);p=p[~p.Player.isin(exclude)].reset_index(drop=True)
    if p.empty:return ""
    attr=(p.Scoring if kind=="G" else p.Playmaking).astype(float).to_numpy()
    line=p.Line.map({1:1.45,2:1.18,3:.92,4:.70}).fillna(1).to_numpy(float)
    w=np.maximum(attr/70*line,.01)
    return random.choices(p.Player.tolist(),weights=w.tolist(),k=1)[0]
def events(team,n):
    out=[]
    for i in range(n):
        sc=pick(team,"G");na=random.choices([0,1,2],weights=L["settings"]["assist_probs"])[0]
        a1=pick(team,"A",[sc]) if na else "";a2=pick(team,"A",[sc,a1]) if na==2 else ""
        out.append({"Team":team,"GoalNo":i+1,"Scorer":sc,"Assist1":a1,"Assist2":a2})
    return out
def makegame(league,gid,week,a,h,ag,hg,ot,agk,asa,hgk,hsa,season="Regular",stage="Regular",sid=None,ev=None):
    if ag==hg:raise ValueError("Final score cannot be tied.")
    if asa<hg or hsa<ag:raise ValueError("Shots against cannot be lower than goals allowed.")
    w=a if ag>hg else h
    qs=[{"Team":a,"Goalie":agk,"SA":asa,"SV":asa-hg,"GA":hg,"Result":"W" if w==a else "OTL" if ot else "L"},
        {"Team":h,"Goalie":hgk,"SA":hsa,"SV":hsa-ag,"GA":ag,"Result":"W" if w==h else "OTL" if ot else "L"}]
    return {"League":league,"GameID":gid,"Week":week,"Away":a,"Home":h,"AwayGoals":ag,"HomeGoals":hg,"OT":ot,
            "SeasonType":season,"Stage":stage,"SeriesID":sid,"Events":ev if ev is not None else events(a,ag)+events(h,hg),"Goalies":qs}
def po_schedule(high,low):
    return [(n,low if n in [1,2,6,7] else high,high if n in [1,2,6,7] else low) for n in range(1,8)]
def series_wins(league,sid):
    ser=next(x for x in L["playoffs"][league]["series"] if x["SeriesID"]==sid)
    out={}
    for t in [ser.get("Team1"),ser.get("Team2")]:
        if t:out[t]=sum(((g["Away"]==t and g["AwayGoals"]>g["HomeGoals"])or(g["Home"]==t and g["HomeGoals"]>g["AwayGoals"])) for g in games(league,"Playoffs") if g.get("SeriesID")==sid)
    return out
def generate_playoffs(league):
    if league=="LHA":
        ss=[]
        for d in ["East","West"]:
            ts=rank("LHA",d).Team.tolist()[:4]
            ss += [{"SeriesID":f"LHA-{d}-SF1","Round":"Division Semifinals","Division":d,"Team1":ts[0],"Team2":ts[3]},
                   {"SeriesID":f"LHA-{d}-SF2","Round":"Division Semifinals","Division":d,"Team1":ts[1],"Team2":ts[2]},
                   {"SeriesID":f"LHA-{d}-F","Round":"Division Finals","Division":d,"Team1":"","Team2":""}]
        ss += [{"SeriesID":"LHA-MMC-F","Round":"Meyers Memorial Cup Finals","Division":"Final","Team1":"","Team2":""}]
    else:
        ts=rank("MLH").Team.tolist()[:4]
        ss=[{"SeriesID":"MLH-SF1","Round":"Semifinals","Division":"MLH","Team1":ts[0],"Team2":ts[3]},
            {"SeriesID":"MLH-SF2","Round":"Semifinals","Division":"MLH","Team1":ts[1],"Team2":ts[2]},
            {"SeriesID":"MLH-F","Round":"MLH Championship","Division":"MLH","Team1":"","Team2":""}]
    L["playoffs"][league]={"generated":True,"series":ss,"champion":None}
def sync_playoffs(league):
    po=L["playoffs"][league]
    if not po["generated"]:return
    z={s["SeriesID"]:s for s in po["series"]};win={}
    for s in po["series"]:
        for t,n in series_wins(league,s["SeriesID"]).items():
            if n>=4:win[s["SeriesID"]]=t
    if league=="LHA":
        for d in ["East","West"]:
            z[f"LHA-{d}-F"]["Team1"]=win.get(f"LHA-{d}-SF1",z[f"LHA-{d}-F"]["Team1"])
            z[f"LHA-{d}-F"]["Team2"]=win.get(f"LHA-{d}-SF2",z[f"LHA-{d}-F"]["Team2"])
        z["LHA-MMC-F"]["Team1"]=win.get("LHA-East-F",z["LHA-MMC-F"]["Team1"])
        z["LHA-MMC-F"]["Team2"]=win.get("LHA-West-F",z["LHA-MMC-F"]["Team2"])
        po["champion"]=win.get("LHA-MMC-F")
    else:
        z["MLH-F"]["Team1"]=win.get("MLH-SF1",z["MLH-F"]["Team1"]);z["MLH-F"]["Team2"]=win.get("MLH-SF2",z["MLH-F"]["Team2"])
        po["champion"]=win.get("MLH-F")
def record_transaction(kind,pid,to_team,notes):
    r=df("rosters");m=r.index[r.PlayerID.eq(pid)]
    if not len(m):raise ValueError("Player not found.")
    i=int(m[0]);old_team=L["rosters"][i]["Team"];old_league=L["rosters"][i]["League"]
    if kind=="Release":L["rosters"][i]["Active"]=False
    else:
        new_league="MLH" if to_team in MLH_TEAMS else "LHA"
        L["rosters"][i]["Team"]=to_team;L["rosters"][i]["League"]=new_league;L["rosters"][i]["Active"]=True
    L["transactions"].append({"ID":"T-"+uuid.uuid4().hex[:8].upper(),"Type":kind,"PlayerID":pid,"Player":L["rosters"][i]["Player"],
                              "FromLeague":old_league,"FromTeam":old_team,"ToLeague":L["rosters"][i]["League"],
                              "ToTeam":L["rosters"][i]["Team"],"Notes":notes})

def bracket_card(title,team1,team2,wins=None):
    wins=wins or {}
    a=team1 or "TBD"; b=team2 or "TBD"
    aw=wins.get(team1,0) if team1 else 0; bw=wins.get(team2,0) if team2 else 0
    st.markdown(f"""<div style="border:1px solid #777;border-radius:8px;padding:10px;margin:8px 0;background:rgba(127,127,127,.08)">
    <div style="font-size:.75rem;opacity:.7;margin-bottom:6px">{title}</div>
    <div style="display:flex;justify-content:space-between;font-weight:600"><span>{a}</span><span>{aw}</span></div>
    <hr style="margin:5px 0;border:none;border-top:1px solid #777">
    <div style="display:flex;justify-content:space-between;font-weight:600"><span>{b}</span><span>{bw}</span></div>
    </div>""",unsafe_allow_html=True)

def show_bracket(league):
    po=L["playoffs"][league]
    if not po.get("generated"): return
    z={s["SeriesID"]:s for s in po["series"]}
    if league=="LHA":
        st.markdown("### Playoff Bracket")
        east,west=st.columns(2)
        for col,d in [(east,"East"),(west,"West")]:
            with col:
                st.markdown(f"#### {d}")
                c1,c2=st.columns(2)
                with c1:
                    for sid in [f"LHA-{d}-SF1",f"LHA-{d}-SF2"]:
                        s=z[sid];bracket_card("Division Semifinal",s.get("Team1"),s.get("Team2"),series_wins(league,sid))
                with c2:
                    s=z[f"LHA-{d}-F"];bracket_card("Division Final",s.get("Team1"),s.get("Team2"),series_wins(league,s["SeriesID"]))
        st.markdown("#### Meyers Memorial Cup Finals")
        s=z["LHA-MMC-F"];center=st.columns([1,2,1])[1]
        with center: bracket_card("Championship",s.get("Team1"),s.get("Team2"),series_wins(league,s["SeriesID"]))
    else:
        st.markdown("### Playoff Bracket")
        c1,c2=st.columns(2)
        with c1:
            for sid in ["MLH-SF1","MLH-SF2"]:
                s=z[sid];bracket_card("Semifinal",s.get("Team1"),s.get("Team2"),series_wins(league,sid))
        with c2:
            s=z["MLH-F"];bracket_card("MLH Championship",s.get("Team1"),s.get("Team2"),series_wins(league,s["SeriesID"]))

st.title("🏒 LHA / MLH League Manager v2.5")
page=st.sidebar.radio("Page",["Dashboard","Teams","Import / Setup","Weekly Games","Standings","Statistics","Game Log / Edit","Playoffs","Transactions & Honors","Commissioner Overrides","Backup / Export"])
league=st.sidebar.radio("League view",["LHA","MLH"],horizontal=True)

if page=="Dashboard":
    st.header(f"{league} Dashboard")
    reg=games(league,"Regular");c=st.columns(4)
    c[0].metric("Teams",len(teams(league)));c[1].metric("Games played",len(reg));c[2].metric("Goals",sum(g["AwayGoals"]+g["HomeGoals"] for g in reg));c[3].metric("Playoffs","Active" if L["playoffs"][league]["generated"] else "Not started")
    if league=="LHA":
        for col,d in zip(st.columns(2),["East","West"]):
            with col:st.subheader(d);st.dataframe(rank(league,d)[["Team","GP","W","L","OTL","PTS"]],hide_index=True,use_container_width=True)
    else:st.dataframe(rank(league)[["Team","GP","W","L","OTL","PTS"]],hide_index=True,use_container_width=True)

elif page=="Teams":
    st.header(f"{league} Team Center")
    team=st.selectbox("Team",teams(league))
    d=rank(league,division(team) if league=="LHA" else None);row=d[d.Team.eq(team)].iloc[0];place=int(d.index[d.Team.eq(team)][0])+1
    info=L["team_info"].setdefault(team,deepcopy(INFO_DEFAULT))
    for k,v in INFO_DEFAULT.items(): info.setdefault(k,v)

    top_logo,top_info=st.columns([1,3])
    with top_logo:
        if info.get("LogoData"):
            try: st.image(base64.b64decode(info["LogoData"]),use_container_width=True)
            except Exception: st.caption("Saved logo could not be displayed.")
        else:
            st.markdown("### Team Logo")
            st.caption("No logo uploaded yet.")
    with top_info:
        st.subheader(team)
        if league=="MLH": st.caption("LHA affiliates: "+", ".join(AFFILIATES[team]))
        c=st.columns(6);c[0].metric("Standing",f"#{place}");c[1].metric("Record",f"{int(row.W)}-{int(row.L)}-{int(row.OTL)}");c[2].metric("Points",int(row.PTS));c[3].metric("GF",int(row.GF));c[4].metric("GA",int(row.GA));c[5].metric("Diff",f"{int(row.DIFF):+d}")

    with st.expander("Team information",expanded=True):
        logo=st.file_uploader("Team logo",type=["png","jpg","jpeg","webp"],key=f"logo-{league}-{team}")
        if logo is not None:
            raw=logo.getvalue()
            info["LogoData"]=base64.b64encode(raw).decode("ascii"); info["LogoType"]=logo.type
            st.success("Logo loaded. It will be included in JSON backups.")
        with st.form(f"team_info-{league}-{team}"):
            a,b=st.columns(2)
            with a:
                coach=st.text_input("Head Coach",info.get("Coach",""))
                gm=st.text_input("GM / Manager",info.get("GM",""))
                arena=st.text_input("Arena / Home Ice",info.get("Arena",""))
                champs=st.text_area("Championships",info.get("Championships",""),placeholder="e.g. 2024, 2027")
            with b:
                divtitles=st.text_area("Division Titles",info.get("DivisionTitles",""),placeholder="e.g. 2023, 2025")
                retired=st.text_area("Retired Numbers",info.get("RetiredNumbers",""),placeholder="e.g. #9 — Player Name")
                honors=st.text_area("Other Team Honors",info.get("TeamHonors",""),placeholder="Presidents' trophies, records, banners, etc.")
                notes=st.text_area("Notes",info.get("Notes",""))
            save=st.form_submit_button("Save team information")
        if save:
            L["team_info"][team].update({"Coach":coach,"GM":gm,"Arena":arena,"Championships":champs,
                "DivisionTitles":divtitles,"RetiredNumbers":retired,"TeamHonors":honors,"Notes":notes})
            st.rerun()
        if info.get("LogoData") and st.button("Remove saved logo",key=f"rm-logo-{league}-{team}"):
            info["LogoData"]="";info["LogoType"]="";st.rerun()

    ov,rt,stats,sch,hist=st.tabs(["Overview","Roster","Statistics","Schedule & Results","Transactions & Honors"])
    with ov:
        a,b=st.columns(2)
        with a:
            st.write("**Coach:** "+(info.get("Coach") or "Not entered"))
            st.write("**GM / Manager:** "+(info.get("GM") or "Not entered"))
            st.write("**Arena:** "+(info.get("Arena") or "Not entered"))
            if league=="MLH":st.write("**Affiliates:** "+", ".join(AFFILIATES[team]))
        with b:
            st.write("**Championships:** "+(info.get("Championships") or "None entered"))
            st.write("**Division Titles:** "+(info.get("DivisionTitles") or "None entered"))
            st.write("**Retired Numbers:** "+(info.get("RetiredNumbers") or "None entered"))
            st.write("**Other Honors:** "+(info.get("TeamHonors") or "None entered"))
        if info.get("Notes"): st.markdown("**Notes**");st.write(info["Notes"])
    with rt:
        r=df("rosters");r=r[(r.League.eq(league))&(r.Team.eq(team))&(r.Active.astype(bool))]
        st.dataframe(r[["Player","Position","Line","Scoring","Playmaking"]],hide_index=True,use_container_width=True) if not r.empty else st.info("No active roster.")
    with stats:
        kind=st.radio("Split",["Regular","Playoffs","Combined"],horizontal=True,key="team_split")
        a=skaters(league,kind);a=a[a.Team.eq(team)] if not a.empty else a
        st.markdown("#### Skaters");st.dataframe(a.sort_values(["PTS","G"],ascending=False),hide_index=True,use_container_width=True) if not a.empty else st.info("No skater stats.")
        g=goalies(league,kind);g=g[g.Team.eq(team)] if not g.empty else g
        st.markdown("#### Goalies");st.dataframe(g,hide_index=True,use_container_width=True) if not g.empty else st.info("No goalie stats.")
    with sch:
        z=[g for g in games(league) if team in [g["Away"],g["Home"]]]
        if z:
            rows=[]
            for g in reversed(z[-10:]):
                gf=g["AwayGoals"] if g["Away"]==team else g["HomeGoals"];ga=g["HomeGoals"] if g["Away"]==team else g["AwayGoals"];opp=g["Home"] if g["Away"]==team else g["Away"]
                rows.append({"Type":g["SeasonType"],"Opponent":opp,"Site":"Away" if g["Away"]==team else "Home","Result":("W" if gf>ga else "L")+f" {gf}-{ga}"})
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        else:st.info("No results.")
    with hist:
        tx=df("transactions")
        if not tx.empty:tx=tx[(tx.FromTeam.eq(team))|(tx.ToTeam.eq(team))]
        st.dataframe(tx,hide_index=True,use_container_width=True) if not tx.empty else st.info("No transactions.")

elif page=="Import / Setup":
    st.header(f"{league} Import / Setup")
    a,b=st.columns(2)
    with a:
        u=st.file_uploader(f"{league} roster CSV/XLSX",type=["csv","xlsx"],key=f"r{league}")
        if u and st.button(f"Import {league} roster"):
            try:
                new=roster_import(upload(u),league)
                L["rosters"]=[x for x in L["rosters"] if x.get("League","LHA")!=league]+new.to_dict("records")
                st.success(f"{len(new)} {league} roster rows imported.")
            except Exception as e:
                st.error(str(e))
    with b:
        u=st.file_uploader(f"{league} schedule CSV/XLSX",type=["csv","xlsx"],key=f"s{league}")
        if u and st.button(f"Import {league} schedule"):
            try:
                new=schedule_import(upload(u),league)
                bad=(set(new.Away)|set(new.Home))-set(teams(league))
                if bad: raise ValueError("Unknown team name(s): "+", ".join(sorted(bad)))
                L["schedule"]=[x for x in L["schedule"] if x.get("League","LHA")!=league]+new.to_dict("records")
                st.success(f"{len(new)} {league} games imported.")
            except Exception as e:
                st.error(str(e))
    st.caption(f"Current database: {len(df('rosters'))} roster rows • {len(df('schedule'))} scheduled games • {len(L['games'])} completed games")

elif page=="Weekly Games":
    st.header("Weekly Games")
    s=df("schedule");s=s[s.League.eq(league)]
    if s.empty:st.info(f"Import a {league} schedule first.")
    else:
        wk=st.selectbox("Week",sorted(s.Week.unique()),key=f"wk{league}");done={g["GameID"] for g in games(league,"Regular")}
        for _,x in s[s.Week.eq(wk)].iterrows():
            with st.expander(("✅ " if x.GameID in done else "⬜ ")+f"{x.Away} at {x.Home}",expanded=x.GameID not in done):
                if x.GameID in done:st.write("Completed — edit under Game Log / Edit.");continue
                A=roster(x.Away,True).Player.tolist();H=roster(x.Home,True).Player.tolist()
                if not A or not H:st.error("Both teams need an active goalie.");continue
                with st.form(x.GameID):
                    c1,c2=st.columns(2)
                    with c1:ag=st.number_input(x.Away+" goals",0,30,0);agk=st.selectbox(x.Away+" goalie",A);asa=st.number_input(x.Away+" goalie SA",0,100,25)
                    with c2:hg=st.number_input(x.Home+" goals",0,30,0);hgk=st.selectbox(x.Home+" goalie",H);hsa=st.number_input(x.Home+" goalie SA",0,100,25)
                    ot=st.checkbox("OT / shootout");go=st.form_submit_button("Finalize & distribute")
                if go:
                    try:
                        L["games"].append(makegame(league,x.GameID,int(x.Week),x.Away,x.Home,ag,hg,ot,agk,asa,hgk,hsa))
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

elif page=="Standings":
    st.header(f"{league} Standings")
    if league=="LHA":
        for col,d in zip(st.columns(2),["East","West"]):
            with col:
                z=rank(league,d);z.insert(0,"Seed",range(1,len(z)+1));st.subheader(d);st.dataframe(z,hide_index=True,use_container_width=True)
    else:
        z=rank(league);z.insert(0,"Seed",range(1,len(z)+1));st.dataframe(z,hide_index=True,use_container_width=True)
        st.caption("Top four qualify for the MLH playoffs.")

elif page=="Statistics":
    st.header(f"{league} Statistics")
    kind=st.radio("Stat split",["Regular","Playoffs","Combined"],horizontal=True)
    a,b=st.tabs(["Skaters","Goalies"])
    with a:
        z=skaters(league,kind)
        if z.empty:st.info("No skater statistics.")
        else:
            sort=st.selectbox("Sort by",["PTS","G","A","GP"]);z=z.sort_values([sort,"G","A"],ascending=False).reset_index(drop=True);z.insert(0,"Rank",range(1,len(z)+1));st.dataframe(z,hide_index=True,use_container_width=True)
    with b:
        z=goalies(league,kind)
        if z.empty:st.info("No goalie statistics.")
        else:st.dataframe(z.sort_values(["W","SV%"],ascending=False),hide_index=True,use_container_width=True)

elif page=="Game Log / Edit":
    pool=games(league)
    if not pool:st.info(f"No {league} games.")
    else:
        ids=[L["games"].index(g) for g in pool];i=st.selectbox("Game",ids,format_func=lambda j:f"{L['games'][j]['GameID']} — {L['games'][j]['Away']} {L['games'][j]['AwayGoals']}, {L['games'][j]['Home']} {L['games'][j]['HomeGoals']}");g=L["games"][i]
        with st.form("editgame"):
            A=roster(g["Away"],True).Player.tolist();H=roster(g["Home"],True).Player.tolist();oldA=g["Goalies"][0]["Goalie"];oldH=g["Goalies"][1]["Goalie"]
            if oldA not in A:A=[oldA]+A
            if oldH not in H:H=[oldH]+H
            c1,c2=st.columns(2)
            with c1:ag=st.number_input(g["Away"]+" goals",0,30,g["AwayGoals"]);agk=st.selectbox("Away goalie",A,index=A.index(oldA));asa=st.number_input("Away goalie SA",0,100,g["Goalies"][0]["SA"])
            with c2:hg=st.number_input(g["Home"]+" goals",0,30,g["HomeGoals"]);hgk=st.selectbox("Home goalie",H,index=H.index(oldH));hsa=st.number_input("Home goalie SA",0,100,g["Goalies"][1]["SA"])
            ot=st.checkbox("OT/SO",g["OT"]);regen=st.checkbox("Regenerate scoring events");save=st.form_submit_button("Save corrections")
        if save:
            try:
                ev=None if regen or ag!=g["AwayGoals"] or hg!=g["HomeGoals"] else g["Events"]
                L["games"][i]=makegame(league,g["GameID"],g["Week"],g["Away"],g["Home"],ag,hg,ot,agk,asa,hgk,hsa,g["SeasonType"],g["Stage"],g.get("SeriesID"),ev);sync_playoffs(league);st.rerun()
            except Exception as e:
                st.error(str(e))
        if st.button("Delete game"):L["games"].pop(i);sync_playoffs(league);st.rerun()

elif page=="Playoffs":
    st.header("Meyers Memorial Cup Playoffs" if league=="LHA" else "MLH Playoffs")
    po=L["playoffs"][league]
    if not po["generated"]:
        if st.button(f"Generate {league} playoff bracket",type="primary"):generate_playoffs(league);st.rerun()
    else:
        sync_playoffs(league)
        if po["champion"]:st.success("🏆 Champion: "+po["champion"])
        show_bracket(league)
        st.divider()
        st.markdown("### Series Detail / Game Entry")
        labels=[f"{s['Round']} — {s.get('Team1') or 'TBD'} vs {s.get('Team2') or 'TBD'}" for s in po["series"]]
        pick_series=st.selectbox("Series",range(len(po["series"])),format_func=lambda i:labels[i])
        ser=po["series"][pick_series];high=ser.get("Team1","");low=ser.get("Team2","")
        if not high or not low:st.info("Waiting for the preceding series.")
        else:
            w=series_wins(league,ser["SeriesID"]);st.markdown(f"### {high} {w.get(high,0)} — {w.get(low,0)} {low}")
            played={int(g["Week"]):g for g in games(league,"Playoffs") if g.get("SeriesID")==ser["SeriesID"]};done=max(w.values() or [0])>=4;next_game=min([n for n in range(1,8) if n not in played],default=8)
            for n,away,home in po_schedule(high,low):
                with st.container(border=True):
                    st.markdown(f"**Game {n}: {away} at {home}**")
                    if n in played:
                        g=played[n];st.success(f"Final — {away} {g['AwayGoals']}, {home} {g['HomeGoals']}"+(" (OT/SO)" if g["OT"] else ""))
                    elif done:st.caption("Not necessary — series completed.")
                    elif n!=next_game:st.caption("Locked until preceding game is completed.")
                    else:
                        A=roster(away,True).Player.tolist();H=roster(home,True).Player.tolist()
                        if not A or not H:st.error("Both teams need an active goalie.");continue
                        with st.form(f"{ser['SeriesID']}-{n}"):
                            c1,c2=st.columns(2)
                            with c1:ag=st.number_input(away+" goals",0,30,0);agk=st.selectbox(away+" goalie",A);asa=st.number_input(away+" goalie SA",0,100,25)
                            with c2:hg=st.number_input(home+" goals",0,30,0);hgk=st.selectbox(home+" goalie",H);hsa=st.number_input(home+" goalie SA",0,100,25)
                            ot=st.checkbox("OT / shootout");go=st.form_submit_button("Finalize Game "+str(n))
                        if go:
                            try:
                                L["games"].append(makegame(league,f"{league}-PO-{ser['SeriesID']}-G{n}",n,away,home,ag,hg,ot,agk,asa,hgk,hsa,"Playoffs",ser["Round"],ser["SeriesID"]));sync_playoffs(league);st.rerun()
                            except Exception as e:
                                st.error(str(e))

elif page=="Transactions & Honors":
    st.header("Transactions & Honors")
    r=df("rosters");moves,log,honors=st.tabs(["Personnel Moves","Transaction Log","All-Star / All-Season"])
    with moves:
        if r.empty:st.info("Import rosters first.")
        else:
            active=r[r.Active.astype(bool)];pid=st.selectbox("Player",active.PlayerID.tolist(),format_func=lambda x:f"{active.loc[active.PlayerID.eq(x),'Player'].iloc[0]} — {active.loc[active.PlayerID.eq(x),'League'].iloc[0]} / {active.loc[active.PlayerID.eq(x),'Team'].iloc[0]}")
            row=active[active.PlayerID.eq(pid)].iloc[0];kind=st.selectbox("Transaction",["Trade / Transfer","Call Up","Send Down","Release"])
            allowed=sum(LHA_DIV.values(),[])+MLH_TEAMS
            if kind=="Call Up" and row.League=="MLH":allowed=AFFILIATES.get(row.Team,[])
            if kind=="Send Down" and row.League=="LHA":allowed=[m for m,a in AFFILIATES.items() if row.Team in a]
            to=st.selectbox("Destination team",allowed,disabled=kind=="Release");notes=st.text_input("Notes")
            if st.button("Record transaction & update roster"):
                record_transaction(kind,pid,to,notes);st.rerun()
    with log:
        z=df("transactions");st.dataframe(z,hide_index=True,use_container_width=True) if not z.empty else st.info("No transactions.")
    with honors:
        if r.empty:st.info("Import rosters first.")
        else:
            rr=r[r.League.eq(league)];pid=st.selectbox("Player",rr.PlayerID.tolist(),format_func=lambda x:f"{rr.loc[rr.PlayerID.eq(x),'Player'].iloc[0]} — {rr.loc[rr.PlayerID.eq(x),'Team'].iloc[0]}",key="honorpid")
            honor=st.selectbox("Selection",["All-Star","All-Season First Team","All-Season Second Team","All-Season Honorable Mention"]);designation=st.text_input("Designation");notes=st.text_input("Notes",key="hn")
            if st.button("Record selection"):
                row=rr[rr.PlayerID.eq(pid)].iloc[0];L["selections"].append({"ID":"S-"+uuid.uuid4().hex[:8].upper(),"League":league,"PlayerID":pid,"Player":row.Player,"Team":row.Team,"Selection":honor,"Designation":designation,"Notes":notes});st.rerun()
            z=df("selections");z=z[z.League.eq(league)] if not z.empty and "League" in z else z
            st.dataframe(z,hide_index=True,use_container_width=True) if not z.empty else st.info("No selections.")

elif page=="Commissioner Overrides":
    st.header(f"{league} Commissioner Overrides")
    t=st.selectbox("Team",teams(league));cur=L["overrides"]["team"].get(t,{})
    p=st.number_input("Points adjustment",value=int(cur.get("PTS",0)),step=1);w=st.number_input("Win adjustment",value=int(cur.get("W",0)),step=1);ls=st.number_input("Loss adjustment",value=int(cur.get("L",0)),step=1);o=st.number_input("OTL adjustment",value=int(cur.get("OTL",0)),step=1)
    if st.button("Save adjustment"):L["overrides"]["team"][t]={"PTS":p,"W":w,"L":ls,"OTL":o};st.rerun()

elif page=="Backup / Export":
    st.download_button("Download complete JSON backup",json.dumps(L,indent=2),"LHA_MLH_backup.json","application/json")
    u=st.file_uploader("Restore backup",type=["json"])
    if u and st.button("Restore"):
        try:
            st.session_state.L=json.loads(u.getvalue().decode("utf-8"))
            st.rerun()
        except Exception as e:
                st.error(str(e))
    for name,data in [(f"{league}_standings",standings(league)),(f"{league}_skaters",skaters(league)),(f"{league}_goalies",goalies(league))]:
        st.download_button("Download "+name+".csv",data.to_csv(index=False),name+".csv","text/csv",disabled=data.empty)
