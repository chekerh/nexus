import argparse
import sys
import os

# Ensure backend modules are importable
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.transcriber import transcribe_video
from app.core.analyst import analyze_transcript

def main():
    parser = argparse.ArgumentParser(description="Nexus-UGC Pipeline Test")
    parser.add_argument("--file", required=True, help="Path to the video file to process")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File {args.file} not found.")
        sys.exit(1)

    print(f"--- Starting Pipeline for: {args.file} ---")
    
    print("[1/2] Step: Transcription (Whisper.cpp)...")
    transcript = transcribe_video(args.file)
    if not transcript:
        print("Critical Error: Transcription failed.")
        sys.exit(1)
        
    print(f"\n[TRANSCRIPT EXTRACT]\n{transcript[:200]}...\n")

    print("[2/2] Step: Viral Analysis (Ollama)...")
    analysis = analyze_transcript(transcript, args.file)
    if not analysis:
        print("Critical Error: AI Analysis failed.")
        sys.exit(1)

    print("\n--- STRATEGIC ANALYSIS RESULTS ---")
    print(analysis)
    print("----------------------------------\n")

if __name__ == "__main__":
    main()
