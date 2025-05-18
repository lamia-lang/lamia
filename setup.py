from setuptools import setup, find_packages

setup(
    name="lamia",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        # Core dependencies
        "python-dotenv>=0.19.0",
        "requests>=2.25.0",     # For Ollama API and service checks
        "aiohttp>=3.8.0",      # For async HTTP requests to OpenAI/Anthropic
        "pyyaml>=6.0.0",       # For config file parsing
        "typing-extensions>=4.0.0",  # For enhanced type hints
    ],
    entry_points={
        'console_scripts': [
            'lamia=lamia.cli:main',
        ],
    },
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "isort>=5.0.0",
            "flake8>=4.0.0",
            "pytest-asyncio>=0.18.0",
        ]
    },
    author="Sergey",
    description="A Python project for interpreting and bridging with various LLM APIs",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.8",
)
