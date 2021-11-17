from setuptools import setup, find_packages

pkgs = find_packages('src')

setup_kwds = dict(
    name='routeservice',
    version="0.0.1",
    zip_safe=False,
    packages=pkgs,
    package_dir={'': 'src'},
    entry_points={},
    )

setup(**setup_kwds)
