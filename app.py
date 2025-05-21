from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from youtube_transcript_api.formatters import TextFormatter
import os
from flask_cors import CORS
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app) 

@app.route('/api/transcript', methods=['POST'])
def get_transcript():
    data = request.get_json()
    video_url = data.get('videoUrl')
    if not video_url:
        return jsonify({ "error": "Video URL is required" }), 400

    # Extract YouTube video ID
    if 'v=' in video_url:
        video_id = video_url.split('v=')[1].split('&')[0]
    elif 'youtu.be/' in video_url:
        video_id = video_url.split('youtu.be/')[1].split('?')[0]
    else:
        return jsonify({ "error": "Invalid YouTube URL" }), 400

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = transcript_list.find_transcript(['en'])  # prioritize English
        formatter = TextFormatter()
        text = formatter.format_transcript(transcript.fetch())
        return jsonify({ "transcript": text })

    except TranscriptsDisabled:
        return jsonify({ "error": "No transcripts available for this video" }), 404
    except Exception as e:
        return jsonify({ "error": "Failed to fetch transcript", "details": str(e) }), 500


@app.route('/api/summarize', methods=['POST'])
def summarize_transcript():
    data = request.get_json()
    transcript = data.get('transcript')
    if not transcript:
        return jsonify({ "error": "Transcript is required" }), 400

    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        return jsonify({ "error": "Missing Gemini API key" }), 500

    prompt_text = (
        "Please summarize the following YouTube video transcript.\n\n"
        "1. Provide a detailed summary paragraph.\n"
        "2. Provide 4-6 key takeaways as bullet points, starting with a heading 'Key Takeaways:'.\n\n"
        f"Transcript:\n{transcript}"
    )

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro:generateContent?key={gemini_api_key}",
        json={
            "contents": [{
                "parts": [{
                    "text": prompt_text
                }]
            }]
        },
        headers={ "Content-Type": "application/json" }
    )

    result = response.json()
    if response.status_code != 200:
        return jsonify({ "error": "Gemini API failed", "details": result }), 500

    raw_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()

    # Split on "Key Takeaways:" heading to separate summary and takeaways
    parts = raw_text.split("Key Takeaways:")
    summary = parts[0].strip()
    key_takeaways = parts[1].strip() if len(parts) > 1 else "No key takeaways found."

    return jsonify({
        "summary": summary,
        "keyTakeaways": key_takeaways
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=5000, debug=True)
