#!/usr/bin/python3
# -*- coding:utf-8 -*-
import os
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md"), 'r', encoding="utf-8") as readme:
	longdesc = readme.read()  #Good joke.


setup(
	name="rawutil",
	version="2.4.8",
	description="A single-file, pure-python package to deal with binary packed data",
	long_description = longdesc,
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
		"Programming Language :: Python :: 3.5",
		"Programming Language :: Python :: 3.6",
		"Programming Language :: Python :: 3.7",
		"Topic :: Utilities",
	],
	keywords = "structures struct binary bytes formats",
	py_modules = ["rawutil"],
	python_requires = ">=3.5",
)
