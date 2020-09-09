# Amara 3 Core

Core of Amara3 project, which contains a variety of data processing tools, is a module for handling Internationalized Resource Identifiers (IRIs)

Uche Ogbuji
uche@ogbuji.net

## Install

Requires Python 3.5+. Just run:

```
pip install amara3.iri
```

## Quick note on project structure

This and related projects follows my long-standing opinions on, and so does not
go with the convention of putting the Python library source in a subdirectory
that in some way is mean to match the project or installed package name.
I admit that more packages use this latter approach, largely because some
influential tools preferred it and tutorials adopted it, but I stick to my
position that using "src", "lib" or better yet "pylib" better serves the
actual meaning of the library directory within a project, as evidenced by
the simple example of a package whose content includes implementations
in other languages as well as Python. That's enough om this from me, but
I'll just leave a couple of references for anyone interested:

* https://hynek.me/articles/testing-packaging/
* https://docs.pytest.org/en/latest/goodpractices.html

Note: The PyPA/Python Packaging SIG has [instructions for such src-like layouts](https://setuptools.readthedocs.io/en/latest/setuptools.html#using-a-src-layout) which include an extra mypackage layer.
This structure does make sense and the minor shift to that might be in order at some point.

