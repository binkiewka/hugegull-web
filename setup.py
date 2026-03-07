from setuptools import setup

from src.info import info

setup(
    name=info.name,
    version=info.version,
    package_dir={"": "src"},
    packages=[""],
    package_data={"": ["*.toml"]},
    entry_points={
        "console_scripts": [
            "hugegull = main:main",
        ],
    },
)