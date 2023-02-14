import siliconcompiler
from siliconcompiler.targets import utils

def make_docs():
    chip = siliconcompiler.Chip('<target>')
    chip.set('fpga', 'partname', 'ice40up5k-sg48')
    setup(chip)
    return chip

####################################################
# Target Setup
####################################################

def setup(chip):
    '''
    Demonstration target for running the open-source fpgaflow.
    '''

    #1. Load flow
    from flows import fpgaflow
    chip.use(fpgaflow)

    #2. Setup default show tools
    utils.set_common_showtools(chip)

    #3. Select default flow
    chip.set('option', 'mode', 'fpga')
    chip.set('option', 'flow', 'fpgaflow')

#########################
if __name__ == "__main__":
    target = make_docs()
    target.write_manifest('fpgaflow_demo.json')
