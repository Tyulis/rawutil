#!/usr/bin/python3
# -*- coding:utf-8 -*-
import os
import rawutil
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md"), 'r', encoding="utf-8") as readme:
	longdesc = readme.read()  # Nice.


setup(
	name="rawutil",
	version=rawutil.__version__,
	description="A pure-python module to read and write binary data",
	long_description = longdesc,
	long_description_content_type="text/markdown",
	url="https://github.com/Tyulis/rawutil",
	author="Tyulis",
	author_email="tyulis@laposte.net",
	license="MIT",
	packages=[],
	zip_safe=False,
	classifiers = [
		"Development Status :: 4 - Beta",
		"Intended Audience :: Developers",
		"License :: OSI Approved :: MIT License",
		"Programming Language :: Python :: 3 :: Only",
		"Programming Language :: Python :: 3.4",
		"Programming Language :: Python :: 3.5",
		"Programming Language :: Python :: 3.6",
		"Programming Language :: Python :: 3.7",
		"Programming Language :: Python :: 3.8",
		"Programming Language :: Python :: 3.9",
		"Programming Language :: Python :: 3.10",
		"Topic :: Utilities",
		"Operating System :: OS Independent",
	],
	keywords = "structures struct binary bytes formats",
	py_modules = ["rawutil"],
	python_requires = ">=3.4",
)
