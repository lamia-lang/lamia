from setuptools import setup, find_packages

setup(
    name="lamia",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        # Core dependencies
        "python-dotenv>=0.19.0",
        "requests>=2.25.0",     # For Ollama API and service checks
        "aiohttp>=3.9.0",      # For async HTTP requests to OpenAI/Anthropic
        "pyyaml>=6.0.0",       # For config file parsing
        "typing-extensions>=4.0.0",  # For enhanced type hints
        "openai>=1.12.0",      # For OpenAI GPT models
        "anthropic>=0.18.1",   # For Anthropic Claude models
        "pydantic>=2.0.0",     # For config validation and object validation
        "beautifulsoup4>=4.12.0",  # For HTML structure validation
        "mistune>=3.0.0",        # For Markdown parsing
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
