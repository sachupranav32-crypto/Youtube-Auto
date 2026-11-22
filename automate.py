import os
import json
import subprocess
import urllib.parse
import requests
import feedparser
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 1. Fetch Live Trending Topic (India)
def get_trending_topic():
    feed = feedparser.parse("https://google.com")
    if feed.entries:
        return feed.entries[0].title
    return "An inspiring emotional story about humanity and hope"

# 2. Generate Script & Image Prompts using Free Gemini API
def generate_content(topic):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = f"""
    Create a gripping 45-second YouTube Short script inspired by or connected to the trending topic: '{topic}'.
    Keep the tone emotional, cinematic, and engaging (similar to a storytelling channel).
    Return ONLY valid JSON with no markdown formatting:
    {{
        "title": "Catchy YouTube Shorts title under 70 chars #Shorts",
        "description": "Engaging 2-sentence description with 5 relevant hashtags",
        "narration": "Full spoken voiceover script (around 90 to 110 words, natural pacing)",
        "image_prompts": [
            "Detailed cinematic 9:16 vertical digital art prompt for scene 1",
            "Detailed cinematic 9:16 vertical digital art prompt for scene 2",
            "Detailed cinematic 9:16 vertical digital art prompt for scene 3",
            "Detailed cinematic 9:16 vertical digital art prompt for scene 4"
        ]
    }}
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    clean_json = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    return json.loads(clean_json)

# 3. Generate Free Neural Voiceover (Microsoft Edge TTS)
def generate_voiceover(text, output_audio="voice.mp3"):
    subprocess.run([
        "edge-tts",
        "--voice", "en-IN-PrabhatNeural",
        "--text", text,
        "--write-media", output_audio
    ], check=True)

# 4. Generate Free AI Images (Pollinations.ai)
def generate_images(prompts):
    image_files = []
    for i, prompt in enumerate(prompts):
        encoded = urllib.parse.quote(prompt)
        url = f"https://pollinations.ai{encoded}?width=1080&height=1920&nologo=true"
        img_data = requests.get(url, timeout=60).content
        filename = f"scene_{i}.jpg"
        with open(filename, "wb") as f:
            f.write(img_data)
        image_files.append(filename)
    return image_files

# 5. Render 9:16 Vertical Short with FFmpeg
def create_video(image_files, audio_file="voice.mp3", output_video="short.mp4"):
    probe = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_file
    ])
    total_duration = float(probe.strip())
    clip_duration = total_duration / len(image_files)

    clip_files = []
    for i, img in enumerate(image_files):
        clip_name = f"clip_{i}.mp4"
        frames = int(clip_duration * 30)
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", img,
            "-vf", f"scale=1080:1920,zoompan=z='min(zoom+0.001,1.15)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920",
            "-c:v", "libx264", "-t", str(clip_duration), "-pix_fmt", "yuv420p", "-r", "30", clip_name
        ], check=True)
        clip_files.append(clip_name)

    with open("clips.txt", "w") as f:
        for clip in clip_files:
            f.write(f"file '{clip}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "clips.txt",
        "-i", audio_file, "-c:v", "copy", "-c:a", "aac", "-shortest", output_video
    ], check=True)

# 6. Auto-Upload to YouTube via Data API v3
def upload_to_youtube(video_file, title, description):
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://googleapis.com",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://googleapis.com"]
    )
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "categoryId": "24"
        },
        "status": {
            "privacyStatus": "unlisted",  # Change "unlisted" to "public" after your first test run
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print("Successfully uploaded! Video ID:", response.get("id"))

if __name__ == "__main__":
    topic = get_trending_topic()
    print("Selected Trend:", topic)
    content = generate_content(topic)
    generate_voiceover(content["narration"])
    images = generate_images(content["image_prompts"])
    create_video(images)
    upload_to_youtube("short.mp4", content["title"], content["description"])

