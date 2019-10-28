#!/usr/bin/env python

from setuptools import find_packages, setup

setup(
    name="gitlab-mr",
    python_requires=">=3.7",
    version="0.0.1",
    description="Utils to ease work at review on gitlab",
    author="Alex Shalynin",
    py_modules=["gitlab_mr"],
    packages=find_packages(exclude=("tests/*",)),
    install_requires=[
        "click>=7.0,<8",
        "python-gitlab>=1.12.1,<1.13",
        "arrow>=0.15.2,<0.16",
    ],
    entry_points={"console_scripts": ["gitlab-mr=gitlab_mr.__main__:cli"]},
    zip_safe=False,
)
