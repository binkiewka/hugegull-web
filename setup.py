import glob
from setuptools import setup

modules = []

for file_name in glob.glob("*.py"):
    if file_name != "setup.py":
        modules.append(file_name[:-3])

setup(
    name="hugegull",
    version="1.1.0",
    py_modules=modules,
    entry_points={
        "console_scripts": [
            "hugegull = main:main",
        ],
    },
)
