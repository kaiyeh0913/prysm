from setuptools import setup

setup(
    name='prysm',
    version='0.5.0',
    description='A python optics module',
    long_description='Uses geometrical and fourier optics to model optical systems',
    license='MIT',
    author='Brandon Dube',
    author_email='brandondube@gmail.com',
    url='https://github.com/brandondube/prysm',
    packages=['prysm'],
    install_requires=['numpy', 'scipy', 'pandas', 'matplotlib'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
    ]
)
