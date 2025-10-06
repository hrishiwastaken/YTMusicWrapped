# ==============================================================================
#  YouTube Music Wrapped - Definitive Final Version
# ==============================================================================
#  Description: This application analyzes a user's YouTube Music watch history
#               from a Google Takeout file, fetches metadata via the YouTube API,
#               and displays a personalized "Wrapped-style" interactive dashboard.
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
    """
    Parses a watch-history.html file by identifying music entries through
    either the URL domain ('music.youtube.com') or an explicit 'YouTube Music'
    text label. Also handles non-standard date abbreviations (e.g., 'Sept').
    """
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
    """Builds and validates the YouTube API service object."""
    try:
        youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
        if not hasattr(youtube, 'videos'): raise ValueError("YouTube service object built incorrectly.")
        return youtube
    except Exception as e:
        st.error(f"Failed to build YouTube client: {e}"); return None

def fetch_video_metadata(_youtube_client, video_ids, progress_bar, status_text):
    """Fetches video details from the YouTube API and updates a progress bar."""
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
                metadata[item["id"]] = {"duration_sec": isodate.parse_duration(item["contentDetails"]["duration"]).total_seconds(), "title": item["snippet"]["title"], "artist": item["snippet"]["channelTitle"]}
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

@st.cache_data
def analyze_data(history_df, metadata):
    """
    Performs the main one-time analysis: merges data, filters, caps duration,
    and adds time period columns.
    """
    if history_df is None or not metadata: return None, 0
    meta_df = pd.DataFrame.from_dict(metadata, orient="index"); music_df = history_df.join(meta_df, on="videoId")
    music_df.dropna(subset=["duration_sec"], inplace=True)
    pre_filter_count = len(music_df)
    music_df_filtered = music_df[music_df['duration_sec'] >= MINIMUM_SONG_DURATION_SECONDS].copy()
    if music_df_filtered.empty:
        st.warning(f"No music entries longer than {MINIMUM_SONG_DURATION_SECONDS} seconds were found."); return None, pre_filter_count
    music_df_filtered["duration_min"] = music_df_filtered["duration_sec"] / 60
    music_df_filtered["capped_duration_min"] = music_df_filtered["duration_min"].clip(upper=MAXIMUM_SONG_DURATION_MINUTES)
    music_df_filtered["month"] = music_df_filtered["timestamp"].dt.to_period('M')
    music_df_filtered["week"] = music_df_filtered["timestamp"].dt.to_period('W')
    return music_df_filtered, pre_filter_count

def get_summary_for_period(df, period_label, full_df, granularity):
    """Calculates all display metrics for a given dataframe with context-aware delta comparison."""
    if df.empty: return None
    summary = {}
    summary['total_minutes'] = df["capped_duration_min"].sum()
    if granularity == "Overall":
        summary['growth_text'] = None
    else:
        current_total = df['capped_duration_min'].sum()
        if granularity == "By Month":
            current_period = df['month'].iloc[0]; previous_period = current_period - 1
            previous_df = full_df[full_df['month'] == previous_period]; period_name = previous_period.strftime('%B')
        else: # By Week
            current_period = df['week'].iloc[0]; previous_period = current_period - 1
            previous_df = full_df[full_df['week'] == previous_period]; period_name = f"previous week"
        previous_total = previous_df['capped_duration_min'].sum()
        if previous_total > 0:
            growth = ((current_total - previous_total) / previous_total) * 100
            summary['growth_text'] = f"{growth:+.1f}% vs {period_name}"
        else:
            summary['growth_text'] = "First period of data"
    song_agg = df.groupby('title').agg(total_minutes=('capped_duration_min', 'sum'), play_count=('title', 'count'))
    song_agg['listen_score'] = song_agg['play_count'] * song_agg['total_minutes']
    song_agg = song_agg.sort_values(by='listen_score', ascending=False)
    fav_song_series = song_agg.head(1)
    summary['fav_song'] = fav_song_series.index[0] if not fav_song_series.empty else "N/A"
    summary['fav_song_duration'] = fav_song_series['total_minutes'].iloc[0] if not fav_song_series.empty else 0
    summary['top_songs'] = song_agg.head(10)
    fav_artist = df.groupby("artist")["capped_duration_min"].sum().nlargest(1)
    summary['fav_artist'] = fav_artist.index[0] if not fav_artist.empty else "N/A"
    summary['fav_artist_duration'] = fav_artist.iloc[0] if not fav_artist.empty else 0
    summary['top_artists'] = df.groupby("artist")["capped_duration_min"].sum().nlargest(10)
    summary['by_day'] = df.groupby(df["timestamp"].dt.date)["capped_duration_min"].sum()
    summary['total_period_minutes'] = df["capped_duration_min"].sum()
    summary['chart_period_label'] = period_label
    df["hour"] = df["timestamp"].dt.hour
    summary['time_buckets'] = df.groupby(pd.cut(df['hour'], bins=[-1, 5, 11, 17, 23], labels=['Night (0-6)', 'Morning (6-12)', 'Afternoon (12-18)', 'Evening (18-24)']))['capped_duration_min'].sum().to_dict()
    return summary

# ==============================================================================
#  3. UI RENDERING & MAIN APP FLOW
# ==============================================================================

def render_sidebar():
    """Renders the sidebar and includes detailed instructions in tooltips."""
    st.sidebar.header("⚙️ Configuration")
    api_key_help_text = """
    **How to get your YouTube API Key:**
    1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
    2.  Create a **New Project**.
    3.  In the search bar, find and enable the **"YouTube Data API v3"**.
    4.  Go to "Credentials", click **"+ CREATE CREDENTIALS"** and select **"API key"**.
    5.  Copy the key. For security, it's best to click "Edit API key" and restrict it to only the "YouTube Data API v3".
    """
    takeout_help_text = """
    **How to get your `watch-history.html` file:**
    1.  Go to [Google Takeout](https://takeout.google.com/).
    2.  Click **"Deselect all"**.
    3.  Scroll down and check the box for **"YouTube and YouTube Music"**.
    4.  Click the button that says "All YouTube data included".
    5.  Click **"Deselect all"** again, then check only **"history"**. Click OK.
    6.  Scroll to the bottom and click "Next step".
    7.  Ensure the format is set to **HTML**. Click "Create export".
    8.  Download the file when it's ready, unzip it, and find `watch-history.html` inside the `Takeout/YouTube and YouTube Music/history/` folder.
    """
    api_key = st.sidebar.text_input("Enter your YouTube API Key", type="password", help=api_key_help_text)
    uploaded_file = st.sidebar.file_uploader("Upload your `watch-history.html`", type=["html"], help=takeout_help_text)
    st.sidebar.markdown("---")
    run_diagnostics = st.sidebar.checkbox("Run Diagnostic Mode", help="Use this to audit the data pipeline if results seem incorrect.")
    return api_key, uploaded_file, run_diagnostics

def render_kpis(summary):
    st.header("✨ Your Music Review"); col1, col2, col3 = st.columns(3)
    col1.metric("Total Music Time (Capped)", f"{int(summary['total_minutes']):,} min", delta=summary['growth_text'])
    col2.metric("Favorite Artist", summary['fav_artist'], f"{int(summary['fav_artist_duration'])} min")
    col3.metric("Favorite Song (by Score)", summary['fav_song'], f"{int(summary['fav_song_duration'])} min")

def render_charts(summary):
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📅 Daily Music Listening"); by_day = summary['by_day']
        if by_day.empty: st.write("No daily listening data to display."); return
        daily_avg = by_day.mean(); plt.style.use("dark_background"); fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(by_day.index, by_day.values, color="#FF0000", alpha=0.9)
        ax.axhline(daily_avg, color="white", linestyle="--", alpha=0.7, label=f"Avg: {daily_avg:.0f} min/day")
        title_text = f"Total of {int(summary['total_period_minutes']):,} minutes in {summary['chart_period_label']}"
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
        st.subheader("🔥 Top Songs (by Listen Score)"); top_songs_df = summary['top_songs'].reset_index()
        top_songs_df['listen_score'] = top_songs_df['listen_score'].astype(int); top_songs_df['total_minutes'] = top_songs_df['total_minutes'].astype(int)
        st.dataframe(top_songs_df.rename(columns={"title": "Song", "listen_score": "Listen Score", "play_count": "Plays", "total_minutes": "Minutes"}))
    with col2:
        st.subheader("🎤 Top Artists (by capped minutes)"); top_artists_df = summary['top_artists'].reset_index()
        top_artists_df['capped_duration_min'] = top_artists_df['capped_duration_min'].astype(int)
        st.dataframe(top_artists_df.rename(columns={"artist": "Artist", "capped_duration_min": "Minutes Listened (Capped)"}))

def render_full_data_tables(df):
    with st.expander("🔍 Full Data Explorer (Scroll & Sort to Verify)"):
        st.markdown("### All Songs, Ranked by Listen Score")
        song_summary = df.groupby('title').agg(total_minutes=('capped_duration_min', 'sum'), actual_minutes=('duration_min', 'sum'), play_count=('title', 'count')).sort_values(by='total_minutes', ascending=False)
        song_summary['listen_score'] = song_summary['play_count'] * song_summary['total_minutes']
        song_summary = song_summary.sort_values(by='listen_score', ascending=False).reset_index()
        song_summary['listen_score'] = song_summary['listen_score'].astype(int); song_summary['total_minutes'] = song_summary['total_minutes'].astype(int); song_summary['actual_minutes'] = song_summary['actual_minutes'].astype(int)
        st.dataframe(song_summary)
        st.markdown("### All Artists, Ranked by Capped Listen Time")
        artist_summary = df.groupby('artist').agg(capped_minutes=('capped_duration_min', 'sum'), actual_minutes=('duration_min', 'sum'), play_count=('artist', 'count')).sort_values(by='capped_minutes', ascending=False).reset_index()
        artist_summary['capped_minutes'] = artist_summary['capped_minutes'].astype(int); artist_summary['actual_minutes'] = artist_summary['actual_minutes'].astype(int)
        st.dataframe(artist_summary)

def render_diagnostics(diagnostics):
    st.warning("🕵️ Diagnostic Mode Enabled"); st.header("Data Pipeline Audit")
    st.subheader("Step 1: HTML Parsing"); st.metric("Total Music Entries Found in HTML", f"{diagnostics['raw_parse_count']:,}")
    st.subheader("Step 2: API Metadata Fetch"); st.metric("Entries with Valid Metadata from API", f"{diagnostics['api_metadata_count']:,}")
    st.subheader("Step 3: Duration Filtering"); st.metric(f"Entries Longer Than {MINIMUM_SONG_DURATION_SECONDS}s (Final Count)", f"{diagnostics['final_qualified_count']:,}")
    st.markdown("---"); st.subheader("Raw Monthly Breakdown (Before Any Filtering)")
    st.write("This table shows the raw count of music entries found in your HTML file for each month. If a month has 0 entries here, the data was not present in your Takeout file.")
    st.dataframe(diagnostics['monthly_raw_counts'])

def main():
    st.title("🎧 YouTube Music Wrapped")
    st.markdown("Your personal YouTube listening history, visualized.")
    api_key, uploaded_file, run_diagnostics = render_sidebar()
    if not api_key or not uploaded_file: st.info("Please provide your API key and upload your `watch-history.html` to begin."); st.stop()
    
    @st.cache_data
    def get_full_dataset(u_file, api_k):
        h_df = parse_html_history(u_file)
        if h_df is None: return None, 0
        yt_client = build_youtube_client(api_k)
        if not yt_client: return None, 0
        dummy_bar, dummy_text = st.progress(0), st.empty()
        u_ids = h_df["videoId"].unique()
        meta = fetch_video_metadata(yt_client, u_ids, dummy_bar, dummy_text)
        dummy_bar.empty(); dummy_text.empty()
        if not meta: return None, 0
        df, pre_filter_count = analyze_data(h_df, meta)
        return df, pre_filter_count

    if run_diagnostics:
        progress_bar = st.progress(0); status_text = st.empty()
        status_text.text("Diagnostic Step 1/3: Parsing HTML...");
        history_df = parse_html_history(uploaded_file)
        if history_df is None: st.stop()
        progress_bar.progress(10)
        youtube_client = build_youtube_client(api_key);
        if not youtube_client: st.stop()
        unique_ids = history_df["videoId"].unique()
        metadata = fetch_video_metadata(youtube_client, unique_ids, progress_bar, status_text)
        if not metadata: st.stop()
        status_text.text("Diagnostic Step 3/3: Analyzing..."); progress_bar.progress(90)
        full_music_df, pre_filter_count = analyze_data(history_df, metadata)
        monthly_raw_counts = history_df.copy(); monthly_raw_counts['month'] = monthly_raw_counts['timestamp'].dt.to_period('M')
        monthly_breakdown = monthly_raw_counts.groupby(monthly_raw_counts['month'].dt.strftime('%B %Y'))['videoId'].count().sort_index(ascending=False).reset_index()
        monthly_breakdown.columns = ["Month", "Raw Listen Count"]
        diagnostics = {"raw_parse_count": len(history_df), "api_metadata_count": pre_filter_count, "final_qualified_count": len(full_music_df) if full_music_df is not None else 0, "monthly_raw_counts": monthly_breakdown}
        progress_bar.empty(); status_text.empty()
        render_diagnostics(diagnostics)
    else:
        with st.spinner("Processing your history for the first time... This may take a few minutes."):
            full_music_df, _ = get_full_dataset(uploaded_file, api_key)
        if full_music_df is None: st.error("Could not generate analytics from your data."); st.stop()
        st.success("Analysis complete!")
        st.info(f"💡 Note: Song listens >{MAXIMUM_SONG_DURATION_MINUTES} min are capped. Favorite song is ranked by a Listen Score (Plays × Minutes).")
        st.markdown("---")
        granularity = st.radio("Select analysis period:", ["Overall", "By Month", "By Week"], horizontal=True)
        display_df = pd.DataFrame(); period_label = "Overall"
        min_date, max_date = full_music_df['timestamp'].min(), full_music_df['timestamp'].max()

        if granularity == "Overall":
            display_df = full_music_df
        elif granularity == "By Month":
            all_months = pd.period_range(start=min_date, end=max_date, freq='M'); month_periods = sorted(all_months, reverse=True)
            month_options = [p.strftime('%B %Y') for p in month_periods]; selected_month_str = st.selectbox("Select Month:", month_options)
            if selected_month_str:
                period_label = selected_month_str; selected_month_period = pd.Period(selected_month_str, freq='M')
                display_df = full_music_df[full_music_df['month'] == selected_month_period]
        elif granularity == "By Week":
            all_weeks = pd.period_range(start=min_date, end=max_date, freq='W'); week_periods = sorted(all_weeks, reverse=True)
            week_options = {p.start_time.strftime('Week of %b %d, %Y'): p for p in week_periods}; selected_week_str = st.selectbox("Select Week:", list(week_options.keys()))
            if selected_week_str:
                period_label = selected_week_str; selected_week_period = week_options[selected_week_str]
                display_df = full_music_df[full_music_df['week'] == selected_week_period]
        
        summary = get_summary_for_period(display_df, period_label, full_music_df, granularity)
        if not summary:
            st.warning(f"No listening data found for the selected period."); st.stop()
        render_kpis(summary)
        st.markdown("---")
        render_charts(summary)
        st.markdown("---")
        render_top_lists(summary)
        st.markdown("---")
        render_full_data_tables(full_music_df)

if __name__ == "__main__":
    main()