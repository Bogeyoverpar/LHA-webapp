import streamlit as st
import pandas as pd
import numpy as np
import random,json,io,uuid
from copy import deepcopy
st.set_page_config(page_title="LHA League Manager v2.3.3",page_icon="🏒",layout="wide")

DIV={"East":["Boston Titans","D.C. Daggers","Toronto Stars","New York Chiefs","Ottawa Capitals","Philadelphia Liberty"],
"West":["Seattle Wildcats","Vancouver Pilots","Los Angeles Jets","Colorado Knights","Detroit Flames","Chicago Railers"]}
SET={"assist_probs":[.08,.27,.65],"learning":.20,"win_pts":2,"otl_pts":1}
def fresh(): return {"version":2.3,"rosters":[],"schedule":[],"games":[],"transactions":[],"selections":[],"overrides":{"team":{},"status":{},"seed":{}},"playoffs":{"generated":False,"series":[],"champion":None},"settings":deepcopy(SET)}
if "L" not in st.session_state: st.session_state.L=fresh()
L=st.session_state.L
for k,v in fresh().items():
    if k not in L:L[k]=deepcopy(v)
if "team_info" not in L:
    L["team_info"]={}
for _division,_teams in DIV.items():
    for _team in _teams:
        L["team_info"].setdefault(_team,{"Coach":"","GM":"","Arena":"","Notes":""})

# v2.3 migration: permanent player IDs and league level
for rec in L.get("rosters",[]):
    if not rec.get("PlayerID"):
        rec["PlayerID"]="P-"+uuid.uuid4().hex[:10].upper()
    rec.setdefault("Level","LHA")

ROSTER_COLS=["PlayerID","Team","Player","Position","Line","Scoring","Playmaking","Active","Level"]
SCHEDULE_COLS=["Week","Away","Home","Date","GameID"]
def df(k):
    rows=L.get(k,[])
    if k=="rosters":
        return pd.DataFrame(rows,columns=ROSTER_COLS) if not rows else pd.DataFrame(rows).reindex(columns=ROSTER_COLS)
    if k=="schedule":
        return pd.DataFrame(rows,columns=SCHEDULE_COLS) if not rows else pd.DataFrame(rows).reindex(columns=SCHEDULE_COLS)
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
def roster_import(d):
    a={str(c).strip().lower():c for c in d.columns}
    miss=[x for x in ["team","player","position","line"] if x not in a]
    if miss:raise ValueError("Missing: "+", ".join(miss))
    o=pd.DataFrame({"Team":d[a["team"]].astype(str).str.strip(),"Player":d[a["player"]].astype(str).str.strip(),
    "Position":d[a["position"]].astype(str).str.strip(),"Line":pd.to_numeric(d[a["line"]],errors="coerce").fillna(3).clip(1,4).astype(int)})
    for c in ["Scoring","Playmaking"]:
        o[c]=pd.to_numeric(d[a[c.lower()]],errors="coerce").fillna(70).clip(1,99) if c.lower() in a else 70
    o["Active"]=d[a["active"]].astype(str).str.lower().isin(["true","1","yes","y"]) if "active" in a else True
    o.insert(0,"PlayerID",["P-"+uuid.uuid4().hex[:10].upper() for _ in range(len(o))])
    o["Level"]=d[a["level"]].astype(str).str.strip() if "level" in a else "LHA"
    return o[(o.Team!="")&(o.Player!="")]
def schedule_import(d):
    a={str(c).strip().lower():c for c in d.columns};miss=[x for x in ["week","away","home"] if x not in a]
    if miss:raise ValueError("Missing: "+", ".join(miss))
    o=pd.DataFrame({"Week":pd.to_numeric(d[a["week"]],errors="coerce").fillna(1).astype(int),"Away":d[a["away"]].astype(str).str.strip(),"Home":d[a["home"]].astype(str).str.strip()})
    o["Date"]=d[a["date"]].astype(str) if "date" in a else ""
    o["GameID"]=[f"REG-W{w:02d}-{i+1:03d}" for i,w in enumerate(o.Week)]
    return o
def validation():
    r=df("rosters");e=[]
    if r.empty:return ["Roster is empty."]
    dup=r[r.duplicated(["Team","Player"],False)]
    if not dup.empty:e.append("Duplicate players: "+", ".join((dup.Team+" — "+dup.Player).drop_duplicates()))
    known=sum(DIV.values(),[])
    bad=sorted(set(r.Team)-set(known))
    if bad:e.append("Unknown division assignment: "+", ".join(bad))
    for t in sorted(r.Team.unique()):
        if not ((r.Team==t)&r.Position.map(P).eq("G")&r.Active.astype(bool)).any():e.append(t+" has no active goalie.")
    return e
def roster(t,g=False):
    r=df("rosters")
    if r.empty:
        return pd.DataFrame(columns=ROSTER_COLS)
    active=r["Active"].fillna(True)
    if active.dtype==object:
        active=active.astype(str).str.lower().isin(["true","1","yes","y"])
    else:
        active=active.astype(bool)
    is_goalie=r["Position"].map(P).eq("G")
    m=(r["Team"].astype(str)==str(t)) & active
    m &= is_goalie if g else ~is_goalie
    return r.loc[m,ROSTER_COLS].drop_duplicates(["Team","Player"]).reset_index(drop=True)
def regular():return [g for g in L["games"] if g.get("Stage","Regular")=="Regular"]
def remaining(t):
    s=df("schedule")
    if s.empty:return 0
    total=((s.Away==t)|(s.Home==t)).sum();played=sum(t in [g["Away"],g["Home"]] for g in regular())
    return max(0,int(total-played))
def standings():
    s={t:{"Team":t,"Division":d,"GP":0,"W":0,"L":0,"OTL":0,"GF":0,"GA":0,"PTS":0} for d,ts in DIV.items() for t in ts}
    for g in regular():
        a,h=g["Away"],g["Home"];ag,hg=g["AwayGoals"],g["HomeGoals"]
        if a not in s or h not in s:continue
        for t,gf,ga in [(a,ag,hg),(h,hg,ag)]:s[t]["GP"]+=1;s[t]["GF"]+=gf;s[t]["GA"]+=ga
        w,l=(a,h) if ag>hg else (h,a);s[w]["W"]+=1;s[w]["PTS"]+=2
        if g["OT"]:s[l]["OTL"]+=1;s[l]["PTS"]+=1
        else:s[l]["L"]+=1
    for t,x in L["overrides"]["team"].items():
        if t in s:
            for k,v in x.items():
                if k in s[t]:s[t][k]+=int(v)
    d=pd.DataFrame(s.values());d["DIFF"]=d.GF-d.GA;d["GR"]=[remaining(t) for t in d.Team];return d
def rank(div):
    d=standings();return d[d.Division==div].sort_values(["PTS","W","DIFF","GF"],ascending=False).reset_index(drop=True)
def statuses(div):
    d=rank(div);out={}
    for i,r in d.iterrows():
        others=d[d.Team!=r.Team].copy();others["MAX"]=others.PTS+others.GR*2;mx=r.PTS+r.GR*2
        po=int((others.MAX>=r.PTS).sum())<=3 # conservative: ties remain live until tiebreak is secure
        elim=(others.PTS>mx).sum()>=4
        dc=(others.MAX<r.PTS).all()
        fifth=d.iloc[4] if len(d)>4 else None
        pom=None if po or elim or fifth is None else max(0,int(fifth.PTS+fifth.GR*2+1-r.PTS))
        dm=None
        if i==0 and not dc and len(d)>1:dm=max(0,int(d.iloc[1].PTS+d.iloc[1].GR*2+1-r.PTS))
        status="Eliminated" if elim else "Division Clinched" if dc else "Playoffs Clinched" if po else "Playoff Position" if i<4 else "In Hunt"
        status=L["overrides"]["status"].get(r.Team,status);out[r.Team]=(status,pom,dm)
    return out
def skaters():
    r=df("rosters")
    if r.empty:return pd.DataFrame()
    b=r[~r.Position.map(P).eq("G")][["Team","Player","Position"]].drop_duplicates().copy();gp={};go={};ast={}
    for g in L["games"]:
        for t in [g["Away"],g["Home"]]:
            for p in roster(t).Player:gp[(t,p)]=gp.get((t,p),0)+1
        for e in g.get("Events",[]):
            k=(e["Team"],e["Scorer"]);go[k]=go.get(k,0)+1
            for a in [e.get("Assist1",""),e.get("Assist2","")]:
                if a:ast[(e["Team"],a)]=ast.get((e["Team"],a),0)+1
    b["GP"]=[gp.get((t,p),0) for t,p in zip(b.Team,b.Player)];b["G"]=[go.get((t,p),0) for t,p in zip(b.Team,b.Player)];b["A"]=[ast.get((t,p),0) for t,p in zip(b.Team,b.Player)];b["PTS"]=b.G+b.A;return b
def goalies():
    rows=[q for g in L["games"] for q in g.get("Goalies",[])]
    if not rows:return pd.DataFrame()
    d=pd.DataFrame(rows);o=[]
    for (t,p),x in d.groupby(["Team","Goalie"]):
        sa=x.SA.sum();sv=x.SV.sum();ga=x.GA.sum();gp=len(x);o.append({"Team":t,"Goalie":p,"GP":gp,"W":(x.Result=="W").sum(),"L":(x.Result=="L").sum(),"OTL":(x.Result=="OTL").sum(),"SA":sa,"SV":sv,"GA":ga,"SO":(x.GA==0).sum(),"SV%":round(sv/sa,3) if sa else 0,"GAA":round(ga/gp,2)})
    return pd.DataFrame(o)
def pick(p,kind,exclude=[]):
    p=p[~p.Player.isin([x for x in exclude if x])].drop_duplicates(["Team","Player"]).reset_index(drop=True)
    if p.empty:return ""
    line=p.Line.map({1:1.45,2:1.18,3:.92,4:.70}).fillna(1).to_numpy(float);positions=p.Position.map(P)
    if kind=="G":attr=p.Scoring.to_numpy(float);pw=np.where(positions.isin(["LW","C","RW","F"]),1.2,.55)
    else:attr=p.Playmaking.to_numpy(float);pw=np.where(positions.isin(["LW","C","RW","F"]),1.05,.95)
    learn=np.ones(len(p));ss=skaters()
    if not ss.empty:
        m=p[["Team","Player"]].merge(ss.groupby(["Team","Player"],as_index=False).agg({"GP":"max","G":"sum","A":"sum"}),how="left",on=["Team","Player"],validate="one_to_one").fillna(0)
        z=(m.G if kind=="G" else m.A).to_numpy(float)/np.maximum(m.GP.to_numpy(float),1)
        if z.max()>0:learn=1+L["settings"]["learning"]*z/z.max()
    w=np.maximum(np.nan_to_num(attr/70*line*pw*learn,nan=.01),.01)
    return random.choices(p.Player.tolist(),weights=w.tolist(),k=1)[0]
def events(t,n):
    p=roster(t);o=[]
    for i in range(n):
        sc=pick(p,"G");na=random.choices([0,1,2],weights=L["settings"]["assist_probs"])[0];a1=pick(p,"A",[sc]) if na else "";a2=pick(p,"A",[sc,a1]) if na==2 else ""
        o.append({"Team":t,"GoalNo":i+1,"Scorer":sc,"Assist1":a1,"Assist2":a2})
    return o
def makegame(gid,week,a,h,ag,hg,ot,agk,asa,hgk,hsa,stage="Regular",sid=None,ev=None):
    if ag==hg:raise ValueError("Final score cannot be tied.")
    if asa<hg or hsa<ag:raise ValueError("Shots against cannot be lower than goals allowed.")
    w=a if ag>hg else h
    qs=[{"Team":a,"Goalie":agk,"SA":asa,"SV":asa-hg,"GA":hg,"Result":"W" if w==a else "OTL" if ot else "L"},{"Team":h,"Goalie":hgk,"SA":hsa,"SV":hsa-ag,"GA":ag,"Result":"W" if w==h else "OTL" if ot else "L"}]
    return {"GameID":gid,"Week":week,"Away":a,"Home":h,"AwayGoals":ag,"HomeGoals":hg,"OT":ot,
            "SeasonType":"Regular" if stage=="Regular" else "Playoffs","Stage":stage,"SeriesID":sid,
            "Events":ev if ev is not None else events(a,ag)+events(h,hg),"Goalies":qs}
def wins(sid):
    s=next(x for x in L["playoffs"]["series"] if x["SeriesID"]==sid);return {t:sum(((g["Away"]==t and g["AwayGoals"]>g["HomeGoals"])or(g["Home"]==t and g["HomeGoals"]>g["AwayGoals"])) for g in L["games"] if g.get("SeriesID")==sid) for t in [s["Team1"],s["Team2"]] if t}
def sync():
    if not L["playoffs"]["generated"]:return
    z={s["SeriesID"]:s for s in L["playoffs"]["series"]};win={}
    for s in z.values():
        for t,n in wins(s["SeriesID"]).items():
            if n>=4:win[s["SeriesID"]]=t
    for d in ["East","West"]:z[d+"-F"]["Team1"]=win.get(d+"-SF1",z[d+"-F"]["Team1"]);z[d+"-F"]["Team2"]=win.get(d+"-SF2",z[d+"-F"]["Team2"])
    z["MMC-F"]["Team1"]=win.get("East-F",z["MMC-F"]["Team1"]);z["MMC-F"]["Team2"]=win.get("West-F",z["MMC-F"]["Team2"]);L["playoffs"]["champion"]=win.get("MMC-F")
def genpo():
    ss=[]
    for d in ["East","West"]:
        ts=rank(d).Team.tolist()[:4];m=L["overrides"]["seed"].get(d,{})
        ts=[m.get(str(i+1),t) for i,t in enumerate(ts)]
        if len(ts)<4:raise ValueError("Need four "+d+" seeds.")
        ss += [{"SeriesID":d+"-SF1","Round":"Division Semifinals","Division":d,"Team1":ts[0],"Team2":ts[3]},{"SeriesID":d+"-SF2","Round":"Division Semifinals","Division":d,"Team1":ts[1],"Team2":ts[2]},{"SeriesID":d+"-F","Round":"Division Finals","Division":d,"Team1":"","Team2":""}]
    ss += [{"SeriesID":"MMC-F","Round":"Meyers Memorial Cup Finals","Division":"Final","Team1":"","Team2":""}]
    L["playoffs"]={"generated":True,"series":ss,"champion":None}


def games_for_type(kind):
    if kind=="Combined": return L["games"]
    return [g for g in L["games"] if g.get("SeasonType","Regular" if g.get("Stage","Regular")=="Regular" else "Playoffs")==kind]

def skaters_by_type(kind):
    chosen=games_for_type(kind); go={};ast={};gp={}
    r=df("rosters")
    for g in chosen:
        for t in [g["Away"],g["Home"]]:
            for _,pr in r[r.Team.eq(t)].iterrows():
                key=pr.get("PlayerID") or (t+"|"+pr.Player); gp[key]=gp.get(key,0)+1
        for e in g.get("Events",[]):
            k=e.get("ScorerID") or (e["Team"]+"|"+e.get("Scorer",""));go[k]=go.get(k,0)+1
            for idkey,namekey in [("Assist1ID","Assist1"),("Assist2ID","Assist2")]:
                nm=e.get(namekey,"")
                if nm:
                    k=e.get(idkey) or (e["Team"]+"|"+nm);ast[k]=ast.get(k,0)+1
    rows=[]
    for _,pr in r[~r.Position.map(P).eq("G")].iterrows():
        k=pr.get("PlayerID") or (pr.Team+"|"+pr.Player)
        if gp.get(k,0) or go.get(k,0) or ast.get(k,0):
            rows.append({"PlayerID":pr.get("PlayerID",""),"Player":pr.Player,"Team":pr.Team,"GP":gp.get(k,0),"G":go.get(k,0),"A":ast.get(k,0),"PTS":go.get(k,0)+ast.get(k,0)})
    return pd.DataFrame(rows)

def goalies_by_type(kind):
    rows=[q for g in games_for_type(kind) for q in g.get("Goalies",[])]
    if not rows:return pd.DataFrame()
    d=pd.DataFrame(rows);o=[]
    for (t,p),x in d.groupby(["Team","Goalie"]):
        sa=x.SA.sum();sv=x.SV.sum();ga=x.GA.sum();gp=len(x)
        o.append({"Team":t,"Goalie":p,"GP":gp,"W":int((x.Result=="W").sum()),"L":int((x.Result=="L").sum()),"OTL":int((x.Result=="OTL").sum()),"SA":sa,"SV":sv,"GA":ga,"SO":int((x.GA==0).sum()),"SV%":round(sv/sa,3) if sa else 0,"GAA":round(ga/gp,2)})
    return pd.DataFrame(o)

def record_transaction(kind,pid,to_team,to_level,notes):
    r=df("rosters"); matches=r.index[r.PlayerID.eq(pid)]
    if not len(matches): raise ValueError("Player not found.")
    i=int(matches[0]); old_team=L["rosters"][i]["Team"]; old_level=L["rosters"][i].get("Level","LHA")
    if kind=="Release": L["rosters"][i]["Active"]=False
    else:
        if to_team:L["rosters"][i]["Team"]=to_team
        if to_level:L["rosters"][i]["Level"]=to_level
        L["rosters"][i]["Active"]=True
    L["transactions"].append({"ID":"T-"+uuid.uuid4().hex[:8].upper(),"Type":kind,"PlayerID":pid,"Player":L["rosters"][i]["Player"],"FromTeam":old_team,"ToTeam":L["rosters"][i]["Team"],"FromLevel":old_level,"ToLevel":L["rosters"][i].get("Level","LHA"),"Notes":notes})

def po_series_schedule(high,low):
    return [(n, low if n in [1,2,6,7] else high, high if n in [1,2,6,7] else low) for n in range(1,8)]

st.title("🏒 LHA League Manager v2.3.3")
page=st.sidebar.radio("League",["Dashboard","Teams","Import / Setup","Weekly Games","Standings","Statistics","Game Log / Edit","Playoffs","Transactions & Honors","Commissioner Overrides","Backup / Export"])
if page=="Teams":
    st.header("Team Center")
    team=st.selectbox("Team",sum(DIV.values(),[]),key="team_page_team")
    division="East" if team in DIV["East"] else "West"
    table=rank(division)
    row=table[table.Team.eq(team)].iloc[0]
    seed=int(table.index[table.Team.eq(team)][0])+1
    q=statuses(division).get(team,("—",None,None))
    info=L["team_info"].setdefault(team,{"Coach":"","GM":"","Arena":"","Notes":""})

    st.subheader(team)
    c=st.columns(6)
    c[0].metric("Division",division)
    c[1].metric("Standing",f"#{seed}")
    c[2].metric("Record",f"{int(row.W)}-{int(row.L)}-{int(row.OTL)}")
    c[3].metric("Points",int(row.PTS))
    c[4].metric("Goal Diff",f"{int(row.DIFF):+d}")
    c[5].metric("Games Remaining",int(row.GR))
    st.caption(f"Playoff status: {q[0]}")

    with st.expander("Team information",expanded=not bool(info.get("Coach"))):
        with st.form("team_info_form"):
            a,b=st.columns(2)
            with a:
                coach=st.text_input("Head Coach",value=info.get("Coach",""))
                arena=st.text_input("Arena / Home Ice",value=info.get("Arena",""))
            with b:
                gm=st.text_input("General Manager / Team Manager",value=info.get("GM",""))
                notes=st.text_area("Team Notes",value=info.get("Notes",""))
            save_info=st.form_submit_button("Save team information")
        if save_info:
            L["team_info"][team]={"Coach":coach,"GM":gm,"Arena":arena,"Notes":notes}
            st.success("Team information saved.")
            st.rerun()

    overview,roster_tab,stats_tab,schedule_tab,history_tab=st.tabs(
        ["Overview","Roster","Statistics","Schedule & Results","Transactions & Honors"]
    )

    with overview:
        a,b=st.columns(2)
        with a:
            st.markdown("#### Staff")
            st.write("**Head Coach:** "+(info.get("Coach") or "Not entered"))
            st.write("**GM / Team Manager:** "+(info.get("GM") or "Not entered"))
            st.write("**Arena:** "+(info.get("Arena") or "Not entered"))
            if info.get("Notes"):st.write(info["Notes"])
        with b:
            st.markdown("#### Season")
            st.write(f"**GF:** {int(row.GF)}")
            st.write(f"**GA:** {int(row.GA)}")
            st.write(f"**Goal differential:** {int(row.DIFF):+d}")
            st.write(f"**Playoff status:** {q[0]}")
            if q[1] is not None:st.write(f"**Playoff magic number:** {q[1]}")
            if q[2] is not None:st.write(f"**Division magic number:** {q[2]}")

    with roster_tab:
        rr=df("rosters")
        rr=rr[(rr.Team.eq(team)) & (rr.Active.astype(bool))].copy() if not rr.empty else rr
        if rr.empty:st.info("No active players on this roster.")
        else:
            rr["Role"]=np.where(rr.Position.map(P).eq("G"),"Goalie","Skater")
            st.dataframe(rr[["Player","Position","Line","Scoring","Playmaking","Level","Role"]].sort_values(["Role","Line","Position","Player"]),hide_index=True,use_container_width=True)

    with stats_tab:
        split=st.radio("Team stat split",["Regular","Playoffs","Combined"],horizontal=True,key="team_stat_split")
        sk=skaters_by_type(split)
        if not sk.empty:
            sk=sk[sk.Team.eq(team)].sort_values(["PTS","G","A"],ascending=False).reset_index(drop=True)
        st.markdown("#### Skaters")
        if sk.empty:st.info("No skater statistics for this split.")
        else:
            sk.insert(0,"Rank",range(1,len(sk)+1))
            st.dataframe(sk[["Rank","Player","GP","G","A","PTS"]],hide_index=True,use_container_width=True)
        gl=goalies_by_type(split)
        if not gl.empty:gl=gl[gl.Team.eq(team)].sort_values(["W","SV%"],ascending=False).reset_index(drop=True)
        st.markdown("#### Goalies")
        if gl.empty:st.info("No goalie statistics for this split.")
        else:st.dataframe(gl[["Goalie","GP","W","L","OTL","SA","SV","GA","SV%","GAA","SO"]],hide_index=True,use_container_width=True)

    with schedule_tab:
        completed=[g for g in L["games"] if team in [g["Away"],g["Home"]]]
        if completed:
            rows=[]
            for g in reversed(completed[-10:]):
                gf=g["AwayGoals"] if g["Away"]==team else g["HomeGoals"]
                ga=g["HomeGoals"] if g["Away"]==team else g["AwayGoals"]
                opp=g["Home"] if g["Away"]==team else g["Away"]
                rows.append({"Type":g.get("SeasonType","Regular"),"Game":g["GameID"],"Opponent":opp,"Site":"Away" if g["Away"]==team else "Home","Result":("W" if gf>ga else "L")+f" {gf}-{ga}"+(" OT" if g["OT"] else "")})
            st.markdown("#### Recent Results")
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        sched=df("schedule")
        done_ids={g["GameID"] for g in regular()}
        upcoming=sched[((sched.Away==team)|(sched.Home==team)) & (~sched.GameID.isin(done_ids))].copy() if not sched.empty else pd.DataFrame()
        st.markdown("#### Upcoming Regular-Season Games")
        if upcoming.empty:st.info("No remaining scheduled games.")
        else:
            upcoming["Opponent"]=np.where(upcoming.Away.eq(team),upcoming.Home,upcoming.Away)
            upcoming["Site"]=np.where(upcoming.Away.eq(team),"Away","Home")
            st.dataframe(upcoming[["Week","Date","Opponent","Site"]].head(10),hide_index=True,use_container_width=True)

    with history_tab:
        tx=df("transactions")
        if not tx.empty:
            tx=tx[(tx.FromTeam.eq(team))|(tx.ToTeam.eq(team))]
        st.markdown("#### Transactions")
        st.dataframe(tx,hide_index=True,use_container_width=True) if not tx.empty else st.info("No transactions involving this team.")
        sel=df("selections")
        if not sel.empty:
            sel=sel[sel.Team.eq(team)] if "Team" in sel.columns else sel.iloc[0:0]
        st.markdown("#### Honors")
        st.dataframe(sel,hide_index=True,use_container_width=True) if not sel.empty else st.info("No recorded honors for this team.")

elif page=="Import / Setup":
    st.caption(f"Current session: {len(df('rosters'))} roster rows • {len(df('schedule'))} scheduled games • {len(L['games'])} completed games")
    a,b=st.columns(2)
    with a:
        u=st.file_uploader("Roster CSV/XLSX",type=["csv","xlsx"])
        if u and st.button("Import roster"):
            try:
                imported = roster_import(upload(u))
                L["rosters"] = imported.to_dict("records")
                errors = validation()
                if errors:
                    for error in errors:
                        st.warning(error)
                else:
                    st.success("Roster imported and validated.")
            except Exception as e:
                st.error(str(e))
    with b:
        u=st.file_uploader("Schedule CSV/XLSX",type=["csv","xlsx"],key="su")
        if u and st.button("Import schedule"):
            try:
                imported = schedule_import(upload(u))
                L["schedule"] = imported.to_dict("records")
                st.success(f"Schedule imported: {len(imported)} games.")
            except Exception as e:
                st.error(str(e))
elif page=="Weekly Games":
    s=df("schedule")
    if s.empty:st.info("Import a schedule first.")
    else:
        wk=st.selectbox("Week",sorted(s.Week.unique()));done={g["GameID"] for g in regular()}
        if df("rosters").empty:
            st.error("No roster is loaded in this session. Import the roster under Import / Setup, or restore a league backup, before entering games.")
            st.stop()
        known_teams=set(sum(DIV.values(),[]))
        bad_games=s[(~s["Away"].isin(known_teams)) | (~s["Home"].isin(known_teams))]
        if not bad_games.empty:
            st.error("The schedule contains team names that do not exactly match the LHA team list. Fix the schedule import before entering games.")
            st.dataframe(bad_games[["Week","Away","Home"]],hide_index=True,use_container_width=True)
            st.stop()
        for _,x in s[s.Week==wk].iterrows():
            with st.expander(("✅ " if x.GameID in done else "⬜ ")+str(x.Away)+" at "+str(x.Home),expanded=x.GameID not in done):
                if x.GameID in done:st.write("Completed — edit it under Game Log / Edit.");continue
                A=roster(x.Away,True).Player.tolist();H=roster(x.Home,True).Player.tolist()
                if not A or not H:st.error("Both teams need an active goalie.");continue
                with st.form(x.GameID):
                    c1,c2=st.columns(2)
                    with c1:ag=st.number_input(x.Away+" goals",0,30,0);agk=st.selectbox(x.Away+" goalie",A);asa=st.number_input(x.Away+" goalie SA",0,100,25)
                    with c2:hg=st.number_input(x.Home+" goals",0,30,0);hgk=st.selectbox(x.Home+" goalie",H);hsa=st.number_input(x.Home+" goalie SA",0,100,25)
                    ot=st.checkbox("OT / shootout");go=st.form_submit_button("Finalize & distribute")
                if go:
                    try:
                        game = makegame(x.GameID,int(x.Week),x.Away,x.Home,ag,hg,ot,agk,asa,hgk,hsa)
                        L["games"].append(game)
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
elif page=="Standings":
    st.header("Standings & Playoff Race")
    for col,dv in zip(st.columns(2),["East","West"]):
        with col:
            st.subheader(dv);d=rank(dv);q=statuses(dv);d.insert(0,"Seed",range(1,len(d)+1));d["Status"]=[q[t][0] for t in d.Team];d["PO Magic"]=[q[t][1] for t in d.Team];d["DIV Magic"]=[q[t][2] for t in d.Team]
            st.dataframe(d[["Seed","Team","GP","W","L","OTL","GF","GA","DIFF","PTS","GR","Status","PO Magic","DIV Magic"]],hide_index=True,use_container_width=True)
    d=standings().sort_values(["PTS","W","DIFF","GF"],ascending=False).reset_index(drop=True)
    if len(d):
        leader=d.iloc[0];other=d.iloc[1:].copy();other["MAX"]=other.PTS+other.GR*2;cl=(other.MAX<leader.PTS).all();magic=None if cl else max(0,int(other.MAX.max()+1-leader.PTS))
        st.info(f"Best overall: {leader.Team} — "+("best regular-season record clinched" if cl else f"league magic # {magic}"))
elif page=="Statistics":
    st.header("League Statistics")
    kind=st.radio("Stat split",["Regular","Playoffs","Combined"],horizontal=True)
    skater_tab,goalie_tab=st.tabs(["Skaters","Goalies"])
    with skater_tab:
        d=skaters_by_type(kind)
        if d.empty:st.info(f"No {kind.lower()} skater statistics yet.")
        else:
            sort_col=st.selectbox("Sort skaters by",["PTS","G","A","GP"],key="skater_sort")
            d=d.sort_values([sort_col,"G","A"],ascending=False).reset_index(drop=True)
            d.insert(0,"Rank",range(1,len(d)+1))
            st.dataframe(d[["Rank","Player","Team","GP","G","A","PTS"]],hide_index=True,use_container_width=True)
    with goalie_tab:
        d=goalies_by_type(kind)
        if d.empty:st.info(f"No {kind.lower()} goalie statistics yet.")
        else:
            sort_col=st.selectbox("Sort goalies by",["W","SV%","GAA","SO","GP"],key="goalie_sort")
            d=d.sort_values(sort_col,ascending=(sort_col=="GAA")).reset_index(drop=True)
            d.insert(0,"Rank",range(1,len(d)+1))
            st.dataframe(d[["Rank","Goalie","Team","GP","W","L","OTL","SA","SV","GA","SV%","GAA","SO"]],hide_index=True,use_container_width=True)

elif page=="Game Log / Edit":
    if not L["games"]:st.info("No games.")
    else:
        i=st.selectbox("Game",range(len(L["games"])),format_func=lambda i:f"{L['games'][i]['GameID']} — {L['games'][i]['Away']} {L['games'][i]['AwayGoals']}, {L['games'][i]['Home']} {L['games'][i]['HomeGoals']}");g=L["games"][i]
        with st.form("edit"):
            c1,c2=st.columns(2);A=roster(g["Away"],True).Player.tolist();H=roster(g["Home"],True).Player.tolist()
            oldA=g["Goalies"][0]["Goalie"]; oldH=g["Goalies"][1]["Goalie"]
            if oldA and oldA not in A: A=[oldA]+A
            if oldH and oldH not in H: H=[oldH]+H
            if not A or not H:
                st.error("This game cannot be edited until both teams have a goalie available in the roster.")
                st.stop()
            with c1:ag=st.number_input(g["Away"]+" goals",0,30,g["AwayGoals"]);agk=st.selectbox("Away goalie",A,index=A.index(oldA) if oldA in A else 0);asa=st.number_input("Away goalie SA",0,100,g["Goalies"][0]["SA"])
            with c2:hg=st.number_input(g["Home"]+" goals",0,30,g["HomeGoals"]);hgk=st.selectbox("Home goalie",H,index=H.index(oldH) if oldH in H else 0);hsa=st.number_input("Home goalie SA",0,100,g["Goalies"][1]["SA"])
            ot=st.checkbox("OT/SO",g["OT"]);regen=st.checkbox("Regenerate scoring events",False);save=st.form_submit_button("Save game corrections")
        if save:
            try:
                preserved_events = None if regen or ag!=g["AwayGoals"] or hg!=g["HomeGoals"] else g["Events"]
                L["games"][i] = makegame(
                    g["GameID"],g["Week"],g["Away"],g["Home"],ag,hg,ot,
                    agk,asa,hgk,hsa,g["Stage"],g.get("SeriesID"),preserved_events
                )
                L["games"][i]["SeasonType"] = g.get("SeasonType","Regular" if g.get("Stage")=="Regular" else "Playoffs")
                sync()
                st.rerun()
            except Exception as e:
                st.error(str(e))
        st.subheader("Manual scorers / assists");edited=[]
        for j,e in enumerate(g["Events"]):
            with st.expander(f"Goal {j+1}: {e['Scorer']} — {e['Team']}"):
                ps=roster(e["Team"]).Player.tolist();opts=[""]+ps;sc=st.selectbox("Scorer",ps,index=ps.index(e["Scorer"]) if e["Scorer"] in ps else 0,key=f"s{i}{j}");a1=st.selectbox("Assist 1",opts,index=opts.index(e.get("Assist1","")) if e.get("Assist1","") in opts else 0,key=f"x{i}{j}");a2=st.selectbox("Assist 2",opts,index=opts.index(e.get("Assist2","")) if e.get("Assist2","") in opts else 0,key=f"y{i}{j}");edited.append({**e,"Scorer":sc,"Assist1":a1,"Assist2":a2})
        if st.button("Save scoring edits"):L["games"][i]["Events"]=edited;st.rerun()
        if st.button("Delete game"):L["games"].pop(i);sync();st.rerun()
elif page=="Playoffs":
    st.header("Meyers Memorial Cup Playoffs")
    if not L["playoffs"]["generated"]:
        if st.button("Generate playoff bracket",type="primary"):genpo();st.rerun()
    else:
        sync()
        if L["playoffs"]["champion"]:st.success("🏆 Meyers Memorial Cup Champion: "+L["playoffs"]["champion"])
        for ser in L["playoffs"]["series"]:
            # Old series records use Team1/Team2. Team1 is the higher seed when generated.
            high=ser.get("HighSeed") or ser.get("Team1","");low=ser.get("LowSeed") or ser.get("Team2","")
            with st.expander(f"{ser['Round']} — {ser['Division']}"+(f" • {high} vs {low}" if high and low else " • awaiting teams"),expanded=bool(high and low)):
                if not high or not low:
                    st.caption("Waiting for the preceding series.");continue
                # Normalize for existing series-win function.
                ser["Team1"]=high;ser["Team2"]=low
                w=wins(ser["SeriesID"]);st.markdown(f"### {high} {w.get(high,0)} — {w.get(low,0)} {low}")
                played={int(g["Week"]):g for g in L["games"] if g.get("SeriesID")==ser["SeriesID"]}
                series_done=max(w.values() or [0])>=4
                next_game=min([n for n in range(1,8) if n not in played],default=8)
                for n,away,home in po_series_schedule(high,low):
                    with st.container(border=True):
                        st.markdown(f"**Game {n}: {away} at {home}**")
                        if n in played:
                            g=played[n];st.success(f"Final — {away} {g['AwayGoals']}, {home} {g['HomeGoals']}"+(" (OT/SO)" if g["OT"] else ""));st.caption("Edit from Game Log / Edit.")
                        elif series_done:
                            st.caption("Not necessary — series completed.")
                        elif n!=next_game:
                            st.caption("Locked until the preceding game is completed.")
                        else:
                            A=roster(away,True).Player.tolist();H=roster(home,True).Player.tolist()
                            if not A or not H:st.error("Both teams need an active goalie.");continue
                            with st.form(f"{ser['SeriesID']}-G{n}"):
                                c1,c2=st.columns(2)
                                with c1:ag=st.number_input(away+" goals",0,30,0,key=f"pag{ser['SeriesID']}{n}");agk=st.selectbox(away+" goalie",A,key=f"pak{ser['SeriesID']}{n}");asa=st.number_input(away+" goalie SA",0,100,25,key=f"pas{ser['SeriesID']}{n}")
                                with c2:hg=st.number_input(home+" goals",0,30,0,key=f"phg{ser['SeriesID']}{n}");hgk=st.selectbox(home+" goalie",H,key=f"phk{ser['SeriesID']}{n}");hsa=st.number_input(home+" goalie SA",0,100,25,key=f"phs{ser['SeriesID']}{n}")
                                ot=st.checkbox("OT / shootout",key=f"pot{ser['SeriesID']}{n}");go=st.form_submit_button("Finalize Game "+str(n))
                            if go:
                                try:
                                    game=makegame(f"PO-{ser['SeriesID']}-G{n}",n,away,home,ag,hg,ot,agk,asa,hgk,hsa,ser["Round"],ser["SeriesID"])
                                    game["SeasonType"]="Playoffs";L["games"].append(game);sync();st.rerun()
                                except Exception as e:
                                    st.error(str(e))

elif page=="Transactions & Honors":
    st.header("Transactions & Honors")
    r=df("rosters")
    moves,log,honors=st.tabs(["Personnel Moves","Transaction Log","All-Star / All-Season"])
    with moves:
        if r.empty: st.info("Import a roster first.")
        else:
            active=r[r.Active.astype(bool)].copy()
            pid=st.selectbox("Player",active.PlayerID.tolist(),format_func=lambda x:f"{active.loc[active.PlayerID==x,'Player'].iloc[0]} — {active.loc[active.PlayerID==x,'Team'].iloc[0]}")
            kind=st.selectbox("Transaction",["Trade / Transfer","Call Up","Send Down","Release"])
            to_team=st.selectbox("Destination team",sum(DIV.values(),[]),disabled=kind=="Release")
            to_level=st.selectbox("Destination level",["LHA","Minor League"],index=1 if kind=="Send Down" else 0,disabled=kind=="Release")
            notes=st.text_input("Notes")
            if st.button("Record transaction & update roster"):
                record_transaction(kind,pid,to_team,to_level,notes);st.success("Transaction recorded.");st.rerun()
    with log:
        d=df("transactions");st.dataframe(d,hide_index=True,use_container_width=True) if not d.empty else st.info("No transactions.")
    with honors:
        if r.empty:st.info("Import a roster first.")
        else:
            pid=st.selectbox("Player",r.PlayerID.tolist(),format_func=lambda x:f"{r.loc[r.PlayerID==x,'Player'].iloc[0]} — {r.loc[r.PlayerID==x,'Team'].iloc[0]}",key="honorpid")
            honor=st.selectbox("Selection",["All-Star","All-Season First Team","All-Season Second Team","All-Season Honorable Mention"])
            designation=st.text_input("Designation",placeholder="East All-Stars, First Team C, etc.")
            notes=st.text_input("Notes",key="honornotes")
            if st.button("Record selection"):
                row=r[r.PlayerID.eq(pid)].iloc[0];L["selections"].append({"ID":"S-"+uuid.uuid4().hex[:8].upper(),"PlayerID":pid,"Player":row.Player,"Team":row.Team,"Selection":honor,"Designation":designation,"Notes":notes});st.rerun()
            d=df("selections");st.dataframe(d,hide_index=True,use_container_width=True) if not d.empty else st.info("No selections.")

elif page=="Commissioner Overrides":
    st.header("Commissioner Overrides")
    a,b,c=st.tabs(["Standings","Status","Seeds"])
    with a:
        t=st.selectbox("Team",sum(DIV.values(),[]));cur=L["overrides"]["team"].get(t,{});p=st.number_input("Points adjustment",value=int(cur.get("PTS",0)),step=1);w=st.number_input("Win adjustment",value=int(cur.get("W",0)),step=1);ls=st.number_input("Loss adjustment",value=int(cur.get("L",0)),step=1);o=st.number_input("OTL adjustment",value=int(cur.get("OTL",0)),step=1)
        if st.button("Save adjustment"):L["overrides"]["team"][t]={"PTS":p,"W":w,"L":ls,"OTL":o};st.rerun()
        if st.button("Reset adjustment"):L["overrides"]["team"].pop(t,None);st.rerun()
    with b:
        t=st.selectbox("Team",sum(DIV.values(),[]),key="st");vals=["Automatic","In Hunt","Playoff Position","Playoffs Clinched","Division Clinched","Best Record Clinched","Eliminated"];v=st.selectbox("Status",vals)
        if st.button("Save status"):L["overrides"]["status"].pop(t,None) if v=="Automatic" else L["overrides"]["status"].update({t:v});st.rerun()
    with c:
        dv=st.selectbox("Division",["East","West"]);auto=rank(dv).Team.tolist();sel={}
        for n in range(1,5):sel[str(n)]=st.selectbox(f"Seed #{n}",DIV[dv],index=DIV[dv].index(L["overrides"]["seed"].get(dv,{}).get(str(n),auto[n-1] if len(auto)>=n else DIV[dv][n-1])),key=f"sd{dv}{n}")
        if st.button("Save seeds"):
            if len(set(sel.values()))<4:st.error("Seeds must be unique.")
            else:L["overrides"]["seed"][dv]=sel;st.rerun()
elif page=="Backup / Export":
    st.download_button("Download complete JSON backup",json.dumps(L,indent=2),"LHA_backup.json","application/json");u=st.file_uploader("Restore backup",type=["json"])
    if u and st.button("Restore"):
        try:
            restored=json.loads(u.getvalue().decode("utf-8"))
            if not isinstance(restored,dict): raise ValueError("Backup is not a valid league-state object.")
            base=fresh()
            for k,v in base.items():
                if k not in restored: restored[k]=deepcopy(v)
            if not isinstance(restored.get("rosters"),list) or not isinstance(restored.get("games"),list):
                raise ValueError("Backup is missing required roster/game data.")
            restored["version"]=2.2
            st.session_state.L=restored
            st.success("Backup restored.")
            st.rerun()
        except Exception as e:
            st.error("Could not restore backup: " + str(e))
    for n,d in [("standings",standings()),("skaters",skaters()),("goalies",goalies())]:st.download_button("Download "+n+".csv",d.to_csv(index=False),n+".csv","text/csv",disabled=d.empty)
elif page=="Dashboard":
    st.header("LHA Dashboard");c=st.columns(4);c[0].metric("Teams",12);c[1].metric("Games played",len(regular()));c[2].metric("Goals",sum(g["AwayGoals"]+g["HomeGoals"] for g in regular()));c[3].metric("Playoffs","Active" if L["playoffs"]["generated"] else "Not started")
    for col,dv in zip(st.columns(2),["East","West"]):
        with col:st.subheader(dv);st.dataframe(rank(dv)[["Team","GP","W","L","OTL","PTS"]],hide_index=True,use_container_width=True)

else:
    st.error(f"Unknown page route: {page}")
