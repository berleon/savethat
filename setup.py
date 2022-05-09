"""setup for matterhorn."""

from distutils.core import setup

# import needed to patch `setup`. Otherwise, install_requires is unknown.
import setuptools  # noqa

setup(
    name="savethat",
    version="0.1",
    author="Leon Sixt",
    author_email="",
    packages=["savethat"],
    package_data={
        "savethat": ["py.typed"],
    },
    install_requires=[
        "anyconfig",
        "GPUtil",
        "b2",
        "b2sdk",
        "black",
        "dill",
        "flake8",
        "ipykernel",
        "ipywidgets",
        "isort",
        "loguru",
        "matplotlib",
        "mypy",
        "numpy",
        "pandas",
        "reproducible",
        "pdoc",
        "pytest",
        "pytest-cov",
        "python-lsp-server[all]",
        "sklearn",
        "types-toml",
        "tqdm",
        "typed-argument-parser",
        "wandb",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [],
    },
)
