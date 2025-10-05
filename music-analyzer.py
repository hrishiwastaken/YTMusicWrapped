# ==============================================================================
#  YouTube Music Wrapped - Version 2.0
# ==============================================================================
#  Description: This version replaces the mock data generator with a real data
#               pipeline that parses the user's HTML file and fetches metadata
#               from the YouTube Data API.
# ==============================================================================

# --- Core and Third-Party Libraries ---
import pandas as pd
import streamlit as st
from datetime import datetime
import isodate
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np

# --- Application Configuration ---
st.set_page_config(page_title="YouTube Music Wrapped", page_icon="🎧", layout="wide")

# ==============================================================================
#  1. DATA LOADING AND API INTERACTION
# ==============================================================================

@st.cache_data
def parse_html_history(uploaded_file):
    """
    Parses watch-history.html using a robust method that finds the video link
    and then uses regex to find the timestamp.
    """
    try:
        html_content = uploaded_file.read()
        soup = BeautifulSoup(html_content, "lxml")
        records = []
        
        timestamp_pattern = re.compile(r'\d{1,2}\s\w{3,4}\s\d{4},\s\d{2}:\d{2}:\d{2}')
        
        entries = soup.find_all("div", {"class": "content-cell"})
        for entry in entries:
            video_id, timestamp = None, None
            
            video_link = entry.find("a", href=re.compile(r"watch\?v="))
            if not video_link:
                continue
            
            video_id = video_link["href"].split("watch?v=")[-1].split("&")[0]

            entry_text = entry.get_text()
            match = timestamp_pattern.search(entry_text)
            
            if match:
                timestamp_str = match.group(0).replace("Sept", "Sep")
                try:
                    timestamp = datetime.strptime(timestamp_str, '%d %b %Y, %H:%M:%S')
                except ValueError:
                    continue
            
            if video_id and timestamp:
                records.append({"videoId": video_id, "timestamp": timestamp})
        
        if not records:
            st.error("Could not parse any valid video entries from your HTML file.")
            return None
            
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"An unexpected error occurred during HTML parsing. Error: {e}")
        return None

def build_youtube_client(api_key):
    """Builds and validates the YouTube API service object."""
    try:
        youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
        if not hasattr(youtube, 'videos'): raise ValueError("YouTube service object built incorrectly.")
        return youtube
    except Exception as e:
        st.error(f"Failed to build YouTube client: {e}"); return None

# NOTE: @st.cache_data is intentionally removed to allow the progress bar to update.
def fetch_video_metadata(_youtube_client, video_ids, progress_bar, status_text):
    """Fetches video details and updates a Streamlit progress bar."""
    metadata = {}
    video_ids_list = list(video_ids)
    total_videos = len(video_ids_list)
    progress_start, progress_end = 10, 90
    
    for i in range(0, total_videos, 50):
        batch_ids = ",".join(video_ids_list[i:i+50])
        try:
            request = _youtube_client.videos().list(part="contentDetails,snippet", id=batch_ids)
            response = request.execute()
        except HttpError:
            continue
        for item in response.get("items", []):
            try:
                metadata[item["id"]] = {
                    "duration_sec": isodate.parse_duration(item["contentDetails"]["duration"]).total_seconds(),
                    "title": item["snippet"]["title"],
                    "artist": item["snippet"]["channelTitle"],
                    "categoryId": item["snippet"].get("categoryId")
                }
            except (KeyError, isodate.ISO8601Error):
                continue
        
        processed_count = min(i + 50, total_videos)
        percent_complete = processed_count / total_videos if total_videos > 0 else 0
        bar_progress = int(progress_start + (percent_complete * (progress_end - progress_start)))
        status_text.text(f"Step 2/3: Fetching video details... ({processed_count} of {total_videos})")
        progress_bar.progress(bar_progress)
    return metadata

# ==============================================================================
#  2. DATA PROCESSING AND ANALYSIS
# ==============================================================================

def analyze_data(history_df, metadata):
    """Performs the initial, one-time analysis and data preparation."""
    if history_df is None or not metadata: return None
    
    meta_df = pd.DataFrame.from_dict(metadata, orient="index")
    df = history_df.join(meta_df, on="videoId")
    df.dropna(subset=["duration_sec"], inplace=True)

    if df.empty:
        st.warning("No valid video data could be processed after fetching from YouTube.")
        return None
    
    df["duration_min"] = df["duration_sec"] / 60
    return df

def get_summary_for_period(df, period_label="Overall"):
    """Calculates all display metrics for a given dataframe."""
    if df.empty: return None
    summary = {}
    summary['total_minutes'] = df["duration_min"].sum()
    summary['growth_text'] = "First period of data"
        
    fav_artist = df.groupby("artist")["duration_min"].sum().nlargest(1)
    summary['fav_artist'] = fav_artist.index[0] if not fav_artist.empty else "N/A"
    summary['fav_artist_duration'] = fav_artist.iloc[0] if not fav_artist.empty else 0
    
    fav_song = df.groupby("title")["duration_min"].sum().nlargest(1)
    summary['fav_song'] = fav_song.index[0] if not fav_song.empty else "N/A"
    summary['fav_song_duration'] = fav_song.iloc[0] if not fav_song.empty else 0

    summary['by_day'] = df.groupby(df["timestamp"].dt.date)["duration_min"].sum()
    summary['total_period_minutes'] = df["duration_min"].sum()
    summary['chart_period_label'] = period_label
    
    df["hour"] = df["timestamp"].dt.hour
    summary['time_buckets'] = {
        "Morning (6-12)": df[(df["hour"]>=6) & (df["hour"]<12)]["duration_min"].sum(),
        "Afternoon (12-18)": df[(df["hour"]>=12) & (df["hour"]<18)]["duration_min"].sum(),
        "Evening (18-24)": df[(df["hour"]>=18) & (df["hour"]<24)]["duration_min"].sum(),
        "Night (0-6)": df[df["hour"]<6]["duration_min"].sum(),
    }
    summary['top_songs'] = df["title"].value_counts().head(10)
    summary['top_artists'] = df.groupby("artist")["duration_min"].sum().nlargest(10)
    return summary

# ==============================================================================
#  3. UI RENDERING & MAIN APP FLOW
# ==============================================================================

def render_sidebar():
    st.sidebar.header("⚙️ Configuration")
    api_key = st.sidebar.text_input("Enter your YouTube API Key", type="password", help="Your API key is required to fetch video details.")
    uploaded_file = st.sidebar.file_uploader("Upload your `watch-history.html`", type=["html"], help="Get this file from Google Takeout.")
    return api_key, uploaded_file

def render_kpis(summary):
    st.header("✨ Your Music Review")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Music Time", f"{int(summary['total_minutes']):,} min", delta=summary['growth_text'])
    col2.metric("Favorite Artist", summary['fav_artist'], f"{int(summary['fav_artist_duration'])} min")
    col3.metric("Favorite Song", summary['fav_song'], f"{int(summary['fav_song_duration'])} min")

def render_charts(summary):
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📅 Daily Music Listening")
        by_day = summary['by_day']
        if by_day.empty: st.write("No daily listening data to display."); return
        daily_avg = by_day.mean(); plt.style.use("dark_background"); fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(by_day.index, by_day.values, color="#FF0000", alpha=0.9)
        ax.axhline(daily_avg, color="white", linestyle="--", alpha=0.7, label=f"Avg: {daily_avg:.0f} min/day")
        title_text = f"Total of {int(summary['total_period_minutes']):,} minutes in {summary['chart_period_label']}"
        ax.set_title(title_text, fontsize=16, weight="bold", color="white")
        ax.set_ylabel("Minutes Listened"); ax.legend(); fig.autofmt_xdate(); plt.tight_layout(); st.pyplot(fig)
    with col2:
        st.subheader("🕒 By Time of Day"); time_buckets = summary.get('time_buckets', {}); sorted_buckets = dict(sorted(time_buckets.items(), key=lambda item: -item[1]))
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
        top_artists_df['duration_min'] = top_artists_df['duration_min'].astype(int)
        st.dataframe(top_artists_df.rename(columns={"artist": "Artist", "duration_min": "Minutes Listened"}))

def main():
    st.title("🎧 YouTube Music Wrapped")
    st.markdown("Your personal YouTube listening history, visualized.")
    api_key, uploaded_file = render_sidebar()
    if not api_key or not uploaded_file:
        st.info("Please provide your API key and upload your `watch-history.html` to begin."); st.stop()

    progress_bar = st.progress(0); status_text = st.empty()
    status_text.text("Step 1/3: Parsing your HTML history file...");
    history_df = parse_html_history(uploaded_file)
    if history_df is None: progress_bar.empty(); status_text.empty(); st.stop()
    progress_bar.progress(10)

    youtube_client = build_youtube_client(api_key)
    if not youtube_client: progress_bar.empty(); status_text.empty(); st.stop()
    
    unique_ids = history_df["videoId"].unique()
    metadata = fetch_video_metadata(youtube_client, unique_ids, progress_bar, status_text)
    if not metadata: progress_bar.empty(); status_text.empty(); st.stop()
    progress_bar.progress(90)

    status_text.text("Step 3/3: Analyzing your listening habits...")
    full_music_df = analyze_data(history_df, metadata)
    progress_bar.progress(100); progress_bar.empty(); status_text.empty()
    
    if full_music_df is None:
        st.error("Could not generate analytics from your data."); st.stop()
    
    st.success("Analysis complete!")
    
    summary = get_summary_for_period(full_music_df)
    if not summary:
        st.warning(f"No listening data found for the selected period."); st.stop()

    render_kpis(summary)
    st.markdown("---")
    render_charts(summary)
    st.markdown("---")
    render_top_lists(summary)

if __name__ == "__main__":
    main()