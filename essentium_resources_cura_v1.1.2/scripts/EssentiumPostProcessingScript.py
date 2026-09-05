# Copyright (c) 2017 Ghostkeeper
# The PostProcessingPlugin is released under the terms of the AGPLv3 or higher.

import re #To perform the search and replace.

from ..Script import Script
from UM.Application import Application
from cura.Settings.ExtruderManager import ExtruderManager

class EssentiumPostProcessingScript(Script):
    """Performs a search-and-replace on all g-code.

    Due to technical limitations, the search can't cross the border between
    layers.
    """

    def getSettingDataString(self):
        return """{
            "name": "Essentium Post Processing Script",
            "key": "EssentiumPostProcessingScript",
            "metadata": {},
            "version": 2,
            "settings":
            {
                "is_g0_replace":
                {
                    "label": "Replace G0 with G1",
                    "description": "When enabled, all G0 commands will be replaced with G1s",
                    "type": "bool",
                    "default_value": true
                },
                "is_z_split":
                {
                    "label": "Separate Z Movements from X&Y Movements",
                    "description": "When enabled, all movements that contain X, Y, and Z movements will be split into two lines: one for XY movement and one for Z movement",
                    "type": "bool",
                    "default_value": true
                }            
            }
        }"""

    def execute(self, data):
        is_g0_replace = self.getSettingValueByKey("is_g0_replace")
        is_z_split = self.getSettingValueByKey("is_z_split")

        extruders = ExtruderManager.getInstance().getActiveExtruderStacks()
        machine_max_feedrate_z = "{:.0f}".format(60 * extruders[0].getProperty("machine_max_feedrate_z","value"))

        xyz_move_regex = re.compile('(G\d).*(F.*X.*Y.*)\s(Z.*)')


        for layer_number, layer in enumerate(data):
            lines = layer.split("\n")
            for line_number, line in enumerate(lines):
                if is_g0_replace and "G0 " in line:
                    lines[line_number] = re.sub('G0','G1',line)
                if is_z_split and xyz_move_regex.search(line):
                    xyz_search = xyz_move_regex.search(lines[line_number])
                    lines[line_number] = xyz_search.group(1) + " F" + machine_max_feedrate_z + " " + xyz_search.group(3) + "\n" + xyz_search.group(1) + " " + xyz_search.group(2)
            new_layer = "\n".join(lines)
            data[layer_number] = new_layer
        return data
