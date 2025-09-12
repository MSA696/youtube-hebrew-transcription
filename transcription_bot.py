#!/usr/bin/env python3
"""
YouTube Hebrew Transcription Bot
Checks for new YouTube Shorts, transcribes to Hebrew, saves to document
Uses only free/low-cost services
"""

import os
import json
import requests
import whisper
import yt_dlp
from datetime import datetime, timedelta
from pathlib import Path
import schedule
import time

# Configuration
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')  # Get free key from Google Cloud Console
CHANNEL_ID = "YOUR_CHANNEL_ID_HERE"  # Replace with target channel ID
OUTPUT_FILE = "transcriptions.txt"
LAST_CHECK_FILE = "last_check.json"
MAX_DURATION = 60  # Only process videos under 60 seconds

class YouTubeTranscriptionBot:
    def __init__(self):
        self.whisper_model = None
        self.load_whisper_model()
        
    def load_whisper_model(self):
        """Load Whisper model (free, runs locally)"""
        try:
            print("Loading Whisper model...")
            self.whisper_model = whisper.load_model("base")  # Use 'tiny' for faster processing
            print("Whisper model loaded successfully")
        except Exception as e:
            print(f"Error loading Whisper model: {e}")
    
    def get_last_check_time(self):
        """Get the last time we checked for videos"""
        try:
            if Path(LAST_CHECK_FILE).exists():
                with open(LAST_CHECK_FILE, 'r') as f:
                    data = json.load(f)
                    return datetime.fromisoformat(data['last_check'])
        except:
            pass
        return datetime.now() - timedelta(days=1)  # Default to yesterday
    
    def save_last_check_time(self):
        """Save the current time as last check time"""
        with open(LAST_CHECK_FILE, 'w') as f:
            json.dump({'last_check': datetime.now().isoformat()}, f)
    
    def get_recent_videos(self):
        """Get recent videos from YouTube channel using free YouTube API"""
        if not YOUTUBE_API_KEY:
            print("YouTube API key not found. Please set YOUTUBE_API_KEY environment variable")
            return []
        
        last_check = self.get_last_check_time()
        
        # YouTube Data API v3 - free tier: 10,000 requests/day
        url = f"https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'channelId': CHANNEL_ID,
            'publishedAfter': last_check.isoformat() + 'Z',
            'order': 'date',
            'type': 'video',
            'maxResults': 10,
            'key': YOUTUBE_API_KEY
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            videos = []
            for item in data.get('items', []):
                video_id = item['id']['videoId']
                title = item['snippet']['title']
                published = item['snippet']['publishedAt']
                
                # Check if it's a short video (under 60 seconds)
                if self.is_short_video(video_id):
                    videos.append({
                        'id': video_id,
                        'title': title,
                        'published': published,
                        'url': f"https://youtube.com/watch?v={video_id}"
                    })
            
            return videos
            
        except Exception as e:
            print(f"Error fetching videos: {e}")
            return []
    
    def is_short_video(self, video_id):
        """Check if video duration is under MAX_DURATION seconds"""
        url = f"https://www.googleapis.com/youtube/v3/videos"
        params = {
            'part': 'contentDetails',
            'id': video_id,
            'key': YOUTUBE_API_KEY
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if data.get('items'):
                duration_str = data['items'][0]['contentDetails']['duration']
                # Parse ISO 8601 duration (e.g., PT1M30S = 90 seconds)
                import re
                match = re.search(r'PT(?:(\d+)M)?(?:(\d+)S)?', duration_str)
                if match:
                    minutes = int(match.group(1) or 0)
                    seconds = int(match.group(2) or 0)
                    total_seconds = minutes * 60 + seconds
                    return total_seconds <= MAX_DURATION
            
            return False
        except:
            return False
    
    def download_audio(self, video_url):
        """Download audio from YouTube video using yt-dlp (free)"""
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'temp_audio.%(ext)s',
            'extractaudio': True,
            'audioformat': 'wav',
            'quiet': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
                
            # Find the downloaded file
            for ext in ['wav', 'mp3', 'm4a', 'webm']:
                audio_file = f"temp_audio.{ext}"
                if Path(audio_file).exists():
                    return audio_file
            
            return None
        except Exception as e:
            print(f"Error downloading audio: {e}")
            return None
    
    def transcribe_to_hebrew(self, audio_file):
        """Transcribe audio to Hebrew using Whisper (free, local)"""
        try:
            # Whisper will auto-detect language and translate to the specified language
            result = self.whisper_model.transcribe(
                audio_file,
                task="translate",  # This translates to English first
                language=None  # Auto-detect
            )
            
            english_text = result["text"]
            
            # Use free translation service (Google Translate via googletrans)
            try:
                from googletrans import Translator
                translator = Translator()
                hebrew_result = translator.translate(english_text, dest='he')
                return hebrew_result.text
            except ImportError:
                print("googletrans not installed. Install with: pip install googletrans==4.0.0-rc1")
                return english_text
            except Exception as e:
                print(f"Translation error: {e}")
                return english_text
                
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return None
    
    def save_transcription(self, video_info, hebrew_text):
        """Save transcription to document file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        entry = f"""
{'='*50}
Date: {timestamp}
Video: {video_info['title']}
URL: {video_info['url']}
Published: {video_info['published']}
{'='*50}
Hebrew Transcription:
{hebrew_text}

"""
        
        try:
            with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                f.write(entry)
            print(f"Transcription saved to {OUTPUT_FILE}")
        except Exception as e:
            print(f"Error saving transcription: {e}")
    
    def cleanup_temp_files(self):
        """Remove temporary audio files"""
        for ext in ['wav', 'mp3', 'm4a', 'webm']:
            temp_file = f"temp_audio.{ext}"
            if Path(temp_file).exists():
                try:
                    os.remove(temp_file)
                except:
                    pass
    
    def process_new_videos(self):
        """Main processing function"""
        print(f"Checking for new videos at {datetime.now()}")
        
        videos = self.get_recent_videos()
        if not videos:
            print("No new short videos found")
            return
        
        print(f"Found {len(videos)} new short video(s)")
        
        for video in videos:
            print(f"Processing: {video['title']}")
            
            # Download audio
            audio_file = self.download_audio(video['url'])
            if not audio_file:
                print(f"Failed to download audio for {video['title']}")
                continue
            
            # Transcribe to Hebrew
            hebrew_text = self.transcribe_to_hebrew(audio_file)
            if not hebrew_text:
                print(f"Failed to transcribe {video['title']}")
                continue
            
            # Limit text to ~500 words
            words = hebrew_text.split()
            if len(words) > 500:
                hebrew_text = ' '.join(words[:500]) + "..."
            
            # Save transcription
            self.save_transcription(video, hebrew_text)
            
            # Cleanup
            self.cleanup_temp_files()
            
            print(f"Successfully processed: {video['title']}")
        
        # Update last check time
        self.save_last_check_time()
        print("Processing complete")

def run_bot():
    """Run the bot once"""
    bot = YouTubeTranscriptionBot()
    bot.process_new_videos()

def schedule_daily_run():
    """Schedule the bot to run daily at specified time"""
    # Schedule for 9:00 AM daily (change as needed)
    schedule.every().day.at("09:00").do(run_bot)
    
    print("Bot scheduled to run daily at 9:00 AM")
    print("Press Ctrl+C to stop")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    # Install required packages:
    print("""
    Required installations:
    pip install yt-dlp openai-whisper googletrans==4.0.0-rc1 schedule requests
    
    Setup steps:
    1. Get free YouTube API key from Google Cloud Console
    2. Set environment variable: export YOUTUBE_API_KEY="your_api_key"
    3. Replace CHANNEL_ID with target channel ID
    4. Run script
    """)
    
    # Choose run mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        # Run once for testing
        run_bot()
    else:
        # Run on schedule
        schedule_daily_run()
