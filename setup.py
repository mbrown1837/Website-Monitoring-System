from setuptools import setup, find_packages
import os

def read_requirements():
    """Parse requirements.txt for setup.py dependencies."""
    req_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    with open(req_path, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name='WebsiteMonitor',
    version='1.0.0',
    author='Your Name/AI Assistant', # Replace with actual author if desired
    author_email='your_email@example.com', # Replace
    description='An automated website monitoring system.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/your_username/your_project_repo', # Replace with actual URL if hosted
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True, # To include non-code files specified in MANIFEST.in (if created)
    install_requires=read_requirements(),
    entry_points={
        'console_scripts': [
            'website-monitor-cli=main:cli',
            'website-monitor-scheduler=src.scheduler:run_scheduler_main', # Assumes a main guard in scheduler
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta', # Or 5 - Production/Stable if ready
        'Intended Audience :: System Administrators',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License', # Assuming MIT, choose as appropriate
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
) 