from setuptools import setup

from src.info import info

setup(
    name=info.name,
    version=info.version,
    package_dir={"": "src"},
    packages=[""],
    package_data={"": ["*.toml", "*.txt", "*.html", "*.css", "*.js"]},
    entry_points={
        "console_scripts": [
            "hugegull = main:main",
            "hugegull-web = webui:main",
            "hugegull-setup = setup_wizard:main",
        ],
    },
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "websockets>=12.0",
        "python-multipart>=0.0.6",
        "aiofiles>=23.2.1",
    ],
    extras_require={
        "web": ["fastapi>=0.104.0", "uvicorn[standard]>=0.24.0", "websockets>=12.0"],
    },
)