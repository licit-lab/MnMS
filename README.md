# mnms

`mnms` (**M**ultimodal **N**etwork **M**odel**S**) Multimodel simulator for DIT4TraM based on trip-based MFD.

## Installation

### From sources

Using [conda](https://docs.conda.io/en/latest/miniconda.html), create a new environment:

````bash
conda env create -f conda/env.yaml
````

Activate it:
````bash
conda activate mnms
````

Finally install the sources in the activated environment:

````bash
python -m pip install -e .
````


## Tests

To launch tests run the following command at the root of the project:
```bash
pytest tests --cov=mnms -v
```