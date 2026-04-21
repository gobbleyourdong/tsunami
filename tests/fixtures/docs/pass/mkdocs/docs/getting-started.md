# Getting Started

This guide walks through setting up the project locally. The steps
below assume you have Python 3.10+ and pip available on your PATH.

## Install

Clone the repository and install the requirements in a virtualenv:

```bash
git clone https://example.com/project.git
cd project
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Copy the example config and edit the fields for your environment:

```bash
cp config.example.yaml config.yaml
```

Set the `database_url` and `api_key` fields to values that match
your setup. The remaining fields use sensible defaults.

## Run

Start the local development server:

```bash
python -m project serve
```
