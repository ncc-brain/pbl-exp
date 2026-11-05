from importlib.metadata import version as _version

project = "pbl-exp"
author = "Qian Chu"
release = _version("pbl-exp")
version = ".".join(release.split(".")[:2])
html_title = f"Predictive Brain Lab Experiment Helpers v{version}"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "numpydoc",
]
autosummary_generate = True
numpydoc_show_class_members = True
templates_path = ["_templates"]

html_theme = "pydata_sphinx_theme"
html_theme_options = {
    "github_url": "https://github.com/ncc-brain/pbl-exp",
    "navbar_align": "right",
}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# pyglet swaps in mock GL libraries under Sphinx, which makes psychopy.visual segfault on import.
autodoc_mock_imports = ["psychopy"]
