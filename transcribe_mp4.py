import whisper
import os
import sys
import subprocess
from pyannote.audio import Pipeline

def extract_audio(mp4_path, wav_path):
    command = [
        "ffmpeg", "-y", "-i", mp4_path,
        "-ac", "1", "-ar", "16000", wav_path
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def diarize_audio(audio_path):
    # Requires HuggingFace access token: https://huggingface.co/pyannote/speaker-diarization
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization",
                                        use_auth_token="YOUR_HF_TOKEN")
    diarization = pipeline(audio_path)
    return diarization

def transcribe_with_speakers(audio_path):
    model = whisper.load_model("base")
    diarization = diarize_audio(audio_path)

    transcript = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        # Extract segment for this speaker
        segment = {"start": turn.start, "end": turn.end}
        audio = whisper.load_audio(audio_path)
        clip = whisper.pad_or_trim(audio[int(turn.start*16000):int(turn.end*16000)])
        mel = whisper.log_mel_spectrogram(clip).to(model.device)
        options = whisper.DecodingOptions()
        result = whisper.decode(model, mel, options)

        transcript.append(f"[{segment['start']:.2f}-{segment['end']:.2f}] {speaker}: {result.text}")

    return "\n".join(transcript)

def main(mp4_file):
    if not os.path.exists(mp4_file):
        print("File does not exist:", mp4_file)
        return

    wav_file = "temp_audio.wav"
    print(f"Extracting audio from: {mp4_file}")
    extract_audio(mp4_file, wav_file)

    print("Diarizing and transcribing...")
    transcript = transcribe_with_speakers(wav_file)

    os.remove(wav_file)

    txt_file = os.path.splitext(mp4_file)[0] + "_transcript.txt"
    with open(txt_file, "w") as f:
        f.write(transcript)
    
    print("Transcription complete. Saved to:", txt_file)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transcribe_mp4.py <file.mp4>")
    else:
        main(sys.argv[1])




'''import whisper
import os
import sys
import subprocess

def extract_audio(mp4_path, wav_path):
    command = [
        "ffmpeg", "-y", "-i", mp4_path,
        "-ac", "1", "-ar", "16000", wav_path
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def transcribe_audio(audio_path):
    model = whisper.load_model("base")  # Options: tiny, base, small, medium, large
    result = model.transcribe(audio_path)
    return result['text']

def main(mp4_file):
    if not os.path.exists(mp4_file):
        print("File does not exist:", mp4_file)
        return

    wav_file = "temp_audio.wav"
    print(f"Extracting audio from: {mp4_file}")
    extract_audio(mp4_file, wav_file)

    print("Transcribing...")
    transcript = transcribe_audio(wav_file)

    # Clean up
    os.remove(wav_file)

    # Save transcript
    txt_file = os.path.splitext(mp4_file)[0] + "_transcript.txt"
    with open(txt_file, "w") as f:
        f.write(transcript)
    
    print("Transcription complete. Saved to:", txt_file)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transcribe_mp4.py <file.mp4>")
    else:
        main(sys.argv[1])'''
