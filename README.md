# 🎧 YouTube Music Wrapped

**Tired of waiting all year for your YouTube Music Recap? We were too.**

This tool puts you in control, transforming your listening history into a personalized, "Wrapped-style" interactive dashboard—anytime you want it. Uncover your *real* top artists, most-played songs, and unique listening habits in just a few clicks. Your stats, at your fingertips.


## ✨ Features

*   **On-Demand "Wrapped":** Generate your personalized music summary whenever you want, not just once a year.
*   **Intelligent Music Detection:** A robust parser sifts through your entire Google Takeout history to find only your genuine YouTube Music listens.
*   **Interactive Time Travel:** Use radio buttons and dropdowns to explore your stats **Overall**, **By Month**, or **By Week**.
*   **Smart Song Ranking:** Ranks your favorite songs using a **"Listen Score"** (Plays × Minutes) that rewards the tracks you *truly* have on repeat, not just the longest ones.
*   **Outlier Protection:** Automatically caps the duration of long-form content (mixes, albums) to give a more accurate picture of your day-to-day listening habits.
*   **Stunning Visualizations:**
    *   A daily listening bar chart to track your consistency and listening streaks.
    *   A stylish neon bubble chart showing your listening patterns by time of day.
*   **Complete Data Transparency:** An expandable "Full Data Explorer" shows complete, scrollable tables of every song and artist, so you can verify every single data point.
*   **Built-in Diagnostic Mode:** Suspect your Takeout file is missing data? Run the diagnostic tool to get a complete audit of the parsing pipeline and confirm data integrity.

## 🤔 The Secret Sauce: How It Works

The magic happens in a few key steps:

1.  **HTML Archeology (Parsing):** First, you upload your `watch-history.html` file. The app acts like an archeologist, carefully sifting through the file's complex structure. It intelligently identifies a music listen if **either** the link points to `music.youtube.com` **or** if the entry is explicitly labeled "YouTube Music". It even handles Google's inconsistent date formats (like "Sep" vs. "Sept").

2.  **Calling the YouTube Oracle (API Fetching):** The app takes the clean list of unique video IDs and queries the official YouTube Data API. It retrieves crucial metadata for each song: its official title, the artist's channel name, and its precise duration.

3.  **Leveling the Playing Field (Duration Capping):** To prevent that one 3-hour DJ mix you listened to from dominating your stats, the app normalizes the data. Any single song listen longer than 7 minutes is counted as exactly 7 minutes. This gives a much truer picture of your most frequent habits.

4.  **Finding Your *Real* Favorites (Listen Score):** This is where the real brains are. Instead of just ranking by play count or total time, the app calculates a **"Listen Score"** for every song. This score is a simple but powerful formula: **`Total Plays × Total Capped Minutes`**. It heavily rewards songs that you listen to both frequently *and* for a significant amount of time.

5.  **Bringing it to Life (Interactive Dashboard):** All of this refined data is then fed into a dynamic Streamlit dashboard, where you can explore your personal music universe with interactive charts and tables.

## 🔧 Setup & Installation

Getting started is easy. You'll need Python 3.8+ installed.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/hrishiwastaken/YTMusicWrapped.git
    cd YTMusicWrappe
    ```

2.  **Create a virtual environment (highly recommended):**
    ```bash
    # For macOS / Linux
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install the dependencies:**
    Create a file named `requirements.txt` in the project folder and add the following lines:
    ```
    streamlit
    pandas
    google-api-python-client
    isodate
    beautifulsoup4
    lxml
    matplotlib
    numpy
    ```
    Then, run this command in your terminal:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the app!**
    ```bash
    streamlit run app.py
    ```

## 🗺️ A Step-by-Step Adventure: How to Use It

The app is designed to be simple. Just follow the steps in the sidebar!

1.  **Step 1: Get Your Credentials**
    *   The app requires two things: a **YouTube API Key** and your **Google Takeout file**.
    *   Hover over the **`?`** next to each input in the sidebar for detailed, step-by-step instructions on how to get them.

2.  **Step 2: Upload and Process**
    *   Enter your API Key into the first field.
    *   Click "Browse files" and upload your `watch-history.html` file.
    *   The app will automatically begin processing. A progress bar will show you its status as it fetches data from the YouTube API. This can take a few minutes for a large history file.

3.  **Step 3: Explore Your Data!**
    *   Once processing is complete, your dashboard will appear.
    *   Use the **"Select analysis period"** radio buttons to switch between **Overall**, **By Month**, and **By Week** views.
    *   Use the dropdown menu to select a specific month or week to drill down into your stats. The entire dashboard will update instantly.
    *   Scroll down to the **"Full Data Explorer"** and click to expand it if you want to see the complete, sortable lists of all your songs and artists.

## ⚙️ Pro Tip: Dealing with Missing Data

If your dashboard stats look lower than expected (e.g., a whole month seems to be missing), it's very likely that the data was not included in your Google Takeout export.

You can prove this using the built-in **Diagnostic Mode**:
1.  Check the **"Run Diagnostic Mode"** box in the sidebar.
2.  Upload your file and key as usual.
3.  Instead of the dashboard, you will see a **Data Pipeline Audit**.
4.  Check the **"Raw Monthly Breakdown"** table. This shows the raw count of entries found *directly in your HTML file*. If a month shows 0 listens here, it confirms the data was missing from the source file itself.

---
