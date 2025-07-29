from setuptools import setup, find_packages

setup(
    name="bluesky-feed-summarizer",
    version="1.0.0",
    description="A Python application that reads Bluesky feed and summarizes it using Claude AI",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "atproto>=0.0.61",
        "anthropic>=0.58.2",
        "click>=8.2.1",
        "python-dotenv>=1.1.1",
        "pydantic>=2.11.7",
        "rich>=14.0.0",
    ],
    entry_points={
        "console_scripts": [
            "bluesky-summarizer=bluesky_summarizer.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
