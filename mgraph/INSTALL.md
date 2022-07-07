# Install Mgraph

Mgraph is the C++ graph library used by `mnms`. You must have `CMake` and `make` installed on your computer.

## C++ Only

Inside your conda environment go to the cpp folder, and install the code using cmake:

```shell
cd cpp
mkdir build
cd build
cmake .. -DCMAKE_PREFIX_PATH=$CONDA_PREFIX \
         -DCMAKE_INSTALL_PREFIX=$CONDA_PREFIX \
         -DCMAKE_BUILD_TYPE=Release
make -j install
```

## Python

To install C++ code and python interface just launch the line:
```shell
python setup.py install       
```
You can install C++ code and python interface with wheel too :
```shell
pip install mgraph-*.whl
```