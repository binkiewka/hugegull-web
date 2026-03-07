log = Log()

class Engine:
    def get_stream_duration(url):
        command = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", url,
        ]

        result = run_cancellable_command(command)

        if abort_event.is_set():
            return 0.0

        if result.returncode != 0:
            return 0.0

        metadata = json.loads(result.stdout)

        if "format" in metadata:
            if "duration" in metadata["format"]:
                return float(metadata["format"]["duration"])

        return 0.0

    def generate_clip_sections(target_duration, total_stream_duration):
        sections = []
        current_sum = 0.0

        end_buffer = 2.0
        safe_duration = total_stream_duration - end_buffer

        while current_sum < target_duration:
            clip_length = random.triangular(
                MIN_CLIP_DURATION, MAX_CLIP_DURATION, AVG_CLIP_DURATION
            )

            if current_sum + clip_length > target_duration:
                clip_length = target_duration - current_sum

                if clip_length < MIN_CLIP_DURATION:
                    clip_length = MIN_CLIP_DURATION

            max_start = safe_duration - clip_length

            if max_start <= 0:
                break

            start_time = random.uniform(0, max_start)
            sections.append({"start": start_time, "duration": clip_length})

            current_sum += clip_length

        return sections


    def generate_random_clips(stream_data, total_duration, run_temp_dir):
        clip_files = []
        sections = generate_clip_sections(DURATION, total_duration)
        total_sections = len(sections)

        log.add(f"Targeting {total_sections} random clips for this run...", "class:info")

        is_split_stream = False

        if isinstance(stream_data, dict):
            if stream_data.get("audio") is not None:
                is_split_stream = True

        v_url = stream_data

        if isinstance(stream_data, dict):
            v_url = stream_data["video"]

        for i in range(total_sections):
            if abort_event.is_set():
                log.add("Clip generation aborted.", "class:error")
                break

            section = sections[i]
            start_time = section["start"]
            current_clip_duration = section["duration"]

            output_name = os.path.join(run_temp_dir, f"temp_clip_{i + 1}.mp4")
            command = ["ffmpeg", "-ss", str(start_time), "-i", v_url]

            if is_split_stream:
                command.extend(["-ss", str(start_time), "-i", stream_data["audio"]])

            command.extend(
                [
                    "-t", str(current_clip_duration),
                    "-vf", f"fps={FPS}",
                    "-c:v", "libx264",
                    "-crf", str(CRF),
                    "-c:a", "aac",
                    "-video_track_timescale", "90000",
                    "-y", output_name,
                ]
            )

            log.add(f"Extracting clip {i + 1}/{total_sections} starting at {start_time:.2f}s (Duration: {current_clip_duration:.2f}s)...", "class:warning")

            result = run_cancellable_command(command)

            if abort_event.is_set():
                break

            if result.returncode != 0:
                log.add(f"Error extracting clip {i}:", "class:error")
                log.add(result.stderr, "class:error")
                continue

            clip_files.append(output_name)

        return clip_files


    def concatenate_clips(clip_files, output_file, run_temp_dir):
        if abort_event.is_set():
            return

        if not clip_files:
            log.add("No clips to concatenate.", "class:error")
            return

        list_file = os.path.join(run_temp_dir, "concat_list.txt")

        with open(list_file, "w") as f:
            for clip in clip_files:
                abs_clip_path = os.path.abspath(clip)
                f.write(f"file '{abs_clip_path}'\n")

        command = [
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            "-video_track_timescale", "90000",
            "-y", output_file,
        ]

        log.add("Concatenating clips...", "class:info")
        result = run_cancellable_command(command)

        if abort_event.is_set():
            log.add("Concatenation aborted.", "class:error")
            return

        if result.returncode != 0:
            log.add("Error concatenating clips:", "class:error")
            log.add(result.stderr, "class:error")
        else:
            log.add("Cleaning up temporary files...", "class:info")
            shutil.rmtree(run_temp_dir, ignore_errors=True)
            log.add(f"Video saved as {output_file}", "class:success")


    def run_pipeline(stream_url):
        abort_event.clear()
        base_name = get_random_name()
        run_id = str(int(time.time() * 1000))
        run_temp_dir = os.path.join(TEMP_DIR, f"project_{run_id}")

        os.makedirs(run_temp_dir, exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        output_file = os.path.join(OUTPUT_DIR, f"{base_name}.mp4")
        counter = 1

        while os.path.exists(output_file):
            output_file = os.path.join(OUTPUT_DIR, f"{base_name}_{counter}.mp4")
            counter += 1

        log.add("Fetching stream duration...", "class:info")
        total_duration = 0.0

        if requires_ytdlp(stream_url):
            stream_url, total_duration = resolve_with_ytdlp(stream_url)
        else:
            total_duration = get_stream_duration(stream_url)

        if abort_event.is_set():
            log.add("Process aborted during duration fetch.", "class:error")
            shutil.rmtree(run_temp_dir, ignore_errors=True)
            return

        if total_duration <= 0:
            log.add("Could not determine stream duration or stream is live/endless.", "class:error")
            shutil.rmtree(run_temp_dir, ignore_errors=True)
            return

        log.add(f"Stream duration: {total_duration} seconds.", "class:success")

        clips = generate_random_clips(stream_url, total_duration, run_temp_dir)
        concatenate_clips(clips, output_file, run_temp_dir)
        notify_done()