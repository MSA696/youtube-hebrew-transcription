"""
YouTube Hebrew Transcription Bot for Cloud Deployment
Transcribes Hebrew audio from YouTube Shorts to Google Docs
Runs on GitHub Actions (free) with Google Cloud services
"""

import os
import json
import requests
import whisper
import yt_dlp
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import base64

# Configuration
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID', "YOUR_CHANNEL_ID_HERE")
GOOGLE_DOC_ID = os.getenv('GOOGLE_DOC_ID', "YOUR_GOOGLE_DOC_ID_HERE")
GOOGLE_CREDENTIALS_B64 = os.getenv('GOOGLE_CREDENTIALS_B64')  # Base64 encoded service account JSON
MAX_DURATION = 180
LAST_CHECK_GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO = os.getenv('GITHUB_REPOSITORY', 'username/repo')

class CloudYouTubeTranscriptionBot:
    def __init__(self):
        self.whisper_model = None
        self.docs_service = None
        self.load_whisper_model()
        self.setup_google_docs()
        
    def load_whisper_model(self):
        """Load Whisper model for Hebrew transcription"""
        try:
            print("Loading Whisper model...")
            # Use 'tiny' model for faster processing in cloud environment
            self.whisper_model = whisper.load_model("tiny")
            print("Whisper model loaded successfully")
        except Exception as e:
            print(f"Error loading Whisper model: {e}")
    
    def setup_google_docs(self):
        """Setup Google Docs API service"""
        try:
            if not GOOGLE_CREDENTIALS_B64:
                print("Google credentials not found")
                return
            
            # Decode base64 credentials
            credentials_json = base64.b64decode(GOOGLE_CREDENTIALS_B64).decode('utf-8')
            credentials_dict = json.loads(credentials_json)
            
            # Setup credentials
            credentials = Credentials.from_service_account_info(
                credentials_dict,
                scopes=['https://www.googleapis.com/auth/documents']
            )
            
            self.docs_service = build('docs', 'v1', credentials=credentials)
            print("Google Docs API setup successful")
            
        except Exception as e:
            print(f"Error setting up Google Docs API: {e}")
    
    def get_last_check_time_from_github(self):
        """Get last check time from GitHub repository file"""
        if not LAST_CHECK_GITHUB_TOKEN:
            return datetime.now() - timedelta(days=1)
        
        try:
            headers = {
                'Authorization': f'token {LAST_CHECK_GITHUB_TOKEN}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/last_check.json"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(data['content']).decode('utf-8')
                timestamp_data = json.loads(content)
                return datetime.fromisoformat(timestamp_data['last_check'])
            
        except Exception as e:
            print(f"Error getting last check time: {e}")
        
        return datetime.now() - timedelta(days=1)
    
    def save_last_check_time_to_github(self):
        """Save last check time to GitHub repository"""
        if not LAST_CHECK_GITHUB_TOKEN:
            return
        
        try:
            headers = {
                'Authorization': f'token {LAST_CHECK_GITHUB_TOKEN}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            timestamp_data = {'last_check': datetime.now().isoformat()}
            content = base64.b64encode(json.dumps(timestamp_data).encode()).decode()
            
            # Check if file exists
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/last_check.json"
            response = requests.get(url, headers=headers)
            
            data = {
                'message': 'Update last check time',
                'content': content
            }
            
            if response.status_code == 200:
                # File exists, update it
                file_data = response.json()
                data['sha'] = file_data['sha']
                requests.put(url, headers=headers, json=data)
            else:
                # Create new file
                requests.put(url, headers=headers, json=data)
                
        except Exception as e:
            print(f"Error saving last check time: {e}")
    
    def get_recent_videos(self):
        """Get recent short videos from YouTube channel"""
        if not YOUTUBE_API_KEY:
            print("YouTube API key not found")
            return []
        
        last_check = self.get_last_check_time_from_github()
        
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
        """Check if video is under MAX_DURATION seconds"""
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
    
    def download_audio_to_temp(self, video_url):
        """Download audio to temporary file"""
        temp_dir = tempfile.mkdtemp()
        audio_path = os.path.join(temp_dir, 'audio')
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{audio_path}.%(ext)s',
            'quiet': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
                
            # Find downloaded file
            for ext in ['wav', 'mp3', 'm4a', 'webm', 'mp4']:
                audio_file = f"{audio_path}.{ext}"
                if os.path.exists(audio_file):
                    return audio_file
            
            return None
        except Exception as e:
            print(f"Error downloading audio: {e}")
            return None
    
    def transcribe_hebrew_audio(self, audio_file):
        """Transcribe Hebrew audio using Whisper"""
        try:
            # Transcribe with Hebrew language specified
            result = self.whisper_model.transcribe(
                audio_file,
                language="he",  # Hebrew language code
                task="transcribe"  # Just transcribe, don't translate
            )
            
            return result["text"].strip()
                
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return None
    
    def append_to_google_doc(self, video_info, hebrew_text):
        """Append transcription to Google Doc"""
        if not self.docs_service:
            print("Google Docs service not available")
            return False
        
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Limit text to ~500 words
            words = hebrew_text.split()
            if len(words) > 500:
                hebrew_text = ' '.join(words[:500]) + "..."
            
            # Format the content
            content = f"""
{'='*50}
תאריך: {timestamp}
כותרת הסרטון: {video_info['title']}
קישור: {video_info['url']}
תאריך פרסום: {video_info['published']}
{'='*50}
תמלול בעברית:
{hebrew_text}

"""
            
            # Get current document to append at the end
            document = self.docs_service.documents().get(documentId=GOOGLE_DOC_ID).execute()
            content_length = len(document.get('body').get('content'))
            
            # Insert text at the end
            requests_body = [{
                'insertText': {
                    'location': {
                        'index': content_length - 1  # Insert before last element
                    },
                    'text': content
                }
            }]
            
            self.docs_service.documents().batchUpdate(
                documentId=GOOGLE_DOC_ID,
                body={'requests': requests_body}
            ).execute()
            
            print(f"Successfully added transcription to Google Doc")
            return True
            
        except Exception as e:
            print(f"Error appending to Google Doc: {e}")
            return False
    
    def cleanup_temp_file(self, file_path):
        """Remove temporary file and its directory"""
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                # Remove the temp directory too
                temp_dir = os.path.dirname(file_path)
                os.rmdir(temp_dir)
        except:
            pass
    
    def process_new_videos(self):
        """Main processing function"""
        print(f"Checking for new Hebrew videos at {datetime.now()}")
        
        videos = self.get_recent_videos()
        if not videos:
            print("No new short videos found")
            self.save_last_check_time_to_github()  # Update timestamp even if no videos
            return
        
        print(f"Found {len(videos)} new short video(s)")
        
        for video in videos:
            print(f"Processing: {video['title']}")
            
            # Download audio to temp file
            audio_file = self.download_audio_to_temp(video['url'])
            if not audio_file:
                print(f"Failed to download audio for {video['title']}")
                continue
            
            # Transcribe Hebrew audio
            hebrew_text = self.transcribe_hebrew_audio(audio_file)
            if not hebrew_text:
                print(f"Failed to transcribe {video['title']}")
                self.cleanup_temp_file(audio_file)
                continue
            
            # Append to Google Doc
            success = self.append_to_google_doc(video, hebrew_text)
            if success:
                print(f"Successfully processed: {video['title']}")
            else:
                print(f"Failed to save transcription for: {video['title']}")
            
            # Cleanup temp file
            self.cleanup_temp_file(audio_file)
        
        # Update last check time
        self.save_last_check_time_to_github()
        print("Processing complete")

def main():
    """Main function to run the bot"""
    bot = CloudYouTubeTranscriptionBot()
    bot.process_new_videos()

if __name__ == "__main__":
    main()
