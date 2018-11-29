from setuptools import setup

with open("README.md", "r", encoding="utf8") as fh:
    long_description = fh.read()

setup(
    name='SeaLant',
    version='1.0.2',
    packages=['sealant'],
    url='https://pypi.org/project/sealant',
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='LICENSE.md',
    author='ae.udahin',
    author_email='aejudakhin@gmail.com',
    description='Библиотека с инструментом для поиска утечек памяти в процессе выполнения тестов в Chrome или Node.js',
    install_requires=[
        'pychrome >= 0.2.2',
        'requests >= 2.19.1',
        'selenium >= 3.13.0'
    ]
)
