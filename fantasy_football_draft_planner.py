import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
import pandas as pd
from io import StringIO

st.set_page_config(page_title="Fantasy Draft Board", layout="wide")

# Configuration
DEFAULT_POSITIONS = ["QB", "RB", "WR", "TE", "FLEX", "DST", "K"]
STATUS_OPTIONS = ["Available", "Drafted", "Unavailable", "Watch"]
STATUS_COLORS = {
    "Available": "#28a745",
    "Drafted": "#6c757d", 
    "Unavailable": "#dc3545",
    "Watch": "#ffc107"
}

# Initialize session state
def initialize_session_state():
    if "boards" not in st.session_state:
        st.session_state.boards = {
            pos: pd.DataFrame(columns=["Rank", "Player", "Team", "Bye", "Notes", "Status"])
            for pos in DEFAULT_POSITIONS
        }
        # Add sample data for RB
        st.session_state.boards["RB"] = pd.DataFrame([
            [1, "Christian McCaffrey", "SF", 9, "Elite talent", "Available"],
            [2, "Breece Hall", "NYJ", 12, "Breakout year", "Available"],
            [3, "Bijan Robinson", "ATL", 11, "Rookie stud", "Available"],
        ], columns=["Rank", "Player", "Team", "Bye", "Notes", "Status"])

    if "hidden_statuses" not in st.session_state:
        st.session_state.hidden_statuses = set()

    if "positions" not in st.session_state:
        st.session_state.positions = list(DEFAULT_POSITIONS)

    if "watchlist_order" not in st.session_state:
        st.session_state.watchlist_order = []

initialize_session_state()

def normalize_board(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure dataframe has correct structure and data types"""
    if df.empty:
        return pd.DataFrame(columns=["Rank", "Player", "Team", "Bye", "Notes", "Status"])
    
    df = df.copy()
    required_cols = ["Rank", "Player", "Team", "Bye", "Notes", "Status"]
    
    # Add missing columns
    for col in required_cols:
        if col not in df.columns:
            df[col] = "" if col not in ["Rank", "Bye"] else None
    
    # Ensure correct column order
    df = df[required_cols]
    
    # Convert data types
    df["Rank"] = pd.to_numeric(df["Rank"], errors="coerce")
    df["Bye"] = pd.to_numeric(df["Bye"], errors="coerce")
    
    # Ensure valid status values
    df.loc[~df["Status"].isin(STATUS_OPTIONS), "Status"] = "Available"
    
    return df

def update_ranks_from_order(df: pd.DataFrame) -> pd.DataFrame:
    """Update ranks based on current dataframe order"""
    if df.empty:
        return df
    df_copy = df.copy().reset_index(drop=True)
    df_copy["Rank"] = range(1, len(df_copy) + 1)
    return df_copy

def add_player(position: str, player_data: dict):
    """Add a new player to the specified position board"""
    board = st.session_state.boards[position].copy()
    
    # Determine next rank
    next_rank = int(board["Rank"].max() + 1) if not board.empty and not board["Rank"].isna().all() else 1
    
    new_row = {
        "Rank": next_rank,
        "Player": player_data.get("Player", "").strip(),
        "Team": player_data.get("Team", "").strip(),
        "Bye": player_data.get("Bye"),
        "Notes": player_data.get("Notes", "").strip(),
        "Status": "Available",
    }
    
    # Add new row and update ranks
    board = pd.concat([board, pd.DataFrame([new_row])], ignore_index=True)
    board = update_ranks_from_order(board)
    st.session_state.boards[position] = board

def bulk_add_players(position: str, text: str):
    """Add multiple players from text input (one per line, pipe-separated)"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        name = parts[0] if len(parts) > 0 else ""
        team = parts[1] if len(parts) > 1 else ""
        bye = parts[2] if len(parts) > 2 and parts[2] else None
        notes = parts[3] if len(parts) > 3 else ""
        
        # Convert bye week to int
        try:
            bye = int(bye) if bye not in (None, "") else None
        except (ValueError, TypeError):
            bye = None
            
        if name:  # Only add if name is provided
            add_player(position, {
                "Player": name, 
                "Team": team, 
                "Bye": bye, 
                "Notes": notes
            })

def export_data() -> str:
    """Export all boards to CSV format"""
    frames = []
    for pos, df in st.session_state.boards.items():
        if df is None or df.empty:
            continue
        temp_df = df.copy()
        temp_df.insert(0, "Position", pos)
        frames.append(temp_df)
    
    if not frames:
        return ""
    
    combined_df = pd.concat(frames, ignore_index=True)
    output = StringIO()
    combined_df.to_csv(output, index=False)
    return output.getvalue()

def import_data(csv_text: str):
    """Import boards from CSV format"""
    try:
        df = pd.read_csv(StringIO(csv_text))
        required_columns = {"Position", "Rank", "Player", "Team", "Bye", "Notes", "Status"}
        missing_columns = required_columns - set(df.columns)
        
        if missing_columns:
            st.error(f"Missing required columns: {', '.join(sorted(missing_columns))}")
            return False
        
        # Group by position and update boards
        for pos, group_df in df.groupby("Position", dropna=False):
            position_df = group_df.drop(columns=["Position"])
            
            # Ensure position exists
            if pos not in st.session_state.positions:
                st.session_state.positions.append(pos)
            
            st.session_state.boards[pos] = normalize_board(position_df)
        
        return True
    except Exception as e:
        st.error(f"Import failed: {str(e)}")
        return False

def get_selected_indices(grid_response, original_df):
    """Get the actual dataframe indices of selected rows with improved error handling"""
    if not grid_response or not "selected_rows" in grid_response:
        return []
    
    selected_rows = grid_response["selected_rows"]
    
    if selected_rows is not None:
        indices = [int(x) for x in selected_rows.index.tolist()]
        return indices
    else:
        print("selected rows is none")
        return []

def mark_selected_players(position: str, selected_indices: list, new_status: str):
    """Mark selected players with new status"""
    if not selected_indices:
        return False
    
    board = st.session_state.boards[position].copy()
    board.loc[selected_indices, "Status"] = new_status
    st.session_state.boards[position] = board
    return True

def remove_selected_players(position: str, selected_indices: list):
    """Remove selected players from board"""
    if not selected_indices:
        return False
    
    board = st.session_state.boards[position].copy()
    board = board.drop(selected_indices).reset_index(drop=True)
    board = update_ranks_from_order(board)
    st.session_state.boards[position] = board
    return True

def get_filtered_board(board: pd.DataFrame, local_hidden: set) -> pd.DataFrame:
    """Filter board based on hidden statuses"""
    if not local_hidden:
        return board
    return board[~board["Status"].isin(local_hidden)].copy()

def get_all_watch_players():
    """Get all players with Watch status from all positions"""
    watch_players = []
    for pos, df in st.session_state.boards.items():
        if df.empty:
            continue
        watch_df = df[df["Status"] == "Watch"].copy()
        if not watch_df.empty:
            watch_df["Position"] = pos
            watch_players.append(watch_df)
    
    if not watch_players:
        return pd.DataFrame(columns=["Rank", "Player", "Team", "Position", "Bye", "Notes", "Status"])
    
    combined = pd.concat(watch_players, ignore_index=True)
    # Reorder columns
    cols = ["Rank", "Player", "Team", "Position", "Bye", "Notes", "Status"]
    combined = combined[cols]
    
    # Apply custom watchlist ordering if it exists
    if st.session_state.watchlist_order:
        try:
            # Create a mapping for custom order
            order_map = {player: idx for idx, player in enumerate(st.session_state.watchlist_order)}
            combined["custom_order"] = combined["Player"].map(order_map).fillna(999)
            combined = combined.sort_values("custom_order").drop("custom_order", axis=1)
        except:
            pass
    
    # Update ranks based on final order
    combined = update_ranks_from_order(combined)
    return combined

# Sidebar Controls
with st.sidebar:
    st.header("🎯 Draft Controls")
    
    # Position Management
    with st.expander("📋 Manage Positions", expanded=True):
        new_position = st.text_input("Add Position", placeholder="e.g., IDP, BENCH")
        
        col1, col2 = st.columns([3, 2])
        with col1:
            if st.button("➕ Add Position", use_container_width=True, disabled=not new_position.strip()):
                pos = new_position.strip().upper()
                if pos not in st.session_state.positions:
                    st.session_state.positions.append(pos)
                    st.session_state.boards[pos] = pd.DataFrame(
                        columns=["Rank", "Player", "Team", "Bye", "Notes", "Status"]
                    )
                    st.success(f"Added {pos}")
                    st.rerun()
        
        with col2:
            if st.button("🔄 Reset", use_container_width=True):
                st.session_state.positions = list(DEFAULT_POSITIONS)
                st.session_state.boards = {
                    pos: pd.DataFrame(columns=["Rank", "Player", "Team", "Bye", "Notes", "Status"])
                    for pos in DEFAULT_POSITIONS
                }
                st.success("Reset to defaults")
                st.rerun()
    
    # Visibility Controls
    with st.expander("👁️ Global Visibility", expanded=True):
        hide_drafted = st.checkbox("Hide Drafted Players", value="Drafted" in st.session_state.hidden_statuses)
        hide_unavailable = st.checkbox("Hide Unavailable Players", value="Unavailable" in st.session_state.hidden_statuses)
        hide_watch = st.checkbox("Hide Watch List", value="Watch" in st.session_state.hidden_statuses)
        
        st.session_state.hidden_statuses = {
            status for status, is_hidden in [
                ("Drafted", hide_drafted),
                ("Unavailable", hide_unavailable), 
                ("Watch", hide_watch)
            ] if is_hidden
        }
    
    # Import/Export
    with st.expander("💾 Import/Export Data", expanded=False):
        # Import
        uploaded_file = st.file_uploader("Import Draft Board", type=["csv"])
        if uploaded_file is not None:
            try:
                content = uploaded_file.getvalue().decode("utf-8")
                if import_data(content):
                    st.success("✅ Data imported successfully!")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Import error: {str(e)}")
        
        # Export
        export_content = export_data()
        st.download_button(
            "📥 Download CSV",
            data=export_content,
            file_name="fantasy_draft_board.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not export_content
        )

# Main Interface
st.title("🏈 Fantasy Football Draft Board")
st.markdown("*Drag players to reorder • Select multiple players for bulk actions • Rankings update automatically*")

# Global Actions
action_cols = st.columns(3)
with action_cols[0]:
    if st.button("🗑️ Clear All Players", use_container_width=True):
        for pos in st.session_state.positions:
            st.session_state.boards[pos] = pd.DataFrame(
                columns=["Rank", "Player", "Team", "Bye", "Notes", "Status"]
            )
        st.success("All players cleared!")
        st.rerun()

with action_cols[1]:
    draft_count = sum(
        len(board[board["Status"] == "Drafted"]) 
        for board in st.session_state.boards.values() 
        if not board.empty
    )
    st.metric("Drafted Players", draft_count)

with action_cols[2]:
    total_count = sum(
        len(board) for board in st.session_state.boards.values() 
        if not board.empty
    )
    st.metric("Total Players", total_count)

st.divider()

# Create tabs including watchlist
all_tabs = ["🎯 WATCHLIST"] + st.session_state.positions
tabs = st.tabs(all_tabs)

# Watchlist Tab
with tabs[0]:
    st.subheader("🎯 Your Watchlist")
    st.markdown("*All players marked as 'Watch' from every position*")
    
    watchlist_df = get_all_watch_players()
    
    if not watchlist_df.empty:
        # Configure watchlist grid
        gb = GridOptionsBuilder.from_dataframe(watchlist_df)
        
        # Make relevant columns editable
        editable_columns = ["Notes"]
        for col in editable_columns:
            gb.configure_column(col, editable=True, wrapText=True, autoHeight=True)
        
        # Configure drag and drop for reordering
        gb.configure_grid_options(rowDragManaged=True, animateRows=True)
        gb.configure_column("Rank", rowDrag=True, lockPosition="left")
        
        # Enable row selection
        gb.configure_selection("multiple", use_checkbox=True)
        
        # Style the status column
        gb.configure_column(
            "Status",
            cellStyle={"backgroundColor": STATUS_COLORS["Watch"]}
        )
        
        # Build grid options
        grid_options = gb.build()
        
        # Display watchlist grid
        watchlist_response = AgGrid(
            watchlist_df,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.VALUE_CHANGED,
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            fit_columns_on_grid_load=True,
            allow_unsafe_jscode=True,
            key="watchlist_grid",
            reload_data=False
        )
        
        # Handle watchlist reordering and changes
        if watchlist_response is not None and "data" in watchlist_response and watchlist_response["data"] is not None:
            try:
                updated_watchlist = pd.DataFrame(watchlist_response["data"])
                if not updated_watchlist.empty:
                    # Check if the order changed
                    current_order = st.session_state.watchlist_order
                    new_order = updated_watchlist["Player"].tolist()
                    
                    # Store the new order
                    st.session_state.watchlist_order = new_order
                    
                    # If order changed, trigger rerun for immediate visual update
                    if current_order != new_order:
                        st.rerun()
            except Exception as e:
                # If there's an error, keep the original order
                pass
        
        # # Watchlist actions
        # st.markdown("**🎯 Watchlist Actions**")
        # watchlist_cols = st.columns(4)
        
        # # Get selected indices for watchlist with improved error handling
        # watchlist_selected_indices = []
        # watchlist_debug_info = ""
        
        # try:
        #     watchlist_selected_indices = get_selected_indices(watchlist_response, watchlist_df)
            
        #     # Debug information for watchlist
        #     if watchlist_response and "selected_rows" in watchlist_response:
        #         selection_count = len(watchlist_response["selected_rows"]) if watchlist_response["selected_rows"] else 0
        #         watchlist_debug_info = f"Watchlist: Grid reported {selection_count} selected, found {len(watchlist_selected_indices)} indices"
                
        # except Exception as e:
        #     st.warning(f"Watchlist selection warning: {str(e)}")
        
        # # Show debug info for watchlist if there's a mismatch  
        # if watchlist_debug_info and len(watchlist_selected_indices) == 0 and watchlist_response.get("selected_rows"):
        #     st.info(f"Debug: {watchlist_debug_info}")
        
        # with watchlist_cols[0]:
        #     if st.button("✅ Mark Available", key="watchlist_available", use_container_width=True):
        #         if watchlist_selected_indices:
        #             count = 0
        #             for idx in watchlist_selected_indices:
        #                 player_row = watchlist_df.iloc[idx]
        #                 position = player_row["Position"]
        #                 # Find player in original position board
        #                 pos_board = st.session_state.boards[position]
        #                 player_mask = (pos_board["Player"] == player_row["Player"]) & (pos_board["Team"] == player_row["Team"])
        #                 pos_indices = pos_board[player_mask].index.tolist()
        #                 if pos_indices:
        #                     mark_selected_players(position, pos_indices, "Available")
        #                     count += 1
        #             if count > 0:
        #                 st.success(f"Marked {count} player(s) as Available!")
        #                 st.rerun()
        #         else:
        #             st.warning("Please select players using the checkboxes")
        
        # with watchlist_cols[1]:
        #     if st.button("✅ Mark Drafted", key="watchlist_drafted", use_container_width=True):
        #         if watchlist_selected_indices:
        #             count = 0
        #             for idx in watchlist_selected_indices:
        #                 player_row = watchlist_df.iloc[idx]
        #                 position = player_row["Position"]
        #                 # Find player in original position board
        #                 pos_board = st.session_state.boards[position]
        #                 player_mask = (pos_board["Player"] == player_row["Player"]) & (pos_board["Team"] == player_row["Team"])
        #                 pos_indices = pos_board[player_mask].index.tolist()
        #                 if pos_indices:
        #                     mark_selected_players(position, pos_indices, "Drafted")
        #                     count += 1
        #             if count > 0:
        #                 st.success(f"Marked {count} player(s) as Drafted!")
        #                 st.rerun()
        #         else:
        #             st.warning("Please select players using the checkboxes")
        
        # with watchlist_cols[2]:
        #     if st.button("❌ Mark Unavailable", key="watchlist_unavailable", use_container_width=True):
        #         if watchlist_selected_indices:
        #             count = 0
        #             for idx in watchlist_selected_indices:
        #                 player_row = watchlist_df.iloc[idx]
        #                 position = player_row["Position"]
        #                 # Find player in original position board
        #                 pos_board = st.session_state.boards[position]
        #                 player_mask = (pos_board["Player"] == player_row["Player"]) & (pos_board["Team"] == player_row["Team"])
        #                 pos_indices = pos_board[player_mask].index.tolist()
        #                 if pos_indices:
        #                     mark_selected_players(position, pos_indices, "Unavailable")
        #                     count += 1
        #             if count > 0:
        #                 st.success(f"Marked {count} player(s) as Unavailable!")
        #                 st.rerun()
        #         else:
        #             st.warning("Please select players using the checkboxes")
        
        # with watchlist_cols[3]:
        #     if st.button("🗑️ Remove from Watchlist", key="watchlist_remove", use_container_width=True):
        #         if watchlist_selected_indices:
        #             count = 0
        #             for idx in watchlist_selected_indices:
        #                 player_row = watchlist_df.iloc[idx]
        #                 position = player_row["Position"]
        #                 # Find player in original position board
        #                 pos_board = st.session_state.boards[position]
        #                 player_mask = (pos_board["Player"] == player_row["Player"]) & (pos_board["Team"] == player_row["Team"])
        #                 pos_indices = pos_board[player_mask].index.tolist()
        #                 if pos_indices:
        #                     mark_selected_players(position, pos_indices, "Available")
        #                     count += 1
        #             if count > 0:
        #                 st.success(f"Removed {count} player(s) from watchlist!")
        #                 st.rerun()
        #         else:
        #             st.warning("Please select players using the checkboxes")
        
        # if watchlist_selected_indices:
        #     st.info(f"📋 {len(watchlist_selected_indices)} player(s) selected")
    
    else:
        st.info("No players in your watchlist yet. Mark players as 'Watch' from other position tabs to see them here.")
    
    st.divider()

# Position Tabs
for position, tab in zip(st.session_state.positions, tabs[1:]):
    with tab:
        st.subheader(f"🎯 {position} Rankings")
        
        # Add Player Form
        with st.container():
            st.markdown("**➕ Add New Player**")
            add_cols = st.columns([3, 1, 1, 2, 1])
            
            with add_cols[0]:
                player_name = st.text_input("Player Name", key=f"{position}_name", placeholder="Enter player name")
            with add_cols[1]:
                team = st.text_input("Team", key=f"{position}_team", placeholder="SF")
            with add_cols[2]:
                bye_week = st.number_input("Bye", key=f"{position}_bye", min_value=0, max_value=18, step=1, value=0)
            with add_cols[3]:
                notes = st.text_input("Notes", key=f"{position}_notes", placeholder="Any notes...")
            with add_cols[4]:
                if st.button("➕ Add", key=f"{position}_add", use_container_width=True, disabled=not player_name.strip()):
                    add_player(position, {
                        "Player": player_name,
                        "Team": team,
                        "Bye": int(bye_week) if bye_week else None,
                        "Notes": notes
                    })
                    st.success(f"Added {player_name}")
                    st.rerun()
        
        # Bulk Add
        with st.expander("📝 Bulk Add Players", expanded=False):
            st.markdown("*Format: Player Name | Team | Bye Week | Notes (one per line)*")
            bulk_text = st.text_area(
                f"Bulk add {position} players:", 
                key=f"{position}_bulk",
                placeholder="Christian McCaffrey | SF | 9 | Elite RB\nBreece Hall | NYJ | 12 | Breakout potential"
            )
            if st.button("📋 Bulk Add", key=f"{position}_bulk_add"):
                bulk_add_players(position, bulk_text)
                st.success("Players added!")
                st.rerun()
        
        # Position-specific visibility controls
        vis_cols = st.columns(3)
        with vis_cols[0]:
            local_hide_drafted = st.checkbox("Hide Drafted", key=f"{position}_hide_drafted")
        with vis_cols[1]:
            local_hide_unavailable = st.checkbox("Hide Unavailable", key=f"{position}_hide_unavailable")
        with vis_cols[2]:
            local_hide_watch = st.checkbox("Hide Watch", key=f"{position}_hide_watch")
        
        local_hidden_statuses = {
            status for status, is_hidden in [
                ("Drafted", local_hide_drafted),
                ("Unavailable", local_hide_unavailable),
                ("Watch", local_hide_watch)
            ] if is_hidden
        }
        
        # Get and prepare board data
        board = normalize_board(st.session_state.boards[position])
        filtered_board = get_filtered_board(board, local_hidden_statuses)
        
        if not filtered_board.empty:
            # Configure AgGrid
            gb = GridOptionsBuilder.from_dataframe(filtered_board)
            
            # Make columns editable
            editable_columns = ["Player", "Team", "Bye", "Notes"]
            for col in editable_columns:
                gb.configure_column(col, editable=True, wrapText=True, autoHeight=True)
            
            # Configure Status column with dropdown
            gb.configure_column(
                "Status",
                editable=True,
                cellEditor="agSelectCellEditor",
                cellEditorParams={"values": STATUS_OPTIONS},
                cellStyle={
                    "styleConditions": [
                        {"condition": f"params.value == '{status}'", "style": {"backgroundColor": color}}
                        for status, color in STATUS_COLORS.items()
                    ]
                }
            )
            
            # Configure drag and drop for reordering
            gb.configure_grid_options(rowDragManaged=True, animateRows=True)
            gb.configure_column("Rank", rowDrag=True, lockPosition="left")
            
            # Enable row selection
            gb.configure_selection("multiple", use_checkbox=True)
            
            # Build grid options
            grid_options = gb.build()
            
            # Display grid
            grid_response = AgGrid(
                filtered_board,
                gridOptions=grid_options,
                update_mode=GridUpdateMode.VALUE_CHANGED | GridUpdateMode.MODEL_CHANGED,
                data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                fit_columns_on_grid_load=True,
                allow_unsafe_jscode=True,
                key=f"grid_{position}",
                reload_data=False
            )
            
            # Handle grid changes and auto-update ranks
            if grid_response is not None and "data" in grid_response and grid_response["data"] is not None:
                try:
                    updated_data = pd.DataFrame(grid_response["data"])
                    if not updated_data.empty:
                        # Always update ranks based on current order
                        updated_data = update_ranks_from_order(updated_data)
                        
                        # Check if data actually changed (for drag operations or status changes)
                        current_board = st.session_state.boards[position]
                        
                        # Compare the essential data to see if something changed
                        data_changed = False
                        if len(updated_data) != len(current_board):
                            data_changed = True
                        elif not updated_data.equals(current_board):
                            # Check if order changed
                            current_order = current_board["Player"].tolist() if not current_board.empty else []
                            new_order = updated_data["Player"].tolist()
                            
                            # Check if status changed
                            current_status = current_board["Status"].tolist() if not current_board.empty else []
                            new_status = updated_data["Status"].tolist()
                            
                            if current_order != new_order or current_status != new_status:
                                data_changed = True
                        
                        # Update the session state
                        st.session_state.boards[position] = updated_data
                        
                        # If data changed, trigger a rerun to show updated interface
                        if data_changed:
                            st.rerun()
                            
                except Exception as e:
                    # If there's an error with the grid data, keep the original board
                    pass
            
            # # Action buttons
            # st.markdown("**🎯 Player Actions**")
            # action_cols = st.columns(4)
            
            # # Get selected indices with improved error handling
            # selected_indices = []
            # selection_debug_info = ""
            
            # try:
            #     selected_indices = get_selected_indices(grid_response, st.session_state.boards[position])
                
            #     # Debug information
            #     if grid_response and "selected_rows" in grid_response:
            #         selection_count = len(grid_response["selected_rows"]) if grid_response["selected_rows"] else 0
            #         selection_debug_info = f"Grid reported {selection_count} selected, found {len(selected_indices)} indices"
                
            # except Exception as e:
            #     st.warning(f"Selection warning: {str(e)}")
            
            # # Show debug info if there's a mismatch
            # if selection_debug_info and len(selected_indices) == 0 and grid_response.get("selected_rows"):
            #     st.info(f"Debug: {selection_debug_info}")
            
            # with action_cols[0]:
            #     if st.button("✅ Mark Drafted", key=f"{position}_mark_drafted", use_container_width=True):
            #         if selected_indices:
            #             if mark_selected_players(position, selected_indices, "Drafted"):
            #                 st.success(f"Marked {len(selected_indices)} player(s) as Drafted!")
            #                 st.rerun()
            #         else:
            #             st.warning("Please select players using the checkboxes")
            
            # with action_cols[1]:
            #     if st.button("❌ Mark Unavailable", key=f"{position}_mark_unavailable", use_container_width=True):
            #         if selected_indices:
            #             if mark_selected_players(position, selected_indices, "Unavailable"):
            #                 st.success(f"Marked {len(selected_indices)} player(s) as Unavailable!")
            #                 st.rerun()
            #         else:
            #             st.warning("Please select players using the checkboxes")
            
            # with action_cols[2]:
            #     if st.button("👀 Add to Watch", key=f"{position}_mark_watch", use_container_width=True):
            #         if selected_indices:
            #             if mark_selected_players(position, selected_indices, "Watch"):
            #                 st.success(f"Added {len(selected_indices)} player(s) to Watchlist!")
            #                 st.rerun()
            #         else:
            #             st.warning("Please select players using the checkboxes")
            
            # with action_cols[3]:
            #     if st.button("🗑️ Remove Selected", key=f"{position}_remove", use_container_width=True):
            #         if selected_indices:
            #             if remove_selected_players(position, selected_indices):
            #                 st.success(f"Removed {len(selected_indices)} player(s)!")
            #                 st.rerun()
            #         else:
            #             st.warning("Please select players using the checkboxes")
            
            # # Display selection info
            # if selected_indices:
            #     st.info(f"📋 {len(selected_indices)} player(s) selected")
        
        else:
            st.info(f"No {position} players to display. Add some players above!")
        
        st.divider()

# Footer
st.markdown("---")
st.markdown(
    "💡 **Tips:** Drag players to reorder (ranks update automatically) • Use checkboxes for bulk actions • "
    "Status colors: 🟢 Available • ⚫ Drafted • 🔴 Unavailable • 🟡 Watch"
)