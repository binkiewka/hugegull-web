import subprocess
import random
import os
import json
import sys

CLIP_DURATION = 6
NUM_CLIPS = 10

def get_stream_duration(url):
    command = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        url,
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        return 0.0

    metadata = json.loads(result.stdout)

    if "format" in metadata:
        if "duration" in metadata["format"]:
            return float(metadata["format"]["duration"])

    return 0.0

def generate_random_clips(url, total_duration, num_clips, clip_duration):
    clip_files = []
    max_start = total_duration - clip_duration

    if max_start <= 0:
        print("Stream is too short.")
        return []

    for i in range(num_clips):
        start_time = random.uniform(0, max_start)
        output_name = os.path.join("temp", f"temp_clip_{i}.mp4")

        command = [
            "ffmpeg",
            "-ss", str(start_time),
            "-i", url,
            "-t", str(clip_duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-y",
            output_name,
        ]

        print(f"Extracting clip {i + 1}/{num_clips} starting at {start_time:.2f}s...")
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clip_files.append(output_name)

    return clip_files

def concatenate_clips(clip_files, output_file):
    if not clip_files:
        print("No clips to concatenate.")
        return

    list_file = os.path.join("temp", "concat_list.txt")

    with open(list_file, "w") as f:
        for clip in clip_files:
            # Paths in the concat file are relative to the concat file's location
            clip_basename = os.path.basename(clip)
            f.write(f"file '{clip_basename}'\n")

    command = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        "-y",
        output_file,
    ]

    print("Concatenating clips...")
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Cleaning up temporary files...")

    for clip in clip_files:
        os.remove(clip)

    os.remove(list_file)
    print(f"Video saved as {output_file}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python script.py <m3u8_url> <output_name_without_ext>")
        sys.exit(1)

    os.makedirs("temp", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    stream_url = sys.argv[1]
    base_name = sys.argv[2]
    output_file = os.path.join("output", f"{base_name}.mp4")
    counter = 1

    while os.path.exists(output_file):
        output_file = os.path.join("output", f"{base_name} ({counter}).mp4")
        counter += 1

    print("Fetching stream duration...")
    total_duration = get_stream_duration(stream_url)

    if total_duration <= 0:
        print("Could not determine stream duration or stream is live/endless.")
        return

    print(f"Stream duration: {total_duration} seconds.")
    clips = generate_random_clips(stream_url, total_duration, NUM_CLIPS, CLIP_DURATION)
    concatenate_clips(clips, output_file)

if __name__ == "__main__":
    main()