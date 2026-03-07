class Proc:
    abort_event = threading.Event()
    active_process = None
    process_lock = threading.Lock()

    class CommandResult:
        def __init__(self, returncode, stdout, stderr):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def run_cancellable_command(command):
        global active_process

        if abort_event.is_set():
            return CommandResult(-1, "", "Aborted by user.")

        with process_lock:
            try:
                active_process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            except Exception as e:
                return CommandResult(-1, "", str(e))

        stdout, stderr = active_process.communicate()
        returncode = active_process.returncode

        with process_lock:
            active_process = None

        return CommandResult(returncode, stdout, stderr)