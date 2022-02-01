"""setup for matterhorn."""

from distutils.core import setup

# import needed to patch `setup`. Otherwise, install_requires is unknown.
import setuptools  # noqa

setup(
    name="phd_flow",
    version="0.1",
    author="Leon Sixt",
    author_email="",
    packages=["phd_flow"],
    package_data={
        "phd_flow": ["py.typed"],
    },
    install_requires=[
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
        "pytest",
        "pytest-cov",
        "python-lsp-server[all]",
        "sklearn",
        "tqdm",
        "typed-argument-parser",
        "wandb",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [],
    },
)
