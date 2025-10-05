# ==============================================================================
#  YouTube Music Wrapped - Version 1.0
# ==============================================================================
#  Description: This is the initial version of the application. It creates the
#               full user interface skeleton and populates it with mock data
#               for demonstration and development purposes.
# ==============================================================================

import pandas as pd
import streamlit as st
import random
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np

# --- Application Configuration ---
st.set_page_config(
    page_title="YouTube Music Wrapped",
    page_icon="🎧",
    layout="wide"
)

# --- MOCK DATA GENERATION ---
@st.cache_data
def create_mock_data():
    """Generates a realistic-looking DataFrame of music listening history."""
    mock_artists = ["The Weeknd", "Daft Punk", "Tame Impala", "Lana Del Rey", "Kendrick Lamar", "Dua Lipa"]
    mock_songs = {
        "The Weeknd": ["Blinding Lights", "Save Your Tears", "Take My Breath"],
        "Daft Punk": ["Get Lucky", "One More Time", "Around the World"],
        "Tame Impala": ["The Less I Know The Better", "Let It Happen", "Borderline"],
        "Lana Del Rey": ["Summertime Sadness", "Video Games", "Doin' Time"],
        "Kendrick Lamar": ["HUMBLE.", "Money Trees", "Alright"],
        "Dua Lipa": ["Don't Start Now", "Levitating", "New Rules"]
    }
    
    records = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    for _ in range(2000): # Generate 2000 fake listens
        artist = random.choice(mock_artists)
        title = random.choice(mock_songs[artist])
        timestamp = start_date + timedelta(seconds=random.randint(0, int((end_date - start_date).total_seconds())))
        duration_min = random.uniform(2.5, 5.0)
        records.append({"timestamp": timestamp, "artist": artist, "title": title, "duration_min": duration_min})
        
    df = pd.DataFrame(records)
    df["capped_duration_min"] = df["duration_min"] # In this version, capped is same as actual
    return df

# --- UI RENDERING FUNCTIONS ---
def render_sidebar():
    st.sidebar.header("⚙️ Configuration")
    st.sidebar.text_input("Enter your YouTube API Key", type="password", disabled=True)
    st.sidebar.file_uploader("Upload your `watch-history.html`", type=["html"], disabled=True)
    st.sidebar.info("Inputs are disabled in this UI-only preview version.")

def render_kpis(summary):
    st.header("✨ Your Music Review")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Music Time", f"{int(summary['total_minutes']):,} min", delta="vs Last Month")
    col2.metric("Favorite Artist", summary['fav_artist'], f"{int(summary['fav_artist_duration'])} min")
    col3.metric("Favorite Song", summary['fav_song'], f"{int(summary['fav_song_duration'])} min")

def render_charts(summary):
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📅 Daily Music Listening")
        by_day = summary['by_day']
        daily_avg = by_day.mean()
        plt.style.use("dark_background"); fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(by_day.index, by_day.values, color="#FF0000", alpha=0.9)
        ax.axhline(daily_avg, color="white", linestyle="--", alpha=0.7, label=f"Avg: {daily_avg:.0f} min/day")
        title_text = f"Total of {int(summary['by_month_total']):,} minutes in {summary['latest_month_str']}"
        ax.set_title(title_text, fontsize=16, weight="bold", color="white")
        ax.set_ylabel("Minutes Listened"); ax.legend(); fig.autofmt_xdate(); plt.tight_layout(); st.pyplot(fig)
    with col2:
        st.subheader("🕒 By Time of Day")
        time_buckets = summary.get('time_buckets', {}); sorted_buckets = dict(sorted(time_buckets.items(), key=lambda item: -item[1]))
        fig2, ax2 = plt.subplots(figsize=(8, 8)); neon_colors = ['#00F5D4', '#00B9FF', '#9B5DE5', '#F15BB5']
        num_bubbles = len(sorted_buckets); radius = 3.8; angles = np.linspace(0, 2 * np.pi, num_bubbles, endpoint=False) + np.pi / num_bubbles
        for i, (label, minutes) in enumerate(sorted_buckets.items()):
            color = neon_colors[i % len(neon_colors)]; size = max(minutes * 1.2, 100) + 200
            angle = angles[i]; x, y = radius * np.cos(angle), radius * np.sin(angle)
            ax2.scatter(x, y, s=size * 1.6, color=color, alpha=0.4); ax2.scatter(x, y, s=size, color=color, alpha=1, edgecolors="white", linewidth=1.5)
            ax2.text(x, y, f"{label}\n{int(minutes)} min", ha="center", va="center", fontsize=10, weight="bold", color="white", path_effects=[pe.withStroke(linewidth=3, foreground='black')])
        ax2.set_xlim(-8, 8); ax2.set_ylim(-8, 8); ax2.set_aspect('equal', adjustable='box'); ax2.axis("off"); st.pyplot(fig2)

def render_top_lists(summary):
    st.header("🏆 Your Top 10s")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔥 Top Songs (by plays)")
        st.dataframe(summary['top_songs'].reset_index().rename(columns={"index": "Title", "title": "Play Count"}))
    with col2:
        st.subheader("🎤 Top Artists (by minutes)")
        top_artists_df = summary['top_artists'].reset_index()
        top_artists_df['capped_duration_min'] = top_artists_df['capped_duration_min'].astype(int)
        st.dataframe(top_artists_df.rename(columns={"artist": "Artist", "capped_duration_min": "Minutes Listened"}))

# --- MAIN APPLICATION FLOW ---
def main():
    st.title("🎧 YouTube Music Wrapped")
    st.markdown("Your personal YouTube listening history, visualized.")
    render_sidebar()
    st.success("Displaying Mock Data. The full application will process your uploaded files.")
    
    # --- Generate and analyze mock data ---
    mock_df = create_mock_data()
    
    # This is a simplified version of the final analysis function for mock data
    summary = {}
    summary['total_minutes'] = mock_df["capped_duration_min"].sum()
    fav_artist = mock_df.groupby("artist")["capped_duration_min"].sum().nlargest(1)
    summary['fav_artist'] = fav_artist.index[0]
    summary['fav_artist_duration'] = fav_artist.iloc[0]
    fav_song = mock_df.groupby("title")["capped_duration_min"].sum().nlargest(1)
    summary['fav_song'] = fav_song.index[0]
    summary['fav_song_duration'] = fav_song.iloc[0]
    summary['by_day'] = mock_df.groupby(mock_df["timestamp"].dt.date)["capped_duration_min"].sum()
    summary['by_month_total'] = mock_df.groupby(mock_df["timestamp"].dt.to_period("M"))["capped_duration_min"].sum().iloc[-1]
    summary['latest_month_str'] = "Overall"
    mock_df["hour"] = mock_df["timestamp"].dt.hour
    summary['time_buckets'] = {
        "Morning": mock_df[(mock_df["hour"]>=6) & (mock_df["hour"]<12)]["duration_min"].sum(),
        "Afternoon": mock_df[(mock_df["hour"]>=12) & (mock_df["hour"]<18)]["duration_min"].sum(),
        "Evening": mock_df[(mock_df["hour"]>=18) & (mock_df["hour"]<24)]["duration_min"].sum(),
        "Night": mock_df[(mock_df["hour"]<6)]["duration_min"].sum(),
    }
    summary['top_songs'] = mock_df["title"].value_counts().head(10)
    summary['top_artists'] = mock_df.groupby("artist")["capped_duration_min"].sum().nlargest(10)

    # --- Render the dashboard with mock data ---
    st.markdown("---")
    render_kpis(summary)
    st.markdown("---")
    render_charts(summary)
    st.markdown("---")
    render_top_lists(summary)

if __name__ == "__main__":
    main()