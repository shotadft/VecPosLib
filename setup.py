"""パッケージセットアップスクリプト"""

import os
from setuptools import setup, find_packages

exclude_patterns = [
    "tests*",
    "venv*",
    "build*",
    "dist*",
    "*.egg-info*",
    ".vscode*",
    "__pycache__*",
    ".mypy_cache*",
    ".pytest_cache*",
    ".coverage*",
    ".tox*",
    ".nox*",
    "htmlcov*",
    ".hypothesis*",
    ".cache*",
    ".ipynb_checkpoints*",
    ".python-version*",
    ".dmypy.json*",
    "Thumbs.db*",
    "Desktop.ini*",
    "*.env*",
    "*.local*",
]

if os.path.exists("README.md"):
    with open("README.md", encoding="utf-8") as f:
        LONG_DESCRIPTION = f.read()
else:
    LONG_DESCRIPTION = ""

setup(
    name="VecPosLib",
    version="1.0.4",
    description="This is a library that enables vector calculations in Python.",
    author="Shotadft",
    author_email="98450322+shotadft@users.noreply.github.com",
    url="https://github.com/shotadft/VecPosLib",
    packages=find_packages(where="package", exclude=exclude_patterns),
    package_data={
        "package": ["py.typed"],
    },
    include_package_data=True,
    install_requires=["numpy>=2.2.0,<2.4", "numba>=0.61.2"],
    extras_require={
        "cupy": ["cupy>=10.0"],
    },
    python_requires=">=3.13",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Libraries",
        "Natural Language :: Japanese",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Typing :: Typed",
        "Programming Language :: Python :: 3.13",
    ],
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
)
