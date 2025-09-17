#!/usr/bin/env python3
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
        self.cookies_file = None
        self.setup_cookies()
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
    
    def setup_cookies(self):
        """Setup cookies for YouTube authentication"""
        cookies_file = None
        
        try:
            # Method 1: Use browser cookies if specified
            browser = os.getenv('YOUTUBE_COOKIES_BROWSER')
            if browser:
                try:
                    import browser_cookie3
                    if browser.lower() == 'chrome':
                        cookies = browser_cookie3.chrome(domain_name='youtube.com')
                    elif browser.lower() == 'firefox':
                        cookies = browser_cookie3.firefox(domain_name='youtube.com')
                    else:
                        cookies = browser_cookie3.load(domain_name='youtube.com')
                    
                    # Save cookies to file
                    cookies_file = 'youtube_cookies.txt'
                    with open(cookies_file, 'w') as f:
                        f.write("# Netscape HTTP Cookie File\n")
                        for cookie in cookies:
                            if 'youtube.com' in cookie.domain:
                                f.write(f"{cookie.domain}\tTRUE\t{cookie.path}\t{'TRUE' if cookie.secure else 'FALSE'}\t{int(cookie.expires) if cookie.expires else 0}\t{cookie.name}\t{cookie.value}\n")
                    
                    print("Browser cookies loaded successfully")
                    return cookies_file
                    
                except ImportError:
                    print("browser_cookie3 not available, trying alternative methods")
                except Exception as e:
                    print(f"Browser cookie extraction failed: {e}")
            
            # Method 2: Use base64 encoded cookies file
            cookies_b64 = os.getenv('YOUTUBE_COOKIES_B64')
            if cookies_b64:
                try:
                    import base64
                    cookies_content = base64.b64decode(cookies_b64).decode('utf-8')
                    cookies_file = 'youtube_cookies.txt'
                    with open(cookies_file, 'w') as f:
                        f.write(cookies_content)
                    print("Base64 cookies loaded successfully")
                    return cookies_file
                except Exception as e:
                    print(f"Base64 cookie loading failed: {e}")
            
            # Method 3: Check if cookies.txt exists in current directory
            if os.path.exists('cookies.txt'):
                print("Found existing cookies.txt file")
                return 'cookies.txt'
                
        except Exception as e:
            print(f"Cookie setup error: {e}")
        
        return None
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
    
    def get_recent_videos(self, force_date=None):
        """Get recent short videos from YouTube channel"""
        if not YOUTUBE_API_KEY:
            print("YouTube API key not found")
            return []
        
        # Allow manual override of check date for retrying failed videos
        if force_date:
            last_check = force_date
            print(f"Forced check date: {last_check}")
        else:
            last_check = self.get_last_check_time_from_github()
            print(f"Last check time: {last_check}")
        
        url = f"https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'channelId': CHANNEL_ID,
            'publishedAfter': last_check.isoformat() + 'Z',
            'order': 'date',
            'type': 'video',
            'maxResults': 50,  # Increased to catch more videos
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
        """Download audio to temporary file with anti-bot measures"""
        temp_dir = tempfile.mkdtemp()
        audio_path = os.path.join(temp_dir, 'audio')
        
        # Enhanced yt-dlp options to avoid bot detection
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{audio_path}.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'wav',
            # Anti-bot detection measures
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            'sleep_interval': 1,
            'max_sleep_interval': 5,
            # Add headers to appear more like a regular browser
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip,deflate',
                'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
                'Keep-Alive': '300',
                'Connection': 'keep-alive',
            }
        }
        
        # Add cookies if available
        if self.cookies_file and os.path.exists(self.cookies_file):
            ydl_opts['cookiefile'] = self.cookies_file
            print(f"Using cookies file: {self.cookies_file}")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Try multiple approaches
                success = False
                
                # Method 1: Standard download
                try:
                    ydl.download([video_url])
                    success = True
                except Exception as e1:
                    print(f"Standard download failed: {e1}")
                    
                    # Method 2: Try with different format selection
                    try:
                        ydl_opts['format'] = 'worst[ext=mp4]/worst'
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                            ydl2.download([video_url])
                            success = True
                    except Exception as e2:
                        print(f"Alternative format failed: {e2}")
                        
                        # Method 3: Use mobile user agent
                        try:
                            ydl_opts['user_agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl3:
                                ydl3.download([video_url])
                                success = True
                        except Exception as e3:
                            print(f"Mobile user agent failed: {e3}")
                
                if not success:
                    print("All download methods failed, trying alternative approach...")
                    return self.download_via_api_alternative(video_url, temp_dir)
                
            # Find downloaded file
            for ext in ['wav', 'mp3', 'm4a', 'webm', 'mp4']:
                audio_file = f"{audio_path}.{ext}"
                if os.path.exists(audio_file):
                    return audio_file
            
            return None
            
        except Exception as e:
            print(f"Error downloading audio: {e}")
            return self.download_via_api_alternative(video_url, temp_dir)
    
    def download_via_api_alternative(self, video_url, temp_dir):
        """Alternative download method using third-party services"""
        try:
            # Extract video ID from URL
            video_id = video_url.split('v=')[1].split('&')[0] if 'v=' in video_url else video_url.split('/')[-1]
            
            # Method 1: Try using a free online converter API
            # Note: This is a fallback method, may not always work
            api_urls = [
                f"https://api.vevioz.com/api/button/mp3/{video_id}",
                f"https://youtube-mp36.p.rapidapi.com/dl?id={video_id}",
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            for api_url in api_urls:
                try:
                    response = requests.get(api_url, headers=headers, timeout=30)
                    if response.status_code == 200:
                        data = response.json()
                        if 'link' in data:
                            # Download the audio file
                            audio_response = requests.get(data['link'], headers=headers, timeout=60)
                            if audio_response.status_code == 200:
                                audio_file = os.path.join(temp_dir, f"audio_{video_id}.mp3")
                                with open(audio_file, 'wb') as f:
                                    f.write(audio_response.content)
                                return audio_file
                except:
                    continue
            
            print("All alternative download methods failed")
            return None
            
        except Exception as e:
            print(f"Alternative download error: {e}")
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
    
    def save_processed_videos_to_github(self, processed_video_ids):
        """Save list of successfully processed video IDs to avoid reprocessing"""
        try:
            headers = {
                'Authorization': f'token {LAST_CHECK_GITHUB_TOKEN}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            processed_data = {'processed_videos': processed_video_ids}
            content = base64.b64encode(json.dumps(processed_data).encode()).decode()
            
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/processed_videos.json"
            response = requests.get(url, headers=headers)
            
            data = {
                'message': 'Update processed videos list',
                'content': content
            }
            
            if response.status_code == 200:
                file_data = response.json()
                data['sha'] = file_data['sha']
                requests.put(url, headers=headers, json=data)
            else:
                requests.put(url, headers=headers, json=data)
                
        except Exception as e:
            print(f"Error saving processed videos: {e}")
    
    def get_processed_videos_from_github(self):
        """Get list of already processed video IDs"""
        if not LAST_CHECK_GITHUB_TOKEN:
            return set()
        
        try:
            headers = {
                'Authorization': f'token {LAST_CHECK_GITHUB_TOKEN}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/processed_videos.json"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(data['content']).decode('utf-8')
                processed_data = json.loads(content)
                return set(processed_data.get('processed_videos', []))
            
        except Exception as e:
            print(f"Error getting processed videos: {e}")
        
        return set()

    def process_new_videos(self):
        """Main processing function with retry logic for failed videos"""
        print(f"Checking for new Hebrew videos at {datetime.now()}")
        
        # Get processed video IDs to avoid reprocessing
        processed_video_ids = self.get_processed_videos_from_github()
        print(f"✅ Already processed {len(processed_video_ids)} videos")
        
        videos = self.get_recent_videos()
        if not videos:
            print("No new short videos found")
            # Only update timestamp if we successfully checked (don't skip failed videos)
            self.save_last_check_time_to_github()
            return
        
        print(f"✅ Found {len(videos)} video(s) from recent check")
        
        # Filter out already processed videos
        unprocessed_videos = [v for v in videos if v['id'] not in processed_video_ids]
        if not unprocessed_videos:
            print("All recent videos have already been processed")
            self.save_last_check_time_to_github()
            return
        
        print(f"✅ Found {len(unprocessed_videos)} new video(s) to process")
        
        successfully_processed = list(processed_video_ids)  # Start with existing processed IDs
        total_attempts = 0
        successful_attempts = 0
        
        for video in unprocessed_videos:
            total_attempts += 1
            print(f"Processing ({total_attempts}/{len(unprocessed_videos)}): {video['title']}")
            
            # Download audio to temp file
            audio_file = self.download_audio_to_temp(video['url'])
            if not audio_file:
                print(f"Failed to download audio for {video['title']} - will retry on next run")
                continue
            
            # Transcribe Hebrew audio
            hebrew_text = self.transcribe_hebrew_audio(audio_file)
            if not hebrew_text:
                print(f"Failed to transcribe {video['title']} - will retry on next run")
                self.cleanup_temp_file(audio_file)
                continue
            
            # Append to Google Doc
            success = self.append_to_google_doc(video, hebrew_text)
            if success:
                print(f"✅ Successfully processed: {video['title']}")
                successfully_processed.append(video['id'])
                successful_attempts += 1
            else:
                print(f"❌ Failed to save transcription for: {video['title']} - will retry on next run")
            
            # Cleanup temp file
            self.cleanup_temp_file(audio_file)
        
        # Save the updated list of processed videos
        self.save_processed_videos_to_github(successfully_processed)
        
        # Only update last check time if we had some success OR if we successfully processed all attempts
        if successful_attempts > 0:
            print(f"✅ Successfully processed {successful_attempts}/{total_attempts} videos")
            self.save_last_check_time_to_github()
        elif total_attempts == 0:
            # No videos to process, safe to update timestamp
            self.save_last_check_time_to_github()
        else:
            # Some failures occurred, don't update timestamp so we retry failed videos next time
            print(f"⚠️ {total_attempts - successful_attempts} videos failed - will retry on next run")
            print("Not updating last check time to ensure failed videos are retried")
        
        print("Processing complete")

    def retry_failed_videos(self, days_back=7):
        """Retry processing videos from the last N days"""
        print(f"Retrying failed videos from the last {days_back} days")
        
        # Get videos from the last N days
        retry_date = datetime.now() - timedelta(days=days_back)
        videos = self.get_recent_videos(force_date=retry_date)
        
        if not videos:
            print("No videos found in the retry period")
            return
        
        # Process all videos (including previously failed ones)
        processed_video_ids = self.get_processed_videos_from_github()
        unprocessed_videos = [v for v in videos if v['id'] not in processed_video_ids]
        
        if not unprocessed_videos:
            print("All videos from retry period have already been processed successfully")
            return
        
        print(f"Retrying {len(unprocessed_videos)} previously failed video(s)")
        
        successfully_processed = list(processed_video_ids)
        successful_retries = 0
        
        for video in unprocessed_videos:
            print(f"Retrying: {video['title']}")
            
            # Download and process
            audio_file = self.download_audio_to_temp(video['url'])
            if not audio_file:
                print(f"Retry failed - could not download: {video['title']}")
                continue
            
            hebrew_text = self.transcribe_hebrew_audio(audio_file)
            if not hebrew_text:
                print(f"Retry failed - could not transcribe: {video['title']}")
                self.cleanup_temp_file(audio_file)
                continue
            
            success = self.append_to_google_doc(video, hebrew_text)
            if success:
                print(f"✅ Retry successful: {video['title']}")
                successfully_processed.append(video['id'])
                successful_retries += 1
            else:
                print(f"❌ Retry failed - could not save: {video['title']}")
            
            self.cleanup_temp_file(audio_file)
        
        # Update processed videos list
        if successful_retries > 0:
            self.save_processed_videos_to_github(successfully_processed)
            print(f"✅ Successfully retried {successful_retries} video(s)")
        else:
            print("❌ No videos were successfully retried")

def main():
    """Main function to run the bot"""
    import sys
    
    bot = CloudYouTubeTranscriptionBot()
    
    # Check for retry mode
    if len(sys.argv) > 1:
        if sys.argv[1] == "retry":
            # Retry failed videos from last 7 days
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            bot.retry_failed_videos(days_back=days)
        elif sys.argv[1] == "reset":
            # Reset last check time to retry from beginning
            reset_date = datetime.now() - timedelta(days=30)
            print(f"Resetting last check time to {reset_date}")
            bot.save_last_check_time_to_github()
        else:
            bot.process_new_videos()
    else:
        # Normal processing
        bot.process_new_videos()

if __name__ == "__main__":
    main()
