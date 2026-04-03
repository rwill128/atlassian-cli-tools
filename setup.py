from setuptools import find_packages, setup


setup(
    name="atlassian-cli-tools",
    version="0.1.0",
    description="Small CLI tools for Jira and Confluence.",
    packages=find_packages(include=["atlassian_cli", "atlassian_cli.*"]),
    entry_points={
        "console_scripts": [
            "tjira=atlassian_cli.jira_cli:main",
            "tconf=atlassian_cli.confluence_cli:main",
        ]
    },
    python_requires=">=3.9",
)
