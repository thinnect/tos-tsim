"""tsim_script.py: tossim simulation helper example script"""

__author__ = "Raido Pahtma"
__license__ = "MIT"

def get_simulation_script(simulation):
    return TossimRuntimeScript(simulation)


class TossimRuntimeScript(object):

    def __init__(self, simulation):
        self.simulation = simulation
        self._printed = False

    def tick(self):
        """This function gets called by the simulation loop"""
        if self._printed is False:
            print("This is an example simulation script, current simulation time is %u" % (self.simulation.tossim.time()))
            self._printed = True
