import streamlit as st
import pandas as pd
from io import StringIO

st.set_page_config(page_title="Draft Board", layout="wide")

DEFAULT_POSITIONS = ["QB", "RB", "WR", "TE", "FLEX", "DST", "K"]
STATUS_OPTIONS = ["Available", "Drafted", "Unavailable", "Watch"]

if "boards" not in st.session_state:
    st.session_state.boards = {
        pos: pd.DataFrame(columns=["Rank", "Player", "Team", "Bye", "Notes", "Status"])
        for pos in DEFAULT_POSITIONS
    }    
    st.session_state.boards["RB"] = pd.DataFrame([
        [1, "Christian McCaffrey", "SF", 9, "", "Available"],
        [2, "Breece Hall", "NYJ", 12, "", "Available"],
        [3, "Bijan Robinson", "ATL", 11, "", "Available"],
    ], columns=["Rank", "Player", "Team", "Bye", "Notes", "Status"])

if "hidden_statuses" not in st.session_state:
    st.session_state.hidden_statuses = set()

if "positions" not in st.session_state:
    st.session_state.positions = list(DEFAULT_POSITIONS)

def normalize_board(df: pd.DataFrame) -> pd.DataFrame:    
    cols = ["Rank", "Player", "Team", "Bye", "Notes", "Status"]
    for c in cols:
        if c not in df.columns:
            df[c] = "" if c != "Rank" else None
    df = df[cols]    
    df["Rank"] = pd.to_numeric(df["Rank"], errors="coerce")
    df["Bye"] = pd.to_numeric(df["Bye"], errors="coerce")    
    df["Status"] = df["Status"].where(df["Status"].isin(STATUS_OPTIONS), "Available")
    return df

def filtered(df: pd.DataFrame) -> pd.DataFrame:
    if not st.session_state.hidden_statuses:
        return df
    return df[~df["Status"].isin(st.session_state.hidden_statuses)]

def reindex_rank(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Rank"] = range(1, len(df) + 1)
    return df

def add_player(position: str, player: dict):
    board = st.session_state.boards[position].copy()
    new_row = {
        "Rank": (board["Rank"].max() or 0) + 1 if not board.empty else 1,
        "Player": player.get("Player", "").strip(),
        "Team": player.get("Team", "").strip(),
        "Bye": player.get("Bye"),
        "Notes": player.get("Notes", "").strip(),
        "Status": "Available",
    }
    board = pd.concat([board, pd.DataFrame([new_row])], ignore_index=True)
    st.session_state.boards[position] = board

def bulk_add(position: str, text: str):
    """
    Lines like:
    Player Name | Team | Bye | Notes
    Only name is required; use pipes optionally.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        parts = [p.strip() for p in ln.split("|")]
        name = parts[0] if len(parts) > 0 else ""
        team = parts[1] if len(parts) > 1 else ""
        bye  = parts[2] if len(parts) > 2 and parts[2] else None
        notes= parts[3] if len(parts) > 3 else ""
        try:
            bye = int(bye) if bye not in (None, "") else None
        except:
            bye = None
        add_player(position, {"Player": name, "Team": team, "Bye": bye, "Notes": notes})

def export_all() -> str:
    frames = []
    for pos, df in st.session_state.boards.items():
        if df is None or df.empty:
            continue
        tmp = df.copy()
        tmp.insert(0, "Position", pos)
        frames.append(tmp)
    if not frames:
        return ""
    big = pd.concat(frames, ignore_index=True)
    out = StringIO()
    big.to_csv(out, index=False)
    return out.getvalue()

def import_all(csv_text: str):
    df = pd.read_csv(StringIO(csv_text))
    required = {"Position", "Rank", "Player", "Team", "Bye", "Notes", "Status"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"Missing required columns in CSV: {', '.join(sorted(missing))}")
        return    
    pos_groups = df.groupby("Position", dropna=False)
    for pos, part in pos_groups:
        part = part.drop(columns=["Position"])
        st.session_state.boards.setdefault(pos, pd.DataFrame(columns=["Rank","Player","Team","Bye","Notes","Status"]))
        st.session_state.boards[pos] = normalize_board(part)
        if pos not in st.session_state.positions:
            st.session_state.positions.append(pos)

with st.sidebar:
    st.header("Controls")
    
    with st.expander("Positions", expanded=True):
        new_pos = st.text_input("Add a new position (e.g., IDP, Bench)", "")
        cols_pos = st.columns([1, 0.3])
        with cols_pos[0]:
            if st.button("Add Position", use_container_width=True, disabled=(not new_pos.strip())):
                p = new_pos.strip().upper()
                if p not in st.session_state.positions:
                    st.session_state.positions.append(p)
                    st.session_state.boards[p] = pd.DataFrame(columns=["Rank","Player","Team","Bye","Notes","Status"])
        with cols_pos[1]:
            if st.button("Reset to Default", use_container_width=True):
                st.session_state.positions = list(DEFAULT_POSITIONS)
                st.session_state.boards = {
                    pos: pd.DataFrame(columns=["Rank", "Player", "Team", "Bye", "Notes", "Status"])
                    for pos in DEFAULT_POSITIONS
                }
    
    with st.expander("Visibility", expanded=True):
        hide_drafted = st.checkbox("Hide Drafted", value=False)
        hide_unavail  = st.checkbox("Hide Unavailable", value=False)
        hide_watch    = st.checkbox("Hide Watch", value=False)
        st.session_state.hidden_statuses = {
            s for s, on in zip(
                ["Drafted", "Unavailable", "Watch"],
                [hide_drafted, hide_unavail, hide_watch]
            ) if on
        }
    
    with st.expander("Import / Export", expanded=False):
        uploaded = st.file_uploader("Import CSV (from this app)", type=["csv"])
        if uploaded is not None:
            try:
                import_all(uploaded.getvalue().decode("utf-8"))
                st.success("Imported boards from CSV.")
            except Exception as e:
                st.error(f"Import failed: {e}")

        csv_text = export_all()
        st.download_button(
            "Download CSV",
            data=csv_text,
            file_name="draft_board.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=(csv_text == "")
        )

st.title("🏈 Fantasy Draft Board")
st.caption("Add players, drag to reorder, set status (Available/Drafted/Unavailable/Watch), and filter by position/status.")

action_cols = st.columns([1, 1, 1, 2, 2, 2])
with action_cols[0]:
    if st.button("Reindex Ranks (All Tabs)", use_container_width=True):
        for p in st.session_state.positions:
            st.session_state.boards[p] = reindex_rank(st.session_state.boards[p])

with action_cols[1]:
    if st.button("Clear All Players (All Tabs)", use_container_width=True):
        for p in st.session_state.positions:
            st.session_state.boards[p] = st.session_state.boards[p].iloc[0:0]

with action_cols[2]:
    if st.button("Mark All Hidden As Drafted", use_container_width=True):        
        st.info("Tip: Use per-tab bulk actions to mark selected rows.")

tabs = st.tabs(st.session_state.positions)

for pos, tab in zip(st.session_state.positions, tabs):
    with tab:
        st.subheader(pos)
        
        add_cols = st.columns([2, 1, 1, 2, 1])
        with add_cols[0]:
            name = st.text_input(f"Add {pos} — Player", key=f"{pos}_name")
        with add_cols[1]:
            team = st.text_input("Team", key=f"{pos}_team", placeholder="e.g., SF")
        with add_cols[2]:
            bye  = st.number_input("Bye", key=f"{pos}_bye", min_value=0, max_value=20, step=1, value=0)
        with add_cols[3]:
            notes= st.text_input("Notes", key=f"{pos}_notes")
        with add_cols[4]:
            if st.button("Add", key=f"{pos}_add_btn", use_container_width=True, disabled=(not name.strip())):
                add_player(pos, {"Player": name, "Team": team, "Bye": int(bye) if bye else None, "Notes": notes})
                st.experimental_rerun()

        with st.expander("Bulk Add (one per line, optional | Team | Bye | Notes)", expanded=False):
            txt = st.text_area(f"Paste names for {pos}", key=f"{pos}_bulk")
            if st.button("Bulk Add", key=f"{pos}_bulk_btn"):
                bulk_add(pos, txt)
                st.experimental_rerun()
        
        board = normalize_board(st.session_state.boards[pos])
        
        c1, c2, c3, c4 = st.columns([1,1,1,2])
        with c1:
            hide_d = st.checkbox("Hide Drafted", value="Drafted" in st.session_state.hidden_statuses, key=f"{pos}_hide_d")
        with c2:
            hide_u = st.checkbox("Hide Unavail", value="Unavailable" in st.session_state.hidden_statuses, key=f"{pos}_hide_u")
        with c3:
            hide_w = st.checkbox("Hide Watch", value="Watch" in st.session_state.hidden_statuses, key=f"{pos}_hide_w")

        local_hidden = {s for s, on in zip(["Drafted","Unavailable","Watch"], [hide_d, hide_u, hide_w]) if on}
        view_df = board[~board["Status"].isin(local_hidden)].copy()
        
        if "Pick" not in board.columns:
            board["Pick"] = False
        if "Pick" not in view_df.columns:
            view_df["Pick"] = False
        
        edited = st.data_editor(
            view_df,
        key=f"editor_{pos}",   
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            column_order=["Pick", "Rank", "Player", "Team", "Bye", "Notes", "Status"],
            column_config={
                "Pick": st.column_config.CheckboxColumn("Pick", help="Select rows for batch actions"),
                "Rank": st.column_config.NumberColumn("Rank", step=1, min_value=1),
                "Player": st.column_config.TextColumn("Player", required=True),
                "Team": st.column_config.TextColumn("Team"),
                "Bye": st.column_config.NumberColumn("Bye", step=1, min_value=0, max_value=20),
                "Notes": st.column_config.TextColumn("Notes"),
                "Status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
            }
        )

                                        
        def make_key(df_):
            return df_.assign(_key=df_["Player"].fillna("") + "|" + df_["Team"].fillna("") + "|" + df_["Notes"].fillna("") + "|" + df_["Bye"].astype(str).fillna(""))

        orig_k = make_key(board)
        edit_k = make_key(edited)

        keep = orig_k[~orig_k["_key"].isin(edit_k["_key"])].drop(columns=["_key"])
        merged = pd.concat([keep, edited.drop(columns=["_key"], errors="ignore")], ignore_index=True)
        
        st.session_state.boards[pos] = merged
        
        act1, act2, act3, act4 = st.columns([1,1,1,1])
        with act1:
            if st.button("Mark Selected Drafted", key=f"{pos}_mark_d"):
                df = st.session_state.boards[pos].copy()
                df.loc[df.get("Pick", False) == True, "Status"] = "Drafted"
                df["Pick"] = False
                st.session_state.boards[pos] = df
                st.experimental_rerun()
        with act2:
            if st.button("Mark Selected Unavailable", key=f"{pos}_mark_u"):
                df = st.session_state.boards[pos].copy()
                df.loc[df.get("Pick", False) == True, "Status"] = "Unavailable"
                df["Pick"] = False
                st.session_state.boards[pos] = df
                st.experimental_rerun()
        with act3:
            if st.button("Remove Selected", key=f"{pos}_remove"):
                df = st.session_state.boards[pos].copy()
                st.session_state.boards[pos] = df[df.get("Pick", False) != True]
                st.experimental_rerun()
        with act4:
            if st.button("Reindex Ranks (This Tab)", key=f"{pos}_reindex"):
                st.session_state.boards[pos] = reindex_rank(st.session_state.boards[pos])
                st.experimental_rerun()

st.caption("Pro tip: drag the left handle in the editor to reorder your ranks, then click \'Reindex Ranks\' to lock in numbering.")
