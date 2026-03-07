import subprocess
import random
import os
import json
import sys
import time
import re
import shutil
import threading


def main():
    app = App(config)
    app.run()


if __name__ == "__main__":
    main()