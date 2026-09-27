import streamlit as st
import pandas as pd
import numpy as np
import json, io, random
from datetime import datetime

st.set_page_config(page_title="LHA League Manager", page_icon="🏒", layout="wide")

DEFAULTS = {
    "assist_probs": [0.08, 0.27, 0.65],   # 0, 1, 2 assists
    "season_learning": 0.20,
    "forward_goal_bonus": 1.20,
    "defense_goal_bonus": 0.55,
    "forward_assist_bonus": 1.05,
    "defense_assist_bonus": 0.95,
}

def blank_state():
    return {
        "league_name": "LHA",
        "rosters": [],
        "schedule": [],
        "games": [],
        "events": [],
        "goalie_games": [],
        "settings": DEFAULTS.copy(),
    }

if "league" not in st.session_state:
    st.session_state.league = blank_state()

L = st.session_state.league

def df(key):
    return pd.DataFrame(L.get(key, []))

def norm_pos(x):
    return str(x).strip().upper()

def load_table(upload):
    name = upload.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(upload)
    xls = pd.ExcelFile(upload)
    return pd.read_excel(upload, sheet_name=0)

def ensure_roster_columns(d):
    aliases = {c.lower().strip(): c for c in d.columns}
    required = ["team", "player", "position"]
    missing = [x for x in required if x not in aliases]
    if missing:
        raise ValueError("Roster needs columns: Team, Player, Position. Missing: " + ", ".join(missing))
    out = pd.DataFrame()
    out["Team"] = d[aliases["team"]].astype(str).str.strip()
    out["Player"] = d[aliases["player"]].astype(str).str.strip()
    out["Position"] = d[aliases["position"]].astype(str).str.strip()
    for col, default in [("Line", 3), ("Scoring", 70), ("Playmaking", 70), ("Active", True)]:
        src = aliases.get(col.lower())
        out[col] = d[src] if src else default
    out["Line"] = pd.to_numeric(out["Line"], errors="coerce").fillna(3).clip(1, 4).astype(int)
    out["Scoring"] = pd.to_numeric(out["Scoring"], errors="coerce").fillna(70).clip(1, 99)
    out["Playmaking"] = pd.to_numeric(out["Playmaking"], errors="coerce").fillna(70).clip(1, 99)
    out["Active"] = out["Active"].astype(str).str.lower().isin(["true","1","yes","y"]) if out["Active"].dtype == object else out["Active"].astype(bool)
    out = out[(out.Team != "") & (out.Player != "")]
    return out

def ensure_schedule_columns(d):
    aliases = {c.lower().strip(): c for c in d.columns}
    required = ["week", "away", "home"]
    missing = [x for x in required if x not in aliases]
    if missing:
        raise ValueError("Schedule needs columns: Week, Away, Home. Missing: " + ", ".join(missing))
    out = pd.DataFrame()
    out["Week"] = pd.to_numeric(d[aliases["week"]], errors="coerce").fillna(1).astype(int)
    out["Away"] = d[aliases["away"]].astype(str).str.strip()
    out["Home"] = d[aliases["home"]].astype(str).str.strip()
    if "date" in aliases:
        out["Date"] = d[aliases["date"]].astype(str)
    else:
        out["Date"] = ""
    out["GameID"] = [f"W{w:02d}-{i+1:03d}" for i,w in enumerate(out["Week"])]
    return out

def completed_game_ids():
    return {g["GameID"] for g in L["games"]}

def player_totals():
    r = df("rosters")
    if r.empty:
        return pd.DataFrame()
    skaters = r[~r.Position.map(norm_pos).eq("G")].copy()
    base = skaters[["Team","Player","Position"]].copy()
    ev = df("events")
    if ev.empty:
        base["GP"] = base["G"] = base["A"] = base["PTS"] = 0
        return base
    games = df("games")
    gp_rows = []
    for _, g in games.iterrows():
        for team in [g["Away"], g["Home"]]:
            active = skaters[(skaters.Team == team) & skaters.Active.astype(bool)]
            for p in active.Player:
                gp_rows.append((team,p))
    gp = pd.DataFrame(gp_rows, columns=["Team","Player"]).value_counts().rename("GP").reset_index() if gp_rows else pd.DataFrame(columns=["Team","Player","GP"])
    goals = ev.groupby(["Team","Scorer"]).size().rename("G").reset_index().rename(columns={"Scorer":"Player"})
    assists = pd.concat([
        ev[["Team","Assist1"]].rename(columns={"Assist1":"Player"}),
        ev[["Team","Assist2"]].rename(columns={"Assist2":"Player"})
    ], ignore_index=True)
    assists = assists[assists.Player.notna() & (assists.Player != "")]
    assists = assists.groupby(["Team","Player"]).size().rename("A").reset_index()
    out = base.merge(gp,on=["Team","Player"],how="left").merge(goals,on=["Team","Player"],how="left").merge(assists,on=["Team","Player"],how="left")
    for c in ["GP","G","A"]:
        out[c] = out[c].fillna(0).astype(int)
    out["PTS"] = out["G"] + out["A"]
    return out

def goalie_totals():
    gg = df("goalie_games")
    if gg.empty:
        return pd.DataFrame(columns=["Team","Goalie","GP","W","L","OTL","SA","SV","GA","SO","SV%","GAA"])
    rows=[]
    for (team,goalie),x in gg.groupby(["Team","Goalie"]):
        gp=len(x); ga=x.GA.sum(); sv=x.SV.sum(); sa=x.SA.sum()
        rows.append({
            "Team":team,"Goalie":goalie,"GP":gp,
            "W":int((x.Result=="W").sum()),"L":int((x.Result=="L").sum()),"OTL":int((x.Result=="OTL").sum()),
            "SA":int(sa),"SV":int(sv),"GA":int(ga),"SO":int((x.GA==0).sum()),
            "SV%": round(sv/sa,3) if sa else 0,
            "GAA": round(ga/gp,2) if gp else 0,
        })
    return pd.DataFrame(rows)

def standings():
    teams = sorted(df("rosters").Team.unique()) if not df("rosters").empty else []
    stats = {t: {"Team":t,"GP":0,"W":0,"L":0,"OTL":0,"GF":0,"GA":0,"PTS":0} for t in teams}
    for g in L["games"]:
        a,h=g["Away"],g["Home"]; ag,hg=int(g["AwayGoals"]),int(g["HomeGoals"])
        if a not in stats: stats[a]={"Team":a,"GP":0,"W":0,"L":0,"OTL":0,"GF":0,"GA":0,"PTS":0}
        if h not in stats: stats[h]={"Team":h,"GP":0,"W":0,"L":0,"OTL":0,"GF":0,"GA":0,"PTS":0}
        for t,gf,ga in [(a,ag,hg),(h,hg,ag)]:
            stats[t]["GP"]+=1; stats[t]["GF"]+=gf; stats[t]["GA"]+=ga
        if ag>hg:
            stats[a]["W"]+=1; stats[a]["PTS"]+=2
            if g.get("OT",False): stats[h]["OTL"]+=1; stats[h]["PTS"]+=1
            else: stats[h]["L"]+=1
        else:
            stats[h]["W"]+=1; stats[h]["PTS"]+=2
            if g.get("OT",False): stats[a]["OTL"]+=1; stats[a]["PTS"]+=1
            else: stats[a]["L"]+=1
    out=pd.DataFrame(stats.values())
    if out.empty: return out
    out["DIFF"]=out["GF"]-out["GA"]
    return out.sort_values(["PTS","W","DIFF","GF"],ascending=[False,False,False,False]).reset_index(drop=True)

def weighted_pick(players, kind, excluded=None):
    excluded = set(excluded or [])
    p = players[~players.Player.isin(excluded)].copy()
    if p.empty: return None
    line_weight = p.Line.map({1:1.45,2:1.18,3:0.92,4:0.70}).fillna(1)
    pos = p.Position.map(norm_pos)
    if kind=="goal":
        attr=p.Scoring.astype(float)
        pos_weight=np.where(pos.isin(["LW","C","RW","F"]),L["settings"]["forward_goal_bonus"],L["settings"]["defense_goal_bonus"])
    else:
        attr=p.Playmaking.astype(float)
        pos_weight=np.where(pos.isin(["LW","C","RW","F"]),L["settings"]["forward_assist_bonus"],L["settings"]["defense_assist_bonus"])
    season=player_totals()
    learn=np.ones(len(p))
    if not season.empty and L["settings"]["season_learning"]>0:
        m=p.merge(season[["Team","Player","GP","G","A"]],on=["Team","Player"],how="left").fillna(0)
        rate=(m["G"] if kind=="goal" else m["A"])/(m["GP"].clip(lower=1))
        if rate.max()>0:
            learn=1 + L["settings"]["season_learning"]*(rate/(rate.max()+1e-9))
    weights=np.maximum(0.01, attr/70*line_weight*pos_weight*learn)
    return random.choices(list(p.Player), weights=list(weights), k=1)[0]

def distribute_goals(team, n_goals, game_id):
    roster=df("rosters")
    p=roster[(roster.Team==team) & roster.Active.astype(bool) & ~roster.Position.map(norm_pos).eq("G")].copy()
    events=[]
    probs=L["settings"]["assist_probs"]
    for goal_no in range(1,int(n_goals)+1):
        scorer=weighted_pick(p,"goal")
        n_ast=random.choices([0,1,2],weights=probs,k=1)[0]
        a1=weighted_pick(p,"assist",[scorer]) if n_ast>=1 else None
        a2=weighted_pick(p,"assist",[scorer,a1]) if n_ast>=2 else None
        events.append({"GameID":game_id,"Team":team,"GoalNo":goal_no,"Scorer":scorer,"Assist1":a1 or "","Assist2":a2 or ""})
    return events

def team_goalies(team):
    r=df("rosters")
    if r.empty:return []
    return list(r[(r.Team==team)&r.Position.map(norm_pos).eq("G")].Player)

st.title("🏒 LHA League Manager")
st.caption("Schedule → enter results → distribute scoring → standings and leaders update automatically.")

with st.sidebar:
    page=st.radio("League",["Dashboard","Import / Setup","Weekly Games","Standings","League Leaders","Game Log","Backup / Export"])
    st.text_input("League name", key="league_name_ui", value=L.get("league_name","LHA"), on_change=lambda: None)
    L["league_name"]=st.session_state.league_name_ui

if page=="Import / Setup":
    st.header("Import league")
    c1,c2=st.columns(2)
    with c1:
        st.subheader("Rosters")
        st.write("Required: **Team, Player, Position**. Optional: Line, Scoring, Playmaking, Active.")
        up=st.file_uploader("Upload roster CSV/XLSX",type=["csv","xlsx"],key="roster")
        if up and st.button("Import roster"):
            try:
                L["rosters"]=ensure_roster_columns(load_table(up)).to_dict("records")
                st.success(f"Imported {len(L['rosters'])} players.")
            except Exception as e: st.error(str(e))
    with c2:
        st.subheader("Schedule")
        st.write("Required: **Week, Away, Home**. Optional: Date.")
        up2=st.file_uploader("Upload schedule CSV/XLSX",type=["csv","xlsx"],key="schedule")
        if up2 and st.button("Import schedule"):
            try:
                L["schedule"]=ensure_schedule_columns(load_table(up2)).to_dict("records")
                st.success(f"Imported {len(L['schedule'])} games.")
            except Exception as e: st.error(str(e))
    st.divider()
    st.subheader("Current setup")
    r=df("rosters"); s=df("schedule")
    st.metric("Players",len(r)); st.metric("Scheduled games",len(s))
    if not r.empty: st.dataframe(r,use_container_width=True,hide_index=True)
    if not s.empty: st.dataframe(s,use_container_width=True,hide_index=True)

elif page=="Weekly Games":
    sched=df("schedule")
    if sched.empty:
        st.info("Import a schedule first.")
    else:
        weeks=sorted(sched.Week.unique())
        week=st.selectbox("Week",weeks)
        wk=sched[sched.Week==week]
        done=completed_game_ids()
        st.caption(f"{sum(g in done for g in wk.GameID)} of {len(wk)} games complete")
        for _,game in wk.iterrows():
            gid=game.GameID
            with st.expander(f"{'✅' if gid in done else '⬜'} {game.Away} at {game.Home} {('— '+str(game.Date)) if str(game.Date) not in ['', 'nan'] else ''}", expanded=gid not in done):
                if gid in done:
                    g=next(x for x in L["games"] if x["GameID"]==gid)
                    st.success(f"Final: {g['Away']} {g['AwayGoals']} — {g['Home']} {g['HomeGoals']}")
                    ev=df("events"); st.dataframe(ev[ev.GameID==gid],use_container_width=True,hide_index=True)
                    continue
                a_goalies=team_goalies(game.Away); h_goalies=team_goalies(game.Home)
                if not a_goalies or not h_goalies:
                    st.warning("Both teams need at least one rostered player with Position = G.")
                    continue
                with st.form(f"form_{gid}"):
                    a,b=st.columns(2)
                    with a:
                        st.markdown(f"**{game.Away}**")
                        ag=st.number_input("Goals",0,30,0,key=f"ag{gid}")
                        hgk=st.selectbox("Starting goalie",h_goalies,key=f"hgk{gid}",help=f"{game.Home} goalie facing {game.Away}")
                        hsa=st.number_input(f"Shots faced by {game.Home} goalie",min_value=int(ag),max_value=100,value=max(int(ag),25),key=f"hsa{gid}")
                    with b:
                        st.markdown(f"**{game.Home}**")
                        hg=st.number_input("Goals",0,30,0,key=f"hg{gid}")
                        agk=st.selectbox("Starting goalie",a_goalies,key=f"agk{gid}",help=f"{game.Away} goalie facing {game.Home}")
                        asa=st.number_input(f"Shots faced by {game.Away} goalie",min_value=int(hg),max_value=100,value=max(int(hg),25),key=f"asa{gid}")
                    ot=st.checkbox("Game ended in overtime/shootout",key=f"ot{gid}")
                    submit=st.form_submit_button("Finalize and distribute stats",type="primary")
                if submit:
                    if ag==hg:
                        st.error("Final hockey score cannot be tied.")
                    else:
                        game_rec={"GameID":gid,"Week":int(game.Week),"Away":game.Away,"Home":game.Home,"AwayGoals":int(ag),"HomeGoals":int(hg),"OT":bool(ot),"Date":str(game.Date)}
                        L["games"].append(game_rec)
                        L["events"].extend(distribute_goals(game.Away,ag,gid))
                        L["events"].extend(distribute_goals(game.Home,hg,gid))
                        winner=game.Away if ag>hg else game.Home
                        for team,goalie,sa,ga in [(game.Away,agk,asa,hg),(game.Home,hgk,hsa,ag)]:
                            if team==winner: result="W"
                            else: result="OTL" if ot else "L"
                            L["goalie_games"].append({"GameID":gid,"Team":team,"Goalie":goalie,"SA":int(sa),"SV":int(sa-ga),"GA":int(ga),"Result":result})
                        st.success("Game finalized. Scoring, goalie stats, standings and leaders updated.")
                        st.rerun()

elif page=="Standings":
    st.header("Standings")
    s=standings()
    if s.empty: st.info("No completed games yet.")
    else:
        s.index=np.arange(1,len(s)+1)
        st.dataframe(s,use_container_width=True)

elif page=="League Leaders":
    st.header("League Leaders")
    sk=player_totals()
    gg=goalie_totals()
    t1,t2=st.tabs(["Skaters","Goalies"])
    with t1:
        if sk.empty: st.info("No player stats yet.")
        else:
            sort=st.selectbox("Sort skaters by",["PTS","G","A","GP"])
            st.dataframe(sk.sort_values([sort,"PTS","G"],ascending=False).reset_index(drop=True),use_container_width=True,hide_index=True)
    with t2:
        if gg.empty: st.info("No goalie stats yet.")
        else:
            st.dataframe(gg.sort_values(["W","SV%","SO"],ascending=False).reset_index(drop=True),use_container_width=True,hide_index=True)

elif page=="Game Log":
    st.header("Game Log")
    games=df("games")
    if games.empty: st.info("No games completed yet.")
    else:
        st.dataframe(games.sort_values(["Week","GameID"]),use_container_width=True,hide_index=True)
        gid=st.selectbox("View scoring detail",games.GameID)
        ev=df("events")
        st.dataframe(ev[ev.GameID==gid],use_container_width=True,hide_index=True)

elif page=="Backup / Export":
    st.header("Backup and export")
    payload=json.dumps(L,indent=2)
    st.download_button("Download league backup (.json)",payload,file_name=f"{L['league_name'].replace(' ','_')}_backup.json",mime="application/json")
    backup=st.file_uploader("Restore league backup",type=["json"])
    if backup and st.button("Restore backup"):
        st.session_state.league=json.load(backup)
        st.success("Backup restored.")
        st.rerun()
    st.divider()
    st.subheader("CSV exports")
    for label,key,func in [
        ("Standings","standings",standings),
        ("Skater stats","skater_stats",player_totals),
        ("Goalie stats","goalie_stats",goalie_totals),
        ("Games","games",lambda:df("games")),
        ("Scoring events","scoring_events",lambda:df("events"))
    ]:
        d=func()
        st.download_button(f"Download {label}",d.to_csv(index=False),file_name=f"{key}.csv",mime="text/csv",disabled=d.empty)

else:
    st.header(L.get("league_name","LHA"))
    games=df("games"); sched=df("schedule")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Teams",df("rosters").Team.nunique() if not df("rosters").empty else 0)
    c2.metric("Games played",len(games))
    c3.metric("Games scheduled",len(sched))
    c4.metric("Goals scored",int(games.AwayGoals.sum()+games.HomeGoals.sum()) if not games.empty else 0)
    st.subheader("Current standings")
    s=standings()
    if not s.empty: st.dataframe(s.head(10),use_container_width=True,hide_index=True)
    st.subheader("Upcoming")
    if sched.empty: st.info("Import a schedule to begin.")
    else:
        done=completed_game_ids()
        upcoming=sched[~sched.GameID.isin(done)].sort_values(["Week","GameID"]).head(10)
        st.dataframe(upcoming,use_container_width=True,hide_index=True)
