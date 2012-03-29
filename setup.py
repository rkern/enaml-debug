# Copyright (c) 2012 by Enthought, Inc.
# All rights reserved.

from setuptools import setup, find_packages

setup(
    name='enaml_debug',
    version='0.1',
    author='Enthought, Inc',
    author_email='info@enthought.com',
    url='https://github.com/enthought/enaml_debug',
    description="Debugging tool for Enaml's constraints-based layout.",
#    long_description=open('README.rst').read(),
    requires=['enaml', 'enable', 'PySide'],
    install_requires=['distribute'],
    packages=find_packages(),
    package_data={'enaml_debug': ['*.enaml']},
    entry_points = dict(
        console_scripts = [
            "enaml-debug = enaml_debug.debug_main:main",
        ],
    ),
)

