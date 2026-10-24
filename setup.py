from setuptools import setup, find_packages

setup(
    name="minimalist-drawing",
    version="1.0.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    package_data={"minimalist_drawing": ["assets/*"]},
    entry_points={
        "gui_scripts": [
            "minimalist-drawing = minimalist_drawing.app:main",
        ],
        "console_scripts": [
            "minimalist-drawing = minimalist_drawing.app:main",
        ],
    },
    install_requires=[
        "PyQt6>=6.5.0",
    ],
)
