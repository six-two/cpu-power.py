# cpu-power.py

View and edit some CPU power saving settings:

- Minimum frequency
- Maximum frequency
- Active cores
- Multithreading / SMT
- Turbo Boost

## Installation

The script needs root permissions to change the CPU settings.
Thus it is recommended to install the package as root:

```
sudo pip install cpu-power.py
```

## Usage

You can view your CPU settings by calling the script without parameters:

```
cpu-power
```

You can also set CPU settings like this (power saving mode):

```
sudo cpu-power set -u 2.2 -d 2.2
```
