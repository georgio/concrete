# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))
from sphinx.builders.html import StandaloneHTMLBuilder
import subprocess
import os

# Doxygen
subprocess.call('doxygen Doxyfile.in', shell=True)

# -- Project information -----------------------------------------------------

project = 'Concrete Compiler'
copyright = '2021, Zama'
author = 'Zama'
description = 'Concrete Compiler is part of Zama Concrete Framework that help you turn any program into its homomorphic equivalent.'
root_url = os.environ.get("DOC_ROOT_URL", "/concrete-compiler")
root_url = root_url if root_url.endswith('/') else root_url + '/'

# The full version, including alpha/beta/rc tags
release = 'v0.1.1'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'myst_parser',
    'sphinx_copybutton',
    'breathe',
    'sphinx.ext.autodoc',
]

myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "dollarmath",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'pydata_sphinx_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
html_css_files = ['css/custom.css']
html_favicon = '_static/favicon.ico'
html_theme_options = {
    "github_url": "https://github.com/zama-ai/concrete-compiler-internal",
    "twitter_url": "https://twitter.com/zama_fhe",
    "icon_links": [{
        "name": "Discourse",
        "url": "https://community.zama.ai/",
        "icon": "fab fa-discourse",
    }],
    "navigation_depth": 2,
    "collapse_navigation": False,
}
html_context = {
    "show_version": True,
    "author": author,
    "description": description,
    "language": "en",
    "versions_url": "#",
}
html_title = "%s Manual" % (project)

# Uncomment for test
# html_extra_path = ["versions.json", "alert.html"]


def setup(app):
    html_init = f"const CURRENT_VERSION = {release!r};"
    html_init += f"const ROOT_URL = {root_url!r};"
    app.add_js_file(None, body=html_init, priority=100)
    app.add_js_file("custom.js")

# -- Breathe configuration -------------------------------------------------


breathe_projects = {
    "C++ Sphinx Doxygen Breathe": "_build/xml/"
}
breathe_default_project = "C++ Sphinx Doxygen Breathe"
breathe_default_members = ('members', 'undoc-members')
