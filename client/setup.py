from setuptools import setup, find_packages
import os

# Search for BUILD_NUMBER environment var. If not found use dev to replace build nbr
build_nbr = os.getenv('BUILD_NUMBER', 'dev')

setup(name='tntclient',
      version='5.1.4665.0.'+build_nbr,
      description='TnT Server Client',
      packages=['tntclient'],
      include_package_data=True,
      install_requires=['requests'])