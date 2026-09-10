# MnMS :candy:

MnMS (**M**ultimodal **N**etwork **M**odelling and **S**imulation) is a multimodal dynamic traffic simulator
designed for a large urban scale. It results from all research activities of the ERC MAGnUM project.
Further extensions related to on-demand mobility have been developed with the DIT4TraM project.

MnMS is an agent-based dynamic simulator for urban mobility. Travelers make mode and route choices considering
all multimodal options on the city transportation network, including traditional modes,
such as personal cars or public transportation, and new mobility services, such as ride-hailing,
ride-sharing, or vehicle sharing.
Vehicles motion is governed by regional multimodal MFD (Macroscopic Fundamental Diagram) curves,
so all vehicles of the same type (car, bus, etc.) share the same speed within a specific region at a given time.
The adoption of this traffic flow modelling framework makes it possible to address at large urban scale
timely research topics such as the management of new mobility services (operation, optimization, regulation),
the design of regulatory policies taking into account the multiple stakeholders setting
of today's urban transportation system, and beyond!


## Installation

### From package manager

This installation method is not available yet. Coming soon...


### From sources

1. Download the latest MnMS sources from https://github.com/EMob-Lab/MnMS/archive/refs/heads/main.zip
   or by cloning the git repository:
   ```shell
   git clone https://github.com/EMob-Lab/MnMS.git
   ```

2. From the root directory of the MnMS sources:
   ```shell
   pip install .

   # Optionally, to run the tests:
   pip install --group dev
   pytest
   ```

Remarks: the `--group <group-name>` option requires pip ≥ 25.1. If you have an older version,
the install command above will fail with an error message such as `no such option: --group`.
In this case, try to upgrade pip beforehand with:
```shell
pip install --upgrade pip
```
Alternatively, install the test dependencies `pytest` and `pytest-cov` manually
(or skip the optional test running step).


### HiPOP dependency

MnMS depends on [HiPOP](https://github.com/EMob-Lab/HiPOP.git), the C++ graph library
used under the hood. It is declared as a regular dependency, thus is automatically fetched
from [PyPI](https://pypi.org/project/HiPOP/) when necessary.
**For most users this is transparent**: a prebuilt HiPOP distribution adapted
to your OS / system architecture is downloaded, and no C++ toolchain is required.

Prebuilt distributions are currently provided for the following environments:
- Windows on x86_64 architecture (i.e. Intel/AMD CPU)
- Linux on x86_64 architecture (i.e. Intel/AMD CPU)
- MacOS (≥ 14 Sonoma) on ARM64 architecture (i.e. Apple M* CPU)

If your environment is not covered, the installation fails while fetching HiPOP.
You then need to build HiPOP locally (a C++ toolchain is required; see the
[HiPOP documentation](https://github.com/EMob-Lab/HiPOP#install-from-local-build)),
or contact the package maintainers.


## Tutorials and examples

Tutorials can be found in the `doc/tutorials` directory as jupyter notebooks.
Some simulation examples can be found in the `examples` directory.


## Documentation

### Built

Build the technical documentation using mkdocs with:

```shell
pip install --group doc
mkdocs serve
```


### Detailed

The detailed documentation is available here:
https://github.com/EMob-Lab/MnMS/blob/develop/doc/MnMS_detailed_documentation.pdf
