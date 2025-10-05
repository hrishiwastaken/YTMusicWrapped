# ==============================================================================
#  YouTube Music Wrapped - Version 3.0
# ==============================================================================
#  Description: This version adds interactive controls, allowing users to
#               filter the dashboard by month. It also adds full, sortable data
#               tables in an expander for data verification and transparency.
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
MINIMUM_SONG_DURATION_SECONDS = 60
MAXIMUM_SONG_DURATION_MINUTES = 7

# ==============================================================================
#  1. DATA LOADING AND API INTERACTION
# ==============================================================================

@st.cache_data
def parse_html_history(uploaded_file):
    """Parses watch-history.html using a flexible method that identifies music entries."""
    try:
        html_content = uploaded_file.read(); soup = BeautifulSoup(html_content, "lxml")
        records = []; entries = soup.find_all("div", {"class": "content-cell"})
        timestamp_pattern = re.compile(r'\d{1,2}\s\w{3,4}\s\d{4},\s\d{2}:\d{2}:\d{2}')
        for entry in entries:
            link = entry.find("a", href=True)
            if not link or "watch?v=" not in link["href"]: continue
            href = link.get("href", ""); header_div = entry.find_previous_sibling("div")
            header_text = header_div.get_text() if header_div else ""
            if not ("music.youtube.com" in href or "YouTube Music" in header_text): continue
            video_id = href.split("watch?v=")[-1].split("&")[0]
            entry_text = entry.get_text(); match = timestamp_pattern.search(entry_text)
            if match:
                timestamp_str_fixed = match.group(0).replace("Sept", "Sep")
                try:
                    timestamp = datetime.strptime(timestamp_str_fixed, '%d %b %Y, %H:%M:%S')
                    records.append({"videoId": video_id, "timestamp": timestamp})
                except ValueError: continue
        if not records:
            st.error("Could not parse any valid music entries from the HTML file."); return None
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"An unexpected error occurred during HTML parsing. Error: {e}"); return None

def build_youtube_client(api_key):
    try:
        youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
        if not hasattr(youtube, 'videos'): raise ValueError("YouTube service object built incorrectly.")
        return youtube
    except Exception as e:
        st.error(f"Failed to build YouTube client: {e}"); return None

def fetch_video_metadata(_youtube_client, video_ids, progress_bar, status_text):
    metadata = {}; video_ids_list = list(video_ids); total_videos = len(video_ids_list)
    progress_start, progress_end = 10, 90
    for i in range(0, total_videos, 50):
        batch_ids = ",".join(video_ids_list[i:i+50])
        try:
            request = _youtube_client.videos().list(part="contentDetails,snippet", id=batch_ids)
            response = request.execute()
        except HttpError: continue
        for item in response.get("items", []):
            try:
                metadata[item["id"]] = {"duration_sec": isodate.parse_duration(item["contentDetails"]["duration"]).total_seconds(), "title": item["snippet"]["title"], "artist": item["snippet"]["channelTitle"], "categoryId": item["snippet"].get("categoryId")}
            except (KeyError, isodate.ISO8601Error): continue
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
    df.dropna(subset=["duration_sec", "categoryId"], inplace=True)
    music_df = df[(df['categoryId'] == '10') & (df['duration_sec'] >= MINIMUM_SONG_DURATION_SECONDS)].copy()
    if music_df.empty:
        st.warning(f"No videos matching the criteria were found.")
        return None
    music_df["duration_min"] = music_df["duration_sec"] / 60
    music_df["capped_duration_min"] = music_df["duration_min"].clip(upper=MAXIMUM_SONG_DURATION_MINUTES)
    # --- NEW: Add month column for filtering ---
    music_df["month"] = music_df["timestamp"].dt.to_period('M')
    return music_df

def get_summary_for_period(df):
    """Calculates all display metrics for a given dataframe (can be all-time or one month)."""
    if df.empty: return None
    summary = {}
    summary['total_minutes'] = df["capped_duration_min"].sum()
    by_month = df.groupby(df["timestamp"].dt.to_period("M"))["capped_duration_min"].sum()
    if len(by_month) > 1:
        growth = ((by_month.iloc[-1] - by_month.iloc[-2]) / by_month.iloc[-2]) * 100 if by_month.iloc[-2] > 0 else 0
        summary['growth_text'] = f"{growth:+.1f}% vs {by_month.index[-2].strftime('%B')}"
    else:
        summary['growth_text'] = "First period of data"
    fav_artist = df.groupby("artist")["capped_duration_min"].sum().nlargest(1)
    summary['fav_artist'] = fav_artist.index[0] if not fav_artist.empty else "N/A"
    summary['fav_artist_duration'] = fav_artist.iloc[0] if not fav_artist.empty else 0
    fav_song = df.groupby("title")["capped_duration_min"].sum().nlargest(1)
    summary['fav_song'] = fav_song.index[0] if not fav_song.empty else "N/A"
    summary['fav_song_duration'] = fav_song.iloc[0] if not fav_song.empty else 0
    summary['by_day'] = df.groupby(df["timestamp"].dt.date)["capped_duration_min"].sum()
    summary['by_month_total'] = by_month.sum()
    summary['latest_month_str'] = by_month.index[-1].strftime('%B %Y') if not by_month.empty else "Selected Period"
    df["hour"] = df["timestamp"].dt.hour
    summary['time_buckets'] = { "Morning (6-12)": df[(df["hour"]>=6) & (df["hour"]<12)]["capped_duration_min"].sum(), "Afternoon (12-18)": df[(df["hour"]>=12) & (df["hour"]<18)]["capped_duration_min"].sum(), "Evening (18-24)": df[(df["hour"]>=18) & (df["hour"]<24)]["capped_duration_min"].sum(), "Night (0-6)": df[df["hour"]<6]["capped_duration_min"].sum() }
    summary['top_songs'] = df.groupby("title")["capped_duration_min"].sum().nlargest(10)
    summary['top_artists'] = df.groupby("artist")["capped_duration_min"].sum().nlargest(10)
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
    st.header("✨ Your Music Review"); col1, col2, col3 = st.columns(3)
    col1.metric("Total Music Time (Capped)", f"{int(summary['total_minutes']):,} min", delta=summary['growth_text'])
    col2.metric("Favorite Artist", summary['fav_artist'], f"{int(summary['fav_artist_duration'])} min")
    col3.metric("Favorite Song", summary['fav_song'], f"{int(summary['fav_song_duration'])} min")

def render_charts(summary):
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📅 Daily Music Listening"); by_day = summary['by_day']
        if by_day.empty: st.write("No daily listening data to display."); return
        daily_avg = by_day.mean(); plt.style.use("dark_background"); fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(by_day.index, by_day.values, color="#FF0000", alpha=0.9)
        ax.axhline(daily_avg, color="white", linestyle="--", alpha=0.7, label=f"Avg: {daily_avg:.0f} min/day")
        title_text = f"Total of {int(summary['by_month_total']):,} minutes in {summary['latest_month_str']}"
        ax.set_title(title_text, fontsize=16, weight="bold", color="white")
        ax.set_ylabel("Minutes Listened (Capped)"); ax.legend(); fig.autofmt_xdate(); plt.tight_layout(); st.pyplot(fig)
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
    st.header("🏆 Your Top 10s"); col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔥 Top Songs (by capped minutes)")
        top_songs_df = summary['top_songs'].reset_index()
        top_songs_df['capped_duration_min'] = top_songs_df['capped_duration_min'].astype(int)
        st.dataframe(top_songs_df.rename(columns={"title": "Song", "capped_duration_min": "Minutes Listened (Capped)"}))
    with col2:
        st.subheader("🎤 Top Artists (by capped minutes)")
        top_artists_df = summary['top_artists'].reset_index()
        top_artists_df['capped_duration_min'] = top_artists_df['capped_duration_min'].astype(int)
        st.dataframe(top_artists_df.rename(columns={"artist": "Artist", "capped_duration_min": "Minutes Listened (Capped)"}))

# --- NEW: Full data table rendering function ---
def render_full_data_tables(df):
    """Renders the full, scrollable data tables for verification."""
    with st.expander("🔍 Full Data Explorer (Scroll & Sort to Verify)"):
        st.markdown("### All Songs, Ranked by Capped Listen Time")
        song_summary = df.groupby('title').agg(
            capped_minutes=('capped_duration_min', 'sum'),
            actual_minutes=('duration_min', 'sum'),
            play_count=('title', 'count')
        ).sort_values(by='capped_minutes', ascending=False).reset_index()
        song_summary['capped_minutes'] = song_summary['capped_minutes'].astype(int)
        song_summary['actual_minutes'] = song_summary['actual_minutes'].astype(int)
        st.dataframe(song_summary)

        st.markdown("### All Artists, Ranked by Capped Listen Time")
        artist_summary = df.groupby('artist').agg(
            capped_minutes=('capped_duration_min', 'sum'),
            actual_minutes=('duration_min', 'sum'),
            play_count=('artist', 'count')
        ).sort_values(by='capped_minutes', ascending=False).reset_index()
        artist_summary['capped_minutes'] = artist_summary['capped_minutes'].astype(int)
        artist_summary['actual_minutes'] = artist_summary['actual_minutes'].astype(int)
        st.dataframe(artist_summary)

def main():
    st.title("🎧 YouTube Music Wrapped")
    st.markdown("Your personal YouTube listening history, visualized.")
    api_key, uploaded_file = render_sidebar()
    if not api_key or not uploaded_file:
        st.info("Please provide your API key and upload your `watch-history.html` to begin."); st.stop()

    # --- Use caching to store the processed dataframe after the first run ---
    @st.cache_data
    def get_full_dataset(u_file, api_k):
        # This function wraps the slow parts to be cached
        progress_bar = st.progress(0); status_text = st.empty()
        status_text.text("Step 1/3: Parsing your HTML history file...");
        h_df = parse_html_history(u_file)
        if h_df is None: return None
        progress_bar.progress(10)
        yt_client = build_youtube_client(api_k)
        if not yt_client: return None
        u_ids = h_df["videoId"].unique()
        meta = fetch_video_metadata(yt_client, u_ids, progress_bar, status_text)
        if not meta: return None
        progress_bar.progress(90)
        status_text.text("Step 3/3: Analyzing your listening habits...")
        full_df = analyze_data(h_df, meta)
        progress_bar.progress(100); progress_bar.empty(); status_text.empty()
        return full_df

    full_music_df = get_full_dataset(uploaded_file, api_key)
    
    if full_music_df is None:
        st.error("Could not generate analytics from your data."); st.stop()
    
    st.success("Analysis complete!")
    st.info(f"💡 Note: Song listens >{MAXIMUM_SONG_DURATION_MINUTES} min are capped to prevent skewing from long mixes.")
    st.markdown("---")

    # --- NEW: Interactive Month Selector ---
    month_options = ["All Time"] + sorted(full_music_df['month'].unique().strftime('%B %Y').tolist(), reverse=True)
    selected_month_str = st.selectbox("View stats for:", month_options)
    
    # Filter the dataframe based on selection
    if selected_month_str == "All Time":
        display_df = full_music_df
        period_label = "Overall"
    else:
        selected_month_period = pd.Period(selected_month_str, freq='M')
        display_df = full_music_df[full_music_df['month'] == selected_month_period]
        period_label = selected_month_str

    summary = get_summary_for_period(display_df)
    if not summary:
        st.warning(f"No listening data found for {selected_month_str}."); st.stop()

    render_kpis(summary)
    st.markdown("---")
    render_charts(summary)
    st.markdown("---")
    render_top_lists(summary)
    st.markdown("---")
    # --- NEW: Render the full data tables ---
    render_full_data_tables(full_music_df) # Always show full data for verification

if __name__ == "__main__":
    main()