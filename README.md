# MnMS :candy:

MnMS (**M**ultimodal **N**etwork **M**odelling and **S**imulation) is a multimodal dynamic traffic simulator designed for a large urban scale. It results from all research activities of the ERC MAGnUM project. Further extensions related to on-demand mobility have been developped with the DIT4TraM project.

MnMS is an agent-based dynamic simulator for urban mobility. Travelers make mode and route choices considering all multimodal options on the city transportation network, including traditional modes, such as personal cars or public transportation, and new mobility services, such as ride-hailing, ride-sharing, or vehicle sharing. Vehicles motion is governed by regional multimodal MFD (Macroscopic Fundamental Diagram) curves, so all vehicles of the same type (car, bus, etc.) share the same speed within a specific region at a given time. The adoption of this traffic flow modeling framework allows to address at large urban scale timely research topics such as the management of new mobility services (operation, optimization, regulation), the design of regulatory policies taking into account the multiple stakeholders setting of today's urban transportation system, and beyond!

## Installation

### From sources

MnMS relies on [HiPOP](https://github.com/licit-lab/HiPOP.git), make sure to clone it before going through the following installation guidelines.

Using [conda](https://docs.conda.io/en/latest/miniconda.html), create and configure a new environment:

````bash
cd MnMS
conda env create -f conda/env.yaml
````

Activate it:
````bash
conda activate mnms
````

Install the MnMS and HiPOP sources in the activated environment:

````bash
python -m pip install -e .
cd $path_to_HiPOP$/HiPOP/python
python install_cpp.py
python -m pip install .
````

## Tutorials and examples

Tutorials can be found in the doc/tutorials folder as jupyter notebook. Some simulation examples can be found in the examples folder.

## Tests

To launch tests run the following command at the root of the project:
```bash
pytest tests --cov=mnms -v
```

## Documentation

### Built

To build the documentation using mkdocs, first update your conda environment with the doc dependencies:

```bash
conda activate mnms
conda env update --file conda/doc.yaml
```

Then build the doc:

```bash
mkdocs serve 
```

### Detailed 

The detailed documentation is available in the doc folder. 
