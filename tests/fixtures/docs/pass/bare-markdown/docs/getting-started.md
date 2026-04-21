# Getting Started

First, install the package:

```bash
pip install example-package
```

Then import it in your Python code:

```python
from example_package import load, process

data = load("input.csv")
result = process(data)
print(result)
```

The default configuration should work for most cases. See the
Architecture page for details on how to customize behavior.

## Troubleshooting

If you see an ImportError, verify your Python version is 3.10 or
newer. The package uses features (PEP 604 syntax, structural
pattern matching) that weren't available in earlier releases.
