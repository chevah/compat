from setuptools import Command, find_packages, setup
import os

VERSION = '0.60.0'


class PublishCommand(Command):
    """
    Publish the source distribution to local pypi cache and remote
    Chevah PyPi server.
    """

    description = "copy distributable to Chevah cache folder"
    user_options = []

    def initialize_options(self):
        self.cwd = None
        self.destination_base = '~/chevah/brink/cache/pypi/'

    def finalize_options(self):
        self.cwd = os.getcwd()

    def run(self):
        assert os.getcwd() == self.cwd, (
            'Must be in package root: %s' % self.cwd)
        self.run_command('bdist_wheel')

        upload_command = self.distribution.get_command_obj('upload')
        upload_command.repository = u'chevah'
        self.run_command('upload')


distribution = setup(
    name="chevah-compat",
    version=VERSION,
    maintainer='Adi Roiban',
    maintainer_email='adi.roiban@chevah.com',
    license='BSD 3-Clause',
    platforms='any',
    description="Chevah OS Compatibility Layer.",
    long_description=open('README.rst').read(),
    url='http://www.chevah.com',
    namespace_packages=['chevah'],
    packages=find_packages('.'),
    scripts=['scripts/nose_runner.py'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        ],
    cmdclass={
        'publish': PublishCommand,
        },
    )
