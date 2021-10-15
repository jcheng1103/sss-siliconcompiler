# Copyright 2020 Silicon Compiler Authors. All Rights Reserved.
import os
import sys
import siliconcompiler
import importlib


if __name__ != "__main__":
    from tests.fixtures import test_wrapper

def test_icarus():


    ydir = (os.path.dirname(os.path.abspath(__file__)) +
            "/../../third_party/designs/oh/stdlib/hdl")

    assert os.path.isdir(ydir), 'third_party/designs/oh submodule not cloned!'

    design = "oh_fifo_sync"
    topfile = ydir + "/" + design + ".v"

    chip = siliconcompiler.Chip(loglevel="INFO")
    chip.set('ydir', ydir)
    chip.set('design', design)
    chip.set('source', topfile)
    chip.set('mode', 'sim')
    chip.set('arg','step','compile')
    chip.target("icarus")
    chip.run()

    # check that compilation succeeded
    assert chip.find_result('vvp', step='compile') is not None

#########################
if __name__ == "__main__":
    test_icarus()
