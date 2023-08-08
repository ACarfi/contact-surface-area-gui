# Contact surface area GUI

This repository includes the necessary code to create a user interface that can take two meshes in STL format as inputs and calculate the contact area between them.

The GUI also provides a 3D visualization of the contact surface area (CSA) displayed over the two original meshes.

## Instruction to use the GUI

### Executable

To use the GUI you must simply download the executable and run it. The graphical user interface will prompt you to input .STL files that contain triangular meshes. The repository includes two sample meshes that you can use to test the software. The executable as been only tested on Windows 11. Here you find the link to the last release:

https://github.com/ACarfi/contact-surface-area-gui/releases/tag/v.1.0

### Source code

Alternatively, you could download the source code and execute the "gui.py" script

### Compile executable

If you wish to create a new executable, first download the source code and then execute the following command while in the main folder.
```
pyinstaller --clean .\src\build.spec
```
