from setuptools import setup

# encoding is explicit on purpose: without it Python uses the locale default,
# which is cp1252 on Windows. README.md is UTF-8, so any character above ASCII
# would be decoded wrong and carried into long_description - and from there
# into PKG-INFO and the rendered PyPI page.
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="QBMP",
    version="0.0.2",
    description="Declarative synthetic dataset generation through mathematical modelling",
    packages=["QBMP"],
    package_dir={"": "SRCS"},
    long_description=long_description,
    long_description_content_type="text/markdown",
    # An SPDX identifier (PEP 639), and the only place the licence is declared.
    # Do NOT add a "License :: OSI Approved :: ..." classifier alongside it -
    # setuptools >= 77 deprecates those and warns on every build.
    #
    # This emits the legacy `License:` metadata field, not `License-Expression:`.
    # The setup() kwarg that emits the modern field is `license_expression=`, but
    # it only exists in setuptools >= 77: on anything older it is an unknown
    # option that is warned about and dropped, leaving the sdist with NO licence
    # metadata at all. Moving to pyproject.toml with a pinned
    # `requires = ["setuptools>=77"]` is the way to get the modern field safely.
    license="GPL-3.0-or-later",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering",
        "Topic :: Software Development :: Testing",
    ],
    keywords=[
        "synthetic-data",
        "dataset-generation",
        "sampling",
        "test-data",
        "coverage"
    ],
    url="https://github.com/Palani-SN/QBMP",
    author="Palani-SN",
    author_email="psn396@gmail.com",
    python_requires=">=3.11",

    install_requires=[
        "pandas>=3.0.5",
        "openpyxl>=3.1.5"
    ],
    extras_require={
        "dev": [
            "pytest >= 3.7",
            "check-manifest",
            "twine",
        ],
    },
)
