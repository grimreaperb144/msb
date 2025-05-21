import streamlit as st
import yt_dlp
import whisper
import ffmpeg
import os
import uuid
from pathlib import Path

# Setup directories
DOWNLOAD_DIR = Path("downloads")
CLIP_DIR = Path("clips")
DOWNLOAD_DIR.mkdir(exist_ok=True)
CLIP_DIR.mkdir(exist_ok=True)

# Whisper model cache
@st.cache_resource
def load_model():
    return whisper.load_model("base")

model = load_model()

def download_video(url):
    st.info("Downloading video...")
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": str(DOWNLOAD_DIR / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4"
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info["id"]
        ext = info["ext"]
        fname = DOWNLOAD_DIR / f"{video_id}.{ext}"
        if not fname.exists():
            raise FileNotFoundError(f"Could not find downloaded video at {fname}")
        return str(fname), info["title"]

def transcribe_video(video_path):
    st.info("Transcribing video with Whisper (may take a while)...")
    result = model.transcribe(str(video_path))
    return result["segments"]

def detect_funny_moments(segments):
    keywords = ["haha", "lol", "laugh", "funny", "rofl", "lmao"]
    funny = []
    for seg in segments:
        if any(word in seg["text"].lower() for word in keywords):
            funny.append(seg)
    return funny

def cut_clip(input_path, start, end):
    clip_id = str(uuid.uuid4())
    output_path = CLIP_DIR / f"{clip_id}.mp4"
    (
        ffmpeg
        .input(str(input_path), ss=start, to=end)
        .output(str(output_path), vcodec='libx264', acodec='aac', strict='experimental', preset='fast', y=None)
        .run(quiet=True, overwrite_output=True)
    )
    return output_path

def vtt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds * 1000) % 1000)
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"

def save_vtt(segments, vtt_path):
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{vtt_time(seg['start'])} --> {vtt_time(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")

st.title("AI Viral Shorts Streamlit App")
st.write("Paste a YouTube URL and get AI-generated viral video clips with captions!")

yt_url = st.text_input("Enter YouTube video URL:")

if yt_url:
    if st.button("Process Video"):
        try:
            video_path, title = download_video(yt_url)
            st.success(f"Downloaded: {title}")

            segments = transcribe_video(video_path)
            funny_segments = detect_funny_moments(segments)
            st.info(f"Found {len(funny_segments)} funny moments.")

            if not funny_segments:
                st.warning("No funny moments detected (by keywords).")
            else:
                for seg in funny_segments:
                    st.write(f"**{seg['text']}**")
                    start, end = seg["start"], seg["end"]
                    clip_path = cut_clip(video_path, start, end)
                    vtt_path = clip_path.with_suffix(".vtt")
                    save_vtt([seg], vtt_path)
                    video_bytes = open(clip_path, "rb").read()
                    st.video(video_bytes)
                    st.download_button(
                        "Download Clip",
                        data=video_bytes,
                        file_name=clip_path.name,
                        mime="video/mp4"
                    )
                    st.download_button(
                        "Download Captions (VTT)",
                        data=open(vtt_path, "rb").read(),
                        file_name=vtt_path.name,
                        mime="text/vtt"
                    )
        except Exception as e:
            st.error(f"Error: {e}")
