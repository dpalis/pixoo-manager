"""
py2app setup for Pixoo Manager.

Build with: python setup.py py2app
"""

from setuptools import setup

from app.__version__ import __version__

APP = ["app/main.py"]
DATA_FILES = [
    ("templates", ["app/templates/base.html"]),
    ("static", ["app/static/favicon.ico"]),
    ("static/css", ["app/static/css/styles.css"]),
    ("static/js", ["app/static/js/app.js"]),
    ("static/vendor", [
        "app/static/vendor/alpine.min.js",
        "app/static/vendor/pico.min.css",
        "app/static/vendor/cropper.min.js",
        "app/static/vendor/cropper.min.css",
    ]),
]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "resources/Pixoo.icns",
    "plist": {
        "CFBundleName": "Pixoo",
        "CFBundleDisplayName": "Pixoo",
        "CFBundleIdentifier": "com.pixoo.manager",
        "CFBundleVersion": __version__,
        "CFBundleShortVersionString": __version__,
        "LSMinimumSystemVersion": "10.15",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.utilities",
    },
    "packages": [
        "uvicorn",
        "fastapi",
        "starlette",
        "PIL",
        "moviepy",
        "yt_dlp",
        "zeroconf",
        "rumps",
        "anyio",
        "jinja2",
        "pydantic",
        "scipy",
        "charset_normalizer",
        "imageio",
        "numpy",
        "aiofiles",
        "httptools",
        "app",
    ],
    "excludes": [
        "tkinter",
        "matplotlib",
        "pandas",
        "PyInstaller",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "wx",
        "pytest",
        "nose",
        "IPython",
        "jupyter",
        "notebook",
    ],
}

setup(
    app=APP,
    name="Pixoo",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
