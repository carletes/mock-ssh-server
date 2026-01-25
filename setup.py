import os

from setuptools import find_packages, setup


def read_requirements():
    ret = []
    fname = os.path.join(os.path.dirname(__file__), "requirements.txt")
    with open(fname, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ret.append(line)
    return ret


def read_long_description():
    with open("README.rst", "r") as f:
        return f.read()


setup(
    name="mock-ssh-server",
    version="0.10.0",
    description="Mock SSH server for testing purposes",
    long_description=read_long_description(),
    url="https://github.com/carletes/mock-ssh-server",
    author="Carlos Valiente",
    author_email="carlos@pepelabs.net",
    license="MIT",
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Testing",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
    package_dir={
        "mockssh": "mockssh",
    },
    packages=find_packages(),
    package_data={
        "mockssh": [
            "sample-user-key",
            "sample-user-key.pub",
            "server-key",
            "server-key.pub",
        ]
    },
    install_requires=read_requirements(),
    zip_safe=False,
)
